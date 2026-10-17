"""Real database tests. Docker lifecycle is owned exclusively by this test session."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pytest
from proof_store import IdempotencyConflict, RevisionConflict
from redis.exceptions import ConnectionError, ResponseError, TimeoutError


def test_claim_job_audit_receipt_and_revision_are_one_commit(store):
    result = store.submit("submit-1", expected=0, payload="currency work")
    assert asdict(result) == {"revision": 1, "duplicate": False}
    assert store.snapshot() == {
        "revision": 1,
        "plan_version": 1,
        "claims": [["submit-1", "pending", "currency work"]],
        "jobs": [["submit-1", "pending", "submit-1"]],
        "receipts": [["submit-1", 1]],
        "audits": [["submit-1", "submit"]],
    }


@pytest.mark.parametrize("round_number", range(10))
def test_concurrent_compare_and_set_has_exactly_one_winner(store, server, round_number):
    barrier = threading.Barrier(8)

    def attempt(i):
        with server.client(store.graph_name) as client:
            barrier.wait(timeout=10)
            try:
                client.submit(f"r{round_number}-{i}", expected=0)
                return "applied"
            except RevisionConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert outcomes.count("applied") == 1
    assert outcomes.count("conflict") == 7
    state = store.snapshot()
    assert state["revision"] == 1
    assert len(state["claims"]) == len(state["jobs"]) == len(state["receipts"]) == 1
    assert len(state["audits"]) == 1


def test_four_writers_retry_conflicts_without_losing_updates(store, server):
    barrier = threading.Barrier(4)

    def writer(i):
        with server.client(store.graph_name) as client:
            barrier.wait(timeout=10)
            for n in range(12):
                for _ in range(200):
                    try:
                        client.submit(f"{i}-{n}", expected=client.revision())
                        break
                    except RevisionConflict:
                        continue
                else:
                    pytest.fail("writer exhausted its bounded retry budget")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(writer, range(4)))
    state = store.snapshot()
    assert state["revision"] == 48
    assert len(state["claims"]) == len(state["jobs"]) == len(state["receipts"]) == 48
    assert len(state["audits"]) == 48


def test_concurrent_duplicate_requests_apply_once(store, server):
    barrier = threading.Barrier(8)

    def attempt(_):
        with server.client(store.graph_name) as client:
            barrier.wait(timeout=10)
            return client.submit("same-request", expected=0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert sum(not result.duplicate for result in outcomes) == 1
    assert {result.revision for result in outcomes} == {1}
    assert len(store.snapshot()["audits"]) == 1


def test_lost_reply_retry_returns_original_result_even_after_later_writes(store, monkeypatch):
    original = store.graph.query

    def drop_reply(query, params=None):
        original(query, params)
        raise ConnectionError("simulated loss of reply after server committed")

    with monkeypatch.context() as patch:
        patch.setattr(store.graph, "query", drop_reply)
        with pytest.raises(ConnectionError, match="loss of reply"):
            store.submit("lost-reply", expected=0)
    store.change_plan("later-change", expected=1)
    result = store.submit("lost-reply", expected=0)
    assert result.duplicate and result.revision == 1
    assert store.revision() == 2
    assert len(store.snapshot()["claims"]) == 1


def test_same_key_with_different_payload_is_rejected(store):
    store.submit("same", expected=0, payload="cents")
    before = store.snapshot()
    with pytest.raises(IdempotencyConflict):
        store.submit("same", expected=0, payload="dollars")
    assert store.snapshot() == before


def test_stale_review_writes_nothing_then_fresh_review_completes_once(store):
    store.submit("claim", expected=0)
    reviewed_revision = store.revision()
    store.change_plan("change", expected=reviewed_revision)
    before = store.snapshot()
    with pytest.raises(RevisionConflict):
        store.complete_review("stale-review", "claim", expected=reviewed_revision)
    assert store.snapshot() == before
    assert store.pending_jobs() == ["claim"]
    result = store.complete_review("fresh-review", "claim", expected=store.revision())
    assert result.revision == 3
    assert store.pending_jobs() == []
    assert store.complete_review("fresh-review", "claim", expected=2).duplicate
    assert store.snapshot()["claims"][0][1] == "approved"


def test_runtime_failure_rolls_back_mutations_and_retry_marker(store, monkeypatch):
    """Inject a runtime type error after writes, not a pre-execution syntax error."""
    original = store.graph.query

    def fail_after_mutation(query, params=None):
        query = query.replace(
            "RETURN p.coord_rev",
            "WITH p SET p.invalid_property = $invalid_property RETURN p.coord_rev",
        )
        return original(query, dict(params or {}, invalid_property={"nested": "map"}))

    before = store.snapshot()
    with monkeypatch.context() as patch:
        patch.setattr(store.graph, "query", fail_after_mutation)
        with pytest.raises(ResponseError, match="Property values can only be"):
            store.submit("rollback", expected=0)
    assert store.snapshot() == before
    assert not store.submit("rollback", expected=0).duplicate


def test_readers_never_observe_a_partial_bundle(store, server):
    started = threading.Event()
    finished = threading.Event()

    def writer():
        try:
            with server.client(store.graph_name) as client:
                started.set()
                for i in range(60):
                    client.submit(f"visible-{i}", expected=i)
        finally:
            finished.set()

    observations = 0
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        assert started.wait(10)
        while not finished.is_set():
            state = store.snapshot()  # one read query, not multiple independent reads
            count = state["revision"]
            assert all(len(state[k]) == count for k in ("claims", "jobs", "receipts", "audits"))
            observations += 1
        future.result(timeout=20)
    assert observations > 0
    assert store.revision() == 60


def test_fresh_python_process_recovers_pending_job(store, server):
    store.submit("recover", expected=0)
    code = """
