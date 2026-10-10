"""Deterministic claim and plan checks (task S-2, UC-05 step 2, UC-03 step 2).

Rules run before the AI reviewer. Each rule is a pure function that returns findings,
and every finding names its evidence and a proposed correction. Finding ids are built
from the claim revision and what was found, so rerunning a review produces the same
ids (NFR-02).

The flagship case: plan v1 says `checkout-response { total_cents: integer }`, and T2
claims it will read `total` as a number. `contract_fields` catches that before any
code is written and proposes `total_cents: integer` instead.
"""

from __future__ import annotations

import difflib
from collections import Counter
from collections.abc import Iterable, Sequence

from midflight.domain.models import (
    EXCERPT_LIMIT,
    Claim,
    Contract,
    Evidence,
    EvidenceKind,
    Finding,
    FindingKind,
    FindingSeverity,
    FindingSource,
    InterfaceUse,
    Plan,
)
from midflight.domain.states import ACTIVE_CLAIM_STATES

_BLOCKING = FindingSeverity.BLOCKING


def check_claim(claim: Claim, plan: Plan, other_claims: Iterable[Claim] = ()) -> list[Finding]:
    """Every rule finding for `claim` against the current approved `plan`.

    `other_claims` may include inactive claims and the claim itself; both are ignored.
    """
    others = [
        other
        for other in other_claims
        if other.id != claim.id and other.state in ACTIVE_CLAIM_STATES
    ]
    return [
        *stale_plan(claim, plan),
        *unknown_references(claim, plan),
        *incomplete_claim(claim),
        *unsupported_scope(claim, plan),
        *contract_fields(claim, plan),
        *duplicate_provider(claim, others),
        *file_overlap(claim, others),
    ]


def has_blocking(findings: Iterable[Finding]) -> bool:
    return any(f.blocking for f in findings)


# Claim rules ---------------------------------------------------------------------------


def stale_plan(claim: Claim, plan: Plan) -> list[Finding]:
    if claim.plan_version == plan.version:
        return []
    return [
        _finding(
            claim,
            FindingKind.STALE_PLAN,
            f"v{claim.plan_version}",
            affected=[claim.id],
            evidence=[_plan_evidence(plan, f"current version is v{plan.version}")],
            explanation=(
                f"The claim was written against plan v{claim.plan_version}, "
                f"but the current plan is v{plan.version}."
            ),
            correction=f"Re-read plan v{plan.version} and resubmit the claim against it.",
        )
    ]


def unknown_references(claim: Claim, plan: Plan) -> list[Finding]:
    findings = []
    if plan.task(claim.task_id) is None:
        findings.append(_unknown(claim, plan, "task", claim.task_id, [t.id for t in plan.tasks]))
    for requirement_id in claim.requirement_ids:
        if plan.requirement(requirement_id) is None:
            valid = [r.id for r in plan.requirements]
            findings.append(_unknown(claim, plan, "requirement", requirement_id, valid))
    for use in (*claim.provides, *claim.consumes):
        if plan.contract(use.contract_id) is None:
            valid = [c.id for c in plan.contracts]
            findings.append(_unknown(claim, plan, "contract", use.contract_id, valid))
    return findings


def incomplete_claim(claim: Claim) -> list[Finding]:
    missing = claim.missing_details()
    if not missing:
        return []
    return [
        _finding(
            claim,
            FindingKind.INCOMPLETE_CLAIM,
            "details",
            affected=[claim.id],
            evidence=[_claim_evidence(claim, "missing: " + "; ".join(missing))],
            explanation="The claim can't be approved until it says how it connects to "
            "other work and how it will be checked (D5, D12).",
            correction="Add " + "; ".join(missing) + ".",
        )
    ]


def unsupported_scope(claim: Claim, plan: Plan) -> list[Finding]:
    findings = []
    for use in claim.provides:
        contract = plan.contract(use.contract_id)
        if contract and contract.provider_task != claim.task_id:
            findings.append(
                _scope(
                    claim,
                    contract,
                    "provides",
                    f"Only {contract.provider_task} provides {contract.id}. Consume it "
                    "instead, or ask the lead to change the plan.",
                )
            )
    for use in claim.consumes:
        contract = plan.contract(use.contract_id)
        if contract and claim.task_id not in contract.consumer_tasks:
            consumers = ", ".join(contract.consumer_tasks) or "no task"
            findings.append(
                _scope(
                    claim,
                    contract,
                    "consumes",
                    f"The plan lists {consumers} as consumers of {contract.id}. Ask the "
                    "lead to add this task before building on it.",
                )
            )
    return findings


