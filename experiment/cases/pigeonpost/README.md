# Case: PigeonPost

Six agents build a parcel service that delivers by pigeon: roost, pricing, dispatch,
billing, tracking, and a customer command line. The product brief every agent reads is
[`starter/README.md`](starter/README.md), and the lead's plan is
[`starter/PLAN.md`](starter/PLAN.md): seven requirements, six tasks, nine contracts. Every
approach gets both. Run B's Midflight plan is the same plan, from the same source
([`plan.py`](plan.py)).

The case is about news that appears after the plan is written. The write-up, with the
reasons for each choice and the ways the case leans toward Midflight, is
[docs/benchmark-pigeonpost.md](../../../docs/benchmark-pigeonpost.md).

## What differs from the HireBot cases

| | HireBot cases | PigeonPost |
| --- | --- | --- |
| Where agents work | Worktrees of one repository on one disk | One clone each of a shared repository (separate laptops) |
| Team chat (run A) | A file on the shared disk | `CHAT.md` on the repository's `chat` branch, read and posted with `tools/chat.py` |
| The plan | Run B's plan had contracts the others didn't see | The same `PLAN.md` for everyone |
| The lead | The person running the trial | An agent with a decision sheet fixed in advance |
| Timing | Everyone starts together | Three agents start, two join in phase 2, one in phase 3 |
| The lead's change | Pasted into every agent | N: pasted to everyone. A: posted once in the chat. B: approved in Midflight |

## The parts

| Agent | Builds | Starts | Its developer's private note |
| --- | --- | --- | --- |
| t1 Roost | the birds and destinations | phase 1 | phase 2: give max payloads in grams |
| t2 Pricing | quotes: fee, promo code, tax | phase 1 | phase 2: charge tax before the promo discount |
| t3 Dispatch | sending, showing, cancelling; flights left | phase 1 | phase 2: refund a cancelled delivery in full |
| t4 Billing | the revenue report | phase 2 | phase 2: keep the 4.00 base fee of a cancelled delivery |
| t5 Command line | every customer command | phase 2 | none |
| t6 Tracking | status and ETA | phase 3 | phase 3: call the ETA field `eta_min` |

## The trial

`python experiment/run.py pigeonpost <run> auto` runs these steps in order (`STEPS` in
[`case.py`](case.py), which also holds the exact words every agent and the lead are given):

1. `lead plan`: run B only, the lead proposes and approves the plan in Midflight.
2. `phase 1`, `phase 2`.
3. `lead answer`: the lead answers what it was asked, from its decision sheet.
4. `lead change`: the lead announces express delivery (plan version 2).
5. `phase 3`, `lead answer`, `phase 4`.
6. `merge`, `repair` ([20 checks](checks.md), run by [`score.py`](score.py)), `record`.

Run B needs a fresh Midflight project: `auto <project id>`.

## Results (October 10, 2026)

One trial per approach.

| Run | Approach | Checks at merge | Events held | Fix rounds | Agent cost | Turns | The lead answered |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [N1](results/N1/) | No channel | 13 of 20 | 3 of 6 | 2 | $2.06 | 126 | never (nobody could ask) |
| [A1](results/A1/) | Team chat | 18 of 20 | 5 of 6 | 1 | $1.88 | 105 | 5 posts |
| [B1](results/B1/) | Midflight | 20 of 20 | 6 of 6 | 0 | $2.69 | 177 | 3 escalations |

- **N1** lost the three events that depend on a developer's private note: the
  cancellation fee, tax before the promo discount, and payloads in grams. Nothing crashed.
- **A1** fixed the tax and the grams through the chat, and lost the cancellation fee: both
  agents read the lead's decision, kept their own developer's instruction, and asked
  again; the lead didn't repeat itself.
- **B1** passed everything at merge. The same second round happened (dispatch kept the
  full refund after the lead's first ruling), Midflight raised it again, the lead ruled
  again, and both parts built it.

B1's cost leaves out the lead's agent ($0.37), the harness's warm-up calls ($0.64), and
Midflight's own reviewer. Each run's `summary.json` ends with notes on what happened. The
write-up is [docs/benchmark-pigeonpost.md](../../../docs/benchmark-pigeonpost.md).

`python experiment/run.py pigeonpost all table` prints every recorded run.
