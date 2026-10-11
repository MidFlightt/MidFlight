"""PigeonPost's plan: the requirements, tasks, and contracts every approach starts from.

One source for three things, so no approach is told more than another:

- starter/PLAN.md, which every agent in every approach reads (`python plan.py` writes it);
- the plan the lead proposes in Midflight (run B): `plan(1, owner)`;
- the lead's launch change: `change_message()` for runs N and A, `plan(2, owner)` for B.
"""

from __future__ import annotations

import copy
from pathlib import Path

REQUIREMENTS = {
    "R-1": (
        "The roost knows the birds (handle, name, max payload in kg, speed in km/h, flights "
        "per day) and the destinations (code, name, distance from the roost in km). "
        "GET /birds lists the birds and GET /birds/{handle} returns one; GET /destinations "
        "lists the destinations and GET /destinations/{code} returns one. An unknown handle "
        "or code is a 404."
    ),
    "R-2": (
        "POST /quote prices a parcel. Delivery fee = 4.00 + 0.50 per km to the destination "
        "+ 2.00 per kg. Promo code COOCOO takes 15% off the delivery fee; any other code is "
        "an error (400). Birdseed Tax is 8% of (delivery fee - promo discount). Total = "
        "delivery fee - promo discount + tax. Money is in credits with two decimals; round "
        "half up to the cent wherever a fraction of a cent appears."
    ),
    "R-3": (
        "POST /deliveries sends a parcel: it prices it by R-2, gives it to the bird with the "
        "smallest max payload that can carry the weight and still has a flight left today, "
        "and uses one of that bird's flights. A parcel heavier than every bird's max payload "
        "is refused, and so is a parcel when no bird that can carry it has a flight left "
        "(400). A weight is a multiple of 0.5 kg, from 0.5."
    ),
    "R-4": (
        "GET /deliveries/{id} returns a delivery. POST /deliveries/{id}/cancel cancels it, "
        "gives the bird its flight back, and returns the delivery with what the customer "
        "gets back as refund (0 until a delivery is cancelled). GET "
        "/birds/{handle}/availability tells how many flights the bird has left today. An "
        "unknown delivery or bird is a 404."
    ),
    "R-5": (
        "GET /report is the revenue report: what PigeonPost earned, how many deliveries are "
        "confirmed and cancelled, and the flights per bird (confirmed deliveries only)."
    ),
    "R-6": (
        "GET /deliveries/{id}/tracking tells where a delivery is: its status, its bird, and "
        "the ETA in whole minutes (distance to the destination / the bird's speed x 60, "
        "rounded half up). A cancelled delivery has ETA 0. An unknown delivery is a 404."
    ),
    "R-7": (
        "The command line (cli/pigeon.py) offers every command in README.md's 'The command "
        "line' section over HTTP and prints exactly the keys listed there. `send` first asks "
        "for the quote (POST /quote) and prints it, then sends the parcel (POST /deliveries) "
        "and prints the delivery."
    ),
}

# id: (title, file, branch, requirements, provides, consumes)
TASKS = {
    "T1": ("Roost", "app/roost.py", "t1-roost", ["R-1"], ["bird", "destination"], []),
    "T2": ("Pricing", "app/pricing.py", "t2-pricing", ["R-2"],
           ["quote-request", "quote"], ["destination"]),
    "T3": ("Dispatch", "app/dispatch.py", "t3-dispatch", ["R-3", "R-4"],
           ["delivery-request", "delivery", "availability"],
           ["bird", "destination", "quote-request", "quote"]),
    "T4": ("Billing", "app/billing.py", "t4-billing", ["R-5"], ["report"], ["delivery"]),
    "T5": ("Command line", "cli/pigeon.py", "t5-cli", ["R-7"], [],
           ["bird", "destination", "quote-request", "quote", "delivery-request", "delivery",
            "availability", "report", "tracking"]),
    "T6": ("Tracking", "app/tracking.py", "t6-tracking", ["R-6"], ["tracking"],
           ["bird", "destination", "delivery"]),
}  # fmt: skip

# id: (provider, consumers, fields)
CONTRACTS = {
    "bird": ("T1", ["T3", "T5", "T6"], {
        "handle": "string", "name": "string", "max_payload": "number", "speed": "number",
        "flights_per_day": "integer"}),
    "destination": ("T1", ["T2", "T3", "T5", "T6"], {
        "code": "string", "name": "string", "distance_km": "number"}),
    "quote-request": ("T2", ["T3", "T5"], {
        "destination": "string", "weight_kg": "number", "promo": "string"}),
    "quote": ("T2", ["T3", "T5"], {
        "delivery_fee": "number", "promo_discount": "number", "tax": "number",
        "total": "number"}),
    "delivery-request": ("T3", ["T5"], {
        "destination": "string", "weight_kg": "number", "promo": "string"}),
    "delivery": ("T3", ["T4", "T5", "T6"], {
        "id": "integer", "destination": "string", "weight_kg": "number", "bird": "string",
        "status": "string", "total": "number", "refund": "number"}),
    "availability": ("T3", ["T5"], {"bird": "string", "flights_left": "integer"}),
    "report": ("T4", ["T5"], {
        "revenue": "number", "confirmed": "integer", "cancelled": "integer",
        "flights": "object"}),
    "tracking": ("T6", ["T5"], {
        "delivery": "integer", "status": "string", "bird": "string",
        "eta_minutes": "integer"}),
}  # fmt: skip

