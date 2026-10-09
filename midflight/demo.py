"""The synthetic checkout project from docs/domain.md (Demo fixture).

Used to seed a local API, by the tests, and later by the demo theater. No real data.
T1 Checkout API provides `checkout-response`, T2 Checkout page consumes it, and T3
Contributor guide has no interfaces. Plan v2 adds `currency: string`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from midflight.domain.models import (
    Contract,
    FieldType,
    Participant,
    Plan,
    PlanStatus,
    Project,
    Requirement,
    Role,
    Task,
)
from midflight.ports import Commit, Store
from midflight.services.participants import hash_token, new_token

PROJECT_ID = "demo"
REPOSITORY = "MidFlightt/midflight-demo-shop"
INSTALLATION_ID = 169380149
LEAD_ID = "p-lead"

# (participant id, role, developer, agent name, task it owns)
PEOPLE: list[tuple[str, Role, str, str | None, str | None]] = [
    (LEAD_ID, Role.LEAD, "somesh", None, None),
    ("p-t1", Role.AGENT, "somesh", "claude-code", "T1"),
    ("p-t2", Role.AGENT, "frederik", "claude-code", "T2"),
    ("p-t3", Role.AGENT, "mithilesh", "claude-code", "T3"),
]


def demo_plan(
    version: int = 1,
    *,
    approved_at: datetime | None = None,
    status: PlanStatus = PlanStatus.APPROVED,
) -> Plan:
    """Plan v1 (`total_cents`) or v2 (adds `currency`), approved by the lead by default."""
    fields = {"total_cents": FieldType.INTEGER}
    if version >= 2:
        fields["currency"] = FieldType.STRING
    approved = status is PlanStatus.APPROVED
    return Plan(
        project_id=PROJECT_ID,
        version=version,
        status=status,
        requirements=[
            Requirement(
                id="R-1",
                description="Show the order total at checkout",
                acceptance_criteria=["The page shows the total the API returns"],
            ),
            Requirement(id="R-2", description="Explain how to contribute"),
        ],
        tasks=[
            Task(
                id="T1",
                title="Checkout API",
                owner="p-t1",
                branch="t1-checkout-api",
                requirement_ids=["R-1"],
                provides=["checkout-response"],
            ),
            Task(
                id="T2",
                title="Checkout page",
                owner="p-t2",
                branch="t2-checkout-page",
                requirement_ids=["R-1"],
                consumes=["checkout-response"],
            ),
            Task(
                id="T3",
                title="Contributor guide",
                owner="p-t3",
                branch="t3-contributor-guide",
                requirement_ids=["R-2"],
            ),
        ],
        contracts=[
            Contract(
                id="checkout-response",
                version=version,
                provider_task="T1",
                consumer_tasks=["T2"],
                fields=fields,
            )
        ],
        approved_by=LEAD_ID if approved else None,
        approved_at=approved_at if approved else None,
        change_reason=("initial plan" if version == 1 else "add currency") if approved else None,
        changed_ids=[] if version == 1 else ["checkout-response"],
    )


def seed(store: Store, tokens: dict[str, str], now: datetime) -> None:
    """Save the demo project, its four participants, and plan v1 in one commit.

    `tokens` maps each participant id to its bearer token; only hashes are stored.
    """
    participants = [
        Participant(
            id=pid,
            project_id=PROJECT_ID,
            role=role,
            developer_name=developer,
            agent_name=agent,
            token_hash=hash_token(tokens[pid]),
        )
        for pid, role, developer, agent, _task in PEOPLE
    ]
    project = Project(
        id=PROJECT_ID,
        repository=REPOSITORY,
        github_installation_id=INSTALLATION_ID,
        lead_id=LEAD_ID,
        participant_ids=[p.id for p in participants],
        current_plan_version=1,
    )
    store.commit(
        Commit(
            project_id=PROJECT_ID,
            idempotency_key="seed:demo",
            puts=[project, *participants, demo_plan(1, approved_at=now)],
        )
    )


def local_tokens(path: Path = Path(".midflight/local-tokens.json")) -> dict[str, str]:
    """Tokens for the demo participants, kept in a git-ignored file so they survive
    restarts. Only the local stdio adapter (a development tool) uses them."""
    tokens: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    for participant_id, *_ in PEOPLE:
        tokens.setdefault(participant_id, new_token())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, indent=2))
    return tokens
