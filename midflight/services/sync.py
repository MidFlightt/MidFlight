"""Whether Midflight's GitHub data is fresh (UC-15, INV-09).

When GitHub is down or rate-limiting, verification marks the project `stale`. While
it's stale, new directives are held (`check_in` doesn't deliver them) and no claim is
approved (`decide_claim` keeps it `pending`). When GitHub answers again, the project is
marked `fresh`, and the claims that were held `pending` are reviewed again.

For the demo, the lead can flip a labeled fault switch (`simulate_github_outage`): it
marks the project stale and makes verification fail exactly as if GitHub were down.
"""

from __future__ import annotations

from midflight.domain.models import (
    ClaimState,
    Job,
    JobKind,
    Participant,
    Project,
    Role,
    SyncState,
)
from midflight.ports import Clock, Commit, JobRunner, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.claims import review_subject
from midflight.services.errors import NotFound, PermissionDenied

FAULT_SWITCH = "fault"  # kind of the auth-store record that turns the switch on
FAULT_REASON = "GitHub unavailable (demo fault switch)"


class SyncService:
    def __init__(self, store: Store, clock: Clock, runner: JobRunner) -> None:
        self._store = store
        self._clock = clock
        self._runner = runner

    def mark_stale(self, project_id: str, reason: str) -> None:
        project = self._project(project_id)
        if project.sync_state is SyncState.STALE:
            return
        stale = Project.model_validate(
            project.model_dump() | {"sync_state": SyncState.STALE, "sync_reason": reason}
        )
        self._save(stale, "project.stale", reason)

    def mark_fresh(self, project_id: str, actor: str = "midflight") -> None:
        """GitHub answers again: clear the flag and review the held claims again."""
        project = self._project(project_id)
        if project.sync_state is SyncState.FRESH:
            return
        now = self._clock.now()
        fresh = Project.model_validate(
            project.model_dump()
            | {"sync_state": SyncState.FRESH, "sync_reason": None, "last_synced_at": now}
        )
        held = [c for c in self._store.list_claims(project_id) if c.state is ClaimState.PENDING]
        correlation_id = new_correlation_id()
        jobs = [
            Job(
                id=self._store.next_id(project_id, "J"),
                project_id=project_id,
                kind=JobKind.CLAIM_REVIEW,
                subject_id=review_subject(c.id, c.revision),
                idempotency_key=f"reconcile:{c.id}:{c.revision}:{project.coord_rev}",
                correlation_id=correlation_id,
                created_at=now,
                updated_at=now,
            )
            for c in held
        ]
        reason = f"GitHub answers again; {len(jobs)} held claim(s) reviewed again"
        self._save(fresh, "project.fresh", reason, actor=actor, jobs=jobs)
        for job in jobs:
            self._runner.submit(job)

    def fault_on(self, project_id: str) -> bool:
        return self._store.get_auth(FAULT_SWITCH, project_id) is not None

    def set_fault(self, lead: Participant, on: bool) -> None:
        """The demo fault switch. Lead only, and only for the lead's own project."""
        if lead.role is not Role.LEAD:
            raise PermissionDenied("only the lead can use the fault switch")
        if on:
            when = self._clock.now().isoformat()
            self._store.put_auth(FAULT_SWITCH, lead.project_id, {"by": lead.id, "at": when})
            self.mark_stale(lead.project_id, FAULT_REASON)
        else:
            self._store.delete_auth(FAULT_SWITCH, lead.project_id)
            self.mark_fresh(lead.project_id, actor=lead.id)

    def _project(self, project_id: str) -> Project:
        project = self._store.get_project(project_id)
        if project is None:
            raise NotFound(f"no project {project_id}")
        return project

    def _save(
        self,
        project: Project,
        action: str,
        reason: str,
        actor: str = "midflight",
        jobs: list[Job] | None = None,
    ) -> None:
        key = f"{action}:{project.id}:{new_correlation_id()}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor=actor,
            action=action,
            entity_ids=[project.id],
            reason=reason,
            correlation_id=new_correlation_id(),
            idempotency_key=key,
        )
        self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=key,
                puts=[project, *(jobs or [])],
                audit=[event],
                bump_coord_rev=True,
            )
        )
