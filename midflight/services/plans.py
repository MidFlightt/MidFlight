"""Proposing and approving plan versions (UC-03, UC-08). Only the lead does either.

A proposed plan is a draft: it can be replaced until it's approved. Approval makes it
immutable and current, and advances coord_rev so reviews in flight rerun against it.

Approving version 2 or later also tells the affected tasks, in the same commit (UC-08):

- each affected task gets one `plan_change` directive (one per plan version and task,
  because a version is approved once);
- the task's older directives still `queued` or `delivered` are superseded (D13);
- the task's approved claims go back to `pending` and are reviewed again against the
  new version, so no affected task keeps an approval based on the old one.

Tasks with no link to the change get nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from midflight.domain.impact import affected_tasks, changed_ids
from midflight.domain.models import (
    AuditEvent,
    ClaimState,
    Contract,
    Directive,
    DirectiveSource,
    DirectiveState,
    Entity,
    Job,
    JobKind,
    Model,
    Participant,
    Plan,
    PlanStatus,
    Project,
    Requirement,
    Role,
)
from midflight.domain.models import Task as PlanTask
from midflight.domain.rules import validate_plan
from midflight.domain.states import SUPERSEDABLE_DIRECTIVE_STATES, move_claim, move_directive
from midflight.ports import Clock, Commit, JobRunner, RevisionConflict, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.claims import review_subject
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict

MAX_APPROVE_RUNS = 3


class PlanDraft(Model):
    """What the lead sends to propose the next plan version."""

    requirements: list[Requirement]
    tasks: list[PlanTask]
    contracts: list[Contract]


@dataclass
class Propagation:
    """What approving a plan change adds to the approval's commit (UC-08)."""

    puts: list[Entity] = field(default_factory=list)
    audit: list[AuditEvent] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)


