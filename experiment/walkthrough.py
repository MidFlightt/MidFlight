"""One simulated run of the whole Midflight workflow, written to docs/pages/walkthrough.html.

    uv run python experiment/walkthrough.py

Five agents and a lead build HireBot Pro (experiment/cases/hirebot-pro). Each step shows
what an agent told Midflight and the exact text Midflight sent back. It runs the real
service code in memory, with the real AI reviewer on Amazon Bedrock, so it needs the same
settings as the service (MIDFLIGHT_REVIEWER_MODEL, MIDFLIGHT_REVIEWER_ROLE_ARN) and AWS
credentials. The plan and the claims are the ones from the experiment's Midflight run,
shortened. Nothing here is scripted on Midflight's side: the replies are whatever the
code and the model produced on this run.
"""

from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midflight.adapters.bedrock import BedrockReviewer
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services
from midflight.api.views import check_in_json, verdict_json
from midflight.config import Settings
from midflight.domain.models import (
    DirectiveResponse,
    EscalationState,
    Participant,
    Project,
    Resolution,
    Role,
)
from midflight.mcp.replies import check_in_text, directives_block, verdict_text
from midflight.ports import ClaimReviewRequest, Commit
from midflight.services.claims import ClaimSubmission
from midflight.services.plans import PlanDraft

REPO = Path(__file__).resolve().parents[1]
RECORDED = REPO / "evals" / "escalations" / "hirebot.json"
OUT = REPO / "docs" / "pages" / "walkthrough.html"
PROJECT = "hirebot"

TASKS = {"T1": "Catalog", "T2": "Pricing", "T3": "Bookings", "T4": "Reports", "T5": "Command line"}

LIST_BOOKINGS = (
    "T3's app/bookings.py exposes an in-process function list_bookings() returning every "
    "booking as a dict; reports.py imports it. Not in the plan contracts: T3 must confirm "
    "the name and shape."
)
PROVIDES_LIST = (
    "bookings.py exposes list_bookings(), returning every booking as a dict, for Reports "
    "(T4) to import."
)
FEE_DECISION = (
    "Cancelling a booking keeps a cancellation fee of 10% of the booking's total (rounded "
    "half up); the customer is refunded the rest. The fee counts as revenue in the report."
)
TOTAL_DECISION = (
    "A booking's total never changes: it stays the amount originally charged, also after "
    "cancelling. Bookings adds separate cancellation_fee and refund fields. Reports "
    "computes the fee as 10% of total."
)


# Recording -------------------------------------------------------------------------------


@dataclass
class Step:
    act: str
    who: str  # a task id, or "lead"
    title: str
    story: str
    sent: list[tuple[str, Any]] = field(default_factory=list)  # (label, text or list)
    reply: str = ""
    behind: list[str] = field(default_factory=list)  # what the reviewer did, if it ran
    outcome: str = ""


class WatchedReviewer:
    """The real reviewer, noting what its first pass flagged and what the second look kept."""

    def __init__(self, reviewer: BedrockReviewer) -> None:
        self._reviewer = reviewer
        self.notes: list[str] = []
        self.reviews = 0
        self.second_looks = 0
        self.dropped = 0
        confirm = reviewer._confirmed

        def watched(finding: dict[str, Any], request: ClaimReviewRequest) -> bool:
            kept = confirm(finding, request)
            self.second_looks += 1
            self.dropped += not kept
            said = str(finding.get("explanation", ""))
            self.notes.append(
                f"First pass flagged a conflict: “{said}” Second look: "
                + (
                    "a real contradiction. It blocks."
                    if kept
                    else "not a contradiction. Kept as a note."
                )
            )
            return kept

        reviewer._confirmed = watched  # type: ignore[method-assign]

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        self.reviews += 1
        others = (
            ", ".join(f"{c.id} ({c.task_id})" for c in request.other_claims) or "no other claims"
        )
        self.notes.append(f"The AI reviewer compared it with the plan and {others}.")
        return self._reviewer.review_claim(request)

    def review_commit(self, request: Any) -> Any:
        return self._reviewer.review_commit(request)


