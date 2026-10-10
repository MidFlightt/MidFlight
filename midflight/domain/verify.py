"""Checking a pushed commit against its claim and the plan (UC-10). Pure: no I/O.

The verification service fetches the evidence from GitHub and passes it in here:

- the claim the branch belongs to (or None),
- the changed paths, and whether GitHub cut the diff short,
- the content at the head commit of the changed and declared files,
- the contract-test results for that exact commit (or None if missing).

Rules, in plain words (all block except the last):

- `evidence_missing`: no approved claim, a truncated diff, or no test results for
  this exact commit. Missing evidence is never a pass (INV-03).
- `test_failure`: a contract test failed.
- `missing_change`: a contract field the task provides, or the claim says it reads,
  appears in none of the task's files.
- `protected_path_changed`: the branch edited contract tests or CI workflows; the
  lead must review it (INV-15).
- `undeclared_change`: a changed file the claim didn't list. Shown, never blocking.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from midflight.domain.models import (
    Claim,
    ClaimState,
    Evidence,
    EvidenceCoverage,
    EvidenceKind,
    Finding,
    FindingKind,
    FindingSeverity,
    FindingSource,
    Plan,
    TestResult,
    VerificationOutcome,
)

# A branch may not change these: they decide whether the branch passes (NFR-10).
PROTECTED_PREFIXES = ("tests/contract/", "contracts/", ".github/")

# What the contract-test workflow uploads (see docs/domain.md, GitHub names).
ARTIFACT_NAME = "contract-results"


def is_protected(path: str) -> bool:
    return path.startswith(PROTECTED_PREFIXES)


def parse_test_results(artifact: object, head_sha: str) -> list[TestResult] | None:
    """The results in a `contract-results` artifact, or None if it's missing, malformed,
    or for another commit. Two shapes are accepted:

    - one result per test: `{"sha": "...", "results": [{"name", "passed", "message"}]}`
    - a summary: `{"head_sha": "...", "passed": true, "failures": ["Provider: ..."]}`,
      as the demo shop's trusted runner writes it
    """
    if not isinstance(artifact, dict):
        return None
    if artifact.get("sha") == head_sha:
        results = artifact.get("results")
        if not isinstance(results, list) or not results:
            return None
        try:
            return [TestResult.model_validate(r) for r in results]
        except ValueError:
            return None
    if artifact.get("head_sha") == head_sha and isinstance(artifact.get("passed"), bool):
        failures = [str(f) for f in artifact.get("failures") or [] if str(f).strip()]
        if artifact["passed"] and not failures:
            return [TestResult(name="contract checks", passed=True)]
        if not failures:
            return [TestResult(name="contract checks", passed=False)]
        return [
            TestResult(
                name=f.split(":", 1)[0].strip() or "contract check", passed=False, message=f[:500]
            )
            for f in failures
        ]
    return None


def coverage(
    claim: Claim | None, truncated: bool, tests: list[TestResult] | None
) -> EvidenceCoverage:
    missing = []
    if claim is None:
        missing.append("an approved claim for this branch")
    if truncated:
        missing.append("the complete diff")
    if tests is None:
        missing.append(f"the {ARTIFACT_NAME} artifact for this commit")
    return EvidenceCoverage(
        diff_complete=not truncated, test_results_present=tests is not None, missing=missing
    )


def check_commit(
    verification_id: str,
    claim: Claim | None,
    plan: Plan,
    head_sha: str,
    changed_paths: Sequence[str],
    truncated: bool,
    contents: Mapping[str, str],
    tests: list[TestResult] | None,
    owners: Mapping[str, str] | None = None,
) -> list[Finding]:
    """What plain rules find in a push (D33). `owners` maps a file to the other task
    whose claim lists it."""
    findings: list[Finding] = []
    short = head_sha[:7]

    def add(
        kind: FindingKind,
        explanation: str,
        correction: str,
        evidence: list[Evidence],
        severity: FindingSeverity = FindingSeverity.BLOCKING,
    ) -> None:
        findings.append(
            Finding(
                id=f"{verification_id}:{kind}:{len(findings) + 1}",
                kind=kind,
                severity=severity,
                source=FindingSource.RULE,
                affected_ids=[claim.id if claim else verification_id],
                evidence=evidence,
                explanation=explanation,
                proposed_correction=correction,
            )
        )

    if claim is None:
        add(
            FindingKind.EVIDENCE_MISSING,
            f"No approved Midflight claim belongs to this branch, so there's nothing to "
            f"verify {short} against.",
            "Submit a claim for the task with submit_claim, wait for approval, then push.",
            [Evidence(kind=EvidenceKind.GITHUB, ref=f"commit {short}")],
        )
    if truncated:
        add(
            FindingKind.EVIDENCE_MISSING,
            f"GitHub returned an incomplete diff for {short}, so it can't be fully checked.",
            "Split the change into smaller pushes.",
            [Evidence(kind=EvidenceKind.DIFF, ref=f"commit {short}")],
        )
    if tests is None:
        add(
            FindingKind.EVIDENCE_MISSING,
            f"No {ARTIFACT_NAME} artifact for {short}: the contract tests didn't report "
            "results for this exact commit.",
            "Make sure the contract-test workflow uploads contract-results with the head SHA.",
            [Evidence(kind=EvidenceKind.TEST, ref=f"{ARTIFACT_NAME} for {short}")],
        )
    else:
        for test in [t for t in tests if not t.passed][:5]:
            add(
                FindingKind.TEST_FAILURE,
                f"Contract test {test.name} failed on {short}.",
                f"Fix the code so contract test {test.name} passes; don't change the test.",
                [Evidence(kind=EvidenceKind.TEST, ref=test.name, excerpt=test.message[:500])],
            )

    protected = [p for p in changed_paths if is_protected(p)]
    if protected:
        add(
            FindingKind.PROTECTED_PATH_CHANGED,
            "This branch changes files that decide whether it passes: "
            + ", ".join(protected[:5])
            + ". The lead must review that (INV-15).",
            "Undo those changes, or ask the lead to change the tests on main.",
            [Evidence(kind=EvidenceKind.DIFF, ref=p) for p in protected[:5]],
        )

    if claim is not None:
        if tests is None:
            # Contract tests check the fields when they run. Without their results this
            # is the only check that the promised fields are in the code.
            findings += _missing_fields(
                verification_id, claim, plan, short, contents, len(findings)
            )
        declared = set(claim.files)
        undeclared = [p for p in changed_paths if p not in declared and not is_protected(p)]
        foreign = [p for p in undeclared if p in (owners or {})]
        undeclared = [p for p in undeclared if p not in foreign]
        if foreign:
            whose = ", ".join(f"{p} ({(owners or {})[p]})" for p in foreign[:8])
            add(
                FindingKind.UNDECLARED_CHANGE,
                f"This push changes files that belong to another task: {whose}.",
                "Undo those changes. If you need something there, say so in your claim's "
                "assumptions and name that task.",
                [Evidence(kind=EvidenceKind.DIFF, ref=p) for p in foreign[:5]],
            )
        if undeclared:
            add(
                FindingKind.UNDECLARED_CHANGE,
                f"Changed files claim {claim.id} didn't list: {', '.join(undeclared[:8])}.",
                "If they're part of this task, add them to the claim next time.",
                [Evidence(kind=EvidenceKind.DIFF, ref=p) for p in undeclared[:5]],
                FindingSeverity.INFO,
            )
    return findings


def decide_verification(findings: Sequence[Finding]) -> VerificationOutcome:
    """Escalations first, then concrete failures, then missing evidence (INV-03)."""
    blocking = {f.kind for f in findings if f.blocking}
    if blocking & {FindingKind.PROTECTED_PATH_CHANGED, FindingKind.REQUIREMENT_CONFLICT}:
        return VerificationOutcome.NEEDS_REVIEW
    if blocking - {FindingKind.EVIDENCE_MISSING, FindingKind.REVIEWER_UNAVAILABLE}:
        return VerificationOutcome.FAILED
    if blocking:
        return VerificationOutcome.INCOMPLETE
    return VerificationOutcome.VERIFIED


def verifiable(claim: Claim) -> bool:
    """Only an approved (or finished) claim can be verified against."""
    return claim.state in (ClaimState.APPROVED, ClaimState.CLOSED)


# A line comment: `#` or `//` at the start of a line or after a space (not the `//` in
# `https://`), to the end of the line.
_LINE_COMMENT = re.compile(r"(?:^|(?<=\s))(?:#|//)[^\n]*", re.MULTILINE)


def _without_comments(text: str) -> str:
    return _LINE_COMMENT.sub("", text)


def _missing_fields(
    verification_id: str,
    claim: Claim,
    plan: Plan,
    short: str,
    contents: Mapping[str, str],
    numbered: int,
) -> list[Finding]:
    """Each contract field the task provides, or the claim says it reads, must appear in
    the code of at least one of the task's files at the head commit. Comments don't
    count, so a comment naming the field can't stand in for using it."""
    task = plan.task(claim.task_id)
    if task is None:
        return []
    needed: dict[str, list[str]] = {}
    for contract_id in task.provides:
        contract = plan.contract(contract_id)
        if contract:
            needed[contract_id] = list(contract.fields)
    for use in claim.consumes:
        contract = plan.contract(use.contract_id)
        if contract:
            needed[use.contract_id] = [f for f in use.fields if f in contract.fields]
    text = "\n".join(_without_comments(t) for t in contents.values())
    findings = []
    for contract_id, fields in needed.items():
        contract = plan.contract(contract_id)
        assert contract is not None
        for field in fields:
            if field in text:
                continue
            numbered += 1
            findings.append(
                Finding(
                    id=f"{verification_id}:{FindingKind.MISSING_CHANGE}:{numbered}",
                    kind=FindingKind.MISSING_CHANGE,
                    severity=FindingSeverity.BLOCKING,
                    source=FindingSource.RULE,
                    affected_ids=[claim.id, contract_id],
                    evidence=[
                        Evidence(
                            kind=EvidenceKind.PLAN,
                            ref=f"plan v{plan.version} {contract_id}",
                            excerpt=f"{field}: {contract.fields[field]}",
                        ),
                        Evidence(
                            kind=EvidenceKind.FILE,
                            ref=f"{', '.join(sorted(contents)[:5]) or 'no files'} at {short}",
                        ),
                    ],
                    explanation=f"Contract {contract_id} needs `{field}` "
                    f"({contract.fields[field]}), but none of the task's files contain it "
                    f"at {short}.",
                    proposed_correction=f"Use `{field}` exactly as contract {contract_id} "
                    "names it, then push again.",
                )
            )
    return findings
