"""H-1 and H-4: projects, join codes, members, and repo checks (UC-01, UC-02, D18)."""

from __future__ import annotations

import re

import pytest

from demo_fixture import NOW
from midflight.adapters.clock import FixedClock
from midflight.adapters.fake_github import FakeRepoAccess
from midflight.adapters.memory_store import MemoryStore
from midflight.demo import demo_plan
from midflight.domain.models import PlanStatus, Role
from midflight.ports import GitHubAccount
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict
from midflight.services.plans import PlanDraft, PlanService
from midflight.services.projects import ProjectService, participant_id

REPO = "acme/shop"
SOMESH = GitHubAccount(id=101, login="somesh", name="Somesh")
FREDERIK = GitHubAccount(id=202, login="Trexz14", name="Frederik")
MITHILESH = GitHubAccount(id=303, login="mithilesh")


@pytest.fixture
def repos() -> FakeRepoAccess:
    return FakeRepoAccess(installations={REPO: 4242}, admins={(REPO, "somesh")})


@pytest.fixture
def service(repos: FakeRepoAccess) -> ProjectService:
    store = MemoryStore()
    clock = FixedClock(NOW)
    return ProjectService(store, clock, repos, PlanService(store, clock))


def test_signing_in_twice_gives_the_same_user(service: ProjectService) -> None:
    first = service.sign_in(SOMESH)
    again = service.sign_in(SOMESH)
    assert first.id == again.id == "u-101"


def test_a_renamed_github_account_keeps_its_user(service: ProjectService) -> None:
    service.sign_in(SOMESH)
    renamed = service.sign_in(GitHubAccount(id=101, login="somesh-a"))
    assert (renamed.id, renamed.github_login) == ("u-101", "somesh-a")


def test_creating_a_project_makes_you_its_lead(service: ProjectService) -> None:
    lead = service.sign_in(SOMESH)
    project = service.create_project(lead, REPO, name="Acme shop")

    assert project.github_installation_id == 4242
    assert re.fullmatch(r"MF-[A-Z2-9]{4}-[A-Z2-9]{4}", project.join_code or "")
    membership = service.membership(lead)
    assert membership.participant.role is Role.LEAD
    assert membership.participant.id == participant_id(project.id, "somesh")


def test_a_github_url_works_as_the_repository(service: ProjectService) -> None:
    lead = service.sign_in(SOMESH)
    assert service.create_project(lead, "https://github.com/acme/shop/").repository == REPO


def test_h4_project_needs_the_app_installed(service: ProjectService, repos: FakeRepoAccess) -> None:
    lead = service.sign_in(SOMESH)
    repos.admins.add(("acme/other", "somesh"))
    with pytest.raises(InvalidRequest, match="isn't installed") as refused:
        service.create_project(lead, "acme/other")
    assert "github.com/apps/" in refused.value.hint


def test_h4_only_a_repo_admin_creates_its_project(service: ProjectService) -> None:
    frederik = service.sign_in(FREDERIK)
    with pytest.raises(PermissionDenied, match="isn't an admin"):
        service.create_project(frederik, REPO)


def test_one_project_per_repository(service: ProjectService) -> None:
    lead = service.sign_in(SOMESH)
    service.create_project(lead, REPO)
    with pytest.raises(StateConflict, match="already has"):
        service.create_project(lead, "ACME/Shop")


def test_teammates_join_with_the_code(service: ProjectService) -> None:
    lead = service.sign_in(SOMESH)
    project = service.create_project(lead, REPO)
    frederik = service.sign_in(FREDERIK)

    joined = service.join(frederik, f"  {project.join_code.lower()} ")  # type: ignore[union-attr]
    assert joined.participant.role is Role.AGENT
    assert joined.participant.id == f"{project.id}.trexz14"
    assert joined.participant.id in joined.project.participant_ids


def test_joining_twice_is_harmless(service: ProjectService) -> None:
    project = service.create_project(service.sign_in(SOMESH), REPO)
    frederik = service.sign_in(FREDERIK)
    first = service.join(frederik, project.join_code or "")
    again = service.join(frederik, project.join_code or "")
    assert first.participant == again.participant
    assert len(again.project.participant_ids) == 2


