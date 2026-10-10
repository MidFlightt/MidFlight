"""The GitHub webhook: `POST /github/webhook` (task M-6, UC-10 step 1).

1. The signature on the raw body is checked with the App's webhook secret. A missing or
   wrong signature gets 401, and nothing is stored (UC-10 1a).
2. Only a finished run of the contract-test workflow (`workflow_run`, action
   `completed`, file `contract.yml`) starts a verification (D4). Anything else gets 202
   and is ignored; `ping` gets 200.
3. A verification job is saved and GitHub gets 202 at once. A redelivered event saves
   nothing new.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from midflight.services.verification import CONTRACT_WORKFLOW, VerificationService, WorkflowRun


def add_webhook_route(app: FastAPI, verifications: VerificationService, secret: str | None) -> None:
    @app.post("/github/webhook", status_code=202, include_in_schema=False)
    async def github_webhook(request: Request) -> JSONResponse:
        if not secret:
            return JSONResponse({"error": "the webhook isn't configured"}, status_code=503)
        body = await request.body()
        if not valid_signature(secret, body, request.headers.get("x-hub-signature-256", "")):
            return JSONResponse({"error": "invalid signature"}, status_code=401)
        event = request.headers.get("x-github-event", "")
        if event == "ping":
            return JSONResponse({"ok": True}, status_code=200)
        run = workflow_run(event, json.loads(body), request.headers.get("x-github-delivery", ""))
        if run is None:
            return JSONResponse({"ignored": "not a finished contract-test run"}, status_code=202)
        job_id = await run_in_threadpool(verifications.enqueue, run)
        if job_id is None:
            return JSONResponse({"ignored": "duplicate, or no project for it"}, status_code=202)
        return JSONResponse({"queued": job_id}, status_code=202)


def valid_signature(secret: str, body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def workflow_run(event: str, payload: dict[str, Any], delivery_id: str) -> WorkflowRun | None:
    """The run in a `workflow_run.completed` event for the contract tests, else None."""
    if event != "workflow_run" or payload.get("action") != "completed":
        return None
    run = payload.get("workflow_run") or {}
    if not str(run.get("path", "")).endswith(CONTRACT_WORKFLOW):
        return None
    return WorkflowRun(
        repository=payload["repository"]["full_name"],
        installation_id=(payload.get("installation") or {}).get("id"),
        run_id=int(run["id"]),
        attempt=int(run.get("run_attempt", 1)),
        head_sha=run["head_sha"],
        head_branch=run["head_branch"],
        delivery_id=delivery_id,
    )
