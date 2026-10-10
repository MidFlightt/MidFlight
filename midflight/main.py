"""The Midflight server: one web app with the REST API, the hosted MCP connector, and
Sign in with GitHub. This is where everything is wired together.

Run it locally:

    uv run midflight-server

It reads settings from the environment or a `.env` file (see `midflight/config.py`).
With `MIDFLIGHT_DEV_LOGIN=1` it needs no GitHub secrets: sign-in is a local form and
every repository counts as having the App installed. Data lives in memory and resets
when the server stops; the AWS deploy (H-5) swaps in DynamoDB. `MIDFLIGHT_SEED_DEMO=1`
also loads the demo project with tokens for the local stdio adapter.

What answers where:

| Path | What |
| --- | --- |
| `/mcp` | The hosted MCP connector (needs sign-in) |
| `/authorize`, `/token`, `/register`, `/.well-known/...` | Sign-in protocol (MCP SDK) |
| `/oauth/github/callback`, `/oauth/dev-login` | Sign-in pages a browser visits |
| `/projects/...`, `/claims/...`, `/jobs/...`, ... | REST API for scripts and hooks |
| `/github/webhook` | GitHub tells Midflight a contract-test run finished |
| `/docs` | REST API reference |
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import FastAPI
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings

from midflight import demo
from midflight.adapters.clock import SystemClock
from midflight.adapters.fake_github import AnyRepoAccess
from midflight.adapters.github import GitHubAppRepoAccess, GitHubAppSignIn
from midflight.adapters.runners import StreamRunner
from midflight.api.app import Services, build_services, create_app
from midflight.api.oauth import MidflightOAuth, add_sign_in_routes
from midflight.config import Settings, load_dotenv
from midflight.mcp.hosted import build_hosted_server
from midflight.ports import Clock, GitHub, GitHubSignIn, RepoAccess, Reviewer, Store
from midflight.services.projects import ProjectService
from midflight.wiring import github_for, reviewer_for, store_for


@dataclass(frozen=True)
class Server:
    app: FastAPI
    services: Services
    projects: ProjectService
    oauth: MidflightOAuth


def create_server(
    settings: Settings,
    *,
    store: Store | None = None,
    clock: Clock | None = None,
    repos: RepoAccess | None = None,
    github_sign_in: GitHubSignIn | None = None,
    reviewer: Reviewer | None = None,
    github: GitHub | None = None,
) -> Server:
    """Build the whole server. Tests pass their own store, clock, and GitHub fakes."""
    store = store or store_for(settings)
    clock = clock or SystemClock()
    repos = repos or _repo_access(settings)
    github_sign_in = github_sign_in or _github_sign_in(settings)
    reviewer = reviewer or reviewer_for(settings)
    github = github or github_for(settings)

    runner = StreamRunner() if settings.table_name else None
    services = build_services(store, clock, reviewer, runner, github)
    projects = ProjectService(store, clock, repos, services.plans)
    oauth = MidflightOAuth(store, projects, settings.public_url, github_sign_in, settings.dev_login)

    auth = AuthSettings(
        issuer_url=settings.public_url,
        resource_server_url=f"{settings.public_url}/mcp",
        validate_token_resource=True,  # refuse tokens issued for any other server
        client_registration_options=ClientRegistrationOptions(enabled=True),
        revocation_options=RevocationOptions(enabled=True),
    )
    mcp = build_hosted_server(
        services, projects, auth=auth, oauth=oauth, public_url=settings.public_url
    )
    add_sign_in_routes(mcp, oauth, github_sign_in)
    # Stateless JSON responses: any server instance (or Lambda) can answer any request.
    mcp_app = mcp.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=_allowed_hosts(settings)
    )

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    if settings.seed_demo:
        demo.seed(store, demo.local_tokens(), clock.now())

    app = create_app(services, lifespan=lifespan, webhook_secret=settings.github_webhook_secret)
    app.mount("/", mcp_app)  # the REST routes match first; everything else is MCP and sign-in
    return Server(app, services, projects, oauth)


def _repo_access(settings: Settings) -> RepoAccess:
    if settings.github_app_configured:
        assert settings.github_app_id and settings.github_private_key
        return GitHubAppRepoAccess(settings.github_app_id, settings.github_private_key)
    if settings.dev_login:
        return AnyRepoAccess()
    raise ValueError(
        "set MIDFLIGHT_GITHUB_APP_ID and a private key, or MIDFLIGHT_DEV_LOGIN=1 for local use"
    )


def _github_sign_in(settings: Settings) -> GitHubSignIn | None:
    if settings.github_sign_in_configured:
        assert settings.github_client_id and settings.github_client_secret
        return GitHubAppSignIn(settings.github_client_id, settings.github_client_secret)
    return None  # only valid with the dev login; MidflightOAuth checks


def _allowed_hosts(settings: Settings) -> TransportSecuritySettings:
    """Only answer requests addressed to our own host (protects against DNS rebinding)."""
    url = urlparse(settings.public_url)
    if url.hostname in ("127.0.0.1", "localhost"):
        hosts = ["127.0.0.1:*", "localhost:*", "127.0.0.1", "localhost"]
        origins = ["http://127.0.0.1:*", "http://localhost:*"]
    else:
        hosts = [url.netloc]
        origins = [f"{url.scheme}://{url.netloc}"]
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


def create_app_from_env() -> FastAPI:
    load_dotenv()
    return create_server(Settings.from_env()).app


def run() -> None:
    """`uv run midflight-server`: serve on the port in MIDFLIGHT_PUBLIC_URL (default 8000)."""
    import uvicorn

    load_dotenv()
    port = urlparse(Settings.from_env().public_url).port or 8000
    uvicorn.run("midflight.main:create_app_from_env", factory=True, host="127.0.0.1", port=port)
