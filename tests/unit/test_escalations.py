"""S-7: conflicts between people's requirements go to the lead (UC-12, UC-13, INV-11)."""

from __future__ import annotations

from typing import Any

import pytest

from demo_fixture import NOW, make_plan, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services
from midflight.domain.models import (
    ClaimState,
    Directive,
    DirectiveResponse,
    DirectiveSource,
    DirectiveState,
    EscalationState,
    FindingKind,
    FindingSeverity,
    Participant,
    Resolution,
)
from midflight.ports import ClaimReviewRequest, Commit
from midflight.services.errors import PermissionDenied, StateConflict
from midflight.services.plans import PlanDraft


class TaxConflictReviewer:
    """Flags the tax question whenever T2 is reviewed while T1 has a claim."""

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        t1 = [c for c in request.other_claims if c.task_id == "T1"]
        if request.claim.task_id != "T2" or not t1:
            return []
        return [
            {
                "id": "x",
                "kind": "requirement_conflict",
                "severity": "blocking",
                "source": "reviewer",
                "affected_ids": [t1[0].id, request.claim.id, "R-1"],
                "explanation": "T2 assumes a tax-inclusive total; T1 returns it tax-exclusive.",
                "proposed_correction": "The lead decides whether totals include tax.",
            }
        ]

    def review_commit(self, request: object) -> Any:
        return []


@pytest.fixture
def team() -> tuple[Services, dict[str, Participant]]:
    store = MemoryStore()
    people = seed(store)
    return build_services(store, FixedClock(NOW), TaxConflictReviewer()), people


def escalate(services: Services, people: dict[str, Participant]) -> tuple[str, str, str]:
    """T1 says totals exclude tax, T2 says they include it. Returns (t1, t2, escalation)."""
    t1 = services.claims.submit(
        people["p-t1"], submission("T1", assumptions=["total_cents excludes tax"])
    )
    t2 = services.claims.submit(
        people["p-t2"], submission("T2", assumptions=["total_cents already includes tax"])
    )
    [escalation] = services.store.list_escalations("demo")
    return t1.claim_id, t2.claim_id, escalation.id


def state(services: Services, claim_id: str) -> ClaimState:
    return services.store.get_claim(claim_id).state


def test_a_requirement_conflict_opens_one_escalation_with_both_sides(team) -> None:
    services, people = team
    t1, t2, eid = escalate(services, people)

    escalation = services.store.get_escalation(eid)
    assert escalation.state is EscalationState.OPEN
    assert escalation.claim_ids == [t2, t1]
    assert escalation.competing_requirement_ids == ["R-1"]
    excerpts = " ".join(e.excerpt for e in escalation.evidence)
    assert "excludes tax" in excerpts and "includes tax" in excerpts
    # Both sides wait for the lead; Midflight doesn't pick one (INV-11).
    assert state(services, t1) is ClaimState.HUMAN_REVIEW_REQUIRED
    assert state(services, t2) is ClaimState.HUMAN_REVIEW_REQUIRED


def test_revising_while_escalated_does_not_open_a_second_escalation(team) -> None:
    services, people = team
    _t1, t2, _eid = escalate(services, people)
    services.claims.submit(people["p-t2"], submission("T2", claim_id=t2, reason="retry"))
    assert len(services.store.list_escalations("demo")) == 1


def test_request_revision_sends_the_leads_decision_to_both_agents(team) -> None:
    services, people = team
    t1, t2, eid = escalate(services, people)
    reason = "Totals exclude tax; the page adds tax itself."
    resolved = services.escalations.resolve(
        people["p-lead"], eid, Resolution.REQUEST_REVISION, reason
    )

    assert resolved.state is EscalationState.RESOLVED
    assert (resolved.resolved_by, resolved.reason, resolved.resolved_at) == (
        "p-lead",
        reason,
        NOW,
    )
    assert state(services, t1) is ClaimState.NEEDS_REVISION
    assert state(services, t2) is ClaimState.NEEDS_REVISION
    directives = services.store.list_directives("demo")
    assert sorted(d.task_id for d in directives) == ["T1", "T2"]
    assert all(reason in d.requested_adjustment for d in directives)
    assert all(d.state is DirectiveState.QUEUED for d in directives)
    [event] = [e for e in services.store.list_audit("demo") if e.action.startswith("escalation.")]
    assert event.action == "escalation.request_revision" and event.actor == "p-lead"


def test_dismiss_reviews_again_and_sets_the_conflict_aside(team) -> None:
    services, people = team
    t1, t2, eid = escalate(services, people)
    services.escalations.resolve(
        people["p-lead"], eid, Resolution.DISMISS, "Both are tax-exclusive."
    )

    assert state(services, t1) is ClaimState.APPROVED
    assert state(services, t2) is ClaimState.APPROVED
    conflict = next(
        f
        for f in services.store.get_claim(t2).findings
        if f.kind is FindingKind.REQUIREMENT_CONFLICT
    )
    assert conflict.severity is FindingSeverity.INFO
    assert "dismissed" in conflict.explanation


def test_clarify_plan_needs_a_newer_plan_first(team) -> None:
    services, people = team
    t1, t2, eid = escalate(services, people)
    lead = people["p-lead"]
    with pytest.raises(StateConflict, match="plan hasn't changed"):
        services.escalations.resolve(lead, eid, Resolution.CLARIFY_PLAN, "See plan v2")

    plan = make_plan(2)
    draft = PlanDraft(requirements=plan.requirements, tasks=plan.tasks, contracts=plan.contracts)
    services.plans.approve(lead, services.plans.propose(lead, draft).version, "Settle tax")
    services.escalations.resolve(lead, eid, Resolution.CLARIFY_PLAN, "Plan v2 settles it")

    # Reviewed again: both cite plan v1, so both revise against v2.
    assert state(services, t1) is ClaimState.NEEDS_REVISION
    assert state(services, t2) is ClaimState.NEEDS_REVISION