def contract_fields(claim: Claim, plan: Plan) -> list[Finding]:
    """Every field a claim reads or provides must exist with the contract's type.

    A consumer may read a subset of the fields. A provider must provide all of them.
    """
    findings = []
    for side, uses in (("consumes", claim.consumes), ("provides", claim.provides)):
        for use in uses:
            contract = plan.contract(use.contract_id)
            if contract is not None:
                findings.extend(_field_mismatches(claim, contract, use, side))
    for use in claim.provides:
        contract = plan.contract(use.contract_id)
        if contract is None:
            continue
        for name, field_type in contract.fields.items():
            if name not in use.fields:
                findings.append(
                    _field_finding(
                        claim,
                        contract,
                        FindingKind.CONTRACT_FIELD_MISSING,
                        name,
                        explanation=f"{contract.id} v{contract.version} requires "
                        f"`{name}: {field_type}`, but the claim doesn't provide it.",
                        correction=f"Provide `{name}: {field_type}`.",
                    )
                )
    return findings


def duplicate_provider(claim: Claim, others: Sequence[Claim]) -> list[Finding]:
    findings = []
    for use in claim.provides:
        rivals = sorted(
            o.id for o in others if any(p.contract_id == use.contract_id for p in o.provides)
        )
        if rivals:
            findings.append(
                _finding(
                    claim,
                    FindingKind.DUPLICATE_PROVIDER,
                    use.contract_id,
                    affected=[claim.id, use.contract_id, *rivals],
                    evidence=[
                        _claim_evidence(claim, f"provides {use.contract_id}"),
                        *(_evidence(EvidenceKind.CLAIM, r, "also provides") for r in rivals),
                    ],
                    explanation=f"{', '.join(rivals)} already provides {use.contract_id}. "
                    "A contract has exactly one provider.",
                    correction="Withdraw one of the claims, or consume the contract instead.",
                )
            )
    return findings


def file_overlap(claim: Claim, others: Sequence[Claim]) -> list[Finding]:
    """Shared files are worth knowing about, never a reason to block (INV-14)."""
    mine = set(claim.files)
    findings = []
    for other in sorted(others, key=lambda o: o.id):
        shared = sorted(mine.intersection(other.files))
        if shared:
            findings.append(
                _finding(
                    claim,
                    FindingKind.FILE_OVERLAP,
                    other.id,
                    severity=FindingSeverity.INFO,
                    affected=[claim.id, other.id],
                    evidence=[_claim_evidence(claim, "shared: " + ", ".join(shared))],
                    explanation=f"{other.id} ({other.task_id}) also expects to change "
                    f"{', '.join(shared)}. This doesn't block either claim.",
                    correction="Coordinate edits to the shared files if they touch the same lines.",
                )
            )
    return findings


# Plan validation (UC-03 step 2) --------------------------------------------------------


def validate_plan(plan: Plan) -> list[str]:
    """Every problem with a drafted plan, in plain words. Empty means it can be approved."""
    problems = []
    for label, ids in (
        ("requirement", [r.id for r in plan.requirements]),
        ("task", [t.id for t in plan.tasks]),
        ("contract", [c.id for c in plan.contracts]),
    ):
        for duplicate, count in Counter(ids).items():
            if count > 1:
                problems.append(f"{label} id {duplicate} is used {count} times")

    task_ids = {t.id for t in plan.tasks}
    requirement_ids = {r.id for r in plan.requirements}
    contract_ids = {c.id for c in plan.contracts}
    for task in plan.tasks:
        for requirement_id in task.requirement_ids:
            if requirement_id not in requirement_ids:
                problems.append(f"task {task.id} cites unknown requirement {requirement_id}")
        for contract_id in (*task.provides, *task.consumes):
            if contract_id not in contract_ids:
                problems.append(f"task {task.id} cites unknown contract {contract_id}")

    for contract in plan.contracts:
        if contract.provider_task not in task_ids:
            problems.append(
                f"contract {contract.id} names unknown provider task {contract.provider_task}"
            )
        for consumer in contract.consumer_tasks:
            if consumer not in task_ids:
                problems.append(f"contract {contract.id} names unknown consumer task {consumer}")
        if contract.provider_task in contract.consumer_tasks:
            problems.append(f"contract {contract.id} lists its provider as a consumer")
        providers = sorted(t.id for t in plan.tasks if contract.id in t.provides)
        if providers and providers != [contract.provider_task]:
            problems.append(
                f"contract {contract.id} must have exactly one provider "
                f"({contract.provider_task}), but tasks {', '.join(providers)} provide it"
            )
        listed_consumers = {t.id for t in plan.tasks if contract.id in t.consumes}
        if listed_consumers - set(contract.consumer_tasks):
            extra = ", ".join(sorted(listed_consumers - set(contract.consumer_tasks)))
            problems.append(f"tasks {extra} consume {contract.id} but aren't listed in it")
    return problems


# Helpers -------------------------------------------------------------------------------


