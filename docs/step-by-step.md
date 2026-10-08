# Step-by-step guide

**Start here.** Find your name, then do the steps in order. Each step tells you what
to do and how to know it worked. Where a step says *"Paste into your coding agent"*,
copy the quoted prompt into Claude Code, or whatever agent you use, inside the
`midflight` folder.

Finish line: **Saturday, October 10.** Sunday, October 11 is spare time for fixes and
submission.

What we're building: [use-cases.md](use-cases.md) (diagram at the top).
Full task details for agents: [development-plan.md](development-plan.md). You don't
need to read it to follow this guide.

Your coding agent reads [AGENTS.md](../AGENTS.md) automatically when it starts in
this folder (Claude Code through `CLAUDE.md`, Codex directly). That file gives it the
rules, the commands, and who owns which folder, so the prompts below can stay short.

---

## Everyone, right now (20 minutes, on a call)

1. **Pull the latest docs.**
   ```bash
   git pull
   ```
2. **Look at the use case diagram** at the top of `docs/use-cases.md` on GitHub (5 min).
3. **Agree on two things.** Everything else uses the defaults in the plan.
   (Already decided: AgentCore is not required, so we don't use it.)
   - **Video length and submission format.** Frederik checks the rules page.
   - **AWS region.** Somesh picks one where Claude models are available on Bedrock,
     for example `us-east-1` or `us-west-2`.
4. **Post the two answers** in the team chat.

---

## Somesh: the logic

You write what Midflight decides: claims, conflicts, plan changes, verification.
You also review Mithilesh's pull requests.

### Today (Wed Oct 7)

1. **Merge the docs branch.**
   ```bash
   cd midflight
   git add -A
   git commit -m "docs: use cases, sequence diagrams, development plan"
   git push -u origin docs/use-cases
   gh pr create --fill --base main
   gh pr merge --squash
   ```
   ✅ The docs are on `main` on GitHub.
2. **Turn on Bedrock model access.** AWS console → Bedrock → *Model access* → enable
   the current Claude Sonnet and Haiku models in your region. Then check:
   ```bash
   aws bedrock list-foundation-models --by-provider anthropic --region us-east-1 --query "modelSummaries[].modelId"
   ```
   ✅ Claude model IDs are listed. Post the region in the chat.
3. **Wait for Mithilesh's scaffold PR (his step 3), review it, and merge it.**
4. **Write the data models.** Paste into your coding agent:
   > Task S-1 in docs/development-plan.md. Implement the entities and enums in
   > docs/domain.md as Pydantic v2 models in midflight/domain/models.py, using the
   > exact names there: Project, Participant, Plan, Requirement, Task, Contract
   > (fields as name→type), Claim (revision, state, provides/consumes with field
   > types, no_interfaces, files, assumptions), Finding (kind, source), Directive
   > (source, blocking, delivery state), Escalation, Verification, Job, AuditEvent.
   > Put the allowed claim transitions in midflight/domain/states.py; any other
   > transition raises. Create midflight/ports.py with Protocol classes Store,
   > Reviewer, GitHub, JobRunner, Clock. Keep it small. Add tests that each model
   > round-trips through JSON and that illegal transitions raise. Don't write any
   > services yet. Resolve the items marked (proposed) in docs/domain.md and update
   > that file.

   ✅ `uv run pytest` passes. Open a PR and ask Mithilesh to approve it. **Everyone
   depends on this, so get it merged tonight.**

### Thu Oct 8

5. **Conflict rules.** Paste into your agent:
   > Task S-2 in docs/development-plan.md. Write midflight/domain/rules.py: check claim
   > references exist in the plan, check consumed contract fields and types match the
   > plan's contract (this must catch `total` vs `total_cents`), and report shared
   > files as an `info` finding that doesn't block. Unit test every rule.

   ✅ Tests pass, including the `total` vs `total_cents` test.
6. **Claim service.** Paste:
   > Task S-3. Write midflight/adapters/memory_store.py and midflight/services/claims.py:
   > submit, revise, withdraw, and check a claim (UC-04, 05, 06 in docs/use-cases.md).
   > Saving a verdict must fail if the project's coordination revision changed since
   > the review started, and then the review reruns. Test the race in UC-05 6a.

   ✅ Two simultaneous conflicting claims can't both be approved (test passes).
7. **AI reviewer.** Paste:
   > Task S-5. Write adapters/fake_reviewer.py (returns scripted findings) and
   > adapters/bedrock_reviewer.py (Strands Agents with Bedrock, structured output as
   > our Finding model). The worker must reject replies that don't match the schema
   > or cite IDs that don't exist. Test that a malformed reply can never approve.

   ✅ Tests pass. One manual run against real Bedrock returns a finding.
8. **Evening: G1 check with everyone.** Frederik drives two agents through the
   `total` vs `total_cents` conflict. It must get caught and then approved after the
   fix.

### Fri Oct 9

9. **Plan changes and directives.** Paste:
   > Task S-6. Write domain/impact.py and services/plans.py: approve a plan version,
   > compare it with the previous one, find the provider and consumers of changed
   > contracts, set their approvals back to pending, and create one directive per
   > affected task (no duplicates, supersede older ones). UC-03 and UC-08.

   ✅ Test: adding `currency` creates directives for T1 and T2 and none for T3.
10. **Escalations.** Paste:
    > Task S-7. services/escalations.py for UC-12 and UC-13: escalate requirement
    > conflicts, let the lead resolve (clarify plan, request revision, dismiss with
    > reason), and keep the original finding.

11. **Pick the model.** Paste:
    > Task S-8. Create evals/ with about 20 labeled claim pairs (real conflicts,
    > harmless overlaps, vague ones, prompt-injection text). Run each candidate
    > Bedrock model 3 times and write a table to evals/results.md with detection rate,
    > unnecessary blocks, latency, and tokens.

    ✅ The table exists. Pick the model and tell the team.
12. **Dashboard.** Paste:
    > Task S-9. Streamlit app in midflight/dashboard/app.py that reads from our API:
    > plan version, tasks and claim states, directives with delivery state,
    > escalations with resolve buttons, stale banner, and a timeline per item.
    > Auto-refresh every 5 seconds.

    ✅ You can resolve an escalation without the terminal.
13. **Evening: G2 check.** On AWS, the currency change reaches T1 and T2, not T3.

### Sat Oct 10

14. **Verify rules.** Paste:
    > Task S-10. services/verify.py for UC-10: given a diff, file contents and test
    > results for one commit, check declared files, required contract fields present,
    > tests passed, and that contract tests and workflows weren't edited (if they
    > were, escalate). Queue a correction directive on failure.

