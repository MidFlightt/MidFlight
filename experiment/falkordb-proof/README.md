# GH-01: FalkorDB persistence proof

This is an isolated experiment for the `graph-hacks` migration. It does **not** implement
MidFlight's full `Store` protocol or change application wiring, models, dependencies,
permissions, or job scheduling.

**Result:** the 23 real-database cases passed on the pinned FalkorDB 4.22.1 image on
ARM64. The existing application suite also passed (433 tests). See
[evidence.json](evidence.json) for the environment, case results, and source hashes.

## Run it

From the repository root, with Python 3.12+, uv, and Docker running:

```sh
uv sync --project experiment/falkordb-proof --locked
uv run --project experiment/falkordb-proof --locked pytest \
  -c experiment/falkordb-proof/pyproject.toml experiment/falkordb-proof
```

Optional machine-readable evidence:

```sh
mkdir -p .midflight/falkordb-proof
uv run --project experiment/falkordb-proof --locked pytest \
  -c experiment/falkordb-proof/pyproject.toml experiment/falkordb-proof \
  --junitxml=.midflight/falkordb-proof/results.xml \
  --proof-metadata=.midflight/falkordb-proof/environment.json
```

The separate project and lockfile keep the main application's dependencies unchanged.
These tests are opt-in; the normal root `uv run pytest` still runs the existing suite.
A missing Docker daemon or failed database startup fails the proof rather than skipping it.

The fixture creates a uniquely named container, named volume, and loopback-only port.
It kills **only that container** in crash tests, then removes its container and volume
at teardown. It never accepts an existing database URL. Do not run with pytest-xdist;
tests share a database process whose restart is intentionally controlled by the suite.
If the test process is itself killed, its `midflight-proof-<random>` container/volume may
need manual cleanup. Never prune unrelated Docker resources.

The image is pinned by version and digest in `conftest.py`. Pull it beforehand on slow
connections (the fixture's Docker commands have a 60-second timeout):

```sh
docker pull falkordb/falkordb:v4.22.1@sha256:b0bdcac2cbaff989e77cb0610439b7a9289e86de033ccbbd4368b66fb680ae7a
```

Persistence is explicitly configured and checked: `appendonly yes`, `appendfsync always`,
RDB snapshots disabled. Durability observations apply to that configuration and a
container-process crash on the tested host, not arbitrary hardware or storage failure.

## Write mechanism

`proof_store.py` contains the exact parameterized Cypher statements.

A successful submission is **one write query** that:

1. Matches the project and checks its `coord_rev` against the reviewed value.
2. Checks that the idempotency receipt does not already exist.
3. Advances the revision and creates a pending claim, pending review job, and their edge.
4. Creates the audit event and receipt in the same query.
5. Returns the committed revision.

No Python lock is used. Independent clients race against the same graph. The database's
conditional query is responsible for choosing the winner.

If a query changes nothing, a read resolves whether the receipt already exists. An exact
retry returns its **original** committed revision, even if later changes advanced the
project. Reusing a successful request key with different input is rejected. A failed
revision check creates no receipt, so its operation can be retried against fresh state.

The receipt's fingerprint includes the operation, project, expected revision, and payload.
Client transport retries are disabled so test failures are not silently hidden.

Review completion is also conditional on both the project revision and a pending job.
A stale completion changes neither claim nor job, creates no receipt/audit, and leaves
work discoverable for a fresh review. `plan_version` and `coord_rev` are separate values.
FalkorDB's schema-cache `version` parameter is not used as application version control.

## What is exercised

| Behavior | Test evidence |
| --- | --- |
| Atomic submission | Claim, job, edge, audit, receipt, and revision saved together |
| Concurrent updates | Ten rounds of eight clients: exactly one winner per shared expected revision |
| Retrying contention | Four writers each commit 12 operations after bounded revision retries; no updates lost |
| Duplicate requests | Eight clients submit the same request; one commit, seven duplicate results |
| Lost reply | Fault injection discards a successful server reply; retry returns the original result after a later plan change |
| Conflicting retry | Same key with changed payload is rejected without mutation |
| Stale review | A plan change invalidates a captured review revision; fresh review then completes once |
| Runtime rollback | Invalid property type injected after mutation clauses rolls back the complete query, including its receipt |
| Reader isolation | One-query snapshots during 60 submissions never observe a partial claim/job/audit/receipt bundle |
| Fresh process | A separate Python process discovers a pending job and completes it |
| Database restart | SIGKILL and restart preserve acknowledged data, receipts, and pending work |
| Crash during writes | Kill during a submission stream; all acknowledged requests survive, recovered requests have complete bundles, retries resolve attempted outcomes |
| Isolation | Separate graphs with identical project/request IDs do not share data |
| Availability | A dead database raises an error instead of returning empty context |

The lost-reply case is a simulated client acknowledgement loss after a real database
commit, not a physical network fault. The crash-during-writes case kills an active stream;
it does not guarantee hitting a particular instruction inside a particular query.

## Interpretation and remaining work

**The bounded persistence gate passes for this mechanism and environment.** We can now
implement the real adapter using conditional, single-query coordination commits.
This is empirical validation, not a proof of every database operation under every failure.

Still required before application migration:

- Implement all `Store` methods and run its existing contract tests against FalkorDB.
- Preserve plan/claim immutability, IDs, authorization, and entity validation.
- Compile complete application commits into atomic writes, including empty entity lists
  and multi-entity updates. This experiment covers only submit/change-plan/complete-review.
- Implement the durable worker, scheduling, retry/backoff policy, and startup recovery.
  This proof only establishes pending-job discovery and idempotent completion primitives.
- Test worker crashes during real model calls, timeouts, and application lifecycle events.
- Verify performance and durability on the intended deployment architecture. Only ARM64
  was exercised here; no failover, replication, disk loss, or power-loss guarantee is claimed.
- Verify graph dependency traversal and the four-agent workflow separately.

The first exploratory restart run failed because Docker reassigned an automatically
published host port. The fixture now reserves an explicit loopback port for the container
lifetime. The database recovered; this was a test-harness connectivity error.

## Sources

- [FalkorDB atomicity and concurrency documentation](https://docs.falkordb.com/design/concurrency)
- [FalkorDB query and parameter semantics](https://docs.falkordb.com/commands/graph.query)
- [Persistence configuration](https://docs.falkordb.com/operations/docker)
- [Graph Hacks development plan](../../docs/graph-hacks/development-plan.md)

This experiment does not rely on `MULTI/EXEC` for rollback across multiple commands;
all related graph writes are contained in one Cypher query.
