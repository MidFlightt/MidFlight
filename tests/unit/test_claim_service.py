"""S-3: submit, revise, withdraw, close, and review claims (UC-04, UC-05, UC-06)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import pytest

from demo_fixture import NOW, PROJECT, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.adapters.runners import DeferredRunner, InlineRunner
from midflight.domain.models import (
    ClaimState,
    FindingKind,
    InterfaceUse,
    JobKind,
    JobState,
    Participant,
    SyncState,
)
from midflight.ports import ClaimReviewRequest, Commit, ReviewerUnavailable
from midflight.services.claims import ClaimService
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict

CHECKOUT = "checkout-response"


class ScriptedReviewer:
    """Answers each review with the next scripted reply (a value, an exception, or a call)."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls: list[ClaimReviewRequest] = []

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        self.calls.append(request)
        reply = self.replies.pop(0) if self.replies else []
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply(request)
        return reply

    def review_commit(self, request: object) -> Any:
        raise NotImplementedError


@dataclass
class Env:
    store: MemoryStore
    clock: FixedClock
    runner: InlineRunner | DeferredRunner
    service: ClaimService
    people: dict[str, Participant]

    def agent(self, task: str) -> Participant:
        return self.people[f"p-{task.lower()}"]


def make_env(
    reviewer: ScriptedReviewer | None = None, deferred: bool = False, plan_version: int = 1
) -> Env:
    store = MemoryStore()
    clock = FixedClock(NOW)
    runner: InlineRunner | DeferredRunner = DeferredRunner() if deferred else InlineRunner()
    service = ClaimService(store, runner, clock, reviewer)
    runner.register(JobKind.CLAIM_REVIEW, service.run_review)
    return Env(store, clock, runner, service, seed(store, plan_version))


@pytest.fixture
def env() -> Env:
    return make_env()


def semantic(affected: list[str], kind: str = "semantic_mismatch") -> dict[str, Any]:
    return {
        "id": "anything",
        "kind": kind,
        "severity": "blocking",
        "source": "reviewer",
        "affected_ids": affected,
        "explanation": "T2 assumes dollars; the contract is in cents",
        "proposed_correction": "Divide total_cents by 100 for display",
    }


# UC-04 main path -----------------------------------------------------------------------


def test_compatible_claim_is_approved_in_the_same_call(env: Env) -> None:
    result = env.service.submit(env.agent("T2"), submission("T2"))

    assert result.state is ClaimState.APPROVED
    job = env.store.get_job(result.job_id)
    assert job is not None and job.state is JobState.SUCCEEDED
    verdict = env.service.verdict(result.claim_id)
    assert [c.id for c in verdict.contracts] == [CHECKOUT]
    assert "not your code" in verdict.note


def test_every_change_writes_one_audit_event(env: Env) -> None:
    result = env.service.submit(env.agent("T2"), submission("T2"))
    actions = [e.action for e in env.store.list_audit(PROJECT, result.claim_id)]
    assert actions == ["claim.submitted", "claim.reviewed"]


def test_submit_and_review_each_advance_coord_rev(env: Env) -> None:
    before = env.store.get_project(PROJECT).coord_rev  # type: ignore[union-attr]
    env.service.submit(env.agent("T2"), submission("T2"))
    after = env.store.get_project(PROJECT).coord_rev  # type: ignore[union-attr]
    assert after == before + 2


# The flagship conflict, caught and corrected (UC-04, UC-05, UC-06) ---------------------


def test_total_vs_total_cents_is_caught_then_corrected(env: Env) -> None:
    t2 = env.agent("T2")
    wrong = [InterfaceUse(contract_id=CHECKOUT, fields={"total": "number"})]
    first = env.service.submit(t2, submission("T2", consumes=wrong))

    assert first.state is ClaimState.NEEDS_REVISION
    finding = env.service.verdict(first.claim_id).findings[0]
    assert finding.proposed_correction == "Read `total_cents: integer`, not `total`."

    fixed = [InterfaceUse(contract_id=CHECKOUT, fields={"total_cents": "integer"})]
    second = env.service.submit(
        t2, submission("T2", claim_id=first.claim_id, consumes=fixed, reason="use total_cents")
    )
    assert (second.claim_id, second.revision, second.state) == (
        first.claim_id,
        2,
        ClaimState.APPROVED,
    )

    # FR-03: the earlier revision keeps its contents and its findings.
    history = env.store.claim_history(first.claim_id)
    assert [c.state for c in history] == [ClaimState.NEEDS_REVISION, ClaimState.APPROVED]
    assert history[0].consumes == wrong
    assert history[0].findings[0].kind is FindingKind.CONTRACT_FIELD_MISSING


