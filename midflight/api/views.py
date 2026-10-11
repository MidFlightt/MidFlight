"""The JSON shapes Midflight returns, shared by the REST API and the MCP servers.

The MCP servers turn these into text with `midflight.mcp.replies`, so an agent reads the
same thing whether it came through REST, the local adapter, or the hosted connector.
"""

from typing import Any

from midflight.domain.models import Participant
from midflight.services.check_in import CheckIn
from midflight.services.claims import Verdict
from midflight.services.decisions import decided_by


def dump(model: Any) -> Any:
    return model.model_dump(mode="json")


def participant_json(p: Participant) -> dict[str, Any]:
    # Never return the token hash (INV-12).
    return p.model_dump(mode="json", exclude={"token_hash"})


def verdict_json(v: Verdict) -> dict[str, Any]:
    return {
        "claim_id": v.claim_id,
        "revision": v.revision,
        "state": v.state.value,
        "review_complete": v.review_complete,
        "findings": [dump(f) for f in v.findings],
        "contracts": [dump(c) for c in v.contracts],
        "directives": [dump(d) for d in v.directives],
        "note": v.note,
    }


def check_in_json(c: CheckIn) -> dict[str, Any]:
    return {
        "plan_version": c.plan_version,
        "changed": c.changed,
        "task": dump(c.task),
        "requirements": [dump(r) for r in c.requirements],
        "contracts": [dump(k) for k in c.contracts],
        "claim": verdict_json(c.claim) if c.claim else None,
        "directives": [dump(d) for d in c.directives],
        "delivered_now": list(c.delivered_now),
        "stale": c.stale,
        "stale_reason": c.stale_reason,
        "ready_to_push": c.ready_to_push,
        "push_blockers": list(c.push_blockers),
        # `seen`: the reply that gave out the caller's `since` marker already held it (D34).
        "marker": c.marker,
        "since_read": c.since_read,
        "plan_seen": c.plan_seen,
        "plan_changed_ids": None if c.plan_changed_ids is None else list(c.plan_changed_ids),
        "assumed_by_others": [
            {
                "task_id": a.task_id,
                "claim_id": a.claim_id,
                "text": a.text,
                "seen": a in c.seen_assumptions,
            }
            for a in c.assumed_by_others
        ],
        "escalations": [
            {"id": e.id, "claim_ids": e.claim_ids, "explanation": e.explanation}
            for e in c.escalations
        ],
        "you_decide": c.you_decide,
        "decisions": [
            {
                "id": d.id,
                "how": decided_by(d),
                "reason": d.reason,
                "claim_ids": d.claim_ids,
                "seen": d.id in c.seen_decision_ids,
            }
            for d in c.decisions
        ],
    }
