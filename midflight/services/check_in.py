"""`check_in`: what an agent needs at a checkpoint (UC-07, UC-16, FR-07).

The reply carries the task's plan context (requirements and the contracts it provides
or consumes), the agent's current claim verdict, and open directives. Directives still
`queued` are marked `delivered` by being returned, unless GitHub data is stale, in
which case they're held (INV-09). `ready_to_push` is what the pre-push hook checks.

It also carries what the plan can't: what other tasks' claims assume about this one
(D27), the escalations the lead hasn't decided yet (D28), and the decisions already made
(D30, D31). An agent sees the ones its claim is part of. The lead sees every open
escalation, and everything Midflight settled without them, so they can overturn it.

Everything a reply carries stays in the agent's context and is paid for again on each
later step. So each reply carries a marker, and an agent that passes it back as `since`
is told what that earlier reply already held and hasn't changed (D34): the task's
requirements and contracts, decisions, and neighbours' assumptions. The connector
leaves those out. The marker travels with the conversation, not the account, so two
sessions signed in as one person never hide anything from each other, and a session
that lost its context simply sends no marker and gets everything.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
from midflight.domain.neighbours import MAX_LENGTH, NeighbourAssumption, assumptions_about
from midflight.domain.states import (
    ACTIVE_CLAIM_STATES,
    OPEN_DIRECTIVE_STATES,
    move_directive,
)
from midflight.ports import Clock, Commit, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.claims import ClaimService, Verdict
from midflight.services.decisions import MIDFLIGHT, decisions_in_force, is_agreement
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
    # To pass back as `since` at the next check-in.
    marker: str = ""
    since_read: bool = False  # the caller's `since` named an earlier check-in on this task
    # What the check-in that gave out `since` already held, unchanged since (D34).
    plan_seen: bool = False  # the task's requirements and contracts
    # The requirements and contracts that are new or different since then; None when
    # that check-in can't be compared with this one.
    plan_changed_ids: Sequence[str] | None = None
    seen_decision_ids: Collection[str] = ()
    seen_assumptions: Collection[NeighbourAssumption] = ()


# Anything saved this close to a check-in may have missed its reply, so it is sent again.
MARKER_SLACK = timedelta(seconds=5)
MARKER_FORMAT = "%Y%m%dT%H%M%SZ"


def marker_for(task_id: str, at: datetime) -> str:
    """Names one check-in on one task: `T3.20261011T011233Z`."""
    return f"{task_id}.{at.astimezone(UTC).strftime(MARKER_FORMAT)}"


def read_marker(marker: str | None, task_id: str, now: datetime) -> datetime | None:
    """When the check-in that gave out `marker` happened, less the slack. None for no
    marker, another task's, one from the future, or anything unreadable: the agent is
    then sent everything, which is always safe."""
    task, _, stamp = (marker or "").strip().rpartition(".")
    if task != task_id:
        return None
    try:
        at = datetime.strptime(stamp, MARKER_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None
    return at - MARKER_SLACK if at <= now else None


class CheckInService:
    def __init__(self, store: Store, clock: Clock, claims: ClaimService) -> None:
        self._store = store
        self._clock = clock
        self._claims = claims

    def check_in(
        self,
        actor: Participant,
        task_id: str | None = None,
        peek: bool = False,
        since: str | None = None,
    ) -> CheckIn:
        """`since` is the marker of an earlier reply the agent still has.

        `peek` is for a caller that shows the agent only part of the reply (the open
        directives, the push blockers). It doesn't count as a check-in."""
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

        now = self._clock.now()
        cursor = actor.model_copy(
            update={"last_check_in_at": now, "last_check_in_rev": project.coord_rev}
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
        puts = [*delivered_now] if peek else [cursor, *delivered_now]
        if puts:
            self._store.commit(
                Commit(project_id=project.id, idempotency_key=key, puts=puts, audit=audit)
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
        # An assumption recorded as agreed is listed once, with the decisions.
        agreed = {d.reason[:MAX_LENGTH] for d in decisions if is_agreement(d)}
        assumed = [
            a
            for a in assumptions_about(task, claim.files if claim else [], claims)
            if a.text not in agreed
        ]
        had = read_marker(since, task.id, now)
        changed_in_plan = self._plan_changes(plan, task, had)
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
            assumed_by_others=assumed,
            escalations=undecided,
            you_decide=lead,
            decisions=decisions,
            marker=marker_for(task.id, now),
            since_read=had is not None,
            plan_seen=changed_in_plan == [],
            plan_changed_ids=changed_in_plan,
            seen_decision_ids=self._seen_decisions(decisions, claim, lead, had),
            seen_assumptions=self._seen_assumptions(assumed, claims, had),
        )

    def _plan_changes(self, plan: Plan, task: Task, since: datetime | None) -> list[str] | None:
        """The task's requirements and contracts that the plan in force at `since` didn't
        have as they are now, and the ones it had that are gone. Empty when nothing
        differs: a new plan version that left the task alone (another task was
        reassigned, say) changes nothing here. None when there is nothing to compare
        with: no marker, no plan then, or the task wasn't this owner's or had another
        title."""
        if since is None:
            return None
        earlier = [
            p
            for p in self._store.list_plans(plan.project_id)
            if p.approved_at is not None and p.approved_at < since
        ]
        if not earlier:
            return None
        now, then = _context(plan, task), _context(max(earlier, key=lambda p: p.version), task)
        if now is None or then is None:
            return None
        different = [i for i, content in now.items() if then.get(i) != content]
        return [*different, *(i for i in then if i not in now)]

    def _seen_decisions(
        self,
        decisions: Sequence[Escalation],
        claim: Claim | None,
        lead: bool,
        since: datetime | None,
    ) -> list[str]:
        """Decisions made before the agent's last check-in, which listed them."""
        if since is None:
            return []
        if not lead:
            # An agent is shown the decisions its claim is part of: none before it had one.
            first = self._store.claim_history(claim.id)[:1] if claim else []
            if not first or first[0].created_at >= since:
                return []
        return [d.id for d in decisions if d.resolved_at is not None and d.resolved_at < since]

    def _seen_assumptions(
        self,
        assumed: Sequence[NeighbourAssumption],
        claims: Sequence[Claim],
        since: datetime | None,
    ) -> list[NeighbourAssumption]:
        """Assumptions the neighbour's claim already stated at the agent's last check-in."""
        if since is None:
            return []
        latest = {c.id: c for c in claims}
        stated: dict[str, set[str]] = {}
        for claim_id in {a.claim_id for a in assumed}:
            claim = latest[claim_id]
            if claim.created_at >= since:
                # Revised since: only what the revision before it also said is old news.
                earlier = [c for c in self._store.claim_history(claim_id) if c.created_at < since]
                if not earlier:
                    continue
                claim = earlier[-1]
            stated[claim_id] = {text[:MAX_LENGTH] for text in claim.assumptions}
        return [a for a in assumed if a.text in stated.get(a.claim_id, ())]

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


def _context(plan: Plan, like: Task) -> dict[str, object] | None:
    """What a check-in says about a task from the plan alone: each requirement and
    contract by id, in a form that compares."""
    task = plan.task(like.id)
    if task is None or task.owner != like.owner or task.title != like.title:
        return None
    requirements = [r for r in plan.requirements if r.id in task.requirement_ids]
    contracts = [c for c in (plan.contract(i) for i in (*task.provides, *task.consumes)) if c]
    # A contract's version follows the plan's, so it changes when nothing else does.
    return {r.id: r.model_dump(mode="json") for r in requirements} | {
        c.id: c.model_dump(mode="json", exclude={"version"}) for c in contracts
    }


def _current_claim(claims: Sequence[Claim], actor: Participant, task_id: str) -> Claim | None:
    """The agent's claim for this task: the active one, else the last one it closed.

    A withdrawn claim isn't shown. The agent gave it up, so for this task it has no claim,
    and its old verdict and findings would only mislead whoever picks the task up next.
    """
    mine = [c for c in claims if c.task_id == task_id and c.agent_id == actor.id]
    active = [c for c in mine if c.state in ACTIVE_CLAIM_STATES]
    pool = active or [c for c in mine if c.state is ClaimState.CLOSED]
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