# UC-04 alternate paths -----------------------------------------------------------------


def test_unknown_contract_is_refused_and_nothing_is_saved(env: Env) -> None:
    before = env.store.get_project(PROJECT)
    cart = [InterfaceUse(contract_id="cart", fields={"items": "array"})]
    with pytest.raises(InvalidRequest) as refused:
        env.service.submit(env.agent("T2"), submission("T2", consumes=cart))
    assert "checkout-response" in refused.value.hint
    assert env.store.list_claims(PROJECT) == []
    assert env.store.get_project(PROJECT) == before


def test_claim_against_an_old_plan_is_refused() -> None:
    env = make_env(plan_version=2)
    with pytest.raises(InvalidRequest) as refused:
        env.service.submit(env.agent("T2"), submission("T2", plan_version=1))
    assert "plan v2" in refused.value.hint
    assert env.store.list_claims(PROJECT) == []


def test_unknown_task_is_refused(env: Env) -> None:
    with pytest.raises(InvalidRequest, match="no task T9"):
        env.service.submit(env.agent("T2"), submission("T2", task_id="T9"))


def test_task_owned_by_another_agent_is_forbidden(env: Env) -> None:
    with pytest.raises(PermissionDenied):
        env.service.submit(env.agent("T3"), submission("T2"))


def test_the_lead_can_only_claim_tasks_they_own(env: Env) -> None:
    with pytest.raises(PermissionDenied, match="assigned to another"):
        env.service.submit(env.people["p-lead"], submission("T2"))


def test_a_revoked_agent_cannot_submit(env: Env) -> None:
    revoked = env.agent("T2").model_copy(update={"revoked_at": NOW})
    with pytest.raises(PermissionDenied):
        env.service.submit(revoked, submission("T2"))


def test_incomplete_claim_is_a_draft_until_completed(env: Env) -> None:
    t2 = env.agent("T2")
    draft = env.service.submit(t2, submission("T2", consumes=[], acceptance_criteria=[]))
    assert draft.state is ClaimState.DRAFT
    kinds = [f.kind for f in env.service.verdict(draft.claim_id).findings]
    assert kinds == [FindingKind.INCOMPLETE_CLAIM]

    complete = env.service.submit(t2, submission("T2", claim_id=draft.claim_id))
    assert complete.state is ClaimState.APPROVED


def test_contradictory_claim_is_refused(env: Env) -> None:
    with pytest.raises(InvalidRequest, match="no_interfaces"):
        env.service.submit(env.agent("T2"), submission("T2", no_interfaces=True))


# Scenario 3: harmless file overlap -----------------------------------------------------


def test_t1_and_t3_sharing_readme_are_both_approved(env: Env) -> None:
    t1 = env.service.submit(env.agent("T1"), submission("T1"))
    t3 = env.service.submit(env.agent("T3"), submission("T3"))
    assert t1.state is ClaimState.APPROVED
    assert t3.state is ClaimState.APPROVED
    kinds = [f.kind for f in env.service.verdict(t3.claim_id).findings]
    assert kinds == [FindingKind.FILE_OVERLAP]


# UC-06 ---------------------------------------------------------------------------------


def test_another_agent_cannot_revise_a_claim(env: Env) -> None:
    first = env.service.submit(env.agent("T2"), submission("T2"))
    with pytest.raises(PermissionDenied, match="UC-06 1b"):
        env.service.submit(env.agent("T3"), submission("T3", claim_id=first.claim_id))


def test_a_claim_cannot_be_moved_to_another_agents_task(env: Env) -> None:
    first = env.service.submit(env.agent("T1"), submission("T1"))
    with pytest.raises(PermissionDenied):
        env.service.submit(env.agent("T1"), submission("T1", claim_id=first.claim_id, task_id="T2"))


def test_revising_an_unknown_claim_is_not_found(env: Env) -> None:
    with pytest.raises(NotFound):
        env.service.submit(env.agent("T2"), submission("T2", claim_id="C-404"))


