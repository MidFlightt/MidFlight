# Midflight: shared vocabulary and coordination workflows

Version: 1.1 | October 6, 2026 | Design reference, not implemented functionality

This document describes the brainstormed coordination service and complements the [open design decisions](design-decisions.md) and [proposed system architecture](../systemarchitecture.md). It does not amend the [draft project requirements](../PROJECT_REQUIREMENTS.md); the documents illustrate different proposed requirement-change examples until the team selects one. The diagrams assume a GitHub-connected project and participating coding agents that consult Midflight at supported checkpoints.

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

Color identifies the **workflow**, not the actor. The owner label inside every node identifies **who performs the action**. A purple border additionally highlights nodes where **MIDFLIGHT** has a direct role; shared labels identify shared responsibility.

| Color | Workflow | What to follow |
| --- | --- | --- |
| Blue | Initial planning and implementation | Plan, claims, comparison, agreement, delivery, and building. |
| Amber | Requirement change | Proposal, human approval, impact analysis, and replanning affected work. |
| Green | Evidence and verification | Collect implementation evidence, review it, and publish a scoped pass. |
| Red | Correction loop | An evidenced mismatch produces a correction directive and another implementation attempt. |
| Gray | Waiting or unaffected work | Missing evidence remains unverified; unrelated work continues. |

- **MIDFLIGHT owner label + purple outline:** Midflight executes or coordinates this stage.
- **HUMANS:** own product decisions and approve requirement changes.
- **CODING AGENTS:** declare, accept technical agreements under team policy, acknowledge, and implement.
- **GITHUB / CI:** supply repository events, commit-specific code, and test evidence.
- **Shared owner labels:** each actor has a distinct part; for example, humans approve a change and Midflight records the new version.
- **Numbered stages 1-8:** normal coordination and verification. **C1-C4:** requirement-change path, available at any time.
- **Solid arrows:** process flow or update delivery. **Dashed arrows:** a possible change during work. **Arrow labels:** outcomes and return paths.
- Acknowledged means received, not implemented. Verified covers checked behavior, not the entire app.

## Where Midflight comes in

| Stage | Midflight's responsibility | Responsibility retained elsewhere |
| --- | --- | --- |
| 3: Compare | Map dependencies, inspect claims and known interfaces, and identify discrepancies or unresolved assumptions. | Agents must report their intentions; Midflight cannot see unreported local plans. |
| 4: Create an agreement | Reuse an authoritative contract if one exists; otherwise propose a shared contract, coordinate acceptance, and record the agreed version. | Agents accept technical details under team policy. Humans resolve ambiguous product behavior. A proposal is not an agreement until accepted. |
| 5: Deliver updates | Create scoped directives, expose them at checkpoints, track acknowledgment, and re-review revised claims. | Coding agents retrieve, acknowledge, and implement; Midflight does not write their code or force an immediate interruption. |
| C2: Record approval | Record the human-approved change as a new plan version. | Humans approve the product change. |
| C3-C4: Propagate change | Find affected tasks, invalidate obsolete approvals, request revised claims, and leave unrelated work alone. | Agents replan and pick up updates at their next checkpoint. |
| 8: Verify | Compare evidence with current decisions and publish a scoped result. | GitHub/CI supply evidence; passing does not prove every behavior works. |
| Correction and waiting | Explain an evidenced mismatch, issue a correction directive, or keep a review unresolved when evidence is missing. | Agents correct the code; humans review unresolved questions when needed. |

## Flowchart 1: workflow with definitions

Read the normal path first. Follow C1-C4 when a requirement changes. Affected tasks return to claim review; unrelated work continues.

