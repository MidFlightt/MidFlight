# PigeonPost after check-in markers (run B2)

Run on October 11, 2026. One new trial of the [PigeonPost benchmark](benchmark-pigeonpost.md)
on the live service, right after S-13 was merged and deployed
([#26](https://github.com/MidFlightt/MidFlight/pull/26)): a `check_in` reply ends with a
marker, and an agent that passes it back gets only what is new. The other three columns
are the October 10 runs; they were not run again.

PigeonPost is Midflight's home ground by design, and every number here is one trial.

## The short answer

Midflight passed every check again, and cost less than it did before the markers.

| | Before markers (B1, Oct 10) | With markers (B2, Oct 11) | Change |
| --- | --- | --- | --- |
| Checks passing right after merging | 20 of 20 | 20 of 20 | same |
| Mid-flight events held | 6 of 6 | 6 of 6 | same |
| Fix rounds | 0 | 0 | same |
| Cost of the six agents | $2.69 | **$2.35** | 12% less |
| Tokens of the six agents, all kinds | 5.84 million | **5.17 million** | 11% less |
| Text Midflight sent the agents | 144,788 characters | **107,612 characters** | 26% less |
| The lead had to decide | 3 times | 2 times | |
| Agent starts without Midflight's tools | 5 | 0 | |

## All four approaches

| | N: no channel | A: team chat | B: Midflight before | B: Midflight with markers |
| --- | --- | --- | --- | --- |
| Checks passing right after merging | 13 of 20 | 18 of 20 | 20 of 20 | **20 of 20** |
| Mid-flight events held | 3 of 6 | 5 of 6 | 6 of 6 | **6 of 6** |
| Fix rounds to pass all | 2 | 1 | 0 | **0** |
| Cost of the agents and the fixer | $2.06 | $1.88 | $2.69 | **$2.35** |
| Cost above the team chat | | | 43% | **25%** |
| Agent turns | 126 | 99 | 160 | 155 |
| Agent minutes | 6.3 | 6.5 | 10.0 | 8.5 |

Midflight is still the most expensive approach on this case. Its gap to the team chat
went from $0.81 to $0.47.

## Tokens

Claude Code reports four kinds. Almost all of a trial is cache reads: an agent reads its
whole conversation again on every step, at a much lower price than new input.

These are the building agents plus the fixer that repairs failed checks after the merge,
the same agents the cost row counts. So the rework is inside the no-channel and team-chat
columns; Midflight needed none.

| | N: no channel | A: team chat | B: before | B: with markers |
| --- | --- | --- | --- | --- |
| Input, not cached | 152 | 168 | 198 | 184 |
| Output | 32,737 | 33,521 | 52,649 | 44,306 |
| Cache read | 3,435,624 | 3,906,466 | 5,518,369 | 4,890,928 |
| Cache write | 261,207 | 190,911 | 264,096 | 233,015 |
| **Total** | 3,729,720 | 4,131,066 | 5,835,312 | **5,168,433** |

What the rework was, inside those totals:

| | N: no channel | A: team chat | B: before | B: with markers |
| --- | --- | --- | --- | --- |
| Fix rounds | 2 | 1 | 0 | 0 |
| The fixer's tokens | 749,834 | 175,732 | 0 | 0 |
| The fixer's cost | $0.33 | $0.12 | $0 | $0 |
| Building agents alone, cost | $1.73 | $1.76 | $2.69 | $2.35 |

The lead's own agent is kept apart, in tokens as in cost: none in N, 257,607 tokens in
A, 810,470 in B before, 805,177 in B with markers.

Cost by agent in B2: roost $0.40, pricing $0.41, dispatch $0.49, billing $0.37, command
line $0.43, tracking $0.25.

## Midflight's own share

Read from the trials' logs with
[`experiment/midflight_share.py`](../experiment/midflight_share.py): the replies the six
building agents really got.

| | B: before | B: with markers |
| --- | --- | --- |
| Calls to Midflight | 56 | 58 |
| Characters the agents sent | 40,680 | 27,166 |
| Characters Midflight sent back | 144,788 | 107,612 |
| Characters per reply | 2,585 | 1,855 |
| Check-ins | 26 | 27 |
| Check-ins that passed a marker | not available then | 12 |

Six of B2's 27 check-ins were an agent's first, with no marker to pass yet. So the agents
passed it in 12 of the 21 where they could. Pricing and dispatch passed it almost every
time (4 of 5 each); the other four agents once each.

## Costs kept apart

| | B: before | B: with markers |
| --- | --- | --- |
| The lead's own agent | $0.37 (810,470 tokens) | $0.36 (805,177 tokens) |
| The harness's warm-up calls | $0.64 | $0.74 |
| Agents, lead, and warm-up together | $3.70 | $3.46 |
| Midflight's reviewer on AWS (Nova 2 Lite) | not measured | not measured |

## What happened in B2

- **Cancellation fee.** Midflight raised the disagreement between dispatch and billing,
  the lead ruled 25%, dispatch still refunded in full, Midflight raised it again, and the
  lead ruled again. Both parts built it. The same two rounds happened in B1.
- **Tax.** Midflight blocked pricing's claim to charge tax before the promo discount as
  a conflict with the plan. Pricing kept the plan's rule.
- **Field name.** Tracking kept the contract's `eta_minutes` over its developer's
  `eta_min`.
- **No false alarm reached the lead.**

## Read this before quoting the numbers

1. **One trial each.** We don't know how much two identical runs differ, so a 12% saving
   may be partly luck.
2. **Two things changed between B1 and B2,** the markers and the Lambda concurrency
   limit (10 to 1,000). B1 restarted five agents that came up without Midflight's tools;
   B2 restarted none. The drop in reply text (26%) is the markers' own effect. The drop
   in cost is both.
3. **The agents skipped the marker in 9 of 21 check-ins.** The saving would be larger if
   they always passed it.
4. **The unit event passed, but not the way the plan says.** The roost kept payloads in
   grams, as its developer asked. Midflight recorded that as agreed between the roost and
   dispatch (decision E-150) instead of holding the plan's kg, as it did in B1. Dispatch
   and the command line convert, so the three checks pass and the product behaves
   correctly, but README and PLAN still say kg.
5. **The project was named "PigeonPost benchmark B2 (markers)"**, and agents can see a
   project's name. It may have nudged them toward the marker.
6. **All six agents sign in as the lead's account,** as in B1, so every check-in returns
   the lead's view of the project. Real teammates would get less text.
7. **The no-channel and team-chat runs are from October 10.** They don't use Midflight,
   so the deploy doesn't affect them, but they were not repeated.

Everything recorded for the run is in
[`experiment/cases/pigeonpost/results/B2/`](../experiment/cases/pigeonpost/results/B2/).
