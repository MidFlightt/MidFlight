"""Escalations: conflicts only the lead can decide (UC-12, UC-13, INV-11).

A review that finds a conflict between people's requirements opens an escalation
(`ClaimService.run_review`). The lead resolves it here, one of three ways:

- `clarify_plan`: the lead approved a plan version that settles the question. The
  involved claims are reviewed again; they cite the old version, so their agents are
  asked to revise against the clarified plan.
- `request_revision`: the involved claims go to `needs_revision`, and each agent gets
  a directive carrying the lead's decision.
- `dismiss`: not a real conflict. The involved claims are reviewed again, and the
  dismissed conflict is set aside (kept as an `info` finding, not blocking).

Midflight records who decided and why, and keeps the original finding.

The lead can also overturn something Midflight settled without them (D31): a technical
decision by the AI reviewer, or an assumption recorded as agreed. `request_revision`
replaces it with the lead's own ruling; `dismiss` withdraws it.
"""

from __future__ import annotations

from midflight.domain.models import (
    Claim,
    ClaimState,
    Directive,
    DirectiveSource,
    Entity,
    Escalation,
    EscalationState,
    Job,
    JobKind,
    Participant,
    Resolution,
    Role,
)
from midflight.domain.states import ACTIVE_CLAIM_STATES, move_claim
from midflight.ports import Clock, Commit, JobRunner, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.claims import review_subject
from midflight.services.decisions import MIDFLIGHT, revision_requests
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict


class EscalationService:
    def __init__(self, store: Store, clock: Clock, runner: JobRunner) -> None:
        self._store = store
        self._clock = clock
        self._runner = runner

    def resolve(
        self, lead: Participant, escalation_id: str, resolution: Resolution, reason: str
    ) -> Escalation:
        if lead.role is not Role.LEAD:
            raise PermissionDenied("only the lead resolves escalations (INV-08)")
        if not reason.strip():
            raise InvalidRequest("resolving an escalation needs a reason")
        escalation = self._store.get_escalation(escalation_id)
        if escalation is None or escalation.project_id != lead.project_id:
            raise NotFound(f"no escalation {escalation_id}")
        project = self._store.get_project(lead.project_id)
        assert project is not None and project.current_plan_version is not None
        version = project.current_plan_version
        claims = [self._store.get_claim(cid) for cid in escalation.claim_ids]
        if escalation.state is not EscalationState.OPEN:
            if escalation.resolved_by != MIDFLIGHT:
                raise StateConflict(f"escalation {escalation_id} is already resolved")
            involved = [c for c in claims if c and c.state in ACTIVE_CLAIM_STATES]
            return self._overturn(lead, escalation, involved, version, resolution, reason)

        waiting = [c for c in claims if c and c.state is ClaimState.HUMAN_REVIEW_REQUIRED]
        if resolution is Resolution.CLARIFY_PLAN and all(
            c.plan_version >= version for c in waiting
        ):
            raise StateConflict(
                "the plan hasn't changed since these claims were written",
                "Propose and approve a plan version that settles the question first, then "
                "resolve with clarify_plan. Or use request_revision or dismiss.",
            )

        now = self._clock.now()
        correlation_id = new_correlation_id()
        puts: list[Entity] = []
        jobs: list[Job] = []
        if resolution is Resolution.REQUEST_REVISION:
            puts += revision_requests(
                self._store, self._clock, escalation, waiting, version, reason, lead.id
            )
        for claim in waiting:
            if resolution is not Resolution.REQUEST_REVISION:
                job = Job(
                    id=self._store.next_id(project.id, "J"),
                    project_id=project.id,
                    kind=JobKind.CLAIM_REVIEW,
                    subject_id=review_subject(claim.id, claim.revision),
                    idempotency_key=f"escalation:{escalation.id}:{claim.id}:{claim.revision}",
                    correlation_id=correlation_id,
                    created_at=now,
                    updated_at=now,
                )
                puts += [move_claim(claim, ClaimState.PENDING), job]
                jobs.append(job)

        resolved = Escalation.model_validate(
            escalation.model_dump()
            | {
                "state": EscalationState.RESOLVED,
                "resolution": resolution,
                "resolved_by": lead.id,
                "reason": reason,
                "resolved_at": now,
            }
        )
        key = f"resolve:{escalation.id}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor=lead.id,
            action=f"escalation.{resolution}",
            entity_ids=[escalation.id, *(c.id for c in waiting)],
            reason=reason,
            correlation_id=correlation_id,
            idempotency_key=key,
            versions={"plan": version},
        )
        self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=key,
                puts=[resolved, *puts],
                audit=[event],
                bump_coord_rev=True,
            )
        )
        for job in jobs:
            self._runner.submit(job)
        return resolved

    def _overturn(
        self,
        lead: Participant,
        escalation: Escalation,
        involved: list[Claim],
        version: int,
        resolution: Resolution,
        reason: str,
    ) -> Escalation:
        """Replace or withdraw something Midflight settled without the lead."""
        if resolution is Resolution.CLARIFY_PLAN:
            raise InvalidRequest(
                "Midflight already settled this one",
                "Overturn it with request_revision (your own ruling) or dismiss (withdraw it).",
            )
        now = self._clock.now()
        puts: list[Entity] = []
        if resolution is Resolution.REQUEST_REVISION:
            puts += revision_requests(
                self._store, self._clock, escalation, involved, version, reason, lead.id
            )
        else:
            puts += [
                Directive(
                    id=self._store.next_id(escalation.project_id, "D"),
                    project_id=escalation.project_id,
                    source=DirectiveSource.PLAN_CHANGE,
                    task_id=claim.task_id,
                    recipient_id=claim.agent_id,
                    plan_version=version,
                    requested_adjustment=f"The lead withdrew {escalation.id} "
                    f"({escalation.reason!r}): {reason} It no longer applies. If you changed "
                    f"claim {claim.id} because of it, revise the claim again.",
                    reason=escalation.explanation,
                    created_at=now,
                )
                for claim in involved
            ]
        overturned = Escalation.model_validate(
            escalation.model_dump()
            | {
                "resolution": resolution,
                "resolved_by": lead.id,
                "reason": reason,
                "resolved_at": now,
            }
        )
        key = f"overturn:{escalation.id}:{new_correlation_id()}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=escalation.project_id,
            actor=lead.id,
            action=f"escalation.overturned.{resolution}",
            entity_ids=[escalation.id, *(c.id for c in involved)],
            reason=f"was {escalation.reason!r} (by {escalation.resolved_by}); now: {reason}",
            correlation_id=new_correlation_id(),
            idempotency_key=key,
            versions={"plan": version},
        )
        self._store.commit(
            Commit(
                project_id=escalation.project_id,
                idempotency_key=key,
                puts=[overturned, *puts],
                audit=[event],
                bump_coord_rev=True,
            )
        )
        return overturned
