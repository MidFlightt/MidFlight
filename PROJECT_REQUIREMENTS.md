# Midflight — Project Requirements

Version: 0.1<br/>
Status: Draft for team review<br/>
Created: October 6, 2026<br/>
Team: Team Yoga<br/>
Project lead: Somesh Agrawal

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

The MVP supports one configured GitHub repository, one integration lead, at least two participating coding-agent sessions, a structured shared plan, and verification of branches associated with open pull requests.

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

- Associate the project with one GitHub repository and its GitHub App installation.
- Register the integration lead, developers, and coding-agent identities.
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
- Allow agents to revise or withdraw their claims and explicitly close completed work.
- Retain claim revision history.
- Track `pending`, `approved`, `needs_revision`, `human_review_required`, `withdrawn`, and `closed` states.

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
- Track `pending`, `acknowledged`, `rejected`, `needs_clarification`, and `superseded` delivery states.
- Record the receiving agent's response.
- Supersede directives made obsolete by later approved changes.
- Distinguish acknowledgment from proof that the code has been corrected.

Acceptance criteria:
- [ ] An affected agent can retrieve an actionable directive for its own task.
- [ ] Acknowledgment is visible to the lead.
- [ ] An obsolete directive is not presented as current work.
- [ ] Duplicate processing does not create duplicate actionable directives.

### FR-07 — Integrate with coding agents through checkpoints

- Provide a local MCP adapter exposing `submit_claim`, `get_task_context`, `get_directives`, and `acknowledge_directive`.
- Let clients retrieve asynchronous review status without resubmitting the claim.
- Document that participating agents must check before implementation, between meaningful work steps, and before pushing.
- Return current plan context and unresolved directives at checkpoints.
- Demonstrate the integration with at least two actual coding-agent sessions.

Acceptance criteria:
- [ ] Both agent sessions can submit claims and retrieve review results.
- [ ] A plan change becomes visible at an affected agent's next checkpoint.
- [ ] An agent with unresolved blocking findings is instructed to pause or revise its work.
- [ ] The interface states that acknowledgment does not equal completed implementation.

Constraint: The MVP relies on agent cooperation at checkpoints. It does not guarantee interruption of arbitrary running coding agents or prevent edits outside the integration.

### FR-08 — Integrate with GitHub

- Use a GitHub App to read repository content and pull requests and write check runs.
- Receive authenticated GitHub webhook events for relevant pull-request and branch changes.
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

These choices come from the initial development plan and can change without changing the product requirements.

| Area | Initial choice |
| --- | --- |
| Language and validation | Python 3.12, Pydantic, uv |
| Coordinating agent | Strands Agents SDK with a configurable Bedrock model; initial candidate: Claude Sonnet 4.5 |
| Agent hosting | Amazon Bedrock AgentCore Runtime |
| API | FastAPI and Mangum on Lambda behind API Gateway HTTP API |
| Persistent state | DynamoDB through Boto3 |
| Background processing | SQS, worker Lambda, dead-letter queue |
| GitHub | GitHub App, REST API, HTTPX |
| Agent adapter | Official MCP Python SDK, local stdio transport |
| Dashboard | Streamlit; local hosting is acceptable for the hackathon demo |
| Tests and CI | pytest, GitHub Actions |
| Deployment and operations | AWS SAM for supporting infrastructure, AgentCore deployment tooling, Secrets Manager, CloudWatch |

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

## 13. Decisions still to confirm

- Team name, lead, and member ownership.
- The two coding-agent environments used for the demonstration.
- Demo repository and AWS account/region, including model access.
- Concrete API authentication mechanism for the MVP.
- Final approved demo contracts and acceptance tests.
- Input size limits, retry limits, and review timeout settings.
- Whether submission requires a publicly hosted dashboard.
- The official October 11 submission cutoff; plan to finish on October 10 until clarified.
