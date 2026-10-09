"""Every external service sits behind one of these protocols (docs/domain.md, Ports).

Tests and laptops use the fakes in `midflight/adapters/`; AWS uses the real adapters.
A change here needs both programmers' approval.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from midflight.domain.models import (
    AuditEvent,
    Claim,
    Directive,
    Entity,
    Escalation,
    Finding,
    Job,
    Participant,
    Plan,
    Project,
    User,
    Verification,
)

# Store ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Commit:
    """One atomic write: every entity in `puts` plus its audit events, or nothing.

    - `expected_coord_rev` makes the write a compare-and-set on `Project.coord_rev`
      (INV-02). If the stored value differs, nothing is written and the store raises
      `RevisionConflict`, so the caller re-reads and reruns the review.
    - `bump_coord_rev` increments `Project.coord_rev` in the same write. Every claim
      or plan change does this.
    - `idempotency_key` makes retries safe (NFR-02, INV-13). A commit whose key was
      already applied writes nothing and returns `duplicate=True`.

    Put a claim together with its review job here, so accepted work can't lose its job
    (UC-04 step 3).
    """

    project_id: str
    idempotency_key: str
    puts: Sequence[Entity] = ()
    audit: Sequence[AuditEvent] = ()
    expected_coord_rev: int | None = None
    bump_coord_rev: bool = False


@dataclass(frozen=True)
class CommitResult:
    applied: bool
    duplicate: bool
    coord_rev: int


class RevisionConflict(Exception):
    """The project's coord_rev moved since the caller read it (INV-02)."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"coord_rev is {actual}, expected {expected}")
        self.expected = expected
        self.actual = actual


class Store(Protocol):
    def commit(self, commit: Commit) -> CommitResult:
        """Apply `commit` atomically, or raise RevisionConflict and write nothing."""
        ...

    def next_id(self, project_id: str, prefix: str) -> str:
        """An increasing id such as `D-3`, unique across all projects. Never reused.

        `project_id` is kept for context; ids are stored by themselves, so two teams
        must never get the same `C-1`.
        """
        ...

    def get_project(self, project_id: str) -> Project | None: ...

    def get_participant(self, participant_id: str) -> Participant | None: ...

    def find_participant_by_token_hash(self, token_hash: str) -> Participant | None: ...

    def list_participants(self, project_id: str) -> list[Participant]: ...

    def get_plan(self, project_id: str, version: int) -> Plan | None: ...

    def list_plans(self, project_id: str) -> list[Plan]: ...

    def get_claim(self, claim_id: str, revision: int | None = None) -> Claim | None:
        """The given revision, or the latest one when `revision` is None."""
        ...

    def claim_history(self, claim_id: str) -> list[Claim]:
        """Every revision, oldest first. Revisions are never overwritten."""
        ...

    def list_claims(self, project_id: str) -> list[Claim]:
        """The latest revision of every claim in the project."""
        ...

    def get_directive(self, directive_id: str) -> Directive | None: ...

    def list_directives(self, project_id: str, task_id: str | None = None) -> list[Directive]: ...

    def get_escalation(self, escalation_id: str) -> Escalation | None: ...

    def list_escalations(self, project_id: str) -> list[Escalation]: ...

    def get_verification(self, verification_id: str) -> Verification | None: ...

    def list_verifications(self, project_id: str) -> list[Verification]: ...

    def get_job(self, job_id: str) -> Job | None: ...

    def list_jobs(self, project_id: str) -> list[Job]: ...

    def list_audit(self, project_id: str, entity_id: str | None = None) -> list[AuditEvent]:
        """Oldest first, optionally only events that mention `entity_id`."""
        ...

    # People and projects (H-1). Users aren't tied to one project, so they're saved
    # directly rather than through a project commit.

    def save_user(self, user: User) -> None: ...

    def get_user(self, user_id: str) -> User | None: ...

    def find_user_by_github_id(self, github_id: int) -> User | None: ...

    def find_project_by_join_code(self, join_code: str) -> Project | None: ...

    def find_project_by_repository(self, repository: str) -> Project | None: ...

    def list_memberships(self, user_id: str) -> list[Participant]:
        """Every project membership of this user, including revoked ones."""
        ...

    # Sign-in records (H-3): OAuth clients, codes, and tokens, keyed by kind and key.
    # Keys for codes and tokens are hashes, never the secret itself.

    def put_auth(
        self, kind: str, key: str, value: dict[str, Any], expires_at: float | None = None
    ) -> None: ...

    def get_auth(self, kind: str, key: str) -> dict[str, Any] | None:
        """The record, or None if it doesn't exist or has expired."""
        ...

    def delete_auth(self, kind: str, key: str) -> None: ...


