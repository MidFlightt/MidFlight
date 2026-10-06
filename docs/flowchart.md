# Midflight: shared vocabulary and coordination workflows

Version: 1.0 | October 6, 2026 | Design reference, not implemented functionality

This document describes the brainstormed coordination service and complements the [open design decisions](design-decisions.md). The diagrams assume a GitHub-connected project and participating coding agents that consult Midflight at supported checkpoints.

The current prototype only compares declared overlap and asks for clarification; it does not implement the approvals, semantic checks, propagation, or verification below. Claims can begin broad and be refined when dependencies emerge. The detailed checkout claims illustrate a shared interface after discovery, not a requirement to enumerate every implementation detail upfront. See the [README](../README.md) for current capabilities.

## Shared vocabulary

| Term | Definition | Checkout example |
| --- | --- | --- |
| Plan | The team's approved product direction and division of work; versioned as decisions change. | Build an online shop; Alice builds the backend and Bob builds the checkout page. |
| Requirement | A specific behavior the product must satisfy. | Display the total calculated by the backend. |
| Task | A piece of work assigned to a person and their coding agent. | Build the checkout page. |
| Claim | An agent's declaration of how it intends to perform a task; intention, not completion. | The page will read `total` as a decimal dollar amount. |
| Assumption | A detail relied on but not yet established by the plan, authoritative code, or an agreement. | The backend will return a field named `total`. |
| Dependency | Something one task needs from another task or existing component. | The page consumes the checkout response. |
| Agreement / contract | A recorded decision about how connected components must work together. | Return `total_cents` as an integer; convert it for display. |
| Discrepancy | A mismatch between connected claims, or between implementation and an approved decision. | The page expects `total`; the backend returns `total_cents`. |
| Directive | A scoped update to an affected agent based on an approved requirement or agreement. | Read `total_cents` and update the mock response. |
| Evidence | Observable information about the implementation. | Pushed code and tests tied to the reviewed commit. |
| Verification | Comparing evidence with the current requirements, claims, and agreements. | Check that the backend and page use the agreed price format. |

An assumption is not automatically an error. Different local variable names are usually harmless; incompatible expectations at a shared boundary are the concern.

## Legend and reading guide

- **Uppercase labels** identify vocabulary categories; names such as Alice and Bob identify the actor.
- **Numbered stages 1-8** are the normal coordination and verification path.
- **Stages C1-C4** are the requirement-change path, which can start at any time.
- **Solid arrows** show process flow or an update passed to another stage.
- **Dashed arrows** show a possible mid-work change, not a mandatory step.
- **Arrow labels** explain conditional outcomes and return paths.
- The PDF uses blue for shared intent, purple for coordination, amber for decisions/changes, and green for evidence/verification. Labels carry the meaning even without color.
- Acknowledged means the agent received an update. Verified means evidence supports the checked behavior. Neither means the entire application is correct.

## Flowchart 1: workflow with definitions

Read the normal path first. Follow C1-C4 when a requirement changes. Affected tasks return to claim review; unrelated work continues.

