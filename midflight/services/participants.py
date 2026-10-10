"""Participants and their bearer tokens (UC-01, INV-08, INV-12).

A token is shown once, when it's issued. Only its SHA-256 hash is stored, so a leaked
database doesn't leak working tokens. Connector users sign in with GitHub instead;
they get a token only for the pre-push hook (`issue_hook_token`, D20).
"""

from __future__ import annotations

import hashlib
import secrets

from midflight.domain.models import Participant, Role
from midflight.ports import Clock, Commit, Store
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied

TOKEN_PREFIX = "mf_"


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ParticipantService:
    def __init__(self, store: Store, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def authenticate(self, token: str) -> Participant | None:
        """The active participant holding `token`, or None (the API answers 401)."""
        participant = self._store.find_participant_by_token_hash(hash_token(token))
        if participant is None or not participant.active:
            return None
        return participant

    def register(
        self,
        lead: Participant,
        *,
        participant_id: str,
        role: Role,
        developer_name: str,
        agent_name: str | None = None,
    ) -> tuple[Participant, str]:
        """Add a participant and return it with its token. The token is never stored."""
        _require_lead(lead)
        project = self._store.get_project(lead.project_id)
        if project is None:
            raise NotFound(f"no project {lead.project_id}")
        if self._store.get_participant(participant_id) is not None:
            raise InvalidRequest(f"participant {participant_id} already exists")
        token = new_token()
        try:
            participant = Participant(
                id=participant_id,
                project_id=project.id,
                role=role,
                developer_name=developer_name,
                agent_name=agent_name,
                token_hash=hash_token(token),
            )
        except ValueError as error:
            raise InvalidRequest(str(error)) from error
        updated = project.model_copy(
            update={"participant_ids": [*project.participant_ids, participant_id]}
        )
        key = f"register:{participant_id}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor=lead.id,
            action="participant.registered",
            entity_ids=[participant_id],
            reason=f"{developer_name} / {agent_name or role}",
            correlation_id=new_correlation_id(),
            idempotency_key=key,
        )
        self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=key,
                puts=[participant, updated],
                audit=[event],
            )
        )
        return participant, token

    def revoke(self, lead: Participant, participant_id: str, reason: str) -> Participant:
        _require_lead(lead)
        participant = self._store.get_participant(participant_id)
        if participant is None or participant.project_id != lead.project_id:
            raise NotFound(f"no participant {participant_id}")
        if not participant.active:
            return participant
        revoked = participant.model_copy(update={"revoked_at": self._clock.now()})
        key = f"revoke:{participant_id}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=lead.project_id,
            actor=lead.id,
            action="participant.revoked",
            entity_ids=[participant_id],
            reason=reason,
            correlation_id=new_correlation_id(),
            idempotency_key=key,
        )
        self._store.commit(
            Commit(project_id=lead.project_id, idempotency_key=key, puts=[revoked], audit=[event])
        )
        return revoked

    def issue_hook_token(self, actor: Participant) -> str:
        """A personal token for the pre-push hook (UC-16, D20). Replaces any earlier one."""
        participant = self._store.get_participant(actor.id)
        if participant is None or not participant.active:
            raise PermissionDenied("you were removed from this project")
        token = new_token()
        updated = Participant.model_validate(
            participant.model_dump() | {"token_hash": hash_token(token)}
        )
        key = f"hook-token:{actor.id}:{new_correlation_id()}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=actor.project_id,
            actor=actor.id,
            action="participant.hook_token",
            entity_ids=[actor.id],
            reason="issued a pre-push hook token (any earlier one stops working)",
            correlation_id=new_correlation_id(),
            idempotency_key=key,
        )
        self._store.commit(
            Commit(project_id=actor.project_id, idempotency_key=key, puts=[updated], audit=[event])
        )
        return token


def _require_lead(actor: Participant) -> None:
    if actor.role is not Role.LEAD:
        raise PermissionDenied("only the lead can do this (INV-08)")