class Run:
    """The project, its people, and the steps recorded so far."""

    def __init__(self) -> None:
        settings = Settings.from_env()
        if not settings.reviewer_model:
            sys.exit("Set MIDFLIGHT_REVIEWER_MODEL (and MIDFLIGHT_REVIEWER_ROLE_ARN) first.")
        self.model = settings.reviewer_model
        self.reviewer = WatchedReviewer(
            BedrockReviewer(settings.reviewer_model, role_arn=settings.reviewer_role_arn)
        )
        self.clock = FixedClock(datetime(2026, 10, 10, 9, 0, tzinfo=UTC))
        self.store = MemoryStore()
        self.services: Services = build_services(self.store, self.clock, self.reviewer)
        self.lead = _person("lead", Role.LEAD)
        self.agents = {task: _person(task.lower(), Role.AGENT) for task in TASKS}
        people = [self.lead, *self.agents.values()]
        project = Project(
            id=PROJECT,
            name="HireBot Pro",
            repository="MidFlightt/hirebot-experiment",
            lead_id=self.lead.id,
            participant_ids=[p.id for p in people],
        )
        self.store.commit(
            Commit(project_id=PROJECT, idempotency_key="seed", puts=[project, *people])
        )
        self.recorded = _recorded_claims()
        self.claim_ids: dict[str, str] = {}
        self.steps: list[Step] = []
        self.act = ""
        self.lead_decisions = 0

    # The lead ----------------------------------------------------------------------------

    def approve_plan(self, recorded_version: int, title: str, story: str, reason: str) -> None:
        self.clock.advance(minutes=3)
        plan = self.recorded["plans"][recorded_version]
        tasks = [t | {"owner": self.agents[t["id"]].id} for t in plan["tasks"]]
        draft = PlanDraft.model_validate(
            {"requirements": plan["requirements"], "tasks": tasks, "contracts": plan["contracts"]}
        )
        proposed = self.services.plans.propose(self.lead, draft)
        approved = self.services.plans.approve(self.lead, proposed.version, reason)
        directives = [
            d for d in self.store.list_directives(PROJECT) if d.plan_version == approved.version
        ]
        sent: list[tuple[str, Any]] = [("Reason", reason)]
        if approved.version == 1:
            sent.append(
                (
                    "Tasks",
                    [
                        f"{t.id} {t.title}: provides {', '.join(t.provides) or 'nothing'}; "
                        f"uses {', '.join(t.consumes) or 'nothing'}"
                        for t in approved.tasks
                    ],
                )
            )
        else:
            sent.append(("What changed", ", ".join(approved.changed_ids)))
        reply = (
            f"Plan v{approved.version} is approved and current. Agents see it at their next "
            "check_in."
        )
        if directives:
            reply += "\n\nDirectives created:\n" + "\n".join(
                f"  {d.id} for {d.task_id} ({TASKS[d.task_id]})" for d in directives
            )
            untouched = [t for t in TASKS if t not in {d.task_id for d in directives}]
            reply += f"\nNo directive for: {', '.join(untouched) or 'nobody'}"
        self._add(
            Step(self.act, "lead", title, story, sent, reply, outcome=f"plan v{approved.version}")
        )

    def lead_looks(self, title: str, story: str) -> list[str]:
        """What the lead sees: the open escalations, as project_status lists them."""
        self.clock.advance(minutes=2)
        waiting = self._open_escalations()
        lines = [f"Open escalations: {len(waiting)}"]
        for e in waiting:
            lines.append(f"- {e.id} (claims {', '.join(e.claim_ids)}): {e.explanation}")
            lines += [f"    {ev.ref}: {ev.excerpt}" for ev in e.evidence if ev.excerpt]
        if waiting:
            lines.append("Decide each one with resolve_escalation. Midflight won't pick a side.")
        self._add(
            Step(
                self.act,
                "lead",
                title,
                story,
                [],
                "\n".join(lines),
                outcome=f"{len(waiting)} waiting" if waiting else "nothing waiting",
            )
        )
        return [e.id for e in waiting]

    def lead_decides(self, title: str, story: str, resolution: Resolution, reason: str) -> None:
        self.clock.advance(minutes=2)
        waiting = self._open_escalations()
        if not waiting:
            return
        replies = []
        for escalation in waiting:
            self.services.escalations.resolve(self.lead, escalation.id, resolution, reason)
            replies.append(
                f"Escalation {escalation.id} resolved ({resolution.value}). Claims "
                f"{', '.join(escalation.claim_ids)} were updated; their agents see it at "
                "their next check_in."
            )
        self.lead_decisions += 1
        self._add(
            Step(
                self.act,
                "lead",
                title,
                story,
                [("Decision", resolution.value), ("Reason the team sees", reason)],
                "\n".join(replies),
                outcome="decided",
            )
        )

    # The agents ---------------------------------------------------------------------------

    def check_in(self, task: str, title: str, story: str) -> None:
        self.clock.advance(minutes=1)
        reply = self.services.check_ins.check_in(self.agents[task], task)
        sent: list[tuple[str, Any]] = []
        answered = []
        for directive in reply.directives:
            if directive.state.value == "delivered":
                self.services.directives.acknowledge(
                    self.agents[task], directive.id, DirectiveResponse.ACKNOWLEDGED
                )
                answered.append(directive.id)
        text = check_in_text(check_in_json(reply))
        if answered:
            text += (
                f"\n\n(The agent then answered {', '.join(answered)} with "
                "acknowledge_directive: acknowledged.)"
            )
        # "Ready to push" only matters at the end; before that, show where the claim stands.
        outcome = reply.claim.state.value if reply.claim else "no claim yet"
        if self.act.startswith("7.") and reply.ready_to_push:
            outcome = "ready to push"
        self._add(Step(self.act, task, title, story, sent, text, outcome=outcome))

    def claim(
        self,
        task: str,
        title: str,
        story: str,
        like: tuple[str, int],
        assumptions: list[str],
        acceptance: list[str] | None = None,
        disagreement: bool = False,
    ) -> None:
        """Submit a claim shaped like recorded claim `like`, with these assumptions.

        `disagreement` marks the claims where the story has a real one. If Midflight
        stops any other claim for the lead, that is a false alarm: the lead dismisses it
        and the agent checks in again.
        """
        self.clock.advance(minutes=2)
        recorded = self.recorded["claims"][like]
        plan_version = self.store.get_project(PROJECT).current_plan_version
        submission = ClaimSubmission.model_validate(
            {
                "claim_id": self.claim_ids.get(task),
                "task_id": task,
                "branch": recorded["branch"],
                "base_sha": recorded["base_sha"],
                "plan_version": plan_version,
                "requirement_ids": recorded["requirement_ids"],
                "files": recorded["files"],
                "provides": recorded["provides"],
                "consumes": recorded["consumes"],
                "assumptions": assumptions,
                "acceptance_criteria": acceptance or recorded["acceptance_criteria"],
            }
        )
        self.reviewer.notes.clear()
        result = self.services.claims.submit(self.agents[task], submission)
        self.claim_ids[task] = result.claim_id
        verdict = verdict_json(self.services.claims.verdict(result.claim_id, result.revision))
        reply = f"{verdict_text(verdict)}\n\n{directives_block(verdict['directives'])}"
        sent = [
            ("Files", ", ".join(recorded["files"])),
            ("Provides", [_use(u) for u in recorded["provides"]] or "nothing"),
            ("Uses", [_use(u) for u in recorded["consumes"]] or "nothing"),
            ("Assumptions", assumptions),
            ("Done when", submission.acceptance_criteria),
        ]
        behind = list(self.reviewer.notes) or [
            "The rules already decided it; the AI reviewer wasn't asked."
        ]
        if len(behind) == 1 and verdict["state"] == "approved":
            behind.append("It flagged nothing.")
        self._add(Step(self.act, task, title, story, sent, reply, behind, verdict["state"]))
        if not disagreement and self._open_escalations():
            self.lead_decides(
                "The lead dismisses a false alarm",
                "Not scripted: on this run the reviewer stopped a claim over something that "
                "isn't a disagreement between people. The lead says so, and Midflight "
                "reviews the claim again without it.",
                Resolution.DISMISS,
                "Not a real conflict: both parts can be built as written.",
            )
            self.check_in(
                task,
                f"{TASKS[task]} checks in again",
                "The dismissed finding is kept as a note and no longer blocks.",
            )

    # Helpers ------------------------------------------------------------------------------

    def _open_escalations(self) -> list[Any]:
        return [e for e in self.store.list_escalations(PROJECT) if e.state is EscalationState.OPEN]

    def _add(self, step: Step) -> None:
        self.steps.append(step)
        print(f"{len(self.steps):>2}. [{step.who}] {step.title} -> {step.outcome}")


