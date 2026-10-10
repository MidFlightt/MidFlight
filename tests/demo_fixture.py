"""Factories for the demo fixture in docs/domain.md, shared by every test.

T1 Checkout API provides `checkout-response`, T2 Checkout page consumes it, and T3
Contributor guide has no interfaces. Plan v1 has `total_cents: integer`; plan v2
adds `currency: string`.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from midflight.domain.models import (
    Claim,
    ClaimState,
    Contract,
    FieldType,
    InterfaceUse,
    Participant,
    Plan,
    PlanStatus,
    Project,
    Requirement,
    Role,
    Task,
)
from midflight.ports import Commit, Store
from midflight.services.claims import ClaimSubmission

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
                owner="p-t1",
                requirement_ids=["R-1"],
                provides=["checkout-response"],
            ),
            Task(
                id="T2",
                title="Checkout page",
                owner="p-t2",
                requirement_ids=["R-1"],
                consumes=["checkout-response"],
            ),
            Task(id="T3", title="Contributor guide", owner="p-t3", requirement_ids=["R-2"]),
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


def token_hash(participant_id: str) -> str:
    return hashlib.sha256(f"token-{participant_id}".encode()).hexdigest()


def seed(store: Store, plan_version: int = 1) -> dict[str, Participant]:
    """Save the demo project, its lead and three agents, and plans v1..plan_version."""
    people = {
        "p-lead": Participant(
            id="p-lead",
            project_id=PROJECT,
            role=Role.LEAD,
            developer_name="somesh",
            token_hash=token_hash("p-lead"),
        )
    }
    for task, developer in (("t1", "somesh"), ("t2", "frederik"), ("t3", "mithilesh")):
        people[f"p-{task}"] = Participant(
            id=f"p-{task}",
            project_id=PROJECT,
            role=Role.AGENT,
            developer_name=developer,
            agent_name="claude-code",
            token_hash=token_hash(f"p-{task}"),
        )
    project = Project(
        id=PROJECT,
        repository="MidFlightt/midflight-demo-shop",
        github_installation_id=169380149,
        lead_id="p-lead",
        participant_ids=list(people),
        current_plan_version=plan_version,
    )
    plans = [make_plan(v) for v in range(1, plan_version + 1)]
    store.commit(
        Commit(
            project_id=PROJECT,
            idempotency_key="seed",
            puts=[project, *people.values(), *plans],
        )
    )
    return people


def submission(base: str = "T2", **overrides: Any) -> ClaimSubmission:
    """A claim as task `base`'s agent sends it, with the same defaults as make_claim."""
    claim = make_claim(base)
    values = claim.model_dump(
        include=set(ClaimSubmission.model_fields) - {"claim_id"}, exclude_none=True
    )
    if base == "T1":
        values |= {
            "files": ["app/api.py", "README.md"],
            "consumes": [],
            "provides": [
                {"contract_id": "checkout-response", "fields": {"total_cents": "integer"}}
            ],
            "acceptance_criteria": ["GET /checkout returns total_cents as an integer"],
        }
    if base == "T3":
        values |= {
            "requirement_ids": ["R-2"],
            "files": ["CONTRIBUTING.md", "README.md"],
            "consumes": [],
            "no_interfaces": True,
            "acceptance_criteria": ["The guide explains branch naming"],
        }
    return ClaimSubmission.model_validate(values | overrides)
