# PigeonPost with Midflight: the lead's prompts for Claude Code

You are the lead, and you build three parts: **T1 Roost**, **T2 Pricing**, and **T4
Billing**. Your teammate builds T3, T5, and T6 with
[their own prompts](pigeonpost-codex-prompts.md).

Open the `pigeonpost` folder in VS Code and paste these into the Claude chat, in order.
On your machine the hosted Midflight is already connected under the name
`midflight-live`.

## Before the first prompt

Two things in the browser, which only you can do:

1. Give the MidFlightt App access to `pigeonpost`:
   https://github.com/organizations/MidFlightt/settings/installations → **Configure** →
   add the repository.
2. Invite your teammate to https://github.com/MidFlightt/pigeonpost with write access
   (Settings → Collaborators).

## Set up the project

### Prompt 1: create the project

```text
Using midflight-live, create a Midflight project for MidFlightt/pigeonpost. Tell me the project id and the join code.
```

Send the join code to your teammate, and ask for their GitHub login. Wait until they say
they have joined.

### Prompt 2: load the plan

Put their login in place of `FRIEND_LOGIN`.

```text
Read PLAN.md. Using midflight-live, propose it to our PigeonPost project exactly as written: requirements R-1 to R-7, the six tasks, and the nine contracts with their fields and types. Branches: t1-roost, t2-pricing, t3-dispatch, t4-billing, t5-cli, t6-tracking. I own T1, T2 and T4. My teammate, GitHub login FRIEND_LOGIN, owns T3, T5 and T6. Then approve the plan with the reason "First plan" and show me the project status.
```

Tell your teammate the plan is approved. They can start now.

## Build

### Prompt 3: the roost (T1)

```text
Create and switch to branch t1-roost from main. My Midflight task is T1 in the PigeonPost project. Read README.md and PLAN.md, check in with midflight-live, submit your claim with every assumption you are making (include units), and wait for the verdict before writing code. Then build app/roost.py and edit only that file. The fleet: budget-bob (Budget Bob) max payload 1 kg, speed 36 km/h, 2 flights per day; express-edna (Express Edna) 2 kg, 90 km/h, 3 flights per day; sir-flaps-a-lot (Sir Flaps-a-Lot) 3 kg, 54 km/h, 2 flights per day; cargo-carl (Cargo Carl) 5 kg, 45 km/h, 1 flight per day. The destinations are in README.md. Check in again before you commit, commit, and tell me if anything is waiting for the lead.
```

### Prompt 4: pricing (T2)

```text
Create and switch to branch t2-pricing from main. My Midflight task is T2 in the PigeonPost project. Read README.md and PLAN.md, check in with midflight-live, submit your claim with every assumption you are making (include units), and wait for the verdict before writing code. Then build app/pricing.py and edit only that file. Check in again before you commit, commit, and tell me if anything is waiting for the lead.
```

### Prompt 5: billing (T4)

Do this one after your teammate has started dispatch, because billing reads deliveries
from it.

```text
Create and switch to branch t4-billing from main. My Midflight task is T4 in the PigeonPost project. Read README.md and PLAN.md, check in with midflight-live, submit your claim with every assumption you are making (include units and how you get every delivery from T3), and wait for the verdict before writing code. Then build app/billing.py and edit only that file. Check in again before you commit, commit, and tell me if anything is waiting for the lead.
```

## Lead the team

### Prompt 6: see what needs you

Paste this every 15 minutes or so. Nothing notifies you when a question is waiting.

```text
Show the PigeonPost project status from midflight-live: each task's claim and verdict, open directives, and open escalations. For each open escalation, show me both sides and wait for my decision before resolving anything.
```

### Prompts 7 to 9: your rulings

When an escalation is about one of these, paste the matching ruling. These are the
decisions the benchmark's checks expect.

Cancellations:

```text
Resolve that escalation with request_revision and this reason: Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, rounded half up to the cent. The customer's refund is the rest. The fee counts as revenue in the report. A cancelled delivery's total stays what was charged.
```

Tax and promo codes:

```text
Resolve that escalation with request_revision and this reason: The plan stands. Birdseed Tax is charged after the promo discount, exactly as R-2 says.
```

Units and names:

```text
Resolve that escalation with request_revision and this reason: The plan stands. Weights and payloads in kg, speeds in km/h, distances in km, money in credits with two decimals, and field names exactly as in the contracts.
```

If it isn't a real disagreement:

```text
Dismiss that escalation with the reason: not a real conflict, both sides say the same thing.
```

### Prompt 10: change the plan halfway

Paste this once everyone has a first version committed. Then tell your teammate the plan
changed.

```text
Using midflight-live, propose the next plan version for PigeonPost: the current plan plus requirement R-8, owned by T2, T3 and T5: "Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express)." Add express: boolean to the quote-request and delivery-request contracts and express_fee: number to the quote contract. Approve it with the reason "Launch change: express delivery", then tell me which tasks got a directive.
```

## Keep your own parts in step

Paste the matching prompt whenever you come back to a task, after the plan change, and
after any ruling.

### Prompt 11: catch up on the roost (T1)

```text
Switch to branch t1-roost. Check in with midflight-live for task T1. Answer any directive, look at what other tasks assume about mine, and revise your claim if anything changed, waiting for the verdict before changing code. Then update app/roost.py, check in again, and commit. Tell me what changed.
```

### Prompt 12: catch up on pricing (T2)

```text
Switch to branch t2-pricing. Check in with midflight-live for task T2. Answer any directive, look at what other tasks assume about mine, and revise your claim if anything changed, waiting for the verdict before changing code. Then update app/pricing.py, check in again, and commit. Tell me what changed.
```

### Prompt 13: catch up on billing (T4)

```text
Switch to branch t4-billing. Check in with midflight-live for task T4. Answer any directive, look at what other tasks assume about mine, and revise your claim if anything changed, waiting for the verdict before changing code. Then update app/billing.py, check in again, and commit. Tell me what changed.
```

## Finish

### Prompts 14 to 16: push each part

```text
Switch to branch t1-roost. Check in with midflight-live for task T1. If it says ready to push, push the branch and open a pull request into main. If not, tell me exactly what is blocking.
```

```text
Switch to branch t2-pricing. Check in with midflight-live for task T2. If it says ready to push, push the branch and open a pull request into main. If not, tell me exactly what is blocking.
```

```text
Switch to branch t4-billing. Check in with midflight-live for task T4. If it says ready to push, push the branch and open a pull request into main. If not, tell me exactly what is blocking.
```

### Prompt 17: merge everything

When all six pull requests are open, yours and your teammate's:

```text
List the open pull requests on MidFlightt/pigeonpost. Show me the list, and when I say go, merge them into main one at a time, then switch to main and pull.
```

### Score it

In a terminal, from the `midflight` folder:

```bash
python experiment/cases/pigeonpost/score.py ../pigeonpost
```

It prints each of the 20 checks with `"passed": true` or `false`, and at the end how many
checks each kind of event passed. The first trials scored 13 (no channel), 18 (team
chat), and 20 (Midflight).

## Starting over

In a terminal, in the `pigeonpost` folder:

```bash
python reset.py
```

Then, because Midflight keeps its plan and claims:

```text
Using midflight-live, withdraw my claims for T1, T2 and T4 in the PigeonPost project, then show me the project status.
```

Your teammate runs `python reset.py --local` and withdraws their own claims. Then start
again at Prompt 2, which proposes the plan as a new version.