import json,sys
from proof_store import ProofStore
with ProofStore(int(sys.argv[1]), sys.argv[2]) as s:
    before=s.snapshot()
    pending=s.pending_jobs()
    s.complete_review('recovered-review',pending[0],expected=s.revision())
    print(json.dumps({'before':before,'pending':pending,'after':s.snapshot()}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(server.port), store.graph_name],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    evidence = json.loads(result.stdout)
    assert evidence["pending"] == ["recover"]
    assert evidence["before"]["claims"][0][1] == "pending"
    assert evidence["after"]["claims"][0][1] == "approved"
    assert store.pending_jobs() == []


def test_killed_database_recovers_acknowledged_commit_and_pending_job(store, server):
    store.submit("durable", expected=0)
    before = store.snapshot()
    server.kill_and_restart()
    with server.client(store.graph_name) as recovered:
        assert recovered.snapshot() == before
        assert recovered.submit("durable", expected=0).duplicate
        assert recovered.pending_jobs() == ["durable"]
        recovered.complete_review("finish", "durable", expected=1)
        assert recovered.pending_jobs() == []


def test_crash_during_writes_recovers_whole_commits_and_allows_safe_retry(store, server):
    """Kill during a stream of writes; distinguish acknowledged and unknown outcomes."""
    first_ack = threading.Event()
    stop = threading.Event()
    acknowledged = []
    attempted = []

    def writer():
        with server.client(store.graph_name) as client:
            for i in range(2000):
                if stop.is_set():
                    break
                key = f"crash-{i}"
                attempted.append((key, i))
                try:
                    client.submit(key, expected=i)
                    acknowledged.append(key)
                    first_ack.set()
                except (ConnectionError, TimeoutError):
                    break

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        assert first_ack.wait(10)
        server.kill()
        stop.set()
        future.result(timeout=20)
    server.start()
    assert 0 < len(acknowledged) < 2000  # the kill interrupted an active workload
    with server.client(store.graph_name) as recovered:
        state = recovered.snapshot()
        keys = {row[0] for row in state["receipts"]}
        assert set(acknowledged) <= keys
        assert keys == {row[0] for row in state["claims"]}
        assert keys == {row[0] for row in state["jobs"]}
        assert keys == {row[0] for row in state["audits"]}
        assert state["revision"] == len(keys)
        for key, expected in attempted:
            result = recovered.submit(key, expected=expected)
            assert result.duplicate == (key in keys)
        assert recovered.revision() == len(attempted)


def test_graphs_are_isolated_even_with_identical_project_and_request_ids(store, server):
    with server.new_store() as other:
        store.submit("same", expected=0, payload="first")
        other.submit("same", expected=0, payload="second")
        store.change_plan("only-first", expected=1)
        assert other.revision() == 1
        assert other.snapshot()["claims"] == [["same", "pending", "second"]]


def test_graph_unavailable_is_an_error_not_empty_context(store, server):
    server.kill()
    try:
        with pytest.raises((ConnectionError, TimeoutError)):
            store.pending_jobs()
    finally:
        server.start()
