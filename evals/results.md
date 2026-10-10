# Reviewer eval: replaying the experiment's escalations

Run on October 10, 2026 with [`replay_escalations.py`](replay_escalations.py). This is
the first part of task S-8: it measures unnecessary blocks and missed conflicts on real
cases. It is not yet the full eval (about 20 cases, tokens, held-out data).

## The cases

Every escalation Midflight opened during the HireBot experiment
([docs/experiment.md](../docs/experiment.md)), rebuilt from the live table: the claim
under review, the plan, and the other claims as they stood at that moment. 13 cases in
[`escalations/hirebot.json`](escalations/hirebot.json):

- **4 real conflicts** (E-3, E-4, E-8, E-10): two statements that answer the same
  question differently. The reviewer should block these.
- **9 false alarms** (the rest): duplicated work, a requirement that is silent, a claim
  already sent back for revision, two claims saying the same thing. The reviewer should
  let these through.

The model doesn't give the same answer every time, even at temperature 0, so each case
is reviewed 5 times: 20 reviews of real conflicts and 45 of false alarms per row.

## Results

| Model | First-pass wording | Second look | Real conflicts blocked | False alarms blocked | Per review |
| --- | --- | --- | --- | --- | --- |
| Nova Pro (as deployed before) | before | no | 20 of 20 | 13 of 45 | 2.0 s |
| Nova Pro | new | no | 19 of 20 | 24 of 45 | 2.0 s |
| Nova Pro | before | yes | 20 of 20 | 9 of 45 | 3.2 s |
| Nova Pro | new | yes | 19 of 20 | 8 of 45 | 3.1 s |
| Nova 2 Lite | before | no | 20 of 20 | 21 of 45 | 1.4 s |
| Nova 2 Lite | new | no | 20 of 20 | 28 of 45 | 1.5 s |
| Nova 2 Lite | before | yes | 20 of 20 | 4 of 45 | 2.7 s |
| **Nova 2 Lite** | **new** | **yes** | **20 of 20** | **1 of 45** | **2.5 s** |
| gpt-oss-120b | new | yes | 9 of 20 | 0 of 45 | 8.4 s |

"Before" rows without a second look also compare against claims awaiting revision, as
the service did then. The other rows skip those claims (D29).

## What it says

1. **The second look is what removes false alarms.** On its own, each model's first pass
   flags a third to two thirds of the false alarms. Asking a second, narrow question
   ("do these statements answer the same question differently?") with the statements
   themselves cuts that to 8 of 45 on Nova Pro and 1 of 45 on Nova 2 Lite.
2. **The new first-pass wording alone makes things worse.** It flags more, on both
   models. It only pays off together with the second look, where a first pass that
   flags freely and a second pass that is strict work well together.
3. **Nova 2 Lite with the second look is the choice:** one false alarm in 45 reviews, at
   about the same speed. It is the reviewer model from this change on.
4. **A real conflict can still slip through.** In an earlier measurement of the same
   setup, E-8 (a 20% cancellation fee against a full refund) passed in 1 of its 5
   reviews, on both models. A miss isn't silent approval of the code: the assumption is
   still shown to the other task at check-in (D27), and `midflight/verify` still checks
   the push. But it is a miss.
5. **On new claims it is not this clean.** The simulated run in
   [docs/pages/walkthrough.html](../docs/pages/walkthrough.html) used freshly worded
   claims. Midflight stopped a claim four times: two were the real questions and two
   were false alarms the second look let through ("two parts both compute prices", and
   "the plan does not mention refunds"). Better than the experiment's 7 of 9, not fixed.
6. **gpt-oss-120b is too timid:** no false alarms, and fewer than half the real conflicts.

## After S-12: who settles it

From S-12 on, the reviewer does more than block. A flag that survives the second look
gets a third narrow question: is this a product decision for the lead, or a technical
one the reviewer settles, and what is the answer? So the replay now counts, per case,
where it ends up. Same 13 cases, five reviews each, Nova 2 Lite:

| | Result |
| --- | --- |
| Real questions stopped | 19 of 20 reviews |
| Of those, sent to the right decider | 15 of 20 |
| False alarms that reached the lead | 0 of 45 reviews |
| False alarms that asked an agent to revise for nothing | 4 of 45 reviews |
| Time per review | 2.9 s |

"The right decider" is the lead for the cancellation fee (E-8) and the reviewer for the
rest: what `total` holds (E-10), and the tax cases the plan already answers (E-3, E-4).
Every miss on that line erred towards the lead: the reviewer sent the `total` question
to the lead in 3 of 5 reviews. An earlier wording, with one combined question, did
worse (16 of 20 stopped, 4 of 45 false alarms to the lead), which is why each question
is its own call.

The "revise for nothing" column is new. Before S-12 a blocking mismatch from the first
pass went straight to the agent unchecked and wasn't counted here.

## Limits

- 13 cases from two runs of one product, and the same cases were used to design the
  changes. The prompt's own example is deliberately not one of them, but this is not a
  held-out test. The fair test is a new trial: see the rerun in docs/experiment.md.
- The two "new, yes" rows for Nova Pro and Nova 2 Lite use the final wording (the Nova
  2 Lite row is the last of three measurements: 20 of 20 and 0 of 45 with a draft,
  19 of 20 and 0 of 45, then 20 of 20 and 1 of 45). The other "new" and "yes" rows were
  measured with the draft, whose example sentence came from case E-8.
- The other claims' states at each moment are rebuilt from timestamps and the audit log,
  which is close but not exact. That is why "as deployed before" blocks 13 of 45 false
  alarms here, while in the live runs all 9 were raised at least once.
- Claude models couldn't be tried: no AWS account available to us can call them yet.

## Rerun it

```sh
export AWS_PROFILE=midflight AWS_DEFAULT_REGION=us-east-1
export MIDFLIGHT_REVIEWER_MODEL=us.amazon.nova-2-lite-v1:0
export MIDFLIGHT_REVIEWER_ROLE_ARN=<the reviewer role>
uv run python evals/replay_escalations.py run --repeat 5
```
