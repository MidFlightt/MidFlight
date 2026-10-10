"""S-2: deterministic claim rules (UC-05 step 2) and plan validation (UC-03 step 2)."""

from __future__ import annotations

from demo_fixture import make_claim, make_plan
from midflight.domain.models import (
    EXCERPT_LIMIT,
    Claim,
    ClaimState,
    Contract,
    FieldType,
    Finding,
    FindingKind,
    FindingSeverity,
    FindingSource,
    InterfaceUse,
    Plan,
    Task,
)
from midflight.domain.rules import check_claim, has_blocking, validate_plan

CHECKOUT = "checkout-response"


def uses(**fields: str) -> list[InterfaceUse]:
    return [InterfaceUse(contract_id=CHECKOUT, fields=fields)]


def t1_claim(**overrides: object) -> Claim:
    values: dict[str, object] = {
        "files": ["app/api.py", "README.md"],
        "consumes": [],
        "provides": uses(total_cents="integer"),
        "acceptance_criteria": ["GET /checkout returns total_cents as an integer"],
    }
    return make_claim("T1", **(values | overrides))


def t3_claim(**overrides: object) -> Claim:
    values: dict[str, object] = {
        "requirement_ids": ["R-2"],
        "files": ["CONTRIBUTING.md", "README.md"],
        "consumes": [],
        "no_interfaces": True,
        "acceptance_criteria": ["The guide explains branch naming"],
    }
    return make_claim("T3", **(values | overrides))


def kinds(findings: list[Finding]) -> list[FindingKind]:
    return [f.kind for f in findings]


def only(findings: list[Finding], kind: FindingKind) -> Finding:
    matching = [f for f in findings if f.kind is kind]
    assert len(matching) == 1, kinds(findings)
    return matching[0]


# Scenario 1: compatible claims ---------------------------------------------------------


def test_compatible_provider_and_consumer_have_no_findings() -> None:
    plan = make_plan(1)
    t1, t2 = t1_claim(), make_claim("T2")
    assert check_claim(t1, plan, [t2]) == []
    assert check_claim(t2, plan, [t1]) == []


def test_t3_with_no_interfaces_has_no_findings() -> None:
    assert check_claim(t3_claim(), make_plan(1)) == []


# Scenario 2: the flagship conflict ------------------------------------------------------


def test_total_vs_total_cents_needs_revision() -> None:
    claim = make_claim("T2", consumes=uses(total="number"))
    findings = check_claim(claim, make_plan(1))

    finding = only(findings, FindingKind.CONTRACT_FIELD_MISSING)
    assert finding.severity is FindingSeverity.BLOCKING
    assert finding.source is FindingSource.RULE
    assert finding.affected_ids == [claim.id, CHECKOUT]
    assert finding.proposed_correction == "Read `total_cents: integer`, not `total`."
    assert "`total_cents: integer`" in finding.explanation
    assert {e.kind.value for e in finding.evidence} == {"plan", "claim"}
    assert has_blocking(findings)


def test_revised_claim_with_total_cents_passes() -> None:
    revised = make_claim("T2", revision=2, consumes=uses(total_cents="integer"))
    assert check_claim(revised, make_plan(1)) == []


def test_right_field_with_wrong_type_is_a_type_mismatch() -> None:
    claim = make_claim("T2", consumes=uses(total_cents="number"))
    finding = only(check_claim(claim, make_plan(1)), FindingKind.CONTRACT_TYPE_MISMATCH)
    assert finding.proposed_correction == "Read `total_cents` as integer."


def test_unrelated_field_name_lists_the_real_fields() -> None:
    claim = make_claim("T2", consumes=uses(shipping_address="string"))
    finding = only(check_claim(claim, make_plan(1)), FindingKind.CONTRACT_FIELD_MISSING)
    assert finding.proposed_correction == (
        "Use only the fields of checkout-response: `total_cents: integer`."
    )


def test_consumer_may_read_a_subset_of_fields() -> None:
    claim = make_claim("T2", plan_version=2, consumes=uses(currency="string"))
    assert check_claim(claim, make_plan(2)) == []


