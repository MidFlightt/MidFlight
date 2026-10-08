# Midflight

An agent that keeps a team's coding agents aligned while they are running.

Agentic AI Hackathon project by **Team Yoga**: Somesh Agrawal (lead), Frederik
Jønsson, and Mithilesh Kowshik. Midflight is a working name.

> **Building or using a coding agent on this repo? Start with [AGENTS.md](AGENTS.md).**
> It links every spec, the rules, the commands, and who owns what.
> New teammate? Start with the [step-by-step guide](docs/step-by-step.md).

## Who it helps

The integration lead on a 2–4 person team where every developer ships through
their own coding agent. Today the lead reads teammates' branches, compares them
to the plan, spots incompatible work, and asks people to change course. Midflight
catches these problems before time and tokens are spent on discarded code.

## How it works

1. **Claim:** before starting, a coding agent declares what it will build and which
   files and interfaces it expects to touch.
2. **Check:** Midflight compares the claim with the shared plan and other open
   claims, and answers in the same call: approved, or what to fix.
3. **Propagate:** when the lead changes a requirement, only the affected tasks get
   a scoped directive, delivered at their next checkpoint.
4. **Verify:** when contract tests finish on a pushed commit, Midflight checks the
   actual diff against the claim and publishes the `midflight/verify` GitHub check.

Conflicts between people's requirements are escalated to the lead. Midflight does
not choose a winner. A passing check is evidence of alignment, not proof that the
code is correct.

**Stack:** coding agents connect through a local MCP adapter and git hooks to a
FastAPI backend on AWS Lambda. DynamoDB holds versioned state, and its stream
triggers a worker that runs explicit rules, then a Strands reviewer on Amazon
Bedrock. A GitHub App reads commits and publishes checks. The lead uses a Streamlit
dashboard. Details: [docs/architecture.md](docs/architecture.md).

## Documentation

| Document | What it covers |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Entry point: reading order, rules, commands, ownership |
| [docs/step-by-step.md](docs/step-by-step.md) | Each person's steps, in order |
| [docs/development-plan.md](docs/development-plan.md) | Tasks, owners, dependencies, daily gates ([visual version](docs/pages/development-plan.html)) |
| [docs/use-cases.md](docs/use-cases.md) | UC-01 to UC-16 with sequence diagrams ([visual version](docs/pages/use-cases.html)) |
| [docs/domain.md](docs/domain.md) | Exact names, states, tools, REST paths, and invariants |
| [docs/requirements.md](docs/requirements.md) | FR/NFR requirements, demo scenarios, definition of done |
| [docs/architecture.md](docs/architecture.md) | Where everything runs, with technology links |
| [docs/design-decisions.md](docs/design-decisions.md) | Decisions D1–D15 and open questions |
| [docs/demo.md](docs/demo.md) | Demo scenarios and storyboard |
| [docs/claim-template.md](docs/claim-template.md) | How to write a claim by hand |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, pull requests, reviews |

The HTML pages are standalone. Open them in a browser after cloning.

## Run the current prototype

The repository holds a small local claim checker while the real system is built.
It needs Python 3.10 or newer and nothing else: no packages, credentials, or AWS.

```sh
python -m midflight demo
python -m midflight check examples/claims.json
python -m unittest discover -s tests -v
```

The prototype compares exact declared files and interface names between claims.
It returns `needs_clarification` for declared overlap, `unknown` for missing
information, and `no_declared_overlap` otherwise. It does not inspect code, judge
semantic compatibility, or save anything between runs. It will be replaced once
task S-3 lands. Shared-plan checks, model reasoning, propagation, GitHub
verification, and AWS deployment are not implemented yet.

## Failure paths and responsible AI

- If an agent says "done, per plan" but the diff breaks the agreed contract, trust
  the diff and fail the check.
- If GitHub errors or rate-limits, mark state stale and hold directives until fresh
  data is available.
- Treat repository text, claims, diffs, and directives as untrusted data. Directives
  are suggestions, never commands to execute.
- Log every directive with its reason. Escalate requirement conflicts to humans.
- Use a synthetic demo project with no real user data.

## Learning with VibeWise

Frederik is using VibeWise to learn while building. Local learning notes live in
`.vibe-wise/`, which is git-ignored because the notes are personal.