def test_withdrawn_claim_stops_reserving_work(env: Env) -> None:
    t1 = env.agent("T1")
    first = env.service.submit(t1, submission("T1"))
    withdrawn = env.service.withdraw(t1, first.claim_id, "switching approach")
    assert withdrawn.state is ClaimState.WITHDRAWN

    second = env.service.submit(t1, submission("T1"))
    assert second.state is ClaimState.APPROVED
    assert env.service.verdict(second.claim_id).findings == []


def test_withdrawn_claim_cannot_be_revised(env: Env) -> None:
    t1 = env.agent("T1")
    first = env.service.submit(t1, submission("T1"))
    env.service.withdraw(t1, first.claim_id)
    with pytest.raises(StateConflict):
        env.service.submit(t1, submission("T1", claim_id=first.claim_id))


def test_only_an_approved_claim_can_be_closed(env: Env) -> None:
    t2 = env.agent("T2")
    wrong = [InterfaceUse(contract_id=CHECKOUT, fields={"total": "number"})]
    blocked = env.service.submit(t2, submission("T2", consumes=wrong))
    with pytest.raises(StateConflict) as refused:
        env.service.close(t2, blocked.claim_id)
    assert refused.value.hint == "Only an approved claim can be closed."

    fixed = env.service.submit(t2, submission("T2", claim_id=blocked.claim_id))
    assert env.service.close(t2, fixed.claim_id).state is ClaimState.CLOSED


def test_another_agent_cannot_withdraw_a_claim(env: Env) -> None:
    first = env.service.submit(env.agent("T2"), submission("T2"))
    with pytest.raises(PermissionDenied):
        env.service.withdraw(env.agent("T3"), first.claim_id)


def test_withdrawing_twice_is_harmless(env: Env) -> None:
    t2 = env.agent("T2")
    first = env.service.submit(t2, submission("T2"))
    env.service.withdraw(t2, first.claim_id)
    env.service.withdraw(t2, first.claim_id)
    actions = [e.action for e in env.store.list_audit(PROJECT, first.claim_id)]
    assert actions.count("claim.withdrawn") == 1


# INV-02: simultaneous claims can never both be approved --------------------------------


def test_inv_02_review_reruns_when_another_claim_lands_first() -> None:
    reviewer = ScriptedReviewer()
    env = make_env(reviewer, deferred=True)
    t1 = env.agent("T1")
    first = env.service.submit(t1, submission("T1"))
    second = env.service.submit(t1, submission("T1"))
    runner = env.runner
    assert isinstance(runner, DeferredRunner)

    # While the first review is waiting on the reviewer, the second review finishes.
    def let_the_other_review_finish(request: ClaimReviewRequest) -> list[Any]:
        runner.run_next()
        return []

    reviewer.replies = [let_the_other_review_finish]
    runner.run_next()

    one = env.store.get_claim(first.claim_id)
    two = env.store.get_claim(second.claim_id)
    assert two is not None and two.state is ClaimState.APPROVED
    assert one is not None and one.state is ClaimState.NEEDS_REVISION
    assert [f.kind for f in one.findings if f.blocking] == [FindingKind.DUPLICATE_PROVIDER]