def test_only_the_lead_resolves_and_only_once(team) -> None:
    services, people = team
    _t1, _t2, eid = escalate(services, people)
    with pytest.raises(PermissionDenied):
        services.escalations.resolve(people["p-t2"], eid, Resolution.DISMISS, "mine wins")
    services.escalations.resolve(people["p-lead"], eid, Resolution.DISMISS, "fine")
    with pytest.raises(StateConflict):
        services.escalations.resolve(people["p-lead"], eid, Resolution.DISMISS, "again")


# Found by the HireBot experiment (docs/experiment.md) -------------------------------


class RecordingReviewer:
    """Finds nothing; remembers which other claims it was shown."""

    def __init__(self) -> None:
        self.seen: list[list[str]] = []

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        self.seen.append([c.id for c in request.other_claims])
        return []

    def review_commit(self, request: object) -> Any:
        return []


def test_the_reviewer_is_never_shown_a_withdrawn_claim() -> None:
    store = MemoryStore()
    people = seed(store)
    reviewer = RecordingReviewer()
    services = build_services(store, FixedClock(NOW), reviewer)
    old = services.claims.submit(people["p-t1"], submission("T1"))
    services.claims.withdraw(people["p-t1"], old.claim_id)
    services.claims.submit(people["p-t2"], submission("T2"))
    assert reviewer.seen[-1] == []


class OneSidedReviewer:
    """Calls it a conflict between people, but cites only the claim under review."""

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        return [
            {
                "id": "x",
                "kind": "requirement_conflict",
                "severity": "blocking",
                "source": "reviewer",
                "affected_ids": [request.claim.id],
                "explanation": "This claim contradicts itself.",
            }
        ]

    def review_commit(self, request: object) -> Any:
        return []


def test_a_conflict_citing_one_tasks_claims_is_a_note_not_an_escalation() -> None:
    store = MemoryStore()
    people = seed(store)
    services = build_services(store, FixedClock(NOW), OneSidedReviewer())
    result = services.claims.submit(people["p-t2"], submission("T2"))
    assert result.state is ClaimState.APPROVED
    assert services.store.list_escalations("demo") == []
    [finding] = services.store.get_claim(result.claim_id).findings
    assert finding.severity is FindingSeverity.INFO and "Not escalated" in finding.explanation


class TaxVersusPlanReviewer:
    """Every claim that isn't T1's gets a conflict with requirement R-1."""

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        if request.claim.task_id == "T1":
            return []
        return [
            {
                "id": "x",
                "kind": "requirement_conflict",
                "severity": "blocking",
                "source": "reviewer",
                "affected_ids": [request.claim.id, "R-1"],
                "explanation": "This claim contradicts requirement R-1.",
            }
        ]

    def review_commit(self, request: object) -> Any:
        return []


def test_claims_in_conflict_with_the_same_requirement_share_one_escalation() -> None:
    store = MemoryStore()
    people = seed(store)
    services = build_services(store, FixedClock(NOW), TaxVersusPlanReviewer())
    t2 = services.claims.submit(people["p-t2"], submission("T2"))
    t3 = services.claims.submit(people["p-t3"], submission("T3", requirement_ids=["R-1"]))
    [escalation] = services.store.list_escalations("demo")
    assert escalation.claim_ids == [t2.claim_id, t3.claim_id]
    assert state(services, t3.claim_id) is ClaimState.HUMAN_REVIEW_REQUIRED
    # One decision by the lead reaches both claims.
    services.escalations.resolve(people["p-lead"], escalation.id, Resolution.REQUEST_REVISION, "x")
    assert state(services, t2.claim_id) is ClaimState.NEEDS_REVISION
    assert state(services, t3.claim_id) is ClaimState.NEEDS_REVISION


def test_lead_replacement_clears_clarification_and_restores_readiness(team) -> None:
    services, people = team
    t1, _t2, eid = escalate(services, people)
    actor = people["p-t1"]
    old = Directive(
        id="D-question",
        source=DirectiveSource.PLAN_CHANGE,
        project_id="demo",
        task_id="T1",
        recipient_id=actor.id,
        plan_version=1,
        requested_adjustment="Clarify the tax assumption",
        reason="Tax question",
        created_at=NOW,
    )
    services.store.commit(Commit(project_id="demo", idempotency_key="question", puts=[old]))
    services.check_ins.check_in(actor, "T1")
    services.directives.acknowledge(
        actor, old.id, DirectiveResponse.NEEDS_CLARIFICATION, "Are totals tax-exclusive?"
    )
    services.escalations.resolve(
        people["p-lead"], eid, Resolution.REQUEST_REVISION, "Totals exclude tax."
    )
    stored = services.store.get_directive(old.id)
    assert stored.state is DirectiveState.SUPERSEDED
    assert stored.response is DirectiveResponse.NEEDS_CLARIFICATION
    [replacement] = services.check_ins.check_in(actor, "T1").directives
    assert not services.check_ins.check_in(actor, "T1").ready_to_push
    services.directives.acknowledge(actor, replacement.id, DirectiveResponse.ACKNOWLEDGED)
    assert not services.check_ins.check_in(actor, "T1").ready_to_push
    result = services.claims.submit(
        actor, submission("T1", claim_id=t1, assumptions=["total_cents excludes tax"])
    )
    assert result.state is ClaimState.APPROVED
    assert services.check_ins.check_in(actor, "T1").ready_to_push
