"""S-1: the domain models round-trip, reject bad data, and hold their invariants."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from demo_fixture import BASE_SHA, NOW, PROJECT, make_claim, make_plan
from midflight.domain.models import (
    EXCERPT_LIMIT,
    AuditEvent,
    ClaimState,
    Contract,
    Directive,
    DirectiveResponse,
    DirectiveSource,
    DirectiveState,
    Escalation,
    EscalationState,
    Evidence,
    EvidenceCoverage,
    EvidenceKind,
    FieldType,
    Finding,
    FindingKind,
    FindingSeverity,
    FindingSource,
    InterfaceUse,
    Job,
    JobKind,
    Participant,
    Plan,
    PlanStatus,
    Project,
    Resolution,
    Role,
    SyncState,
    TestResult,
    Verification,
    VerificationOutcome,
)

TOKEN_HASH = "a" * 64


def finding(**overrides: Any) -> Finding:
    values: dict[str, Any] = {
        "id": "F-1",
        "kind": FindingKind.CONTRACT_FIELD_MISSING,
        "severity": FindingSeverity.BLOCKING,
        "source": FindingSource.RULE,
        "affected_ids": ["C-T2", "checkout-response"],
        "evidence": [Evidence(kind=EvidenceKind.PLAN, ref="checkout-response v1")],
        "explanation": "`total` is not a field of checkout-response",
        "proposed_correction": "Read `total_cents: integer` (cents), not `total`.",
    }
    return Finding(**(values | overrides))


def directive(**overrides: Any) -> Directive:
    values: dict[str, Any] = {
        "id": "D-42",
        "project_id": PROJECT,
        "source": DirectiveSource.PLAN_CHANGE,
        "task_id": "T2",
        "recipient_id": "p-t2",
        "plan_version": 2,
        "changed_ids": ["checkout-response"],
        "requested_adjustment": "Display `currency` next to the total",
        "reason": "Plan v2 adds currency: string to checkout-response",
        "created_at": NOW,
    }
    return Directive(**(values | overrides))


def verification(**overrides: Any) -> Verification:
    values: dict[str, Any] = {
        "id": "V-1",
        "job_id": "J-9",
        "project_id": PROJECT,
        "claim_id": "C-T1",
        "claim_revision": 2,
        "plan_version": 2,
        "pr_number": 12,
        "base_sha": BASE_SHA,
        "head_sha": "abc1234",
        "evidence_coverage": EvidenceCoverage(diff_complete=True, test_results_present=True),
        "test_results": [TestResult(name="test_checkout_contract", passed=True)],
        "outcome": VerificationOutcome.VERIFIED,
        "created_at": NOW,
    }
    return Verification(**(values | overrides))


def escalation(**overrides: Any) -> Escalation:
    values: dict[str, Any] = {
        "id": "E-7",
        "project_id": PROJECT,
        "competing_requirement_ids": ["R-1"],
        "claim_ids": ["C-T1", "C-T2"],
        "explanation": "T2 wants a tax-inclusive total; T1 returns tax-exclusive",
        "created_at": NOW,
    }
    return Escalation(**(values | overrides))


def every_entity() -> list[BaseModel]:
    return [
        Project(id=PROJECT, repository="MidFlightt/midflight-demo-shop", lead_id="p-lead"),
        Participant(
            id="p-t2",
            project_id=PROJECT,
            role=Role.AGENT,
            developer_name="frederik",
            agent_name="claude-code",
            token_hash=TOKEN_HASH,
        ),
        make_plan(2),
        make_claim("T2"),
        finding(),
        directive(),
        escalation(),
        verification(),
        Job(
            id="J-1",
            project_id=PROJECT,
            kind=JobKind.CLAIM_REVIEW,
            subject_id="C-T2",
            idempotency_key="claim:C-T2:1",
            correlation_id="corr-1",
            created_at=NOW,
            updated_at=NOW,
        ),
        AuditEvent(
            id="A-1",
            project_id=PROJECT,
            actor="p-t2",
            action="claim.submitted",
            entity_ids=["C-T2"],
            versions={"plan": 1, "claim_revision": 1},
            reason="initial claim",
            correlation_id="corr-1",
            idempotency_key="claim:C-T2:1",
            timestamp=NOW,
        ),
    ]


# Round trips and strictness ------------------------------------------------------------


@pytest.mark.parametrize("entity", every_entity(), ids=lambda e: type(e).__name__)
def test_every_model_round_trips_through_json(entity: BaseModel) -> None:
    restored = type(entity).model_validate_json(entity.model_dump_json())
    assert restored == entity


def test_unknown_fields_are_rejected() -> None:
    # A reviewer reply that smuggles in an extra field is not a Finding (INV-01).
    with pytest.raises(ValidationError):
        Finding.model_validate(finding().model_dump() | {"approve": True})


def test_models_are_immutable() -> None:
    claim = make_claim()
    with pytest.raises(ValidationError):
        claim.state = ClaimState.APPROVED  # type: ignore[misc]


def test_enum_values_match_domain_reference() -> None:
    assert [s.value for s in ClaimState] == [
        "draft",
        "pending",
        "approved",
        "needs_revision",
        "human_review_required",
        "withdrawn",
        "closed",
    ]
    assert [s.value for s in DirectiveState] == [
        "queued",
        "delivered",
        "acknowledged",
        "rejected",
        "needs_clarification",
        "superseded",
    ]
    assert [o.value for o in VerificationOutcome] == [
        "verified",
        "failed",
        "needs_review",
        "incomplete",
    ]


# Plan ----------------------------------------------------------------------------------


def test_plan_lookups_find_tasks_contracts_and_requirements(plan_v2: Plan) -> None:
    contract = plan_v2.contract("checkout-response")
    assert contract is not None
    assert contract.fields == {"total_cents": FieldType.INTEGER, "currency": FieldType.STRING}
    assert plan_v2.task("T3") is not None
    assert plan_v2.requirement("R-2") is not None
    assert plan_v2.task("T9") is None


def test_approved_plan_needs_approver_time_and_reason(plan_v1: Plan) -> None:
    with pytest.raises(ValidationError, match="approved plan needs"):
        Plan.model_validate(plan_v1.model_dump() | {"change_reason": None})


def test_proposed_plan_cannot_carry_approval(plan_v1: Plan) -> None:
    with pytest.raises(ValidationError, match="proposed plan"):
        Plan.model_validate(plan_v1.model_dump() | {"status": PlanStatus.PROPOSED})


def test_contract_needs_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        Contract(id="c", version=1, provider_task="T1", fields={})


# Claims (D5, D12) ----------------------------------------------------------------------


def test_complete_claim_has_nothing_missing() -> None:
    assert make_claim().missing_details() == []
    assert make_claim().is_complete


def test_t3_with_no_interfaces_is_complete() -> None:
    claim = make_claim(
        "T3",
        consumes=[],
        no_interfaces=True,
        files=["CONTRIBUTING.md"],
        acceptance_criteria=["The guide explains the branch naming rule"],
    )
    assert claim.is_complete


def test_claim_without_interfaces_or_criteria_says_what_is_missing() -> None:
    claim = make_claim(consumes=[], acceptance_criteria=[], state=ClaimState.DRAFT)
    missing = claim.missing_details()
    assert len(missing) == 2
    assert any("no_interfaces" in m for m in missing)
    assert any("acceptance_criteria" in m for m in missing)


def test_no_interfaces_contradicting_listed_interfaces_is_rejected() -> None:
    with pytest.raises(ValidationError, match="no_interfaces"):
        make_claim(no_interfaces=True)


def test_same_contract_twice_on_one_side_is_rejected() -> None:
    use = InterfaceUse(contract_id="checkout-response", fields={"total_cents": FieldType.INTEGER})
    with pytest.raises(ValidationError, match="same contract twice"):
        make_claim(consumes=[use, use])


def test_interface_use_carries_field_types() -> None:
    # The flagship conflict is visible in the data: T2 expects `total` as a number.
    claim = make_claim(
        consumes=[InterfaceUse(contract_id="checkout-response", fields={"total": "number"})]
    )
    assert claim.consumes[0].fields == {"total": FieldType.NUMBER}


def test_claim_needs_a_real_sha() -> None:
    with pytest.raises(ValidationError):
        make_claim(base_sha="main")


# Findings ------------------------------------------------------------------------------


def test_inv_14_file_overlap_can_never_block() -> None:
    with pytest.raises(ValidationError, match="INV-14"):
        finding(kind=FindingKind.FILE_OVERLAP, severity=FindingSeverity.BLOCKING)
    assert not finding(kind=FindingKind.FILE_OVERLAP, severity=FindingSeverity.INFO).blocking


def test_inv_01_reviewer_can_only_propose_semantic_findings() -> None:
    with pytest.raises(ValidationError, match="reviewer can't produce"):
        finding(source=FindingSource.REVIEWER, kind=FindingKind.STALE_PLAN)
    assert finding(source=FindingSource.REVIEWER, kind=FindingKind.SEMANTIC_MISMATCH)


def test_finding_must_cite_what_it_affects() -> None:
    with pytest.raises(ValidationError):
        finding(affected_ids=[])


def test_evidence_excerpt_is_capped() -> None:
    with pytest.raises(ValidationError):
        Evidence(kind=EvidenceKind.DIFF, ref="app/api.py", excerpt="x" * (EXCERPT_LIMIT + 1))


# Directives (D13, INV-05) --------------------------------------------------------------


def test_inv_05_plan_change_and_correction_directives_do_not_collide() -> None:
    # Plan v2 sends T1 a currency directive; later T1's push fails verification on v2.
    plan_change = directive(task_id="T1")
    correction = directive(
        id="D-50",
        task_id="T1",
        source=DirectiveSource.VERIFICATION,
        verification_id="V-1",
    )
    assert plan_change.dedupe_key != correction.dedupe_key
    assert plan_change.dedupe_key == directive(id="D-99", task_id="T1").dedupe_key


def test_verification_id_is_set_exactly_for_verification_directives() -> None:
    with pytest.raises(ValidationError, match="verification_id"):
        directive(source=DirectiveSource.VERIFICATION)
    with pytest.raises(ValidationError, match="verification_id"):
        directive(verification_id="V-1")


def test_answered_directive_records_matching_response() -> None:
    with pytest.raises(ValidationError, match="matching response"):
        directive(state=DirectiveState.ACKNOWLEDGED)
    with pytest.raises(ValidationError, match="matching response"):
        directive(state=DirectiveState.REJECTED, response=DirectiveResponse.ACKNOWLEDGED)
    with pytest.raises(ValidationError, match="hasn't answered"):
        directive(state=DirectiveState.DELIVERED, response=DirectiveResponse.ACKNOWLEDGED)


def test_directives_block_by_default() -> None:
    assert directive().blocking


# Escalations ---------------------------------------------------------------------------


def test_resolved_escalation_records_who_why_and_when() -> None:
    with pytest.raises(ValidationError, match="resolved escalation"):
        escalation(state=EscalationState.RESOLVED, resolution=Resolution.DISMISS)
    resolved = escalation(
        state=EscalationState.RESOLVED,
        resolution=Resolution.CLARIFY_PLAN,
        resolved_by="p-lead",
        reason="Totals exclude tax",
        resolved_at=NOW,
    )
    assert resolved.state is EscalationState.RESOLVED


def test_open_escalation_cannot_carry_a_resolution() -> None:
    with pytest.raises(ValidationError, match="open escalation"):
        escalation(resolution=Resolution.DISMISS)


def test_escalation_involves_a_claim_or_a_verification() -> None:
    with pytest.raises(ValidationError, match="at least one claim"):
        escalation(claim_ids=[])
    assert escalation(claim_ids=[], verification_id="V-1")


# Verification (INV-03) -----------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"evidence_coverage": EvidenceCoverage(diff_complete=False, test_results_present=True)},
        {"evidence_coverage": EvidenceCoverage(diff_complete=True, test_results_present=False)},
        {
            "evidence_coverage": EvidenceCoverage(
                diff_complete=True, test_results_present=True, missing=["web/checkout.js"]
            )
        },
        {"test_results": []},
        {"test_results": [TestResult(name="test_checkout_contract", passed=False)]},
        {"findings": [finding()]},
        {"claim_id": None},
        {"plan_version": None},
    ],
    ids=[
        "diff truncated",
        "no test results",
        "file missing",
        "no tests ran",
        "test failed",
        "blocking finding",
        "no claim",
        "no plan version",
    ],
)
def test_inv_03_missing_evidence_is_never_verified(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="INV-03"):
        verification(**overrides)


def test_incomplete_evidence_can_still_be_recorded_as_incomplete() -> None:
    result = verification(
        outcome=VerificationOutcome.INCOMPLETE,
        evidence_coverage=EvidenceCoverage(
            diff_complete=False, test_results_present=False, missing=["contract-results"]
        ),
        test_results=[],
    )
    assert result.outcome is VerificationOutcome.INCOMPLETE


def test_info_findings_do_not_prevent_verified() -> None:
    overlap = finding(kind=FindingKind.FILE_OVERLAP, severity=FindingSeverity.INFO)
    assert verification(findings=[overlap]).outcome is VerificationOutcome.VERIFIED


# Projects and participants -------------------------------------------------------------


def test_stale_project_says_why() -> None:
    with pytest.raises(ValidationError, match="sync_reason"):
        Project(id=PROJECT, repository="o/r", lead_id="p-lead", sync_state=SyncState.STALE)


def test_project_repository_is_owner_slash_name() -> None:
    with pytest.raises(ValidationError):
        Project(id=PROJECT, repository="midflight-demo-shop", lead_id="p-lead")


def test_agent_participant_needs_an_agent_name() -> None:
    with pytest.raises(ValidationError, match="agent_name"):
        Participant(
            id="p", project_id=PROJECT, role=Role.AGENT, developer_name="d", token_hash=TOKEN_HASH
        )


def test_inv_12_participant_stores_a_hash_not_a_token() -> None:
    with pytest.raises(ValidationError):
        Participant(
            id="p",
            project_id=PROJECT,
            role=Role.LEAD,
            developer_name="somesh",
            token_hash="mf_live_plaintext_token",
        )


def test_revoked_participant_is_inactive() -> None:
    lead = Participant(
        id="p", project_id=PROJECT, role=Role.LEAD, developer_name="s", token_hash=TOKEN_HASH
    )
    assert lead.active
    assert not lead.model_copy(update={"revoked_at": NOW}).active
