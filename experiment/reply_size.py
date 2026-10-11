"""How much text Midflight puts into its agents' context, measured without spending tokens.

A trial's agents call Midflight a few dozen times. Everything it replies stays in their
context and is read again on every later step, so the size of those replies is most of
what Midflight costs over a plain chat file. This replays one recorded trial's calls
(HireBot Pro run B2: every `check_in`, `submit_claim`, and `acknowledge_directive`, in
order, with the words the agents really sent) against Midflight in memory, and adds up
what goes in and what comes back.

    python experiment/reply_size.py extract ../experiment-runs/hirebot-pro/B2/logs
    python experiment/reply_size.py run                   # agents call it as they did
    python experiment/reply_size.py run --since           # they pass the check-in marker
    python experiment/reply_size.py run --since --short   # and revise with only what changed

`extract` saves the calls next to the trial's results. `run` needs no network: the AI
reviewer is scripted to raise the one real conflict of the case (the cancellation fee),
and the lead's two actions are replayed from the case. It measures whichever Midflight is
on the Python path, so an older checkout can be measured with the same script:

    PYTHONPATH=../some-other-checkout python experiment/reply_size.py run

Tokens are estimated (a model's tokenizer isn't available offline): one per word, number,
or punctuation mark, and one per line break with its indent. Compare runs, don't quote
the absolute numbers.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp import Client

from midflight.adapters.clock import FixedClock
from midflight.adapters.fake_github import FakeRepoAccess
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import build_services
from midflight.mcp.hosted import build_hosted_server
from midflight.ports import ClaimReviewRequest, GitHubAccount
from midflight.services.projects import ProjectService

HERE = Path(__file__).parent
CALLS = HERE / "cases" / "hirebot-pro" / "results" / "B2" / "midflight-calls.json"
PLANS = HERE.parent / "evals" / "escalations" / "hirebot.json"
REPO = "acme/hirebot"
TOOLS = ("check_in", "submit_claim", "acknowledge_directive")
REVISED_PARTS = (
    "provides", "consumes", "assumptions", "files", "requirement_ids", "acceptance_criteria",
)  # fmt: skip
# The lead's ruling in run B2 (escalation E-27).
RULING = (
    "Cancelling a booking keeps a cancellation fee of 10% of the booking's total (rounded "
    "half up); the customer is refunded the rest. The fee counts as revenue in the report."
)


def tokens(text: str) -> int:
    return len(re.findall(r"\n[ \t]*|\w+|[^\w\s]", text))


# Extract ---------------------------------------------------------------------------------


def extract(logs: Path) -> list[dict[str, Any]]:
    """Every Midflight call the trial's agents made that Midflight answered, in order."""
    calls = []
    for log in sorted(logs.glob("[0-9]*.jsonl")):
        _, agent, label = log.stem.split("-", 2)
        pending: dict[str, dict[str, Any]] = {}
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            message = event.get("message") if isinstance(event, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                tool = str(block.get("name", "")).rsplit("__", 1)[-1]
                if block.get("type") == "tool_use" and tool in TOOLS:
                    pending[block["id"]] = {
                        "agent": agent,
                        "phase": label,
                        "tool": tool,
                        "input": block["input"],
                    }
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                    call = pending.pop(block["tool_use_id"])
                    if not block.get("is_error"):  # a failed call was made again
                        calls.append(call)
    return calls


# Replay ----------------------------------------------------------------------------------


def fee_conflict(request: ClaimReviewRequest) -> list[dict[str, Any]]:
    """The scripted reviewer: reports keeps a 20% fee, bookings refunds in full."""
    said = " ".join(request.claim.assumptions)
    bookings = [c for c in request.other_claims if c.task_id == "T3"]
    if request.claim.task_id != "T4" or "20%" not in said or not bookings:
        return []
    return [
        {
            "id": "x",
            "kind": "requirement_conflict",
            "severity": "blocking",
            "source": "reviewer",
            "affected_ids": [bookings[0].id, request.claim.id],
            "explanation": f"{request.claim.id} assumes a 20% cancellation fee is added to "
            f"revenue, while {bookings[0].id} assumes cancelled bookings are refunded in full "
            "and earn nothing. These contradict each other on how a cancellation affects "
            "revenue.",
            "proposed_correction": "The lead must decide whether a cancelled booking keeps "
            "a fee or is refunded in full: it changes what the customer pays and what the "
            "business earns, and no requirement answers it.",
        }
    ]


class Reviewer:
    def review_claim(self, request: ClaimReviewRequest) -> Any:
        return fee_conflict(request)

    def review_commit(self, request: object) -> Any:
        return []


class Replay:
    def __init__(self, since: bool, short: bool) -> None:
        self.since, self.short = since, short
        store = MemoryStore()
        self.clock = FixedClock(datetime(2026, 10, 10, 18, 0, tzinfo=UTC))
        self.services = build_services(store, self.clock, Reviewer())
        self.people = ["lead", "t1", "t2", "t3", "t4", "t5"]
        admins = {(REPO, "lead")}
        repos = FakeRepoAccess(installations={REPO: 1}, admins=admins)
        projects = ProjectService(store, self.clock, repos, self.services.plans)
        self.users = {
            name: projects.sign_in(GitHubAccount(100 + i, name)).id
            for i, name in enumerate(self.people)
        }
        self.caller = "lead"
        self.server = build_hosted_server(
            self.services, projects, current_user_id=lambda: self.users[self.caller]
        )
        self.rows: list[dict[str, Any]] = []
        self.claim_ids: dict[str, str] = {}
        self.sent: dict[str, dict[str, Any]] = {}  # each agent's last claim, as sent
        self.markers: dict[str, str] = {}
        self.open_directive: dict[str, str | None] = {}
        self.accepts_since = (
            "since" in inspect.signature(self.services.check_ins.check_in).parameters
        )

    async def call(self, client: Client, who: str, tool: str, **args: Any) -> str:
        self.caller = who
        self.clock.advance(seconds=20)
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        return result.content[0].text  # type: ignore[union-attr]

    async def plan(self, client: Client, version: int, reason: str) -> None:
        cases = json.loads(PLANS.read_text(encoding="utf-8"))["cases"]
        plan = next(c["plan"] for c in cases if c["plan"]["version"] == version)
        tasks = [t | {"owner": t["id"].lower()} for t in plan["tasks"]]
        contracts = [{k: v for k, v in c.items() if k != "version"} for c in plan["contracts"]]
        proposed = await self.call(
            client, "lead", "propose_plan",
            requirements=plan["requirements"], tasks=tasks, contracts=contracts,
        )  # fmt: skip
        number = int(re.search(r"Proposed plan v(\d+)", proposed).group(1))  # type: ignore[union-attr]
        await self.call(client, "lead", "approve_plan", version=number, reason=reason)

    async def rule(self, client: Client) -> None:
        status = await self.call(client, "lead", "project_status")
        for escalation in re.findall(r"^- (E-\d+) ", status.split("Decisions in force")[0], re.M):
            await self.call(
                client, "lead", "resolve_escalation",
                escalation_id=escalation, resolution="request_revision", reason=RULING,
            )  # fmt: skip

    async def play(self, calls: list[dict[str, Any]]) -> None:
        async with Client(self.server) as client:
            created = await self.call(client, "lead", "create_project", repository=REPO)
            code = re.search(r"Join code: (MF-\S+)", created).group(1)  # type: ignore[union-attr]
            for name in self.people[1:]:
                await self.call(client, name, "join_project", join_code=code)
            await self.plan(client, 3, "the starting plan")
            phase = "p1"
            for call in calls:
                if call["phase"] != phase:
                    if call["phase"] == "p2":
                        await self.plan(client, 4, "half-hour bookings and rush orders")
                    elif phase == "p2":
                        await self.rule(client)
                    phase = call["phase"]
                await self.one(client, call)

    async def one(self, client: Client, call: dict[str, Any]) -> None:
        agent, tool = call["agent"], call["tool"]
        args = {k: v for k, v in call["input"].items() if k != "project_id"}
        if tool == "check_in":
            if self.since and self.accepts_since and agent in self.markers:
                args["since"] = self.markers[agent]
        elif tool == "submit_claim":
            # The trial's plan versions were 5 and 6; here they are 1 and 2.
            args["plan_version"] = max(1, args["plan_version"] - 4)
            if "claim_id" in args:
                args["claim_id"] = self.claim_ids[agent]
                if self.short and "status" not in args:
                    before = self.sent[agent]
                    args = {
                        k: v for k, v in args.items()
                        if k not in REVISED_PARTS or v != before.get(k)
                    }  # fmt: skip
            self.sent[agent] = self.sent.get(agent, {}) | args
        elif tool == "acknowledge_directive":
            if not self.open_directive.get(agent):
                return  # the trial's directive has no counterpart in this replay
            args["directive_id"] = self.open_directive[agent]
        reply = await self.call(client, agent, tool, **args)
        if "Midflight refused this" in reply:
            sys.exit(f"{agent} {tool} was refused:\n{reply}")
        if found := re.search(r"Claim (C-\d+) rev", reply):
            self.claim_ids[agent] = found.group(1)
        if found := re.search(r'pass since="([^"]+)"', reply):
            self.markers[agent] = found.group(1)
        directive = re.search(r"^(D-\d+) \((?:queued|delivered)", reply, re.M)
        self.open_directive[agent] = directive.group(1) if directive else None
        sent = json.dumps(args)
        self.rows.append(
            {
                "agent": agent,
                "phase": call["phase"],
                "tool": tool,
                "sent_chars": len(sent),
                "sent_tokens": tokens(sent),
                "reply_chars": len(reply),
                "reply_tokens": tokens(reply),
                "reply": reply,
            }
        )


def report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_tool: dict[str, Counter[str]] = {}
    for row in rows:
        count = by_tool.setdefault(row["tool"], Counter())
        count["calls"] += 1
        for key in ("sent_chars", "sent_tokens", "reply_chars", "reply_tokens"):
            count[key] += row[key]
    total: Counter[str] = Counter()
    for count in by_tool.values():
        total.update(count)
    print(
        f"{'tool':24}{'calls':>6}{'sent chars':>12}{'~tokens':>9}{'reply chars':>13}{'~tokens':>9}"
    )
    for tool, c in [*by_tool.items(), ("TOTAL", total)]:
        print(
            f"{tool:24}{c['calls']:>6}{c['sent_chars']:>12}{c['sent_tokens']:>9}"
            f"{c['reply_chars']:>13}{c['reply_tokens']:>9}"
        )
    return {"total": dict(total), "by_tool": {t: dict(c) for t, c in by_tool.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=["extract", "run"])
    parser.add_argument("logs", nargs="?", type=Path)
    parser.add_argument("--since", action="store_true", help="agents pass the check-in marker")
    parser.add_argument("--short", action="store_true", help="revisions send only what changed")
    parser.add_argument("--save", type=Path, help="write every reply and the totals here")
    args = parser.parse_args()
    if args.step == "extract":
        if args.logs is None:
            sys.exit("extract needs the trial's logs folder")
        calls = extract(args.logs)
        CALLS.write_text(json.dumps(calls, indent=1), encoding="utf-8")
        print(f"saved {len(calls)} calls to {CALLS}")
        return
    replay = Replay(args.since, args.short)
    asyncio.run(replay.play(json.loads(CALLS.read_text(encoding="utf-8"))))
    totals = report(replay.rows)
    if args.save:
        args.save.write_text(json.dumps({"rows": replay.rows} | totals, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