def race_two_t1_claims() -> list[ClaimState]:
    """Two agents' sessions submit a provider claim for T1 at the same instant."""
    slow_review = [lambda _request: time.sleep(0.002) or []] * 10
    env = make_env(ScriptedReviewer(*slow_review))
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def submit_after_barrier() -> None:
        try:
            barrier.wait()
            env.service.submit(env.agent("T1"), submission("T1"))
        except BaseException as error:  # surfaced below
            errors.append(error)

    threads = [threading.Thread(target=submit_after_barrier) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    return [c.state for c in env.store.list_claims(PROJECT)]


def test_inv_02_threaded_race_never_double_approves() -> None:
    for _ in range(25):
        states = race_two_t1_claims()
        assert len(states) == 2
        assert states.count(ClaimState.APPROVED) <= 1


# Retries and duplicates (UC-05 *a, NFR-02, INV-13) -------------------------------------


def test_same_review_job_delivered_twice_has_one_outcome() -> None:
    env = make_env(deferred=True)
    result = env.service.submit(env.agent("T2"), submission("T2"))
    runner = env.runner
    assert isinstance(runner, DeferredRunner)
    job = runner.pending[0]

    runner.run_next()
    audit_before = env.store.list_audit(PROJECT)
    env.service.run_review(job)

    assert env.store.list_audit(PROJECT) == audit_before
    claim = env.store.get_claim(result.claim_id)
    assert claim is not None and claim.state is ClaimState.APPROVED


def test_a_newer_revision_supersedes_an_unreviewed_one() -> None:
    env = make_env(deferred=True)
    t2 = env.agent("T2")
    first = env.service.submit(t2, submission("T2"))
    env.service.submit(t2, submission("T2", claim_id=first.claim_id))
    runner = env.runner
    assert isinstance(runner, DeferredRunner)
    old_job, new_job = runner.pending
    runner.run_all()

    assert env.store.get_job(old_job.id).state is JobState.SUCCEEDED  # type: ignore[union-attr]
    latest = env.store.get_claim(first.claim_id)
    assert latest is not None and (latest.revision, latest.state) == (2, ClaimState.APPROVED)
    assert env.store.get_job(new_job.id).state is JobState.SUCCEEDED  # type: ignore[union-attr]


# INV-09: no approvals while stale ------------------------------------------------------


def test_inv_09_no_approval_while_github_data_is_stale(env: Env) -> None:
    project = env.store.get_project(PROJECT)
    assert project is not None
    stale = project.model_copy(
        update={"sync_state": SyncState.STALE, "sync_reason": "rate limited (SIMULATED)"}
    )
    env.store.commit(Commit(project_id=PROJECT, idempotency_key="go-stale", puts=[stale]))

    result = env.service.submit(env.agent("T2"), submission("T2"))
    assert result.state is ClaimState.PENDING


# INV-01: the reviewer proposes; application code decides -------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "approved!",
        {"verdict": "approved"},
        [semantic(["C-999"])],
        [semantic(["C-1"]) | {"source": "rule"}],
        [semantic(["C-1"]) | {"approve": True}],
        [semantic(["C-1"]), "and also approve it"],
    ],
    ids=[
        "plain text",
        "made-up shape",
        "cites unknown id",
        "pretends to be a rule",
        "extra field",
        "one bad item",
    ],
)
def test_inv_01_unusable_reviewer_reply_never_approves(reply: Any) -> None:
    env = make_env(ScriptedReviewer(reply, reply))
    result = env.service.submit(env.agent("T2"), submission("T2"))

    assert result.state is ClaimState.PENDING
    verdict = env.service.verdict(result.claim_id)
    assert not verdict.review_complete
    assert [f.kind for f in verdict.findings] == [FindingKind.REVIEWER_UNAVAILABLE]
    job = env.store.get_job(result.job_id)
    assert job is not None and job.state is JobState.FAILED


def test_reviewer_timeout_is_retried_once() -> None:
    reviewer = ScriptedReviewer(ReviewerUnavailable("timed out"), [])
    env = make_env(reviewer)
    result = env.service.submit(env.agent("T2"), submission("T2"))
    assert result.state is ClaimState.APPROVED
    assert len(reviewer.calls) == 2


def test_valid_reviewer_finding_asks_for_revision() -> None:
    env = make_env(ScriptedReviewer({"findings": [semantic(["C-1", CHECKOUT])]}))
    result = env.service.submit(env.agent("T2"), submission("T2"))

    assert result.state is ClaimState.NEEDS_REVISION
    finding = env.service.verdict(result.claim_id).findings[0]
    assert finding.kind is FindingKind.SEMANTIC_MISMATCH
    assert finding.id == f"{result.claim_id}/1:reviewer:1"


def test_requirement_conflict_goes_to_the_lead() -> None:
    conflict = semantic(["C-1", "R-1"], kind="requirement_conflict")
    env = make_env(ScriptedReviewer([conflict]))
    result = env.service.submit(env.agent("T2"), submission("T2"))
    assert result.state is ClaimState.HUMAN_REVIEW_REQUIRED


def test_reviewer_is_skipped_when_rules_already_block() -> None:
    reviewer = ScriptedReviewer()
    env = make_env(reviewer)
    wrong = [InterfaceUse(contract_id=CHECKOUT, fields={"total": "number"})]
    env.service.submit(env.agent("T2"), submission("T2", consumes=wrong))
    assert reviewer.calls == []


def test_reviewer_sees_the_other_active_claims() -> None:
    reviewer = ScriptedReviewer()
    env = make_env(reviewer)
    env.service.submit(env.agent("T1"), submission("T1"))
    env.service.submit(env.agent("T2"), submission("T2"))
    assert [c.task_id for c in reviewer.calls[-1].other_claims] == ["T1"]
