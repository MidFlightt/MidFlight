"""The hosted MCP connector every team uses (task H-2, decisions D16 and D18).

Served at `<public url>/mcp` behind Sign in with GitHub (`midflight.api.oauth`). Each
tool call:

1. finds who is calling, from their access token (the token's subject is a user id);
2. finds which project they mean (`project_id`, or their only project);
3. calls the same services the REST API uses, with their membership as the actor;
4. replies in plain text from `midflight.mcp.replies`.

Tools for everyone signed in: `my_projects`, `create_project`, `join_project`.
Tools for members: `check_in`, `submit_claim`, `acknowledge_directive`, `project_status`.
Tools for the lead: `propose_plan`, `approve_plan`, `assign_task`, `resolve_escalation`,
`rotate_join_code`, `remove_member`, and the demo fault switch `simulate_github_outage`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from midflight.api.app import Services
from midflight.api.views import check_in_json, verdict_json
from midflight.domain.models import Contract as PlanContract
from midflight.domain.models import (
    DirectiveResponse,
    EscalationState,
    FieldType,
    Id,
    InterfaceUse,
    JobState,
    Model,
    Participant,
    Requirement,
    Resolution,
    Role,
    Text,
    User,
)
from midflight.domain.models import Task as PlanTask
from midflight.domain.states import OPEN_DIRECTIVE_STATES
from midflight.mcp.instructions import (
    ACKNOWLEDGE_DIRECTIVE,
    CHECK_IN,
    HOSTED_INSTRUCTIONS,
    SUBMIT_CLAIM,
)
from midflight.mcp.replies import check_in_text, directives_block, refused_text, verdict_text
from midflight.services.claims import ClaimSubmission
from midflight.services.directives import ACK_NOTE
from midflight.services.errors import PermissionDenied, ServiceError
from midflight.services.plans import PlanDraft
from midflight.services.projects import Membership, ProjectService

# How long submit_claim waits for a review before answering "pending" (D3).
WAIT_SECONDS = 55.0


# Inputs for the lead's plan tools: tasks name their owner by GitHub login --------------


class TaskInput(Model):
    id: Id
    title: Text
    owner: Text  # the member's GitHub login
    requirement_ids: list[Id] = []
    provides: list[Id] = []
    consumes: list[Id] = []
    branch: str | None = None


class ContractInput(Model):
    id: Id
    provider_task: Id
    consumer_tasks: list[Id] = []
    fields: dict[Text, FieldType]


def _signed_in_user_id() -> str | None:
    token = get_access_token()
    return token.subject if token else None


def build_hosted_server(
    services: Services,
    projects: ProjectService,
    *,
    auth: AuthSettings | None = None,
    oauth: OAuthAuthorizationServerProvider | None = None,
    current_user_id: Callable[[], str | None] = _signed_in_user_id,
    wait_seconds: float = WAIT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> MCPServer:
    """The hosted MCP server. Tests pass `current_user_id` instead of real sign-in."""
    server = MCPServer(
        "midflight",
        instructions=HOSTED_INSTRUCTIONS,
        version="0.2.0",
        auth=auth,
        auth_server_provider=oauth,
    )
    store = services.store

    # Who is calling, and in which project ----------------------------------------------

    def me() -> User:
        user_id = current_user_id()
        if user_id is None:
            raise PermissionDenied("you aren't signed in to Midflight", "Reconnect the connector.")
        return projects.user(user_id)

    def membership(project_id: str | None) -> Membership:
        return projects.membership(me(), project_id)

    def lead(project_id: str | None) -> Participant:
        member = membership(project_id).participant
        if member.role is not Role.LEAD:
            raise PermissionDenied("only the project's lead can do this", "Ask your lead.")
        return member

    def answer(action: Callable[[], str]) -> str:
        """Run a tool; a refusal becomes a readable reply instead of an error."""
        try:
            return action()
        except ServiceError as error:
            return refused_text(
                {
                    "detail": error.detail,
                    "hint": error.hint,
                    "findings": [f.model_dump(mode="json") for f in error.findings],
                }
            )

    def login_of(participant_id: str) -> str:
        member = store.get_participant(participant_id)
        return member.developer_name if member else participant_id

    def with_directives(text: str, member: Participant, task_id: str | None = None) -> str:
        try:
            reply = check_in_json(services.check_ins.check_in(member, task_id))
        except ServiceError:
            return text
        return f"{text}\n\n{directives_block(reply['directives'])}"

    # Joining a project -----------------------------------------------------------------

    @server.tool(description="List the Midflight projects you belong to, and your role in each.")
    def my_projects() -> str:
        def act() -> str:
            mine = projects.memberships(me())
            if not mine:
                return (
                    "You aren't in a Midflight project yet. Ask your lead for the join code "
                    "and call join_project, or call create_project for a repository you admin."
                )
            lines = ["Your Midflight projects:"]
            for m in mine:
                project, role = m.project, m.participant.role.value
                line = f"- {project.id}: {project.name} ({project.repository}), you are {role}"
                if m.participant.role is Role.LEAD:
                    line += f", join code {m.project.join_code}"
                lines.append(line)
            return "\n".join(lines)

        return answer(act)

    @server.tool(
        description="Create a Midflight project for a GitHub repository you administer. "
        "The Midflight GitHub App must be installed on it. You become the lead and get a "
        "join code to share with your team."
    )
    def create_project(repository: str, name: str | None = None) -> str:
        def act() -> str:
            project = projects.create_project(me(), repository, name)
            return (
                f"Created project {project.id} for {project.repository}. You are its lead.\n"
                f"Join code: {project.join_code}\n"
                "Share the join code with your teammates; they call join_project with it.\n"
                "Next: once they've joined, write the plan with propose_plan (each task's owner "
                "is a member's GitHub login), then approve_plan."
            )

        return answer(act)

    @server.tool(description="Join a Midflight project with the join code your lead shared.")
    def join_project(join_code: str) -> str:
        def act() -> str:
            joined = projects.join(me(), join_code)
            return (
                f"You're a member of {joined.project.name} ({joined.project.id}). "
                f"Lead: {login_of(joined.project.lead_id)}.\n"
                "Next: call check_in to see your task. If none is assigned yet, ask your lead."
            )

        return answer(act)

    # Agent work ------------------------------------------------------------------------

    @server.tool(description=CHECK_IN)
    def check_in(task_id: str | None = None, project_id: str | None = None) -> str:
        return answer(
            lambda: check_in_text(
                check_in_json(
                    services.check_ins.check_in(membership(project_id).participant, task_id)
                )
            )
        )

    @server.tool(description=SUBMIT_CLAIM)
    def submit_claim(
        task_id: str,
        plan_version: int,
        branch: str,
        base_sha: str,
        acceptance_criteria: list[str] | None = None,
        provides: list[InterfaceUse] | None = None,
        consumes: list[InterfaceUse] | None = None,
        no_interfaces: bool = False,
        assumptions: list[str] | None = None,
        files: list[str] | None = None,
        requirement_ids: list[str] | None = None,
        claim_id: str | None = None,
        reason: str | None = None,
        status: Literal["withdrawn", "closed"] | None = None,
        project_id: str | None = None,
    ) -> str:
        def act() -> str:
            member = membership(project_id).participant
            if status is not None:
                if claim_id is None:
                    return f"To set status {status}, pass the claim_id."
                change = (
                    services.claims.withdraw if status == "withdrawn" else services.claims.close
                )
                claim = change(member, claim_id, reason)
                text = f"Claim {claim.id} rev {claim.revision}: {claim.state.value.upper()}"
                return with_directives(text, member, task_id)
            submission = ClaimSubmission(
                claim_id=claim_id,
                task_id=task_id,
                branch=branch,
                base_sha=base_sha,
                plan_version=plan_version,
                requirement_ids=requirement_ids or [],
                files=files or [],
                provides=provides or [],
                consumes=consumes or [],
                no_interfaces=no_interfaces,
                assumptions=assumptions or [],
                acceptance_criteria=acceptance_criteria or [],
                reason=reason,
            )
            result = services.claims.submit(member, submission)
            if not wait_for_review(result.job_id):
                text = (
                    f"Claim {result.claim_id} rev {result.revision}: PENDING. The review is still "
                    "running. Work only on steps that don't depend on it; the verdict comes with "
                    "your next check_in. Don't resubmit."
                )
                return with_directives(text, member, task_id)
            verdict = verdict_json(services.claims.verdict(result.claim_id, result.revision))
            return f"{verdict_text(verdict)}\n\n{directives_block(verdict['directives'])}"

        return answer(act)

    def wait_for_review(job_id: str) -> bool:
        """Locally reviews finish inline; on AWS the worker finishes them. Poll briefly."""
        deadline = time.monotonic() + wait_seconds
        while True:
            job = store.get_job(job_id)
            if job is not None and job.state in (JobState.SUCCEEDED, JobState.FAILED):
                return True
            if time.monotonic() >= deadline:
                return False
            sleep(1.0)

    @server.tool(description=ACKNOWLEDGE_DIRECTIVE)
    def acknowledge_directive(
        directive_id: str,
        response: Literal["acknowledged", "rejected", "needs_clarification"],
        note: str | None = None,
        project_id: str | None = None,
    ) -> str:
        def act() -> str:
            member = membership(project_id).participant
            answered = services.directives.acknowledge(
                member, directive_id, DirectiveResponse(response), note
            )
            text = f"Directive {answered.id}: {answered.state.value}. {ACK_NOTE}"
            return with_directives(text, member, answered.task_id)

        return answer(act)

    @server.tool(
        description="See the project at a glance: plan version, members and their tasks, "
        "claims, open directives, and escalations."
    )
    def project_status(project_id: str | None = None) -> str:
        def act() -> str:
            m = membership(project_id)
            project = m.project
            lines = [f"{project.name} ({project.id}), repository {project.repository}"]
            if m.participant.role is Role.LEAD:
                lines.append(f"Join code: {project.join_code}")
            plan = store.get_plan(project.id, project.current_plan_version or 0)
            members = [store.get_participant(pid) for pid in project.participant_ids]
            lines.append("\nMembers:")
            for member in members:
                if member is None or not member.active:
                    continue
                tasks = [t.id for t in plan.tasks if t.owner == member.id] if plan else []
                lines.append(
                    f"- {member.developer_name} ({member.role.value})"
                    + (f": {', '.join(tasks)}" if tasks else ": no task yet")
                )
            if plan is None:
                lines.append("\nNo plan approved yet. The lead writes one with propose_plan.")
                return "\n".join(lines)
            lines.append(f"\nPlan v{plan.version}:")
            claims = {c.task_id: c for c in store.list_claims(project.id)}
            for task in plan.tasks:
                claim = claims.get(task.id)
                state = (
                    f"claim {claim.id} rev {claim.revision} {claim.state.value}"
                    if claim
                    else "no claim"
                )
                lines.append(f"- {task.id} {task.title} ({login_of(task.owner)}): {state}")
            open_directives = [
                d for d in store.list_directives(project.id) if d.state in OPEN_DIRECTIVE_STATES
            ]
            lines.append(f"\nOpen directives: {len(open_directives)}")
            lines += [
                f"- {d.id} for {d.task_id} ({d.state.value}): {d.requested_adjustment}"
                for d in open_directives
            ]
            if project.sync_state.value == "stale":
                lines.append(f"\nGitHub data is STALE: {project.sync_reason}")
            verifications = sorted(
                store.list_verifications(project.id), key=lambda v: v.created_at
            )[-5:]
            if verifications:
                lines.append("\nLatest midflight/verify results:")
                lines += [
                    f"- {v.id} {v.outcome.value} for {v.head_sha[:7]}"
                    + (f" (claim {v.claim_id})" if v.claim_id else "")
                    for v in verifications
                ]
            escalations = [
                e for e in store.list_escalations(project.id) if e.state is EscalationState.OPEN
            ]
            lines.append(f"\nOpen escalations: {len(escalations)}")
            for e in escalations:
                lines.append(f"- {e.id} (claims {', '.join(e.claim_ids)}): {e.explanation}")
                lines += [f"    {ev.ref}: {ev.excerpt}" for ev in e.evidence if ev.excerpt]
            if escalations and m.participant.role is Role.LEAD:
                lines.append(
                    "Decide each one with resolve_escalation. Midflight won't pick a side."
                )
            return "\n".join(lines)

        return answer(act)

    # Lead tools ------------------------------------------------------------------------

    @server.tool(
        description="Lead only. Propose the project's next plan version: requirements, tasks "
        "(each owned by a member's GitHub login), and contracts with typed fields. Then "
        "call approve_plan with the version it returns."
    )
    def propose_plan(
        requirements: list[Requirement],
        tasks: list[TaskInput],
        contracts: list[ContractInput] | None = None,
        project_id: str | None = None,
    ) -> str:
        def act() -> str:
            member = lead(project_id)
            plan_tasks = [
                PlanTask(
                    id=t.id,
                    title=t.title,
                    owner=projects.member(member.project_id, t.owner).id,
                    requirement_ids=t.requirement_ids,
                    provides=t.provides,
                    consumes=t.consumes,
                    branch=t.branch,
                )
                for t in tasks
            ]
            plan_contracts = [PlanContract(version=1, **c.model_dump()) for c in contracts or []]
            draft = PlanDraft(requirements=requirements, tasks=plan_tasks, contracts=plan_contracts)
            plan = services.plans.propose(member, draft)
            changed = ", ".join(plan.changed_ids) or "first version"
            return (
                f"Proposed plan v{plan.version} ({changed}). Nothing changes for the team until "
                f"you approve it: call approve_plan with version {plan.version} and a reason."
            )

        return answer(act)

    @server.tool(description="Lead only. Approve a proposed plan version, with a reason.")
    def approve_plan(version: int, reason: str, project_id: str | None = None) -> str:
        def act() -> str:
            plan = services.plans.approve(lead(project_id), version, reason)
            return (
                f"Plan v{plan.version} is approved and current. "
                "Agents see it at their next check_in."
            )

        return answer(act)

    @server.tool(description="Lead only. Give a plan task to a member, by GitHub login.")
    def assign_task(task_id: str, member: str, project_id: str | None = None) -> str:
        def act() -> str:
            plan = projects.assign_task(lead(project_id), task_id, member)
            return f"{task_id} now belongs to {member} (plan v{plan.version})."

        return answer(act)

    @server.tool(
        description="Lead only. Decide an open escalation (a conflict between people's "
        "requirements). clarify_plan: you already approved a plan version that settles it; "
        "the claims are reviewed again. request_revision: the involved agents revise their "
        "claims to match your reason. dismiss: not a real conflict; the claims are reviewed "
        "again without it. Always give the reason the team will see."
    )
    def resolve_escalation(
        escalation_id: str,
        resolution: Literal["clarify_plan", "request_revision", "dismiss"],
        reason: str,
        project_id: str | None = None,
    ) -> str:
        def act() -> str:
            resolved = services.escalations.resolve(
                lead(project_id), escalation_id, Resolution(resolution), reason
            )
            return (
                f"Escalation {resolved.id} resolved ({resolution}). Claims "
                f"{', '.join(resolved.claim_ids)} were updated; their agents see it at their "
                "next check_in."
            )

        return answer(act)

    @server.tool(
        description="Lead only, for demos: a labeled fault switch. on=true makes Midflight "
        "behave as if GitHub were down for this project (data marked stale, new directives "
        "held, no approvals); on=false recovers and reviews held claims again."
    )
    def simulate_github_outage(on: bool, project_id: str | None = None) -> str:
        def act() -> str:
            services.sync.set_fault(lead(project_id), on)
            if on:
                return (
                    "Fault switch ON: Midflight now treats GitHub as unavailable for this "
                    "project. Directives are held and nothing is approved until you turn it off."
                )
            return "Fault switch OFF: GitHub data is fresh again; held claims were reviewed again."

        return answer(act)

    @server.tool(description="Lead only. Replace the join code; the old one stops working.")
    def rotate_join_code(project_id: str | None = None) -> str:
        return answer(lambda: f"New join code: {projects.rotate_join_code(lead(project_id))}")

    @server.tool(description="Lead only. Remove a member from the project, by GitHub login.")
    def remove_member(member: str, project_id: str | None = None) -> str:
        def act() -> str:
            projects.remove_member(lead(project_id), member)
            return f"{member} is no longer a member. Their calls are refused from now on."

        return answer(act)

    return server
