"""Factories for the demo fixture in docs/domain.md, shared by every test.

T1 Checkout API provides `checkout-response`, T2 Checkout page consumes it, and T3
Contributor guide has no interfaces. Plan v1 has `total_cents: integer`; plan v2
adds `currency: string`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from midflight.domain.models import (
    Claim,
    ClaimState,
    Contract,
    FieldType,
    InterfaceUse,
    Plan,
    PlanStatus,
    Requirement,
    Task,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
PROJECT = "demo"
BASE_SHA = "9f3e1a2"


def make_plan(version: int = 1) -> Plan:
    fields = {"total_cents": FieldType.INTEGER}
    if version >= 2:
        fields["currency"] = FieldType.STRING
    return Plan(
        project_id=PROJECT,
        version=version,
        status=PlanStatus.APPROVED,
        requirements=[
            Requirement(id="R-1", description="Show the order total at checkout"),
            Requirement(id="R-2", description="Explain how to contribute"),
        ],
        tasks=[
            Task(
                id="T1",
                title="Checkout API",
                owner="p-somesh",
                requirement_ids=["R-1"],
                provides=["checkout-response"],
            ),
            Task(
                id="T2",
                title="Checkout page",
                owner="p-frederik",
                requirement_ids=["R-1"],
                consumes=["checkout-response"],
            ),
            Task(id="T3", title="Contributor guide", owner="p-mithilesh", requirement_ids=["R-2"]),
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
        approved_by="p-lead",
        approved_at=NOW,
        change_reason="initial plan" if version == 1 else "add currency",
        changed_ids=[] if version == 1 else ["checkout-response"],
    )


def make_claim(task_id: str = "T2", **overrides: Any) -> Claim:
    values: dict[str, Any] = {
        "id": f"C-{task_id}",
        "revision": 1,
        "project_id": PROJECT,
        "task_id": task_id,
        "agent_id": f"p-{task_id.lower()}",
        "branch": f"{task_id.lower()}-work",
        "base_sha": BASE_SHA,
        "plan_version": 1,
        "state": ClaimState.PENDING,
        "requirement_ids": ["R-1"],
        "files": ["web/checkout.js"],
        "consumes": [
            InterfaceUse(contract_id="checkout-response", fields={"total_cents": FieldType.INTEGER})
        ],
        "assumptions": ["total_cents is an integer number of cents"],
        "acceptance_criteria": ["The page shows $49.99 for 4999 cents"],
        "created_at": NOW,
    }
    values.update(overrides)
    return Claim(**values)
