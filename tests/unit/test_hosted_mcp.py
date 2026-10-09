"""H-2: the hosted MCP connector, driven by an MCP client as two different people."""

from __future__ import annotations

import re
from typing import Any

import pytest
from mcp import Client

from demo_fixture import NOW
from midflight.adapters.clock import FixedClock
from midflight.adapters.fake_github import FakeRepoAccess
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import build_services
from midflight.mcp.hosted import build_hosted_server
from midflight.mcp.instructions import HOSTED_INSTRUCTIONS
from midflight.ports import GitHubAccount
from midflight.services.projects import ProjectService

pytestmark = pytest.mark.anyio

REPO = "acme/shop"
CHECKOUT = "checkout-response"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Team:
    """One server, and a switch for who is calling it."""

    def __init__(self) -> None:
        store = MemoryStore()
        clock = FixedClock(NOW)
        self.services = build_services(store, clock)
        self.repos = FakeRepoAccess(installations={REPO: 4242}, admins={(REPO, "somesh")})
        self.projects = ProjectService(store, clock, self.repos, self.services.plans)
        self.users = {
            "somesh": self.projects.sign_in(GitHubAccount(101, "somesh")).id,
            "frederik": self.projects.sign_in(GitHubAccount(202, "frederik")).id,
            "stranger": self.projects.sign_in(GitHubAccount(303, "stranger")).id,
        }
        self.caller = "somesh"
        self.server = build_hosted_server(
            self.services, self.projects, current_user_id=lambda: self.users[self.caller]
        )

    async def call(self, client: Client, who: str, tool: str, **args: Any) -> str:
        self.caller = who
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        return result.content[0].text  # type: ignore[union-attr]


def plan_args() -> dict[str, Any]:
    return {
        "requirements": [{"id": "R-1", "description": "Show the order total at checkout"}],
        "tasks": [
            {
                "id": "T1",
                "title": "Checkout API",
                "owner": "somesh",
                "requirement_ids": ["R-1"],
                "provides": [CHECKOUT],
            },
            {
                "id": "T2",
                "title": "Checkout page",
                "owner": "frederik",
                "requirement_ids": ["R-1"],
                "consumes": [CHECKOUT],
            },
        ],
        "contracts": [
            {
                "id": CHECKOUT,
                "provider_task": "T1",
                "consumer_tasks": ["T2"],
                "fields": {"total_cents": "integer"},
            },
        ],
    }


def claim_args(**overrides: Any) -> dict[str, Any]:
    return {
        "task_id": "T2",
        "plan_version": 1,
        "branch": "t2-checkout-page",
        "base_sha": "9f3e1a2",
        "requirement_ids": ["R-1"],
        "consumes": [{"contract_id": CHECKOUT, "fields": {"total": "number"}}],
        "assumptions": ["total is a decimal number of dollars"],
        "acceptance_criteria": ["The page shows $49.99"],
    } | overrides


async def test_connector_offers_the_tools_and_getting_started_instructions() -> None:
    team = Team()
    async with Client(team.server) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert client.instructions == HOSTED_INSTRUCTIONS
    assert {
        "my_projects",
        "create_project",
        "join_project",
        "check_in",
        "submit_claim",
        "acknowledge_directive",
        "project_status",
        "propose_plan",
        "approve_plan",
        "assign_task",
        "resolve_escalation",
        "rotate_join_code",
        "remove_member",
    } == names


