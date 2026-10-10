"""Stand-ins for GitHub, for tests and local development.

`FakeRepoAccess` answers "is the App installed?" and "is this person an admin?" from
what a test configured. `AnyRepoAccess` says yes to everything, for a local server
with the dev login, where there's no real GitHub App behind it.
"""

from __future__ import annotations


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