```mermaid
flowchart TD
    P["1 · PLAN + REQUIREMENTS<br/>OWNER: HUMANS<br/>Approve product behavior and divide the work"]
    P --> C["2 · TASKS + CLAIMS<br/>OWNER: CODING AGENTS<br/>Declare intended work and identify ASSUMPTIONS"]
    C --> D["3 · DEPENDENCIES + DISCREPANCIES<br/>OWNER: MIDFLIGHT<br/>Compare connected claims and current requirements"]
    D --> A["4 · AGREEMENT / CONTRACT<br/>OWNER: MIDFLIGHT + AGENTS<br/>Midflight reuses or proposes a contract, coordinates acceptance, and records it<br/>Humans decide ambiguous product behavior"]
    A --> U["5 · DIRECTIVES + ACKNOWLEDGMENT<br/>OWNER: MIDFLIGHT + AGENTS<br/>Midflight sends scoped updates and tracks acknowledgment<br/>Agents retrieve at checkpoints and revise claims; Midflight re-reviews"]
    U --> B["6 · IMPLEMENTATION<br/>OWNER: CODING AGENTS<br/>Build against the current agreement"]
    B --> E["7 · EVIDENCE<br/>OWNER: AGENTS + GITHUB / CI<br/>Push code and supply relevant tests for that commit"]
    E --> V["8 · VERIFICATION<br/>OWNER: MIDFLIGHT<br/>Compare evidence with the current plan and agreements"]

    B -.->|"Change proposed during work"| CP["C1 · PROPOSED REQUIREMENT CHANGE<br/>OWNER: HUMANS<br/>Describe the new product behavior"]
    CP --> AP["C2 · APPROVAL + NEW PLAN VERSION<br/>OWNER: HUMANS + MIDFLIGHT<br/>Humans approve; Midflight records the new version<br/>Unapproved proposals do not replace the plan"]
    AP --> IM["C3 · IMPACT CHECK<br/>OWNER: MIDFLIGHT<br/>Follow dependencies to identify affected tasks"]
    IM -->|"Affected"| RP["C4 · REPLAN<br/>OWNER: MIDFLIGHT + AGENTS<br/>Midflight invalidates affected approvals and requests revised claims<br/>Agents retrieve the update and replan at checkpoints"]
    RP --> C
    IM -->|"Unaffected"| UC["CONTINUE EXISTING WORK<br/>OWNER: CODING AGENTS<br/>No irrelevant updates"]

    V -->|"Matches and current"| OK["PASS<br/>OWNER: MIDFLIGHT<br/>Publish verification for this commit and plan version"]
    V -->|"Mismatch"| F["CORRECTION / DISCREPANCY<br/>OWNER: MIDFLIGHT<br/>Create an evidence-backed correction directive"]
    F --> U
    V -->|"Missing evidence"| M["UNVERIFIED<br/>OWNER: MIDFLIGHT<br/>Request evidence or human review; do not pass"]
    M --> E
    V -->|"Plan changed during review"| RV["SUPERSEDED REVIEW<br/>OWNER: MIDFLIGHT<br/>Re-evaluate current requirements"]
    RV --> IM

    subgraph LEGEND["LEGEND: fill and arrows = workflow; purple border = Midflight involvement"]
        direction LR
        L1["BLUE<br/>Initial plan and implementation"]
        L2["AMBER<br/>Requirement change"]
        L3["GREEN<br/>Evidence and verification"]
        L4["RED<br/>Correction loop"]
        L5["GRAY<br/>Waiting or unaffected"]
        L6["PURPLE BORDER<br/>Midflight acts or coordinates<br/>Read OWNER for shared responsibility"]
    end

    classDef core fill:#EAF2FC,stroke:#245E9D,color:#15283B,stroke-width:1px;
    classDef change fill:#FFF3DA,stroke:#966419,color:#15283B,stroke-width:1px;
    classDef verify fill:#E8F4ED,stroke:#2C7050,color:#15283B,stroke-width:1px;
    classDef fix fill:#FCECEF,stroke:#B23A48,color:#15283B,stroke-width:1px;
    classDef neutral fill:#F2F5F7,stroke:#697888,color:#15283B,stroke-width:1px;
    classDef midflight stroke:#7654A3,stroke-width:3px;
    class P,C,D,A,U,B,L1,L6 core;
    class CP,AP,IM,RP,RV,L2 change;
    class E,V,OK,L3 verify;
    class F,L4 fix;
    class UC,M,L5 neutral;
    class D,A,U,AP,IM,RP,V,OK,F,M,RV,L6 midflight;
    linkStyle 0,1,2,3,4 stroke:#245E9D,stroke-width:2px;
    linkStyle 5,6,13 stroke:#2C7050,stroke-width:2px;
    linkStyle 7,8,9,10,11,18,19 stroke:#966419,stroke-width:2px;
    linkStyle 14,15 stroke:#B23A48,stroke-width:2px;
    linkStyle 12,16,17 stroke:#697888,stroke-width:2px;
```

## Flowchart 2: checkout example with labeled categories

The team starts with a normal plan that does not define every interface detail. Both agents can follow its intent while independently filling the same gap differently. For this demo, monetary amounts are USD integer cents; currency-general conversion is outside the example.

