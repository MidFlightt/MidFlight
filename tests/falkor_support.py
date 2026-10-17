"""Opt-in real database fixtures, reusing GH-01's isolated pinned server harness."""

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--falkordb", action="store_true", help="Run isolated Docker store tests")


@pytest.fixture(scope="session")
def falkor_server(request):
    if not request.config.getoption("--falkordb"):
        pytest.skip("real FalkorDB tests require --falkordb")
    # Load only the unchanged GH-01 harness; never connect to an existing database.
    directory = Path(__file__).resolve().parents[1] / "experiment/falkordb-proof"
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location(
            "falkor_proof_harness", directory / "conftest.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(directory))

    # The harness's metadata option is intentionally disabled here.
    class Config:
        def getoption(self, name):
            return None

    class Request:
        config = Config()

    yield from module.server.__wrapped__(Request())


@pytest.fixture
def falkor_store(falkor_server):
    from midflight.adapters.falkor_store import FalkorStore

    store = FalkorStore.connect(port=falkor_server.port, graph_name="adapter_" + uuid.uuid4().hex)
    try:
        yield store
    finally:
        store.graph.delete()
        store.close()