def _person(name: str, role: Role) -> Participant:
    return Participant(
        id=f"p-{name}", project_id=PROJECT, role=role, developer_name=name, user_id=f"u-{name}"
    )


def _use(use: dict[str, Any]) -> str:
    return f"{use['contract_id']}: " + ", ".join(f"{k} ({v})" for k, v in use["fields"].items())


def _recorded_claims() -> dict[str, Any]:
    """The plans and claims saved from the experiment's Midflight run."""
    cases = json.loads(RECORDED.read_text(encoding="utf-8"))["cases"]
    plans = {case["plan"]["version"]: case["plan"] for case in cases}
    claims = {}
    for case in cases:
        for claim in [case["claim"], *(o["claim"] for o in case["other_claims"])]:
            claims[(claim["id"], claim["revision"])] = claim
    return {"plans": plans, "claims": claims}


# What to notice, written after reading the run of October 10, 2026. Midflight's replies
# change from run to run, so rewrite these if you run it again. Each is (steps, note).
RUN_NOTES = [
    (
        "6, 7, 10",
        "An assumption no contract covers reaches the right agent. Reports assumed "
        "a function in the bookings code; Bookings saw that at its check-in, agreed in its own "
        "claim, and Reports saw the answer. Nobody else was involved.",
    ),
    (
        "7 to 9",
        "A false alarm, not scripted. The reviewer said Bookings and Pricing can't "
        "both compute prices. They can; it is duplicated work, not a disagreement. The second "
        "look kept it, so the lead had to dismiss it.",
    ),
    (
        "11 to 14",
        "The plan change produced four directives and none for the catalog, which "
        "the change doesn't touch.",
    ),
    (
        "16",
        "A second false alarm. Bookings was stopped because the plan “does not "
        "mention” refunds. A plan being silent is not a conflict. It happened to land on "
        "the agent that was about to be in a real one.",
    ),
    (
        "18 to 21",
        "The real disagreement: a full refund against a 20% fee. Reports' conflict "
        "joined the open question, so the lead read both sides once and answered once.",
    ),
    (
        "25 to 27",
        "A real catch before any code: Bookings would overwrite a booking's total "
        "with the fee, and Reports would take 10% of that total.",
    ),
    ("32, 33", "The command line was never stopped. In the experiment it was stopped three times."),
]
RUN_VERDICT = (
    "On this run Midflight stopped a claim four times. Two were the real questions and two "
    "were false alarms, so the reviewer is better than in the experiment but not fixed. "
    "The lead acted three times: one dismissal and two decisions."
)


