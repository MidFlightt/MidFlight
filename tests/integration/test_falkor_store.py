"""GH-02: real-database races and persistence of the complete Store adapter."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from demo_fixture import NOW, PROJECT, make_claim, seed
from midflight.domain.models import AuditEvent, ClaimState, Job, JobKind, User
from midflight.ports import Commit, RevisionConflict


def bundle(key="bundle", expected=0):
    return Commit(
        project_id=PROJECT,
        idempotency_key=key,
        expected_coord_rev=expected,
        bump_coord_rev=True,
        puts=[
            make_claim(),
            Job(
                id="J-1",
                project_id=PROJECT,
                kind=JobKind.CLAIM_REVIEW,
                subject_id="C-T2",
                idempotency_key=key,
                correlation_id=key,
                created_at=NOW,
                updated_at=NOW,
            ),
        ],
        audit=[
            AuditEvent(
                id="A-1",
                project_id=PROJECT,
                actor="p-t2",
                action="submit",
                entity_ids=["C-T2"],
                reason="test",
                correlation_id=key,
                idempotency_key=key,
                timestamp=NOW,
            )
        ],
    )


def parallel(store, operation, count=8):
    barrier = Barrier(count)

    def call(i):
        barrier.wait()
        return operation(i)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(call, range(count)))


def test_concurrent_cas_writes_one_complete_bundle(falkor_store):
    seed(falkor_store)

    def write(i):
        try:
            return falkor_store.commit(bundle(str(i))).applied
        except RevisionConflict:
            return False

    assert sum(parallel(falkor_store, write)) == 1
    assert len(falkor_store.list_claims(PROJECT)) == 1
    assert len(falkor_store.list_jobs(PROJECT)) == 1
    assert len(falkor_store.list_audit(PROJECT)) == 1
    assert falkor_store.get_project(PROJECT).coord_rev == 1


def test_same_request_concurrently_and_after_lost_reply(falkor_store):
    seed(falkor_store)
    results = parallel(falkor_store, lambda _: falkor_store.commit(bundle()))
    assert sum(r.applied for r in results) == 1
    falkor_store.commit(Commit(PROJECT, "later", bump_coord_rev=True))
    assert falkor_store.commit(bundle()).coord_rev == 1
    assert len(falkor_store.list_audit(PROJECT)) == 1


def test_stale_review_changes_neither_verdict_nor_job(falkor_store):
    seed(falkor_store)
    falkor_store.commit(bundle())
    before = falkor_store.get_claim("C-T2")
    with pytest.raises(RevisionConflict):
        falkor_store.commit(
            replace(
                bundle("review"), puts=[before.model_copy(update={"state": ClaimState.APPROVED})]
            )
        )
    assert falkor_store.get_claim("C-T2") == before
    assert len(falkor_store.list_audit(PROJECT)) == 1


def test_history_guards_are_atomic_without_coord_revision(falkor_store):
    seed(falkor_store)

    def write(i):
        try:
            falkor_store.commit(Commit(PROJECT, str(i), puts=[make_claim(files=[f"{i}.py"])]))
            return True
        except ValueError:
            return False

    assert sum(parallel(falkor_store, write)) == 1
    assert len(falkor_store.claim_history("C-T2")) == 1


def test_restart_recovers_all_state_and_duplicate_receipts(falkor_store, falkor_server):
    from midflight.adapters.falkor_store import FalkorStore

    seed(falkor_store)
    falkor_store.commit(bundle())
    user = User(id="u1", github_id=42, github_login="test", created_at=NOW)
    falkor_store.save_user(user)
    falkor_store.put_auth("client", "c", {"nested": {"value": [1, True]}})
    assert falkor_store.next_id(PROJECT, "C") == "C-1"
    falkor_server.kill_and_restart()
    fresh = FalkorStore.connect(port=falkor_server.port, graph_name=falkor_store.graph.name)
    try:
        assert fresh.get_user("u1") == user
        assert fresh.get_auth("client", "c") == {"nested": {"value": [1, True]}}
        assert fresh.next_id(PROJECT, "C") == "C-2"
        assert fresh.commit(bundle()).duplicate
        assert fresh.get_plan(PROJECT, 1) is not None
        assert fresh.get_participant("p-t1") is not None
        assert len(fresh.list_jobs(PROJECT)) == len(fresh.list_audit(PROJECT)) == 1
    finally:
        fresh.close()


def test_global_ids_under_contention(falkor_store):
    ids = parallel(falkor_store, lambda i: falkor_store.next_id(str(i), "C"))
    assert len(set(ids)) == 8


def test_audit_owner_and_duplicate_entities_are_rejected_atomically(falkor_store):
    seed(falkor_store)
    write = bundle()
    with pytest.raises(ValueError):
        falkor_store.commit(
            replace(write, audit=[write.audit[0].model_copy(update={"project_id": "other"})])
        )
    with pytest.raises(ValueError):
        falkor_store.commit(replace(write, puts=[make_claim(), make_claim(files=["changed"])]))
    assert not falkor_store.list_claims(PROJECT)
    assert not falkor_store.list_jobs(PROJECT)
    assert not falkor_store.list_audit(PROJECT)


def test_commit_retry_after_transport_loses_success_response(falkor_store, monkeypatch):
    from redis.exceptions import TimeoutError

    seed(falkor_store)
    query = falkor_store._query

    def lose_reply(*args, **kwargs):
        query(*args, **kwargs)
        raise TimeoutError("simulated lost response after durable write")

    with monkeypatch.context() as patch:
        patch.setattr(falkor_store, "_query", lose_reply)
        with pytest.raises(TimeoutError):
            falkor_store.commit(bundle())
    assert falkor_store.commit(bundle()).duplicate
    assert falkor_store.get_project(PROJECT).coord_rev == 1
    assert len(falkor_store.list_audit(PROJECT)) == 1


def test_engine_error_rolls_back_all_mutations(falkor_store, monkeypatch):
    from redis.exceptions import ResponseError

    seed(falkor_store)
    query = falkor_store._query

    def invalid_property(text, params):
        # Inject an invalid property after all entity/audit/receipt mutation clauses.
        text = text.replace(") RETURN outcome", "SET target.invalid = $invalid ) RETURN outcome")
        return query(text, {**params, "invalid": {"unsupported": "map"}})

    with monkeypatch.context() as patch:
        patch.setattr(falkor_store, "_query", invalid_property)
        with pytest.raises(ResponseError):
            falkor_store.commit(bundle())
    assert falkor_store.get_project(PROJECT).coord_rev == 0
    assert falkor_store.list_jobs(PROJECT) == falkor_store.list_claims(PROJECT) == []
    assert falkor_store.list_audit(PROJECT) == []
    assert falkor_store.commit(bundle()).applied


def test_other_project_cannot_reuse_identity_or_receipt(falkor_store):
    seed(falkor_store)
    falkor_store.commit(bundle())
    other = falkor_store.get_project(PROJECT).model_copy(update={"id": "other", "coord_rev": 0})
    falkor_store.commit(Commit("other", "new-project", puts=[other]))
    with pytest.raises(ValueError, match="belongs to"):
        falkor_store.commit(
            Commit("other", "steal", puts=[make_claim(project_id="other", revision=2)])
        )
    with pytest.raises(ValueError, match="belongs to"):
        falkor_store.commit(Commit("other", "bundle", bump_coord_rev=True))
    assert falkor_store.get_project("other").coord_rev == 0
    assert not falkor_store.list_claims("other")
    assert falkor_store.get_claim("C-T2").project_id == PROJECT


def test_unknown_project_leaves_no_shell_or_receipt(falkor_store):
    with pytest.raises(LookupError):
        falkor_store.commit(bundle())
    assert falkor_store.get_project(PROJECT) is None
    seed(falkor_store)
    assert falkor_store.commit(bundle()).applied


def test_dead_database_does_not_look_like_empty_results(falkor_store, falkor_server):
    from redis.exceptions import ConnectionError

    seed(falkor_store)
    falkor_server.kill()
    try:
        with pytest.raises(ConnectionError):
            falkor_store.list_jobs(PROJECT)
        with pytest.raises(ConnectionError):
            falkor_store.commit(bundle())
    finally:
        falkor_server.start()


def test_readback_lookups_filters_and_missing_records(falkor_store):
    from midflight.domain.models import Escalation

    seed(falkor_store)
    falkor_store.commit(bundle())
    escalation = Escalation(
        id="E-1", project_id=PROJECT, claim_ids=["C-T2"], explanation="test", created_at=NOW
    )
    falkor_store.commit(Commit(PROJECT, "escalate", puts=[escalation]))
    assert falkor_store.get_escalation("E-1") == escalation
    assert falkor_store.list_escalations(PROJECT) == [escalation]
    assert len(falkor_store.list_participants(PROJECT)) > 0
    assert falkor_store.get_job("J-1") == bundle().puts[1]
    assert len(falkor_store.list_audit(PROJECT, "C-T2")) == 1
    assert not falkor_store.list_audit(PROJECT, "unrelated")
    for method in (
        "get_project",
        "get_participant",
        "get_claim",
        "get_directive",
        "get_escalation",
        "get_verification",
        "get_job",
        "get_user",
    ):
        assert getattr(falkor_store, method)("absent") is None
    assert falkor_store.get_plan(PROJECT, 99) is None
    assert falkor_store.get_claim("C-T2", 99) is None
    assert not falkor_store.list_claims("other")
    assert not falkor_store.list_directives("other")
    assert not falkor_store.list_escalations("other")
    assert not falkor_store.list_verifications("other")
    assert not falkor_store.list_participants("other")
    assert not falkor_store.list_plans("other")
    assert not falkor_store.list_jobs("other")
    assert falkor_store.get_auth("client", "absent") is None
    falkor_store.delete_auth("client", "absent")


def test_concurrent_project_creation_has_one_cas_winner(falkor_store):
    from midflight.domain.models import Project

    def write(i):
        try:
            return falkor_store.commit(
                Commit(
                    PROJECT,
                    f"create-{i}",
                    puts=[Project(id=PROJECT, repository="team/repo", lead_id="lead")],
                    expected_coord_rev=0,
                    bump_coord_rev=True,
                )
            ).applied
        except RevisionConflict:
            return False

    assert sum(parallel(falkor_store, write)) == 1
    assert falkor_store.get_project(PROJECT).coord_rev == 1


def test_competing_approved_plans_cannot_overwrite_history(falkor_store):
    from demo_fixture import make_plan

    seed(falkor_store)

    def write(i):
        try:
            falkor_store.commit(
                Commit(
                    PROJECT,
                    f"approve-{i}",
                    puts=[make_plan(2).model_copy(update={"change_reason": f"approval {i}"})],
                )
            )
            return True
        except ValueError:
            return False

    assert sum(parallel(falkor_store, write)) == 1
    assert len(falkor_store.list_plans(PROJECT)) == 2
