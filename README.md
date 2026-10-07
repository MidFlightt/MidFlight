# Midflight

An agent that keeps a team's coding agents aligned while they are running.

Agentic AI Hackathon project by **Team Yoga**: Somesh Agrawal (lead), Frederik
Jønsson, and Mithilesh Kowshik. Midflight is a working name.

## Who it helps

The integration lead on a 2–4 person team where every developer ships through
their own coding agent. Today the lead reads teammates' branches, compares them
to the plan, spots incompatible work, and asks people to change course. Midflight
aims to catch these problems before time and tokens are spent on discarded code.

## Core workflow

1. **Claim:** Before starting, a coding agent declares what it will build and
   which files and interfaces it expects to touch.
2. **Check:** Midflight compares the claim with the shared plan and open claims,
   and raises objections before implementation.
3. **Propagate:** A changed requirement produces specific, scoped suggestions
   for affected in-progress tasks.
4. **Verify:** On push, Midflight checks the actual diff against the claim and
   sets a GitHub status check.

Conflicts between people's requirements are escalated to humans. Midflight does
not choose a winner. A successful check supplies evidence of alignment; it does
not replace correctness tests or guarantee a branch is safe to merge.

## Proposed system architecture

The [system architecture](systemarchitecture.md) explains where each component
runs, with diagrams for the service layout, claim review, and requirement changes.
Each technology includes a short explanation and official documentation links.

- **Agents and lead:** local MCP adapters connect coding agents to the shared
  backend; a Streamlit dashboard shows the lead plans, findings, and decisions.
- **Backend:** Python, FastAPI, and Pydantic behind API Gateway and Lambda;
  DynamoDB stores versioned plans, claims, directives, jobs, and audit history.
- **Reviews:** durable jobs reach SQS workers through a job relay. Workers enforce
  explicit rules and validate findings from a Strands reviewer hosted on AgentCore
  Runtime using a Bedrock model.
- **Evidence:** a GitHub App retrieves code and publishes `midflight/verify`;
  GitHub Actions supplies trusted contract-test results for the reviewed commit.

This is a proposed design for team review. The current prototype remains a local,
in-memory declaration checker. See the [draft requirements](PROJECT_REQUIREMENTS.md)
for scope and acceptance gates, and the [open decisions](docs/design-decisions.md)
for choices to settle before implementation.

## Read before building

1. [Draft project requirements](PROJECT_REQUIREMENTS.md) — intended behavior,
   MVP scope, reliability rules, and demonstration acceptance criteria.
2. [Shared vocabulary and workflows](docs/flowchart.md) — ownership, agreements,
   checkpoints, and the checkout example.
3. [System architecture](systemarchitecture.md) — concise diagrams, technologies,
   responsibilities, and official reading links.
4. [Extended architecture and reading guide](docs/architecture-reading-guide.md)
   — tradeoffs, concurrency, evidence handling, and a suggested learning order.

The first proposed build milestone is two actual coding-agent sessions submitting
incompatible claims, receiving an explained finding, and revising a claim through
the review workflow. Plan-change propagation and GitHub verification follow.

## Failure paths and responsible AI

- If an agent says “done, per plan” but the diff breaks the agreed contract,
  trust the diff and block the alignment check.
- If GitHub errors or rate-limits, mark affected state stale and emit no
  directives until fresh data is available.
- Treat repository text, claims, diffs, and directives as untrusted data.
  Directives are suggestions, never commands to execute.
- Log every directive with its reason. Escalate requirement conflicts to humans.
- Use a synthetic demo project with no real user data.

## Start here

### Run the local prototype

Requires Python 3.10 or newer; no packages, credentials, or AWS account needed.
Run these commands from the repository root:

```sh
python3 -m midflight demo
python3 -m midflight check examples/claims.json
python3 -m unittest discover -s tests -v
```

Claims require an ID, owner, and goal. Files and shared interface names are
optional. Omitted or null lists mean unknown; an empty list explicitly declares
no items. Use consistent, exact names such as `user-api` across related claims.
The checker does not infer relationships, expand path patterns, or inspect code.

The command processes claims in order against earlier open claims. Resubmitting
the same ID and owner refines that claim in memory. Reviews are snapshots at
submission time; earlier reviews are not automatically refreshed. Nothing is
saved between runs. Owner labels are not authenticated identities.

Results are `needs_clarification` for declared overlap, `unknown` for missing
information, or `no_declared_overlap` when complete declarations have no exact
matches. None grants permission to proceed or proves semantic compatibility.
Questions are printed for human inspection, not sent to coding agents.

- [Team workflow](CONTRIBUTING.md)
- [Draft project requirements](PROJECT_REQUIREMENTS.md)
- [System architecture and technology references](systemarchitecture.md)
- [Extended architecture and reading guide](docs/architecture-reading-guide.md)
- [Claim template](docs/claim-template.md)
- [Hackathon demo and acceptance criteria](docs/demo.md)
- [Open design decisions](docs/design-decisions.md)
- [Shared vocabulary and proposed workflows (Mermaid)](docs/flowchart.md)
- [Illustrated workflow reference (PDF)](docs/midflight-workflows.pdf)

This repository includes a local claim-checking prototype and tests. Shared-plan
checking, model reasoning, propagation, diff verification, GitHub integration,
and AWS deployment remain unimplemented.

## Learning with VibeWise

Frederik is using VibeWise to learn while building. Meaningful design choices
come before implementation. Local learning notes live in `.vibe-wise/`; invoke
VibeWise to resume them. These notes are personal, so keeping that directory out
of shared commits is recommended.