# Plan v2: the provider must provide every field ----------------------------------------


def test_provider_missing_a_new_field_needs_revision() -> None:
    claim = t1_claim(plan_version=2)
    finding = only(check_claim(claim, make_plan(2)), FindingKind.CONTRACT_FIELD_MISSING)
    assert finding.proposed_correction == "Provide `currency: string`."


def test_provider_with_every_field_passes() -> None:
    claim = t1_claim(plan_version=2, provides=uses(total_cents="integer", currency="string"))
    assert check_claim(claim, make_plan(2)) == []


def test_provider_renaming_a_field_gets_both_findings() -> None:
    claim = t1_claim(provides=uses(total="integer"))
    findings = check_claim(claim, make_plan(1))
    assert kinds(findings) == [FindingKind.CONTRACT_FIELD_MISSING] * 2
    corrections = {f.proposed_correction for f in findings}
    assert corrections == {
        "Provide `total_cents: integer`, not `total`.",
        "Provide `total_cents: integer`.",
    }


# Versions and references ---------------------------------------------------------------


def test_claim_against_an_old_plan_is_stale() -> None:
    finding = only(check_claim(make_claim("T2"), make_plan(2)), FindingKind.STALE_PLAN)
    assert finding.blocking
    assert finding.proposed_correction == "Re-read plan v2 and resubmit the claim against it."


def test_unknown_task_requirement_and_contract_are_each_reported() -> None:
    claim = make_claim(
        "T9",
        requirement_ids=["R-1", "R-7"],
        consumes=[InterfaceUse(contract_id="cart", fields={"items": FieldType.ARRAY})],
    )
    findings = [
        f for f in check_claim(claim, make_plan(1)) if f.kind is FindingKind.UNKNOWN_REFERENCE
    ]
    corrections = sorted(f.proposed_correction or "" for f in findings)
    assert corrections == [
        "Use one of: R-1, R-2.",
        "Use one of: T1, T2, T3.",
        "Use one of: checkout-response.",
    ]


# Completeness (D5, D12) ----------------------------------------------------------------


def test_claim_without_interfaces_or_criteria_is_incomplete() -> None:
    claim = make_claim("T2", consumes=[], acceptance_criteria=[], state=ClaimState.DRAFT)
    finding = only(check_claim(claim, make_plan(1)), FindingKind.INCOMPLETE_CLAIM)
    assert finding.blocking
    assert "no_interfaces" in (finding.proposed_correction or "")
    assert "acceptance_criteria" in (finding.proposed_correction or "")


# Scope ---------------------------------------------------------------------------------


def test_consumer_claiming_to_provide_the_contract_is_out_of_scope() -> None:
    claim = make_claim("T2", consumes=[], provides=uses(total_cents="integer"))
    finding = only(check_claim(claim, make_plan(1)), FindingKind.UNSUPPORTED_SCOPE)
    assert "Only T1 provides checkout-response" in (finding.proposed_correction or "")


def test_unlisted_task_consuming_the_contract_is_out_of_scope() -> None:
    claim = t3_claim(no_interfaces=False, consumes=uses(total_cents="integer"))
    finding = only(check_claim(claim, make_plan(1)), FindingKind.UNSUPPORTED_SCOPE)
    assert "T2 as consumers" in (finding.proposed_correction or "")


# Other active claims -------------------------------------------------------------------


def test_second_provider_of_the_same_contract_is_blocked() -> None:
    plan = make_plan(1)
    first = t1_claim(state=ClaimState.APPROVED)
    second = t1_claim(id="C-T1-second")
    finding = only(check_claim(second, plan, [first]), FindingKind.DUPLICATE_PROVIDER)
    assert finding.blocking
    assert first.id in finding.affected_ids


def test_a_pending_rival_provider_does_not_block() -> None:
    # The first approval wins; the race-safe save in S-3 stops a double approval.
    first = t1_claim()
    second = t1_claim(id="C-T1-second")
    findings = check_claim(second, make_plan(1), [first])
    assert FindingKind.DUPLICATE_PROVIDER not in kinds(findings)
    assert not has_blocking(findings)


