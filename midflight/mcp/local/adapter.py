"""Development tool: the MCP tools over stdio, calling a Midflight API (M-3, D20).

Customers use the hosted connector (`midflight.mcp.hosted`); this adapter is for
working on Midflight locally.

    claude mcp add midflight -e MIDFLIGHT_URL=http://127.0.0.1:8000 \\
        -e MIDFLIGHT_TOKEN=<token> -e MIDFLIGHT_PROJECT=demo \\
        -- uv run --directory <path-to-midflight> python -m midflight.mcp.local.adapter

Three tools: `submit_claim` (waits up to 60 s and returns the verdict in the same
call), `check_in`, and `acknowledge_directive`. Every reply ends with the task's open
directives. The server's instructions are the agent instructions in docs/domain.md.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from midflight.domain.models import InterfaceUse
from midflight.mcp.instructions import (
    ACKNOWLEDGE_DIRECTIVE,
    CHECK_IN,
    INSTRUCTIONS,
    SUBMIT_CLAIM,
)
from midflight.mcp.local.client import MidflightApi, MidflightUnavailable, NotSignedIn, Refused
from midflight.mcp.replies import (
    check_in_text,
    directives_block,
    refused_text,
    verdict_text,
)

# The agent instructions from docs/domain.md (Interfaces, D10). Keep the two in sync.
UNREACHABLE = (
    "Midflight is unreachable ({reason}), so this couldn't be reviewed. Do NOT proceed as "
    "if your claim were approved. Tell your developer, and try again shortly."
)
NOT_SIGNED_IN = (
    "Midflight rejected the token ({reason}). Check MIDFLIGHT_TOKEN in this MCP server's "
    "configuration; the lead issues tokens."
)

DONE_STATES = {"succeeded", "failed"}

Git = Callable[[list[str]], str | None]


def build_server(
    api: MidflightApi | None,
    *,
    config_error: str | None = None,
    wait_seconds: float = 60.0,
    poll_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    git: Git | None = None,
) -> MCPServer:
    """The MCP server around one Midflight API connection."""
    server = MCPServer("midflight", instructions=INSTRUCTIONS, version="0.1.0")
    run_git = git or _git

    def guarded(action: Callable[[MidflightApi], str]) -> str:
        if api is None:
            return f"Midflight isn't configured: {config_error}"
        try:
            return action(api)
        except MidflightUnavailable as error:
            return UNREACHABLE.format(reason=error)
        except NotSignedIn as error:
            return NOT_SIGNED_IN.format(reason=error)
        except Refused as error:
            return refused_text(error.body)

    def with_directives(api: MidflightApi, text: str, task_id: str | None = None) -> str:
        try:
            reply = api.check_in(task_id)
        except (MidflightUnavailable, NotSignedIn, Refused):
            return text
        return f"{text}\n\n{directives_block(reply['directives'])}"

    @server.tool(description=SUBMIT_CLAIM)
    def submit_claim(
        task_id: str,
        plan_version: int,
        acceptance_criteria: list[str] | None = None,
        provides: list[InterfaceUse] | None = None,
        consumes: list[InterfaceUse] | None = None,
        no_interfaces: bool = False,
        assumptions: list[str] | None = None,
        files: list[str] | None = None,
        requirement_ids: list[str] | None = None,
        claim_id: str | None = None,
        reason: str | None = None,
        branch: str | None = None,
        base_sha: str | None = None,
        status: Literal["withdrawn", "closed"] | None = None,
    ) -> str:
        def act(api: MidflightApi) -> str:
            if status is not None:
                if claim_id is None:
                    return f"To set status {status}, pass the claim_id."
                change = api.withdraw if status == "withdrawn" else api.close
                claim = change(claim_id, reason)
                text = f"Claim {claim['id']} rev {claim['revision']}: {claim['state'].upper()}"
                return with_directives(api, text, task_id)
            current_branch = branch or run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            current_sha = base_sha or run_git(["rev-parse", "HEAD"])
            if not current_branch or not current_sha:
                return "Couldn't read your git branch and commit. Pass branch and base_sha."
            body: dict[str, Any] = {
                "claim_id": claim_id,
                "task_id": task_id,
                "branch": current_branch,
                "base_sha": current_sha,
                "plan_version": plan_version,
                "requirement_ids": requirement_ids or [],
                "files": files or [],
                "provides": [u.model_dump(mode="json") for u in provides or []],
                "consumes": [u.model_dump(mode="json") for u in consumes or []],
                "no_interfaces": no_interfaces,
                "assumptions": assumptions or [],
                "acceptance_criteria": acceptance_criteria or [],
                "reason": reason,
            }
            submitted = api.submit_claim(body)
            deadline = time.monotonic() + wait_seconds
            while True:
                job = api.job(submitted["job_id"])
                if job["job"]["state"] in DONE_STATES and job["verdict"]:
                    verdict = job["verdict"]
                    return f"{verdict_text(verdict)}\n\n{directives_block(verdict['directives'])}"
                if time.monotonic() >= deadline:
                    text = (
                        f"Claim {submitted['claim_id']} rev {submitted['revision']}: PENDING. "
                        f"The review is still running (job {submitted['job_id']}). Work only "
                        "on steps that don't depend on it; the verdict comes with your next "
                        "check_in. Don't resubmit."
                    )
                    return with_directives(api, text, task_id)
                sleep(poll_seconds)

        return guarded(act)

    @server.tool(description=CHECK_IN)
    def check_in(task_id: str | None = None) -> str:
        return guarded(lambda api: check_in_text(api.check_in(task_id)))

    @server.tool(description=ACKNOWLEDGE_DIRECTIVE)
    def acknowledge_directive(
        directive_id: str,
        response: Literal["acknowledged", "rejected", "needs_clarification"],
        note: str | None = None,
    ) -> str:
        def act(api: MidflightApi) -> str:
            answered = api.acknowledge(directive_id, response, note)
            directive = answered["directive"]
            text = f"Directive {directive['id']}: {directive['state']}. {answered['note']}"
            return with_directives(api, text, directive["task_id"])

        return guarded(act)

    return server


def _git(args: list[str]) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def main() -> None:
    # stdout is the MCP channel; keep httpx's per-request INFO lines out of the log too.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    url = os.environ.get("MIDFLIGHT_URL", "http://127.0.0.1:8000")
    token = os.environ.get("MIDFLIGHT_TOKEN")
    project = os.environ.get("MIDFLIGHT_PROJECT", "demo")
    if not token:
        server = build_server(None, config_error="set MIDFLIGHT_TOKEN to your Midflight token")
    else:
        server = build_server(MidflightApi.connect(url, token, project))
    server.run("stdio")


if __name__ == "__main__":
    main()
