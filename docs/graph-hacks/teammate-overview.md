# MidFlight → Graph Hacks: teammate overview

Proposed scope, October 16, 2026. See the [full development plan](development-plan.md) for implementation phases, dependencies, code changes, and acceptance criteria.

## The demonstration

**Four coding agents work in parallel in a four-window split screen. We introduce a requirement change once. MidFlight uses FalkorDB to identify which agents are affected, explains why, and delivers the change to them. The unaffected agent continues working.**

We build from the **official MidFlight repository**.

## The architecture

**Four agents → existing MidFlight MCP tools → one MidFlight service → FalkorDB.**

FalkorDB becomes our only database for this hackathon version. MCP remains the interface agents use; the hackathon does not require a particular FalkorDB MCP implementation.

## What changes

- Replace DynamoDB persistence with FalkorDB.
- Replace DynamoDB Streams with a recoverable worker inside the service.
- Represent plans, tasks, contracts, claims, and decisions as connected data.
- Add multi-hop impact queries and explanations to agent check-ins.
- Preserve revision checks, safe retries, and recovery.
- Provide a separate, reproducible hackathon setup.

Reuse existing coordination rules and the review workflow. This is a focused hackathon adaptation, not a migration of the current production deployment.

## How we approach it

1. Agree on the graph model, impact behavior, shared interfaces, and four-agent scenario.
2. Prove that FalkorDB handles concurrent updates, duplicate requests, stale reviews, atomic writes, and restart recovery correctly.
3. Connect graph analysis to the existing plan-change and check-in workflow.
4. Run the real four-agent demo and independently test their integrated code.
5. Package setup instructions, graph queries, documentation, and the video.

The example chain is **Pricing → Checkout → Reporting**, with **Notifications** independent. A pricing change should trigger review along that chain and leave Notifications alone.

Agents receive updates at their normal checkpoints. A dependency means “review this impact,” not automatically “your code is wrong.”

The first milestone is one complete flow: **one change → graph traversal → relevant agents notified → explanation → verified adaptation.**

Target submission: **October 18, 2026, 9:30 AM PDT**, before the **11:29 AM PDT** deadline. Primary track: **Agent Memory and Coordination**.

[Official hackathon rules](https://www.wemakedevs.org/hackathons/falkordb/rules)
