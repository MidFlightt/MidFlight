"""Turning findings into a claim verdict (UC-05 step 5). Pure: no I/O.

Application code decides; the model only proposes findings (INV-01).
"""

from __future__ import annotations

from collections.abc import Sequence

from midflight.domain.models import Claim, ClaimState, Finding, FindingKind


def decide_claim(claim: Claim, findings: Sequence[Finding], *, stale: bool) -> ClaimState:
    """The state a reviewed claim moves to.

    - Missing details keep it a `draft` (D5).
    - A conflict between people's requirements goes to the lead (INV-11).
    - Any other blocking finding asks the agent to revise.
    - No usable review, or stale GitHub data, holds it `pending`: never approved
      without a review (INV-01), and no approvals while stale (INV-09).
    """
    if not claim.is_complete:
        return ClaimState.DRAFT
    blocking = [f for f in findings if f.blocking]
    if any(f.kind is FindingKind.REQUIREMENT_CONFLICT for f in blocking):
        return ClaimState.HUMAN_REVIEW_REQUIRED
    if any(f.kind is not FindingKind.REVIEWER_UNAVAILABLE for f in blocking):
        return ClaimState.NEEDS_REVISION
    if blocking or stale:
        return ClaimState.PENDING
    return ClaimState.APPROVED
