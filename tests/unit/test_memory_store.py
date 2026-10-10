"""MemoryStore: atomic commits, compare-and-set, idempotency, and history protection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from demo_fixture import PROJECT, make_claim, make_plan, seed
from midflight.adapters.memory_store import MemoryStore
from midflight.domain.models import ClaimState, PlanStatus, SyncState
from midflight.ports import Commit, RevisionConflict


@pytest.fixture
def store() -> MemoryStore:
    s = MemoryStore()
    seed(s)
    return s


def rev(store: MemoryStore) -> int:
    project = store.get_project(PROJECT)
    assert project is not None
    return project.coord_rev


def test_bump_advances_coord_rev(store: MemoryStore) -> None:
    before = rev(store)
    result = store.commit(
        Commit(project_id=PROJECT, idempotency_key="a", puts=[make_claim()], bump_coord_rev=True)
    )
    assert result.applied and result.coord_rev == before + 1 == rev(store)


def test_inv_02_stale_compare_and_set_writes_nothing(store: MemoryStore) -> None:
    with pytest.raises(RevisionConflict):
        store.commit(
            Commit(
                project_id=PROJECT,
                idempotency_key="b",
                puts=[make_claim()],
                expected_coord_rev=rev(store) + 5,
            )
        )
    assert store.list_claims(PROJECT) == []


def test_repeated_idempotency_key_writes_once(store: MemoryStore) -> None:
    commit = Commit(
        project_id=PROJECT, idempotency_key="c", puts=[make_claim()], bump_coord_rev=True
    )
    store.commit(commit)
    again = store.commit(commit)
    assert again.duplicate and not again.applied
    assert rev(store) == 1


def test_a_bad_entity_fails_the_whole_commit(store: MemoryStore) -> None:
    edited = make_claim(files=["somewhere/else.py"])
    store.commit(Commit(project_id=PROJECT, idempotency_key="d", puts=[make_claim()]))
    with pytest.raises(ValueError, match="new revision"):
        store.commit(
            Commit(project_id=PROJECT, idempotency_key="e", puts=[make_claim("T1"), edited])
        )
    assert [c.task_id for c in store.list_claims(PROJECT)] == ["T2"]


def test_a_saved_revision_can_change_only_its_verdict(store: MemoryStore) -> None:
    store.commit(Commit(project_id=PROJECT, idempotency_key="f", puts=[make_claim()]))
    approved = make_claim(state=ClaimState.APPROVED)
    store.commit(Commit(project_id=PROJECT, idempotency_key="g", puts=[approved]))
    assert store.get_claim("C-T2").state is ClaimState.APPROVED  # type: ignore[union-attr]


def test_an_approved_plan_cannot_change(store: MemoryStore) -> None:
    changed = make_plan(1).model_copy(update={"change_reason": "rewritten"})
    with pytest.raises(ValueError, match="approved"):
        store.commit(Commit(project_id=PROJECT, idempotency_key="h", puts=[changed]))


def test_saving_a_project_never_rolls_back_coord_rev(store: MemoryStore) -> None:
    old = store.get_project(PROJECT)
    store.commit(Commit(project_id=PROJECT, idempotency_key="i", bump_coord_rev=True))
    assert old is not None
    stale = old.model_copy(update={"sync_state": SyncState.STALE, "sync_reason": "test"})
    store.commit(Commit(project_id=PROJECT, idempotency_key="j", puts=[stale]))
    assert rev(store) == 1


@pytest.mark.filterwarnings("ignore:Pydantic serializer warnings")
def test_invalid_data_from_model_copy_is_refused(store: MemoryStore) -> None:
    project = store.get_project(PROJECT)
    assert project is not None
    broken = project.model_copy(update={"sync_state": "sideways"})
    with pytest.raises(ValidationError):
        store.commit(Commit(project_id=PROJECT, idempotency_key="k", puts=[broken]))


def test_another_projects_entity_is_refused(store: MemoryStore) -> None:
    with pytest.raises(ValueError, match="belongs to"):
        store.commit(
            Commit(project_id=PROJECT, idempotency_key="l", puts=[make_claim(project_id="other")])
        )


def test_reads_return_the_latest_revision_and_full_history(store: MemoryStore) -> None:
    store.commit(Commit(project_id=PROJECT, idempotency_key="m", puts=[make_claim()]))
    store.commit(Commit(project_id=PROJECT, idempotency_key="n", puts=[make_claim(revision=2)]))
    assert store.get_claim("C-T2").revision == 2  # type: ignore[union-attr]
    assert store.get_claim("C-T2", 1).revision == 1  # type: ignore[union-attr]
    assert [c.revision for c in store.claim_history("C-T2")] == [1, 2]
    assert [c.revision for c in store.list_claims(PROJECT)] == [2]


def test_ids_are_numbered_per_prefix(store: MemoryStore) -> None:
    assert [store.next_id(PROJECT, "D") for _ in range(2)] == ["D-1", "D-2"]
    assert store.next_id(PROJECT, "J") == "J-1"


def test_plans_are_listed_in_version_order(store: MemoryStore) -> None:
    v2 = make_plan(2).model_copy(update={"status": PlanStatus.APPROVED})
    store.commit(Commit(project_id=PROJECT, idempotency_key="o", puts=[v2]))
    assert [p.version for p in store.list_plans(PROJECT)] == [1, 2]
