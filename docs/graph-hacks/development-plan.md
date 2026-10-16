# MidFlight for Graph Hacks — full development plan

Status: proposed implementation plan, recorded October 16, 2026. Implementation has not started in this branch.

This is the Graph Hacks starting point for the official [MidFlight repository](https://github.com/MidFlightt/MidFlight), based on inspected commit `2b6a31bf62e09c127d33b325131b4dbcb912be43`. Its existing test suite and lint checks passed during inspection; that is baseline evidence, not validation of this proposed migration.

For the short version, see the [teammate overview](teammate-overview.md). This plan supersedes the earlier DynamoDB-plus-FalkorDB proposal for this hackathon. Existing AWS documentation describes the current implementation, not this target architecture. No team assignments are prescribed here.

## 1. Objective

Adapt official MidFlight into a graph-backed coordination system for coding agents.

Four agents work simultaneously on different parts of one application. A developer introduces a requirement change once. MidFlight follows dependencies in FalkorDB, determines which tasks require review, and delivers relevant context to those agents. Unaffected agents continue working.

Every notification should explain the relationship behind it:

> Your reporting task consumes orders produced by Checkout, which depends on the changed pricing contract.

The graph identifies potential impact. Existing rules and review determine whether implementation changes are required.

## 2. Architecture

**Four coding agents → MidFlight MCP service → FalkorDB**

The MidFlight service also runs the existing rules and reviewer, plus a background review worker.

| Component | Responsibility |
| --- | --- |
| Coding agents | Implement tasks, declare claims, check for updates, and respond to changes |
| MCP interface | Expose MidFlight's project, plan, claim, and check-in tools |
| MidFlight service | Enforce permissions, manage revisions, coordinate reviews, and deliver updates |
| FalkorDB | Persist shared state and execute dependency and evidence queries |
| Reviewer | Evaluate compatibility using the plan, claims, and graph-derived context |

Use one service process for the hackathon deployment. All agents connect to it; they do not write directly to the database.

Short state changes may be serialized while agents and model reviews continue concurrently. Reviews must recheck the project revision before saving their results.

FalkorDB is the only database for this version. There is no DynamoDB-to-FalkorDB synchronization layer.

## 3. Scope

### Required

- Four separately identified coding agents working in parallel.
- Persistent projects, plans, tasks, contracts, claims, decisions, directives, and jobs.
- Graph-based direct and downstream impact analysis.
- Relevant updates delivered through existing agent checkpoints.
- Evidence paths explaining why each task is affected.
- Recovery after service restart or a fresh agent session.
- Safe retries and protection against outdated review results.
- An independent test of the agents' integrated application.
- Reproducible setup and a recorded demonstration.

### Deferred

- Migration of existing production data or replacement of the live deployment.
- Multiple service replicas or distributed workers.
- Automatic interruption or wake-up of idle agents.
- A custom dashboard.
- Document ingestion, embeddings, or a GraphRAG pipeline.
- Changes to the underlying AI model solely for the hackathon.

Existing GitHub verification functionality should remain compatible. Making the demo depend on a complete production GitHub deployment is optional. Any simplified demo sign-in must remain confined to a controlled local environment; it must not become a public authentication bypass.

## 4. What we reuse and replace

Reuse official MidFlight's domain models, deterministic checks, review validation, plan and claim workflow, MCP tools, and tests wherever their behavior remains applicable.

Replace:

1. Runtime persistence with a FalkorDB-backed store.
2. DynamoDB Streams with a recoverable worker inside the service.
3. Direct-only impact analysis with graph traversal across task and contract dependencies.
4. Agent context responses with versions that include dependency paths and change explanations.
5. Deployment with a separate service-and-FalkorDB setup.

Preserve the official system's current agreement semantics. Do not introduce the local prototype's separate `agree` workflow.

## 5. Graph model

Start with existing structured information rather than extracting a new model from arbitrary conversation text.

| Entity | Relationships |
| --- | --- |
| Project | Contains plan versions and participants |
| Plan version | Contains requirements, tasks, and contracts |
| Task | Implements requirements; provides and consumes contracts |
| Claim revision | Belongs to a task; declares interfaces and assumptions |
| Assumption | Originates in a claim; may reference another task |
| Decision | References supporting claims and evidence |
| Directive | Targets a task; records the triggering change |
| Review job | References the exact claim revision being reviewed |

Keep previous plan and claim revisions. Queries must explicitly select applicable versions.

Represent task-ID, title, or filename matches as inferred assumption references. They must not silently become confirmed contractual dependencies.

Store operational records required by the existing service—request identifiers, audit events, and authentication records—in the same database, outside general agent-context queries. Preserve hashed-token behavior; never include credentials in demo exports or graph visualizations. Use synthetic project data.

## 6. Required graph queries

Implement parameterized queries for:

1. Directly affected tasks for a plan change.
2. Downstream consumers reached through task/contract relationships.
3. Evidence paths from each changed item to an affected task.
4. Current task context: contracts, claims, decisions, and outstanding directives.
5. Assumptions referring to a task, with their source claim.
6. Pending review work for restart recovery.

For impact analysis, consider old and new plan relationships separately and combine the results. This preserves removed dependencies without creating paths assembled from incompatible plan versions.

Deduplicate affected tasks, handle cycles, and impose explicit limits. A truncated query must report incomplete analysis.

Keep existing deterministic conflict checks. Initially retain existing peer-claim context for semantic review and add graph evidence; reducing that context is a later optimization.

## 7. Persistence and correctness

The current store provides atomic commits, idempotency, and project revision checks. The FalkorDB adapter must preserve those guarantees.

A coordination commit must save related records together:

- Claim plus review job.
- Approved plan plus directives and re-review jobs.
- Review result plus audit evidence.

Use database-supported atomic operations for these commits. A Python lock alone does not protect against a crash halfway through several database writes. Prove the chosen mechanism on the pinned FalkorDB version before broad integration.

Keep MidFlight's own `coord_rev` property. FalkorDB's query `version` option relates to schema caching and is not a substitute for application revision control.

First prove:

- Concurrent updates cannot silently overwrite one another.
- Repeating the same request produces one outcome.
- A review based on an old revision cannot approve current work.
- A crash cannot leave half a coordination commit.
- Pending jobs survive restart.

This is the first implementation gate. If it fails, resolve persistence design before building more behavior on top.

## 8. Development sequence and dependencies

### Phase 1 — Freeze behavior and interfaces

- Confirm the four-task demo and expected impact paths.
- Define the graph store and query interfaces.
- Define graph-unavailable and incomplete-analysis behavior.
- Confirm the single-process deployment boundary.
- Select a pinned FalkorDB version and persistent local configuration.

**Exit:** one shared specification for tests and implementation.

### Phase 2 — Implement FalkorDB persistence

Depends on Phase 1.

- Add the client and configuration.
- Implement the existing store interface, including project setup and sign-in records.
- Persist relationships alongside entity records.
- Port store contract tests to the real database.
- Complete the concurrency, retry, crash, and restart proof.

**Exit:** basic project, plan, and claim operations persist correctly without DynamoDB.

### Phase 3 — Replace the job runner

Depends on Phase 2's atomic commit and job persistence guarantees.

- Save jobs with the operations that create them.
- Add an in-process background worker.
- Recover unfinished work on startup.
- Bound retries and expose failures.
- Discard or re-review results when their source revision has changed.
- Ensure a disconnected MCP request does not lose an accepted job.

**Exit:** claim review completes and recovers without DynamoDB Streams.

### Phase 4 — Integrate graph-based coordination

Graph queries can be developed after Phase 1; end-to-end integration depends on Phases 2 and 3.

- Keep the pure calculation of changed plan items.
- Query affected tasks and evidence paths.
- Create scoped directives and re-review jobs.
- Include explanations in check-in responses and graph evidence in review context.
- Prevent graph-dependent approval when analysis is unavailable or incomplete.

A plan change must complete with the necessary directives or fail clearly before approval.

**Exit:** one approved change reaches direct and indirect dependents through the normal MCP workflow.

### Phase 5 — Run the four-agent demonstration

Depends on Phase 4. Prepare workspaces and prompts earlier.

- Give each agent its own workspace and task; connect all four to one project.
- Let them declare claims and begin implementing.
- Introduce the change once through the authorized plan workflow.
- Observe affected agents receiving updates at checkpoints.
- Confirm the unaffected agent checks in and receives no change directive.
- Run an independent integration test.
- Restart the service or open a fresh agent session and demonstrate recovery.

**Exit:** complete behavior with real agents, not only scripted service calls.

### Phase 6 — Package and submit

Depends on a successful Phase 5 rehearsal.

- Verify clean-environment setup.
- Document the graph model and actual Cypher queries.
- Record the four-window demonstration.
- Document limitations and observed manual interventions.
- Distinguish pre-existing functionality from hackathon contributions.
- Include AI-assistance disclosure and selected tracks.

**Exit:** a reproducible submission with working evidence.

## 9. Expected code changes

All paths refer to this official repository. New filenames are proposed.

| Area | Files |
| --- | --- |
| Graph persistence | New `midflight/adapters/falkor_store.py` and Cypher query files |
| Shared interfaces | `midflight/ports.py`; targeted additions to domain models |
| Graph query results | Proposed `midflight/domain/graph.py` |
| Impact propagation | `midflight/services/plans.py`; retain pure comparison in `domain/impact.py` |
| Review context | `services/claims.py`, `adapters/bedrock.py` |
| Agent explanations | `services/check_in.py`, `api/views.py`, `mcp/replies.py` |
| Durable job execution | `adapters/runners.py` and a new service worker module |
| Configuration and wiring | `config.py`, `wiring.py`, `main.py`, `api/app.py` |
| Setup | `pyproject.toml`, `uv.lock`, `.env.example`, Compose configuration |
| Validation | Store, service, MCP, graph integration, and scenario tests |
| Documentation | README, architecture, graph model, setup, and demo instructions |

Do not select `StreamRunner` merely because an old AWS setting exists. Make backend and runner selection explicit. Keep database access outside pure domain functions.

## 10. Four-window demo

Use a synthetic commerce application:

| Window | Agent task |
| --- | --- |
| 1 | Pricing: calculate prices and expose the pricing contract |
| 2 | Checkout: consume pricing and create order records |
| 3 | Reporting: consume order records and produce revenue reports |
| 4 | Notifications: manage an independent subscription workflow |

A suitable change is introducing currency-aware pricing and orders.

Approve it once. The graph should identify the pricing-to-checkout-to-reporting path. Notifications remains independent by design.

Show each affected agent's actual check-in explanation and response. Do not manually give each agent the change. Show the unaffected agent continuing useful work and checking in normally.

Finish with tests covering currency propagation, correct reporting behavior, and the independent notifications feature.

## 11. Acceptance criteria

- Four real agents participate in one shared project.
- Relevant tasks receive one directive per applicable change; unrelated tasks receive none.
- Direct and indirect dependency paths are visible.
- Removed links and cycles behave correctly.
- Graph evidence uses the correct plan and claim revisions.
- Stale reviews cannot approve newer state.
- Retries do not duplicate commits or work.
- Restart preserves context and pending work.
- Graph failure cannot masquerade as “no impact.”
- Existing applicable tests still pass.
- Integrated application behavior is checked independently.

## 12. Delivery priorities and decisions before implementation

Confirm the graph model, impact semantics, shared interfaces, atomic write mechanism, deployment boundary, and demo acceptance fixture before broad implementation. Shared model and port changes still require the repository's normal technical review.

Complete persistence correctness first, then one full graph-driven change workflow. Prioritize a reliable real-agent demonstration and clear evidence over additional features.

Aim to freeze features Saturday evening and submit by **Sunday, October 18, 2026, 9:30 AM PDT**, ahead of the **11:29 AM PDT deadline**.

Preferred track: **Agent Memory and Coordination**. Add **Agents That Act on Connected Data** if the completed demonstration supports it.

## References

- [Official hackathon rules and submission requirements](https://www.wemakedevs.org/hackathons/falkordb/rules)
- [FalkorDB queries and schema-version parameter](https://docs.falkordb.com/commands/graph.query)
- [FalkorDB Docker deployment and persistence](https://docs.falkordb.com/operations/docker)
- [Current code guide](../code-guide.md)
- [Current store contracts](../../midflight/ports.py)