# Jobs ----------------------------------------------------------------------------------

JobHandler = Callable[[Job], None]


class JobRunner(Protocol):
    def submit(self, job: Job) -> None:
        """Run `job` with the registered handler, now (InlineRunner) or later (AWS)."""
        ...


# Reviewer ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimReviewRequest:
    """Everything the model sees about a claim. All of it is untrusted data (INV-07)."""

    plan: Plan
    claim: Claim
    other_claims: Sequence[Claim]
    rule_findings: Sequence[Finding]


@dataclass(frozen=True)
class CommitReviewRequest:
    """Everything the model sees about a pushed commit. Untrusted data (INV-07)."""

    plan: Plan
    claim: Claim
    head_sha: str
    diff: str
    files: Mapping[str, str] = field(default_factory=dict)
    rule_findings: Sequence[Finding] = ()


class ReviewerUnavailable(Exception):
    """The model timed out or errored. Never treated as approval (INV-01)."""


class Reviewer(Protocol):
    """Proposes findings. It never decides an outcome.

    Both methods return the model's raw reply (parsed JSON). Application code
    validates it against the Finding schema and checks every cited id before using
    it, so a malformed reply can't approve anything (INV-01).
    """

    def review_claim(self, request: ClaimReviewRequest) -> Any: ...

    def review_commit(self, request: CommitReviewRequest) -> Any: ...


# GitHub --------------------------------------------------------------------------------


@dataclass(frozen=True)
class PullRequestInfo:
    number: int
    head_branch: str
    head_sha: str
    base_sha: str


@dataclass(frozen=True)
class ChangedFiles:
    paths: Sequence[str]
    patch: str
    truncated: bool = False


@dataclass(frozen=True)
class CheckRunRequest:
    head_sha: str
    conclusion: str
    title: str
    summary: str
    annotations: Sequence[Mapping[str, Any]] = ()


class GitHubUnavailable(Exception):
    """GitHub errored, rate-limited, or timed out. Marks the project stale (UC-15)."""

    def __init__(self, reason: str, retry_after: datetime | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class GitHub(Protocol):
    """Fresh reads of GitHub state. Never trust webhook order (FR-08)."""

    def pull_for_branch(self, repository: str, branch: str) -> PullRequestInfo | None: ...

    def changed_files(self, repository: str, base_sha: str, head_sha: str) -> ChangedFiles:
        """The diff between two commits. `truncated` is True if GitHub cut it short."""
        ...

    def file_content(self, repository: str, path: str, ref: str) -> str | None: ...

    def run_artifact(self, repository: str, run_id: int, name: str) -> Any | None:
        """The parsed JSON of an Actions artifact, or None if missing or expired."""
        ...

    def create_check_run(self, repository: str, request: CheckRunRequest) -> int:
        """Publish a check run and return its id."""
        ...


# GitHub sign-in and repo access (H-3, H-4) ----------------------------------------------


@dataclass(frozen=True)
class GitHubAccount:
    id: int
    login: str
    name: str | None = None


class GitHubSignIn(Protocol):
    """Sign in with GitHub through the Midflight App's user authorization (D17)."""

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        """Where to send the person's browser to sign in."""
        ...

    def account_for_code(self, code: str, redirect_uri: str) -> GitHubAccount:
        """Trade the code GitHub sent back for the signed-in account."""
        ...


class RepoAccess(Protocol):
    """What Midflight needs to know before linking a project to a repo (H-4)."""

    def installation_id(self, repository: str) -> int | None:
        """The Midflight App's installation id on `owner/name`, or None if not installed."""
        ...

    def is_admin(self, repository: str, login: str) -> bool:
        """Whether this GitHub user can administer the repo."""
        ...


# Clock ---------------------------------------------------------------------------------


class Clock(Protocol):
    def now(self) -> datetime:
        """The current time, timezone-aware."""
        ...