class PlanService:
    def __init__(self, store: Store, clock: Clock, runner: JobRunner | None = None) -> None:
        self._store = store
        self._clock = clock
        self._runner = runner

    def current(self, project_id: str) -> Plan:
        project = self._store.get_project(project_id)
        if project is None:
            raise NotFound(f"no project {project_id}")
        if project.current_plan_version is None:
            raise NotFound("no plan has been approved yet")
        plan = self._store.get_plan(project_id, project.current_plan_version)
        assert plan is not None
        return plan

    def get(self, project_id: str, version: int) -> Plan:
        plan = self._store.get_plan(project_id, version)
        if plan is None:
            raise NotFound(f"no plan v{version}")
        return plan

    def propose(self, lead: Participant, draft: PlanDraft) -> Plan:
        """Save the next version as a proposal. Nothing is saved if it's invalid (2a)."""
        _require_lead(lead)
        project = self._store.get_project(lead.project_id)
        if project is None:
            raise NotFound(f"no project {lead.project_id}")
        version = (project.current_plan_version or 0) + 1
        current = (
            self._store.get_plan(project.id, project.current_plan_version)
            if project.current_plan_version
            else None
        )
        contracts = [c.model_copy(update={"version": version}) for c in draft.contracts]
        plan = Plan(
            project_id=project.id,
            version=version,
            status=PlanStatus.PROPOSED,
            requirements=draft.requirements,
            tasks=draft.tasks,
            contracts=contracts,
        )
        problems = validate_plan(plan)
        if problems:
            raise InvalidRequest(
                "the plan is not valid; nothing was saved", "Fix: " + "; ".join(problems) + "."
            )
        plan = plan.model_copy(update={"changed_ids": changed_ids(current, plan)})
        key = f"propose:{project.id}:v{version}:{new_correlation_id()}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor=lead.id,
            action="plan.proposed",
            entity_ids=[f"plan:v{version}", *plan.changed_ids],
            reason=f"changes {', '.join(plan.changed_ids) or 'nothing yet (first plan)'}",
            correlation_id=new_correlation_id(),
            idempotency_key=key,
            versions={"plan": version},
        )
        self._store.commit(
            Commit(project_id=project.id, idempotency_key=key, puts=[plan], audit=[event])
        )
        return plan

    def approve(self, lead: Participant, version: int, reason: str) -> Plan:
        """Make a proposed version current. Fails if another version was approved first.

        A claim saved at the same moment only means a reread: the approval retries.
        """
        _require_lead(lead)
        if not reason.strip():
            raise InvalidRequest("approving a plan needs a reason")
        for _ in range(MAX_APPROVE_RUNS):
            project = self._store.get_project(lead.project_id)
            if project is None:
                raise NotFound(f"no project {lead.project_id}")
            plan = self.get(project.id, version)
            if plan.status is PlanStatus.APPROVED:
                raise StateConflict(f"plan v{version} is already approved")
            if version != (project.current_plan_version or 0) + 1:
                raise StateConflict(
                    f"plan v{project.current_plan_version} was approved after this draft",
                    "Propose the change again on top of the current version (UC-03 4a).",
                )
            approved = Plan.model_validate(
                plan.model_dump()
                | {
                    "status": PlanStatus.APPROVED,
                    "approved_by": lead.id,
                    "approved_at": self._clock.now(),
                    "change_reason": reason,
                }
            )
            current = project.model_copy(update={"current_plan_version": version})
            key = f"approve:{project.id}:v{version}"
            event = audit_event(
                self._store,
                self._clock,
                project_id=project.id,
                actor=lead.id,
                action="plan.approved",
                entity_ids=[f"plan:v{version}", *plan.changed_ids],
                reason=reason,
                correlation_id=new_correlation_id(),
                idempotency_key=key,
                versions={"plan": version},
            )
            change = self._propagation(project, approved, lead)
            try:
                self._store.commit(
                    Commit(
                        project_id=project.id,
                        idempotency_key=key,
                        puts=[approved, current, *change.puts],
                        audit=[event, *change.audit],
                        expected_coord_rev=project.coord_rev,
                        bump_coord_rev=True,
                    )
                )
            except RevisionConflict:
                continue
            for job in change.jobs:
                self._submit(job)
            return approved
        raise StateConflict("the project kept changing while approving", "Approve again.")

    def _propagation(self, project: Project, plan: Plan, lead: Participant) -> Propagation:
        """Directives, superseded directives, and re-reviews for the affected tasks."""
        change = Propagation()
        if project.current_plan_version is None:
            return change  # the first plan changes nothing anyone built on
        previous = self._store.get_plan(project.id, project.current_plan_version)
        assert previous is not None
        affected = affected_tasks(previous, plan, plan.changed_ids)
        if not affected:
            return change
        now = self._clock.now()
        correlation_id = new_correlation_id()
        directives = self._store.list_directives(project.id)
        claims = self._store.list_claims(project.id)
        touched: list[str] = []
        for task_id, ids in affected.items():
            task = plan.task(task_id)
            assert task is not None
            change.puts += [
                move_directive(d, DirectiveState.SUPERSEDED)
                for d in directives
                if d.task_id == task_id and d.state in SUPERSEDABLE_DIRECTIVE_STATES
            ]
            directive = Directive(
                id=self._store.next_id(project.id, "D"),
                project_id=project.id,
                source=DirectiveSource.PLAN_CHANGE,
                task_id=task_id,
                recipient_id=task.owner,
                plan_version=plan.version,
                changed_ids=ids,
                requested_adjustment=_adjustment(plan, task_id, ids),
                reason=plan.change_reason or "plan changed",
                created_at=now,
            )
            change.puts.append(directive)
            touched.append(directive.id)
            for claim in claims:
                if claim.task_id != task_id or claim.state is not ClaimState.APPROVED:
                    continue
                job = Job(
                    id=self._store.next_id(project.id, "J"),
                    project_id=project.id,
                    kind=JobKind.CLAIM_REVIEW,
                    subject_id=review_subject(claim.id, claim.revision),
                    idempotency_key=f"revalidate:{claim.id}:{claim.revision}:v{plan.version}",
                    correlation_id=correlation_id,
                    created_at=now,
                    updated_at=now,
                )
                change.puts += [move_claim(claim, ClaimState.PENDING), job]
                change.jobs.append(job)
                touched.append(claim.id)
        change.audit.append(
            audit_event(
                self._store,
                self._clock,
                project_id=project.id,
                actor=lead.id,
                action="plan.propagated",
                entity_ids=touched,
                reason=f"plan v{plan.version} affects {', '.join(affected)}",
                correlation_id=correlation_id,
                idempotency_key=f"propagate:{project.id}:v{plan.version}",
                versions={"plan": plan.version},
            )
        )
        return change

    def _submit(self, job: Job) -> None:
        if self._runner is not None:
            self._runner.submit(job)


def _adjustment(plan: Plan, task_id: str, ids: list[str]) -> str:
    """What changed for this task, in words an agent can act on."""
    parts = []
    for i in ids:
        contract = plan.contract(i)
        if contract is not None:
            fields = ", ".join(f"{name}: {kind}" for name, kind in contract.fields.items())
            parts.append(f"contract {i} is now {{{fields}}}")
        elif plan.requirement(i) is not None:
            parts.append(f"requirement {i} changed")
        elif i == task_id:
            parts.append(f"your task {i} changed")
        else:
            parts.append(f"{i} was removed")
    return (
        f"Plan v{plan.version}: {'; '.join(parts)}. Call check_in, then submit a revised "
        f"claim against plan v{plan.version} before building on this."
    )


def _require_lead(actor: Participant) -> None:
    if actor.role is not Role.LEAD:
        raise PermissionDenied("only the lead can propose or approve plans (INV-08)")