async def test_the_whole_team_flow_through_the_connector() -> None:
    team = Team()
    async with Client(team.server) as client:
        # The lead has no project yet, then creates one.
        assert "aren't in a Midflight project" in await team.call(client, "somesh", "my_projects")
        created = await team.call(client, "somesh", "create_project", repository=REPO)
        code = re.search(r"Join code: (MF-\S+)", created).group(1)  # type: ignore[union-attr]

        # A teammate joins with the code.
        joined = await team.call(client, "frederik", "join_project", join_code=code)
        assert "You're a member" in joined and "Lead: somesh" in joined

        # The lead writes the plan, naming owners by GitHub login, and approves it.
        proposed = await team.call(client, "somesh", "propose_plan", **plan_args())
        assert "Proposed plan v1" in proposed
        approved = await team.call(client, "somesh", "approve_plan", version=1, reason="v1")
        assert "Plan v1 is approved" in approved

        # The teammate sees their task and contract, and the total conflict is caught.
        look = await team.call(client, "frederik", "check_in")
        assert "Task T2: Checkout page (plan v1)" in look and "total_cents: integer" in look
        caught = await team.call(client, "frederik", "submit_claim", **claim_args())
        assert "NEEDS_REVISION" in caught
        assert "Fix: Read `total_cents: integer`, not `total`." in caught

        claim_id = re.search(r"Claim (C-\d+)", caught).group(1)  # type: ignore[union-attr]
        fixed = claim_args(
            claim_id=claim_id,
            consumes=[{"contract_id": CHECKOUT, "fields": {"total_cents": "integer"}}],
            reason="use total_cents",
        )
        assert "rev 2: APPROVED" in await team.call(client, "frederik", "submit_claim", **fixed)

        # The lead sees it all at a glance.
        status = await team.call(client, "somesh", "project_status")
        assert "Join code:" in status
        assert "- frederik (agent): T2" in status
        assert f"T2 Checkout page (frederik): claim {claim_id} rev 2 approved" in status


async def test_only_the_lead_writes_the_plan_and_sees_the_code() -> None:
    team = Team()
    async with Client(team.server) as client:
        created = await team.call(client, "somesh", "create_project", repository=REPO)
        code = re.search(r"Join code: (MF-\S+)", created).group(1)  # type: ignore[union-attr]
        await team.call(client, "frederik", "join_project", join_code=code)

        refused = await team.call(client, "frederik", "propose_plan", **plan_args())
        assert "only the project's lead" in refused
        status = await team.call(client, "frederik", "project_status")
        assert "Join code" not in status


async def test_plan_owners_must_have_joined() -> None:
    team = Team()
    async with Client(team.server) as client:
        await team.call(client, "somesh", "create_project", repository=REPO)
        refused = await team.call(client, "somesh", "propose_plan", **plan_args())
    assert "frederik isn't a member" in refused
    assert "Share the join code" in refused


async def test_strangers_see_nothing() -> None:
    team = Team()
    async with Client(team.server) as client:
        await team.call(client, "somesh", "create_project", repository=REPO)
        assert "aren't in a Midflight project" in await team.call(client, "stranger", "check_in")
        refused = await team.call(client, "stranger", "join_project", join_code="MF-AAAA-BBBB")
    assert "no project has that join code" in refused


async def test_a_removed_member_is_refused() -> None:
    team = Team()
    async with Client(team.server) as client:
        created = await team.call(client, "somesh", "create_project", repository=REPO)
        code = re.search(r"Join code: (MF-\S+)", created).group(1)  # type: ignore[union-attr]
        await team.call(client, "frederik", "join_project", join_code=code)
        removed = await team.call(client, "somesh", "remove_member", member="frederik")
        assert "no longer a member" in removed
        assert "aren't in a Midflight project" in await team.call(client, "frederik", "check_in")


async def test_creating_a_project_without_the_app_explains_how_to_install() -> None:
    team = Team()
    async with Client(team.server) as client:
        refused = await team.call(client, "somesh", "create_project", repository="acme/other")
    assert "isn't installed" in refused and "github.com/apps/" in refused


async def test_two_teams_claims_never_collide() -> None:
    team = Team()
    team.repos.installations["acme/api"] = 7
    team.repos.admins.add(("acme/api", "frederik"))
    async with Client(team.server) as client:
        for lead, repo, owner in (("somesh", REPO, "somesh"), ("frederik", "acme/api", "frederik")):
            await team.call(client, lead, "create_project", repository=repo)
            plan = plan_args()
            plan["tasks"] = [t | {"owner": owner} for t in plan["tasks"]]
            await team.call(client, lead, "propose_plan", **plan)
            await team.call(client, lead, "approve_plan", version=1, reason="v1")
            await team.call(client, lead, "submit_claim", **claim_args())
    claims = [
        c
        for p in ("somesh", "frederik")
        for c in team.services.store.list_claims(
            team.projects.membership(team.projects.user(team.users[p])).project.id
        )
    ]
    assert len({c.id for c in claims}) == 2, [c.id for c in claims]
