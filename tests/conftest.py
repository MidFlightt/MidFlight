"""Pytest fixtures for the demo project. The factories live in demo_fixture.py."""

import pytest

from demo_fixture import make_plan
from midflight.domain.models import Plan


@pytest.fixture
def plan_v1() -> Plan:
    return make_plan(1)


@pytest.fixture
def plan_v2() -> Plan:
    return make_plan(2)
