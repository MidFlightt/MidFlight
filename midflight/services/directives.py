"""An agent's answer to a directive (UC-09). `acknowledged` means received (INV-10)."""

from __future__ import annotations

from midflight.domain.models import Directive, DirectiveResponse, DirectiveState, Participant
from midflight.domain.states import IllegalTransition, respond
from midflight.ports import Clock, Commit, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.errors import NotFound, PermissionDenied, StateConflict

ACK_NOTE = (
    "Recorded. Acknowledged means received, not implemented: midflight/verify checks "
    "the code. If this changes your work, submit a revised claim before building on it."
)


class DirectiveService:
    def __init__(self, store: Store, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def acknowledge(
        self,
        actor: Participant,
        directive_id: str,
        response: DirectiveResponse,
        note: str | None = None,
    ) -> Directive:
        directive = self._store.get_directive(directive_id)
        if directive is None or directive.project_id != actor.project_id:
            raise NotFound(f"no directive {directive_id}")
        if directive.recipient_id != actor.id:
            raise PermissionDenied(f"directive {directive_id} is for another agent")
        if directive.state is DirectiveState.SUPERSEDED:
            raise StateConflict(
                f"directive {directive_id} was replaced by a newer one (UC-09 1a)",
                "Check in to get the current directive.",
            )
        try:
            answered = respond(directive, response, note)
        except IllegalTransition as error:
            raise StateConflict(str(error), "Check in to see the directive's state.") from error
        key = f"ack:{directive_id}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=actor.project_id,
            actor=actor.id,
            action=f"directive.{response}",
            entity_ids=[directive_id, directive.task_id],
            reason=note or str(response),
            correlation_id=new_correlation_id(),
            idempotency_key=key,
            versions={"plan": directive.plan_version},
        )
        self._store.commit(
            Commit(
                project_id=actor.project_id,
                idempotency_key=key,
                puts=[answered],
                audit=[event],
            )
        )
        return answered
