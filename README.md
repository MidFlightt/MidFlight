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

## Planned AWS architecture

- Strands agent running on Bedrock AgentCore with a Bedrock model.
- DynamoDB for plan and claim state.
- Lambda for GitHub webhooks.
- GitHub API for diffs and commit status checks: the external tool we do not build.

These are the team's proposed services. Runtime, API contracts, authentication,
data model, and deployment details still need design decisions.

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

- [Team workflow](CONTRIBUTING.md)
- [Claim template](docs/claim-template.md)
- [Hackathon demo and acceptance criteria](docs/demo.md)
- [Open design decisions](docs/design-decisions.md)

This initial repository contains project and collaboration documentation. There
is no application, test suite, or AWS deployment yet.

## Learning with VibeWise

Frederik is using VibeWise to learn while building. Meaningful design choices
come before implementation. Local learning notes live in `.vibe-wise/`; invoke
VibeWise to resume them. These notes are personal, so keeping that directory out
of shared commits is recommended.