15. **Midday: G3 check.** A wrong push gives a red `midflight/verify` check, and the
    fix gives a green one.
16. **Afternoon: review Frederik's write-up**, and be the "lead" in the final
    recording.

---

## Mithilesh: the connections

You build everything that connects Midflight to the outside world: API, agent
tools, hooks, AWS, GitHub. You also review Somesh's pull requests.

### Today (Wed Oct 7)

1. **Get the repo.**
   ```bash
   git clone https://github.com/Trexz14/midflight.git
   cd midflight
   ```
2. **Install uv.**
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - Mac/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. **Scaffold the project.** Paste into your coding agent:
   > Task M-1 in docs/development-plan.md. Set up this repo as a uv project with
   > Python 3.12: pyproject.toml with dependencies pydantic, fastapi, mangum, mcp,
   > boto3, githubkit, strands-agents, aws-lambda-powertools, streamlit, httpx,
   > pyyaml, and dev dependencies pytest, moto, respx, ruff. Create the folder layout from the
   > plan with empty __init__.py files. Add .github/workflows/ci.yml that runs
   > `uv run ruff check` and `uv run pytest` on every pull request. Add .env.example
   > with MIDFLIGHT_URL, MIDFLIGHT_TOKEN, MIDFLIGHT_PROJECT, and
   > MIDFLIGHT_BEDROCK_MODEL_ID. Keep the existing tests passing.

   ✅ `uv run pytest` passes locally. Open a PR, and CI is green on it. Somesh merges.
