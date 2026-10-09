"""The JSON shapes Midflight returns, shared by the REST API and the MCP servers.

The MCP servers turn these into text with `midflight.mcp.replies`, so an agent reads the
same thing whether it came through REST, the local adapter, or the hosted connector.
"""

from typing import Any

from midflight.domain.models import Participant
from midflight.services.check_in import CheckIn
from midflight.services.claims import Verdict


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
    }
