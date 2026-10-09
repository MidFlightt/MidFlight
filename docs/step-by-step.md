# Step-by-step guide

**Start here.** Find your name and do your steps in order. Each step says how to know it
worked. Where a step says *"Paste into your coding agent"*, copy the quoted prompt into
Claude Code (or your agent) inside the `midflight` folder; your agent reads
[AGENTS.md](../AGENTS.md) automatically.

Finish line: **Saturday, October 10.** Sunday, October 11 is spare time for fixes and
submission.

**Where we are (October 8):** the hosted connector is built and tested on a laptop:
projects with join codes, Sign in with GitHub, the connector's tools, the claim checks,
and the AWS code. It isn't deployed yet. How the code fits together:
[code-guide.md](code-guide.md).

---

## Everyone: get the code and try it (15 minutes)

1. **Get the repo**, or update your copy:
   ```bash
   git clone https://github.com/MidFlightt/MidFlight.git midflight
   cd midflight
   uv sync
   ```
   (Already cloned the old `Trexz14/midflight`? Run
   `git remote set-url origin https://github.com/MidFlightt/MidFlight.git`, then
   `git pull`.)
2. **Run it:**
   ```bash
   cp .env.example .env
   uv run midflight-server
   ```
   ✅ <http://127.0.0.1:8000/docs> opens.
3. **Connect Claude Code** in another terminal and sign in through the dev form that
   opens in your browser:
   ```bash
   claude mcp add --transport http midflight http://127.0.0.1:8000/mcp
   ```
   ✅ In Claude Code, ask "create a Midflight project for acme/shop". It answers with a
   join code.

---

## Somesh

1. **GitHub App settings** (5 minutes): make it public, generate a client secret, add
   the callback URL `http://127.0.0.1:8000/oauth/github/callback`
   ([details](development-plan.md#human-steps)). Put the client secret, the `.pem` path,
   and the webhook secret in your `.env`, and remove `MIDFLIGHT_DEV_LOGIN=1`.
   ✅ `uv run midflight-server`, then connecting Claude Code sends you to GitHub to sign
   in.
2. **AWS** once the account is verified: root MFA, budget, deploy identity, AWS CLI and
   SAM CLI, Bedrock playground check ([details](development-plan.md#human-steps)).
3. **Deploy:** follow [infra/README.md](../infra/README.md).
   ✅ `curl <FunctionUrl>healthz` prints `{"status":"ok"}`, and Claude Code connects to
   the Function URL.
4. **Next code tasks** (paste into your agent one at a time):
   > Task S-6 in docs/development-plan.md: plan-change directives. When the lead
   > approves a new plan version, find the tasks it affects, send each one directive
   > (D13), reset their approvals, and supersede older directives.

   > Task S-5: the Bedrock reviewer behind the Reviewer port, with the model chosen in D7.

---

## Mithilesh

1. **Read** [code-guide.md](code-guide.md), then run the tests: `uv run pytest`.
2. **CI** (M-1). Paste into your agent:
   > Task M-1: add .github/workflows/ci.yml that runs `uv sync`, `uv run ruff check .`,
   > and `uv run pytest` on every pull request and on pushes to main.

   ✅ A pull request shows a green check.
3. **GitHub verification** (M-6), once the deploy exists. Paste:
   > Task M-6 in docs/development-plan.md: the GitHub webhook (signature check,
   > delivery dedupe, workflow_run trigger, routed by installation id to its project),
   > fetching the head, diff, contents, and test artifact, and publishing
   > midflight/verify.

---

## Frederik

1. **Try the connector** (the "Everyone" steps above), and tell Somesh anything that
   feels confusing. You're the first user.
2. **The demo-shop repo** (F-2). In `midflight-demo-shop`, paste into your agent:
   > Create a tiny shop for a demo. api/checkout.py: a FastAPI endpoint GET /checkout
   > returning JSON {"total_cents": 4999}. web/checkout.html: a page that shows "$49.99".
   > tests/contract/test_checkout.py: a pytest test that the response has total_cents as
   > an integer. .github/workflows/contract.yml: runs the contract tests on every pull
   > request, first restoring tests/contract/ from main so a branch can't change its own
   > tests, then uploads the results (with the commit SHA) as an artifact named
   > contract-results. A CODEOWNERS file making Somesh the owner of tests/ and .github/.

   ✅ The Actions tab shows a green run; changing `total_cents` to `total` turns it red.
3. **The storyboard** in [demo.md](demo.md), using the scene list at the end of the
   [development plan](development-plan.md#demo-storyboard). The setup scene is now 20
   seconds: install the App, paste the connector URL, sign in, share the join code.

---

## If we're running late

Drop things in this order: the pre-push hook, the AI reviewer inside verification, a
live GitHub outage (use the fault switch), ChatGPT in the demo.

**Never drop:** the connector with sign-in and join code, the conflict caught before
coding, the red check on a false "done", escalating conflicts to the lead, and holding
updates while data is stale.
