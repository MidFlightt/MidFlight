# Code guide

How the Midflight code is organized and what happens, file by file, when people use it.
Read this before opening the code. For *why* things are this way, see
[design-decisions.md](design-decisions.md); for exact names and rules,
[domain.md](domain.md).

## The big picture

```mermaid
flowchart LR
    Client["AI client<br/>(Claude Code, Claude, ChatGPT)"] -- "/mcp + sign-in" --> Main
    Scripts["Scripts, hooks"] -- "REST + token" --> Main
    subgraph Server["The Midflight server (midflight/main.py)"]
        Main["web app"] --> MCP["mcp/hosted.py<br/>the connector's tools"]
        Main --> OAuth["api/oauth.py<br/>Sign in with GitHub"]
        Main --> REST["api/app.py<br/>REST routes"]
        MCP --> Services
        REST --> Services
        OAuth --> Services
        Services["services/<br/>what Midflight does"] --> Domain["domain/<br/>rules and decisions (pure)"]
        Services --> Ports["ports.py<br/>interfaces to the outside"]
    end
    Ports --> Adapters["adapters/<br/>memory or DynamoDB store, GitHub, clock"]
```

Three layers, from the inside out:

1. **`domain/`** is the core: the data (models), what's allowed (states), the checks
   (rules), and the verdict (decide). No I/O at all, so it's easy to test and reason
   about.
2. **`services/`** are the things Midflight *does*: submit a claim, approve a plan,
   create a project, check in. They use the domain and talk to the outside world only
   through `ports.py`.
3. **The edges** turn requests into service calls: the hosted MCP connector
   (`mcp/hosted.py`), sign-in (`api/oauth.py`), the REST API (`api/app.py`), and the
   AWS worker (`aws/worker.py`). `main.py` wires them together.

`adapters/` are the real and fake versions of each port: in-memory or DynamoDB store,
real or fake GitHub, a real or frozen clock. Tests use the fakes; nothing in a test
touches AWS or GitHub.

## Folder by folder

### `midflight/domain/`: the rules (no I/O)

| File | What it holds |
| --- | --- |
| `models.py` | Every entity as a Pydantic model: `User`, `Project`, `Participant`, `Plan`, `Claim`, `Finding`, `Directive`, `Verification`, `Job`, ... Models reject unknown fields, can't be changed in place, and refuse data that breaks a rule they can check themselves (for example, a verification can't be `verified` with missing evidence). |
| `states.py` | Which state changes are allowed (`pending → approved`, ...). Anything else raises. |
| `rules.py` | The deterministic claim checks: unknown ids, old plan version, wrong contract field or type (`total` vs `total_cents`), scope, duplicate provider, shared files. |
| `decide.py` | Findings in, verdict out: `approved`, `needs_revision`, `draft`, `human_review_required`, or held `pending`. |
| `impact.py` | What changed between two plan versions, and which tasks that touches. |
| `verify.py` | The checks on a pushed commit: missing evidence, failed contract tests, a contract field missing from the task's files, edits to protected test or CI files, undeclared files. |

### `midflight/services/`: what Midflight does

