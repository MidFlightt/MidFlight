"""S-1: claim and directive transitions match docs/domain.md, and nothing else is allowed."""

from __future__ import annotations

import itertools

import pytest

from demo_fixture import NOW, PROJECT, make_claim
from midflight.domain.models import (
    ClaimState,
    Directive,
    DirectiveResponse,
    DirectiveSource,
    DirectiveState,
    VerificationOutcome,
)
from midflight.domain.states import (
    ACTIVE_CLAIM_STATES,
    CLAIM_TRANSITIONS,
    IllegalTransition,
    check_claim_transition,
    check_conclusion,
    move_claim,
    move_directive,
    respond,
)

C = ClaimState
D = DirectiveState

# The state diagram in docs/domain.md, edge by edge. If this changes, change the doc.
DOMAIN_CLAIM_EDGES = {
    (None, C.DRAFT),
    (None, C.PENDING),
    (C.DRAFT, C.PENDING),
    (C.PENDING, C.APPROVED),
    (C.PENDING, C.NEEDS_REVISION),
    (C.PENDING, C.HUMAN_REVIEW_REQUIRED),
    (C.APPROVED, C.HUMAN_REVIEW_REQUIRED),
    (C.NEEDS_REVISION, C.PENDING),
    (C.HUMAN_REVIEW_REQUIRED, C.PENDING),
    (C.HUMAN_REVIEW_REQUIRED, C.NEEDS_REVISION),
    (C.APPROVED, C.PENDING),
    (C.APPROVED, C.CLOSED),
    (C.DRAFT, C.WITHDRAWN),
    (C.PENDING, C.WITHDRAWN),
    (C.NEEDS_REVISION, C.WITHDRAWN),
    (C.HUMAN_REVIEW_REQUIRED, C.WITHDRAWN),
    (C.APPROVED, C.WITHDRAWN),
}


def test_claim_transitions_match_the_domain_diagram() -> None:
    edges = {(start, end) for start, ends in CLAIM_TRANSITIONS.items() for end in ends}
    assert edges == DOMAIN_CLAIM_EDGES


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (s, e)
        for s, e in itertools.product([None, *ClaimState], ClaimState)
        if (s, e) not in DOMAIN_CLAIM_EDGES
    ],
)
def test_every_other_claim_transition_raises(start: ClaimState | None, end: ClaimState) -> None:
    with pytest.raises(IllegalTransition):
        check_claim_transition(start, end)


def test_a_claim_cannot_jump_straight_to_approved() -> None:
    # Approval only comes from a review of a pending claim (INV-01, INV-02).
    for start in (None, C.DRAFT, C.NEEDS_REVISION, C.HUMAN_REVIEW_REQUIRED):
        with pytest.raises(IllegalTransition):
            check_claim_transition(start, C.APPROVED)


def test_withdrawn_and_closed_are_final_and_inactive() -> None:
    for final in (C.WITHDRAWN, C.CLOSED):
        assert not CLAIM_TRANSITIONS[final]
        assert final not in ACTIVE_CLAIM_STATES


def test_move_claim_returns_a_new_claim_and_keeps_the_original() -> None:
    pending = make_claim()
    approved = move_claim(pending, C.APPROVED)
    assert approved.state is C.APPROVED
    assert pending.state is C.PENDING
    assert approved.revision == pending.revision


def test_plan_change_sends_an_approved_claim_back_to_pending() -> None:
    approved = move_claim(make_claim(), C.APPROVED)
    assert move_claim(approved, C.PENDING).state is C.PENDING


# Directives ----------------------------------------------------------------------------


def make_directive(state: DirectiveState = D.QUEUED) -> Directive:
    return Directive(
        id="D-42",
        project_id=PROJECT,
        source=DirectiveSource.PLAN_CHANGE,
        task_id="T2",
        recipient_id="p-t2",
        plan_version=2,
        requested_adjustment="Display `currency` next to the total",
        reason="Plan v2 adds currency",
        state=state,
        created_at=NOW,
    )


def test_directive_is_delivered_then_answered() -> None:
    delivered = move_directive(make_directive(), D.DELIVERED)
    answered = respond(delivered, DirectiveResponse.ACKNOWLEDGED, "will display it")
    assert answered.state is D.ACKNOWLEDGED
    assert answered.response is DirectiveResponse.ACKNOWLEDGED
    assert answered.response_note == "will display it"


def test_an_undelivered_directive_cannot_be_answered() -> None:
    with pytest.raises(IllegalTransition):
        respond(make_directive(), DirectiveResponse.ACKNOWLEDGED, None)


def test_a_directive_is_answered_only_once() -> None:
    answered = respond(make_directive(D.DELIVERED), DirectiveResponse.REJECTED, "out of scope")
    with pytest.raises(IllegalTransition):
        respond(answered, DirectiveResponse.ACKNOWLEDGED, None)


def test_answers_go_through_respond_not_move_directive() -> None:
    with pytest.raises(IllegalTransition, match="respond"):
        move_directive(make_directive(D.DELIVERED), D.ACKNOWLEDGED)


def test_superseding_keeps_an_earlier_question() -> None:
    asked = respond(make_directive(D.DELIVERED), DirectiveResponse.NEEDS_CLARIFICATION, "which?")
    superseded = move_directive(asked, D.SUPERSEDED)
    assert superseded.state is D.SUPERSEDED
    assert superseded.response is DirectiveResponse.NEEDS_CLARIFICATION


def test_acknowledged_directives_are_never_superseded() -> None:
    answered = respond(make_directive(D.DELIVERED), DirectiveResponse.ACKNOWLEDGED, None)
    with pytest.raises(IllegalTransition):
        move_directive(answered, D.SUPERSEDED)


# Check conclusions (UC-11) -------------------------------------------------------------


def test_outcomes_map_to_check_conclusions() -> None:
    assert check_conclusion(VerificationOutcome.VERIFIED) == "success"
    assert check_conclusion(VerificationOutcome.FAILED) == "failure"
    assert check_conclusion(VerificationOutcome.NEEDS_REVIEW) == "action_required"
    assert check_conclusion(VerificationOutcome.INCOMPLETE) == "action_required"


def test_no_outcome_is_ever_neutral_or_skipped() -> None:
    conclusions = {check_conclusion(o) for o in VerificationOutcome}
    assert not conclusions & {"neutral", "skipped"}
