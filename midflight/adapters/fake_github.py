"""Stand-ins for GitHub, for tests and local development.

`FakeRepoAccess` answers "is the App installed?" and "is this person an admin?" from
what a test configured. `AnyRepoAccess` says yes to everything, for a local server
with the dev login, where there's no real GitHub App behind it. `FakeGitHub` plays the
pull requests, diffs, files, and test artifacts a verification reads.
"""

from __future__ import annotations

from typing import Any

from midflight.ports import ChangedFiles, CheckRunRequest, GitHubUnavailable, PullRequestInfo


class FakeRepoAccess:
    def __init__(
        self,
        installations: dict[str, int] | None = None,
        admins: set[tuple[str, str]] | None = None,
    ) -> None:
        self.installations = {k.lower(): v for k, v in (installations or {}).items()}
        self.admins = {(repo.lower(), login.lower()) for repo, login in (admins or set())}

    def installation_id(self, repository: str) -> int | None:
        return self.installations.get(repository.lower())

    def is_admin(self, repository: str, login: str) -> bool:
        return (repository.lower(), login.lower()) in self.admins


class AnyRepoAccess:
    """Local development only: every repository has the App and everyone is an admin."""

    def installation_id(self, repository: str) -> int | None:
        return 1

    def is_admin(self, repository: str, login: str) -> bool:
        return True


class FakeGitHub:
    """Scripted GitHub for verification tests. Set `down` to simulate an outage."""

    def __init__(self) -> None:
        self.pulls: dict[str, PullRequestInfo] = {}  # by branch
        self.diffs: dict[str, ChangedFiles] = {}  # by head sha
        self.files: dict[tuple[str, str], str] = {}  # (path, sha) -> content
        self.artifacts: dict[int, Any] = {}  # by workflow run id
        self.checks: list[CheckRunRequest] = []
        self.down: str | None = None

    def pull_for_branch(self, repository: str, branch: str) -> PullRequestInfo | None:
        self._gate()
        return self.pulls.get(branch)

    def changed_files(self, repository: str, base_sha: str, head_sha: str) -> ChangedFiles:
        self._gate()
        return self.diffs.get(head_sha, ChangedFiles(paths=(), patch=""))

    def file_content(self, repository: str, path: str, ref: str) -> str | None:
        self._gate()
        return self.files.get((path, ref))

    def run_artifact(self, repository: str, run_id: int, name: str) -> Any | None:
        self._gate()
        return self.artifacts.get(run_id)

    def create_check_run(self, repository: str, request: CheckRunRequest) -> int:
        self._gate()
        self.checks.append(request)
        return len(self.checks)

    def _gate(self) -> None:
        if self.down:
            raise GitHubUnavailable(self.down)
