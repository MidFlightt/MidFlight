"""Allowed state transitions, and the verification-to-check mapping (docs/domain.md).

Application code changes state only through these functions, so an illegal move
raises instead of being saved.
"""

from __future__ import annotations

from collections.abc import Mapping

from midflight.domain.models import (
    Claim,
    ClaimState,
    Directive,
    DirectiveResponse,
    DirectiveState,
    VerificationOutcome,
)


class IllegalTransition(ValueError):
    """A state change the domain does not allow."""


_C = ClaimState

# `None` is a claim that doesn't exist yet.
CLAIM_TRANSITIONS: Mapping[ClaimState | None, frozenset[ClaimState]] = {
    None: frozenset({_C.DRAFT, _C.PENDING}),
    _C.DRAFT: frozenset({_C.PENDING, _C.WITHDRAWN}),
    _C.PENDING: frozenset({_C.APPROVED, _C.NEEDS_REVISION, _C.HUMAN_REVIEW_REQUIRED, _C.WITHDRAWN}),
    _C.NEEDS_REVISION: frozenset({_C.PENDING, _C.WITHDRAWN}),
    _C.HUMAN_REVIEW_REQUIRED: frozenset({_C.PENDING, _C.NEEDS_REVISION, _C.WITHDRAWN}),
    _C.APPROVED: frozenset({_C.PENDING, _C.HUMAN_REVIEW_REQUIRED, _C.CLOSED, _C.WITHDRAWN}),
    _C.WITHDRAWN: frozenset(),
    _C.CLOSED: frozenset(),
}

# Claims in these states reserve work and take part in other claims' checks (FR-03).
ACTIVE_CLAIM_STATES = frozenset(
    {_C.DRAFT, _C.PENDING, _C.APPROVED, _C.NEEDS_REVISION, _C.HUMAN_REVIEW_REQUIRED}
)

_D = DirectiveState

DIRECTIVE_TRANSITIONS: Mapping[DirectiveState, frozenset[DirectiveState]] = {
    _D.QUEUED: frozenset({_D.DELIVERED, _D.SUPERSEDED}),
    _D.DELIVERED: frozenset({_D.ACKNOWLEDGED, _D.REJECTED, _D.NEEDS_CLARIFICATION, _D.SUPERSEDED}),
    _D.NEEDS_CLARIFICATION: frozenset({_D.SUPERSEDED}),
    _D.ACKNOWLEDGED: frozenset(),
    _D.REJECTED: frozenset(),
    _D.SUPERSEDED: frozenset(),
}

# Directives still waiting on the agent. Blocking ones refuse a push (UC-16).
OPEN_DIRECTIVE_STATES = frozenset({_D.QUEUED, _D.DELIVERED, _D.NEEDS_CLARIFICATION})

# A replacement retires all open directives, including questions awaiting the lead (D13).
SUPERSEDABLE_DIRECTIVE_STATES = OPEN_DIRECTIVE_STATES


def check_claim_transition(current: ClaimState | None, target: ClaimState) -> None:
    if target not in CLAIM_TRANSITIONS[current]:
        start = current.value if current else "new"
        raise IllegalTransition(f"claim can't move from {start} to {target.value}")


def check_directive_transition(current: DirectiveState, target: DirectiveState) -> None:
    if target not in DIRECTIVE_TRANSITIONS[current]:
        raise IllegalTransition(f"directive can't move from {current.value} to {target.value}")


def move_claim(claim: Claim, target: ClaimState) -> Claim:
    """The same claim revision in `target`, or IllegalTransition."""
    check_claim_transition(claim.state, target)
    return Claim.model_validate(claim.model_dump() | {"state": target})


def move_directive(directive: Directive, target: DirectiveState) -> Directive:
    """The same directive in `target`, or IllegalTransition. Agent answers use `respond`."""
    if target.value in {r.value for r in DirectiveResponse}:
        raise IllegalTransition("record an agent's answer with respond(), not move_directive()")
    check_directive_transition(directive.state, target)
    return Directive.model_validate(directive.model_dump() | {"state": target})


def respond(directive: Directive, response: DirectiveResponse, note: str | None) -> Directive:
    """Record the agent's answer (UC-09). `acknowledged` means received (INV-10)."""
    target = DirectiveState(response.value)
    check_directive_transition(directive.state, target)
    return Directive.model_validate(
        directive.model_dump() | {"state": target, "response": response, "response_note": note}
    )


# GitHub check conclusion per outcome (UC-11). Never `neutral` or `skipped`.
CHECK_CONCLUSIONS: Mapping[VerificationOutcome, str] = {
    VerificationOutcome.VERIFIED: "success",
    VerificationOutcome.FAILED: "failure",
    VerificationOutcome.NEEDS_REVIEW: "action_required",
    VerificationOutcome.INCOMPLETE: "action_required",
}


def check_conclusion(outcome: VerificationOutcome) -> str:
    return CHECK_CONCLUSIONS[outcome]
