"""The operator can retry an ambiguous hosted response without creating another take."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "reset_flight", Path(__file__).parents[2] / "scripts/reset_flight.py"
)
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)


def test_lost_response_reuses_request_and_rotates_credentials(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    journal = tmp_path / "pending.json"
    reset.save_private(
        config,
        {
            "url": "https://example.invalid",
            "token": "old",
            "project_id": "old",
            "source_plan_version": 4,
        },
    )
    calls = []

    def api(cfg, path, payload=None):
        if path.endswith("/state"):
            return {"project": {"coord_rev": 7}}
        if path.endswith("/plans/current"):
            return {"project_id": "new", "version": 1}
        calls.append(payload)
        if len(calls) == 1:
            raise TimeoutError("response lost")
        return {"project": {"id": "new"}, "token": "new-secret"}

    monkeypatch.setattr(reset, "api", api)
    with pytest.raises(TimeoutError):
        reset.reset_hosted(config, journal)
    result = reset.reset_hosted(config, journal)
    assert calls[0] == calls[1]
    assert calls[1]["source_plan_version"] == 4
    assert result["project"]["id"] == "new"
    assert json.loads(config.read_text())["token"] == "new-secret"
    assert config.stat().st_mode & 0o777 == 0o600
    reset.reset_hosted(config, journal)
    assert len(calls) == 2
