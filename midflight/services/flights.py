"""Lead-authorized fresh coordination state for an existing repository."""

import hashlib

from midflight.domain.models import Participant, PlanStatus, Project, Role
from midflight.ports import Clock, Store
from midflight.services.audit import audit_event
from midflight.services.errors import InvalidRequest, PermissionDenied, StateConflict
from midflight.services.projects import new_join_code


class FlightService:
    def __init__(self, store: Store, clock: Clock) -> None:
        self.store, self.clock = store, clock

    def start(
        self,
        actor: Participant,
        request_id: str,
        expected_coord_rev: int,
        *,
        lead_token_hash: str | None = None,
        source_plan_version: int | None = None,
    ) -> Project:
        saved = self.store.get_participant(actor.id)
        if (
            actor.role is not Role.LEAD
            or saved is None
            or not saved.active
            or saved.role is not Role.LEAD
            or saved.project_id != actor.project_id
        ):
            raise PermissionDenied("Only the active flight lead can start a new flight.")
        if not request_id.strip() or len(request_id) > 128:
            raise InvalidRequest("Use a nonempty request_id of at most 128 characters.")
        old = self.store.get_project(actor.project_id)
        if old is None or old.lead_id != actor.id:
            raise PermissionDenied("Only the flight lead can start a new flight.")
        if old.archived_at:
            if old.flight_request_id == request_id:
                return self.store.get_project(old.successor_project_id)
            raise StateConflict("This flight is already archived.")
        if old.coord_rev != expected_coord_rev:
            raise StateConflict("Flight changed; read its state and retry.")
        digest = hashlib.sha256(f"{old.id}:{request_id}".encode()).hexdigest()[:16]
        new_id = f"flight-{digest}"
        members = [m for m in self.store.list_participants(old.id) if m.active]
        if len(members) > 25:
            raise InvalidRequest("New flights support at most 25 active members.")
        if any(not m.user_id for m in members):
            raise InvalidRequest(
                "New flights require signed-in memberships; migrate token-only members first."
            )
        users = {m.id: self.store.get_user(m.user_id) for m in members}
        if any(user is None for user in users.values()):
            raise InvalidRequest("A member's sign-in record is missing.")
        mapping = {m.id: f"{new_id}.{users[m.id].github_login.lower()}" for m in members}
        if len(set(mapping.values())) != len(members):
            raise InvalidRequest("Members must have distinct names.")
        copied = [
            m.model_copy(
                update=dict(
                    id=mapping[m.id],
                    project_id=new_id,
                    token_hash=lead_token_hash if m.id == actor.id else None,
                    last_check_in_at=None,
                    last_check_in_rev=None,
                )
            )
            for m in members
        ]
        version = source_plan_version or old.current_plan_version
        plan = self.store.get_plan(old.id, version) if version else None
        if version and (plan is None or plan.status is not PlanStatus.APPROVED):
            raise InvalidRequest("The source plan must exist and be approved.")
        if plan:
            if any(t.owner not in mapping for t in plan.tasks):
                raise InvalidRequest(
                    "Reassign tasks owned by removed members before starting a flight."
                )
            plan = plan.model_copy(
                update=dict(
                    project_id=new_id,
                    version=1,
                    tasks=[t.model_copy(update={"owner": mapping[t.owner]}) for t in plan.tasks],
                    contracts=[c.model_copy(update={"version": 1}) for c in plan.contracts],
                    approved_by=mapping[actor.id],
                    approved_at=self.clock.now(),
                    change_reason=f"Lead started a fresh flight from approved plan v{version}.",
                    changed_ids=[],
                )
            )
        successor = Project(
            id=new_id,
            name=old.name,
            repository=old.repository,
            github_installation_id=old.github_installation_id,
            created_by=actor.user_id,
            lead_id=mapping[actor.id],
            participant_ids=list(mapping.values()),
            join_code=new_join_code(),
            current_plan_version=1 if plan else None,
            sync_state=old.sync_state,
            sync_reason=old.sync_reason,
            last_synced_at=old.last_synced_at,
        )
        archived = old.model_copy(
            update=dict(
                archived_at=self.clock.now(),
                successor_project_id=new_id,
                flight_request_id=request_id,
            )
        )
        events = [
            audit_event(
                self.store,
                self.clock,
                project_id=pid,
                actor=actor.id if pid == old.id else mapping[actor.id],
                action=action,
                entity_ids=[old.id, new_id],
                reason="Lead started a fresh flight; previous history retained.",
                correlation_id=new_id,
                idempotency_key=f"flight:{old.id}:{request_id}",
                versions={"previous_coord_rev": old.coord_rev},
            )
            for pid, action in [(old.id, "flight.archived"), (new_id, "flight.started")]
        ]
        try:
            self.store.replace_flight(archived, successor, copied, plan, events)
        except StateConflict:
            current = self.store.get_project(old.id)
            if current.archived_at and current.flight_request_id == request_id:
                return self.store.get_project(current.successor_project_id)
            raise
        return successor