def test_inv_14_shared_files_are_info_and_never_block() -> None:
    # Scenario 3: T1 and T3 both touch README.md.
    plan = make_plan(1)
    t1, t3 = t1_claim(), t3_claim()
    findings = check_claim(t3, plan, [t1])
    finding = only(findings, FindingKind.FILE_OVERLAP)
    assert finding.severity is FindingSeverity.INFO
    assert "README.md" in finding.explanation
    assert not has_blocking(findings)


def test_withdrawn_and_closed_claims_are_ignored() -> None:
    plan = make_plan(1)
    for state in (ClaimState.WITHDRAWN, ClaimState.CLOSED):
        gone = t1_claim(id="C-old", state=state)
        assert check_claim(t1_claim(), plan, [gone]) == []
        assert check_claim(t3_claim(), plan, [gone]) == []


def test_a_claim_is_not_compared_with_itself() -> None:
    claim = t1_claim()
    assert check_claim(claim, make_plan(1), [claim]) == []


# Retry safety and limits ---------------------------------------------------------------


def test_rerunning_the_rules_gives_the_same_finding_ids() -> None:
    claim = make_claim("T2", consumes=uses(total="number"))
    plan = make_plan(1)
    assert check_claim(claim, plan) == check_claim(claim, plan)


def test_finding_ids_differ_between_revisions() -> None:
    plan = make_plan(1)
    first = check_claim(make_claim("T2", consumes=uses(total="number")), plan)
    second = check_claim(make_claim("T2", revision=2, consumes=uses(total="number")), plan)
    assert first[0].id != second[0].id


def test_huge_contracts_still_fit_the_evidence_limit() -> None:
    fields = {f"field_{n:03}": FieldType.STRING for n in range(200)}
    plan = make_plan(1)
    big = Contract(id=CHECKOUT, version=1, provider_task="T1", consumer_tasks=["T2"], fields=fields)
    plan = Plan.model_validate(plan.model_dump() | {"contracts": [big.model_dump()]})
    findings = check_claim(make_claim("T2", consumes=uses(total="number")), plan)
    assert findings
    assert all(len(e.excerpt) <= EXCERPT_LIMIT for f in findings for e in f.evidence)


# Plan validation (UC-03 2a) ------------------------------------------------------------


def test_demo_plans_are_valid() -> None:
    assert validate_plan(make_plan(1)) == []
    assert validate_plan(make_plan(2)) == []


def test_plan_problems_are_all_listed() -> None:
    plan = make_plan(1)
    bad = Plan.model_validate(
        plan.model_dump()
        | {
            "tasks": [
                *(t.model_dump() for t in plan.tasks),
                Task(
                    id="T1",
                    title="Duplicate",
                    owner="p-x",
                    requirement_ids=["R-9"],
                    provides=[CHECKOUT, "cart"],
                ).model_dump(),
            ],
            "contracts": [
                plan.contracts[0].model_dump() | {"consumer_tasks": ["T2", "T8"]},
            ],
        }
    )
    problems = validate_plan(bad)
    assert "task id T1 is used 2 times" in problems
    assert "task T1 cites unknown requirement R-9" in problems
    assert "task T1 cites unknown contract cart" in problems
    assert "contract checkout-response names unknown consumer task T8" in problems


def test_two_tasks_providing_one_contract_is_invalid() -> None:
    plan = make_plan(1)
    tasks = [t.model_dump() for t in plan.tasks]
    tasks[1]["provides"] = [CHECKOUT]
    problems = validate_plan(Plan.model_validate(plan.model_dump() | {"tasks": tasks}))
    assert any("exactly one provider" in p for p in problems)


def test_consumer_missing_from_the_contract_is_invalid() -> None:
    plan = make_plan(1)
    tasks = [t.model_dump() for t in plan.tasks]
    tasks[2]["consumes"] = [CHECKOUT]
    problems = validate_plan(Plan.model_validate(plan.model_dump() | {"tasks": tasks}))
    assert "tasks T3 consume checkout-response but aren't listed in it" in problems
