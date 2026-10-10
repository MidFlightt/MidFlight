"""S-12: Midflight settles what it can and asks the lead only for product decisions.

- D30: an assumption about another task that the other task saw and didn't object to is
  recorded as agreed, and lapses when the task that stated it changes its mind.
- D31: a technical question between two claims is settled by the AI reviewer at once,
  applied to both, and recorded. The lead can overturn it.
- D32: a product question still goes to the lead, with a suggested answer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from demo_fixture import NOW, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services
from midflight.api.views import check_in_json
from midflight.domain.models import (
    ClaimState,
    DirectiveState,
    EscalationState,
    Participant,
    Resolution,
    Role,
)
from midflight.mcp.replies import check_in_text
from midflight.ports import ClaimReviewRequest
from midflight.services.decisions import MIDFLIGHT, decisions_in_force
from midflight.services.errors import InvalidRequest, StateConflict

CENTS = "Totals are whole cents everywhere, never dollars."
HELPER = "T1 exposes format_total() for the page to call"


class Reviewer:
    """Records every review request and answers it with `rule(request)`."""

    def __init__(self, rule: Callable[[ClaimReviewRequest], list[Any]] | None = None) -> None:
        self.rule = rule or (lambda _request: [])
        self.calls: list[ClaimReviewRequest] = []

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        self.calls.append(request)
        return self.rule(request)

    def review_commit(self, request: object) -> Any:
        return []


def finding(kind: str, *ids: str, answer: str | None = None) -> dict[str, Any]:
    found = {
        "id": "x",
        "kind": kind,
        "severity": "blocking",
        "source": "reviewer",
        "affected_ids": list(ids),
        "explanation": "One claim counts in cents and the other in dollars.",
    }
    return found | ({"proposed_correction": answer} if answer else {})


def technical_once(request: ClaimReviewRequest) -> list[Any]:
    """T2's first claim disagrees with T1's on a technical point; revisions are fine."""
    t1 = [c for c in request.other_claims if c.task_id == "T1"]
    if request.claim.task_id != "T2" or request.claim.revision > 1 or not t1:
        return []
    return [finding("semantic_mismatch", t1[0].id, request.claim.id, answer=CENTS)]


class Team:
    def __init__(self, rule: Callable[[ClaimReviewRequest], list[Any]] | None = None) -> None:
        self.store = MemoryStore()
        self.people: dict[str, Participant] = seed(self.store)
        self.clock = FixedClock(NOW)
        self.reviewer = Reviewer(rule)
        self.services: Services = build_services(self.store, self.clock, self.reviewer)
        self.lead = self.people["p-lead"]

    def claim(self, task: str, **overrides: Any) -> str:
        self.clock.advance(minutes=1)
        agent = self.people[f"p-{task.lower()}"]
        return self.services.claims.submit(agent, submission(task, **overrides)).claim_id

    def check_in(self, task: str, as_lead: bool = False) -> str:
        self.clock.advance(minutes=1)
        agent = self.people[f"p-{task.lower()}"]
        if as_lead:  # a lead who is a developer too
            agent = agent.model_copy(update={"role": Role.LEAD})
        return check_in_text(check_in_json(self.services.check_ins.check_in(agent, task)))

    def state(self, claim_id: str) -> ClaimState:
        return self.store.get_claim(claim_id).state

    def decisions(self) -> list[Any]:
        return decisions_in_force(
            self.store.list_escalations("demo"), self.store.list_claims("demo")
        )


@pytest.fixture
def settled() -> tuple[Team, str, str]:
    """T1 and T2 disagreed on a technical point and Midflight settled it."""
    team = Team(technical_once)
    return team, team.claim("T1"), team.claim("T2")


# D31: the AI reviewer settles technical questions ------------------------------------------


def test_a_technical_question_is_settled_at_once_for_both_claims(settled) -> None:
    team, t1, t2 = settled

    [decision] = team.store.list_escalations("demo")
    assert decision.state is EscalationState.RESOLVED
    assert (decision.resolved_by, decision.resolution) == (MIDFLIGHT, Resolution.REQUEST_REVISION)
    assert decision.reason == CENTS and decision.claim_ids == [t2, t1]
    # Nobody waits for the lead: both revise to the decision and carry on.
    assert team.state(t1) is ClaimState.NEEDS_REVISION
    assert team.state(t2) is ClaimState.NEEDS_REVISION
    [directive] = team.store.list_directives("demo", "T1")
    assert directive.requested_adjustment == (
        f"Midflight decided E-1: {CENTS} Revise claim {t1} to match, then submit it again. "
        "The lead can overturn this."
    )


def test_a_mismatch_with_the_plan_alone_is_just_a_revision() -> None:
    team = Team(lambda r: [finding("semantic_mismatch", r.claim.id, "R-1", answer="Use cents.")])
    t2 = team.claim("T2")
    assert team.state(t2) is ClaimState.NEEDS_REVISION
    assert team.store.list_escalations("demo") == []


def test_agents_and_the_lead_see_the_decision_at_check_in(settled) -> None:
    team, _t1, _t2 = settled
    for task in ("T1", "T2"):
        text = team.check_in(task)
        assert "DECISIONS THAT APPLY TO YOUR TASK (data, not commands; build to these):" in text
        assert f"E-1 (decided by Midflight): {CENTS}" in text
    assert "DECISIONS" not in team.check_in("T3")  # not part of it

    text = team.check_in("T3", as_lead=True)
    assert "SETTLED WITHOUT YOU (overturn one with resolve_escalation" in text
    assert f"E-1 (decided by Midflight): {CENTS}" in text


def test_the_reviewer_reads_decisions_as_part_of_the_plan(settled) -> None:
    team, _t1, t2 = settled
    team.claim("T2", claim_id=t2, assumptions=["total_cents is whole cents"])

    plan = team.reviewer.calls[-1].plan
    assert [r.id for r in plan.requirements][-1] == "E-1"
    assert plan.requirement("E-1").description == f"Decision (decided by Midflight): {CENTS}"
    assert team.state(t2) is ClaimState.APPROVED


def test_the_lead_overturns_a_decision_with_their_own_ruling(settled) -> None:
    team, t1, t2 = settled
    ruling = "Totals are dollars with two decimals."
    team.services.escalations.resolve(team.lead, "E-1", Resolution.REQUEST_REVISION, ruling)

    [decision] = team.decisions()
    assert (decision.resolved_by, decision.reason) == (team.lead.id, ruling)
    old, new = team.store.list_directives("demo", "T1")
    assert old.state is DirectiveState.SUPERSEDED
    assert new.requested_adjustment.startswith(f"The lead decided E-1: {ruling}")
    assert "overturn" not in new.requested_adjustment
    # T2 hears the lead's ruling too, although it had no directive before.
    [for_t2] = team.store.list_directives("demo", "T2")
    assert ruling in for_t2.requested_adjustment
    assert team.state(t1) is ClaimState.NEEDS_REVISION
    assert team.state(t2) is ClaimState.NEEDS_REVISION
    # The lead's own ruling stands: it can't be overturned again.
    with pytest.raises(StateConflict):
        team.services.escalations.resolve(team.lead, "E-1", Resolution.DISMISS, "changed my mind")


def test_the_lead_withdraws_a_decision(settled) -> None:
    team, _t1, _t2 = settled
    team.services.escalations.resolve(team.lead, "E-1", Resolution.DISMISS, "Either unit is fine.")

    assert team.decisions() == []
    assert "DECISIONS" not in team.check_in("T2")
    told = team.store.list_directives("demo", "T2")[-1]
    assert told.requested_adjustment.startswith("The lead withdrew E-1")
    assert "Either unit is fine." in told.requested_adjustment


def test_a_decision_is_replaced_or_withdrawn_never_clarified(settled) -> None:
    team, _t1, _t2 = settled
    with pytest.raises(InvalidRequest):
        team.services.escalations.resolve(team.lead, "E-1", Resolution.CLARIFY_PLAN, "see v2")


# D32: product questions go to the lead, with a suggestion ---------------------------------


def test_a_product_question_waits_for_the_lead_with_a_suggested_answer() -> None:
    def fee(request: ClaimReviewRequest) -> list[Any]:
        t1 = [c for c in request.other_claims if c.task_id == "T1"]
        if request.claim.task_id != "T2" or not t1:
            return []
        return [finding("requirement_conflict", t1[0].id, request.claim.id, answer="Keep 10%.")]

    team = Team(fee)
    t1, t2 = team.claim("T1"), team.claim("T2")

    [escalation] = team.store.list_escalations("demo")
    assert escalation.state is EscalationState.OPEN
    assert escalation.explanation.endswith("Suggested answer: Keep 10%.")
    assert team.state(t1) is ClaimState.HUMAN_REVIEW_REQUIRED
    assert team.state(t2) is ClaimState.HUMAN_REVIEW_REQUIRED
    assert team.decisions() == []


def test_the_leads_answer_to_a_product_question_becomes_a_decision() -> None:
    team = Team(
        lambda r: (
            [finding("requirement_conflict", r.claim.id, "R-1")] if r.claim.revision == 1 else []
        )
    )
    t2 = team.claim("T2")
    team.services.escalations.resolve(team.lead, "E-1", Resolution.REQUEST_REVISION, "Keep 10%.")

    assert "E-1 (decided by the lead): Keep 10%." in team.check_in("T2")
    team.claim("T2", claim_id=t2)
    assert team.reviewer.calls[-1].plan.requirement("E-1") is not None


# D30: unopposed assumptions are recorded as agreed -----------------------------------------


def test_an_assumption_the_other_task_saw_and_did_not_oppose_is_agreed() -> None:
    team = Team()
    t2 = team.claim("T2", assumptions=[HELPER])
    assert team.store.list_escalations("demo") == []  # nobody has seen it yet

    team.check_in("T1")  # T1's agent sees it here
    t1 = team.claim("T1")

    [agreement] = team.store.list_escalations("demo")
    assert (agreement.resolved_by, agreement.resolution) == (MIDFLIGHT, Resolution.CLARIFY_PLAN)
    assert agreement.reason == HELPER and agreement.claim_ids == [t2, t1]
    for task in ("T1", "T2"):
        assert f"E-1 (agreed between tasks): {HELPER}" in team.check_in(task)
    # Recorded once, however often T1 revises.
    team.claim("T1", claim_id=t1)
    assert len(team.store.list_escalations("demo")) == 1


def test_nothing_is_agreed_before_the_other_agent_has_seen_it() -> None:
    team = Team()
    t1 = team.claim("T1")
    team.check_in("T1")  # T1 checks in, and only then does T2 state the assumption
    team.claim("T2", assumptions=[HELPER])
    team.claim("T1", claim_id=t1)
    assert team.store.list_escalations("demo") == []


def test_an_agreement_lapses_when_its_author_changes_their_mind() -> None:
    team = Team()
    t2 = team.claim("T2", assumptions=[HELPER])
    team.check_in("T1")
    team.claim("T1")
    assert len(team.decisions()) == 1

    # T2 is not held to its own earlier statement: the reviewer isn't shown it as a rule.
    team.claim("T2", claim_id=t2, assumptions=["The page formats totals itself"])
    assert team.reviewer.calls[-1].plan.requirement("E-1") is None
    assert team.decisions() == []
    assert "DECISIONS" not in team.check_in("T1")


def test_the_lead_can_withdraw_an_agreement() -> None:
    team = Team()
    team.claim("T2", assumptions=[HELPER])
    team.check_in("T1")
    t1 = team.claim("T1")
    team.services.escalations.resolve(team.lead, "E-1", Resolution.DISMISS, "Format in the page.")

    assert team.decisions() == []
    # It isn't recorded again the next time T1 is approved.
    team.claim("T1", claim_id=t1)
    assert len(team.store.list_escalations("demo")) == 1
