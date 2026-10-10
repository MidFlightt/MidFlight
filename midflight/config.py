"""Settings for the Midflight server, read from environment variables.

Locally, put them in a `.env` file in the repository root (git-ignored); see
`.env.example`. On AWS, the deploy sets them (H-5).

| Variable | Meaning |
| --- | --- |
| `MIDFLIGHT_PUBLIC_URL` | Where people reach the server; locally `http://127.0.0.1:8000`. |
| `MIDFLIGHT_DEV_LOGIN` | `1` replaces Sign in with GitHub with a local form. Never on AWS. |
| `MIDFLIGHT_SEED_DEMO` | `1` loads the demo project for the local stdio adapter. |
| `MIDFLIGHT_GITHUB_CLIENT_ID` | The GitHub App's client id (sign-in). |
| `MIDFLIGHT_GITHUB_CLIENT_SECRET` | The GitHub App's client secret (sign-in). Secret. |
| `MIDFLIGHT_GITHUB_APP_ID` | The GitHub App's id (repo checks). |
| `MIDFLIGHT_GITHUB_PRIVATE_KEY_PATH` | Path to the App's `.pem` private key. Secret. |
| `MIDFLIGHT_GITHUB_PRIVATE_KEY` | The key itself, instead of a path. Secret. |
| `MIDFLIGHT_TABLE` | DynamoDB table name. Unset means an in-memory store. |
| `MIDFLIGHT_SECRET_ID` | Secrets Manager secret holding the secrets above, as JSON (AWS). |
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    public_url: str = "http://127.0.0.1:8000"
    dev_login: bool = False
    seed_demo: bool = False
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_app_id: str | None = None
    github_private_key: str | None = None
    table_name: str | None = None

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        read_secret: Callable[[str], dict[str, str]] | None = None,
    ) -> Settings:
        env = dict(os.environ if env is None else env)
        if env.get("MIDFLIGHT_SECRET_ID"):
            # On AWS the secrets live in Secrets Manager, not in environment variables.
            secret = (read_secret or _read_secret)(env["MIDFLIGHT_SECRET_ID"])
            for name, value in secret.items():
                if value and value != "REPLACE_ME":
                    env.setdefault(f"MIDFLIGHT_{name.upper()}", value)
        key = env.get("MIDFLIGHT_GITHUB_PRIVATE_KEY")
        key_path = env.get("MIDFLIGHT_GITHUB_PRIVATE_KEY_PATH")
        if not key and key_path:
            key = Path(key_path).expanduser().read_text()
        return cls(
            public_url=(env.get("MIDFLIGHT_PUBLIC_URL") or cls.public_url).rstrip("/"),
            dev_login=env.get("MIDFLIGHT_DEV_LOGIN", "") == "1",
            seed_demo=env.get("MIDFLIGHT_SEED_DEMO", "") == "1",
            github_client_id=env.get("MIDFLIGHT_GITHUB_CLIENT_ID") or None,
            github_client_secret=env.get("MIDFLIGHT_GITHUB_CLIENT_SECRET") or None,
            github_app_id=env.get("MIDFLIGHT_GITHUB_APP_ID") or None,
            github_private_key=key or None,
            table_name=env.get("MIDFLIGHT_TABLE") or None,
        )

    @property
    def github_sign_in_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def github_app_configured(self) -> bool:
        return bool(self.github_app_id and self.github_private_key)


def load_dotenv(path: Path = Path(".env")) -> None:
    """Copy `KEY=value` lines from a .env file into the environment, without overriding."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _read_secret(secret_id: str) -> dict[str, str]:
    import boto3

    value = boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)["SecretString"]
    return json.loads(value)
