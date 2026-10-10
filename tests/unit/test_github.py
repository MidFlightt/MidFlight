"""H-3 and H-4 with the real GitHub code paths, against a fake GitHub (no network).

- `GitHubAppSignIn` and `GitHubAppRepoAccess` make the right calls and read the answers.
- The server's sign-in sends the browser to GitHub and, on GitHub's callback, back to
  the AI client with a Midflight code.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from midflight.adapters.fake_github import FakeRepoAccess
from midflight.adapters.github import GitHubAppRepoAccess, GitHubAppSignIn, GitHubError
from midflight.config import Settings
from midflight.main import create_server
from midflight.ports import GitHubAccount

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()


def fake_github(routes: dict[tuple[str, str], tuple[int, Any]], seen: list[httpx.Request]):
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = routes.get(
            (request.method, request.url.path), (404, {"message": "Not Found"})
        )
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


# Sign-in adapter -----------------------------------------------------------------------


def test_sign_in_url_goes_to_github_with_the_app_client_id() -> None:
    url = urlparse(GitHubAppSignIn("Iv23li", "secret").authorize_url("st", "https://m/cb"))
    query = parse_qs(url.query)
    assert url.netloc == "github.com" and url.path == "/login/oauth/authorize"
    assert query == {"client_id": ["Iv23li"], "redirect_uri": ["https://m/cb"], "state": ["st"]}


def test_a_github_code_becomes_the_signed_in_account() -> None:
    seen: list[httpx.Request] = []
    http = httpx.Client(
        transport=fake_github(
            {
                ("POST", "/login/oauth/access_token"): (200, {"access_token": "ghu_x"}),
                ("GET", "/user"): (200, {"id": 7, "login": "somesh", "name": "Somesh"}),
            },
            seen,
        )
    )
    account = GitHubAppSignIn("Iv23li", "secret", http).account_for_code("code1", "https://m/cb")
    assert account == GitHubAccount(id=7, login="somesh", name="Somesh")
    assert "client_secret=secret" in seen[0].content.decode()
    assert seen[1].headers["Authorization"] == "Bearer ghu_x"


def test_a_rejected_github_code_is_a_clear_error() -> None:
    http = httpx.Client(
        transport=fake_github(
            {("POST", "/login/oauth/access_token"): (200, {"error": "bad_verification_code"})}, []
        )
    )
    with pytest.raises(GitHubError, match="didn't accept"):
        GitHubAppSignIn("Iv23li", "secret", http).account_for_code("old", "https://m/cb")


# Repo access adapter -------------------------------------------------------------------


def repo_access(routes: dict[tuple[str, str], tuple[int, Any]], seen: list[httpx.Request]):
    http = httpx.Client(base_url="https://api.github.com", transport=fake_github(routes, seen))
    return GitHubAppRepoAccess("5233457", PEM, http)


def test_installation_id_authenticates_as_the_app() -> None:
    seen: list[httpx.Request] = []
    access = repo_access({("GET", "/repos/acme/shop/installation"): (200, {"id": 169380149})}, seen)
    assert access.installation_id("acme/shop") == 169380149
    app_jwt = seen[0].headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(app_jwt, KEY.public_key(), algorithms=["RS256"])
    assert claims["iss"] == "5233457" and claims["exp"] - claims["iat"] <= 600


def test_no_installation_means_none() -> None:
    assert repo_access({}, []).installation_id("acme/other") is None


@pytest.mark.parametrize(("permission", "admin"), [("admin", True), ("write", False)])
def test_admin_check_reads_the_collaborator_permission(permission: str, admin: bool) -> None:
    seen: list[httpx.Request] = []
    access = repo_access(
        {
            ("GET", "/repos/acme/shop/installation"): (200, {"id": 9}),
            ("POST", "/app/installations/9/access_tokens"): (201, {"token": "ghs_inst"}),
            ("GET", "/repos/acme/shop/collaborators/somesh/permission"): (
                200,
                {"permission": permission},
            ),
        },
        seen,
    )
    assert access.is_admin("acme/shop", "somesh") is admin
    assert seen[-1].headers["Authorization"] == "Bearer ghs_inst"


def test_github_errors_are_reported_not_hidden() -> None:
    access = repo_access({("GET", "/repos/acme/shop/installation"): (500, {})}, [])
    with pytest.raises(GitHubError, match="500"):
        access.installation_id("acme/shop")


# The server's GitHub sign-in pages -----------------------------------------------------


class FakeGitHubSignIn:
    def authorize_url(self, state: str, redirect_uri: str) -> str:
        return f"https://github.example/login?state={state}&redirect_uri={redirect_uri}"

    def account_for_code(self, code: str, redirect_uri: str) -> GitHubAccount:
        assert code == "gh-code"
        return GitHubAccount(id=55, login="frederik")


def test_server_signs_in_through_github_and_returns_to_the_client() -> None:
    base = "http://127.0.0.1:8000"
    server = create_server(
        Settings(public_url=base),
        repos=FakeRepoAccess(),
        github_sign_in=FakeGitHubSignIn(),
    )
    with TestClient(server.app, base_url=base, follow_redirects=False) as http:
        client = http.post(
            "/register",
            json={
                "redirect_uris": ["http://127.0.0.1:9/cb"],
                "token_endpoint_auth_method": "none",
            },
        ).json()
        start = http.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": "http://127.0.0.1:9/cb",
                "code_challenge": "x" * 43,
                "code_challenge_method": "S256",
                "state": "s1",
            },
        )
        to_github = urlparse(start.headers["location"])
        assert to_github.netloc == "github.example"
        query = parse_qs(to_github.query)
        assert query["redirect_uri"] == [f"{base}/oauth/github/callback"]

        back = http.get(
            "/oauth/github/callback", params={"code": "gh-code", "state": query["state"][0]}
        )
        assert back.status_code == 302
        to_client = parse_qs(urlparse(back.headers["location"]).query)
        assert to_client["state"] == ["s1"] and to_client["code"]
        assert http.get("/oauth/dev-login").status_code == 404  # no dev login on a real server

        replay = http.get(
            "/oauth/github/callback", params={"code": "gh-code", "state": query["state"][0]}
        )
        assert replay.status_code == 400
    assert server.projects.user("u-55").github_login == "frederik"


def test_a_real_server_refuses_to_start_without_sign_in_configured() -> None:
    with pytest.raises(ValueError, match="Sign in with GitHub"):
        create_server(Settings(public_url="http://127.0.0.1:8000"), repos=FakeRepoAccess())


def test_settings_read_the_private_key_from_a_file(tmp_path: Any) -> None:
    key_file = tmp_path / "app.pem"
    key_file.write_text(PEM)
    settings = Settings.from_env(
        {
            "MIDFLIGHT_GITHUB_APP_ID": "5233457",
            "MIDFLIGHT_GITHUB_PRIVATE_KEY_PATH": str(key_file),
            "MIDFLIGHT_PUBLIC_URL": "https://example.test/",
        }
    )
    assert settings.github_app_configured and settings.public_url == "https://example.test"
    assert settings.github_private_key == PEM
