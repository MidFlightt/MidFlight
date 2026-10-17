# GH-02 — FalkorDB Store adapter

The full existing `Store` protocol is implemented in
[`midflight/adapters/falkor_store.py`](../../midflight/adapters/falkor_store.py).
It can be injected into `build_services`. Backend selection and the recoverable
worker are separate follow-up changes; this does not switch the hosted deployment.

## Use and verification

Install the optional client dependencies with `uv sync --locked --extra falkordb`.
For a development server with the persistence configuration proved in
[GH-01](../../experiment/falkordb-proof/README.md):

```python
from midflight.adapters.falkor_store import FalkorStore

store = FalkorStore.connect(graph_name="midflight", host="127.0.0.1", port=6379)
# Inject store into build_services(store, clock, ...).
# On shutdown:
store.close()
```

Connection keyword arguments go to the FalkorDB client, including authentication
and TLS settings. Supply secrets through deployment configuration, never source.
The constructor also accepts an existing client Graph; the caller owns that connection.
Use a dedicated graph per deployment and provision its persistence before use.
Construction synchronously initializes labels and ID/key indexes before any requests
are accepted. Do not bypass this initialization: the first CI run found that concurrent
project-creation queries compiled against absent labels could all pass the empty-project
revision check on the pinned engine. Indexed schema initialization plus ten independent
empty-graph race tests guard this case. Initialize the single service before starting workers.

Run all store contract tests and adapter failure tests with:

```sh
uv run --extra falkordb pytest --falkordb tests/unit/test_store.py tests/integration/test_falkor_store.py
```

These tests create their own digest-pinned Docker server, loopback port and disposable
volume through the unchanged GH-01 harness. They never connect to an existing server.
An explicit run fails if Docker or the dependency is unavailable. Ordinary `uv run pytest`
skips the real-database cases. CI runs them in a separate job.

## Atomic writes

Each `Commit` is a single parameterized Cypher query. Before mutation, that query
checks the receipt, project revision, project ownership and immutable plan/claim
history. Only a valid query branch creates or updates the project, entities, audit
events and receipt. `FOREACH` executes the mutation block zero times on rejection.
No Python lock or pre-read supplies the concurrency guarantee.

The project revision is a separate node property, so saving an old Project snapshot
cannot roll it back. Reads overlay that property onto the saved model. Approved plans
cannot change; a saved claim revision can change only its verdict. Canonical JSON
compares nested declarations without depending on dictionary key order.

Receipts retain the original committed revision. Repeating a key for the same project
returns that result even after later changes, matching the existing Store contract.
Unlike the standalone GH-01 experiment, this interface does **not** fingerprint and
reject changed payloads under an existing key: callers must use a stable key for the
same operation, as with the existing adapters. Transport retries are disabled; callers
retry an ambiguous commit with its original key. ID allocation is atomic but not
idempotent: an ambiguous response may leave a gap, and IDs must never be reused.

Additional validation rejects cross-project reuse of global entity IDs or receipt keys,
audit events owned by another project, and conflicting versions of the same record
inside one commit. These checks tighten malformed-input handling without changing
valid service operations or the shared models/ports.

## Stored graph

Entities have `MFEntity` and a type label (`MFProject`, `MFPlan`, `MFClaim`, etc.).
Canonical JSON preserves every domain field; scalar fields support parameterized
lookups. Composite keys encode JSON arrays to avoid delimiter collisions. Plan keys
include project and version; claim keys include ID and revision.

Projects link to entities through `CONTAINS`, audit events through `AUDITED`, and
receipts through `RECORDED`. `MFIdentity` records prevent global IDs moving between
projects. `MFCounter` supplies global counters by prefix. `MFUser` and `MFAuth` are
operational records, outside project context. Auth expiry is enforced on every read;
expired records remain stored until explicitly deleted. Token/join-code/repository
lookups use current node fields, so rotation leaves no stale lookup pointers.

This is the persistence layer. Versioned Task/Contract/Requirement nodes, dependency
edges and evidence traversal are **not yet materialized**: plans still contain their
full structured definitions as JSON. Those are the next graph-coordination work and
must be written atomically with plans before graph-based impact is enabled. Do not
export the entire operational graph to agents or a demo viewer.

## Evidence and boundaries

The tests cover every existing shared store contract (including the service scenario),
competing CAS writes, concurrent duplicate requests, immutable-history races without
revision bumps, stale reviews, an injected lost success response, rollback after an
engine error, cross-project collisions, dead-database errors, and SIGKILL recovery
of records, jobs, audit, auth, users, receipts and counters through a fresh connection.

Errors propagate rather than masquerading as missing data. Successful persistence
requires the pinned, durable server configuration; see GH-01 for its evidence and
limits. This does not prove disk failure recovery, replication, production load or
multi-worker execution. ID/key lookups are indexed; filtered lists still scan typed labels. Additional indexes
and load bounds need measurement before scaling beyond the small hackathon deployment. The worker
must still recover and execute stored jobs, and runtime wiring must explicitly select
FalkorDB and its matching runner before deployment.
