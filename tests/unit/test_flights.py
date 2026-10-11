"""Fresh flights preserve history and atomically replace the repository's active flight."""

import boto3
import pytest
from moto import mock_aws

from demo_fixture import NOW
from midflight.adapters.clock import FixedClock
from midflight.adapters.dynamo_store import DynamoStore
from midflight.adapters.memory_store import MemoryStore
from midflight.domain.models import Participant, Project, Role, User
from midflight.ports import Commit
from midflight.services.errors import PermissionDenied, StateConflict
from midflight.services.flights import FlightService


@pytest.fixture(params=["memory", "dynamo"])
def setup(request):
    with mock_aws():
        if request.param == "memory":
            store = MemoryStore()
        else:
            client = boto3.client("dynamodb", region_name="us-east-1")
            DynamoStore.create_table(client, "flights")
            store = DynamoStore("flights", client)
        store.save_user(User(id="u-1", github_id=1, github_login="lead", created_at=NOW))
        lead = Participant(
            id="old.lead", project_id="old", role=Role.LEAD, developer_name="Lead", user_id="u-1"
        )
        project = Project(
            id="old",
            repository="acme/shop",
            lead_id=lead.id,
            participant_ids=[lead.id],
            join_code="OLD",
        )
        store.commit(Commit("old", "seed-flight", puts=[project, lead]))
        yield store, lead, FlightService(store, FixedClock(NOW))


def test_new_flight_is_empty_and_old_is_frozen(setup):
    store, lead, service = setup
    new = service.start(lead, "take-1", 0)
    assert new.id != "old"
    assert store.find_project_by_repository("acme/shop").id == new.id
    assert store.find_project_by_join_code("OLD") is None
    assert store.get_project("old").successor_project_id == new.id
    assert store.list_claims(new.id) == store.list_escalations(new.id) == []
    assert store.get_participant(new.lead_id).user_id == "u-1"
    assert service.start(lead, "take-1", 0).id == new.id
    with pytest.raises(StateConflict):
        store.commit(Commit("old", "stale-write", puts=[lead]))
    with pytest.raises(StateConflict):
        service.start(lead, "another-take", 0)


def test_only_lead_and_expected_revision(setup):
    store, lead, service = setup
    with pytest.raises(PermissionDenied):
        service.start(lead.model_copy(update={"role": Role.AGENT}), "take", 0)
    with pytest.raises(StateConflict):
        service.start(lead, "take", 99)
    assert store.find_project_by_repository("acme/shop").id == "old"


def test_copies_approved_plan_as_v1_without_decisions(setup):
    from demo_fixture import make_plan

    store, lead, service = setup
    source = make_plan().model_copy(
        update={
            "project_id": "old",
            "version": 4,
            "approved_by": lead.id,
            "tasks": [t.model_copy(update={"owner": lead.id}) for t in make_plan().tasks],
        }
    )
    old = store.get_project("old").model_copy(update={"current_plan_version": 4})
    store.commit(Commit("old", "plan", puts=[old, source]))
    new = service.start(lead, "copy-plan", 0)
    copied = store.get_plan(new.id, 1)
    assert copied.requirements == source.requirements
    assert all(t.owner == new.lead_id for t in copied.tasks)
    assert copied.approved_by == new.lead_id
    assert store.get_plan("old", 4) == source
    assert len(store.list_audit("old")) == len(store.list_audit(new.id)) == 1
    assert len(store.list_memberships("u-1")) == 2


def test_stale_atomic_replace_cannot_override_new_work(setup):
    store, lead, service = setup
    original = store.replace_flight

    def raced(*args):
        store.commit(Commit("old", "intervening-work", bump_coord_rev=True))
        original(*args)

    store.replace_flight = raced
    with pytest.raises(StateConflict):
        service.start(lead, "race", 0)
    assert not store.get_project("old").archived_at
    assert store.find_project_by_repository("acme/shop").id == "old"


def test_rest_reset_retries_and_successor_token_work(setup):
    import hashlib

    from fastapi.testclient import TestClient

    from midflight.api.app import build_services, create_app

    store, lead, _ = setup
    lead = lead.model_copy(update={"token_hash": hashlib.sha256(b"old-secret").hexdigest()})
    store.commit(Commit("old", "token", puts=[lead]))
    client = TestClient(create_app(build_services(store, FixedClock(NOW))))
    headers = {"Authorization": "Bearer old-secret"}
    body = {"request_id": "first", "expected_coord_rev": 0}
    response = client.post("/projects/old/flights", headers=headers, json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    retry = client.post("/projects/old/flights", headers=headers, json=body)
    assert retry.json() == result
    new_id = result["project"]["id"]
    assert (
        client.get(
            f"/projects/{new_id}/state", headers={"Authorization": "Bearer " + result["token"]}
        ).status_code
        == 200
    )
    assert client.get(f"/projects/{new_id}/state", headers=headers).status_code == 403
    assert client.post("/projects/old/flights", json=body).status_code == 401
