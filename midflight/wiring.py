"""Which real adapter to use for each port, from the settings.

Shared by the web server (`midflight.main`) and the worker Lambda (`midflight.aws.worker`)
so both build the same thing:

| Port | Configured | Not configured |
| --- | --- | --- |
| Store | DynamoDB (`MIDFLIGHT_TABLE`) | in memory |
| Reviewer | Bedrock (`MIDFLIGHT_REVIEWER_MODEL`), maybe via another account | rules only |
| GitHub | the GitHub App (App id and private key) | none: verification can't run |
"""

from __future__ import annotations

from midflight.adapters.bedrock import BedrockReviewer
from midflight.adapters.dynamo_store import DynamoStore
from midflight.adapters.github import GitHubAppClient
from midflight.adapters.memory_store import MemoryStore
from midflight.config import Settings
from midflight.ports import GitHub, Reviewer, Store


def store_for(settings: Settings) -> Store:
    return DynamoStore(settings.table_name) if settings.table_name else MemoryStore()


def reviewer_for(settings: Settings) -> Reviewer | None:
    if not settings.reviewer_model:
        return None
    return BedrockReviewer(settings.reviewer_model, role_arn=settings.reviewer_role_arn)


def github_for(settings: Settings) -> GitHub | None:
    if not settings.github_app_configured:
        return None
    assert settings.github_app_id and settings.github_private_key
    return GitHubAppClient(settings.github_app_id, settings.github_private_key)
