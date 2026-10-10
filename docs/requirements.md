# Midflight — Project Requirements

Version: 0.2<br/>
Status: Draft for team review. Updated October 7 with decisions D1–D15.<br/>
Created: October 6, 2026<br/>
Team: Team Yoga<br/>
Project lead: Somesh Agrawal

## How to use this document

- **Coding agents:** don't read this end to end. Find your task's use cases in
  [development-plan.md](development-plan.md), then look up the FR and NFR IDs those
  use cases cite. [§14](#14-traceability) maps every requirement to its use cases
  and tasks.
- Each requirement has a stable ID (`FR-04`, `NFR-03`). Cite IDs in tests, PRs, and
  findings.
- Acceptance checkboxes are gates for the finished MVP, not a record of what works
  today.
- Exact names (states, tools, check names) are in [domain.md](domain.md). Decisions
  that changed this document are in [design-decisions.md](design-decisions.md).
- Everything in §5 and §6 is P0: required for the demo, not optional.

## 1. Product purpose

Midflight helps an integration lead keep teammates' coding agents aligned while they work. It compares intended work with a shared plan, identifies conflicts between active tasks, distributes requirement changes, and verifies pushed code against approved claims.

The product should reduce repeated integration review and catch contract drift early. It does not guarantee that code is correct or eliminate human review.

## 2. Intended users

| User | Need |
| --- | --- |
| Integration lead | Maintain the shared plan, see conflicting work, resolve requirement disagreements, and inspect verification evidence. |
| Developer | Understand the approved scope of their task and respond to changes without repeatedly coordinating by hand. |
| Coding agent | Declare intended work, retrieve current requirements, receive scoped updates, and report acknowledgment. |

The initial target is a team of 2–4 developers, each working through a coding agent.

## 3. Scope and priorities

- **P0 — Hackathon MVP:** Required for the complete demonstration. Includes the essential reliability and failure behavior.
- **P1 — After the MVP:** Proposed enhancements to implement only after P0 works reliably.
- **Out of scope:** Explicitly excluded from the initial implementation.

The MVP is one hosted service (D16) that any team can join: each project has one GitHub repository, one integration lead, at least two participating coding-agent sessions, a structured shared plan, and verification of branches associated with open pull requests.

All requirements are initially unimplemented. Acceptance checkboxes are completion gates, not a record of current functionality.

## 4. Core workflow

1. The lead creates and approves a versioned plan with requirements and interface contracts.
2. A coding agent submits a claim describing its intended work before implementation.
3. Midflight checks the claim against the plan and other active claims.
4. The agent proceeds after approval, or revises its claim in response to findings.
5. The lead changes a requirement when needed.
6. Midflight identifies affected tasks and creates scoped directives.
7. Participating agents retrieve and acknowledge directives at checkpoints.
8. A developer pushes code to a branch associated with an open pull request.
9. Midflight reviews the exact commit and publishes a GitHub check with supporting evidence.
10. Requirement disagreements and uncertain findings are escalated to the lead.

## 5. Functional requirements — P0

### FR-01 — Configure the project and participants

- People sign in with GitHub through the hosted connector (D17); nothing is installed or self-hosted (D16).
- A signed-in person creates a project for a repository where the Midflight GitHub App is installed and they have admin rights, and becomes its lead (D18).
- Teammates join with the project's join code; the lead assigns plan tasks to members, can rotate the code, and can remove members.
- Associate claims with the submitting agent, developer, task, and branch.
- Enforce project and role boundaries on API requests.

Acceptance criteria:
- [ ] A configured participant can access their project's permitted operations.
- [ ] An unauthenticated caller cannot read project data or submit mutations.
- [ ] A developer or agent cannot perform lead-only plan approval or conflict resolution.

### FR-02 — Maintain a structured, versioned shared plan

- Store stable requirement IDs, descriptions, acceptance criteria, tasks, and interface contracts.
- Identify which tasks provide or consume each interface.
- Keep an immutable history of approved plan versions.
- Allow the lead to approve plan changes with a reason.
- Associate every claim, directive, and verification result with the plan version it uses.
- Distinguish proposed requirements from the authoritative approved plan.

Acceptance criteria:
- [ ] A lead can create a plan and approve a new version.
- [ ] Previous approved versions remain available for inspection.
- [ ] A coding agent cannot silently change the approved requirements.
- [ ] A change identifies the requirement and contract IDs that were modified.

### FR-03 — Submit and manage work claims

- Require a claim before a participating agent begins implementation.
- Capture task ID, agent ID, developer, branch, base commit SHA, plan version, requirement IDs, intended files, provided interfaces, consumed interfaces, and acceptance criteria.
- Validate required fields and references before reviewing a claim.
- Allow agents to revise or withdraw their claims and explicitly close completed work (`status: closed`, D11).
- Retain claim revision history.
- Track `draft`, `pending`, `approved`, `needs_revision`, `human_review_required`, `withdrawn`, and `closed` states. An incomplete claim is saved as `draft` and cannot be approved until its interfaces (or an explicit `no_interfaces: true`) and acceptance criteria exist (D5, D12).

Acceptance criteria:
- [ ] A valid submission receives a stable claim ID and a review job ID.
- [ ] Invalid or unknown requirement references return an actionable error.
- [ ] Revisions preserve prior claim contents and findings.
- [ ] Withdrawn or closed claims no longer reserve active work.

### FR-04 — Check claims for alignment and conflicts

- Compare each claim with the approved plan and other active claims.
- Use deterministic checks for stale versions, missing references, and explicit contract mismatches.
- Use the coordinating agent to identify semantic conflicts, unsupported scope, and incompatible interpretations.
- Treat shared file access as a potential conflict, not an automatic rejection.
- Return an approval, revision request, or request for human resolution.
- Include affected requirement/claim IDs, evidence, an explanation, and a proposed correction in findings.
- Validate model output before accepting it as a finding.

Acceptance criteria:
- [ ] Two compatible claims can both be approved.
- [ ] Incompatible producer/consumer interface assumptions are identified before coding.
- [ ] Harmless file overlap does not automatically block work.
- [ ] A malformed model response cannot produce an approval.
- [ ] Two simultaneous submissions cannot both be approved using obsolete claim-state snapshots.

### FR-05 — Identify tasks affected by a plan change

- On approval of a new plan version, inspect active claims and declared dependencies.
- Identify directly affected tasks and downstream consumers of changed interfaces.
- Explain why each selected task is affected.
- Leave unrelated tasks unchanged.
- Mark affected approvals as requiring revalidation when their underlying requirements change.
- Escalate ambiguous impact instead of inventing a requirement decision.

Acceptance criteria:
- [ ] Changing a response field identifies both its producer and declared consumers.
- [ ] An unrelated documentation task receives no change directive.
- [ ] Affected work cannot retain a current approval without revalidation.

### FR-06 — Create and track scoped directives

- Create a directive for each affected task with a stable ID and recipient.
- Include the source plan version, changed requirement IDs, reason, requested adjustment, and relevant evidence.
- Deliver directives as structured data; never execute directive text as commands.
- Track `queued`, `delivered`, `acknowledged`, `rejected`, `needs_clarification`, and `superseded` delivery states.
- Record the receiving agent's response.
- Supersede directives made obsolete by later approved changes.
- Distinguish acknowledgment from proof that the code has been corrected.

Acceptance criteria:
- [ ] An affected agent can retrieve an actionable directive for its own task.
- [ ] Acknowledgment is visible to the lead.
- [ ] An obsolete directive is not presented as current work.
- [ ] Duplicate processing does not create duplicate actionable directives.

### FR-07 — Integrate with coding agents through checkpoints

- Serve a hosted remote MCP endpoint (OAuth, streamable HTTP) exposing `submit_claim`, `check_in`, and `acknowledge_directive` (D3), plus project and lead tools (D16).
- `submit_claim` waits up to 60 seconds and returns the verdict in the same call. A longer review returns `pending` with a job ID, and the verdict arrives with the next `check_in`, without resubmitting the claim.
- Every tool reply carries the task's unacknowledged directives.
- Provide a git pre-push hook that refuses a push while a blocking directive is unacknowledged or the claim is not approved for the current plan version, and a Claude Code hook that runs `check_in` automatically.
- Deliver checkpoint rules to the agent through the MCP adapter's server instructions and tool descriptions (D10): list assumptions in the claim; plan checkpoints at the critical points of the task (before implementation, before building on a contract or shared interface, when an assumption or the scope changes, before pushing); call `check_in` at each; submit a revised claim when an assumption or the scope changes and wait for the verdict.
- Return current plan context and unresolved directives at checkpoints.
- Demonstrate the integration with at least two actual coding-agent sessions.

Acceptance criteria:
- [ ] Both agent sessions can submit claims and retrieve review results.
- [ ] A plan change becomes visible at an affected agent's next checkpoint.
- [ ] An agent given only the adapter's instructions lists its assumptions in the claim and checks in at a critical point before pushing.
- [ ] An assumption added mid-task reaches Midflight as a revised claim and gets a verdict before the agent builds on it.
- [ ] An agent with unresolved blocking findings is instructed to pause or revise its work.
- [ ] The interface states that acknowledgment does not equal completed implementation.

Constraint: The MVP relies on agent cooperation at checkpoints. It does not guarantee interruption of arbitrary running coding agents or prevent edits outside the integration.

### FR-08 — Integrate with GitHub

- Use a GitHub App to read repository content and pull requests and write check runs.
- Receive authenticated GitHub webhook events. Verification starts on `workflow_run.completed` for the contract-test workflow, so test evidence exists for the commit (D4).
- Validate webhook signatures before accepting events.
- Persist or enqueue accepted events before acknowledging successful receipt.
- Fetch current GitHub state rather than assuming webhook arrival order is authoritative.
- Track installation, repository, pull request, branch, base SHA, and head SHA for each review.
- Handle pagination and explicitly detect missing, truncated, or unsupported evidence.

Acceptance criteria:
- [ ] An invalid webhook signature is rejected.
- [ ] A relevant push triggers a verification job for the correct commit.
- [ ] Repeated or out-of-order events cannot overwrite newer results with obsolete results.
- [ ] Incomplete evidence cannot produce a successful verification.

### FR-09 — Verify pushed code against the claim and plan

- Compare the exact commit's changes with the approved claim and current approved requirements.
- Detect undeclared changes, missing required changes, and interface contract violations within the supported demo scope.
- Inspect relevant file content in addition to agent completion messages.
- Incorporate contract-test evidence tied to the reviewed commit.
- Use model reasoning for semantic findings and deterministic checks for explicit contract rules.
- Publish the `midflight/verify` GitHub check with findings and evidence.
- Record verified success, demonstrated failure, human review needed, or incomplete/stale review as distinct outcomes.
- Allow reruns after corrections or human resolution.
- Never reuse a result for a different commit or an obsolete plan version.

Acceptance criteria:
- [ ] A claim-compliant change passes the supported checks.
- [ ] Code that violates the agreed contract fails even if its agent reports completion.
- [ ] Ambiguous findings request human review instead of silently passing.
- [ ] Missing evidence or stale dependencies cannot produce success.
- [ ] A newer commit supersedes an in-progress review of an older commit.
- [ ] The demo repository requires `midflight/verify` before merge, using GitHub branch protection or rulesets.

Constraint: Verification covers declared requirements and available evidence. It is not a guarantee of overall code correctness. Execute repository tests in isolated CI, not in the coordinator's privileged runtime.

### FR-10 — Escalate conflicts for human resolution

- Present competing requirements and their evidence to the lead.
- Allow the lead to clarify the plan, request a claim revision, or dismiss an unsupported finding with a reason.
- Record who resolved the conflict and the explanation.
- Trigger revalidation after changes to requirements or claims.
- Do not let the coordinating agent choose between conflicting human requirements on its own.

Acceptance criteria:
- [ ] Unresolved requirement conflicts remain visible and prevent affected approvals.
- [ ] A lead's resolution is recorded and traceable to subsequent revalidation.
- [ ] Dismissing a finding does not erase the original evidence.

### FR-11 — Provide an integration dashboard

- Show the current approved plan and version.
- List active tasks, agents, branches, claims, and approval states.
- Show conflicts, supporting evidence, and resolution actions.
- Show directives and acknowledgment states.
- Display verification status for each reviewed commit with a GitHub link.
- Display stale-state warnings, last successful synchronization, and outstanding jobs.
- Provide a chronological activity view.
- Support lead-only plan changes and conflict resolution.

Acceptance criteria:
- [ ] The lead can identify which tasks need attention without reading raw logs.
- [ ] Every finding can be traced to its requirement, claim, or code evidence.
- [ ] The dashboard distinguishes a failed check from an incomplete or stale review.

### FR-12 — Preserve a durable audit trail

- Record plan changes, claim submissions and revisions, findings, directives, acknowledgments, verification outcomes, and human resolutions.
- Include timestamps, actor IDs, relevant versions, and correlation/job IDs.
- Record concise decision reasons rather than hidden model reasoning.
- Preserve history when current state changes.
- Exclude credentials and sensitive tokens from logs.

Acceptance criteria:
- [ ] A reviewer can reconstruct why a directive or failed check was created.
- [ ] Repeated processing does not duplicate the logical audit event.
- [ ] Audit entries remain available after a claim closes.

## 6. Reliability and safety requirements — P0

| ID | Requirement | Acceptance gate |
| --- | --- | --- |
| NFR-01 | Process slow reviews asynchronously. | Claim submissions and webhook handling do not wait for model completion; callers can retrieve job status. |
| NFR-02 | Make state changes safe to retry. | Duplicate webhook and queue delivery produces one logical outcome. |
| NFR-03 | Protect concurrent updates. | Approval writes validate the plan and claim-state versions used during review; obsolete decisions are retried or discarded. |
| NFR-04 | Handle GitHub errors and rate limits. | Mark affected state stale, suppress dependent directives and approvals, respect retry guidance, and reconcile after recovery. |
| NFR-05 | Bound model and network work. | Use timeouts, limited retries, input limits, and explicit incomplete-review outcomes. |
| NFR-06 | Preserve failed jobs for inspection. | Exhausted retries become visible failures with a recoverable job record or dead-letter queue entry. |
| NFR-07 | Enforce authorization in application code. | Only permitted identities can change state; model-generated content cannot grant permissions. |
| NFR-08 | Treat repository content as untrusted evidence. | Instructions embedded in code, comments, diffs, or descriptions cannot trigger arbitrary tool execution or change the approved plan. |
| NFR-09 | Protect credentials. | GitHub secrets are stored securely, backend roles use scoped permissions, and tokens are absent from source control and logs. |
| NFR-10 | Keep verification evidence trustworthy. | Test expectations are controlled independently of the branch being reviewed, and results are associated with the correct commit. |
| NFR-11 | Make deployment reproducible. | Commit dependency locks, infrastructure configuration, and documented setup steps. |
| NFR-12 | Observe behavior and cost. | Record job latency, errors, model usage where available, and verification outcomes without logging credentials. |

Outage limitation: When GitHub is unavailable, Midflight may be unable to update a previously published check. The dashboard must report that limitation and reconcile checks after recovery. Do not claim that every outage immediately revokes a green GitHub check.

## 7. Minimum data model

| Entity | Required information |
| --- | --- |
| Project | Repository, GitHub installation, participants, lead, current plan version, synchronization state |
| Plan version | Version, approver, timestamp, requirements, contracts, tasks, dependency links, change reason |
| Claim revision | Claim/revision IDs, agent, developer, task, branch, base SHA, plan version, scope, interfaces, criteria, state |
| Finding | Type, severity, affected IDs, evidence, explanation, proposed correction, resolution state |
| Directive | ID, recipient, task, plan version, changed requirements, requested adjustment, reason, delivery state |
| Verification | Job ID, claim revision, plan version, base/head SHAs, evidence coverage, findings, test results, GitHub check ID, outcome |
| Processing job | Event identity, job type, attempt count, state, timestamps, error, correlation ID |
| Audit event | Actor, action, timestamp, related entity/version IDs, reason, correlation ID |

The approved plan and durable application state are authoritative. Agent conversation history is not a substitute for either.

## 8. Proposed implementation stack

These choices come from the [development plan](development-plan.md#architecture-baseline) and can change without changing the product requirements.

| Area | Initial choice |
| --- | --- |
| Language and validation | Python 3.12, Pydantic, uv |
| Coordinating agent | A Bedrock model through the Converse API (D21), configured with `MIDFLIGHT_REVIEWER_MODEL`; default Claude Sonnet 5.5, to be confirmed by the S-8 eval |
| Agent hosting | Runs inside the worker Lambda (AgentCore Runtime not required; D1) |
| API | FastAPI on a Lambda behind a Lambda Function URL (D19), serving REST, `/mcp`, OAuth, and the GitHub webhook |
| Persistent state | DynamoDB through Boto3 |
| Background processing | DynamoDB Streams trigger the worker Lambda; SQS dead-letter queue; idempotency keys on every write |
| GitHub | GitHub App, REST calls with httpx (D23) |
| Agent connection | Hosted remote MCP endpoint on the official MCP Python SDK 2.x (`MCPServer`), with its OAuth server and Sign in with GitHub (D16, D17); a git pre-push hook; the local stdio adapter is a development tool (D20) |
| Lead interface | Lead tools in the same connector (`project_status`, plan and escalation tools); a read-only status page is stretch |
| Tests and CI | pytest, GitHub Actions |
| Deployment and operations | AWS SAM, Secrets Manager, CloudWatch |

## 9. Proposed enhancements — P1

These are optional follow-up ideas, not required commitments for the hackathon.

- [ ] Support multiple repositories and projects.
- [ ] Add adapters or host-specific hooks for additional coding-agent environments.
- [ ] Add near-real-time delivery where the coding-agent host supports it.
- [ ] Show a visual dependency graph of tasks and interfaces.
- [ ] Import draft requirements from repository documents or issues, with lead approval before activation.
- [ ] Add claim leases or inactivity reminders to identify abandoned work.
- [ ] Add configurable conflict policies and approval rules.
- [ ] Support more programming languages and contract formats.
- [ ] Offer a hosted dashboard with team sign-in.
- [ ] Add team-authorized notifications outside the dashboard.
- [ ] Export audit history and measured coordination metrics.

## 10. Out of scope for the MVP

- Automatically merging pull requests or resolving code merge conflicts.
- Autonomously choosing between conflicting human requirements.
- Guaranteeing correctness, security, or compatibility of arbitrary code.
- Guaranteeing immediate interruption of every coding-agent host.
- Preventing developers from editing outside the cooperative checkpoint workflow.
- Training or fine-tuning a model.
- Adding a vector database, generalized repository knowledge graph, or multi-agent coordinator swarm.
- Running arbitrary repository code in the privileged coordinator runtime.
- Production-scale multi-tenancy, billing, and enterprise administration.
- Removing the need for human code review.

## 11. Required demonstration and evaluation

Use a synthetic checkout project with a backend task, a frontend task, and an unrelated documentation task. The initial contract returns `total_cents` as an integer.

| Scenario | Expected result |
| --- | --- |
| Compatible backend/frontend claims | Both claims are approved. |
| Frontend expects decimal `total` while backend provides integer `total_cents` | Midflight identifies the incompatible contract before implementation. |
| Two tasks harmlessly touch the same file | File overlap is visible without an automatic rejection. |
| Lead adds a required `currency` field | Affected producer and consumer tasks receive scoped directives. |
| Unrelated documentation task | No irrelevant directive is issued. |
| Agent reports completion but pushes the wrong field | Verification fails with code or contract-test evidence. |
| GitHub failure or simulated rate limit | State becomes stale and dependent directives stop until fresh evidence is available. |
| Duplicate webhook | No duplicate logical review outcome or directive. |
| Simultaneous conflicting claims | No conflicting approvals based on an obsolete snapshot. |
| New commit or plan version arrives during review | The obsolete result cannot establish current verification success. |
| Instruction-like text appears in repository content | It is treated as data and cannot authorize actions. |
| Correction and recovery | Fresh verification succeeds and the audit trail explains the transition. |

Measure detection results, unnecessary blocks, review latency, acknowledgment status, and observed model usage. Report actual measurements; do not invent hours or tokens saved.

## 12. Definition of done

- [ ] All P0 acceptance criteria pass in the supported demo scope.
- [ ] At least two actual coding-agent sessions participate through the integration.
- [ ] A real GitHub push reaches the deployed AWS backend and produces a check.
- [ ] The four capabilities — claim, check, propagate, and verify — work together.
- [ ] Both advertised failure paths are demonstrated: false completion and stale GitHub data.
- [ ] Human requirement conflicts are escalated and resolved through an audited workflow.
- [ ] The dashboard clearly displays evidence, current state, and unresolved work.
- [ ] Automated tests cover the key deterministic rules and retry/concurrency behavior.
- [ ] Setup, deployment, permissions, limitations, and demo instructions are documented.
- [ ] The demo uses synthetic project data and no real user data.
- [ ] A repeatable demo script and backup recording are ready.

## 13. Decisions

Settled and open decisions live in [design-decisions.md](design-decisions.md).
As of October 7: team and ownership are in [development-plan.md](development-plan.md);
the demo uses two Claude Code sessions (D6) and the `currency` change (D2); the MVP
uses hashed, revocable bearer tokens per participant (UC-01); REST paths are fixed in
[domain.md](domain.md#rest-api) (D15). The AWS region (D7),
video rules (D9), limits and timeouts, hosted dashboard, and the official cutoff are
still open.

## 14. Traceability

Use this table to find what implements a requirement and where it is tested. Task
IDs are from [development-plan.md](development-plan.md); use cases are in
[use-cases.md](use-cases.md); invariants are in [domain.md](domain.md#invariants).

| Requirement | Use cases | Tasks | Invariants |
| --- | --- | --- | --- |
| FR-01 Project and participants | UC-01 | M-2, S-1, H-1, H-3, H-4 | INV-08, INV-12 |
| FR-02 Versioned plan | UC-03 | S-1, S-6, M-2 | INV-04 |
| FR-03 Claims | UC-04, UC-06 | S-3, M-2, M-3 | — |
| FR-04 Claim checks | UC-04, UC-05, UC-12 | S-2, S-3, S-5, S-8 | INV-01, INV-02, INV-14 |
| FR-05 Affected tasks | UC-08, UC-12 | S-6 | INV-11 |
| FR-06 Directives | UC-07, UC-08, UC-09 | S-6, M-3, M-4 | INV-05, INV-10 |
| FR-07 Agent checkpoints | UC-02, UC-07, UC-09, UC-16 | M-3, M-4, F-3 | INV-07 |
| FR-08 GitHub integration | UC-10, UC-15 | M-6, M-7 | INV-03, INV-06 |
| FR-09 Verification | UC-10, UC-11, UC-12 | S-10, M-6, F-2 | INV-03, INV-04, INV-15 |
| FR-10 Escalation | UC-03, UC-12, UC-13 | S-7 | INV-11 |
| FR-11 Dashboard | UC-14 | S-9 | — |
| FR-12 Audit trail | UC-13, UC-14 | S-3, S-6, S-7, S-9 | INV-13 |
| NFR-01 Async reviews | UC-04 | M-3, M-5 | — |
| NFR-02 Safe retries | UC-05, UC-08 | S-3, S-6, M-5 | INV-05, INV-06 |
| NFR-03 Concurrent updates | UC-05 | S-3, M-5 | INV-02 |
| NFR-04 GitHub errors | UC-15 | M-7 | INV-09 |
| NFR-05 Bounded work | UC-05 | S-5, M-5 | — |
| NFR-06 Failed jobs visible | UC-14, UC-15 | M-5, S-9 | — |
| NFR-07 Authorization | UC-01 | M-2 | INV-08 |
| NFR-08 Untrusted content | UC-10 | S-5, S-10, S-8 | INV-07 |
| NFR-09 Credentials | UC-01 | M-2, M-5, M-6 | INV-12 |
| NFR-10 Trustworthy evidence | UC-10 | F-2, M-6, S-10 | INV-15 |
| NFR-11 Reproducible deploy | — | M-1, M-5 | — |
| NFR-12 Behavior and cost | UC-14 | M-5, S-8 | — |
