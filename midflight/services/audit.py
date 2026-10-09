"""Building audit events. Every state change saves one in the same commit (INV-13)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from midflight.domain.models import AuditEvent
from midflight.ports import Clock, Store


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:12]


def audit_event(
    store: Store,
    clock: Clock,
    *,
    project_id: str,
    actor: str,
    action: str,
    entity_ids: Sequence[str],
    reason: str,
    correlation_id: str,
    idempotency_key: str,
    versions: Mapping[str, int | str] | None = None,
) -> AuditEvent:
    return AuditEvent(
        id=store.next_id(project_id, "A"),
        project_id=project_id,
        actor=actor,
        action=action,
        entity_ids=list(entity_ids),
        versions=dict(versions or {}),
        reason=reason,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        timestamp=clock.now(),
    )
