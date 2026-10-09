"""The real GitHub, for Sign in with GitHub (H-3) and repo checks (H-4).

Both go through the one Midflight GitHub App ("MidFlight Team Yoga"):

- Sign-in uses the App's user authorization: the browser goes to GitHub, comes back
  with a code, and Midflight trades the code (with the App's client secret) for a
  short-lived user token, used once to read who signed in.
- Repo checks authenticate as the App itself: a JWT signed with the App's private key
  says "I am the App", which is enough to ask where the App is installed, and to get
  an installation token for reading a repository's collaborators.

Plain HTTP calls with httpx; githubkit arrives with the verification work (M-6).
"""

from __future__ import annotations

import time
from urllib.parse import urlencode

import httpx
import jwt

from midflight.ports import GitHubAccount

GITHUB = "https://github.com"
API = "https://api.github.com"
JSON = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


class GitHubError(Exception):
    """GitHub refused or failed a request Midflight needed."""


class GitHubAppSignIn:
    def __init__(self, client_id: str, client_secret: str, http: httpx.Client | None = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http or httpx.Client(timeout=15)

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {"client_id": self._client_id, "redirect_uri": redirect_uri, "state": state}
        )
        return f"{GITHUB}/login/oauth/authorize?{query}"

    def account_for_code(self, code: str, redirect_uri: str) -> GitHubAccount:
        token_response = self._http.post(
            f"{GITHUB}/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        token = token_response.json().get("access_token") if token_response.is_success else None
        if not token:
            raise GitHubError(
                f"GitHub didn't accept the sign-in code ({token_response.text[:200]})"
            )
        user = self._http.get(f"{API}/user", headers={**JSON, "Authorization": f"Bearer {token}"})
        if not user.is_success:
            raise GitHubError(f"couldn't read the signed-in GitHub account ({user.status_code})")
        body = user.json()
        return GitHubAccount(id=body["id"], login=body["login"], name=body.get("name"))


class GitHubAppRepoAccess:
    def __init__(self, app_id: str, private_key: str, http: httpx.Client | None = None) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._http = http or httpx.Client(base_url=API, timeout=15)

    def installation_id(self, repository: str) -> int | None:
        response = self._http.get(f"/repos/{repository}/installation", headers=self._as_app())
        if response.status_code == 404:
            return None
        self._check(response, f"look up the App installation on {repository}")
        return int(response.json()["id"])

    def is_admin(self, repository: str, login: str) -> bool:
        installation = self.installation_id(repository)
        if installation is None:
            return False
        token = self._installation_token(installation)
        response = self._http.get(
            f"/repos/{repository}/collaborators/{login}/permission",
            headers={**JSON, "Authorization": f"Bearer {token}"},
        )
        if response.status_code == 404:
            return False
        self._check(response, f"read {login}'s permission on {repository}")
        return response.json().get("permission") == "admin"

    def _installation_token(self, installation_id: int) -> str:
        response = self._http.post(
            f"/app/installations/{installation_id}/access_tokens", headers=self._as_app()
        )
        self._check(response, "get an installation token")
        return str(response.json()["token"])

    def _as_app(self) -> dict[str, str]:
        now = int(time.time())
        # Backdated a minute for clock drift; GitHub allows at most 10 minutes.
        claims = {"iat": now - 60, "exp": now + 540, "iss": self._app_id}
        token = jwt.encode(claims, self._private_key, algorithm="RS256")
        return {**JSON, "Authorization": f"Bearer {token}"}

    @staticmethod
    def _check(response: httpx.Response, doing: str) -> None:
        if not response.is_success:
            raise GitHubError(f"couldn't {doing}: GitHub answered {response.status_code}")
