"""The Midflight REST API (task M-2). Paths are the table in docs/domain.md (D15).

`create_app(services)` builds the app around any set of services. `midflight.main`
adds the hosted MCP connector and sign-in on top, for local runs and for AWS.
Errors are JSON `{error, detail, hint}`; refusals with findings include them too.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from midflight.adapters.runners import InlineRunner
from midflight.api.views import check_in_json, dump, participant_json, verdict_json
from midflight.api.webhook import add_webhook_route
from midflight.domain.models import (
    DirectiveResponse,
    JobKind,
    JobState,
    Model,
    Participant,
    Resolution,
    Role,
    Text,
)
from midflight.hooks.pre_push import SCRIPT as PRE_PUSH_HOOK
from midflight.ports import Clock, GitHub, JobRunner, Reviewer, Store
from midflight.services.check_in import CheckInService
from midflight.services.claims import ClaimService, ClaimSubmission, parse_review_subject
from midflight.services.directives import ACK_NOTE, DirectiveService
from midflight.services.errors import NotFound, PermissionDenied, ServiceError
from midflight.services.escalations import EscalationService
from midflight.services.participants import ParticipantService
from midflight.services.plans import PlanDraft, PlanService
from midflight.services.sync import SyncService
from midflight.services.verification import VerificationService

# Services ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Services:
    store: Store
    claims: ClaimService
    plans: PlanService
    participants: ParticipantService
    check_ins: CheckInService
    directives: DirectiveService
    escalations: EscalationService
    sync: SyncService
    verifications: VerificationService


def build_services(
    store: Store,
    clock: Clock,
    reviewer: Reviewer | None = None,
    runner: JobRunner | None = None,
    github: GitHub | None = None,
) -> Services:
    """Wire every service to one store. Jobs run inline unless a runner is given (on
    AWS, `StreamRunner`: the worker Lambda runs them)."""
    inline = InlineRunner() if runner is None else None
    runner = runner or inline
    assert runner is not None
    claims = ClaimService(store, runner, clock, reviewer)
    sync = SyncService(store, clock, runner)
    verifications = VerificationService(store, clock, runner, sync, github, reviewer)
    if inline is not None:
        inline.register(JobKind.CLAIM_REVIEW, claims.run_review)
        inline.register(JobKind.VERIFICATION, verifications.run)
    return Services(
        store=store,
        claims=claims,
        plans=PlanService(store, clock, runner),
        participants=ParticipantService(store, clock),
        check_ins=CheckInService(store, clock, claims),
        directives=DirectiveService(store, clock),
        escalations=EscalationService(store, clock, runner),
        sync=sync,
        verifications=verifications,
    )


# Request bodies ------------------------------------------------------------------------


class RegisterRequest(Model):
    id: Text
    role: Role
    developer_name: Text
    agent_name: str | None = None


class ReasonRequest(Model):
    reason: Text


class OptionalReason(Model):
    reason: str | None = None


class CheckInRequest(Model):
    task_id: str | None = None


class AckRequest(Model):
    response: DirectiveResponse
    note: str | None = None


class ResolveRequest(Model):
    resolution: Resolution
    reason: Text


# App -----------------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def create_app(
    services: Services, lifespan: Any = None, webhook_secret: str | None = None
) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Midflight",
        version="0.1.0",
        description="Keeps a small team's coding agents aligned while they work.",
    )

    @app.exception_handler(ServiceError)
    def service_error(_request: Request, error: ServiceError) -> JSONResponse:
        body: dict[str, Any] = {
            "error": type(error).__name__,
            "detail": error.detail,
            "hint": error.hint,
        }
        if error.findings:
            body["findings"] = [dump(f) for f in error.findings]
        return JSONResponse(status_code=error.status, content=body)

    @app.exception_handler(HTTPException)
    def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": "Unauthorized", "detail": error.detail, "hint": _AUTH_HINT},
            headers=error.headers,
        )

    def caller(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> Participant:
        if credentials is None:
            raise HTTPException(401, "missing bearer token", {"WWW-Authenticate": "Bearer"})
        participant = services.participants.authenticate(credentials.credentials)
        if participant is None:
            raise HTTPException(401, "invalid or revoked token", {"WWW-Authenticate": "Bearer"})
        return participant

    Caller = Annotated[Participant, Depends(caller)]

    def in_project(pid: str, actor: Participant) -> None:
        if actor.project_id != pid:
            raise PermissionDenied(f"your token is for project {actor.project_id}, not {pid}")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Participants (UC-01)

    @app.post("/projects/{pid}/participants", status_code=status.HTTP_201_CREATED)
    def register(pid: str, body: RegisterRequest, actor: Caller) -> dict[str, Any]:
        in_project(pid, actor)
        participant, token = services.participants.register(
            actor,
            participant_id=body.id,
            role=body.role,
            developer_name=body.developer_name,
            agent_name=body.agent_name,
        )
        return {
            "participant": participant_json(participant),
            "token": token,
            "note": "This token is shown once. Only its hash is stored.",
        }

    @app.post("/participants/{participant_id}/revoke")
    def revoke(participant_id: str, body: ReasonRequest, actor: Caller) -> dict[str, Any]:
        return participant_json(services.participants.revoke(actor, participant_id, body.reason))

    # Plans (UC-03)

    @app.get("/projects/{pid}/plans/current")
    def current_plan(pid: str, actor: Caller) -> Any:
        in_project(pid, actor)
        return dump(services.plans.current(pid))

    @app.get("/projects/{pid}/plans/{version}")
    def plan(pid: str, version: int, actor: Caller) -> Any:
        in_project(pid, actor)
        return dump(services.plans.get(pid, version))

    @app.post("/projects/{pid}/plans", status_code=status.HTTP_201_CREATED)
    def propose_plan(pid: str, body: PlanDraft, actor: Caller) -> Any:
        in_project(pid, actor)
        return dump(services.plans.propose(actor, body))

    @app.post("/projects/{pid}/plans/{version}/approve")
    def approve_plan(pid: str, version: int, body: ReasonRequest, actor: Caller) -> Any:
        in_project(pid, actor)
        return dump(services.plans.approve(actor, version, body.reason))

    # Claims (UC-04, UC-06)

    @app.post("/projects/{pid}/claims", status_code=status.HTTP_202_ACCEPTED)
    def submit_claim(pid: str, body: ClaimSubmission, actor: Caller) -> dict[str, Any]:
        in_project(pid, actor)
        result = services.claims.submit(actor, body)
        return {
            "claim_id": result.claim_id,
            "revision": result.revision,
            "job_id": result.job_id,
            "state": result.state.value,
        }

    @app.post("/claims/{claim_id}/withdraw")
    def withdraw(claim_id: str, body: OptionalReason, actor: Caller) -> Any:
        return dump(services.claims.withdraw(actor, claim_id, body.reason))

    @app.post("/claims/{claim_id}/close")
    def close(claim_id: str, body: OptionalReason, actor: Caller) -> Any:
        return dump(services.claims.close(actor, claim_id, body.reason))

    @app.get("/claims/{claim_id}")
    def claim(claim_id: str, actor: Caller) -> dict[str, Any]:
        latest = services.store.get_claim(claim_id)
        if latest is None or latest.project_id != actor.project_id:
            raise NotFound(f"no claim {claim_id}")
        return {
            "claim": dump(latest),
            "verdict": verdict_json(services.claims.verdict(claim_id)),
            "history": [dump(c) for c in services.store.claim_history(claim_id)],
        }

    # Jobs (UC-04, UC-14)

    @app.get("/jobs/{job_id}")
    def job(job_id: str, actor: Caller) -> dict[str, Any]:
        found = services.store.get_job(job_id)
        if found is None or found.project_id != actor.project_id:
            raise NotFound(f"no job {job_id}")
        verdict = None
        done = found.state in (JobState.SUCCEEDED, JobState.FAILED)
        if found.kind is JobKind.CLAIM_REVIEW and done:
            claim_id, revision = parse_review_subject(found.subject_id)
            verdict = verdict_json(services.claims.verdict(claim_id, revision))
        return {"job": dump(found), "verdict": verdict}

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str, actor: Caller) -> Any:
        return dump(services.claims.retry_review(actor, job_id))

    # Check-in and directives (UC-07, UC-09, UC-16)

    @app.post("/projects/{pid}/check-in")
    def check_in(pid: str, body: CheckInRequest, actor: Caller) -> dict[str, Any]:
        in_project(pid, actor)
        return check_in_json(services.check_ins.check_in(actor, body.task_id))

    @app.post("/projects/{pid}/push-check")
    def push_check(pid: str, body: CheckInRequest, actor: Caller) -> PlainTextResponse:
        """For the pre-push hook: 200 if ready to push, 409 with the reasons if not."""
        in_project(pid, actor)
        reply = services.check_ins.check_in(actor, body.task_id)
        if reply.ready_to_push:
            return PlainTextResponse(f"Midflight: {reply.task.id} is ready to push.\n")
        lines = [f"Midflight: {reply.task.id} isn't ready to push:"]
        lines += [f"  - {blocker}" for blocker in reply.push_blockers]
        lines += [f"  {d.id}: {d.requested_adjustment}" for d in reply.directives if d.blocking]
        lines.append("Ask your agent to call check_in, deal with the above, and push again.")
        return PlainTextResponse("\n".join(lines) + "\n", status_code=409)

    @app.get("/hook/pre-push", include_in_schema=False)
    def pre_push_hook() -> PlainTextResponse:
        return PlainTextResponse(PRE_PUSH_HOOK)

    @app.post("/directives/{directive_id}/ack")
    def acknowledge(directive_id: str, body: AckRequest, actor: Caller) -> dict[str, Any]:
        answered = services.directives.acknowledge(actor, directive_id, body.response, body.note)
        return {"directive": dump(answered), "note": ACK_NOTE}

    # Escalations (UC-13)

    @app.post("/escalations/{escalation_id}/resolve")
    def resolve_escalation(escalation_id: str, body: ResolveRequest, actor: Caller) -> Any:
        return dump(
            services.escalations.resolve(actor, escalation_id, body.resolution, body.reason)
        )

    # Dashboard and audit (UC-14)

    @app.get("/projects/{pid}/state")
    def state(pid: str, actor: Caller) -> dict[str, Any]:
        in_project(pid, actor)
        store = services.store
        project = store.get_project(pid)
        if project is None:
            raise NotFound(f"no project {pid}")
        plan = store.get_plan(pid, project.current_plan_version or 0)
        return {
            "project": dump(project),
            "plan": dump(plan) if plan else None,
            "participants": [participant_json(p) for p in store.list_participants(pid)],
            "claims": [dump(c) for c in store.list_claims(pid)],
            "directives": [dump(d) for d in store.list_directives(pid)],
            "escalations": [dump(e) for e in store.list_escalations(pid)],
            "verifications": [dump(v) for v in store.list_verifications(pid)],
            "jobs": [dump(j) for j in store.list_jobs(pid)],
        }

    @app.get("/projects/{pid}/audit")
    def audit(pid: str, actor: Caller, entity_id: str | None = None) -> list[Any]:
        in_project(pid, actor)
        return [dump(e) for e in services.store.list_audit(pid, entity_id)]

    # GitHub (UC-10)
    add_webhook_route(app, services.verifications, webhook_secret)

    return app


_AUTH_HINT = "Send Authorization: Bearer <token>. Tokens come from the lead (UC-01)."