```mermaid
flowchart TD
    P["1 · PLAN + REQUIREMENTS<br/>Approved product behavior and division of work"]
    P --> C["2 · TASKS + CLAIMS<br/>Agents declare intended work and identify ASSUMPTIONS"]
    C --> D["3 · DEPENDENCIES + DISCREPANCIES<br/>Compare connected claims with current requirements<br/>Identify incompatible or unresolved shared assumptions"]
    D --> A["4 · AGREEMENT / CONTRACT<br/>Use existing authoritative decisions or resolve a new agreement<br/>Humans decide unclear product behavior"]
    A --> U["5 · DIRECTIVES + ACKNOWLEDGMENT<br/>Affected agents retrieve updates at a checkpoint<br/>Acknowledge and revise claims; re-review changed claims"]
    U --> B["6 · IMPLEMENTATION<br/>Build against the current agreement"]
    B --> E["7 · EVIDENCE<br/>Pushed code and relevant tests for a specific commit"]
    E --> V["8 · VERIFICATION<br/>Compare evidence with the current plan and agreements"]

    B -.->|"A change may be proposed during work"| CP["C1 · PROPOSED REQUIREMENT CHANGE<br/>Describe the new product behavior"]
    CP --> AP["C2 · HUMAN APPROVAL + PLAN VERSION<br/>Clarify and approve; preserve the previous version<br/>Unapproved proposals do not replace the current plan"]
    AP --> IM["C3 · IMPACT CHECK<br/>Follow dependencies to identify affected tasks"]
    IM -->|"Affected"| RP["C4 · REPLAN<br/>Invalidate affected approvals<br/>Request revised claims; agents pick up changes at checkpoints"]
    RP --> C
    IM -->|"Unaffected"| UC["Continue existing work<br/>Do not send irrelevant updates"]

    V -->|"Matches and still current"| OK["PASS<br/>Checked behavior verified for this commit and plan version"]
    V -->|"Mismatch"| F["DISCREPANCY<br/>Create an evidence-backed correction"]
    F --> U
    V -->|"Missing evidence"| M["UNVERIFIED<br/>Collect evidence or request review"]
    M --> E
    V -->|"Plan changed during review"| RV["SUPERSEDED REVIEW<br/>Re-evaluate against the current plan"]
    RV --> IM
```

## Flowchart 2: checkout example with labeled categories

The team starts with a normal plan that does not define every interface detail. Both agents can follow its intent while independently filling the same gap differently. For this demo, monetary amounts are USD integer cents; currency-general conversion is outside the example.

```mermaid
flowchart TD
    P["1 · PLAN + REQUIREMENT v1<br/>Build a shop; checkout displays the backend's final total"]
    P --> CA["2A · TASK + CLAIM — ALICE<br/>Build backend; return total_cents: 4999<br/>ASSUMPTION: the page understands cents"]
    P --> CB["2B · TASK + CLAIM — BOB<br/>Build checkout page; expect total: 49.99<br/>ASSUMPTION: the backend returns dollars"]
    CA --> D["3 · DEPENDENCY + DISCREPANCY<br/>Bob's page consumes Alice's response<br/>Field names and units disagree"]
    CB --> D
    D --> A["4 · AGREEMENT / CONTRACT<br/>v1: use integer total_cents<br/>After approved change: v2 also supplies subtotal_cents and tax_cents<br/>Agents coordinate and accept the applicable agreement"]
    A --> U["5 · DIRECTIVES + ACKNOWLEDGMENT<br/>v1: Bob uses total_cents and matching mock data<br/>v2: Alice adds the breakdown; Bob displays it<br/>Agents receive, acknowledge, and revise claims at checkpoints"]
    U --> B["6 · IMPLEMENTATION<br/>Both agents build and test against the current agreement"]
    B --> E["7 · EVIDENCE<br/>Code is pushed; relevant tests run on that commit"]
    E --> V["8 · VERIFICATION<br/>Check the response AND the page against the current version"]

    B -.->|"Team changes its mind"| CP["C1 · NEW REQUIREMENT<br/>Show subtotal and tax separately before payment"]
    CP --> AP["C2 · HUMAN APPROVAL + PLAN v2<br/>Keep the final total; also show subtotal and tax<br/>Confirm that their sum equals the final total in this demo"]
    AP --> IM["C3 · DEPENDENCY / IMPACT CHECK<br/>Backend must provide the breakdown<br/>Checkout page must display it"]
    IM -->|"Alice and Bob affected"| RP["C4 · REPLAN<br/>Old claims need revision<br/>Propose subtotal_cents and tax_cents alongside total_cents"]
    RP --> CA
    RP --> CB
    IM -->|"Unrelated task"| UC["Product-description work continues"]

    V -->|"Current agreement implemented"| OK["PASS<br/>The checked price behavior follows the current plan"]
    V -->|"Only total implemented after v2 approval"| F["DISCREPANCY<br/>Code follows v1, but the team approved v2"]
    F --> U
    V -->|"Insufficient evidence"| M["UNVERIFIED<br/>Request evidence or review"]
    M --> E
    V -->|"Plan changes during review"| RV["SUPERSEDED REVIEW<br/>Recheck current requirements; do not publish an outdated pass"]
    RV --> IM
```