def _field_mismatches(
    claim: Claim, contract: Contract, use: InterfaceUse, side: str
) -> list[Finding]:
    findings = []
    verb = "read" if side == "consumes" else "provide"
    for name, claimed_type in use.fields.items():
        expected = contract.fields.get(name)
        if expected is None:
            nearest = _nearest_field(name, contract)
            if nearest:
                suggestion = f"{verb.capitalize()} `{nearest}: {contract.fields[nearest]}`, "
                suggestion += f"not `{name}`."
            else:
                suggestion = f"Use only the fields of {contract.id}: {_field_list(contract)}."
            findings.append(
                _field_finding(
                    claim,
                    contract,
                    FindingKind.CONTRACT_FIELD_MISSING,
                    name,
                    explanation=f"The claim expects to {verb} `{name}: {claimed_type}`, but "
                    f"{contract.id} v{contract.version} has no field `{name}`. Its fields "
                    f"are {_field_list(contract)}.",
                    correction=suggestion,
                )
            )
        elif expected != claimed_type:
            findings.append(
                _field_finding(
                    claim,
                    contract,
                    FindingKind.CONTRACT_TYPE_MISMATCH,
                    name,
                    explanation=f"The claim treats `{name}` as {claimed_type}, but "
                    f"{contract.id} v{contract.version} defines it as {expected}.",
                    correction=f"{verb.capitalize()} `{name}` as {expected}.",
                )
            )
    return findings


def _nearest_field(name: str, contract: Contract) -> str | None:
    matches = difflib.get_close_matches(name, list(contract.fields), n=1, cutoff=0.3)
    return matches[0] if matches else None


def _field_list(contract: Contract) -> str:
    return ", ".join(f"`{n}: {t}`" for n, t in contract.fields.items())


def _field_finding(
    claim: Claim,
    contract: Contract,
    kind: FindingKind,
    field_name: str,
    *,
    explanation: str,
    correction: str,
) -> Finding:
    return _finding(
        claim,
        kind,
        f"{contract.id}.{field_name}",
        affected=[claim.id, contract.id],
        evidence=[
            _evidence(
                EvidenceKind.PLAN, f"{contract.id} v{contract.version}", _field_list(contract)
            ),
            _claim_evidence(claim, _uses_excerpt(claim, contract.id)),
        ],
        explanation=explanation,
        correction=correction,
    )


def _scope(claim: Claim, contract: Contract, side: str, correction: str) -> Finding:
    return _finding(
        claim,
        FindingKind.UNSUPPORTED_SCOPE,
        f"{side}.{contract.id}",
        affected=[claim.id, contract.id],
        evidence=[
            _evidence(
                EvidenceKind.PLAN,
                f"{contract.id} v{contract.version}",
                f"provider {contract.provider_task}; consumers "
                f"{', '.join(contract.consumer_tasks) or 'none'}",
            )
        ],
        explanation=f"Task {claim.task_id} {side} {contract.id}, which the plan doesn't allow.",
        correction=correction,
    )


def _unknown(claim: Claim, plan: Plan, label: str, ref: str, valid: list[str]) -> Finding:
    return _finding(
        claim,
        FindingKind.UNKNOWN_REFERENCE,
        f"{label}.{ref}",
        affected=[claim.id],
        evidence=[_plan_evidence(plan, f"valid {label} ids: {', '.join(valid) or 'none'}")],
        explanation=f"Plan v{plan.version} has no {label} `{ref}`.",
        correction=f"Use one of: {', '.join(valid) or 'none'}.",
    )


def _uses_excerpt(claim: Claim, contract_id: str) -> str:
    parts = []
    for side, uses in (("provides", claim.provides), ("consumes", claim.consumes)):
        for use in uses:
            if use.contract_id == contract_id:
                fields = ", ".join(f"{n}: {t}" for n, t in use.fields.items())
                parts.append(f"{side} {contract_id} {{{fields}}}")
    return "; ".join(parts)


def _evidence(kind: EvidenceKind, ref: str, excerpt: str) -> Evidence:
    if len(excerpt) > EXCERPT_LIMIT:
        excerpt = excerpt[: EXCERPT_LIMIT - 1] + "…"
    return Evidence(kind=kind, ref=ref, excerpt=excerpt)


def _plan_evidence(plan: Plan, excerpt: str) -> Evidence:
    return _evidence(EvidenceKind.PLAN, f"plan v{plan.version}", excerpt)


def _claim_evidence(claim: Claim, excerpt: str) -> Evidence:
    return _evidence(EvidenceKind.CLAIM, f"{claim.id} rev {claim.revision}", excerpt)


def _finding(
    claim: Claim,
    kind: FindingKind,
    subject: str,
    *,
    affected: list[str],
    evidence: list[Evidence],
    explanation: str,
    correction: str,
    severity: FindingSeverity = _BLOCKING,
) -> Finding:
    return Finding(
        id=f"{claim.id}/{claim.revision}:{kind}:{subject}",
        kind=kind,
        severity=severity,
        source=FindingSource.RULE,
        affected_ids=affected,
        evidence=evidence,
        explanation=explanation,
        proposed_correction=correction,
    )