4. **Review Somesh's models PR** (his step 4) when it comes in. Approve it tonight
   if it looks right.

### Thu Oct 8

5. **The API.** Paste:
   > Task M-2. FastAPI app in midflight/api/ using the in-memory store and an inline
   > job runner. Bearer-token auth (store only token hashes) with lead and agent
   > roles. Implement the endpoints in the REST API table in docs/domain.md, with
   > exactly those paths, plus a `midflight admin bootstrap --seed demo` command that
   > creates the project, the lead, and plan v1. Test 401, 403, and the happy paths
   > with TestClient.

   ✅ `uv run uvicorn midflight.api.app:app` runs, and `/docs` shows the endpoints.
6. **The agent tools (MCP adapter).** Paste:
   > Task M-3. midflight/mcp/server.py using FastMCP with three tools:
   > submit_claim (posts the claim, then polls the job every 2 s for up to 60 s and
   > returns the verdict, contract, and findings), check_in, and
   > acknowledge_directive. submit_claim also accepts status withdrawn or closed.
   > Every tool reply must include pending directives. Read MIDFLIGHT_URL,
   > MIDFLIGHT_TOKEN, and MIDFLIGHT_PROJECT from the environment. Set the FastMCP server's
   > `instructions` to the "Agent instructions" text in docs/domain.md (decision D10),
   > and repeat the relevant rule in each tool's description, so a connected agent
   > lists its assumptions, plans its own checkpoints, and revises its claim when an
   > assumption changes.

7. **Connect it to Claude Code** and try it:
   ```bash
   claude mcp add midflight -e MIDFLIGHT_URL=http://127.0.0.1:8000 -e MIDFLIGHT_TOKEN=<token> -e MIDFLIGHT_PROJECT=<project-id> -- uv run --directory <path-to-midflight> python -m midflight.mcp.server
   ```
   ✅ In Claude Code, `/mcp` shows midflight with three tools. Give the agent a small
   task with no other guidance: it lists its assumptions and checkpoints before coding.
8. **Help Frederik connect his two agent sessions**, then do the G1 check together
   in the evening.

### Fri Oct 9

9. **Hooks.** Paste:
   > Task M-4. midflight/hooks/pre_push.py: a git pre-push hook that calls check_in
   > for the branch's task and refuses the push if a blocking directive is
   > unacknowledged or the claim isn't approved for the current plan (warn and allow
   > if Midflight is unreachable). Also a Claude Code hook script that runs check_in
   > and prints new directives so they're added to the agent's context. Write install
   > steps in docs/hooks.md.

   ✅ A push is blocked when a directive is waiting.
10. **Deploy to AWS.** Paste:
    > Task M-5. infra/template.yaml (AWS SAM): HTTP API → Lambda running our FastAPI
    > app via Mangum, DynamoDB tables with streams, a worker Lambda triggered by the
    > stream (filter to new job items, batch size 1, 2 retries, failures to an SQS
    > dead-letter queue), Secrets Manager for the GitHub secrets. Write
    > adapters/dynamo_store.py with conditional writes, tested with moto. Use
    > Powertools idempotency in the worker.

    Then:
    ```bash
    sam build
    sam deploy --guided
    ```
    ✅ The API URL works, and the G1 conflict scenario passes against it.
11. **Evening: G2 check with everyone.**

### Sat Oct 10

12. **Create the GitHub App.** GitHub → Settings → Developer settings → GitHub Apps →
    New:
    - Webhook URL: `<your API URL>/github/webhook`, with a random webhook secret
    - Permissions: Checks *read & write*. Contents, Pull requests, Actions, Metadata
      *read*.
    - Events: *Workflow run*
    - Install it on the demo-shop repo. Put the App ID, private key, and webhook
      secret in Secrets Manager.
13. **Verification plumbing.** Paste:
    > Task M-6. Webhook endpoint that checks the signature (401 if wrong), drops
    > duplicate delivery IDs, and saves a verify job. In the worker, use githubkit to
    > get the PR head, diff, file contents, and the test artifact for that commit,
    > call services/verify.py, re-check the head before publishing, then publish the
    > `midflight/verify` check run.

