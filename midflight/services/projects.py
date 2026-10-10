"""Projects, members, and join codes (tasks H-1 and H-4, decisions D16 and D18).

How a team forms:

1. Someone signs in with GitHub (`sign_in`) and creates a project for a repository
   (`create_project`). Midflight checks the GitHub App is installed on that repository
   and that this person can administer it. The creator becomes the project's lead and
   gets a join code.
2. Teammates sign in and `join` with the code. Each becomes a member with the `agent`
   role. A person can belong to many projects.
3. The lead can assign plan tasks to members, rotate the join code, and remove members.

A member's participant id is `<project id>.<github login>`, for example
`shop-4f9a.frederik`, so plans stay readable.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from midflight.domain.models import Participant, Plan, Project, Role, User
from midflight.ports import Clock, Commit, GitHubAccount, RepoAccess, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict
from midflight.services.plans import PlanDraft, PlanService

# No 0/O or 1/I, so a code read aloud or copied by hand still works.
JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")
APP_INSTALL_HINT = (
    "Install the Midflight GitHub App on the repository first: "
    "https://github.com/apps/midflight-team-yoga/installations/new"
)


def new_join_code() -> str:
    part = lambda: "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(4))  # noqa: E731
    return f"MF-{part()}-{part()}"


def participant_id(project_id: str, github_login: str) -> str:
    return f"{project_id}.{github_login.lower()}"


@dataclass(frozen=True)
class Membership:
    project: Project
    participant: Participant


class ProjectService:
    def __init__(self, store: Store, clock: Clock, repos: RepoAccess, plans: PlanService) -> None:
        self._store = store
        self._clock = clock
        self._repos = repos
        self._plans = plans

    # Signing in ------------------------------------------------------------------------

    def sign_in(self, account: GitHubAccount) -> User:
        """The Midflight user for this GitHub account, created on first sign-in."""
        user = self._store.find_user_by_github_id(account.id)
        if user is None:
            user = User(
                id=f"u-{account.id}",
                github_id=account.id,
                github_login=account.login,
                name=account.name,
                created_at=self._clock.now(),
            )
        elif user.github_login != account.login or user.name != account.name:
            # People can rename their GitHub account; keep the login current.
            user = user.model_copy(update={"github_login": account.login, "name": account.name})
        self._store.save_user(user)
        return user

    def user(self, user_id: str) -> User:
        user = self._store.get_user(user_id)
        if user is None:
            raise NotFound("you're signed in as a user Midflight doesn't know; sign in again")
        return user

    # Creating and joining --------------------------------------------------------------

    def create_project(self, user: User, repository: str, name: str | None = None) -> Project:
        """Create a project for a repository; the creator becomes its lead (UC-01)."""
        repository = repository.strip().removeprefix("https://github.com/").strip("/")
        if not REPOSITORY.match(repository):
            raise InvalidRequest(
                f"'{repository}' isn't a GitHub repository", "Use the form owner/name."
            )
        existing = self._store.find_project_by_repository(repository)
        if existing is not None:
            raise StateConflict(
                f"{repository} already has a Midflight project ({existing.name})",
                "Ask its lead for the join code and call join_project.",
            )
        installation = self._repos.installation_id(repository)
        if installation is None:
            raise InvalidRequest(
                f"the Midflight GitHub App isn't installed on {repository}", APP_INSTALL_HINT
            )
        if not self._repos.is_admin(repository, user.github_login):
            raise PermissionDenied(
                f"{user.github_login} isn't an admin of {repository}",
                "Only a repository admin can create its Midflight project.",
            )

        project_id = f"{_slug(repository.split('/')[1])}-{secrets.token_hex(2)}"
        lead = Participant(
            id=participant_id(project_id, user.github_login),
            project_id=project_id,
            role=Role.LEAD,
            developer_name=user.github_login,
            user_id=user.id,
        )
        project = Project(
            id=project_id,
            name=name or repository,
            repository=repository,
            github_installation_id=installation,
            join_code=new_join_code(),
            created_by=user.id,
            lead_id=lead.id,
            participant_ids=[lead.id],
        )
        self._save(
            project.id,
            [project, lead],
            actor=lead.id,
            action="project.created",
            reason=f"{user.github_login} created a project for {repository}",
            entity_ids=[project.id, lead.id],
        )
        return project

    def join(self, user: User, join_code: str) -> Membership:
        """Join the project that owns `join_code` as a member (UC-02)."""
        project = self._store.find_project_by_join_code(join_code.strip().upper())
        if project is None:
            raise InvalidRequest(
                "no project has that join code",
                "Check the code with your lead; it may have been rotated.",
            )
        member_id = participant_id(project.id, user.github_login)
        existing = self._store.get_participant(member_id)
        if existing is not None:
            if not existing.active:
                raise PermissionDenied(f"the lead removed you from {project.name}")
            return Membership(project, existing)
        member = Participant(
            id=member_id,
            project_id=project.id,
            role=Role.AGENT,
            developer_name=user.github_login,
            user_id=user.id,
        )
        updated = project.model_copy(
            update={"participant_ids": [*project.participant_ids, member.id]}
        )
        self._save(
            project.id,
            [updated, member],
            actor=member.id,
            action="member.joined",
            reason=f"{user.github_login} joined with the join code",
            entity_ids=[member.id],
        )
        return Membership(updated, member)

    # Finding a membership --------------------------------------------------------------

    def memberships(self, user: User) -> list[Membership]:
        """The user's active memberships, with their projects."""
        found = []
        for member in self._store.list_memberships(user.id):
            project = self._store.get_project(member.project_id)
            if member.active and project is not None:
                found.append(Membership(project, member))
        return found

    def membership(self, user: User, project_id: str | None = None) -> Membership:
        """The membership a tool call acts in: the named project, or the user's only one."""
        mine = self.memberships(user)
        if project_id is not None:
            match = [m for m in mine if m.project.id == project_id]
            if not match:
                raise PermissionDenied(f"you aren't a member of project {project_id}")
            return match[0]
        if len(mine) == 1:
            return mine[0]
        if not mine:
            raise InvalidRequest(
                "you aren't in a Midflight project yet",
                "Ask your lead for the join code and call join_project, or create_project.",
            )
        options = ", ".join(f"{m.project.id} ({m.project.name})" for m in mine)
        raise InvalidRequest(
            "you're in several projects; say which one", f"Pass project_id: {options}."
        )

    def member(self, project_id: str, github_login: str) -> Participant:
        member = self._store.get_participant(participant_id(project_id, github_login))
        if member is None or not member.active:
            raise InvalidRequest(
                f"{github_login} isn't a member of this project",
                "Share the join code with them and ask them to call join_project.",
            )
        return member

    # Lead actions ----------------------------------------------------------------------

    def rotate_join_code(self, lead: Participant) -> str:
        """Replace the join code; the old one stops working. People already in stay in."""
        project = self._lead_project(lead)
        code = new_join_code()
        self._save(
            project.id,
            [project.model_copy(update={"join_code": code})],
            actor=lead.id,
            action="project.join_code_rotated",
            reason="the lead rotated the join code",
            entity_ids=[project.id],
        )
        return code

    def remove_member(self, lead: Participant, github_login: str) -> Participant:
        project = self._lead_project(lead)
        member = self.member(project.id, github_login)
        if member.id == lead.id:
            raise InvalidRequest("the lead can't remove themselves")
        removed = member.model_copy(update={"revoked_at": self._clock.now()})
        self._save(
            project.id,
            [removed],
            actor=lead.id,
            action="member.removed",
            reason=f"the lead removed {github_login}",
            entity_ids=[member.id],
        )
        return removed

    def assign_task(self, lead: Participant, task_id: str, github_login: str) -> Plan:
        """Give a plan task to a member. Plans are immutable, so this approves a new
        version with only that task's owner changed."""
        project = self._lead_project(lead)
        member = self.member(project.id, github_login)
        current = self._plans.current(project.id)
        if current.task(task_id) is None:
            valid = ", ".join(t.id for t in current.tasks)
            raise InvalidRequest(f"plan v{current.version} has no task {task_id}", f"Use: {valid}.")
        tasks = [
            t.model_copy(update={"owner": member.id}) if t.id == task_id else t
            for t in current.tasks
        ]
        draft = PlanDraft(
            requirements=current.requirements, tasks=tasks, contracts=current.contracts
        )
        proposed = self._plans.propose(lead, draft)
        return self._plans.approve(lead, proposed.version, f"assign {task_id} to {github_login}")

    # Helpers ---------------------------------------------------------------------------

    def _lead_project(self, lead: Participant) -> Project:
        if lead.role is not Role.LEAD:
            raise PermissionDenied("only the project's lead can do this (INV-08)")
        project = self._store.get_project(lead.project_id)
        if project is None:
            raise NotFound(f"no project {lead.project_id}")
        return project

    def _save(
        self,
        project_id: str,
        puts: list[Project | Participant],
        *,
        actor: str,
        action: str,
        reason: str,
        entity_ids: list[str],
    ) -> None:
        key = f"{action}:{project_id}:{new_correlation_id()}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project_id,
            actor=actor,
            action=action,
            entity_ids=entity_ids,
            reason=reason,
            correlation_id=new_correlation_id(),
            idempotency_key=key,
        )
        self._store.commit(
            Commit(project_id=project_id, idempotency_key=key, puts=puts, audit=[event])
        )


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "project"
