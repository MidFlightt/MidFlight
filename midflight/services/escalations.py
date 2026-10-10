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
"""

from __future__ import annotations

from midflight.domain.models import (
    ClaimState,
    Directive,
    DirectiveSource,
    DirectiveState,
    Entity,
    Escalation,
    EscalationState,
    Job,
    JobKind,
    Participant,
    Resolution,
    Role,
)
from midflight.domain.states import SUPERSEDABLE_DIRECTIVE_STATES, move_claim, move_directive
from midflight.ports import Clock, Commit, JobRunner, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.claims import review_subject
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
        if escalation.state is not EscalationState.OPEN:
            raise StateConflict(f"escalation {escalation_id} is already resolved")
        project = self._store.get_project(lead.project_id)
        assert project is not None and project.current_plan_version is not None
        version = project.current_plan_version

        claims = [self._store.get_claim(cid) for cid in escalation.claim_ids]
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
        directives = self._store.list_directives(project.id)
        for claim in waiting:
            if resolution is Resolution.REQUEST_REVISION:
                puts.append(move_claim(claim, ClaimState.NEEDS_REVISION))
                puts += [
                    move_directive(d, DirectiveState.SUPERSEDED)
                    for d in directives
                    if d.task_id == claim.task_id and d.state in SUPERSEDABLE_DIRECTIVE_STATES
                ]
                puts.append(
                    Directive(
                        id=self._store.next_id(project.id, "D"),
                        project_id=project.id,
                        source=DirectiveSource.PLAN_CHANGE,
                        task_id=claim.task_id,
                        recipient_id=claim.agent_id,
                        plan_version=version,
                        changed_ids=escalation.competing_requirement_ids,
                        requested_adjustment=f"The lead decided escalation {escalation.id}: "
                        f"{reason} Revise claim {claim.id} to match, then submit it again.",
                        reason=escalation.explanation,
                        created_at=now,
                    )
                )
            else:
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
