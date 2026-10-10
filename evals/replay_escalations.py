"""Replay recorded escalations through the AI reviewer and count what it does.

Every escalation Midflight opened during the HireBot experiment is one labelled case:
the claim under review, the plan, the other claims as they stood at that moment, and
whether the conflict was real (the lead decided it) or a false alarm (the lead dismissed
it, or the stated conflict isn't in the data). A good reviewer stops the real ones, sends
each to the right decider (the lead for a product question, itself for a technical
one), and lets the false ones through.

    python evals/replay_escalations.py export   # rebuild the cases from the live table
    python evals/replay_escalations.py run      # replay them with the current reviewer

`run` calls Amazon Bedrock, so it needs AWS credentials and the same settings as the
service (MIDFLIGHT_REVIEWER_MODEL, MIDFLIGHT_REVIEWER_ROLE_ARN). The model doesn't answer
the same way every time, so `--repeat N` reviews each case N times and counts.
`--no-second-look` shows the first pass alone. Results are written up in
evals/results.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from midflight.adapters.bedrock import BedrockReviewer
from midflight.domain.models import Claim, ClaimState, Plan, Resolution
from midflight.ports import ClaimReviewRequest, ReviewerUnavailable
from midflight.services.claims import _known_ids, _only_between_people
from midflight.services.review import parse_reviewer_findings

CASES = Path(__file__).parent / "escalations" / "hirebot.json"

# What each recorded escalation really was. `real` means two statements in the data
# could not both hold; everything else stopped agents for nothing.
LABELS = {
    "E-1": ("false", "compared with a withdrawn claim; both said the same thing"),
    "E-2": ("false", "a price preview and the server's tax math agree"),
    "E-3": ("real", "developer note 'rates include tax' against requirement R-2"),
    "E-4": ("real", "the same tax question, seen from the storefront's claim"),
    "E-5": ("false", "two parts each keep a copy of the rate table"),
    "E-6": ("false", "'the requirement doesn't say how' is not a conflict"),
    "E-7": ("false", "said the plan requires the total to change; it doesn't"),
    "E-8": ("real", "20% cancellation fee against a full refund"),
    "E-9": ("false", "compared with a claim its agent had been told to revise"),
    "E-10": ("real", "total overwritten on cancel against total never changes"),
    "E-11": ("false", "printing a total and computing a fee don't contradict"),
    "E-12": ("false", "both claims said the same thing"),
    "E-13": ("false", "'gives the hours back' does not change a total"),
}

# Who should settle each real one (D31, D32). The tax cases are answered by the plan
# (requirement R-2 says 8% tax), so the plan wins and no person is needed.
DECIDER = {"E-3": "reviewer", "E-4": "reviewer", "E-8": "lead", "E-10": "reviewer"}


# Export ----------------------------------------------------------------------------------


def export(table: str, project: str) -> None:
    """Rebuild each case from the stored claims, plans, escalations, and audit log."""
    from midflight.adapters.dynamo_store import DynamoStore

    store = DynamoStore(table)
    escalations = sorted(store.list_escalations(project), key=lambda e: int(e.id[2:]))
    revisions = {
        c.id: [r for n in range(1, c.revision + 1) if (r := store.get_claim(c.id, n))]
        for c in store.list_claims(project)
    }
    withdrawn_at = {
        claim_id: event.timestamp
        for event in store.list_audit(project)
        if event.action == "claim.withdrawn"
        for claim_id in event.entity_ids
    }
    cases = []
    for escalation in escalations:
        claim_id, _, revision = escalation.finding_ids[0].split(":")[0].partition("/")
        reviewed = revisions[claim_id][int(revision) - 1]
        moment = reviewed.created_at
        plan = store.get_plan(project, reviewed.plan_version)
        assert plan is not None
        others = []
        for other_id, history in revisions.items():
            before = [r for r in history if r.created_at <= moment]
            gone = other_id in withdrawn_at and withdrawn_at[other_id] <= moment
            if other_id == claim_id or not before or gone:
                continue
            latest = before[-1]
            # The lead had asked for this claim to be revised, and it hadn't been yet.
            awaiting = any(
                e.resolution is Resolution.REQUEST_REVISION
                and other_id in e.claim_ids
                and e.resolved_at is not None
                and latest.created_at <= e.resolved_at <= moment
                for e in escalations
            )
            others.append({"claim": _as_submitted(latest), "awaiting_revision": awaiting})
        label, why = LABELS[escalation.id]
        cases.append(
            {
                "id": escalation.id,
                "label": label,
                "why": why,
                "reviewer_said": escalation.explanation,
                "lead_answered": f"{escalation.resolution}: {escalation.reason}",
                "plan": plan.model_dump(mode="json"),
                "claim": _as_submitted(reviewed),
                "other_claims": others,
            }
        )
    CASES.parent.mkdir(exist_ok=True)
    CASES.write_text(json.dumps({"project": project, "cases": cases}, indent=1), encoding="utf-8")
    print(f"wrote {len(cases)} cases to {CASES}")


def _as_submitted(claim: Claim) -> dict[str, Any]:
    """The claim as its agent sent it: no verdict, and not yet reviewed."""
    return claim.model_dump(mode="json", exclude={"findings"}) | {"state": "pending"}


# Replay ----------------------------------------------------------------------------------


def run(second_look: bool, skip_awaiting: bool, repeat: int) -> None:
    from midflight.config import Settings

    settings = Settings.from_env()
    if not settings.reviewer_model:
        sys.exit("Set MIDFLIGHT_REVIEWER_MODEL (and MIDFLIGHT_REVIEWER_ROLE_ARN) first.")
    reviewer = BedrockReviewer(settings.reviewer_model, role_arn=settings.reviewer_role_arn)
    if not second_look:
        reviewer._second_look = lambda reply, _request: reply  # type: ignore[method-assign]

    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    print(f"model {settings.reviewer_model}; second look {'on' if second_look else 'off'}; ")
    print(f"claims awaiting revision {'skipped' if skip_awaiting else 'compared'}; ", end="")
    print(f"{repeat} review(s) per case\n")
    tally = {"caught": 0, "right decider": 0, "real": 0, "to lead": 0, "revised": 0, "false": 0}
    started = time.monotonic()
    for case in cases:
        plan = Plan.model_validate(case["plan"])
        claim = Claim.model_validate(case["claim"])
        others = [
            Claim.model_validate(o["claim"] | {"state": ClaimState.APPROVED})
            for o in case["other_claims"]
            if not (skip_awaiting and o["awaiting_revision"])
        ]
        request = ClaimReviewRequest(plan=plan, claim=claim, other_claims=others, rule_findings=[])
        outcomes = [_outcome(reviewer, request) for _ in range(repeat)]
        lead, own = outcomes.count("lead"), outcomes.count("reviewer")
        if case["label"] == "real":
            wanted = DECIDER[case["id"]]
            tally["real"] += repeat
            tally["caught"] += lead + own
            tally["right decider"] += outcomes.count(wanted)
            note = f"should go to: {wanted}"
        else:
            tally["false"] += repeat
            tally["to lead"] += lead
            tally["revised"] += own
            note = "should pass"
        print(
            f"{case['id']:>5}  {case['label']:<5}  lead {lead}  reviewer {own}  "
            f"passes {repeat - lead - own}   ({note})"
        )
    print(
        f"\nreal questions: stopped {tally['caught']} of {tally['real']} reviews, "
        f"{tally['right decider']} sent to the right decider"
        f"\nfalse alarms: {tally['to lead']} of {tally['false']} reviews went to the lead, "
        f"{tally['revised']} asked the agent to revise for nothing"
        f"\n{(time.monotonic() - started) / (repeat * len(cases)):.1f}s per review"
    )


def _outcome(reviewer: BedrockReviewer, request: ClaimReviewRequest) -> str:
    """Who ends up settling it: the `lead`, the `reviewer`, or nobody (it `passes`)."""
    plan, claim, others = request.plan, request.claim, request.other_claims
    try:
        reply = reviewer.review_claim(request)
    except ReviewerUnavailable:
        reply = reviewer.review_claim(request)  # the service asks twice too
    findings = parse_reviewer_findings(reply, _known_ids(plan, claim, others), claim)
    # The same last step the service applies before a finding can stop anyone.
    kinds = {
        f.kind.value
        for f in (_only_between_people(f, plan, claim, others) for f in findings or [])
        if f.blocking
    }
    if "requirement_conflict" in kinds:
        return "lead"
    return "reviewer" if "semantic_mismatch" in kinds else "passes"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=["export", "run"])
    parser.add_argument("--table", default="midflight-Table-17NA6ODOVW8ZP")
    parser.add_argument("--project", default="midflight-9854")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--no-second-look", action="store_true")
    parser.add_argument("--compare-awaiting", action="store_true")
    args = parser.parse_args()
    if args.step == "export":
        export(args.table, args.project)
    else:
        run(not args.no_second_look, not args.compare_awaiting, args.repeat)


if __name__ == "__main__":
    main()
