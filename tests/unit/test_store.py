"""The Store contract: every test runs against MemoryStore and DynamoStore (on moto).

Atomic commits, the coord_rev compare-and-set, idempotency, history protection, and the
lookups the hosted connector needs. If the two stores ever disagree, a test here fails.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError

from demo_fixture import NOW, PROJECT, make_claim, make_plan, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.dynamo_store import DynamoStore
from midflight.adapters.fake_github import FakeGitHub
from midflight.adapters.memory_store import MemoryStore
from midflight.api.app import build_services
from midflight.domain.models import ClaimState, Participant, PlanStatus, Role, SyncState, User
from midflight.ports import ChangedFiles, Commit, PullRequestInfo, RevisionConflict, Store
from midflight.services.plans import PlanDraft
from midflight.services.verification import WorkflowRun


@pytest.fixture(params=["memory", "dynamo"])
def store(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[Store]:
    if request.param == "memory":
        s: Any = MemoryStore()
        seed(s)
        yield s
        return
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(key, value)
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        DynamoStore.create_table(client, "midflight-test")
        s = DynamoStore("midflight-test", client)
        seed(s)
        yield s


def rev(store: Store) -> int:
    project = store.get_project(PROJECT)
    assert project is not None
    return project.coord_rev


def test_bump_advances_coord_rev(store: Store) -> None:
    before = rev(store)
    result = store.commit(
        Commit(project_id=PROJECT, idempotency_key="a", puts=[make_claim()], bump_coord_rev=True)
    )
    assert result.applied and result.coord_rev == before + 1 == rev(store)


def test_inv_02_stale_compare_and_set_writes_nothing(store: Store) -> None:
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


def test_repeated_idempotency_key_writes_once(store: Store) -> None:
    commit = Commit(
        project_id=PROJECT, idempotency_key="c", puts=[make_claim()], bump_coord_rev=True
    )
    store.commit(commit)
    again = store.commit(commit)
    assert again.duplicate and not again.applied
    assert rev(store) == 1


def test_a_bad_entity_fails_the_whole_commit(store: Store) -> None:
    edited = make_claim(files=["somewhere/else.py"])
    store.commit(Commit(project_id=PROJECT, idempotency_key="d", puts=[make_claim()]))
    with pytest.raises(ValueError, match="new revision"):
        store.commit(
            Commit(project_id=PROJECT, idempotency_key="e", puts=[make_claim("T1"), edited])
        )
    assert [c.task_id for c in store.list_claims(PROJECT)] == ["T2"]


def test_a_saved_revision_can_change_only_its_verdict(store: Store) -> None:
    store.commit(Commit(project_id=PROJECT, idempotency_key="f", puts=[make_claim()]))
    approved = make_claim(state=ClaimState.APPROVED)
    store.commit(Commit(project_id=PROJECT, idempotency_key="g", puts=[approved]))
    assert store.get_claim("C-T2").state is ClaimState.APPROVED  # type: ignore[union-attr]


def test_an_approved_plan_cannot_change(store: Store) -> None:
    changed = make_plan(1).model_copy(update={"change_reason": "rewritten"})
    with pytest.raises(ValueError, match="approved"):
        store.commit(Commit(project_id=PROJECT, idempotency_key="h", puts=[changed]))


def test_saving_a_project_never_rolls_back_coord_rev(store: Store) -> None:
    old = store.get_project(PROJECT)
    store.commit(Commit(project_id=PROJECT, idempotency_key="i", bump_coord_rev=True))
    assert old is not None
    stale = old.model_copy(update={"sync_state": SyncState.STALE, "sync_reason": "test"})
    store.commit(Commit(project_id=PROJECT, idempotency_key="j", puts=[stale]))
    assert rev(store) == 1


@pytest.mark.filterwarnings("ignore:Pydantic serializer warnings")
def test_invalid_data_from_model_copy_is_refused(store: Store) -> None:
    project = store.get_project(PROJECT)
    assert project is not None
    broken = project.model_copy(update={"sync_state": "sideways"})
    with pytest.raises(ValidationError):
        store.commit(Commit(project_id=PROJECT, idempotency_key="k", puts=[broken]))


def test_another_projects_entity_is_refused(store: Store) -> None:
    with pytest.raises(ValueError, match="belongs to"):
        store.commit(
            Commit(project_id=PROJECT, idempotency_key="l", puts=[make_claim(project_id="other")])
        )


def test_reads_return_the_latest_revision_and_full_history(store: Store) -> None:
    store.commit(Commit(project_id=PROJECT, idempotency_key="m", puts=[make_claim()]))
    store.commit(Commit(project_id=PROJECT, idempotency_key="n", puts=[make_claim(revision=2)]))
    assert store.get_claim("C-T2").revision == 2  # type: ignore[union-attr]
    assert store.get_claim("C-T2", 1).revision == 1  # type: ignore[union-attr]
    assert [c.revision for c in store.claim_history("C-T2")] == [1, 2]
    assert [c.revision for c in store.list_claims(PROJECT)] == [2]


def test_ids_are_numbered_per_prefix(store: Store) -> None:
    assert [store.next_id(PROJECT, "D") for _ in range(2)] == ["D-1", "D-2"]
    assert store.next_id(PROJECT, "J") == "J-1"


def test_plans_are_listed_in_version_order(store: Store) -> None:
    v2 = make_plan(2).model_copy(update={"status": PlanStatus.APPROVED})
    store.commit(Commit(project_id=PROJECT, idempotency_key="o", puts=[v2]))
    assert [p.version for p in store.list_plans(PROJECT)] == [1, 2]


# What the hosted connector needs (H-1, H-3) -------------------------------------------


def test_users_are_found_by_id_and_github_account(store: Store) -> None:
    user = User(id="u-7", github_id=7, github_login="somesh", created_at=NOW)
    store.save_user(user)
    assert store.get_user("u-7") == user
    assert store.find_user_by_github_id(7) == user
    assert store.find_user_by_github_id(8) is None


def test_projects_are_found_by_join_code_and_repository(store: Store) -> None:
    project = store.get_project(PROJECT)
    assert project is not None
    coded = project.model_copy(update={"join_code": "MF-AAAA-BBBB"})
    store.commit(Commit(project_id=PROJECT, idempotency_key="code1", puts=[coded]))
    assert store.find_project_by_join_code("MF-AAAA-BBBB").id == PROJECT  # type: ignore[union-attr]
    assert store.find_project_by_repository(project.repository.upper()) is not None

    rotated = coded.model_copy(update={"join_code": "MF-CCCC-DDDD"})
    store.commit(Commit(project_id=PROJECT, idempotency_key="code2", puts=[rotated]))
    assert store.find_project_by_join_code("MF-AAAA-BBBB") is None
    assert store.find_project_by_join_code("MF-CCCC-DDDD") is not None


def test_memberships_list_a_users_participants(store: Store) -> None:
    member = Participant(
        id=f"{PROJECT}.ana",
        project_id=PROJECT,
        role=Role.AGENT,
        developer_name="ana",
        user_id="u-9",
    )
    store.commit(Commit(project_id=PROJECT, idempotency_key="join", puts=[member]))
    assert [p.id for p in store.list_memberships("u-9")] == [f"{PROJECT}.ana"]
    assert store.get_participant(f"{PROJECT}.ana") == member


def test_participants_are_found_by_token_hash(store: Store) -> None:
    lead = store.get_participant("p-lead")
    assert lead is not None and lead.token_hash is not None
    assert store.find_participant_by_token_hash(lead.token_hash) == lead
    assert store.find_participant_by_token_hash("0" * 64) is None


def test_sign_in_records_expire(store: Store) -> None:
    store.put_auth("code", "abc", {"subject": "u-1"}, time.time() + 60)
    store.put_auth("code", "old", {"subject": "u-2"}, time.time() - 1)
    store.put_auth("client", "c1", {"name": "Claude"})
    assert store.get_auth("code", "abc") == {"subject": "u-1"}
    assert store.get_auth("code", "old") is None
    assert store.get_auth("client", "c1") == {"name": "Claude"}
    store.delete_auth("code", "abc")
    assert store.get_auth("code", "abc") is None


def test_ids_never_repeat_across_projects(store: Store) -> None:
    assert store.next_id("one", "C") != store.next_id("two", "C")


def test_plan_change_verification_and_fault_switch_work_on_this_store(store: Store) -> None:
    """S-6, M-6, and M-7 write new kinds of items together; each store must take them."""
    github = FakeGitHub()
    services = build_services(store, FixedClock(NOW), github=github)
    t1, lead = store.get_participant("p-t1"), store.get_participant("p-lead")
    claim = services.claims.submit(t1, submission("T1"))

    # A failed push: a verification, a check, and a correction directive.
    github.pulls["t1-work"] = PullRequestInfo(12, "t1-work", "abc1234", "9f3e1a2")
    github.diffs["abc1234"] = ChangedFiles(paths=["app/api.py"], patch="")
    github.files[("app/api.py", "abc1234")] = "return {'total': 49.99}"
    github.artifacts[1] = {"sha": "abc1234", "results": [{"name": "t", "passed": False}]}
    repo = "MidFlightt/midflight-demo-shop"
    services.verifications.enqueue(WorkflowRun(repo, 169380149, 1, 1, "abc1234", "t1-work", "d"))
    [verification] = store.list_verifications(PROJECT)
    assert verification.outcome.value == "failed" and verification.check_run_id == 1

    # A plan change supersedes the correction and sends T1 back for review.
    plan = make_plan(2)
    draft = PlanDraft(requirements=plan.requirements, tasks=plan.tasks, contracts=plan.contracts)
    services.plans.approve(lead, services.plans.propose(lead, draft).version, "add currency")
    states = sorted((d.source.value, d.state.value) for d in store.list_directives(PROJECT, "T1"))
    assert states == [("plan_change", "queued"), ("verification", "superseded")]
    assert store.get_claim(claim.claim_id).state is ClaimState.NEEDS_REVISION

    # The fault switch round trip.
    services.sync.set_fault(lead, True)
    assert store.get_project(PROJECT).sync_state is SyncState.STALE
    services.sync.set_fault(lead, False)
    assert store.get_project(PROJECT).sync_state is SyncState.FRESH


def test_a_replaced_token_stops_working(store: Store) -> None:
    old = store.get_participant("p-t1")
    new_hash = "f" * 64
    replaced = old.model_copy(update={"token_hash": new_hash})
    store.commit(Commit(project_id=PROJECT, idempotency_key="rotate", puts=[replaced]))
    assert store.find_participant_by_token_hash(old.token_hash) is None
    assert store.find_participant_by_token_hash(new_hash).id == "p-t1"