# The story -------------------------------------------------------------------------------


def play(run: Run) -> None:
    run.act = "1. The lead writes the plan"
    run.approve_plan(
        3,
        "The lead approves plan v1",
        "The lead splits HireBot Pro into five tasks and writes down the contracts between "
        "them: which task provides which data, with field names and types. This is the "
        "lead's up-front work.",
        "First plan for HireBot Pro",
    )

    run.act = "2. Every agent claims before it codes"
    run.claim(
        "T1",
        "Catalog claims its task",
        "Each agent starts by telling Midflight what it will build and what it takes for "
        "granted. The catalog depends on nobody.",
        ("C-7", 1),
        [
            "GET /api/agents returns a JSON array of agent objects; GET /api/agents/{handle} "
            "returns one, and 404 if unknown.",
            "weekly_capacity is the static weekly total, not the hours remaining. Bookings "
            "tracks what is left.",
        ],
    )
    run.claim(
        "T2",
        "Pricing claims its task",
        "Pricing says it will keep its own copy of the rates. That is an assumption about "
        "the catalog's task, so it names T1.",
        ("C-8", 1),
        [
            "Catalog (T1) has no lookup I can import yet, so pricing keeps its own copy of "
            "the README rate table.",
            "POST /api/quote takes {items:[{agent,hours}], promo_code optional} and returns "
            "the five quote fields as integers.",
            "Tax is rounded half up.",
        ],
    )
    run.claim(
        "T3",
        "Bookings claims its task",
        "Bookings also computes prices itself. In the experiment, the old reviewer called "
        "this a conflict with pricing and stopped the agent for nothing.",
        ("C-10", 1),
        [
            "Pricing (T2) and catalog (T1) have no Python API I can import, so bookings.py "
            "computes the quote itself from the README rules, with its own copy of the rate "
            "table.",
            "POST /api/bookings takes the same request body as a quote.",
            "A booking's id is a string; its status is 'confirmed' or 'cancelled'.",
        ],
    )
    run.claim(
        "T4",
        "Reports claims its task",
        "Reports needs every booking, and no contract says how to get them. It assumes a "
        "function in the bookings code and says so. This exact assumption went nowhere in "
        "the experiment and broke the merged product.",
        ("C-12", 1),
        [
            "Revenue is the sum of booking.total over confirmed bookings only.",
            LIST_BOOKINGS,
            "Each booking.items element is {agent: <handle>, hours: <number>}.",
        ],
    )
    run.check_in(
        "T3",
        "Bookings checks in before writing code",
        "A check-in is the agent asking “what do I need to know right now?”. This time "
        "the answer includes what Reports assumes about bookings.",
    )
    run.claim(
        "T3",
        "Bookings answers by revising its claim",
        "Bookings agrees to provide the function and says so in its own claim, naming T4.",
        ("C-10", 1),
        [
            "bookings.py computes the quote itself from the README rules, with its own copy "
            "of the rate table.",
            PROVIDES_LIST,
            "A booking's id is a string; its status is 'confirmed' or 'cancelled'.",
        ],
    )
    run.check_in(
        "T4",
        "Reports checks in and sees the answer",
        "The loop closes without either developer or the lead doing anything.",
    )

    run.act = "3. The lead changes the plan"
    run.approve_plan(
        4,
        "The lead approves plan v2: half-hour bookings and rush orders",
        "Two changes for launch. Midflight works out which tasks the change touches and "
        "creates a directive for each of those, and only those.",
        "Two changes for launch: half-hour bookings, and rush orders with a 25% rush fee",
    )
    run.check_in(
        "T1",
        "Catalog checks in",
        "The change doesn't touch the catalog, so the catalog agent hears nothing and keeps "
        "working.",
    )
    run.check_in(
        "T2",
        "Pricing checks in",
        "Pricing gets a directive saying what changed for it. A directive is information to "
        "weigh, not a command. The agent acknowledges it.",
    )
    run.claim(
        "T2",
        "Pricing revises its claim for the new plan",
        "An approval on the old plan no longer counts for a task the change touches, so "
        "pricing claims again against plan v2.",
        ("C-8", 2),
        [
            "Hours must be a positive multiple of 0.5, else HTTP 400.",
            "rush_fee is 25% of (subtotal - volume discount - promo discount); tax is 8% of "
            "that amount plus the rush fee; everything rounded half up.",
            "Catalog (T1) has no lookup I can import, so pricing keeps its own copy of the "
            "README rate table.",
        ],
    )

    run.act = "4. Two developers disagree"
    run.check_in("T3", "Bookings checks in", "Bookings picks up its plan-change directive.")
    run.claim(
        "T3",
        "Bookings revises, with its developer's instruction",
        "The bookings developer has told their agent: when a booking is cancelled, refund "
        "the customer in full. The agent puts that in its claim.",
        ("C-10", 2),
        [
            "Hours are multiples of 0.5; availability is returned as a number.",
            "Developer instruction: cancelling refunds the customer in full. The booking "
            "gets a refund field equal to its total. Reports (T4) should leave cancelled "
            "bookings out of revenue.",
            PROVIDES_LIST,
        ],
        disagreement=True,
    )
    run.check_in("T4", "Reports checks in", "Reports picks up its directive too.")
    run.claim(
        "T4",
        "Reports revises, with a different instruction",
        "The reports developer has told their agent the opposite: a cancelled booking keeps "
        "a 20% fee, and the fee is revenue. Neither agent can settle this, and Midflight "
        "must not pick a side.",
        ("C-12", 2),
        [
            "Developer decision: a cancelled booking keeps a 20% cancellation fee, which "
            "counts as revenue. Revenue is confirmed totals plus 20% of each cancelled "
            "booking's total, rounded half up.",
            "booking.total is the full amount the customer was charged and is not changed "
            "by cancelling.",
            LIST_BOOKINGS,
        ],
        disagreement=True,
    )
    run.check_in(
        "T3",
        "Bookings checks in and learns it is part of the question",
        "Bookings' claim was fine when it was reviewed. Now it is one side of a "
        "disagreement, so its agent is told too.",
    )
    run.lead_looks(
        "The lead looks at the project",
        "The lead sees the question with both developers' sentences side by side.",
    )
    run.lead_decides(
        "The lead decides",
        "The answer is neither developer's: a 10% fee.",
        Resolution.REQUEST_REVISION,
        FEE_DECISION,
    )

    run.act = "5. The decision reaches both agents"
    run.check_in(
        "T3",
        "Bookings checks in",
        "The decision arrives as a directive, with the lead's words.",
    )
    run.claim(
        "T3",
        "Bookings revises to the lead's decision",
        "Bookings builds the 10% fee, and decides to overwrite the booking's total with the "
        "fee that was kept.",
        ("C-10", 2),
        [
            "Per the lead's decision: cancelling keeps a fee of 10% of the booking's "
            "original total, rounded half up, and refunds the rest.",
            "On cancel, the booking's total field is overwritten with the fee kept, so a "
            "cancelled booking's total is the fee.",
            PROVIDES_LIST,
        ],
        ["Cancel returns the hours, sets status cancelled, and sets total to the 10% fee kept"],
        disagreement=True,
    )
    run.check_in("T4", "Reports checks in", "Reports gets the same decision.")
    run.claim(
        "T4",
        "Reports revises to the lead's decision",
        "Reports takes 10% of each cancelled booking's total, assuming the total is still "
        "the amount charged. Built as claimed, the two parts would count a tenth of a "
        "tenth.",
        ("C-12", 2),
        [
            "Per the lead's decision: revenue is confirmed totals plus 10% of each cancelled "
            "booking's total, rounded half up.",
            "booking.total is the amount originally charged and is not changed by cancelling.",
            LIST_BOOKINGS,
        ],
        [
            "GET /api/report returns revenue (confirmed totals + 10% of cancelled totals), "
            "confirmed, cancelled, and hours per agent"
        ],
        disagreement=True,
    )
    run.lead_looks(
        "The lead looks again",
        "If Midflight caught the mismatch, it is waiting here.",
    )
    run.lead_decides(
        "The lead settles what total means",
        "One sentence from the lead fixes the interface for both.",
        Resolution.REQUEST_REVISION,
        TOTAL_DECISION,
    )
    run.check_in("T3", "Bookings checks in", "Bookings reads the ruling.")
    run.claim(
        "T3",
        "Bookings revises",
        "Bookings keeps total as it was and adds two fields.",
        ("C-10", 2),
        [
            "A booking's total never changes, also after cancelling.",
            "On cancel the booking gets cancellation_fee (10% of total, rounded half up) and "
            "refund (total minus the fee); both are 0 while confirmed.",
            PROVIDES_LIST,
        ],
        [
            "Cancel returns the hours, sets status cancelled, leaves total unchanged, and sets "
            "cancellation_fee and refund"
        ],
    )
    run.check_in("T4", "Reports checks in", "Reports reads the ruling.")
    run.claim(
        "T4",
        "Reports revises",
        "Reports' plan already matched the ruling; it says so.",
        ("C-12", 2),
        [
            "booking.total never changes after cancelling. Revenue is confirmed totals plus "
            "10% of each cancelled booking's total, rounded half up; I compute the fee from "
            "total myself.",
            LIST_BOOKINGS,
        ],
        [
            "GET /api/report returns revenue (confirmed totals + 10% of cancelled totals), "
            "confirmed, cancelled, and hours per agent"
        ],
    )

    run.act = "6. Everyone else carried on"
    run.check_in(
        "T5",
        "The command line checks in",
        "The command line uses every API. In the experiment it was stopped three times by "
        "questions that changed nothing it wrote. Here it was never part of one.",
    )
    run.claim(
        "T5",
        "The command line claims against plan v2",
        "It prints whatever the APIs return, and says so.",
        ("C-9", 2),
        [
            "POST /api/quote and POST /api/bookings take {items:[{agent,hours}], promo_code "
            "optional, rush optional}.",
            "The command line does no price or fee math: it prints each total exactly as "
            "the API returns it.",
            "Errors are non-2xx with a JSON 'detail'; the command line prints error: <detail>.",
        ],
    )

    run.act = "7. Before pushing"
    for task, name in TASKS.items():
        run.check_in(
            task,
            f"{name} checks in before pushing",
            "The last check-in. “Ready to push: yes” is what the pre-push hook asks "
            "for; after the push, midflight/verify checks the real code on GitHub."
            if task == "T1"
            else "",
        )


