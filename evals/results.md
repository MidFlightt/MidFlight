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
| **Nova 2 Lite** | **new** | **yes** | **19 of 20** | **0 of 45** | **2.4 s** |
| gpt-oss-120b | new | yes | 9 of 20 | 0 of 45 | 8.4 s |

"Before" rows without a second look also compare against claims awaiting revision, as
the service did then. The other rows skip those claims (D29).

## What it says

1. **The second look is what removes false alarms.** On its own, each model's first pass
   flags a third to two thirds of the false alarms. Asking a second, narrow question
   ("do these statements answer the same question differently?") with the statements
   themselves cuts that to 8 of 45 on Nova Pro and 0 of 45 on Nova 2 Lite.
2. **The new first-pass wording alone makes things worse.** It flags more, on both
   models. It only pays off together with the second look, where a first pass that
   flags freely and a second pass that is strict work well together.
3. **Nova 2 Lite with the second look is the choice:** no false alarms in 45 reviews, at
   about the same speed. It is the reviewer model from this change on.
4. **It still missed a real conflict once in 20.** E-8 (a 20% cancellation fee against a
   full refund) passed in 1 of its 5 reviews, on both models. A miss isn't silent
   approval of the code: the assumption is still shown to the other task at check-in
   (D27), and `midflight/verify` still checks the push. But it is a miss.
5. **gpt-oss-120b is too timid:** no false alarms, and fewer than half the real conflicts.

## Limits

- 13 cases from two runs of one product, and the same cases were used to design the
  changes. The prompt's own example is deliberately not one of them, but this is not a
  held-out test. The fair test is a new trial: see the rerun in docs/experiment.md.
- The two "new, yes" rows for Nova Pro and Nova 2 Lite use the final wording. The other
  "new" and "yes" rows were measured with a draft whose example sentence came from case
  E-8; with that draft Nova 2 Lite scored 20 of 20 and 0 of 45.
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