def test_a_wrong_code_adds_nobody(service: ProjectService) -> None:
    service.create_project(service.sign_in(SOMESH), REPO)
    with pytest.raises(InvalidRequest, match="no project has that join code"):
        service.join(service.sign_in(FREDERIK), "MF-AAAA-BBBB")


def test_a_rotated_code_stops_working(service: ProjectService) -> None:
    lead_user = service.sign_in(SOMESH)
    project = service.create_project(lead_user, REPO)
    lead = service.membership(lead_user).participant
    new_code = service.rotate_join_code(lead)

    with pytest.raises(InvalidRequest):
        service.join(service.sign_in(FREDERIK), project.join_code or "")
    assert service.join(service.sign_in(MITHILESH), new_code).participant.role is Role.AGENT


def test_only_the_lead_rotates_or_removes(service: ProjectService) -> None:
    project = service.create_project(service.sign_in(SOMESH), REPO)
    member = service.join(service.sign_in(FREDERIK), project.join_code or "").participant
    with pytest.raises(PermissionDenied, match="lead"):
        service.rotate_join_code(member)
    with pytest.raises(PermissionDenied, match="lead"):
        service.remove_member(member, "somesh")


def test_a_removed_member_cannot_rejoin_or_act(service: ProjectService) -> None:
    lead_user = service.sign_in(SOMESH)
    project = service.create_project(lead_user, REPO)
    frederik = service.sign_in(FREDERIK)
    service.join(frederik, project.join_code or "")
    service.remove_member(service.membership(lead_user).participant, "Trexz14")

    with pytest.raises(PermissionDenied, match="removed"):
        service.join(frederik, project.join_code or "")
    with pytest.raises(InvalidRequest, match="aren't in a Midflight project"):
        service.membership(frederik)


def test_membership_needs_a_project_id_when_you_are_in_several(
    service: ProjectService, repos: FakeRepoAccess
) -> None:
    lead = service.sign_in(SOMESH)
    repos.installations["acme/api"] = 7
    repos.admins.add(("acme/api", "somesh"))
    first = service.create_project(lead, REPO)
    second = service.create_project(lead, "acme/api")

    with pytest.raises(InvalidRequest, match="several projects") as ambiguous:
        service.membership(lead)
    assert first.id in ambiguous.value.hint and second.id in ambiguous.value.hint
    assert service.membership(lead, second.id).project.id == second.id


def test_no_access_to_a_project_you_are_not_in(service: ProjectService) -> None:
    project = service.create_project(service.sign_in(SOMESH), REPO)
    with pytest.raises(PermissionDenied, match="aren't a member"):
        service.membership(service.sign_in(FREDERIK), project.id)


def test_lead_assigns_a_task_as_a_new_plan_version(service: ProjectService) -> None:
    lead_user = service.sign_in(SOMESH)
    project = service.create_project(lead_user, REPO)
    lead = service.membership(lead_user).participant
    service.join(service.sign_in(FREDERIK), project.join_code or "")

    v1 = demo_plan(1, status=PlanStatus.PROPOSED)
    tasks = [t.model_copy(update={"owner": lead.id}) for t in v1.tasks]
    plans = service._plans
    proposed = plans.propose(
        lead, PlanDraft(requirements=v1.requirements, tasks=tasks, contracts=v1.contracts)
    )
    plans.approve(lead, proposed.version, "initial plan")

    v2 = service.assign_task(lead, "T2", "Trexz14")
    assert v2.version == 2
    assert v2.task("T2").owner == f"{project.id}.trexz14"  # type: ignore[union-attr]
    assert v2.task("T1").owner == lead.id  # type: ignore[union-attr]


def test_assigning_to_someone_who_has_not_joined_explains_how(service: ProjectService) -> None:
    lead_user = service.sign_in(SOMESH)
    service.create_project(lead_user, REPO)
    with pytest.raises(InvalidRequest, match="isn't a member") as refused:
        service.assign_task(service.membership(lead_user).participant, "T2", "nobody")
    assert "join code" in refused.value.hint


def test_unknown_user_id_is_not_found(service: ProjectService) -> None:
    with pytest.raises(NotFound):
        service.user("u-999")