# The page --------------------------------------------------------------------------------

CSS = """
:root { --bg:#f7f7f5; --card:#fff; --ink:#1c1c1a; --dim:#6b6b66; --line:#e2e1dc;
  --ok:#1f7a45; --ok-bg:#e3f4ea; --warn:#9a5b00; --warn-bg:#fdf0d8; --bad:#b42318;
  --bad-bg:#fde7e4; --wait:#1f5fa8; --wait-bg:#e3eefb; --lead:#6b3fa0; --lead-bg:#efe6fa;
  --code:#f0efea; }
@media (prefers-color-scheme: dark) { :root { --bg:#141413; --card:#1e1e1c; --ink:#ecebe6;
  --dim:#a09f98; --line:#33332f; --ok:#6fd39a; --ok-bg:#16301f; --warn:#f0b65a;
  --warn-bg:#33270f; --bad:#ff8a7a; --bad-bg:#3a1a16; --wait:#8fbcf5; --wait-bg:#172a42;
  --lead:#c5a3f0; --lead-bg:#2a1f3a; --code:#2a2a27; } }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif }
.wrap { max-width:1120px; margin:0 auto; padding:28px 16px 80px }
h1 { font-size:1.75rem; margin:0 0 6px; text-wrap:balance }
h2 { font-size:1.25rem; margin:44px 0 4px; padding-top:14px; border-top:1px solid var(--line) }
h3 { font-size:1.02rem; margin:0 }
p { margin:6px 0; max-width:75ch } .dim { color:var(--dim) }
code { font:13px ui-monospace,Consolas,monospace; background:var(--code); padding:1px 5px;
  border-radius:4px }
.note { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--wait);
  border-radius:8px; padding:10px 14px; margin:14px 0; max-width:90ch }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px;
  margin:18px 0 }
.stat { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:10px 12px }
.stat b { display:block; font-size:1.5rem; font-variant-numeric:tabular-nums }
.stat span { color:var(--dim); font-size:.86rem }
table { border-collapse:collapse; width:100%; background:var(--card); border:1px solid var(--line);
  border-radius:8px; font-size:.9rem }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line);
  vertical-align:top }
th { color:var(--dim); font-weight:600 } tr:last-child td { border-bottom:0 }
.scroll { overflow-x:auto }
.step { background:var(--card); border:1px solid var(--line); border-radius:12px; margin:14px 0;
  overflow:hidden }
.step.lead { border-left:4px solid var(--lead) }
.step > header { display:flex; gap:12px; align-items:flex-start; padding:12px 16px }
.step > header > div { flex:1; min-width:0 }
.num { background:var(--code); border-radius:50%; min-width:30px; height:30px; display:grid;
  place-items:center; font-weight:600; font-variant-numeric:tabular-nums }
.who { font-size:.76rem; font-weight:700; letter-spacing:.03em; text-transform:uppercase;
  color:var(--dim) }
.step.lead .who { color:var(--lead) }
.story { color:var(--dim); margin:3px 0 0 }
.badge { font-size:.78rem; font-weight:600; padding:2px 9px; border-radius:999px;
  white-space:nowrap }
.badge.ok { color:var(--ok); background:var(--ok-bg) }
.badge.warn { color:var(--warn); background:var(--warn-bg) }
.badge.lead { color:var(--lead); background:var(--lead-bg) }
.badge.muted { color:var(--dim); background:var(--code) }
.cols { display:grid; grid-template-columns:minmax(0,5fr) minmax(0,7fr);
  border-top:1px solid var(--line) }
.cols > div { padding:12px 16px; min-width:0 }
.cols > div + div { border-left:1px solid var(--line) }
.cols.one { grid-template-columns:1fr }
@media (max-width:760px) { .cols { grid-template-columns:1fr }
  .cols > div + div { border-left:0; border-top:1px solid var(--line) } }
h4 { margin:0 0 8px; font-size:.78rem; letter-spacing:.04em; text-transform:uppercase;
  color:var(--dim) }
dl { margin:0; display:grid; grid-template-columns:96px minmax(0,1fr); gap:6px 10px;
  font-size:.9rem }
dt { color:var(--dim) } dd { margin:0 } dd ul { margin:0; padding-left:18px }
dd li { margin:2px 0 }
pre { margin:0; font:12.5px/1.5 ui-monospace,Consolas,monospace; background:var(--code);
  border-radius:8px; padding:10px 12px; white-space:pre-wrap; overflow-wrap:anywhere }
details { margin:2px 0 } summary { cursor:pointer; color:var(--wait) }
pre .hl { display:block; margin:0 -12px; padding:0 12px; border-left:3px solid transparent }
pre .hl.ok { background:var(--ok-bg); border-color:var(--ok) }
pre .hl.warn { background:var(--warn-bg); border-color:var(--warn) }
pre .hl.wait { background:var(--wait-bg); border-color:var(--wait) }
.behind { margin:10px 0 0; padding:0; list-style:none; font-size:.86rem; color:var(--dim) }
.behind li { padding:4px 0 4px 12px; border-left:2px solid var(--line); margin:4px 0 }
nav { display:flex; flex-wrap:wrap; gap:6px; margin:14px 0 }
nav a { text-decoration:none; color:var(--ink); background:var(--card);
  border:1px solid var(--line);
  border-radius:6px; padding:4px 9px; font-size:.85rem }
"""

