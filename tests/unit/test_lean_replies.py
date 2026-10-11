"""S-13: a reply leaves out what the agent already has (D34).

Everything Midflight returns stays in the agent's context and is paid for again on every
later step. A check-in reply therefore ends with a marker. An agent that passes it back
as `since` gets the task's requirements and contracts, a decision, or a neighbour's
assumption only when it is new, with what was left out named. An agent that passes
nothing gets everything. A claim revision says only what changes.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from mcp import Client

from demo_fixture import NOW, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.fake_github import FakeRepoAccess
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services
from midflight.api.views import check_in_json
from midflight.domain.models import DirectiveResponse, FieldType, Participant, Resolution
from midflight.mcp.hosted import build_hosted_server
from midflight.mcp.replies import (
    REPEAT_HINT,
    SAME_CONTRACTS,
    SAME_PLAN,
    check_in_text,
    plan_lines,
)
from midflight.ports import GitHubAccount
from midflight.services.check_in import marker_for, read_marker
from midflight.services.plans import PlanDraft
from midflight.services.projects import ProjectService

HELPER = "T1 exposes format_total() for the page to call"
FIELDS = "checkout-response (v1, provider T1): total_cents: integer"


def marker(reply: str) -> str:
    """The marker a check-in reply ends with."""
    found = re.search(r'pass since="([^"]+)"', reply.splitlines()[-1])
    assert found, reply
    return found.group(1)


class Team:
    """The demo project, with a clock that moves between calls as a real one does."""

    def __init__(self) -> None:
        self.store = MemoryStore()
        seed(self.store)
        self.clock = FixedClock(NOW)
        self.services: Services = build_services(self.store, self.clock)

    def person(self, task: str) -> Participant:
        """As the API sees the caller: read from the store."""
        found = self.store.get_participant("p-lead" if task == "lead" else f"p-{task.lower()}")
        assert found is not None
        return found

    def claim(self, task: str, **overrides: Any) -> str:
        self.clock.advance(minutes=1)
        agent = self.person(task)
        return self.services.claims.submit(agent, submission(task, **overrides)).claim_id

    def check_in(self, task: str, since: str | None = None, peek: bool = False) -> str:
        self.clock.advance(minutes=1)
        reply = self.services.check_ins.check_in(self.person(task), task, peek, since)
        return check_in_text(check_in_json(reply))

    def new_plan(self, **changes: Any) -> None:
        """The lead approves the next plan version: the current one with `changes`."""
        self.clock.advance(minutes=1)
        project = self.store.get_project("demo")
        assert project is not None and project.current_plan_version is not None
        plan = self.store.get_plan("demo", project.current_plan_version)
        assert plan is not None
        draft = PlanDraft(
            requirements=changes.get("requirements", plan.requirements),
            tasks=changes.get("tasks", plan.tasks),
            contracts=changes.get("contracts", plan.contracts),
        )
        proposed = self.services.plans.propose(self.person("lead"), draft)
        self.services.plans.approve(self.person("lead"), proposed.version, "test")

    def add_currency(self) -> None:
        plan = self.store.get_plan("demo", 1)
        assert plan is not None
        contract = plan.contracts[0]
        fields = contract.fields | {"currency": FieldType.STRING}
        self.new_plan(contracts=[contract.model_copy(update={"version": 2, "fields": fields})])


# The marker ---------------------------------------------------------------------------------


def test_a_marker_names_one_check_in_on_one_task() -> None:
    text = marker_for("T3", NOW)
    assert text == "T3.20261008T120000Z"
    later = NOW.replace(minute=5)
    # A little before the check-in: what was saved right then is sent once more.
    assert read_marker(text, "T3", later) == NOW.replace(hour=11, minute=59, second=55)


@pytest.mark.parametrize(
    "text", [None, "", "T3", "nonsense", "T2.20261008T120000Z", "T3.20261008T130000Z", "T3.x"]
)
def test_no_marker_another_tasks_a_future_or_an_unreadable_one_means_everything(
    text: str | None,
) -> None:
    assert read_marker(text, "T3", NOW.replace(minute=5)) is None


# Requirements and contracts -----------------------------------------------------------------


def test_a_check_in_without_a_marker_lists_everything() -> None:
    team = Team()
    first = team.check_in("T2")
    again = team.check_in("T2")
    for reply in (first, again):
        assert "Requirement R-1:" in reply and FIELDS in reply
        assert REPEAT_HINT not in reply
        assert marker(reply).startswith("T2.")


def test_with_the_marker_they_are_named_instead_of_repeated() -> None:
    team = Team()
    first = team.check_in("T2")
    later = team.check_in("T2", since=marker(first))
    assert "Requirement R-1:" not in later and FIELDS not in later
    assert SAME_PLAN in later and REPEAT_HINT in later
    assert len(later) < len(first)
    assert marker(later) != marker(first)


def test_two_sessions_on_one_account_hide_nothing_from_each_other() -> None:
    team = Team()
    mine = team.check_in("T2")
    # A second session of the same person has no marker: it gets everything.
    assert FIELDS in team.check_in("T2")
    assert FIELDS not in team.check_in("T2", since=marker(mine))


def test_a_plan_change_is_said_once_by_the_directive_that_delivers_it() -> None:
    team = Team()
    first = team.check_in("T2")
    team.add_currency()
    after = team.check_in("T2", since=marker(first))
    # The directive spells out the changed contract; the reply doesn't list it again.
    assert "contract checkout-response is now {total_cents: integer, currency: string}" in after
    assert "Requirements and contracts: changed as directive D-" in after
    assert "Build against:" not in after and "Requirement R-1:" not in after
    assert SAME_PLAN not in after


def test_without_the_directive_only_what_changed_is_listed() -> None:
    team = Team()
    first = team.check_in("T2")
    team.add_currency()
    reply = team.services.check_ins.check_in(team.person("T2"), "T2")
    [directive] = reply.directives
    team.services.directives.acknowledge(
        team.person("T2"), directive.id, DirectiveResponse.ACKNOWLEDGED
    )
    team.clock.advance(minutes=1)
    after = check_in_json(
        team.services.check_ins.check_in(team.person("T2"), "T2", since=marker(first))
    )
    assert after["plan_changed_ids"] == ["checkout-response"]
    assert plan_lines(after, after["plan_changed_ids"]) == [
        "",
        "Build against:",
        "  checkout-response (v2, provider T1): total_cents: integer, currency: string",
        "",
        "Unchanged since the check-in you named: R-1.",
    ]


def test_without_a_marker_a_changed_plan_is_listed_whole() -> None:
    team = Team()
    team.check_in("T2")
    team.add_currency()
    after = team.check_in("T2")
    assert "Requirement R-1:" in after and "currency: string" in after
    assert "Unchanged since" not in after and "changed as directive" not in after


def test_a_plan_change_elsewhere_does_not_send_them_again() -> None:
    team = Team()
    first = team.check_in("T2")
    plan = team.store.get_plan("demo", 1)
    assert plan is not None
    # T3 goes to someone else: a new plan version that says nothing new about T2.
    moved = [t.model_copy(update={"owner": "p-lead"}) if t.id == "T3" else t for t in plan.tasks]
    team.new_plan(tasks=moved)
    after = team.check_in("T2", since=marker(first))
    assert "(plan v2)" in after and SAME_PLAN in after


def test_a_marker_from_before_the_task_changed_hands_sends_them_again() -> None:
    team = Team()
    first = team.check_in("T3")
    plan = team.store.get_plan("demo", 1)
    assert plan is not None
    handed = [t.model_copy(update={"owner": "p-t2"}) if t.id == "T3" else t for t in plan.tasks]
    team.new_plan(tasks=handed)
    team.clock.advance(minutes=1)
    reply = team.services.check_ins.check_in(team.person("T2"), "T3", since=marker(first))
    assert reply.since_read and not reply.plan_seen


def test_a_peek_does_not_count_as_a_check_in() -> None:
    team = Team()
    # The push check and the directives after a tool reply show the agent only a part.
    team.check_in("T2", peek=True)
    assert team.person("T2").last_check_in_at is None
    assert "No changes since your last check-in" not in team.check_in("T2")


# Decisions, assumptions, the claim, directives ----------------------------------------------


def test_an_assumption_the_agent_has_is_counted_and_a_new_one_is_shown() -> None:
    team = Team()
    team.claim("T1")
    t2 = team.claim("T2", assumptions=[HELPER])
    first = team.check_in("T1")
    assert HELPER in first

    later = team.check_in("T1", since=marker(first))
    assert HELPER not in later
    assert "assumptions about yours sent before and unchanged: 1 (from T2)" in later

    # T2 revises: it repeats the old assumption and adds one. Only the new one is news.
    news = "T1 returns HTTP 400 with a JSON detail on a bad cart"
    team.claim("T2", claim_id=t2, assumptions=[HELPER, news])
    after = team.check_in("T1", since=marker(later))
    assert news in after and HELPER not in after
    assert "sent before and unchanged: 1 (from T2)" in after
    assert HELPER in team.check_in("T1")


def test_a_decision_the_agent_has_is_named_and_a_new_one_is_shown() -> None:
    team = Team()
    t1 = team.claim("T1")
    team.claim("T2", assumptions=[HELPER])
    team.check_in("T1")  # T1 sees the assumption...
    team.claim("T1", claim_id=t1)  # ...and doesn't object
    [agreed] = [e for e in team.store.list_escalations("demo") if e.resolution is not None]
    assert agreed.resolution is Resolution.CLARIFY_PLAN
    line = f"{agreed.id} (agreed between tasks): {HELPER}"

    first = team.check_in("T2")
    assert line in first
    later = team.check_in("T2", since=marker(first))
    assert line not in later
    assert f"Decisions sent before and still in force: {agreed.id}." in later
    assert line in team.check_in("T2")
    # Once agreed, it is listed with the decisions and not again as an assumption.
    for_t1 = team.check_in("T1")
    assert for_t1.count(HELPER) == 1 and "OTHER TASKS ASSUME" not in for_t1


def test_a_decision_made_after_the_marker_is_shown_in_full() -> None:
    team = Team()
    t1 = team.claim("T1")
    team.claim("T2", assumptions=[HELPER])
    before = team.check_in("T2")
    team.check_in("T1")
    team.claim("T1", claim_id=t1)
    after = team.check_in("T2", since=marker(before))
    assert f"(agreed between tasks): {HELPER}" in after
    assert "sent before and still in force" not in after


def test_with_the_marker_an_approved_claim_is_one_line() -> None:
    team = Team()
    claim_id = team.claim("T2")
    first = team.check_in("T2")
    assert "Midflight checked your declared intent" in first
    later = team.check_in("T2", since=marker(first))
    assert f"Your claim {claim_id} rev 1: APPROVED" in later and "Findings: none." in later
    assert "Midflight checked your declared intent" not in later
    assert "Next: plan your checkpoints" not in later
    assert "Ready to push: yes." in later


def test_a_directive_comes_with_its_reason_once() -> None:
    team = Team()
    team.claim("T2")
    first = team.check_in("T2")
    team.add_currency()
    delivered = team.check_in("T2", since=marker(first))
    assert "(delivered, blocking, plan v2)" in delivered and "  Why: " in delivered
    # Still open at the next check-in: the request is repeated, the reason isn't.
    again = team.check_in("T2", since=marker(delivered))
    assert "(delivered, blocking, plan v2)" in again and "  Why: " not in again
    assert "  Why: " in team.check_in("T2")


# Through the connector ----------------------------------------------------------------------

REPO = "acme/shop"
CHECKOUT = "checkout-response"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Connected:
    """One hosted server with a lead (somesh) and a teammate (frederik) who owns T2."""

    def __init__(self) -> None:
        store = MemoryStore()
        self.clock = FixedClock(NOW)
        self.services = build_services(store, self.clock)
        repos = FakeRepoAccess(installations={REPO: 4242}, admins={(REPO, "somesh")})
        self.projects = ProjectService(store, self.clock, repos, self.services.plans)
        self.users = {
            "somesh": self.projects.sign_in(GitHubAccount(101, "somesh")).id,
            "frederik": self.projects.sign_in(GitHubAccount(202, "frederik")).id,
        }
        self.caller = "somesh"
        self.server = build_hosted_server(
            self.services, self.projects, current_user_id=lambda: self.users[self.caller]
        )

    async def call(self, client: Client, who: str, tool: str, **args: Any) -> str:
        self.caller = who
        self.clock.advance(minutes=1)
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        return result.content[0].text  # type: ignore[union-attr]

    async def start(self, client: Client) -> None:
        created = await self.call(client, "somesh", "create_project", repository=REPO)
        code = re.search(r"Join code: (MF-\S+)", created).group(1)  # type: ignore[union-attr]
        await self.call(client, "frederik", "join_project", join_code=code)
        plan = {
            "requirements": [{"id": "R-1", "description": "Show the order total at checkout"}],
            "tasks": [
                {"id": "T1", "title": "Checkout API", "owner": "somesh",
                 "requirement_ids": ["R-1"], "provides": [CHECKOUT]},
                {"id": "T2", "title": "Checkout page", "owner": "frederik",
                 "requirement_ids": ["R-1"], "consumes": [CHECKOUT]},
            ],
            "contracts": [
                {"id": CHECKOUT, "provider_task": "T1", "consumer_tasks": ["T2"],
                 "fields": {"total_cents": "integer", "currency": "string", "items": "array"}},
            ],
        }  # fmt: skip
        await self.call(client, "somesh", "propose_plan", **plan)
        await self.call(client, "somesh", "approve_plan", version=1, reason="v1")


def claim_args(**overrides: Any) -> dict[str, Any]:
    return {
        "task_id": "T2",
        "plan_version": 1,
        "branch": "t2-checkout-page",
        "base_sha": "9f3e1a2",
        "requirement_ids": ["R-1"],
        "files": ["web/checkout.js"],
        "consumes": [{"contract_id": CHECKOUT, "fields": {"total_cents": "integer"}}],
        "assumptions": ["total_cents is an integer number of cents"],
        "acceptance_criteria": ["The page shows $49.99"],
    } | overrides


def claim_id_in(reply: str) -> str:
    found = re.search(r"Claim (C-\d+)", reply)
    assert found, reply
    return found.group(1)


@pytest.mark.anyio
async def test_check_in_with_since_through_the_connector() -> None:
    team = Connected()
    async with Client(team.server) as client:
        await team.start(client)
        first = await team.call(client, "frederik", "check_in")
        short = await team.call(client, "frederik", "check_in", since=marker(first))
        everything = await team.call(client, "frederik", "check_in")
    assert FIELDS in first and FIELDS in everything
    assert FIELDS not in short and SAME_PLAN in short


@pytest.mark.anyio
async def test_a_first_claim_gets_the_contract_list_and_a_revision_names_it() -> None:
    team = Connected()
    async with Client(team.server) as client:
        await team.start(client)
        first = await team.call(client, "frederik", "submit_claim", **claim_args())
        revised = await team.call(
            client, "frederik", "submit_claim", **claim_args(claim_id=claim_id_in(first))
        )
    assert "rev 1: APPROVED" in first and FIELDS in first and SAME_CONTRACTS not in first
    assert "rev 2: APPROVED" in revised and SAME_CONTRACTS in revised and FIELDS not in revised


@pytest.mark.anyio
async def test_a_revision_onto_a_new_plan_version_gets_the_contract_list() -> None:
    team = Connected()
    async with Client(team.server) as client:
        await team.start(client)
        first = await team.call(client, "frederik", "submit_claim", **claim_args())
        await team.call(client, "somesh", "assign_task", task_id="T1", member="somesh")
        revised = await team.call(
            client,
            "frederik",
            "submit_claim",
            **claim_args(claim_id=claim_id_in(first), plan_version=2),
        )
    assert "rev 2" in revised and "checkout-response (v2, provider T1)" in revised


@pytest.mark.anyio
async def test_a_revision_keeps_the_parts_it_leaves_out() -> None:
    team = Connected()
    async with Client(team.server) as client:
        await team.start(client)
        first = await team.call(client, "frederik", "submit_claim", **claim_args())
        claim_id = claim_id_in(first)
        revised = await team.call(
            client,
            "frederik",
            "submit_claim",
            task_id="T2",
            plan_version=1,
            branch="t2-checkout-page",
            base_sha="9f3e1a2",
            claim_id=claim_id,
            assumptions=["total_cents is cents", "T1 serves GET /checkout"],
        )
    assert "rev 2: APPROVED" in revised
    claim = team.services.store.get_claim(claim_id)
    assert claim is not None and claim.revision == 2
    assert claim.assumptions == ["total_cents is cents", "T1 serves GET /checkout"]
    # Everything it didn't mention is as the first revision had it.
    assert claim.files == ["web/checkout.js"]
    assert claim.requirement_ids == ["R-1"]
    assert claim.acceptance_criteria == ["The page shows $49.99"]
    assert [u.contract_id for u in claim.consumes] == [CHECKOUT]


@pytest.mark.anyio
async def test_a_revision_can_empty_a_list_by_passing_it_empty() -> None:
    team = Connected()
    async with Client(team.server) as client:
        await team.start(client)
        first = await team.call(client, "frederik", "submit_claim", **claim_args())
        claim_id = claim_id_in(first)
        emptied = claim_args(claim_id=claim_id, assumptions=[])
        await team.call(client, "frederik", "submit_claim", **emptied)
    claim = team.services.store.get_claim(claim_id)
    assert claim is not None and claim.assumptions == []


@pytest.mark.anyio
async def test_a_new_claim_takes_nothing_from_another_agents_claim() -> None:
    team = Connected()
    async with Client(team.server) as client:
        await team.start(client)
        first = await team.call(client, "frederik", "submit_claim", **claim_args())
        # The lead's agent names frederik's claim: refused, and nothing of it is reused.
        refused = await team.call(
            client,
            "somesh",
            "submit_claim",
            task_id="T1",
            plan_version=1,
            branch="t1-api",
            base_sha="9f3e1a2",
            claim_id=claim_id_in(first),
        )
    assert "Midflight refused this" in refused
    claim = team.services.store.get_claim(claim_id_in(first))
    assert claim is not None and claim.revision == 1