The v1 fields in stages 2A and 2B describe the first pass. On a C4 return, replace those claims with revisions targeting v2; do not recreate the original assumptions. The applicable v2 agreement is established before v2 directives are delivered.

## Demo fixtures

### Before coordination

Alice proposes this response:

```json
{"total_cents": 4999, "currency": "USD"}
```

Bob independently mocks this response:

```json
{"total": 49.99, "currency": "USD"}
```

Different files can merge cleanly even though these expectations are incompatible. Tests built around each agent's own mock may also pass independently.

### After the approved requirement change

An example response satisfying the v2 agreement:

```json
{"subtotal_cents": 4500, "tax_cents": 499, "total_cents": 4999, "currency": "USD"}
```

The page should show subtotal $45.00, tax $4.99, and total $49.99. These are synthetic amounts for an interface demonstration, not tax guidance. Verification should check both response values and the consumer's behavior; the presence of fields alone is insufficient.

## Implementation rules for agents

1. **Preserve authority.** A generated proposal is not an approved requirement. Follow existing authoritative interfaces when present. Escalate ambiguous product decisions to people.
2. **Make declarations explicit.** GitHub reveals pushed code, not an agent's unreported plans. Claim and checkpoint integration is necessary for pre-implementation coordination.
3. **Version decisions.** Bind claims, agreements, directives, evidence, and reviews to their versions. Revalidate before publishing a result if the plan, dependent agreements, or reviewed commit changed.
4. **Coordinate affected work only.** Use dependencies to select recipients. Do not pause all unrelated work merely because one requirement changed.
5. **Respect checkpoint limits.** No universal live interruption is assumed. Mark an update as pending until the agent retrieves and acknowledges it. Do not claim stale local work has stopped automatically.
6. **Separate delivery from completion.** Queued, acknowledged, implemented, and verified are different states. An acknowledgment alone cannot pass verification.
7. **Review changed claims.** Material claim revisions must pass the comparison stage before approval. The diagrams compress this internal re-review to keep the main path readable.
8. **Use evidence for corrections.** A completion message is not proof. Cite the affected requirement/agreement and actual evidence when reporting a discrepancy.
9. **Fail honestly.** Missing or stale evidence means unverified. On GitHub errors, suspend dependent approvals/directives until fresh state is available; show the limitation if an existing GitHub check cannot be updated.
10. **Keep action authority outside model text.** Validate structured outputs and permissions in application code. Directives are data for the receiving agent, not arbitrary executable commands.
11. **Scope the claim.** A passing review covers checked behavior at a particular commit and plan version. It does not establish overall application correctness.

## Legend for ownership

- **Humans:** approve product intent, requirement changes, and unresolved product tradeoffs.
- **Coding agents:** propose implementation details, declare assumptions, acknowledge directives, and write code/tests.
- **Midflight:** compare declarations, track dependencies and versions, coordinate agreements, deliver scoped updates, and verify evidence.
- **GitHub / CI:** supply pushed-code events, commit-specific evidence, test results, and the check surface.

## Demonstration success conditions

- A sensible initial plan exists before any agent starts.
- Midflight catches the initial field-name/unit discrepancy before substantial implementation.
- Agents establish and implement a shared v1 agreement.
- A human-approved mid-build requirement change creates v2.
- Alice and Bob receive targeted updates; an unrelated task continues.
- An implementation that only satisfies v1 cannot pass review against v2.
- Corrected implementation and supporting tests pass the applicable v2 checks.
- The UI distinguishes update delivery from verified implementation.
