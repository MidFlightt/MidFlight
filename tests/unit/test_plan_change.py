"""S-6: a plan change reaches exactly the affected tasks (UC-03, UC-08, UC-09, UC-16)."""

from __future__ import annotations

import pytest

from demo_fixture import NOW, make_plan, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services
from midflight.domain.impact import affected_tasks
from midflight.domain.models import (
    ClaimState,
    DirectiveResponse,
    DirectiveSource,
    DirectiveState,
    FieldType,
    FindingKind,
    Participant,
    Requirement,
    SyncState,
)
from midflight.ports import Commit
from midflight.services.errors import StateConflict
from midflight.services.plans import PlanDraft

CHECKOUT = "checkout-response"


@pytest.fixture
def team() -> tuple[Services, dict[str, Participant]]:
    store = MemoryStore()
    people = seed(store)
    return build_services(store, FixedClock(NOW)), people


def approve_all_three(services: Services, people: dict[str, Participant]) -> dict[str, str]:
    """T1, T2, and T3 each get an approved claim on plan v1. Returns claim id per task."""
    claims = {}
    for task in ("T1", "T2", "T3"):
        result = services.claims.submit(people[f"p-{task.lower()}"], submission(task))
        assert result.state is ClaimState.APPROVED
        claims[task] = result.claim_id
    return claims


def change_plan(services: Services, lead: Participant, version: int = 2) -> None:
    """The lead adds `currency` (D2): propose the demo plan v2 and approve it."""
    plan = make_plan(version)
    draft = PlanDraft(requirements=plan.requirements, tasks=plan.tasks, contracts=plan.contracts)
    proposed = services.plans.propose(lead, draft)
    services.plans.approve(lead, proposed.version, "Checkout must show the currency")


# Which tasks a change touches (pure) ---------------------------------------------------


def test_a_contract_change_affects_its_provider_and_consumer_only() -> None:
    old, new = make_plan(1), make_plan(2)
    assert affected_tasks(old, new, [CHECKOUT]) == {"T1": [CHECKOUT], "T2": [CHECKOUT]}


def test_a_requirement_change_affects_the_tasks_that_implement_it() -> None:
    old, new = make_plan(1), make_plan(1)
    assert affected_tasks(old, new, ["R-2"]) == {"T3": ["R-2"]}


def test_a_removed_contract_still_reaches_its_old_provider() -> None:
    old = make_plan(1)
    tasks = [t.model_copy(update={"provides": [], "consumes": []}) for t in old.tasks]
    new = old.model_copy(update={"contracts": [], "tasks": tasks})
    assert set(affected_tasks(old, new, [CHECKOUT])) == {"T1", "T2"}


# The currency scenario (UC-08) ---------------------------------------------------------


def test_currency_change_sends_directives_to_t1_and_t2_and_none_to_t3(team) -> None:
    services, people = team
    approve_all_three(services, people)
    change_plan(services, people["p-lead"])

    directives = services.store.list_directives("demo")
    assert sorted(d.task_id for d in directives) == ["T1", "T2"]
    for d in directives:
        assert d.source is DirectiveSource.PLAN_CHANGE
        assert d.state is DirectiveState.QUEUED
        assert d.plan_version == 2 and d.blocking
        assert d.changed_ids == [CHECKOUT]
        assert "currency: string" in d.requested_adjustment
        assert d.reason == "Checkout must show the currency"
    assert {d.recipient_id for d in directives} == {"p-t1", "p-t2"}


def test_affected_approvals_are_reviewed_again_and_unaffected_ones_stay(team) -> None:
    services, people = team
    claims = approve_all_three(services, people)
    change_plan(services, people["p-lead"])

    for task in ("T1", "T2"):
        claim = services.store.get_claim(claims[task])
        assert claim.state is ClaimState.NEEDS_REVISION
        assert FindingKind.STALE_PLAN in {f.kind for f in claim.findings}
    assert services.store.get_claim(claims["T3"]).state is ClaimState.APPROVED


def test_unaffected_task_can_still_push(team) -> None:
    services, people = team
    approve_all_three(services, people)
    change_plan(services, people["p-lead"])
    reply = services.check_ins.check_in(people["p-t3"], "T3")
    assert reply.ready_to_push and not reply.directives


