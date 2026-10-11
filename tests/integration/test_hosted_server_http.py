"""H-2 and H-3 end to end: the real server over HTTP, signing in like an AI client does.

Starts `midflight.main` on a free port with the dev login (so no GitHub secrets are
needed) and does what Claude or ChatGPT does when you add the connector: register,
open the sign-in page, trade the code for a token, then call the MCP tools with it.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from midflight.config import Settings
from midflight.main import create_server

pytestmark = pytest.mark.anyio

REDIRECT = "http://127.0.0.1:9/callback"  # the client's own page; never actually opened


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    app = create_server(Settings(public_url=url, dev_login=True)).app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < deadline, "server didn't start"
        time.sleep(0.05)
    yield url
    server.should_exit = True
    thread.join(timeout=10)


def sign_in(base_url: str, login: str) -> dict[str, Any]:
    """Everything an AI client does to get a Midflight token, with `login` signing in."""
    http = httpx.Client(base_url=base_url, follow_redirects=False)
    client = http.post(
        "/register",
        json={
            "client_name": "test client",
            "redirect_uris": [REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert client.status_code == 201, client.text
    client_id = client.json()["client_id"]

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    start = http.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_challenge": challenge.decode(),
            "code_challenge_method": "S256",
            "state": "abc",
        },
    )
    assert start.status_code == 302, start.text
    login_page = urlparse(start.headers["location"])
    assert login_page.path == "/oauth/dev-login"

    pending = parse_qs(login_page.query)["pending"][0]
    done = http.post("/oauth/dev-login", data={"pending": pending, "login": login})
    assert done.status_code == 302, done.text
    back = urlparse(done.headers["location"])
    assert f"{back.scheme}://{back.netloc}{back.path}" == REDIRECT
    params = parse_qs(back.query)
    assert params["state"] == ["abc"]

    tokens = http.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": params["code"][0],
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert tokens.status_code == 200, tokens.text
    return tokens.json() | {"client_id": client_id, "code": params["code"][0], "verifier": verifier}


async def call(base_url: str, token: str, tool: str, **args: Any) -> str:
    http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30)
    async with Client(streamable_http_client(f"{base_url}/mcp", http_client=http)) as client:
        result = await client.call_tool(tool, args)
    assert not result.is_error, result.content
    return result.content[0].text  # type: ignore[union-attr]


def test_mcp_without_a_token_points_to_sign_in(base_url: str) -> None:
    response = httpx.post(f"{base_url}/mcp", json={})
    assert response.status_code == 401
    assert "resource_metadata" in response.headers["www-authenticate"]
    discovery = httpx.get(f"{base_url}/.well-known/oauth-authorization-server").json()
    assert discovery["authorization_endpoint"] == f"{base_url}/authorize"
    assert discovery["registration_endpoint"] == f"{base_url}/register"


async def test_two_people_sign_in_create_and_join_over_http(base_url: str) -> None:
    lead = sign_in(base_url, "somesh")
    created = await call(base_url, lead["access_token"], "create_project", repository="acme/http")
    code = re.search(r"Join code: (MF-\S+)", created).group(1)  # type: ignore[union-attr]

    teammate = sign_in(base_url, "frederik")
    joined = await call(base_url, teammate["access_token"], "join_project", join_code=code)
    assert "Lead: somesh" in joined
    mine = await call(base_url, teammate["access_token"], "my_projects")
    assert "acme/http" in mine and "you are agent" in mine


def test_a_code_works_once_and_refresh_rotates(base_url: str) -> None:
    person = sign_in(base_url, "mithilesh")
    reuse = httpx.post(
        f"{base_url}/token",
        data={
            "grant_type": "authorization_code",
            "code": person["code"],
            "redirect_uri": REDIRECT,
            "client_id": person["client_id"],
            "code_verifier": person["verifier"],
        },
    )
    assert reuse.status_code == 400

    refreshed = httpx.post(
        f"{base_url}/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": person["refresh_token"],
            "client_id": person["client_id"],
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["access_token"] != person["access_token"]
    again = httpx.post(
        f"{base_url}/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": person["refresh_token"],
            "client_id": person["client_id"],
        },
    )
    assert again.status_code == 400


def test_a_made_up_token_is_refused(base_url: str) -> None:
    response = httpx.post(
        f"{base_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Authorization": "Bearer not-a-real-token", "Accept": "application/json"},
    )
    assert response.status_code == 401


def test_the_connector_offers_no_event_stream(base_url: str) -> None:
    """A signed-in GET asks for a stream of server events. This server answers each
    request by itself and has no such stream, so it must say so at once: on AWS an open
    stream holds a whole Lambda until it times out, and a few of them lock everyone out."""
    token = sign_in(base_url, "somesh")["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    response = httpx.get(f"{base_url}/mcp", headers=headers, timeout=5)
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    # Without a token the answer is still "sign in first", so clients can find out how.
    assert httpx.get(f"{base_url}/mcp", timeout=5).status_code == 401
