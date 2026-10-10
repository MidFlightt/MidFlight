# Scenarios

Each file is one demo scenario, played by `tests/scenario_runner.py` against the real
services with fakes (in-memory store, scripted AI reviewer). `uv run pytest
tests/test_scenarios.py -v` runs them all. Somesh writes them; Frederik checks each
one against its use case.

A claim lists only what differs from the demo defaults in `tests/demo_fixture.py`:
T1 provides `checkout-response {total_cents: integer}`, T2 consumes it, and T3 has no
interfaces.

```yaml
name: What happens, in one sentence
requirement: "requirements §11: the row this covers"
use_cases: [UC-04, UC-05]
plan_version: 1            # optional; seeds plans v1..N, N is current
reviewer:                  # optional scripted AI replies, in order; then it finds nothing
  - []                     # no findings
  - {raise: unavailable}   # the model timed out
steps:
  - say: Optional narration, shown if the step fails
    submit: {as: T2, name: page, claim: {consumes: [...]}}
    expect: {state: needs_revision, blocking: [contract_field_missing]}
```

| Step | Does |
| --- | --- |
| `submit: {as, name?, revise?, claim?}` | The task's agent submits a claim. `revise: page` sends a new revision of the claim named `page`. |
| `withdraw: {as, claim, reason?}` / `close: {...}` | The agent withdraws or closes a named claim |
| `race: {as, names: [a, b]}` | Two claims at once: the second review saves while the first is still running |
| `go_stale: "reason"` | Marks GitHub data stale |
| `claims: {page: approved}` | Checks the current state of named claims |

| `expect` key | Checks |
| --- | --- |
| `state`, `revision` | The verdict |
| `findings`, `blocking` | Finding kinds, all or only blocking (order doesn't matter) |
| `correction` | One finding proposes exactly this correction |
| `contracts` | Contracts returned to build against |
| `review_complete` | `false` when the AI review was unusable |
| `error`, `hint_contains`, `nothing_saved` | The step is refused with this error, and nothing changed |

Unknown keys are errors, so a typo fails the test instead of skipping a check.
