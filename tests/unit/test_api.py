"""M-2: the REST API over the in-memory store (UC-01, 03, 04, 06, 07, 09, 14, 16)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from demo_fixture import NOW
from midflight import demo
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services, create_app
from midflight.domain.models import Directive, DirectiveSource, PlanStatus, SyncState
from midflight.ports import ClaimReviewRequest, Commit, ReviewerUnavailable

TOKENS = {pid: f"mf_test_{pid}" for pid, *_ in demo.PEOPLE}
CHECKOUT = "checkout-response"


def auth(pid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKENS[pid]}"}


LEAD, T1, T2, T3 = auth("p-lead"), auth("p-t1"), auth("p-t2"), auth("p-t3")


def claim_body(task: str = "T2", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "task_id": task,
        "branch": f"{task.lower()}-work",
        "base_sha": "9f3e1a2",
        "plan_version": 1,
        "requirement_ids": ["R-1"],
        "files": ["web/checkout.js"],
        "consumes": [{"contract_id": CHECKOUT, "fields": {"total_cents": "integer"}}],
        "assumptions": ["total_cents is an integer number of cents"],
        "acceptance_criteria": ["The page shows $49.99 for 4999 cents"],
    }
    if task == "T1":
        body |= {
            "files": ["app/api.py"],
            "consumes": [],
            "provides": [{"contract_id": CHECKOUT, "fields": {"total_cents": "integer"}}],
        }
    return body | overrides


class FlakyReviewer:
    def __init__(self) -> None:
        self.down = True

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        if self.down:
            raise ReviewerUnavailable("timed out")
        return []

    def review_commit(self, request: object) -> Any:
        raise NotImplementedError


def make_client(reviewer: Any = None) -> tuple[TestClient, Services]:
    store = MemoryStore()
    clock = FixedClock(NOW)
    demo.seed(store, TOKENS, NOW)
    services = build_services(store, clock, reviewer)
    return TestClient(create_app(services)), services


@pytest.fixture
def client() -> TestClient:
    return make_client()[0]


# Auth (UC-01, INV-08, INV-12) ----------------------------------------------------------


def test_healthz_needs_no_token(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic abc"}]
)
def test_inv_08_unauthenticated_calls_get_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/projects/demo/plans/current", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"
    assert "Bearer" in response.json()["hint"]


def test_revoked_token_gets_401(client: TestClient) -> None:
    revoked = client.post("/participants/p-t3/revoke", json={"reason": "left"}, headers=LEAD)
    assert revoked.status_code == 200
    assert client.get("/projects/demo/plans/current", headers=T3).status_code == 401


def test_inv_08_agents_cannot_approve_plans_or_register_people(client: TestClient) -> None:
    approve = client.post("/projects/demo/plans/1/approve", json={"reason": "x"}, headers=T1)
    register = client.post(
        "/projects/demo/participants",
        json={"id": "p-x", "role": "agent", "developer_name": "x", "agent_name": "codex"},
        headers=T1,
    )
    assert approve.status_code == 403
    assert register.status_code == 403
    assert register.json()["error"] == "PermissionDenied"


def test_a_token_only_works_for_its_project(client: TestClient) -> None:
    assert client.get("/projects/other/plans/current", headers=T1).status_code == 403


def test_registering_returns_the_token_once_and_never_its_hash(client: TestClient) -> None:
    response = client.post(
        "/projects/demo/participants",
        json={"id": "p-t4", "role": "agent", "developer_name": "ana", "agent_name": "codex"},
        headers=LEAD,
    )
    assert response.status_code == 201
    token = response.json()["token"]
    assert "token_hash" not in response.json()["participant"]
    plan = client.get("/projects/demo/plans/current", headers={"Authorization": f"Bearer {token}"})
    assert plan.status_code == 200
    state = client.get("/projects/demo/state", headers=LEAD).json()
    assert all("token_hash" not in p for p in state["participants"])


# The G1 flow over HTTP (UC-04, UC-05, UC-06) --------------------------------------------


def test_total_vs_total_cents_over_http(client: TestClient) -> None:
    wrong = [{"contract_id": CHECKOUT, "fields": {"total": "number"}}]
    submitted = client.post("/projects/demo/claims", json=claim_body(consumes=wrong), headers=T2)
    assert submitted.status_code == 202
    first = submitted.json()
    assert first["state"] == "needs_revision"

    job = client.get(f"/jobs/{first['job_id']}", headers=T2).json()
    assert job["job"]["state"] == "succeeded"
    corrections = [f["proposed_correction"] for f in job["verdict"]["findings"]]
    assert corrections == ["Read `total_cents: integer`, not `total`."]

    revised = client.post(
        "/projects/demo/claims",
        json=claim_body(claim_id=first["claim_id"], reason="use total_cents"),
        headers=T2,
    ).json()
    assert (revised["revision"], revised["state"]) == (2, "approved")

    detail = client.get(f"/claims/{first['claim_id']}", headers=T2).json()
    assert [c["state"] for c in detail["history"]] == ["needs_revision", "approved"]
    assert detail["verdict"]["contracts"][0]["fields"] == {"total_cents": "integer"}


def test_unknown_contract_is_refused_with_findings(client: TestClient) -> None:
    cart = [{"contract_id": "cart", "fields": {"items": "array"}}]
    response = client.post("/projects/demo/claims", json=claim_body(consumes=cart), headers=T2)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "InvalidRequest"
    assert "checkout-response" in body["hint"]
    assert body["findings"][0]["kind"] == "unknown_reference"


def test_malformed_claim_is_a_422(client: TestClient) -> None:
    response = client.post("/projects/demo/claims", json={"task_id": "T2"}, headers=T2)
    assert response.status_code == 422


def test_claiming_another_agents_task_is_403(client: TestClient) -> None:
    response = client.post("/projects/demo/claims", json=claim_body("T2"), headers=T3)
    assert response.status_code == 403


def test_withdraw_and_close(client: TestClient) -> None:
    claim = client.post("/projects/demo/claims", json=claim_body("T1"), headers=T1).json()
    closed = client.post(f"/claims/{claim['claim_id']}/close", json={}, headers=T1)
    assert closed.json()["state"] == "closed"
    again = client.post(f"/claims/{claim['claim_id']}/withdraw", json={}, headers=T1)
    assert again.status_code == 409


def test_another_project_cannot_read_a_claim_or_job(client: TestClient) -> None:
    claim = client.post("/projects/demo/claims", json=claim_body("T1"), headers=T1).json()
    assert client.get(f"/claims/{claim['claim_id']}", headers=T2).status_code == 200
    assert client.get("/claims/C-404", headers=T2).status_code == 404
    assert client.get("/jobs/J-404", headers=T2).status_code == 404


# Plans (UC-03) -------------------------------------------------------------------------


def plan_v2_body() -> dict[str, Any]:
    plan = demo.demo_plan(2, status=PlanStatus.PROPOSED).model_dump(mode="json")
    return {k: plan[k] for k in ("requirements", "tasks", "contracts")}


def test_lead_proposes_and_approves_plan_v2(client: TestClient) -> None:
    proposed = client.post("/projects/demo/plans", json=plan_v2_body(), headers=LEAD)
    assert proposed.status_code == 201
    assert proposed.json()["status"] == "proposed"
    assert proposed.json()["changed_ids"] == [CHECKOUT]

    approved = client.post(
        "/projects/demo/plans/2/approve", json={"reason": "add currency"}, headers=LEAD
    )
    assert approved.json()["status"] == "approved"
    current = client.get("/projects/demo/plans/current", headers=T2).json()
    assert current["version"] == 2
    assert client.get("/projects/demo/plans/1", headers=T2).json()["version"] == 1


def test_approving_twice_is_a_conflict(client: TestClient) -> None:
    client.post("/projects/demo/plans", json=plan_v2_body(), headers=LEAD)
    client.post("/projects/demo/plans/2/approve", json={"reason": "add currency"}, headers=LEAD)
    again = client.post("/projects/demo/plans/2/approve", json={"reason": "again"}, headers=LEAD)
    assert again.status_code == 409


def test_invalid_plan_is_refused_with_every_problem(client: TestClient) -> None:
    body = plan_v2_body()
    body["contracts"][0]["provider_task"] = "T9"
    response = client.post("/projects/demo/plans", json=body, headers=LEAD)
    assert response.status_code == 400
    assert "unknown provider task T9" in response.json()["hint"]


def test_a_claim_on_the_old_plan_is_refused_after_v2(client: TestClient) -> None:
    client.post("/projects/demo/plans", json=plan_v2_body(), headers=LEAD)
    client.post("/projects/demo/plans/2/approve", json={"reason": "add currency"}, headers=LEAD)
    response = client.post("/projects/demo/claims", json=claim_body(), headers=T2)
    assert response.status_code == 400
    assert "plan v2" in response.json()["hint"]


# Check-in (UC-07, UC-16, FR-07) --------------------------------------------------------


def test_first_check_in_gives_the_task_and_its_contracts(client: TestClient) -> None:
    body = client.post("/projects/demo/check-in", json={}, headers=T2).json()
    assert body["task"]["id"] == "T2"
    assert [r["id"] for r in body["requirements"]] == ["R-1"]
    assert body["contracts"][0]["fields"] == {"total_cents": "integer"}
    assert body["claim"] is None
    assert body["ready_to_push"] is False
    assert body["push_blockers"] == ["no claim for this task; submit one before pushing"]


def test_check_in_after_approval_is_ready_to_push(client: TestClient) -> None:
    client.post("/projects/demo/claims", json=claim_body(), headers=T2)
    body = client.post("/projects/demo/check-in", json={"task_id": "T2"}, headers=T2).json()
    assert body["claim"]["state"] == "approved"
    assert body["ready_to_push"] is True


def test_second_check_in_reports_no_changes(client: TestClient) -> None:
    client.post("/projects/demo/check-in", json={}, headers=T2)
    assert client.post("/projects/demo/check-in", json={}, headers=T2).json()["changed"] is False


def test_checking_in_on_another_agents_task_is_403(client: TestClient) -> None:
    response = client.post("/projects/demo/check-in", json={"task_id": "T1"}, headers=T2)
    assert response.status_code == 403


def test_the_lead_uses_the_dashboard_not_check_in(client: TestClient) -> None:
    assert client.post("/projects/demo/check-in", json={}, headers=LEAD).status_code == 403


# Directives (UC-07, UC-09, INV-09, INV-10) ---------------------------------------------


def queue_directive(services: Services, directive_id: str = "D-42") -> None:
    directive = Directive(
        id=directive_id,
        project_id="demo",
        source=DirectiveSource.PLAN_CHANGE,
        task_id="T2",
        recipient_id="p-t2",
        plan_version=1,
        requested_adjustment="Display `currency` next to the total",
        reason="test directive",
        created_at=NOW,
    )
    services.store.commit(
        Commit(project_id="demo", idempotency_key=f"q:{directive_id}", puts=[directive])
    )


def test_check_in_delivers_a_directive_and_it_blocks_the_push() -> None:
    client, services = make_client()
    client.post("/projects/demo/claims", json=claim_body(), headers=T2)
    queue_directive(services)

    body = client.post("/projects/demo/check-in", json={}, headers=T2).json()
    assert body["delivered_now"] == ["D-42"]
    assert body["directives"][0]["state"] == "delivered"
    assert body["ready_to_push"] is False
    assert "D-42" in body["push_blockers"][0]

    ack = client.post(
        "/directives/D-42/ack", json={"response": "acknowledged", "note": "on it"}, headers=T2
    ).json()
    assert ack["directive"]["state"] == "acknowledged"
    assert "not implemented" in ack["note"]
    after = client.post("/projects/demo/check-in", json={}, headers=T2).json()
    assert after["ready_to_push"] is True


def test_an_undelivered_directive_cannot_be_answered() -> None:
    client, services = make_client()
    queue_directive(services)
    response = client.post("/directives/D-42/ack", json={"response": "acknowledged"}, headers=T2)
    assert response.status_code == 409


def test_another_agent_cannot_answer_a_directive() -> None:
    client, services = make_client()
    queue_directive(services)
    client.post("/projects/demo/check-in", json={}, headers=T2)
    response = client.post("/directives/D-42/ack", json={"response": "rejected"}, headers=T1)
    assert response.status_code == 403


def test_inv_09_directives_are_held_while_stale() -> None:
    client, services = make_client()
    queue_directive(services)
    project = services.store.get_project("demo")
    assert project is not None
    stale = project.model_copy(
        update={"sync_state": SyncState.STALE, "sync_reason": "rate limited"}
    )
    services.store.commit(Commit(project_id="demo", idempotency_key="stale", puts=[stale]))

    body = client.post("/projects/demo/check-in", json={}, headers=T2).json()
    assert body["stale"] is True
    assert body["delivered_now"] == []
    assert body["directives"] == []
    assert services.store.get_directive("D-42").state == "queued"  # type: ignore[union-attr]


# Jobs and audit (UC-14) ----------------------------------------------------------------


def test_lead_retries_a_failed_review() -> None:
    reviewer = FlakyReviewer()
    client, _ = make_client(reviewer)
    first = client.post("/projects/demo/claims", json=claim_body(), headers=T2).json()
    assert first["state"] == "pending"
    failed = client.get(f"/jobs/{first['job_id']}", headers=T2).json()
    assert failed["job"]["state"] == "failed"
    assert failed["verdict"]["review_complete"] is False

    assert client.post(f"/jobs/{first['job_id']}/retry", headers=T2).status_code == 403
    reviewer.down = False
    retried = client.post(f"/jobs/{first['job_id']}/retry", headers=LEAD).json()
    assert retried["state"] == "succeeded"
    claim = client.get(f"/claims/{first['claim_id']}", headers=T2).json()
    assert claim["claim"]["state"] == "approved"


def test_audit_trail_for_one_claim(client: TestClient) -> None:
    claim = client.post("/projects/demo/claims", json=claim_body(), headers=T2).json()
    events = client.get(
        "/projects/demo/audit", params={"entity_id": claim["claim_id"]}, headers=LEAD
    ).json()
    assert [e["action"] for e in events] == ["claim.submitted", "claim.reviewed"]


def test_dashboard_state_lists_everything(client: TestClient) -> None:
    client.post("/projects/demo/claims", json=claim_body(), headers=T2)
    state = client.get("/projects/demo/state", headers=LEAD).json()
    assert state["plan"]["version"] == 1
    assert [c["task_id"] for c in state["claims"]] == ["T2"]
    assert len(state["participants"]) == 4


# The local server ----------------------------------------------------------------------


def test_local_tokens_stay_the_same_across_restarts(tmp_path: Path) -> None:
    from midflight.api.local import local_tokens

    path = tmp_path / "tokens.json"
    first = local_tokens(path)
    assert set(first) == {pid for pid, *_ in demo.PEOPLE}
    assert local_tokens(path) == first
