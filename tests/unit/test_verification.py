"""M-6, S-10, M-7: verifying pushes, the webhook, and GitHub outages (UC-10, 11, 15)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from demo_fixture import NOW, PROJECT, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.fake_github import FakeGitHub
from midflight.adapters.github import API, GitHubAppClient
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import Services, build_services, create_app
from midflight.domain.models import (
    ClaimState,
    DirectiveSource,
    DirectiveState,
    EscalationState,
    FindingKind,
    Participant,
    SyncState,
    Verification,
    VerificationOutcome,
)
from midflight.ports import ChangedFiles, CheckRunRequest, GitHubUnavailable, PullRequestInfo
from midflight.services.errors import PermissionDenied
from midflight.services.sync import FAULT_REASON
from midflight.services.verification import WorkflowRun

REPO = "MidFlightt/midflight-demo-shop"
INSTALLATION = 169380149
BRANCH = "t1-work"  # the demo T1 claim's branch
GOOD_API = "def checkout():\n    return {'total_cents': 4999}\n"
WRONG_API = "def checkout():\n    return {'total': 49.99}\n"


class Team:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.people: dict[str, Participant] = seed(self.store)
        self.github = FakeGitHub()
        self.services: Services = build_services(self.store, FixedClock(NOW), github=self.github)
        self.t1_claim = self.services.claims.submit(self.people["p-t1"], submission("T1"))
        assert self.t1_claim.state is ClaimState.APPROVED
        self.runs = 0

    def push(
        self,
        sha: str = "abc1234",
        files: dict[str, str] | None = None,
        tests: list[tuple[str, bool]] | None = None,
        branch: str = BRANCH,
        artifact_sha: str | None = None,
        head_now: str | None = None,
    ) -> WorkflowRun:
        """Pretend the agent pushed `files` and the contract tests reported `tests`."""
        files = {"app/api.py": GOOD_API} if files is None else files
        tests = [("test_total_cents_is_an_integer", True)] if tests is None else tests
        self.runs += 1
        self.github.pulls[branch] = PullRequestInfo(12, branch, head_now or sha, "9f3e1a2")
        self.github.diffs[sha] = ChangedFiles(paths=list(files), patch="(diff)")
        for path, text in files.items():
            self.github.files[(path, sha)] = text
        self.github.artifacts[self.runs] = {
            "sha": artifact_sha or sha,
            "results": [
                {"name": n, "passed": ok, "message": "" if ok else "KeyError"} for n, ok in tests
            ],
        }
        return WorkflowRun(REPO, INSTALLATION, self.runs, 1, sha, branch, f"delivery-{self.runs}")

    def verify(self, run: WorkflowRun) -> Verification | None:
        self.services.verifications.enqueue(run)
        found = [v for v in self.store.list_verifications(PROJECT) if v.head_sha == run.head_sha]
        return found[-1] if found else None


# Verification outcomes (UC-10, UC-11) --------------------------------------------------


def test_a_correct_push_is_verified_and_published_as_success() -> None:
    team = Team()
    v = team.verify(team.push())
    assert v.outcome is VerificationOutcome.VERIFIED
    assert (v.claim_id, v.claim_revision, v.plan_version) == (team.t1_claim.claim_id, 1, 1)
    [check] = team.github.checks
    assert check.conclusion == "success" and check.head_sha == "abc1234"
    assert v.check_run_id == 1


def test_a_failing_contract_test_becomes_a_correction_directive() -> None:
    team = Team()
    run = team.push(
        files={"app/api.py": WRONG_API}, tests=[("test_total_cents_is_an_integer", False)]
    )
    v = team.verify(run)

    # CI ran the contract tests; Midflight relays what failed and adds no opinion (D33).
    assert v.outcome is VerificationOutcome.FAILED
    assert {f.kind for f in v.findings if f.blocking} == {FindingKind.TEST_FAILURE}
    assert team.github.checks[0].conclusion == "failure"
    assert "total_cents" in team.github.checks[0].summary

    [directive] = team.store.list_directives(PROJECT, "T1")
    assert directive.source is DirectiveSource.VERIFICATION
    assert directive.verification_id == v.id and directive.recipient_id == "p-t1"
    assert "total_cents" in directive.requested_adjustment


def test_a_field_already_in_a_declared_file_counts() -> None:
    team = Team()
    team.github.files[("app/api.py", "abc1234")] = GOOD_API
    v = team.verify(team.push(files={"README.md": "Docs only."}))
    assert v.outcome is VerificationOutcome.VERIFIED


def test_missing_test_results_are_incomplete_never_success() -> None:
    team = Team()
    run = team.push()
    team.github.artifacts.clear()
    v = team.verify(run)
    assert v.outcome is VerificationOutcome.INCOMPLETE
    assert not v.evidence_coverage.test_results_present
    assert team.github.checks[0].conclusion == "action_required"


def test_test_results_for_another_commit_do_not_count() -> None:
    team = Team()
    v = team.verify(team.push(artifact_sha="fff0000"))
    assert v.outcome is VerificationOutcome.INCOMPLETE


def test_editing_the_contract_tests_goes_to_the_lead() -> None:
    team = Team()
    files = {"app/api.py": GOOD_API, "tests/contract/test_checkout.py": "assert True"}
    v = team.verify(team.push(files=files))
    assert v.outcome is VerificationOutcome.NEEDS_REVIEW
    [escalation] = team.store.list_escalations(PROJECT)
    assert escalation.verification_id == v.id and escalation.state is EscalationState.OPEN


def test_undeclared_files_are_shown_but_do_not_block() -> None:
    team = Team()
    v = team.verify(team.push(files={"app/api.py": GOOD_API, "app/util.py": "x = 1"}))
    assert v.outcome is VerificationOutcome.VERIFIED
    assert FindingKind.UNDECLARED_CHANGE in {f.kind for f in v.findings}


def test_a_push_without_an_approved_claim_is_incomplete() -> None:
    team = Team()
    v = team.verify(team.push(branch="someone-elses-branch"))
    assert v.outcome is VerificationOutcome.INCOMPLETE and v.claim_id is None


def test_a_newer_failure_supersedes_the_older_correction() -> None:
    team = Team()
    failing = {"files": {"app/api.py": WRONG_API}, "tests": [("test_total_cents", False)]}
    team.verify(team.push(sha="aaa1111", **failing))
    team.verify(team.push(sha="bbb2222", **failing))
    states = [d.state for d in team.store.list_directives(PROJECT, "T1")]
    assert states == [DirectiveState.SUPERSEDED, DirectiveState.QUEUED]


def test_a_comment_naming_the_field_does_not_count() -> None:
    team = Team()
    sneaky = "# returns total_cents, honest\ndef checkout():\n    return {'total': 49.99}\n"
    # No test results for this commit, so the field check is the only one there is.
    v = team.verify(team.push(files={"app/api.py": sneaky}, artifact_sha="0ld5ha1"))
    assert FindingKind.MISSING_CHANGE in {f.kind for f in v.findings if f.blocking}
    assert "total_cents" in team.github.checks[0].title  # the clearest reason leads


def test_passing_contract_tests_are_trusted_over_the_field_check() -> None:
    team = Team()
    v = team.verify(team.push(files={"app/api.py": WRONG_API}))
    assert v.outcome is VerificationOutcome.VERIFIED
    assert not [f for f in v.findings if f.kind is FindingKind.MISSING_CHANGE]


def test_changing_another_tasks_file_fails_the_push() -> None:
    team = Team()
    t2 = team.services.claims.submit(team.people["p-t2"], submission("T2"))
    assert t2.state is ClaimState.APPROVED  # T2's claim lists web/checkout.js

    files = {"app/api.py": GOOD_API, "web/checkout.js": "// T1 was here\n"}
    v = team.verify(team.push(files=files))

    assert v.outcome is VerificationOutcome.FAILED
    [foreign] = [f for f in v.findings if f.blocking]
    assert foreign.kind is FindingKind.UNDECLARED_CHANGE
    assert "web/checkout.js (T2)" in foreign.explanation
    [directive] = team.store.list_directives(PROJECT, "T1")
    assert "Undo those changes" in directive.requested_adjustment


def test_no_ai_reads_the_pushed_code() -> None:
    class NeverAsked:
        def review_claim(self, request: object) -> list[object]:
            return []

        def review_commit(self, request: object) -> list[object]:
            raise AssertionError("the pushed code must not go to the AI reviewer")

    team = Team()
    team.services = build_services(team.store, FixedClock(NOW), NeverAsked(), github=team.github)
    assert team.verify(team.push()).outcome is VerificationOutcome.VERIFIED


def test_a_url_is_not_mistaken_for_a_comment() -> None:
    team = Team()
    code = "requests.get('https://shop.test/checkout').json()['total_cents']  # cents\n"
    v = team.verify(team.push(files={"app/api.py": code}))
    assert v.outcome is VerificationOutcome.VERIFIED


def test_the_demo_shops_summary_artifact_counts() -> None:
    team = Team()
    run = team.push()
    team.github.artifacts[run.run_id] = {"head_sha": run.head_sha, "passed": True, "failures": []}
    assert team.verify(run).outcome is VerificationOutcome.VERIFIED

    failing = team.push(sha="bad0001", files={"app/api.py": WRONG_API})
    team.github.artifacts[failing.run_id] = {
        "head_sha": failing.head_sha,
        "passed": False,
        "failures": ["Provider: Expected {'total_cents': 'integer'}, got {'total': 'number'}"],
    }
    v = team.verify(failing)
    assert v.outcome is VerificationOutcome.FAILED
    assert [t.name for t in v.test_results] == ["Provider"]


# Dropping stale and duplicate work (UC-10 1, 6a) ---------------------------------------


def test_a_push_run_and_a_pull_request_run_for_one_commit_verify_once() -> None:
    team = Team()
    push_run = team.push()
    pr_run = WorkflowRun(REPO, INSTALLATION, 99, 1, push_run.head_sha, BRANCH, "d-pr")
    team.github.artifacts[99] = team.github.artifacts[push_run.run_id]
    team.services.verifications.enqueue(push_run)
    assert team.services.verifications.enqueue(pr_run) is None
    assert len(team.github.checks) == 1


def test_a_push_to_main_with_no_pull_request_or_claim_gets_no_check() -> None:
    team = Team()
    run = WorkflowRun(REPO, INSTALLATION, 7, 1, "aaa0000", "main", "d-main")
    team.github.artifacts[7] = {"sha": "aaa0000", "results": [{"name": "t", "passed": True}]}
    team.services.verifications.enqueue(run)
    assert team.store.list_verifications(PROJECT) == [] and team.github.checks == []


def test_a_duplicate_delivery_saves_one_job_and_one_check() -> None:
    team = Team()
    run = team.push()
    assert team.services.verifications.enqueue(run) is not None
    assert team.services.verifications.enqueue(run) is None
    assert len(team.store.list_verifications(PROJECT)) == 1
    assert len(team.github.checks) == 1


def test_a_newer_head_drops_the_result() -> None:
    team = Team()
    assert team.verify(team.push(head_now="def5678")) is None
    assert team.github.checks == []


def test_other_repositories_and_installations_are_ignored() -> None:
    team = Team()
    run = team.push()
    other_repo = WorkflowRun("someone/else", INSTALLATION, 1, 1, "abc1234", BRANCH, "d")
    other_install = WorkflowRun(REPO, 999, 1, 1, "abc1234", BRANCH, "d")
    assert team.services.verifications.enqueue(other_repo) is None
    assert team.services.verifications.enqueue(other_install) is None
    assert run  # the real run is untouched


# GitHub outages and the demo fault switch (UC-15, M-7) ---------------------------------


def test_an_outage_marks_the_project_stale_and_holds_approvals_until_it_recovers() -> None:
    team = Team()
    run = team.push()
    team.github.down = "GitHub answered 503"
    with pytest.raises(GitHubUnavailable):
        team.services.verifications.enqueue(run)
    project = team.store.get_project(PROJECT)
    assert project.sync_state is SyncState.STALE and "503" in project.sync_reason

    held = team.services.claims.submit(team.people["p-t2"], submission("T2"))
    assert held.state is ClaimState.PENDING  # no approvals while stale (INV-09)

    team.github.down = None
    team.verify(team.push(sha="abc9999"))
    assert team.store.get_project(PROJECT).sync_state is SyncState.FRESH
    assert team.store.get_claim(held.claim_id).state is ClaimState.APPROVED


def test_the_fault_switch_behaves_like_an_outage() -> None:
    team = Team()
    lead = team.people["p-lead"]
    team.services.sync.set_fault(lead, True)
    project = team.store.get_project(PROJECT)
    assert project.sync_state is SyncState.STALE and project.sync_reason == FAULT_REASON
    with pytest.raises(GitHubUnavailable):
        team.services.verifications.enqueue(team.push())
    assert team.services.check_ins.check_in(team.people["p-t1"], "T1").stale

    team.services.sync.set_fault(lead, False)
    assert team.store.get_project(PROJECT).sync_state is SyncState.FRESH


def test_only_the_lead_flips_the_fault_switch() -> None:
    team = Team()
    with pytest.raises(PermissionDenied):
        team.services.sync.set_fault(team.people["p-t2"], True)


# The webhook endpoint (UC-10 step 1) ---------------------------------------------------

SECRET = "webhook-secret"


def signed(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def run_event(sha: str = "abc1234", path: str = ".github/workflows/contract.yml") -> bytes:
    return json.dumps(
        {
            "action": "completed",
            "repository": {"full_name": REPO},
            "installation": {"id": INSTALLATION},
            "workflow_run": {
                "id": 1,
                "run_attempt": 1,
                "path": path,
                "head_sha": sha,
                "head_branch": BRANCH,
            },
        }
    ).encode()


def post(client: TestClient, body: bytes, event: str = "workflow_run", sig: str | None = None):
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "d-1",
        "X-Hub-Signature-256": sig if sig is not None else signed(body),
        "Content-Type": "application/json",
    }
    return client.post("/github/webhook", content=body, headers=headers)


def test_webhook_with_a_bad_signature_is_401_and_stores_nothing() -> None:
    team = Team()
    client = TestClient(create_app(team.services, webhook_secret=SECRET))
    body = run_event()
    assert post(client, body, sig=signed(body, "wrong")).status_code == 401
    assert post(client, body, sig="").status_code == 401
    assert team.store.list_verifications(PROJECT) == []


def test_webhook_queues_a_verification_for_a_finished_contract_run() -> None:
    team = Team()
    team.push()  # GitHub's state for run 1
    client = TestClient(create_app(team.services, webhook_secret=SECRET))
    response = post(client, run_event())
    assert response.status_code == 202 and "queued" in response.json()
    [v] = team.store.list_verifications(PROJECT)
    assert v.outcome is VerificationOutcome.VERIFIED


def test_webhook_ignores_other_events_and_answers_ping() -> None:
    team = Team()
    client = TestClient(create_app(team.services, webhook_secret=SECRET))
    assert post(client, b"{}", event="ping").status_code == 200
    assert post(client, b'{"action": "opened"}', event="pull_request").status_code == 202
    other = run_event(path=".github/workflows/ci.yml")
    assert post(client, other).json() == {"ignored": "not a finished contract-test run"}
    assert team.store.list_verifications(PROJECT) == []


def test_webhook_without_a_secret_refuses() -> None:
    team = Team()
    client = TestClient(create_app(team.services))
    assert post(client, run_event()).status_code == 503


# The real GitHub client, against a fake GitHub (no network) ----------------------------


def test_github_client_publishes_the_check_and_maps_outages() -> None:
    from test_github import PEM

    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == f"/repos/{REPO}/installation":
            return httpx.Response(200, json={"id": INSTALLATION})
        if path == f"/app/installations/{INSTALLATION}/access_tokens":
            return httpx.Response(201, json={"token": "ghs_x"})
        if path == f"/repos/{REPO}/check-runs":
            return httpx.Response(201, json={"id": 77})
        if path == f"/repos/{REPO}/pulls":
            return httpx.Response(503, json={})
        return httpx.Response(404, json={})

    http = httpx.Client(base_url=API, transport=httpx.MockTransport(handle))
    client = GitHubAppClient("5233457", PEM, http=http)
    request = CheckRunRequest(head_sha="abc1234", conclusion="failure", title="t", summary="s")
    assert client.create_check_run(REPO, request) == 77
    body: dict[str, Any] = json.loads(seen[-1].content)
    assert body["name"] == "midflight/verify" and body["conclusion"] == "failure"
    assert seen[-1].headers["authorization"] == "Bearer ghs_x"
    with pytest.raises(GitHubUnavailable):
        client.pull_for_branch(REPO, BRANCH)
