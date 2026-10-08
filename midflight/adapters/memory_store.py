"""An in-memory Store for tests and laptops. DynamoStore (M-5) must behave the same.

One lock guards everything, so a commit is atomic and the coord_rev compare-and-set
can't interleave with another commit (INV-02).
"""

from __future__ import annotations

import threading
from collections import defaultdict

from midflight.domain.models import (
    AuditEvent,
    Claim,
    Directive,
    Entity,
    Escalation,
    Job,
    Participant,
    Plan,
    PlanStatus,
    Project,
    Verification,
)
from midflight.ports import Commit, CommitResult, RevisionConflict

# The parts of a saved claim revision that may still change: its verdict.
_CLAIM_VERDICT_FIELDS = {"state", "findings"}


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._projects: dict[str, Project] = {}
        self._participants: dict[str, Participant] = {}
        self._plans: dict[tuple[str, int], Plan] = {}
        self._claims: dict[str, dict[int, Claim]] = {}
        self._directives: dict[str, Directive] = {}
        self._escalations: dict[str, Escalation] = {}
        self._verifications: dict[str, Verification] = {}
        self._jobs: dict[str, Job] = {}
        self._audit: list[AuditEvent] = []
        self._applied: dict[str, int] = {}
        self._counters: dict[tuple[str, str], int] = defaultdict(int)

    # Writes ----------------------------------------------------------------------------

    def commit(self, commit: Commit) -> CommitResult:
        with self._lock:
            if commit.idempotency_key in self._applied:
                rev = self._applied[commit.idempotency_key]
                return CommitResult(applied=False, duplicate=True, coord_rev=rev)

            stored = self._projects.get(commit.project_id)
            if commit.expected_coord_rev is not None:
                actual = stored.coord_rev if stored else 0
                if actual != commit.expected_coord_rev:
                    raise RevisionConflict(commit.expected_coord_rev, actual)

            project = stored
            for entity in commit.puts:
                if isinstance(entity, Project):
                    # Only bump_coord_rev changes coord_rev; a project read earlier must
                    # not roll it back.
                    rev = stored.coord_rev if stored else entity.coord_rev
                    project = entity.model_copy(update={"coord_rev": rev})
            if project is None:
                raise LookupError(f"unknown project {commit.project_id}")
            for entity in commit.puts:
                self._check(commit.project_id, entity)

            for entity in commit.puts:
                if not isinstance(entity, Project):
                    self._put(entity)
            if commit.bump_coord_rev:
                project = project.model_copy(update={"coord_rev": project.coord_rev + 1})
            self._projects[project.id] = project
            self._audit.extend(commit.audit)
            self._applied[commit.idempotency_key] = project.coord_rev
            return CommitResult(applied=True, duplicate=False, coord_rev=project.coord_rev)

    def next_id(self, project_id: str, prefix: str) -> str:
        with self._lock:
            self._counters[(project_id, prefix)] += 1
            return f"{prefix}-{self._counters[(project_id, prefix)]}"

    def _check(self, project_id: str, entity: Entity) -> None:
        """Refuse invalid data and writes that would rewrite history, before saving anything.

        `model_copy(update=...)` skips validation, so every entity is checked again here.
        """
        type(entity).model_validate(entity.model_dump())
        owner = entity.id if isinstance(entity, Project) else entity.project_id
        if owner != project_id:
            raise ValueError(f"{type(entity).__name__} belongs to {owner}, not {project_id}")
        if isinstance(entity, Plan):
            saved = self._plans.get((entity.project_id, entity.version))
            if saved is not None and saved.status is PlanStatus.APPROVED and saved != entity:
                raise ValueError(f"plan v{entity.version} is approved and can't change")
        if isinstance(entity, Claim):
            saved_claim = self._claims.get(entity.id, {}).get(entity.revision)
            if saved_claim is not None:
                before = saved_claim.model_dump(exclude=_CLAIM_VERDICT_FIELDS)
                if before != entity.model_dump(exclude=_CLAIM_VERDICT_FIELDS):
                    raise ValueError(
                        f"claim {entity.id} rev {entity.revision} is saved; submit a new "
                        "revision instead of editing it"
                    )

    def _put(self, entity: Entity) -> None:
        match entity:
            case Participant():
                self._participants[entity.id] = entity
            case Plan():
                self._plans[(entity.project_id, entity.version)] = entity
            case Claim():
                self._claims.setdefault(entity.id, {})[entity.revision] = entity
            case Directive():
                self._directives[entity.id] = entity
            case Escalation():
                self._escalations[entity.id] = entity
            case Verification():
                self._verifications[entity.id] = entity
            case Job():
                self._jobs[entity.id] = entity
            case _:
                raise TypeError(f"can't store {type(entity).__name__}")

    # Reads -----------------------------------------------------------------------------

    def get_project(self, project_id: str) -> Project | None:
        with self._lock:
            return self._projects.get(project_id)

    def get_participant(self, participant_id: str) -> Participant | None:
        with self._lock:
            return self._participants.get(participant_id)

    def find_participant_by_token_hash(self, token_hash: str) -> Participant | None:
        with self._lock:
            return next(
                (p for p in self._participants.values() if p.token_hash == token_hash), None
            )

    def list_participants(self, project_id: str) -> list[Participant]:
        with self._lock:
            return [p for p in self._participants.values() if p.project_id == project_id]

    def get_plan(self, project_id: str, version: int) -> Plan | None:
        with self._lock:
            return self._plans.get((project_id, version))

    def list_plans(self, project_id: str) -> list[Plan]:
        with self._lock:
            plans = [p for (pid, _), p in self._plans.items() if pid == project_id]
            return sorted(plans, key=lambda p: p.version)

    def get_claim(self, claim_id: str, revision: int | None = None) -> Claim | None:
        with self._lock:
            revisions = self._claims.get(claim_id)
            if not revisions:
                return None
            if revision is None:
                return revisions[max(revisions)]
            return revisions.get(revision)

    def claim_history(self, claim_id: str) -> list[Claim]:
        with self._lock:
            revisions = self._claims.get(claim_id, {})
            return [revisions[r] for r in sorted(revisions)]

    def list_claims(self, project_id: str) -> list[Claim]:
        with self._lock:
            latest = (revs[max(revs)] for revs in self._claims.values())
            return [c for c in latest if c.project_id == project_id]

    def get_directive(self, directive_id: str) -> Directive | None:
        with self._lock:
            return self._directives.get(directive_id)

    def list_directives(self, project_id: str, task_id: str | None = None) -> list[Directive]:
        with self._lock:
            return [
                d
                for d in self._directives.values()
                if d.project_id == project_id and (task_id is None or d.task_id == task_id)
            ]

    def get_escalation(self, escalation_id: str) -> Escalation | None:
        with self._lock:
            return self._escalations.get(escalation_id)

    def list_escalations(self, project_id: str) -> list[Escalation]:
        with self._lock:
            return [e for e in self._escalations.values() if e.project_id == project_id]

    def get_verification(self, verification_id: str) -> Verification | None:
        with self._lock:
            return self._verifications.get(verification_id)

    def list_verifications(self, project_id: str) -> list[Verification]:
        with self._lock:
            return [v for v in self._verifications.values() if v.project_id == project_id]

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, project_id: str) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs.values() if j.project_id == project_id]

    def list_audit(self, project_id: str, entity_id: str | None = None) -> list[AuditEvent]:
        with self._lock:
            return [
                e
                for e in self._audit
                if e.project_id == project_id and (entity_id is None or entity_id in e.entity_ids)
            ]
