"""H-5: the AWS path on moto. The web side saves a claim and its job; the DynamoDB stream
hands the job to the worker Lambda, which reviews the claim."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws

from demo_fixture import NOW, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.dynamo_store import DynamoStore
from midflight.adapters.runners import StreamRunner
from midflight.api.app import build_services
from midflight.aws.worker import handler
from midflight.config import Settings
from midflight.domain.models import ClaimState, JobState
from midflight.main import create_server

TABLE = "midflight-test"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        db = boto3.client("dynamodb", region_name="us-east-1")
        DynamoStore.create_table(db, TABLE)
        yield db


def stream_event(db: Any, job_id: str) -> dict[str, Any]:
    """The record DynamoDB's stream would send for a new job item."""
    items = db.scan(TableName=TABLE)["Items"]
    job_item = next(
        i for i in items if i.get("type", {}).get("S") == "job" and job_id in i["SK"]["S"]
    )
    return {"Records": [{"eventName": "INSERT", "dynamodb": {"NewImage": job_item}}]}


def test_the_worker_reviews_a_claim_saved_by_the_web_side(client: Any) -> None:
    store = DynamoStore(TABLE, client)
    people = seed(store)
    services = build_services(store, FixedClock(NOW), runner=StreamRunner())

    result = services.claims.submit(people["p-t2"], submission("T2"))
    assert result.state is ClaimState.PENDING  # saved; nobody has reviewed it yet

    handler(stream_event(client, result.job_id), services=services)
    claim = store.get_claim(result.claim_id)
    assert claim is not None and claim.state is ClaimState.APPROVED
    assert store.get_job(result.job_id).state is JobState.SUCCEEDED  # type: ignore[union-attr]

    handler(stream_event(client, result.job_id), services=services)  # delivered twice
    reviewed = [
        e for e in store.list_audit("demo", result.claim_id) if e.action == "claim.reviewed"
    ]
    assert len(reviewed) == 1


def test_the_worker_ignores_items_that_are_not_new_jobs(client: Any) -> None:
    services = build_services(DynamoStore(TABLE, client), FixedClock(NOW), runner=StreamRunner())
    handler(
        {"Records": [{"eventName": "MODIFY", "dynamodb": {"NewImage": {"type": {"S": "job"}}}}]},
        services=services,
    )


def test_settings_read_secrets_from_secrets_manager() -> None:
    secret = {
        "github_client_secret": "shh",
        "github_private_key": "-----BEGIN PRIVATE KEY-----",
        "github_webhook_secret": "REPLACE_ME",
    }
    settings = Settings.from_env(
        {
            "MIDFLIGHT_SECRET_ID": "midflight/github",
            "MIDFLIGHT_GITHUB_CLIENT_ID": "Iv23li",
            "MIDFLIGHT_TABLE": TABLE,
        },
        read_secret=lambda secret_id: secret if secret_id == "midflight/github" else {},
    )
    assert settings.github_client_secret == "shh"
    assert settings.github_private_key == "-----BEGIN PRIVATE KEY-----"
    assert settings.github_sign_in_configured and settings.table_name == TABLE


def test_the_server_uses_dynamodb_when_a_table_is_set(client: Any) -> None:
    server = create_server(Settings(dev_login=True, table_name=TABLE))
    assert isinstance(server.services.store, DynamoStore)
