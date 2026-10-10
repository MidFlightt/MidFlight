"""Decisions: questions between tasks that have been answered (D30, D31).

A decision is a resolved escalation that tells agents what to build:

- The lead answered a product question (`request_revision`, resolved by the lead).
- Midflight's AI reviewer settled a technical question between two claims
  (`request_revision`, resolved by `midflight`). The lead can overturn it.
- One task stated an assumption about another, that task's agent saw it, and its next
  claim was approved without objecting (`clarify_plan`, resolved by `midflight`). This
  kind lapses on its own when the task that stated it changes its mind.

Decisions are stored as escalations so that the shared model doesn't grow a new entity.
Agents see the ones about their task at every check-in, and the AI reviewer reads them
as part of the plan, so a later claim is checked against them.
"""

from __future__ import annotations

from collections.abc import Sequence

from midflight.domain.models import (
    Claim,
    ClaimState,
    Directive,
    DirectiveSource,
    DirectiveState,
    Entity,
    Escalation,
    EscalationState,
    Requirement,
    Resolution,
)
from midflight.domain.states import (
    ACTIVE_CLAIM_STATES,
    CLAIM_TRANSITIONS,
    SUPERSEDABLE_DIRECTIVE_STATES,
    move_claim,
    move_directive,
)
from midflight.ports import Clock, Store

# Who resolved an escalation when no person did.
MIDFLIGHT = "midflight"


def is_agreement(escalation: Escalation) -> bool:
    """An assumption nobody objected to, as opposed to a ruling."""
    return escalation.resolved_by == MIDFLIGHT and escalation.resolution is Resolution.CLARIFY_PLAN


def decided_by(escalation: Escalation) -> str:
    """How to describe a decision's origin to an agent or the lead."""
    if is_agreement(escalation):
        return "agreed between tasks"
    return "decided by Midflight" if escalation.resolved_by == MIDFLIGHT else "decided by the lead"


def decisions_in_force(
    escalations: Sequence[Escalation], claims: Sequence[Claim]
) -> list[Escalation]:
    """The decisions agents should build to right now, oldest first.

    `claims` are the latest revisions. A decision applies while at least one claim it
    was about is still active: once every one is withdrawn or closed, there is nobody
    left to build to it. An agreement also holds only while the claim that proposed it
    (the first one listed) is active and still states the assumption.
    """
    latest = {c.id: c for c in claims}
    active = {c.id for c in claims if c.state in ACTIVE_CLAIM_STATES}
    in_force = []
    for escalation in sorted(escalations, key=lambda e: e.created_at):
        if escalation.state is not EscalationState.RESOLVED:
            continue
        if not active & set(escalation.claim_ids):
            continue
        if is_agreement(escalation):
            proposer = latest.get(escalation.claim_ids[0])
            still_stated = (
                proposer is not None
                and proposer.state in ACTIVE_CLAIM_STATES
                and escalation.reason in proposer.assumptions
            )
            if still_stated:
                in_force.append(escalation)
        elif escalation.resolution is Resolution.REQUEST_REVISION:
            in_force.append(escalation)
    return in_force


def as_requirements(decisions: Sequence[Escalation]) -> list[Requirement]:
    """Decisions in the form the AI reviewer reads the rest of the plan in."""
    return [
        Requirement(id=d.id, description=f"Decision ({decided_by(d)}): {d.reason}")
        for d in decisions
    ]


def revision_requests(
    store: Store,
    clock: Clock,
    escalation: Escalation,
    claims: Sequence[Claim],
    plan_version: int,
    reason: str,
    decider: str,
) -> list[Entity]:
    """Send each claim back for revision, with a directive carrying the decision.

    Open directives for the same task are superseded, so an agent answers one message
    about this, not two. A claim that can't move to `needs_revision` (already there,
    withdrawn, closed) is left as it is but still gets the directive.
    """
    directives = store.list_directives(escalation.project_id)
    overturn = " The lead can overturn this." if decider == MIDFLIGHT else ""
    who = "Midflight" if decider == MIDFLIGHT else "The lead"
    puts: list[Entity] = []
    for claim in claims:
        if ClaimState.NEEDS_REVISION in CLAIM_TRANSITIONS[claim.state]:
            puts.append(move_claim(claim, ClaimState.NEEDS_REVISION))
        puts += [
            move_directive(d, DirectiveState.SUPERSEDED)
            for d in directives
            if d.task_id == claim.task_id and d.state in SUPERSEDABLE_DIRECTIVE_STATES
        ]
        puts.append(
            Directive(
                id=store.next_id(escalation.project_id, "D"),
                project_id=escalation.project_id,
                source=DirectiveSource.PLAN_CHANGE,
                task_id=claim.task_id,
                recipient_id=claim.agent_id,
                plan_version=plan_version,
                changed_ids=escalation.competing_requirement_ids,
                requested_adjustment=f"{who} decided {escalation.id}: {reason} Revise claim "
                f"{claim.id} to match, then submit it again.{overturn}",
                reason=escalation.explanation,
                created_at=clock.now(),
            )
        )
    return puts
