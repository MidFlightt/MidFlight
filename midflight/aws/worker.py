"""The worker Lambda: runs background jobs saved by the web Lambda (task H-5).

When the web Lambda saves a claim, it saves its review job in the same DynamoDB
transaction. DynamoDB's stream delivers each new job item here (the template filters
the stream to new items of type `job`), and the job's handler runs, exactly as
`InlineRunner` does on a laptop. If a handler fails, Lambda retries the record twice,
then sends it to the dead-letter queue (NFR-06).
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from midflight.adapters.clock import SystemClock
from midflight.adapters.dynamo_store import DynamoStore
from midflight.adapters.runners import StreamRunner
from midflight.api.app import Services, build_services
from midflight.config import Settings
from midflight.domain.models import Job, JobKind


@cache
def _services() -> Services:
    settings = Settings.from_env()
    if not settings.table_name:
        raise RuntimeError("MIDFLIGHT_TABLE isn't set")
    store = DynamoStore(settings.table_name)
    return build_services(store, SystemClock(), runner=StreamRunner())


def run_job(job: Job, services: Services) -> None:
    """Run one job with its handler. Each handler is safe to run twice (INV-13)."""
    if job.kind is JobKind.CLAIM_REVIEW:
        services.claims.run_review(job)
    else:
        # Plan propagation (S-6), verification (M-6), and reconcile (M-7) plug in here.
        raise NotImplementedError(f"no handler for {job.kind} jobs yet")


def handler(event: dict[str, Any], context: Any = None, services: Services | None = None) -> None:
    """Lambda entry point for DynamoDB stream events."""
    services = services or _services()
    for record in event.get("Records", []):
        image = record.get("dynamodb", {}).get("NewImage", {})
        if record.get("eventName") != "INSERT" or image.get("type", {}).get("S") != "job":
            continue
        job = Job.model_validate(json.loads(image["data"]["S"]))
        run_job(job, services)
