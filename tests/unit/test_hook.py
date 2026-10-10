"""M-4: the pre-push hook, its token, and the push check (UC-16, D8, D20)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demo_fixture import NOW, make_plan, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services, create_app
from midflight.domain.models import Participant
from midflight.hooks.pre_push import SCRIPT
from midflight.services.plans import PlanDraft


@pytest.fixture
def team() -> tuple[Services, dict[str, Participant], TestClient]:
    store = MemoryStore()
    people = seed(store)
    services = build_services(store, FixedClock(NOW))
    return services, people, TestClient(create_app(services))


def push_check(client: TestClient, token: str, task: str = "T1"):
    return client.post(
        "/projects/demo/push-check",
        json={"task_id": task},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_push_is_blocked_until_the_claim_is_approved(team) -> None:
    services, people, client = team
    token = services.participants.issue_hook_token(people["p-t1"])

    blocked = push_check(client, token)
    assert blocked.status_code == 409 and "no claim for this task" in blocked.text

    services.claims.submit(people["p-t1"], submission("T1"))
    ready = push_check(client, token)
    assert ready.status_code == 200 and "ready to push" in ready.text


def test_an_unanswered_directive_blocks_the_push(team) -> None:
    services, people, client = team
    token = services.participants.issue_hook_token(people["p-t1"])
    services.claims.submit(people["p-t1"], submission("T1"))
    plan = make_plan(2)
    lead = people["p-lead"]
    draft = PlanDraft(requirements=plan.requirements, tasks=plan.tasks, contracts=plan.contracts)
    services.plans.approve(lead, services.plans.propose(lead, draft).version, "add currency")

    reply = push_check(client, token)
    [directive] = services.store.list_directives("demo", "T1")
    assert reply.status_code == 409
    assert directive.id in reply.text and "currency" in reply.text


def test_a_new_hook_token_replaces_the_old_one(team) -> None:
    services, people, client = team
    old = services.participants.issue_hook_token(people["p-t1"])
    new = services.participants.issue_hook_token(people["p-t1"])
    assert push_check(client, old).status_code == 401
    assert push_check(client, new).status_code == 409


def test_the_hook_script_is_served_with_unix_line_endings(team) -> None:
    _services, _people, client = team
    script = client.get("/hook/pre-push").text
    assert script.startswith("#!/bin/sh\n") and "\r" not in script
    assert "/push-check" in script


# The script itself, run by sh with a stand-in curl --------------------------------------

needs_sh = pytest.mark.skipif(
    not (shutil.which("sh") and shutil.which("git")), reason="needs sh and git"
)


def run_hook(tmp_path: Path, curl_reply: str | None, configured: bool = True):
    """Run the hook in a fresh repo. `curl_reply` is what curl prints; None = unreachable."""
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    if configured:
        for key, value in (("url", "http://mf"), ("project", "demo"), ("token", "mf_x")):
            subprocess.run(
                ["git", "-C", str(repo), "config", f"midflight.{key}", value], check=True
            )
    hook = repo / "hook.sh"
    hook.write_bytes(SCRIPT.encode())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = "exit 7\n" if curl_reply is None else f"printf '%s' '{curl_reply}'\n"
    (bin_dir / "curl").write_bytes(f"#!/bin/sh\n{fake}".encode())
    (bin_dir / "curl").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["sh", "hook.sh"], cwd=repo, env=env, capture_output=True, text=True, timeout=30
    )


@needs_sh
def test_the_script_blocks_on_409(tmp_path: Path) -> None:
    result = run_hook(tmp_path, "T1 is not ready to push\n409")
    assert result.returncode == 1 and "push blocked" in result.stderr


@needs_sh
def test_the_script_allows_on_200(tmp_path: Path) -> None:
    assert run_hook(tmp_path, "ready\n200").returncode == 0


@needs_sh
def test_the_script_warns_and_allows_when_midflight_is_unreachable(tmp_path: Path) -> None:
    result = run_hook(tmp_path, None)
    assert result.returncode == 0 and "can't reach Midflight" in result.stderr


@needs_sh
def test_the_script_allows_when_not_set_up(tmp_path: Path) -> None:
    result = run_hook(tmp_path, "x\n409", configured=False)
    assert result.returncode == 0 and "not set up" in result.stderr