```mermaid
flowchart TD
    P["1 · PLAN + REQUIREMENT v1<br/>OWNER: HUMANS<br/>Build a shop; checkout displays the backend's final total"]
    P --> CA["2A · TASK + CLAIM - ALICE<br/>OWNER: ALICE'S CODING AGENT<br/>Return total_cents: 4999<br/>ASSUMPTION: the page understands cents"]
    P --> CB["2B · TASK + CLAIM - BOB<br/>OWNER: BOB'S CODING AGENT<br/>Expect total: 49.99<br/>ASSUMPTION: the backend returns dollars"]
    CA --> D["3 · DEPENDENCY + DISCREPANCY<br/>OWNER: MIDFLIGHT<br/>Bob consumes Alice's response<br/>Identify the field-name and unit mismatch"]
    CB --> D
    D --> A["4 · AGREEMENT / CONTRACT<br/>OWNER: MIDFLIGHT + AGENTS<br/>Midflight proposes and records the accepted contract<br/>v1: total_cents; after approval, v2 adds subtotal_cents and tax_cents<br/>Agents accept technical details; humans decide unclear behavior"]
    A --> U["5 · DIRECTIVES + ACKNOWLEDGMENT<br/>OWNER: MIDFLIGHT + AGENTS<br/>Midflight sends targeted updates and tracks receipt<br/>v1: Bob uses total_cents; v2: Alice provides the breakdown and Bob displays it<br/>Agents acknowledge at checkpoints and revise claims"]
    U --> B["6 · IMPLEMENTATION<br/>OWNER: CODING AGENTS<br/>Build and test the current agreement"]
    B --> E["7 · EVIDENCE<br/>OWNER: AGENTS + GITHUB / CI<br/>Push code and run relevant tests on that commit"]
    E --> V["8 · VERIFICATION<br/>OWNER: MIDFLIGHT<br/>Check the response AND page against the current version"]

    B -.->|"Team changes its mind"| CP["C1 · NEW REQUIREMENT<br/>OWNER: HUMANS<br/>Show subtotal and tax separately before payment"]
    CP --> AP["C2 · APPROVAL + PLAN v2<br/>OWNER: HUMANS + MIDFLIGHT<br/>Humans approve the breakdown; Midflight records v2<br/>For this demo, subtotal plus tax equals total"]
    AP --> IM["C3 · DEPENDENCY / IMPACT CHECK<br/>OWNER: MIDFLIGHT<br/>Identify Alice's response and Bob's page as affected"]
    IM -->|"Alice and Bob affected"| RP["C4 · REPLAN<br/>OWNER: MIDFLIGHT + AGENTS<br/>Midflight requests revised claims<br/>Agents propose subtotal_cents and tax_cents alongside total_cents"]
    RP --> CA
    RP --> CB
    IM -->|"Unrelated task"| UC["PRODUCT-DESCRIPTION WORK CONTINUES<br/>OWNER: UNRELATED CODING AGENT"]

    V -->|"Current agreement implemented"| OK["PASS<br/>OWNER: MIDFLIGHT<br/>Publish the scoped verification result"]
    V -->|"Only total implemented after v2 approval"| F["CORRECTION / DISCREPANCY<br/>OWNER: MIDFLIGHT<br/>Explain that code follows v1 while approved v2 needs the breakdown<br/>Send a correction to the affected agent"]
    F --> U
    V -->|"Insufficient evidence"| M["UNVERIFIED<br/>OWNER: MIDFLIGHT<br/>Request evidence or review"]
    M --> E
    V -->|"Plan changes during review"| RV["SUPERSEDED REVIEW<br/>OWNER: MIDFLIGHT<br/>Recheck requirements; do not publish an outdated pass"]
    RV --> IM

    subgraph LEGEND["LEGEND: fill and arrows = workflow; purple border = Midflight involvement"]
        direction LR
        L1["BLUE<br/>Initial plan and implementation"]
        L2["AMBER<br/>Requirement change"]
        L3["GREEN<br/>Evidence and verification"]
        L4["RED<br/>Correction loop"]
        L5["GRAY<br/>Waiting or unaffected"]
        L6["PURPLE BORDER<br/>Midflight acts or coordinates<br/>Read OWNER for shared responsibility"]
    end

    classDef core fill:#EAF2FC,stroke:#245E9D,color:#15283B,stroke-width:1px;
    classDef change fill:#FFF3DA,stroke:#966419,color:#15283B,stroke-width:1px;
    classDef verify fill:#E8F4ED,stroke:#2C7050,color:#15283B,stroke-width:1px;
    classDef fix fill:#FCECEF,stroke:#B23A48,color:#15283B,stroke-width:1px;
    classDef neutral fill:#F2F5F7,stroke:#697888,color:#15283B,stroke-width:1px;
    classDef midflight stroke:#7654A3,stroke-width:3px;
    class P,CA,CB,D,A,U,B,L1,L6 core;
    class CP,AP,IM,RP,RV,L2 change;
    class E,V,OK,L3 verify;
    class F,L4 fix;
    class UC,M,L5 neutral;
    class D,A,U,AP,IM,RP,V,OK,F,M,RV,L6 midflight;
    linkStyle 0,1,2,3,4,5,6 stroke:#245E9D,stroke-width:2px;
    linkStyle 7,8,16 stroke:#2C7050,stroke-width:2px;
    linkStyle 9,10,11,12,13,14,21,22 stroke:#966419,stroke-width:2px;
    linkStyle 17,18 stroke:#B23A48,stroke-width:2px;
    linkStyle 15,19,20 stroke:#697888,stroke-width:2px;
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
