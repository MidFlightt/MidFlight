"""Proposing and approving plan versions (UC-03). Only the lead does either (INV-08).

A proposed plan is a draft: it can be replaced until it's approved. Approval makes it
immutable and current, and advances coord_rev so reviews in flight rerun against it.
Telling affected tasks about the change is UC-08 (task S-6).
"""

from __future__ import annotations

from midflight.domain.impact import changed_ids
from midflight.domain.models import (
    Contract,
    Model,
    Participant,
    Plan,
    PlanStatus,
    Requirement,
    Role,
)
from midflight.domain.models import Task as PlanTask
from midflight.domain.rules import validate_plan
from midflight.ports import Clock, Commit, RevisionConflict, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict

MAX_APPROVE_RUNS = 3


class PlanDraft(Model):
    """What the lead sends to propose the next plan version."""

    requirements: list[Requirement]
    tasks: list[PlanTask]
    contracts: list[Contract]


class PlanService:
    def __init__(self, store: Store, clock: Clock) -> None:
        self._store = store
        self._clock = clock

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
            try:
                self._store.commit(
                    Commit(
                        project_id=project.id,
                        idempotency_key=key,
                        puts=[approved, current],
                        audit=[event],
                        expected_coord_rev=project.coord_rev,
                        bump_coord_rev=True,
                    )
                )
            except RevisionConflict:
                continue
            return approved
        raise StateConflict("the project kept changing while approving", "Approve again.")


def _require_lead(actor: Participant) -> None:
    if actor.role is not Role.LEAD:
        raise PermissionDenied("only the lead can propose or approve plans (INV-08)")
