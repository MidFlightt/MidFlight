# Design decisions

The log of choices that shape the build. If another document disagrees with a
decision here, this file wins (see the order in [AGENTS.md](../AGENTS.md#when-documents-disagree)).

**Status meanings:** *Decided* was confirmed by the team. *Default* applies unless
the kickoff call changes it. *To confirm* needs a named person to check a fact.
When a default is confirmed or changed, update its row and the date.

## Kickoff decisions (October 7, 2026)

| ID | Question | Decision | Status | Affects |
| --- | --- | --- | --- | --- |
| D1 | Do the hackathon rules require AgentCore Runtime? | No. The Strands reviewer runs inside the worker Lambda and calls Bedrock directly. It stays behind the `Reviewer` port, so it can move to AgentCore later (stretch task X-1). | Decided Oct 7 | S-5, M-5 |
| D2 | Canonical plan change for the demo | Add `currency: string` to `checkout-response`. The subtotal/tax example in the archived flowcharts is not used. | Default | F-2, S-6, scenarios |
| D3 | Tools agents call | `submit_claim` (waits up to 60 s for the verdict; `status: withdrawn` withdraws), `check_in`, `acknowledge_directive`. Replaces `get_task_context` and `get_directives`. Project and lead tools join them in D16. | Default | M-3, FR-07 |
| D4 | What triggers verification | `workflow_run.completed` for the contract-test workflow, so test evidence exists when verification starts | Default | M-6, FR-08 |
| D5 | Incomplete claims | Saved as `draft`. No approval until interfaces and acceptance criteria are present. | Default | S-3, FR-03 |
| D6 | The two demo agent hosts | Two Claude Code sessions | Default | M-4, F-3 |
| D7 | AWS account, region, Bedrock model access | `us-east-1`. Reviewer model `us.anthropic.claude-sonnet-5-5` (D21) until S-8 measures. Bedrock answers "Operation not allowed" for every model on the new account, so a support case is open and the deploy runs rules only. | To confirm: Somesh (Bedrock access) | S-5, M-5 |
| D8 | Pre-push hook when Midflight is unreachable | Warn and allow. The GitHub check still verifies. | Default | M-4 |
| D9 | Video length and submission format | Check the rules page. Plan for 3 minutes. | To confirm: Frederik | F-1, F-5 |
| D10 | How agents sync while they implement | Agent-planned checkpoints. When an agent connects, the MCP adapter sends instructions (repeated in each tool description) telling it to list its assumptions in the claim, plan checkpoints at the critical points of its task, call `check_in` at each one, and submit a revised claim when an assumption or its scope changes, waiting for the verdict before building on it. No model change: this uses `Claim.assumptions` and claim revisions (UC-06). Checkpoints are guidance, not stored or enforced; the pre-push hook and `midflight/verify` remain the backstop. Tracking them is stretch task X-4. Exact wording: [domain.md](domain.md#interfaces). | Decided Oct 7 (Somesh) | M-3, FR-07, UC-02, UC-07 |

## Consistency pass (October 7, 2026)

Gaps found when checking the specs against each other before S-1. Each one was a
place where two documents, or two tasks, would have built different things.

| ID | Question | Decision | Status | Affects |
| --- | --- | --- | --- | --- |
| D11 | How does an agent close finished work? FR-03 requires it, but D3 only had `status: withdrawn`. | `submit_claim` also accepts `status: closed`. REST: `POST /claims/{cid}/close`. Only an `approved` claim can close. | Default | M-2, M-3, S-3, UC-06 |
| D12 | When is a claim with no interfaces complete? D5 required interfaces, so T3 (contributor guide) could never leave `draft`. | Complete = at least one acceptance criterion, plus at least one `provides`/`consumes` entry **or** `no_interfaces: true`. Otherwise `draft` with an `incomplete_claim` finding. | Default | S-1, S-2, S-3 |
| D13 | Directive kinds and dedupe. A verification failure on plan v2 creates a correction directive for T1, which collided with INV-05's (plan version, task) key. | `Directive.source` is `plan_change` or `verification`, and `Directive.blocking` is a field. Dedupe key: `plan_change` → (plan version, task); `verification` → (verification id). A newer plan supersedes the task's older directives that are still `queued` or `delivered`. | Default | S-1, S-6, S-10, INV-05 |
| D14 | Escalation state transitions. UC-12 moves already-approved claims to `human_review_required`, and UC-13 can request a revision, but the state diagram allowed neither. | Add `approved → human_review_required`, `human_review_required → needs_revision` (lead requests revision), and `human_review_required → withdrawn`. | Default | S-1, S-7 |
| D15 | REST paths. Use cases, step-by-step, and the one-shot prompt used different paths for the same calls. | One table in [domain.md](domain.md#rest-api). Paths are scoped by project id; the adapter reads `MIDFLIGHT_PROJECT`. `check_in` is a `POST` because it marks directives delivered. | Default | M-2, M-3, M-4, S-9 |

## Hosted product (October 8, 2026)

Midflight is one service that Team Yoga hosts for every team, like a Canva or Figma
connector. No customer clones the repo, runs a server, or creates a GitHub App.

| ID | Question | Decision | Status | Affects |
| --- | --- | --- | --- | --- |
| D16 | What do users install? | Nothing. A lead installs the public **MidFlight Team Yoga** GitHub App on their repo and adds Midflight to their AI client as a custom connector (one URL). Teammates add the same URL. A directory listing (one-click Connect) is a post-hackathon submission, not code. | Decided Oct 8 (Somesh) | H-1 to H-5, UC-01, UC-02 |
| D17 | How do people sign in? | **Sign in with GitHub.** Midflight runs the OAuth authorization server the MCP spec asks for (with dynamic client registration, which Claude and ChatGPT use), and sends people to GitHub to log in through the same GitHub App's user authorization. A Midflight user is a GitHub account. Tokens are opaque, short-lived, and stored hashed. | Decided Oct 8 | H-3 |
| D18 | How does a team form? | The person who creates a project is its lead. Creating it returns a **join code**; anyone signed in who enters the code joins as an agent. The lead assigns plan tasks to members, can rotate the code, and can remove a member. One GitHub account can lead or join many projects. | Decided Oct 8 | H-1 |
| D19 | Where does it run? | One web Lambda behind a **Lambda Function URL** serves the REST API, the remote MCP endpoint (`/mcp`, stateless, JSON responses), OAuth, and the GitHub webhook. API Gateway is dropped: its 30-second limit is shorter than `submit_claim`'s 60-second wait. A worker Lambda reads the DynamoDB stream. Reserved concurrency caps cost and abuse in place of a WAF. | Decided Oct 8 | H-5 |
| D20 | What happens to the local adapter and seeded tokens? | Development tools only. The demo seed (`MIDFLIGHT_SEED_DEMO=1`) and the stdio adapter (`midflight/mcp/local/`) stay for tests and laptops. A local dev login (pick a name instead of GitHub) exists only when `MIDFLIGHT_DEV_LOGIN=1` and is never deployed. The pre-push hook authenticates with a personal hook token the agent gets from a tool. | Decided Oct 8 | H-2, H-3, M-4 |

## Building the rest (October 9, 2026)

Choices made while building S-5 to M-7. Each keeps the behavior in the use cases and
picks the simplest way to get it.

| ID | Question | Decision | Status | Affects |
| --- | --- | --- | --- | --- |
| D21 | How does the reviewer call the model? | Bedrock's **Converse API through boto3**, with one forced tool (`report_findings`) whose input schema is the findings list, instead of Strands. Same structured output, no new dependency. Off unless `MIDFLIGHT_REVIEWER_MODEL` is set (deploy parameter `ReviewerModel`). | Default | S-5, D1 |
| D22 | Where does plan-change propagation run? | **Inside the approval's commit**, not a separate `plan_propagation` job: no approval can exist without its directives, and the approval's idempotency key already prevents duplicates (INV-05). Affected approved claims go back to `pending` with a review job; unaffected approvals stay valid, so those tasks can still push. | Default | S-6, UC-08 |
| D23 | How does verification read GitHub, and what do its rules check? | Plain httpx calls with the App's installation token (no githubkit). Each contract field the task provides, or the claim says it reads, must appear in the task's files at the head commit. Changed files the claim didn't list are `info`. Protected paths: `tests/contract/` and `.github/`. | Default | M-6, S-10 |
| D24 | Stale handling and the fault switch | A GitHub outage marks the project stale and the job fails, so the stream retries it (2 retries, then the dead-letter queue). The next successful GitHub read marks it fresh and reviews held claims again; there's no manual reconcile. The fault switch is the lead tool `simulate_github_outage`, replacing `/admin/fault` and `/admin/reconcile`. | Default | M-7, UC-15 |
| D25 | What each escalation resolution does | `clarify_plan` needs a newer approved plan first; the claims are reviewed again and revise against it. `request_revision` sends each involved agent a directive with the lead's decision (superseding open ones). `dismiss` reviews the claims again with the conflict kept as `info`, for revisions written before the decision. | Default | S-7, UC-13 |
| D26 | How does a developer get the pre-push hook without cloning Midflight? | `hook_setup` returns the commands: download the script from `GET /hook/pre-push`, and store the project, a personal hook token, and the task in `.git/config`. The hook asks `POST /projects/{pid}/push-check`, which answers plain text 200 or 409. | Default | M-4, UC-16, D20 |

## Architecture baseline (October 7, 2026)

Simplifications adopted in the [development plan](development-plan.md#architecture-baseline):

| Choice | Instead of | Why |
| --- | --- | --- |
| DynamoDB Stream triggers the worker Lambda directly, with an SQS dead-letter queue | A relay Lambda feeding a main SQS queue | Fewer moving parts. The stream is the durable outbox. |
| Reviewer inside the worker | AgentCore Runtime | D1 |
| ~~githubkit~~ Raw httpx calls (D23) | githubkit | Five calls didn't justify a new dependency |
| Typed contract fields (`fields: {name: type}`) | Free-text contracts | The flagship `total` vs `total_cents` conflict is caught by a rule, not a model |
| Idempotency keys on every store commit | Powertools idempotency | Duplicate webhook and stream deliveries write nothing twice, with no extra library |
| Every external service behind a port with a fake | Direct SDK calls | The whole system runs and tests on a laptop |

## Earlier decisions still in force

- **Lightweight claims (Oct 6).** Claims can start broad and be refined. Exact
  changes aren't required upfront. D5 adds the rule that approval needs interfaces
  and acceptance criteria.
- **Rules first, model second.** Deterministic checks (references, contract fields
  and types, versions) run before the AI reviewer. The model proposes findings;
  application code decides; humans own product decisions.
- **File overlap is not a conflict.** Shared files produce an `info` finding and
  never block on their own.

## Open questions

| # | Question | Default until answered | Raised in |
| --- | --- | --- | --- |
| Q1 | Can developers submit claims directly, or only their agents? | Agents only, through the connector. Any member's agent may claim a task that member owns, the lead's included (in a hosted project the lead is usually a developer too). | use-cases review question 2, D18 |
| Q2 | Can agents accept a Midflight-proposed contract without the lead? | No. Contract changes go through the lead (UC-03) or an escalation (UC-13). | use-cases review question 4 |
| Q3 | Can an agent read a contract it consumes but doesn't own (UC-07 2d)? | Read-only view of contracts it consumes; anything else about another task is 403 | use-cases review question 6 |
| Q4 | Does the submission need a publicly hosted dashboard? | No. The lead works through their AI client with the lead tools (`project_status`, plan and escalation tools, D16). A read-only status page served by the backend is stretch task X-3. | requirements §13, D16 |
| Q5 | Input size limits, retry limits, review timeout | 60 s claim wait; 2 worker retries; limits set in M-5 | requirements §13 |
| Q6 | Official submission cutoff | Finish Oct 10, submit Oct 11 | requirements §13 |