14. **Stale handling.** Paste:
    > Task M-7. When GitHub errors or rate-limits, mark the project stale, hold
    > directives, retry after the reset time, and reconcile when it recovers. Add a
    > clearly labeled fault-injection switch so we can show this in the demo.

15. **Midday: G3 check.** Red check, then green check, on a real push.

---

## Frederik: demo and story

You build the stage the demo happens on, check that each day's build actually works,
and turn it into the video and submission. You don't need to touch Midflight's code.

### Today (Wed Oct 7)

1. **Read the hackathon rules page.** Find the deadline, video length, video
   format, and what to submit. Post it in the chat.
2. **Look at the visual pages.** After `git pull`, open
   `docs/pages/use-cases.html` in your browser. Skim the diagram and the sequence
   diagrams for UC-04, UC-08, and UC-10. Those three are the heart of the demo.
3. **Write the storyboard.** Open `docs/demo.md` and rewrite the "Demo sequence"
   section using the scene list at the bottom of `docs/development-plan.md`. For
   each scene, write: what's on screen, what you say, and how many seconds it takes.
   ✅ Open a PR. Somesh reviews it.

### Thu Oct 8

4. **Create the demo shop repo.** This is the fake project our agents will work on.
   ```bash
   gh repo create midflight-demo-shop --private --clone
   cd midflight-demo-shop
   ```
   Paste into your coding agent:
   > Create a tiny shop for a demo. api/checkout.py: a FastAPI endpoint
   > GET /checkout returning JSON {"total_cents": 4999}. web/checkout.html: a page that
   > fetches it and shows "$49.99". tests/contract/test_checkout.py: a pytest test that
   > the response has total_cents as an integer. .github/workflows/contract.yml: runs
   > the contract tests on every pull request, but first restores tests/contract/
   > from main so a branch can't change its own tests, then uploads the results
   > (including the commit SHA) as an artifact named contract-results. A CODEOWNERS file making Somesh the owner of tests/ and
   > .github/. A short README.

   ✅ Push it. The Actions tab shows a green run. Change `total_cents` to `total`
   on a test branch, and the run goes red.
5. **Set up two agent sessions.** With Mithilesh's help (his step 7), open two
   Claude Code windows in the demo-shop folder, one called "T1 backend" and one
   called "T2 frontend", both with the midflight MCP connected.
6. **Evening: run G1 and record it.** In T2, ask the agent to build the checkout
   page expecting `total` in dollars. Midflight should answer with the `total_cents`
   correction in the same reply. Record the screen. ✅ You have the footage.

### Fri Oct 9

7. **Write the acceptance checklist.** Create `docs/acceptance-runs.md` with one row
   per scenario from the table in `docs/use-cases.md` → "Demo traceability": what
   you do, what should happen, what actually happened, and how long it took.
8. **Evening: run G2 and record it.** The lead changes the plan to add `currency`.
   T1 and T2 get the update, T3 gets nothing, and a push is blocked until the update
   is acknowledged. Fill in your checklist. ✅ Footage plus checklist rows.

### Sat Oct 10

9. **Midday: run G3.** Push the wrong field, show the red check, push the fix, show
   the green check.
10. **Afternoon: record the final video** following your storyboard. Then record a
    **second full take as a backup.**
11. **Edit the video**: captions, trim, title card.
12. **Write the submission.** Include what it does, the architecture picture, the
    measured results (Somesh's eval table and your checklist timings), and screenshots
    added to the README. Somesh reviews it.

### Sun Oct 11

13. Fix anything broken, re-record if needed, **submit.**

---

## If we're running late

Drop things in this order:
1. The Claude Code hook (keep the pre-push hook).
2. The AI reviewer in verification.
3. Dashboard polish.
4. Showing a live GitHub outage (use the fault switch instead).

**Never drop:** conflict caught before coding, the red check on a false "done",
escalating conflicts to the lead, and holding updates while state is stale.
