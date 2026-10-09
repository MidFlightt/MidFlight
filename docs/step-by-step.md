# Step-by-step guide

**Start here.** Find your name and do your steps in order. Each step says how to know it
worked.

Finish line: **Saturday, October 10.** Sunday, October 11 is spare time for fixes and
submission.

**Where we are (October 9):** every code task is built, tested (about 360 tests), and
ready to deploy: the connector with Sign in with GitHub and join codes, the claim
checks, plan-change directives, escalations to the lead, GitHub verification with the
`midflight/verify` check, stale handling with a demo fault switch, the pre-push hook,
and CI. What's left is account settings, the demo-shop repo, and the video. How the
code fits together: [code-guide.md](code-guide.md).

The live connector URL, for everyone:

```
https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
```

---

## Everyone: connect to Midflight (5 minutes, no cloning)

1. **Add the connector** to Claude Code:
   ```bash
   claude mcp add --transport http --scope user midflight https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
   ```
   In Claude Code, run `/mcp`, choose **midflight**, and sign in with GitHub in the
   browser that opens.
2. **Join the project:** ask your agent "join Midflight project MF-XXXX-XXXX", with the
   join code Somesh sends you in chat (it isn't written here, because anyone with the
   code can join).
   ✅ "my Midflight projects" lists the demo-shop project.
3. **Install the pre-push hook** in your clone of `midflight-demo-shop`: ask your agent
   "set up the Midflight pre-push hook for my task" and run the commands it gives you.
   ✅ A push before your claim is approved prints "midflight: push blocked".

Working on Midflight's own code? `git clone https://github.com/MidFlightt/MidFlight.git`,
`uv sync`, `cp .env.example .env`, `uv run midflight-server`, and connect Claude Code to
`http://127.0.0.1:8000/mcp` instead.

---

## Somesh

1. ~~GitHub App sign-in settings, AWS account, deploy~~ Done.
2. **GitHub App webhook and permissions** (5 minutes), in the App's settings:
   - Webhook: **Active**, URL
     `https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/github/webhook`,
     secret = the `MIDFLIGHT_GITHUB_WEBHOOK_SECRET` in your `.env`.
   - Permissions: **Checks: read and write**; **Actions, Contents, Pull requests,
     Metadata: read**. Events: **Workflow run**.
   - If GitHub asks, accept the new permissions on the installation.

   ✅ The App's **Advanced → Recent Deliveries** shows a green `ping`.
3. **Bedrock access** (5 minutes, then wait). Every Bedrock call from this account
   answers "Operation not allowed", even for Amazon's own models, so AWS hasn't
   enabled Bedrock for the new account. Open a support case (free): Support Center →
   Create case → **Account and billing** → "Please enable Amazon Bedrock model
   invocation for account 376564125271 in us-east-1."
   ✅ A message in the Bedrock playground gets an answer. Then the AI reviewer is one
   redeploy away ([infra/README.md](../infra/README.md#turning-on-the-ai-reviewer)).
4. **Lambda concurrency** (2 minutes): Service Quotas → AWS Lambda → Concurrent
   executions → request 1,000 (new accounts allow 10).
5. **The eval** (S-8), once Bedrock works. Paste into your agent:
   > Task S-8 in docs/development-plan.md: an eval harness with about 20 labeled claim
   > pairs, measuring recall, unnecessary blocks, latency, and tokens per model.

---

## Mithilesh

1. **Read** [code-guide.md](code-guide.md), then run the tests: `uv run pytest`.
2. **Review** the verification code you own: `midflight/api/webhook.py`,
   `midflight/services/verification.py`, `midflight/services/sync.py`,
   `midflight/hooks/pre_push.py`, and `.github/workflows/ci.yml`.
3. **Live check** once Frederik's `contract.yml` is on `main`: open a pull request in
   `midflight-demo-shop` with an approved claim's branch.
   ✅ The pull request shows `midflight/verify`. Changing `total_cents` to `total` turns
   it red, with the reason in the check's summary.

---

## Frederik

1. **Connect** (the "Everyone" steps above), and tell Somesh anything that feels
   confusing. You're the first user.
2. ~~**The demo-shop repo** (F-2)~~ Done October 8 (`MidFlightt/MidFlight-demo-shop`):
   the checkout API and page, the trusted contract runner, and `contract.yml`, which
   restores `tests/contract/` and `contracts/` from main and uploads `contract-results`.
   Midflight reads that artifact as it is. One fix left: `.mcp.json.example` still points
   at the old local adapter; replace it with the hosted connector:
   ```json
   {"mcpServers": {"midflight": {"type": "http", "url": "https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp"}}}
   ```
   Saved as `.mcp.json`, Claude Code offers the connector to anyone who opens the repo.
3. **The storyboard** in [demo.md](demo.md), using the scene list at the end of the
   [development plan](development-plan.md#demo-storyboard), and the animated version from
   [video-prompt.md](video-prompt.md). For the outage scene, the
   lead asks their agent to "simulate a GitHub outage" (the labeled fault switch) and
   later to turn it off.

---

## If we're running late

Drop things in this order: the pre-push hook, the AI reviewer inside verification, a
live GitHub outage (use the fault switch), ChatGPT in the demo.

**Never drop:** the connector with sign-in and join code, the conflict caught before
coding, the red check on a false "done", escalating conflicts to the lead, and holding
updates while data is stale.
