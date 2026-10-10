# Midflight

Keeps a team's coding agents aligned with the plan, and with each other, while they work.

Agentic AI Hackathon project by **Team Yoga**: Somesh Agrawal (lead), Frederik
Jønsson, and Mithilesh Kowshik.

> **New here?** Read the [code guide](docs/code-guide.md) to see how the code fits
> together. Coding agents start with [AGENTS.md](AGENTS.md).

## What it does

On a team where everyone ships through a coding agent, agents drift: one builds an API
returning `total_cents`, another builds a page reading `total`, and nobody notices until
merge. Midflight catches that **before code is written**:

1. **Claim:** before building, an agent says what it will build and which interfaces it
   provides or uses.
2. **Check:** Midflight compares that with the team's plan and the other agents' claims,
   and answers in the same call: approved, or exactly what to fix ("Read
   `total_cents: integer`, not `total`").
3. **Propagate:** when the lead changes the plan, only the affected agents get an update.
4. **Verify:** when tests finish on a pushed commit, Midflight checks the real diff and
   posts a `midflight/verify` check on the pull request.

Conflicts between people's requirements go to the lead; Midflight never picks a winner.
A green check is evidence of alignment, not proof that the code is correct.

## How a team uses it

Midflight is one hosted service. Nobody clones this repo or runs a server.

| Who | Does |
| --- | --- |
| **Lead** | Installs the **MidFlightt** GitHub App on the repo. Adds Midflight to their AI client as a connector (one URL) and signs in with GitHub. Asks their agent to "create a Midflight project for `owner/repo`" and shares the join code it gets. Writes the plan by talking to the agent. |
| **Teammate** | Adds the same connector, signs in with GitHub, and asks their agent to "join Midflight project `MF-XXXX-XXXX`". |

In Claude Code the connector is one command:

```bash
claude mcp add --transport http midflight https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
```

In Claude or ChatGPT it's **Add custom connector** with the same URL. Developers can
also ask their agent to set up the pre-push hook (`hook_setup`), which stops a push
Midflight isn't ready for.

## Run it locally

You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env        # MIDFLIGHT_DEV_LOGIN=1: sign in with a form, no GitHub secrets
uv run midflight-server     # http://127.0.0.1:8000 (REST docs at /docs)
claude mcp add --transport http midflight http://127.0.0.1:8000/mcp
```

Data is in memory locally and resets when the server stops.

```bash
uv run pytest               # all tests (about 20 seconds)
uv run ruff check .         # lint
uv run python tests/scenario_report.py   # trace every demo scenario into docs/pages/scenarios.html
```

Deploying to AWS: [infra/README.md](infra/README.md).

## How it's built

A FastAPI server serves the MCP connector (`/mcp`), Sign in with GitHub, and a REST API.
On AWS it runs as a Lambda behind a Function URL; DynamoDB holds the data, and its stream
hands claim reviews and push verifications to a worker Lambda. Claims are checked by explicit rules first, then
an AI reviewer on Amazon Bedrock whose findings are validated before they count. One
GitHub App reads commits and publishes checks. Details:
[docs/architecture.md](docs/architecture.md) and the [code guide](docs/code-guide.md).

## Documentation

| Document | What it covers |
| --- | --- |
| [docs/code-guide.md](docs/code-guide.md) | How the code is organized, file by file, and what happens when people use it |
| [AGENTS.md](AGENTS.md) | Entry point for coding agents: rules, commands, ownership |
| [docs/development-plan.md](docs/development-plan.md) | Tasks, owners, gates, and the human steps ([visual version](docs/pages/development-plan.html)) |
| [docs/use-cases.md](docs/use-cases.md) | UC-01 to UC-16 with sequence diagrams ([visual version](docs/pages/use-cases.html)) |
| [docs/domain.md](docs/domain.md) | Exact names, states, tools, REST paths, and invariants |
| [docs/design-decisions.md](docs/design-decisions.md) | Decisions D1–D20 and open questions |
| [docs/requirements.md](docs/requirements.md) | Requirements, demo scenarios, definition of done |
| [docs/architecture.md](docs/architecture.md) | Where everything runs, with technology links |
| [docs/demo.md](docs/demo.md) | Demo scenarios and storyboard |
| [infra/README.md](infra/README.md) | Deploying to AWS |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, pull requests, reviews |

## Responsible AI

- The AI reviewer only proposes findings; application code decides, and a malformed or
  untrustworthy reply can never approve anything.
- Repository text, claims, diffs, and directives are data, never commands.
- Every decision is logged with its reason; requirement conflicts go to a human.
- Sign-in tokens and codes are stored only as hashes; secrets live in AWS Secrets Manager.
- The demo uses a synthetic project with no real user data.