| File | Does |
| --- | --- |
| `projects.py` | Sign in (a GitHub account becomes a `User`), create a project (checks the App is installed and you're a repo admin), join with a code, rotate the code, remove a member, assign a task. |
| `claims.py` | Submit, revise, withdraw, close a claim; run the review job (rules, then the AI reviewer, then decide, saved only if nothing changed meanwhile). |
| `review.py` | Checks the AI reviewer's reply before anything uses it; a bad reply is thrown away. |
| `plans.py` | Propose and approve plan versions (lead only). Approving a change also sends one directive to each affected task and sends their approvals back for review, in the same commit. |
| `escalations.py` | The lead's decision on a conflict between people's requirements: clarify the plan, request revisions, or dismiss. |
| `verification.py` | The verification job: read the push from GitHub, run the checks, publish `midflight/verify`, and queue a correction directive or an escalation. |
| `sync.py` | Stale and fresh GitHub data, and the demo fault switch. |
| `check_in.py` | What an agent gets at a checkpoint: its task, requirements, contracts, claim verdict, directives, and whether it may push. |
| `directives.py` | An agent's answer to a directive. |
| `participants.py` | Tokens for scripts and the pre-push hook (stored as hashes); `issue_hook_token` for `hook_setup`. |
| `audit.py`, `errors.py` | Building audit events; the errors services raise (each maps to an HTTP status). |

### The edges

| File | Does |
| --- | --- |
| `main.py` | Builds the whole server: store, services, sign-in, the connector, the REST API. `uv run midflight-server` starts it. |
| `config.py` | Settings from environment variables or `.env`. |
| `wiring.py` | Which real adapter each part uses (DynamoDB or memory, Bedrock or no reviewer, the GitHub App), shared by the server and the worker. |
| `mcp/hosted.py` | The connector's 16 tools. Each one finds who's calling (from their sign-in), finds their project, calls a service, and replies in plain text. |
| `mcp/instructions.py` | The rules every connected agent is told (claim first, check in at checkpoints, ...), and the tool descriptions. |
| `mcp/replies.py` | Turns results into the text an agent reads, with directives fenced off as data. |
| `api/oauth.py` | Sign in with GitHub: the OAuth flow AI clients expect, with GitHub doing the login. |
| `api/app.py`, `api/views.py` | The REST API (for scripts and hooks) and the JSON shapes it returns. |
| `api/webhook.py` | `POST /github/webhook`: checks GitHub's signature and queues a verification when the contract tests finish. |
| `hooks/pre_push.py` | The git pre-push hook script Midflight hands out at `/hook/pre-push`. |
| `aws/worker.py` | The AWS worker Lambda: runs claim reviews and verifications from the DynamoDB stream. |
| `mcp/local/` | A development tool: the agent tools over stdio, for working on Midflight locally. Customers never use it. |
| `demo.py` | The synthetic demo project (T1, T2, T3) for tests and local runs. |

### `midflight/adapters/`: the outside world

| File | Is |
| --- | --- |
| `memory_store.py` | The store in memory: for tests and a laptop. |
| `dynamo_store.py` | The same store on DynamoDB: for AWS. The same tests run against both. |
| `github.py` | Real GitHub: sign-in, "is the App installed / is this person an admin?", and everything verification reads and publishes. |
| `fake_github.py` | Fake GitHub for tests and the dev login. |
| `bedrock.py` | The AI reviewer on Amazon Bedrock. It proposes findings only. |
| `runners.py` | How background jobs run: now (`InlineRunner`), when a test says (`DeferredRunner`), or by the AWS worker (`StreamRunner`). |
| `clock.py` | The real clock, and a frozen one for tests. |

### Elsewhere

| Path | Is |
| --- | --- |
| `infra/` | The AWS deploy: template, packaging, secrets ([infra/README.md](../infra/README.md)). |
| `tests/unit/` | One test file per part (below). |
| `tests/integration/` | The real server over HTTP, signing in like an AI client. |
| `tests/scenarios/` | Demo scenarios as YAML, played against the real services. |
| `docs/` | Specs, decisions, plan, and this guide. `docs/archive/` is old background. |

## Journey 1: someone adds the connector and signs in

1. They add `https://<server>/mcp` to their AI client.
2. The client calls `/mcp` without a token. The MCP SDK's auth layer (configured in
   `main.py`) answers **401**, pointing at Midflight's sign-in discovery document.
3. The client registers itself (`/register`) and opens `/authorize` in the browser.
   `MidflightOAuth.authorize` in `api/oauth.py` remembers the request and sends the
   browser to GitHub (`GitHubAppSignIn.authorize_url` in `adapters/github.py`).
