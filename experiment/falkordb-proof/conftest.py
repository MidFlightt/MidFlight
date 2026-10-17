"""Start an isolated, digest-pinned database. Never target a user's existing server."""

from __future__ import annotations

import json
import socket
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from proof_store import ProofStore
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import ConnectionError, TimeoutError
from redis.retry import Retry

IMAGE = (
    "falkordb/falkordb:v4.22.1@"
    "sha256:b0bdcac2cbaff989e77cb0610439b7a9289e86de033ccbbd4368b66fb680ae7a"
)


def docker(*args):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


class Server:
    def __init__(self):
        self.name = "midflight-proof-" + uuid.uuid4().hex[:12]
        self.volume = self.name + "-data"
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]

    def client(self, graph_name):
        return ProofStore(self.port, graph_name)

    def wait_ready(self):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with Redis(
                    host="127.0.0.1",
                    port=self.port,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                    retry=Retry(NoBackoff(), 0),
                ) as client:
                    if client.ping():
                        return
            except (ConnectionError, TimeoutError):
                pass
            time.sleep(0.1)
        raise RuntimeError("database failed to start: " + docker("logs", self.name))

    def kill(self):
        docker("kill", "--signal", "KILL", self.name)

    def start(self):
        docker("start", self.name)
        self.wait_ready()

    def kill_and_restart(self):
        self.kill()
        self.start()

    @contextmanager
    def new_store(self):
        graph_name = "proof_" + uuid.uuid4().hex
        with self.client(graph_name) as store:
            store.initialize()
            try:
                yield store
            finally:
                store.graph.delete()


@pytest.fixture(scope="session")
def server(request):
    server = Server()
    docker("info", "--format", "{{.ServerVersion}}")
    docker("volume", "create", server.volume)
    try:
        docker(
            "run",
            "-d",
            "--name",
            server.name,
            "-p",
            f"127.0.0.1:{server.port}:6379",
            "--mount",
            f"source={server.volume},target=/data",
            "-e",
            'REDIS_ARGS=--appendonly yes --appendfsync always --save ""',
            "-e",
            "FALKORDB_ARGS=TIMEOUT 10000 MAX_QUEUED_QUERIES 100",
            IMAGE,
        )
        server.port = int(docker("port", server.name, "6379/tcp").rsplit(":", 1)[1])
        server.wait_ready()
        metadata = {
            "image": IMAGE,
            "image_id": docker("inspect", server.name, "--format", "{{.Image}}"),
            "architecture": docker("image", "inspect", IMAGE, "--format", "{{.Architecture}}"),
            "modules": docker("exec", server.name, "redis-cli", "--json", "MODULE", "LIST"),
            "persistence": docker(
                "exec",
                server.name,
                "redis-cli",
                "--json",
                "CONFIG",
                "GET",
                "appendonly",
                "appendfsync",
                "save",
            ),
        }
        metadata["modules"] = json.loads(metadata["modules"])
        metadata["persistence"] = json.loads(metadata["persistence"])
        assert metadata["persistence"] == {
            "appendonly": "yes",
            "appendfsync": "always",
            "save": "",
        }
        assert any(m["name"] == "graph" and m["ver"] == 42201 for m in metadata["modules"])
        output = request.config.getoption("proof_metadata")
        if output:
            Path(output).write_text(json.dumps(metadata, indent=2) + "\n")
        yield server
    finally:
        subprocess.run(["docker", "rm", "-f", server.name], capture_output=True, timeout=30)
        docker("volume", "rm", server.volume)


@pytest.fixture
def store(server):
    with server.new_store() as store:
        yield store


def pytest_addoption(parser):
    parser.addoption("--proof-metadata", default=None, help="Save tested image/config metadata")
