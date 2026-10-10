"""Midflight's shared vocabulary: the entities and enums in docs/domain.md.

Once merged, this module is the source of truth for names (AGENTS.md). A change here
needs both programmers' approval and an update to docs/domain.md in the same PR.

Every model rejects unknown fields and is immutable: create a changed copy with
`model_copy(update=...)` and save it through the store. Where a model can enforce an
invariant on its own data, it does, so an invalid state can't even be constructed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Id = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,40}$")]
TokenHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Repository = Annotated[str, StringConstraints(pattern=r"^[\w.-]+/[\w.-]+$")]
Version = Annotated[int, Field(ge=1)]

EXCERPT_LIMIT = 500


class Model(BaseModel):
    """Base for every entity: unknown fields are rejected and instances are frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# Enums ---------------------------------------------------------------------------------


class Role(StrEnum):
    LEAD = "lead"
    AGENT = "agent"


class PlanStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"


class FieldType(StrEnum):
    """The type of one contract field, as JSON Schema names it."""

    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class ClaimState(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


class DirectiveSource(StrEnum):
    PLAN_CHANGE = "plan_change"
    VERIFICATION = "verification"


class DirectiveState(StrEnum):
    QUEUED = "queued"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    NEEDS_CLARIFICATION = "needs_clarification"
    SUPERSEDED = "superseded"


class DirectiveResponse(StrEnum):
    """What an agent may answer through `acknowledge_directive`."""

    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    NEEDS_CLARIFICATION = "needs_clarification"


class FindingSeverity(StrEnum):
    BLOCKING = "blocking"
    INFO = "info"


class FindingSource(StrEnum):
    """`rule` means application code produced it; `reviewer` means the AI did."""

    RULE = "rule"
    REVIEWER = "reviewer"


class FindingKind(StrEnum):
    # Claim rules (S-2)
    STALE_PLAN = "stale_plan"
    UNKNOWN_REFERENCE = "unknown_reference"
    INCOMPLETE_CLAIM = "incomplete_claim"
    CONTRACT_FIELD_MISSING = "contract_field_missing"
    CONTRACT_TYPE_MISMATCH = "contract_type_mismatch"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    DUPLICATE_PROVIDER = "duplicate_provider"
    FILE_OVERLAP = "file_overlap"
    # AI reviewer (S-5)
    SEMANTIC_MISMATCH = "semantic_mismatch"
    REQUIREMENT_CONFLICT = "requirement_conflict"
    REVIEWER_UNAVAILABLE = "reviewer_unavailable"
    # Verification rules (S-10)
    UNDECLARED_CHANGE = "undeclared_change"
    MISSING_CHANGE = "missing_change"
    TEST_FAILURE = "test_failure"
    PROTECTED_PATH_CHANGED = "protected_path_changed"
    EVIDENCE_MISSING = "evidence_missing"


# The only kinds the AI reviewer may propose. Everything else comes from application code.
REVIEWER_KINDS = frozenset({FindingKind.SEMANTIC_MISMATCH, FindingKind.REQUIREMENT_CONFLICT})


class EvidenceKind(StrEnum):
    PLAN = "plan"
    CLAIM = "claim"
    DIFF = "diff"
    FILE = "file"
    TEST = "test"
    GITHUB = "github"


class VerificationOutcome(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    INCOMPLETE = "incomplete"


class SyncState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


class EscalationState(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class Resolution(StrEnum):
    CLARIFY_PLAN = "clarify_plan"
    REQUEST_REVISION = "request_revision"
    DISMISS = "dismiss"


class JobKind(StrEnum):
    CLAIM_REVIEW = "claim_review"
    PLAN_PROPAGATION = "plan_propagation"
    VERIFICATION = "verification"
    RECONCILE = "reconcile"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# Project and people --------------------------------------------------------------------


class Project(Model):
    id: Id
    repository: Repository
    github_installation_id: int | None = None
    lead_id: Id
    participant_ids: list[Id] = []
    current_plan_version: Version | None = None
    sync_state: SyncState = SyncState.FRESH
    sync_reason: str | None = None
    last_synced_at: AwareDatetime | None = None
    coord_rev: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _stale_needs_reason(self) -> Self:
        if self.sync_state is SyncState.STALE and not self.sync_reason:
            raise ValueError("a stale project must say why (sync_reason)")
        return self


class Participant(Model):
    id: Id
    project_id: Id
    role: Role
    developer_name: Text
    agent_name: str | None = None
    token_hash: TokenHash
    revoked_at: AwareDatetime | None = None
    last_check_in_at: AwareDatetime | None = None
    last_check_in_rev: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _agents_are_named(self) -> Self:
        if self.role is Role.AGENT and not self.agent_name:
            raise ValueError("an agent participant needs an agent_name, e.g. claude-code")
        return self

    @property
    def active(self) -> bool:
        return self.revoked_at is None


# Plan ----------------------------------------------------------------------------------


class Requirement(Model):
    id: Id
    description: Text
    acceptance_criteria: list[Text] = []


class Task(Model):
    id: Id
    title: Text
    owner: Id
    branch: str | None = None
    requirement_ids: list[Id] = []
    provides: list[Id] = []
    consumes: list[Id] = []


class Contract(Model):
    id: Id
    version: Version
    provider_task: Id
    consumer_tasks: list[Id] = []
    fields: dict[Text, FieldType] = Field(min_length=1)


class Plan(Model):
    project_id: Id
    version: Version
    status: PlanStatus = PlanStatus.PROPOSED
    requirements: list[Requirement] = []
    tasks: list[Task] = []
    contracts: list[Contract] = []
    approved_by: Id | None = None
    approved_at: AwareDatetime | None = None
    change_reason: str | None = None
    changed_ids: list[Id] = []

    @model_validator(mode="after")
    def _approval_is_complete(self) -> Self:
        approval = (self.approved_by, self.approved_at, self.change_reason)
        if self.status is PlanStatus.APPROVED and not all(approval):
            raise ValueError("an approved plan needs approved_by, approved_at, and change_reason")
        if self.status is PlanStatus.PROPOSED and (self.approved_by or self.approved_at):
            raise ValueError("a proposed plan can't carry approval details")
        return self

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def contract(self, contract_id: str) -> Contract | None:
        return next((c for c in self.contracts if c.id == contract_id), None)

    def requirement(self, requirement_id: str) -> Requirement | None:
        return next((r for r in self.requirements if r.id == requirement_id), None)


# Claims and findings -------------------------------------------------------------------


class InterfaceUse(Model):
    """One contract a claim provides or consumes, with the fields and types it expects."""

    contract_id: Id
    fields: dict[Text, FieldType] = Field(min_length=1)


class Claim(Model):
    """One revision of an agent's declaration of intent. Revised, never edited in place."""

    id: Id
    revision: Version
    project_id: Id
    task_id: Id
    agent_id: Id
    branch: Text
    base_sha: Sha
    plan_version: Version
    state: ClaimState
    requirement_ids: list[Id] = []
    files: list[Text] = []
    provides: list[InterfaceUse] = []
    consumes: list[InterfaceUse] = []
    no_interfaces: bool = False
    assumptions: list[Text] = []
    acceptance_criteria: list[Text] = []
    reason: str | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _interfaces_are_consistent(self) -> Self:
        if self.no_interfaces and (self.provides or self.consumes):
            raise ValueError("no_interfaces is true, but the claim lists provides or consumes")
        for side, uses in (("provides", self.provides), ("consumes", self.consumes)):
            ids = [use.contract_id for use in uses]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{side} lists the same contract twice")
        return self

    def missing_details(self) -> list[str]:
        """What keeps this claim in `draft` (D5, D12). Empty means complete."""
        missing = []
        if not (self.provides or self.consumes or self.no_interfaces):
            missing.append("interfaces: list provides/consumes, or set no_interfaces: true")
        if not self.acceptance_criteria:
            missing.append("acceptance_criteria: at least one")
        return missing

    @property
    def is_complete(self) -> bool:
        return not self.missing_details()


class Evidence(Model):
    kind: EvidenceKind
    ref: Text
    excerpt: str = Field(default="", max_length=EXCERPT_LIMIT)


class Finding(Model):
    id: Id
    kind: FindingKind
    severity: FindingSeverity
    source: FindingSource
    affected_ids: list[Id] = Field(min_length=1)
    evidence: list[Evidence] = []
    explanation: Text
    proposed_correction: str | None = None

    @model_validator(mode="after")
    def _kind_fits_source_and_severity(self) -> Self:
        if self.kind is FindingKind.FILE_OVERLAP and self.severity is not FindingSeverity.INFO:
            raise ValueError("file overlap is always info, never blocking (INV-14)")
        if self.source is FindingSource.REVIEWER and self.kind not in REVIEWER_KINDS:
            raise ValueError(f"the reviewer can't produce a {self.kind} finding")
        return self

    @property
    def blocking(self) -> bool:
        return self.severity is FindingSeverity.BLOCKING


# Directives and escalations ------------------------------------------------------------

_ANSWERED = {
    DirectiveState.ACKNOWLEDGED,
    DirectiveState.REJECTED,
    DirectiveState.NEEDS_CLARIFICATION,
}


class Directive(Model):
    """A scoped update for one task. Data for the agent, never a command (INV-07)."""

    id: Id
    project_id: Id
    source: DirectiveSource
    task_id: Id
    recipient_id: Id
    plan_version: Version
    verification_id: Id | None = None
    changed_ids: list[Id] = []
    requested_adjustment: Text
    reason: Text
    blocking: bool = True
    state: DirectiveState = DirectiveState.QUEUED
    response: DirectiveResponse | None = None
    response_note: str | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _source_and_response_agree(self) -> Self:
        from_verification = self.source is DirectiveSource.VERIFICATION
        if from_verification != (self.verification_id is not None):
            raise ValueError("verification_id is set exactly when source is verification")
        if self.state in _ANSWERED:
            if self.response is None or self.response.value != self.state.value:
                raise ValueError("an answered directive records the matching response")
        elif self.state is not DirectiveState.SUPERSEDED and self.response is not None:
            raise ValueError("a directive the agent hasn't answered can't carry a response")
        return self

    @property
    def dedupe_key(self) -> str:
        """At most one actionable directive per key (INV-05, D13)."""
        if self.source is DirectiveSource.VERIFICATION:
            return f"{self.project_id}:verification:{self.verification_id}"
        return f"{self.project_id}:plan_change:v{self.plan_version}:{self.task_id}"


class Escalation(Model):
    """A conflict only the lead can decide. Midflight never picks a winner (INV-11)."""

    id: Id
    project_id: Id
    competing_requirement_ids: list[Id] = []
    claim_ids: list[Id] = []
    verification_id: Id | None = None
    finding_ids: list[Id] = []
    evidence: list[Evidence] = []
    explanation: Text
    state: EscalationState = EscalationState.OPEN
    resolution: Resolution | None = None
    resolved_by: Id | None = None
    reason: str | None = None
    resolved_at: AwareDatetime | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _resolution_is_complete(self) -> Self:
        if not (self.claim_ids or self.verification_id):
            raise ValueError("an escalation involves at least one claim or verification")
        details = (self.resolution, self.resolved_by, self.reason, self.resolved_at)
        if self.state is EscalationState.RESOLVED and not all(details):
            raise ValueError("a resolved escalation records resolution, who, why, and when")
        if self.state is EscalationState.OPEN and any(details):
            raise ValueError("an open escalation can't carry resolution details")
        return self


# Verification --------------------------------------------------------------------------


class TestResult(Model):
    __test__ = False  # not a pytest test class

    name: Text
    passed: bool
    message: str = ""


class EvidenceCoverage(Model):
    """What evidence verification actually had. Anything missing blocks `verified`."""

    diff_complete: bool
    test_results_present: bool
    missing: list[Text] = []


class Verification(Model):
    id: Id
    job_id: Id
    project_id: Id
    claim_id: Id | None = None
    claim_revision: Version | None = None
    plan_version: Version | None = None
    pr_number: int | None = None
    base_sha: Sha
    head_sha: Sha
    evidence_coverage: EvidenceCoverage
    findings: list[Finding] = []
    test_results: list[TestResult] = []
    outcome: VerificationOutcome
    check_run_id: int | None = None
    superseded_by: Id | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _verified_needs_full_evidence(self) -> Self:
        if self.outcome is not VerificationOutcome.VERIFIED:
            return self
        problems = []
        if self.claim_id is None or self.claim_revision is None or self.plan_version is None:
            problems.append("no approved claim and plan version")
        coverage = self.evidence_coverage
        if not coverage.diff_complete or not coverage.test_results_present or coverage.missing:
            problems.append("evidence is incomplete")
        if not self.test_results or not all(t.passed for t in self.test_results):
            problems.append("contract tests did not all pass")
        if any(f.blocking for f in self.findings):
            problems.append("there are blocking findings")
        if problems:
            raise ValueError("can't be verified: " + "; ".join(problems) + " (INV-03)")
        return self


# Jobs and audit ------------------------------------------------------------------------


class Job(Model):
    id: Id
    project_id: Id
    kind: JobKind
    subject_id: Id
    idempotency_key: Text
    attempts: int = Field(default=0, ge=0)
    state: JobState = JobState.QUEUED
    error: str | None = None
    correlation_id: Id
    result_ref: Id | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class AuditEvent(Model):
    """One state change: who did what, why, and against which versions (INV-13)."""

    id: Id
    project_id: Id
    actor: Id
    action: Text
    entity_ids: list[Id] = Field(min_length=1)
    versions: dict[str, int | str] = {}
    reason: Text
    correlation_id: Id
    idempotency_key: Text
    timestamp: AwareDatetime


# Anything the store saves as its own item.
Entity = Project | Participant | Plan | Claim | Directive | Escalation | Verification | Job