def test_directive_arrives_at_check_in_and_blocks_the_push_until_answered(team) -> None:
    services, people = team
    claims = approve_all_three(services, people)
    change_plan(services, people["p-lead"])
    t2 = people["p-t2"]

    reply = services.check_ins.check_in(t2, "T2")
    [directive] = reply.directives
    assert directive.state is DirectiveState.DELIVERED
    assert not reply.ready_to_push

    services.directives.acknowledge(t2, directive.id, DirectiveResponse.ACKNOWLEDGED)
    revised = submission(
        "T2",
        claim_id=claims["T2"],
        plan_version=2,
        consumes=[{"contract_id": CHECKOUT, "fields": {"total_cents": "integer"}}],
    )
    assert services.claims.submit(t2, revised).state is ClaimState.APPROVED
    assert services.check_ins.check_in(t2, "T2").ready_to_push


def test_one_directive_per_plan_version_and_task(team) -> None:
    services, people = team
    approve_all_three(services, people)
    change_plan(services, people["p-lead"])
    with pytest.raises(StateConflict):
        services.plans.approve(people["p-lead"], 2, "again")
    assert len(services.store.list_directives("demo")) == 2


@pytest.mark.parametrize(
    "old_state",
    [DirectiveState.QUEUED, DirectiveState.DELIVERED, DirectiveState.NEEDS_CLARIFICATION],
)
def test_a_newer_plan_supersedes_unanswered_directives(team, old_state) -> None:
    services, people = team
    approve_all_three(services, people)
    change_plan(services, people["p-lead"])
    if old_state is not DirectiveState.QUEUED:
        for task in ("T1", "T2"):
            actor = people[f"p-{task.lower()}"]
            [directive] = services.check_ins.check_in(actor, task).directives
            if old_state is DirectiveState.NEEDS_CLARIFICATION:
                services.directives.acknowledge(
                    actor, directive.id, DirectiveResponse.NEEDS_CLARIFICATION, "Which currency?"
                )
    # Plan v3 changes the contract again (adds a field to it).
    plan = make_plan(2)
    contract = plan.contracts[0]
    contract = contract.model_copy(
        update={"fields": {**contract.fields, "tax_cents": FieldType.INTEGER}}
    )
    draft = PlanDraft(requirements=plan.requirements, tasks=plan.tasks, contracts=[contract])
    lead = people["p-lead"]
    services.plans.approve(lead, services.plans.propose(lead, draft).version, "Show tax too")

    by_version = {
        (d.task_id, d.plan_version): d.state for d in services.store.list_directives("demo")
    }
    assert by_version[("T1", 2)] is DirectiveState.SUPERSEDED
    assert by_version[("T2", 2)] is DirectiveState.SUPERSEDED
    assert by_version[("T1", 3)] is DirectiveState.QUEUED
    assert by_version[("T2", 3)] is DirectiveState.QUEUED


def test_directives_are_held_while_github_data_is_stale(team) -> None:
    services, people = team
    approve_all_three(services, people)
    change_plan(services, people["p-lead"])
    store = services.store
    project = store.get_project("demo")
    stale = project.model_copy(
        update={"sync_state": SyncState.STALE, "sync_reason": "GitHub rate limit"}
    )
    store.commit(Commit(project_id="demo", idempotency_key="stale", puts=[stale]))

    reply = services.check_ins.check_in(people["p-t2"], "T2")
    assert reply.stale and not reply.directives
    assert store.list_directives("demo", "T2")[0].state is DirectiveState.QUEUED


def test_the_first_plan_sends_no_directives(team) -> None:
    services, _people = team
    assert services.store.list_directives("demo") == []


def test_the_change_is_audited_with_the_plan_version(team) -> None:
    services, people = team
    approve_all_three(services, people)
    change_plan(services, people["p-lead"])
    [event] = [e for e in services.store.list_audit("demo") if e.action == "plan.propagated"]
    assert event.versions == {"plan": 2}
    assert "T1" in event.reason and "T2" in event.reason and "T3" not in event.reason


def test_a_directive_spells_out_a_new_requirement(team) -> None:
    services, people = team
    approve_all_three(services, people)
    plan = make_plan(1)
    promo = Requirement(id="R-9", description="Promo code BEEPBOOP takes 10% off")
    tasks = [
        t.model_copy(update={"requirement_ids": [*t.requirement_ids, "R-9"]}) if t.id == "T2" else t
        for t in plan.tasks
    ]
    draft = PlanDraft(
        requirements=[*plan.requirements, promo], tasks=tasks, contracts=plan.contracts
    )
    lead = people["p-lead"]
    services.plans.approve(lead, services.plans.propose(lead, draft).version, "Prime Day")
    [directive] = services.store.list_directives("demo")
    assert directive.task_id == "T2"
    assert (
        "new requirement R-9: Promo code BEEPBOOP takes 10% off" in directive.requested_adjustment
    )
