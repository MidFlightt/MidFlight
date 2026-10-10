"""Checking the AI reviewer's reply before anything uses it (INV-01, INV-07).

The reviewer returns raw JSON. A reply is used only if every finding fits the
`Finding` schema, comes from the reviewer, and cites only ids that exist. Otherwise
the whole reply is discarded: one bad finding means none of it is trusted.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from pydantic import ValidationError

from midflight.domain.models import (
    Claim,
    Evidence,
    EvidenceKind,
    Finding,
    FindingKind,
    FindingSeverity,
    FindingSource,
)


def parse_reviewer_findings(
    raw: Any, known_ids: Collection[str], claim: Claim
) -> list[Finding] | None:
    """The reviewer's findings, re-numbered for this claim revision, or None to discard.

    Accepts a list of findings or `{"findings": [...]}`.
    """
    items = raw.get("findings") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return None
    findings = []
    for n, item in enumerate(items, start=1):
        try:
            finding = Finding.model_validate(item)
        except ValidationError:
            return None
        if finding.source is not FindingSource.REVIEWER:
            return None
        if not set(finding.affected_ids) <= set(known_ids):
            return None
        findings.append(finding.model_copy(update={"id": f"{_prefix(claim)}:reviewer:{n}"}))
    return findings


def reviewer_unavailable(claim: Claim, reason: str) -> Finding:
    """Recorded when no usable review exists. Holds the claim; never approves it."""
    return Finding(
        id=f"{_prefix(claim)}:{FindingKind.REVIEWER_UNAVAILABLE}",
        kind=FindingKind.REVIEWER_UNAVAILABLE,
        severity=FindingSeverity.BLOCKING,
        source=FindingSource.RULE,
        affected_ids=[claim.id],
        evidence=[Evidence(kind=EvidenceKind.CLAIM, ref=f"{claim.id} rev {claim.revision}")],
        explanation=f"The AI review didn't complete ({reason}). The claim stays pending "
        "and is not approved.",
        proposed_correction="No change needed. Midflight retries the review, or the lead "
        "retries it from the dashboard.",
    )


def _prefix(claim: Claim) -> str:
    return f"{claim.id}/{claim.revision}"
