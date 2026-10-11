"""A Midflight for one trial, on this machine: no AWS, no sign-in, nothing kept.

The trials in this folder normally use the live service. This runs the Midflight of the
checkout it is started from instead, so two versions of the code can be compared on the
same case under the same conditions:

    python experiment/local_midflight.py serve          # prints the project id, then serves
    python experiment/local_midflight.py lead plan      # the lead approves the plan change
    python experiment/local_midflight.py lead rule      # the lead decides open escalations
    python experiment/local_midflight.py lead status

Then run the trial against it (see experiment/README.md):

    MIDFLIGHT_MCP_CONFIG=experiment/midflight-local.mcp.json \\
    MIDFLIGHT_EXPERIMENT_PROJECT=<project id> python experiment/run.py hirebot-pro B3 ...

What is the same as a live trial: the connector and everything behind it, one person
signed in who leads the project and owns every task, and the HireBot Pro plan.
What is different, and must be said with any result: everything is held in memory, and
the AI reviewer is scripted. It raises the case's one real conflict (reports keeps a 20%
cancellation fee, bookings refunds in full) as a question for the lead, which is what
the live reviewer did in run B2, and nothing else.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
import urllib.request
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from mcp import Client
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from midflight.adapters.clock import SystemClock
from midflight.adapters.fake_github import FakeRepoAccess
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import build_services
from midflight.main import _without_event_stream
from midflight.mcp.hosted import build_hosted_server
from midflight.ports import ClaimReviewRequest, GitHubAccount
from midflight.services.projects import ProjectService

HERE = Path(__file__).parent
PLANS = HERE.parent / "evals" / "escalations" / "hirebot.json"
REPO = "acme/hirebot"
PORT = 8765
LEAD = "somesh"
# The lead's fixed decision in this case (experiment/cases/hirebot-pro/README.md).
RULING = (
    "Cancelling a booking keeps a cancellation fee of 10% of the booking's total (rounded "
    "half up); the customer is refunded the rest. The fee counts as revenue in the report."
)


class Reviewer:
    """Raises the case's one real conflict, the way the live reviewer did in run B2."""

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        claims = [request.claim, *request.other_claims]
        reports = next((c for c in claims if c.task_id == "T4"), None)
        bookings = next((c for c in claims if c.task_id == "T3"), None)
        if request.claim.task_id not in ("T3", "T4") or reports is None or bookings is None:
            return []
        fee, refund = " ".join(reports.assumptions), " ".join(bookings.assumptions)
        if "20%" not in fee or "10%" in fee or "10%" in refund:
            return []
        return [
            {
                "id": "x",
                "kind": "requirement_conflict",
                "severity": "blocking",
                "source": "reviewer",
                "affected_ids": [bookings.id, reports.id],
                "explanation": f"{reports.id} assumes a 20% cancellation fee is added to "
                f"revenue, while {bookings.id} assumes cancelled bookings are refunded in "
                "full and earn nothing. These contradict each other on how a cancellation "
                "affects revenue.",
                "proposed_correction": "The lead must decide whether a cancelled booking "
                "keeps a fee or is refunded in full: it changes what the customer pays and "
                "what the business earns, and no requirement answers it.",
            }
        ]

    def review_commit(self, request: object) -> Any:
        return []


def plan_args(version: int) -> dict[str, Any]:
    """The HireBot Pro plan as recorded: 3 is the starting plan, 4 the lead's change."""
    cases = json.loads(PLANS.read_text(encoding="utf-8"))["cases"]
    plan = next(c["plan"] for c in cases if c["plan"]["version"] == version)
    return {
        "requirements": plan["requirements"],
        "tasks": [t | {"owner": LEAD} for t in plan["tasks"]],
        "contracts": [{k: v for k, v in c.items() if k != "version"} for c in plan["contracts"]],
    }


def serve(port: int) -> None:
    import uvicorn

    store, clock = MemoryStore(), SystemClock()
    services = build_services(store, clock, Reviewer())
    repos = FakeRepoAccess(installations={REPO: 1}, admins={(REPO, LEAD)})
    projects = ProjectService(store, clock, repos, services.plans)
    user = projects.sign_in(GitHubAccount(1, LEAD)).id
    server = build_hosted_server(services, projects, current_user_id=lambda: user)

    async def tool(called: str, /, **args: Any) -> str:
        async with Client(server) as client:
            result = await client.call_tool(called, args)
            return result.content[0].text  # type: ignore[union-attr]

    async def approve(version: int, reason: str) -> str:
        proposed = await tool("propose_plan", **plan_args(version))
        number = int(re.search(r"Proposed plan v(\d+)", proposed).group(1))  # type: ignore[union-attr]
        return await tool("approve_plan", version=number, reason=reason)

    async def lead(request: Request) -> PlainTextResponse:
        action = request.path_params["action"]
        if action == "plan":
            return PlainTextResponse(await approve(4, "half-hour bookings and rush orders"))
        status = await tool("project_status")
        if action == "status":
            return PlainTextResponse(status)
        waiting = re.findall(r"^- (E-\d+) ", status.split("Decisions in force")[0], re.M)
        done = [
            await tool(
                "resolve_escalation",
                escalation_id=e,
                resolution="request_revision",
                reason=RULING,
            )
            for e in waiting
        ]
        return PlainTextResponse("\n".join(done) or "No escalation is waiting.")

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        created = await tool("create_project", repository=REPO, name="HireBot experiment")
        project = re.search(r"\b(hirebot-[0-9a-f]{4})\b", created).group(1)  # type: ignore[union-attr]
        await approve(3, "the starting plan")
        print(f"PROJECT {project}", flush=True)
        async with server.session_manager.run():
            yield

    mcp_app = server.streamable_http_app(stateless_http=True, json_response=True)
    app = Starlette(
        routes=[
            Route("/lead/{action}", lead, methods=["POST"]),
            Mount("/", _without_event_stream(mcp_app)),
        ],
        lifespan=lifespan,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main() -> None:
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 else PORT)
    elif step == "lead" and len(sys.argv) > 2 and sys.argv[2] in ("plan", "rule", "status"):
        url = f"http://127.0.0.1:{PORT}/lead/{sys.argv[2]}"
        with urllib.request.urlopen(urllib.request.Request(url, method="POST")) as reply:
            print(reply.read().decode("utf-8"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