4. GitHub sends the browser back to `/oauth/github/callback` with a code.
   `github_callback` trades it for the GitHub account, then
   `MidflightOAuth.finish_sign_in` calls `ProjectService.sign_in` (creating the `User`
   on first sign-in) and sends the browser back to the client with Midflight's own
   one-time code.
5. The client trades that code at `/token` for an access token (1 hour) and a refresh
   token (30 days). Codes and tokens are stored only as hashes.
6. Every `/mcp` call now carries the token. The SDK checks it with
   `MidflightOAuth.load_access_token`; the token's `subject` is the user id, which the
   tools read in `mcp/hosted.py`.

Locally with `MIDFLIGHT_DEV_LOGIN=1`, step 3 shows a form where you type a GitHub login
instead of going to GitHub. That form doesn't exist on a real server.

## Journey 2: a team forms

1. The lead's agent calls `create_project(repository="acme/shop")`
   (`mcp/hosted.py`), which calls `ProjectService.create_project`.
2. It checks the App is installed on the repo and the lead is an admin there
   (`RepoAccess`, real version in `adapters/github.py`), that the repo has no project
   yet, then saves the project and the lead's membership in one commit, with an audit
   event. The reply shows the join code.
3. A teammate's agent calls `join_project(join_code=...)`, which adds them as a member
   with the `agent` role.
4. The lead's agent calls `propose_plan` (tasks name owners by GitHub login) and
   `approve_plan`. From then on, `check_in` shows each member their task.

## Journey 3: an agent submits a claim

1. The agent calls `submit_claim` (`mcp/hosted.py`) with what it will build.
2. `ClaimService.submit` (`services/claims.py`) checks the caller owns the task,
   refuses unknown ids or an old plan version with nothing saved, then saves the claim
   **and its review job in one commit**.
3. The job runs:
   - **on a laptop**, immediately (`InlineRunner`);
   - **on AWS**, the DynamoDB stream hands the new job to the worker Lambda
     (`aws/worker.py`).
4. `ClaimService.run_review` runs the rules (`domain/rules.py`), then the AI reviewer
   if no rule blocked (its reply checked by `services/review.py`), then
   `domain/decide.py`. It saves the verdict **only if the project hasn't changed since
   it read it**; otherwise it reruns. That's what stops two conflicting claims from both
   being approved.
5. Back in `submit_claim`, the tool waits for the job (up to 55 seconds), then replies
   with the verdict, the contracts to build against, any fixes, and open directives.

## Journey 4: the lead changes the plan

1. The lead proposes plan v2, which adds `currency` to `checkout-response`, and approves
   it (`services/plans.py`).
2. In the same commit: T1 (provides the contract) and T2 (reads it) each get one
   directive saying what changed; T3 (no link) gets nothing; T1's and T2's approved
   claims go back to `pending` and are reviewed again, so they're asked to revise.
3. Each directive reaches its agent in the next reply it gets from Midflight
   (`check_in`, `submit_claim`, or the pre-push hook). Midflight can't interrupt a
   running agent. A push is blocked until the agent answers it.

## Journey 5: an agent pushes

1. GitHub runs the repo's contract tests (`contract.yml`). When the run finishes, GitHub
   calls `/github/webhook` (`api/webhook.py`), which checks the signature and saves a
   verification job.
2. `VerificationService.run` (`services/verification.py`) reads the pull request, the
   diff, the task's files, and the test results for that exact commit, then runs the
   checks in `domain/verify.py`.
3. It reads the head and the plan again; if either moved, the result is dropped.
4. It publishes `midflight/verify` on the commit: success, failure, or action required.
   A failure also queues a correction directive for the agent ("use `total_cents`").
5. If GitHub is down, the project goes stale (`services/sync.py`): directives are held
   and nothing is approved until GitHub answers again.

To see journey 3 step by step for every demo scenario, open
[docs/pages/scenarios.html](pages/scenarios.html) (regenerate with
`uv run python tests/scenario_report.py`).

