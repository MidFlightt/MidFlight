"""`check_in`: what an agent needs at a checkpoint (UC-07, UC-16, FR-07).

The reply carries the task's plan context (requirements and the contracts it provides
or consumes), the agent's current claim verdict, and open directives. Directives still
`queued` are marked `delivered` by being returned, unless GitHub data is stale, in
which case they're held (INV-09). `ready_to_push` is what the pre-push hook checks.

It also carries what the plan can't: what other tasks' claims assume about this one
(D27), the escalations the lead hasn't decided yet (D28), and the decisions already made
(D30, D31). An agent sees the ones its claim is part of. The lead sees every open
escalation, and everything Midflight settled without them, so they can overturn it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from midflight.domain.models import (
    Claim,
    ClaimState,
    Contract,
    Directive,
    DirectiveState,
    Escalation,
    EscalationState,
    Participant,
    Plan,
    Requirement,
    Role,
    SyncState,
    Task,
)
from midflight.domain.neighbours import NeighbourAssumption, assumptions_about
from midflight.domain.states import (
    ACTIVE_CLAIM_STATES,
    OPEN_DIRECTIVE_STATES,
    move_directive,
)
from midflight.ports import Clock, Commit, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.claims import ClaimService, Verdict
from midflight.services.decisions import MIDFLIGHT, decisions_in_force
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict


@dataclass(frozen=True)
class CheckIn:
    plan_version: int
    task: Task
    requirements: Sequence[Requirement]
    contracts: Sequence[Contract]
    claim: Verdict | None
    directives: Sequence[Directive]
    delivered_now: Sequence[str]
    changed: bool
    stale: bool
    stale_reason: str | None
    ready_to_push: bool
    push_blockers: Sequence[str]
    assumed_by_others: Sequence[NeighbourAssumption] = ()
    escalations: Sequence[Escalation] = ()
    you_decide: bool = False  # the escalations are the lead's own to resolve
    decisions: Sequence[Escalation] = ()


class CheckInService:
    def __init__(self, store: Store, clock: Clock, claims: ClaimService) -> None:
        self._store = store
        self._clock = clock
        self._claims = claims

    def check_in(self, actor: Participant, task_id: str | None = None) -> CheckIn:
        if not actor.active:
            raise PermissionDenied("you were removed from this project")
        project = self._store.get_project(actor.project_id)
        if project is None:
            raise NotFound(f"no project {actor.project_id}")
        if project.current_plan_version is None:
            raise StateConflict("no plan has been approved yet", "The lead approves plan v1.")
        plan = self._store.get_plan(project.id, project.current_plan_version)
        assert plan is not None
        task = self._task(plan, actor, task_id)
        stale = project.sync_state is SyncState.STALE

        # Queued directives are delivered by this reply, or held while stale (INV-09).
        stored = self._store.list_directives(project.id, task.id)
        delivered_now = (
            []
            if stale
            else [move_directive(d, DirectiveState.DELIVERED) for d in stored if _queued(d)]
        )
        delivered_ids = {d.id for d in delivered_now}
        updated = {d.id: d for d in delivered_now}
        directives = [
            updated.get(d.id, d)
            for d in stored
            if d.state in OPEN_DIRECTIVE_STATES and (not _queued(d) or d.id in delivered_ids)
        ]

        cursor = actor.model_copy(
            update={
                "last_check_in_at": self._clock.now(),
                "last_check_in_rev": project.coord_rev,
            }
        )
        key = f"check-in:{actor.id}:{new_correlation_id()}"
        audit = (
            [
                audit_event(
                    self._store,
                    self._clock,
                    project_id=project.id,
                    actor=actor.id,
                    action="directive.delivered",
                    entity_ids=sorted(delivered_ids),
                    reason=f"returned to {task.id} at check-in",
                    correlation_id=new_correlation_id(),
                    idempotency_key=key,
                    versions={"plan": plan.version},
                )
            ]
            if delivered_now
            else []
        )
        self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=key,
                puts=[cursor, *delivered_now],
                audit=audit,
            )
        )

        claims = self._store.list_claims(project.id)
        claim = _current_claim(claims, actor, task.id)
        verdict = self._claims.verdict(claim.id, claim.revision) if claim else None
        blockers = _push_blockers(claim, directives)
        lead = actor.role is Role.LEAD
        escalations = self._store.list_escalations(project.id)
        undecided = [
            e
            for e in escalations
            if e.state is EscalationState.OPEN
            and (lead or (claim is not None and claim.id in e.claim_ids))
        ]
        # An agent builds to the decisions its claim is part of. The lead reviews what
        # Midflight settled on its own.
        decisions = [
            d
            for d in decisions_in_force(escalations, claims)
            if (lead and d.resolved_by == MIDFLIGHT)
            or (claim is not None and claim.id in d.claim_ids)
        ]
        return CheckIn(
            plan_version=plan.version,
            task=task,
            requirements=[r for r in plan.requirements if r.id in task.requirement_ids],
            contracts=[
                c for c in (plan.contract(i) for i in (*task.provides, *task.consumes)) if c
            ],
            claim=verdict,
            directives=directives,
            delivered_now=sorted(delivered_ids),
            changed=actor.last_check_in_rev != project.coord_rev,
            stale=stale,
            stale_reason=project.sync_reason if stale else None,
            ready_to_push=not blockers,
            push_blockers=blockers,
            assumed_by_others=assumptions_about(task, claim.files if claim else [], claims),
            escalations=undecided,
            you_decide=lead,
            decisions=decisions,
        )

    def _task(self, plan: Plan, actor: Participant, task_id: str | None) -> Task:
        if task_id is None:
            owned = [t for t in plan.tasks if t.owner == actor.id]
            if not owned:
                raise InvalidRequest(f"no task in plan v{plan.version} is assigned to you")
            return owned[0]
        task = plan.task(task_id)
        if task is None:
            raise InvalidRequest(
                f"plan v{plan.version} has no task {task_id}",
                "Use one of: " + ", ".join(t.id for t in plan.tasks) + ".",
            )
        if task.owner != actor.id:
            raise PermissionDenied(
                f"task {task_id} belongs to another agent",
                "Your own check-in already lists every contract your task uses (Q3).",
            )
        return task


def _current_claim(claims: Sequence[Claim], actor: Participant, task_id: str) -> Claim | None:
    mine = [c for c in claims if c.task_id == task_id and c.agent_id == actor.id]
    active = [c for c in mine if c.state in ACTIVE_CLAIM_STATES]
    pool = active or mine
    return max(pool, key=lambda c: c.created_at) if pool else None


def _queued(directive: Directive) -> bool:
    return directive.state is DirectiveState.QUEUED


def _push_blockers(claim: Claim | None, directives: Sequence[Directive]) -> list[str]:
    blockers = []
    if claim is None:
        blockers.append("no claim for this task; submit one before pushing")
    elif claim.state is not ClaimState.APPROVED:
        # A plan change sends affected approvals back for review (UC-08 step 3), so an
        # approval on an older plan version is still valid for an unaffected task.
        blockers.append(f"claim {claim.id} is {claim.state}, not approved")
    for directive in directives:
        if directive.blocking:
            blockers.append(f"directive {directive.id} is {directive.state}; answer it first")
    return blockers
