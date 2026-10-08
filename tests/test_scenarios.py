"""S-4: every YAML scenario in tests/scenarios/ plays through and gets the expected answers."""

from __future__ import annotations

from pathlib import Path

import pytest
from scenario_runner import Play, all_scenarios, load


@pytest.mark.parametrize("path", all_scenarios(), ids=lambda p: p.stem)
def test_scenario(path: Path) -> None:
    Play(load(path)).run()