## Where the safety rules live

| Rule | Enforced in |
| --- | --- |
| The AI never approves on its own (INV-01) | `services/review.py` throws away bad replies; `domain/decide.py` decides |
| No double approval in a race (INV-02) | `Store.commit` with `expected_coord_rev` (both stores), `run_review` reruns |
| Missing evidence is never `verified` (INV-03) | `Verification` model in `domain/models.py`, `domain/verify.py` |
| One directive per plan version and task (INV-05) | `services/plans.py`, in the approval's commit |
| Repository text is data, never instructions (INV-07) | `adapters/bedrock.py` puts it inside `<data>`; `mcp/replies.py` fences directives |
| Nothing approved and directives held while stale (INV-09) | `domain/decide.py`, `services/check_in.py`, `services/sync.py` |
| Midflight never picks between people (INV-11) | `services/claims.py` opens an escalation; `services/escalations.py` records the lead's decision |
| Edits to contract tests or CI are escalated (INV-15) | `domain/verify.py` |
| Only the lead approves plans and manages the team (INV-08) | `services/plans.py`, `services/projects.py`, `mcp/hosted.py` |
| Tokens and codes stored as hashes (INV-12) | `api/oauth.py`, `services/participants.py` |
| One audit event per change, no duplicates on retry (INV-13) | every service's commit, with an idempotency key |
| Shared files never block (INV-14) | `Finding` model and `domain/rules.py` |
| People only see their own projects | `ProjectService.membership` |

## The tests

`uv run pytest` runs everything (about 360 tests, 20 seconds). Each file proves one part:

| File | Proves |
| --- | --- |
| `unit/test_models.py`, `test_states.py` | The models refuse bad data; only allowed state changes happen |
| `unit/test_rules.py` | Each claim check, including `total` vs `total_cents` |
| `unit/test_claim_service.py` | Submitting, revising, the race, bad AI replies, stale data |
| `unit/test_store.py` | Both stores behave the same (memory and DynamoDB) |
| `unit/test_projects.py` | Creating, joining, codes, removing, assigning, repo checks |
| `unit/test_hosted_mcp.py` | The connector's tools, as two people working together |
| `unit/test_github.py` | Real GitHub code against a fake GitHub; the GitHub sign-in pages |
| `unit/test_aws.py` | The worker reviews a claim saved by the web side; secrets from Secrets Manager |
| `unit/test_api.py` | The REST API, its 401 and 403 cases |
| `unit/test_mcp_local_adapter.py` | The local stdio adapter (development tool) |
| `unit/test_plan_change.py` | A plan change reaches T1 and T2, not T3; supersede; held while stale |
| `unit/test_escalations.py` | The tax conflict escalates; each resolution |
| `unit/test_bedrock.py` | The Bedrock reviewer against a fake Bedrock |
| `unit/test_verification.py` | Pushes verified, failed, incomplete, escalated; the webhook; outages and the fault switch |
| `unit/test_hook.py` | The pre-push hook: the real script, its token, the push check |
| `integration/test_hosted_server_http.py` | The real server over HTTP: sign in like an AI client, then use the tools |
| `test_scenarios.py` | Every demo scenario in `tests/scenarios/` |

## Try it yourself

```bash
uv sync
cp .env.example .env             # MIDFLIGHT_DEV_LOGIN=1 is already on
uv run midflight-server          # http://127.0.0.1:8000, REST docs at /docs
```

In another terminal, connect Claude Code and sign in through the dev form:

```bash
claude mcp add --transport http midflight http://127.0.0.1:8000/mcp
```

Then ask Claude: "create a Midflight project for acme/shop". To act as a teammate on
the same machine, add the connector a second time under another name (the name keeps
its own sign-in), sign in with a different login, and ask "join Midflight project
<code>":

```bash
claude mcp add --transport http midflight-teammate http://127.0.0.1:8000/mcp
```