# The lead's launch change (plan version 2): express delivery. --------------------------

EXPRESS = (
    "Express delivery. A quote or a delivery can be express. An express parcel pays an "
    "express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is "
    "then 8% of (delivery fee - promo discount + express fee), and the total includes the "
    "express fee. On the command line, quote and send take --express and print a new "
    "line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express)."
)
EXPRESS_TASKS = ["T2", "T3", "T5"]
EXPRESS_FIELDS = {
    "quote-request": {"express": "boolean"},
    "delivery-request": {"express": "boolean"},
    "quote": {"express_fee": "number"},
}
CHANGE_REASON = "Launch change: express delivery"


def tables(version: int) -> tuple[dict, dict, dict]:
    """Requirements, tasks, and contracts as of a plan version."""
    requirements = dict(REQUIREMENTS)
    tasks = copy.deepcopy(TASKS)
    contracts = copy.deepcopy(CONTRACTS)
    if version >= 2:
        requirements["R-8"] = EXPRESS
        for task in EXPRESS_TASKS:
            tasks[task][3].append("R-8")
        for contract, fields in EXPRESS_FIELDS.items():
            contracts[contract][2].update(fields)
    return requirements, tasks, contracts


def plan(version: int, owner: str) -> dict:
    """The plan as Midflight's propose_plan takes it. `owner` owns every task: in a trial
    all six agents are signed in as the person running it."""
    requirements, tasks, contracts = tables(version)
    return {
        "requirements": [{"id": i, "description": text} for i, text in requirements.items()],
        "tasks": [
            {"id": i, "title": f"{title} ({file})", "owner": owner, "branch": branch,
             "requirement_ids": reqs, "provides": provides, "consumes": consumes}
            for i, (title, file, branch, reqs, provides, consumes) in tasks.items()
        ],
        "contracts": [
            {"id": i, "provider_task": provider, "consumer_tasks": consumers, "fields": fields}
            for i, (provider, consumers, fields) in contracts.items()
        ],
    }  # fmt: skip


def render(version: int = 1) -> str:
    """The plan as the Markdown page every agent reads (starter/PLAN.md)."""
    requirements, tasks, contracts = tables(version)
    lines = [
        f"# PigeonPost: the plan (version {version})",
        "",
        "The lead wrote this plan before anyone started. README.md describes the product;",
        "this page says who builds what and what the parts hand each other.",
        "",
        "## Requirements",
        "",
        "| Id | Requirement |",
        "| --- | --- |",
        *(f"| {i} | {text} |" for i, text in requirements.items()),
        "",
        "## Tasks",
        "",
        "One developer, with their AI agent, per task. Each task edits only its file.",
        "",
        "| Task | Part | File | Requirements | Provides | Consumes |",
        "| --- | --- | --- | --- | --- | --- |",
        *(
            f"| {i} | {title} | `{file}` | {', '.join(reqs)} | "
            f"{names(provides)} | {names(consumes)} |"
            for i, (title, file, _, reqs, provides, consumes) in tasks.items()
        ),
        "",
        "## Contracts",
        "",
        "What one part hands another, as JSON. Field names and types are exact.",
        "",
        "| Contract | From | To | Fields |",
        "| --- | --- | --- | --- |",
        *(
            f"| `{i}` | {provider} | {', '.join(consumers)} | "
            f"{', '.join(f'`{name}`: {kind}' for name, kind in fields.items())} |"
            for i, (provider, consumers, fields) in contracts.items()
        ),
        "",
    ]
    return "\n".join(lines)


def change_message() -> str:
    """The launch change in the lead's words, for the approaches without Midflight. It
    says what plan version 2 says, and nothing more."""
    fields = "; ".join(
        f"`{contract}` gains " + ", ".join(f"`{name}`: {kind}" for name, kind in added.items())
        for contract, added in EXPRESS_FIELDS.items()
    )
    parts = ", ".join(f"{TASKS[t][0].lower()} ({t})" for t in EXPRESS_TASKS)
    return (
        f"One change for launch, a new requirement R-8. {EXPRESS} Contracts: {fields}. "
        f"It concerns {parts}."
    )


def names(contracts: list[str]) -> str:
    return ", ".join(f"`{c}`" for c in contracts) or "none"


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "starter" / "PLAN.md"
    target.write_text(render(1), encoding="utf-8", newline="\n")
    print(f"wrote {target}")
