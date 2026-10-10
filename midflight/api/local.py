"""The API on a laptop: in-memory store, inline review jobs, the demo project seeded.

    uv run uvicorn midflight.api.local:create_local_app --factory --reload

Tokens for the demo lead and agents are kept in `.midflight/local-tokens.json`
(git-ignored), so they stay the same across restarts and the MCP config keeps working.
State itself is in memory and resets on every restart. Set MIDFLIGHT_SEED=none to start
empty, or MIDFLIGHT_TOKENS_FILE to keep tokens elsewhere.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI

from midflight import demo
from midflight.adapters.clock import SystemClock
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import build_services, create_app
from midflight.services.participants import new_token

TOKENS_FILE = Path(os.environ.get("MIDFLIGHT_TOKENS_FILE", ".midflight/local-tokens.json"))


def local_tokens(path: Path = TOKENS_FILE) -> dict[str, str]:
    """The saved demo tokens, creating any that are missing."""
    tokens: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    for participant_id, *_ in demo.PEOPLE:
        tokens.setdefault(participant_id, new_token())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, indent=2))
    return tokens


def create_local_app() -> FastAPI:
    clock = SystemClock()
    store = MemoryStore()
    if os.environ.get("MIDFLIGHT_SEED", "demo") == "demo":
        demo.seed(store, local_tokens(), clock.now())
        print(
            f"midflight: seeded the demo project; tokens are in {TOKENS_FILE}",
            file=sys.stderr,
        )
    return create_app(build_services(store, clock))
