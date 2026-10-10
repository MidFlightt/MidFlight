"""The real GitHub: Sign in with GitHub (H-3), repo checks (H-4), verification (M-6).

All three go through the one Midflight GitHub App:

- Sign-in uses the App's user authorization: the browser goes to GitHub, comes back
  with a code, and Midflight trades the code (with the App's client secret) for a
  short-lived user token, used once to read who signed in.
- Repo checks authenticate as the App itself: a JWT signed with the App's private key
  says "I am the App", which is enough to ask where the App is installed, and to get
  an installation token for reading a repository's collaborators.
- Verification (`GitHubAppClient`) uses the same installation token to read pull
  requests, diffs, files, and test artifacts, and to publish the `midflight/verify`
  check run.

Plain HTTP calls with httpx.
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx
import jwt

from midflight.ports import (
    ChangedFiles,
    CheckRunRequest,
    GitHubAccount,
    GitHubUnavailable,
    PullRequestInfo,
)

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


CHECK_NAME = "midflight/verify"
ARTIFACT_LIMIT = 5_000_000  # bytes; a contract-results artifact is a few kilobytes


class GitHubAppClient(GitHubAppRepoAccess):
    """Everything verification reads from and writes to GitHub (M-6), as the App.

    Each call uses the installation token for the repository's owner, cached until a
    few minutes before it expires. An outage, rate limit, or timeout raises
    `GitHubUnavailable`, which marks the project stale (UC-15); any other refusal (for
    example a missing App permission) raises `GitHubError`.
    """

    def __init__(self, app_id: str, private_key: str, http: httpx.Client | None = None) -> None:
        super().__init__(app_id, private_key, http)
        self._tokens: dict[str, tuple[str, float]] = {}

    def pull_for_branch(self, repository: str, branch: str) -> PullRequestInfo | None:
        owner = repository.split("/")[0]
        response = self._call(
            "GET", repository, f"/repos/{repository}/pulls", params={"head": f"{owner}:{branch}"}
        )
        self._check(response, f"list pull requests for {branch}")
        pulls = response.json()
        if not pulls:
            return None
        pull = pulls[0]
        return PullRequestInfo(
            number=pull["number"],
            head_branch=pull["head"]["ref"],
            head_sha=pull["head"]["sha"],
            base_sha=pull["base"]["sha"],
        )

    def changed_files(self, repository: str, base_sha: str, head_sha: str) -> ChangedFiles:
        path = f"/repos/{repository}/compare/{base_sha}...{head_sha}"
        response = self._call("GET", repository, path)
        self._check(response, f"compare {base_sha[:7]}...{head_sha[:7]}")
        files = response.json().get("files", [])
        patch = "\n".join(
            f"diff --git a/{f['filename']} b/{f['filename']}\n{f.get('patch', '')}" for f in files
        )
        # The compare API lists at most 300 files; more means the diff is incomplete.
        return ChangedFiles(
            paths=[f["filename"] for f in files], patch=patch, truncated=len(files) >= 300
        )

    def file_content(self, repository: str, path: str, ref: str) -> str | None:
        response = self._call(
            "GET",
            repository,
            f"/repos/{repository}/contents/{quote(path)}",
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if response.status_code == 404:
            return None
        self._check(response, f"read {path} at {ref[:7]}")
        return response.text

    def run_artifact(self, repository: str, run_id: int, name: str) -> Any | None:
        response = self._call(
            "GET",
            repository,
            f"/repos/{repository}/actions/runs/{run_id}/artifacts",
            params={"name": name},
        )
        self._check(response, f"list artifacts of run {run_id}")
        found = [
            a
            for a in response.json().get("artifacts", [])
            if a["name"] == name and not a.get("expired")
        ]
        if not found:
            return None
        # GitHub answers with a redirect to short-lived storage; fetch that without our token.
        link = self._call(
            "GET", repository, f"/repos/{repository}/actions/artifacts/{found[0]['id']}/zip"
        )
        if link.status_code != 302:
            self._check(link, f"download artifact {name}")
            return None
        try:
            archive = httpx.get(link.headers["location"], timeout=30)
        except httpx.HTTPError as error:
            raise GitHubUnavailable(f"couldn't download artifact {name}") from error
        if not archive.is_success or len(archive.content) > ARTIFACT_LIMIT:
            return None
        with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
            names = [n for n in zipped.namelist() if n.endswith(".json")]
            if not names:
                return None
            try:
                return json.loads(zipped.read(names[0]))
            except ValueError:
                return None

    def create_check_run(self, repository: str, request: CheckRunRequest) -> int:
        response = self._call(
            "POST",
            repository,
            f"/repos/{repository}/check-runs",
            json={
                "name": CHECK_NAME,
                "head_sha": request.head_sha,
                "status": "completed",
                "conclusion": request.conclusion,
                "output": {
                    "title": request.title,
                    "summary": request.summary[:65_000],
                    "annotations": list(request.annotations)[:50],
                },
            },
        )
        self._check(response, f"publish {CHECK_NAME}")
        return int(response.json()["id"])

    # Helpers ---------------------------------------------------------------------------

    def _call(self, method: str, repository: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**JSON, "Authorization": f"Bearer {self._token(repository)}"}
        headers |= kwargs.pop("headers", {})
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as error:
            raise GitHubUnavailable(f"GitHub didn't answer ({type(error).__name__})") from error
        _raise_if_unavailable(response)
        return response

    def _token(self, repository: str) -> str:
        owner = repository.split("/")[0].lower()
        cached = self._tokens.get(owner)
        if cached and cached[1] > time.time():
            return cached[0]
        try:
            installation = self.installation_id(repository)
            if installation is None:
                raise GitHubError(f"the Midflight App isn't installed on {repository}")
            token = self._installation_token(installation)
        except httpx.HTTPError as error:
            raise GitHubUnavailable(f"GitHub didn't answer ({type(error).__name__})") from error
        # Installation tokens last an hour; renew five minutes early.
        self._tokens[owner] = (token, time.time() + 55 * 60)
        return token


def _raise_if_unavailable(response: httpx.Response) -> None:
    """GitHub is down or rate-limiting us: worth retrying later, not a refusal."""
    limited = response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0"
    if response.status_code >= 500 or response.status_code == 429 or limited:
        retry_after = None
        if reset := response.headers.get("x-ratelimit-reset"):
            retry_after = datetime.fromtimestamp(int(reset), UTC)
        elif seconds := response.headers.get("retry-after"):
            retry_after = datetime.now(UTC) + timedelta(seconds=int(seconds))
        raise GitHubUnavailable(f"GitHub answered {response.status_code}", retry_after)