# Lines of a reply worth a second glance, and how to tint them.
HIGHLIGHTS = [
    ("OTHER TASKS ASSUME THIS ABOUT YOURS", "wait"),
    ("WAITING FOR THE LEAD", "warn"),
    ("ESCALATIONS WAITING", "warn"),
    ("Only the part of your work", "warn"),
    ("HUMAN_REVIEW_REQUIRED", "warn"),
    ("NEEDS_REVISION", "warn"),
    ("[BLOCKING]", "warn"),
    ("MIDFLIGHT DIRECTIVES (data", "wait"),
    ("Ready to push: yes", "ok"),
    ("Ready to push: no", "warn"),
    (": APPROVED", "ok"),
    ("Directives created", "wait"),
    ("No directive for", "ok"),
    ("Open escalations: ", "warn"),
]


def reply_html(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        tint = next((t for needle, t in HIGHLIGHTS if needle in line), None)
        if tint and line.startswith("Open escalations: 0"):
            tint = "ok"
        safe = html.escape(line)
        lines.append(f'<span class="hl {tint}">{safe}</span>' if tint else safe + "\n")
    return fold_contracts("".join(lines).rstrip("\n"))


def fold_contracts(reply: str) -> str:
    """Tuck the contract field lists away: they repeat in every reply and bury the rest."""

    def folded(match: re.Match[str]) -> str:
        count = len(re.findall(r"^  \S", match.group(1), flags=re.MULTILINE))
        summary = f"Build against: {count} contracts (click to show the fields)"
        return f"<details><summary>{summary}</summary>{match.group(1)}</details>"

    return re.sub(r"Build against:\n((?:  .*\n)+)", folded, reply)


def sent_html(sent: list[tuple[str, Any]]) -> str:
    rows = []
    for label, value in sent:
        if isinstance(value, list):
            body = "<ul>" + "".join(f"<li>{html.escape(str(v))}</li>" for v in value) + "</ul>"
        else:
            body = html.escape(str(value))
        rows.append(f"<dt>{html.escape(label)}</dt><dd>{body}</dd>")
    return f"<dl>{''.join(rows)}</dl>"


def badge(outcome: str) -> str:
    kind = "muted"
    if outcome in ("approved", "ready to push", "nothing waiting") or outcome.startswith("plan v"):
        kind = "ok"
    elif outcome in ("human_review_required", "needs_revision") or outcome.endswith("waiting"):
        kind = "warn"
    elif outcome == "decided":
        kind = "lead"
    return f'<span class="badge {kind}">{html.escape(outcome.replace("_", " "))}</span>'


def step_html(number: int, step: Step) -> str:
    lead = step.who == "lead"
    who = "The lead" if lead else f"{step.who} · {TASKS[step.who]} agent"
    verb = "The lead told Midflight" if lead else "The agent told Midflight"
    tool = "submit_claim" if any(label == "Assumptions" for label, _ in step.sent) else "check_in"
    left = f"<div><h4>{verb}</h4>{sent_html(step.sent)}</div>" if step.sent else ""
    asked = (
        ""
        if step.sent or lead
        else f'<p class="dim" style="margin:0 0 8px">The agent called <code>{tool}</code>.</p>'
    )
    behind = (
        "<ul class='behind'>" + "".join(f"<li>{html.escape(b)}</li>" for b in step.behind) + "</ul>"
        if step.behind
        else ""
    )
    heading = "The lead saw" if lead and not step.sent else "Midflight replied"
    right = f"<div><h4>{heading}</h4>{asked}<pre>{reply_html(step.reply)}</pre>{behind}</div>"
    story = f'<p class="story">{html.escape(step.story)}</p>' if step.story else ""
    return (
        f'<article class="step{" lead" if lead else ""}" id="s{number}"><header>'
        f'<span class="num">{number}</span><div><span class="who">{who}</span>'
        f"<h3>{html.escape(step.title)}</h3>{story}</div>{badge(step.outcome)}</header>"
        f'<div class="cols{"" if left else " one"}">{left}{right}</div></article>'
    )


def page(run: Run) -> str:
    plan = run.store.get_plan(PROJECT, 2)
    assert plan is not None
    escalations = run.store.list_escalations(PROJECT)
    real = sum(e.resolution is Resolution.REQUEST_REVISION for e in escalations)
    claims = sum(any(label == "Assumptions" for label, _ in s.sent) for s in run.steps)
    all_ready = all(run.services.check_ins.check_in(run.agents[t], t).ready_to_push for t in TASKS)
    acts: list[str] = []
    body = []
    for number, step in enumerate(run.steps, start=1):
        if step.act not in acts:
            acts.append(step.act)
            body.append(f'<h2 id="a{len(acts)}">{html.escape(step.act)}</h2>')
        body.append(step_html(number, step))
    nav = "".join(f'<a href="#a{i}">{html.escape(a)}</a>' for i, a in enumerate(acts, start=1))
    tasks = "".join(
        f"<tr><td>{t.id}</td><td>{html.escape(t.title)}</td>"
        f"<td>{html.escape(', '.join(t.provides) or 'nothing')}</td>"
        f"<td>{html.escape(', '.join(t.consumes) or 'nothing')}</td></tr>"
        for t in plan.tasks
    )
    stats = [
        (claims, "claims and revisions"),
        (run.reviewer.reviews, "AI reviews"),
        (run.reviewer.second_looks, "conflicts given a second look"),
        (run.reviewer.dropped, "of those the second look dropped"),
        (len(escalations), "questions that reached the lead"),
        (real, "of those the lead had to decide"),
        (len(escalations) - real, "of those the lead dismissed"),
    ]
    notes = "".join(
        f"<tr><td style='white-space:nowrap'>{html.escape(steps)}</td>"
        f"<td>{html.escape(note)}</td></tr>"
        for steps, note in RUN_NOTES
    )
    stats_html = "".join(
        f'<div class="stat"><b>{n}</b><span>{label}</span></div>' for n, label in stats
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Midflight walkthrough</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>One run of the Midflight workflow, step by step</h1>
<p>Five AI agents and a lead build HireBot Pro, a marketplace for hiring AI agents by the
hour. Each card shows what one of them told Midflight and the exact text Midflight sent
back. Read it top to bottom: claim, check, change the plan, disagree, decide, push.</p>
<div class="note"><b>What this is.</b> A simulation, run once on October 10, 2026 with
<code>experiment/walkthrough.py</code>. It uses Midflight's real service code in memory
and the real AI reviewer (<code>{html.escape(run.model)}</code> on Amazon Bedrock). The
plan and the claims come from the agents in our experiment, shortened. The agents here
follow a script; Midflight's replies do not: they are whatever the code and the model
produced on this run. It is not the deployed service and no code was built.</div>
<div class="stats">{stats_html}</div>
<p class="dim">At the end, every task was ready to push: <b>{"yes" if all_ready else "no"}</b>.</p>
<h2 style="border:0;margin-top:26px">What to notice in this run</h2>
<p>{html.escape(RUN_VERDICT)}</p>
<div class="scroll"><table><tr><th>Steps</th><th>What happened</th></tr>{notes}</table></div>
<h2 style="border:0;margin-top:26px">The plan the lead wrote</h2>
<p>Each contract is a named piece of data with fields and types. One task provides it and
others use it. Requirements and field lists appear in the replies below.</p>
<div class="scroll"><table>
<tr><th>Task</th><th>Part</th><th>Provides</th><th>Uses</th></tr>{tasks}</table></div>
<nav>{nav}</nav>
{"".join(body)}
</div></body></html>
"""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run = Run()
    play(run)
    OUT.write_text(page(run), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
