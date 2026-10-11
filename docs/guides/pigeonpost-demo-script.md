# PigeonPost demo script: three Midflight moments

A short, repeatable demo on the PigeonPost project (`pigeonpost-65f8`, repository
`MidFlightt/pigeonpost`). It shows the three moments from
[demo.md](../demo.md)'s acceptance scenarios:

1. **A claim is rejected before any code is written**, with the fix in the same reply.
2. **The lead changes the plan**, and only the tasks it touches hear about it.
3. **Two developers disagree**, and the question goes to the lead with both sides.

Two people: **Somesh** (lead; Claude Code; tasks T1, T2, T4; the Midflight connector is
named `midflight-live`) and **the teammate** (Codex; tasks T3, T5, T6; the connector is
named `midflight`).

Every scene works on claims only, so each takes about a minute and nobody waits for code.
Building comes after, off camera.

**Rehearse once before recording.** Scenes 1 to 3 are decided by Midflight's fixed rules
and come out the same every time. Scene 4 depends on Midflight's AI reviewer noticing the
disagreement; it did in the benchmark trial, but it is the one scene that can vary.

## Before recording

The teammate clears his old claim (Somesh's are already withdrawn). In Codex:

```text
Using the midflight tools, withdraw my claim C-46 for task T3 in project pigeonpost-65f8, with the reason "starting over for the demo". Then switch to main, pull, and delete my local branch t3-dispatch if it exists.
```

Somesh checks the slate is clean. In Claude Code:

```text
Show the status of Midflight project pigeonpost-65f8 from midflight-live.
```

It should show plan v1, no approved claims, and no open directives, escalations, or
decisions.

## Scene 1: a normal claim (teammate)

In Codex:

```text
Create and switch to branch t3-dispatch from main. Read README.md and PLAN.md. My Midflight task is T3 in project pigeonpost-65f8. Call the midflight check_in tool for T3. Then call submit_claim for app/dispatch.py: list the contracts I provide (delivery-request, delivery, availability) and the ones I consume (bird, destination, quote-request, quote) with the exact fields and types from the plan, and put my assumptions about T1 and T2 in assumptions, with units. Show me the verdict word for word. Do not write code yet.
```

**What to show:** `APPROVED`. Dispatch has said it reads `total` from pricing's quote.

## Scene 2: a claim is rejected (Somesh)

In Claude Code:

```text
Create and switch to branch t2-pricing from main. My Midflight task is T2 in project pigeonpost-65f8. Check in with midflight-live, then submit a claim for app/pricing.py. I want money as whole cents, so in the quote contract provide total_cents: integer in place of total. Submit it exactly that way even though PLAN.md says otherwise: I want to see what Midflight says. Show me the verdict word for word. Do not write code and do not change the claim until I say so.
```

**What to show:** `NEEDS_REVISION`, before a line of code exists. Midflight says the
`quote` contract has no field `total_cents` and gives the fix: provide `total: number`,
not `total_cents`. This is a rule, not an AI opinion.

Then:

```text
Do what Midflight says: fix the claim, submit it again, and show me the verdict word for word.
```

**What to show:** `APPROVED`.

## Scene 3: the lead changes the plan (Somesh, then both)

Somesh, as lead, in Claude Code:

```text
Using midflight-live, propose the next plan version for project pigeonpost-65f8: the current plan plus requirement R-8, owned by T2, T3 and T5: "Express delivery. A quote or a delivery can be express. An express parcel pays an express fee of 50% of the delivery fee (before any promo discount). Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total includes the express fee. On the command line, quote and send take --express and print a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't express)." Add express: boolean to the quote-request and delivery-request contracts and express_fee: number to the quote contract. Approve it with the reason "Launch change: express delivery", then tell me which tasks got a directive.
```

**What to show:** directives for T2, T3, and T5. Nothing for T1, T4, or T6.

The teammate, in Codex. Nobody told him anything:

```text
Call the midflight check_in tool for task T3 in project pigeonpost-65f8 and show me exactly what it returns. Do not change anything yet.
```

**What to show:** the directive waiting for T3, with what changed.

Somesh shows a task the change doesn't touch:

```text
Check in with midflight-live for task T4 in project pigeonpost-65f8 and show me exactly what it returns.
```

**What to show:** no directives.

Then each brings his claim up to date. Teammate:

```text
For task T3 in project pigeonpost-65f8: acknowledge the directive with acknowledge_directive, revise my claim for the express change (delivery-request gains express: boolean, quote gains express_fee: number), submit it, and show me the verdict word for word. Do not write code.
```

Somesh:

```text
Check in with midflight-live for task T2 in project pigeonpost-65f8, acknowledge the directive, revise my claim for the express change (quote-request gains express: boolean, quote gains express_fee: number), submit it, and show me the verdict word for word. Do not write code.
```

**What to show:** both `APPROVED` against plan v2.

## Scene 4: two developers disagree (teammate, Somesh, then the lead)

Each developer tells his own agent a different rule about cancellations. Neither tells
the other.

The teammate, in Codex:

```text
For task T3 in project pigeonpost-65f8: my rule is that a cancelled delivery is refunded in full, and we keep nothing. Revise my claim and add this assumption exactly: "T4: a cancelled delivery is refunded in full (refund = total). PigeonPost keeps no fee, so a cancelled delivery adds nothing to revenue." Submit it and show me the verdict word for word. Do not write code.
```

Somesh, in Claude Code:

```text
Create and switch to branch t4-billing from main. My Midflight task is T4 in project pigeonpost-65f8. Check in with midflight-live, then submit a claim for app/billing.py with the plan's report and delivery fields. My rule is that a cancelled delivery is not free for us. Add this assumption exactly: "T3: a cancelled delivery keeps the 4.00 base fee (refund = total - 4.00), and that 4.00 counts as revenue in the report." Show me the verdict word for word. Do not write code.
```

**What to show:** `HUMAN_REVIEW_REQUIRED`. Midflight doesn't pick a winner. It names the
question and says the lead must decide.

Somesh, as lead:

```text
Show the status of Midflight project pigeonpost-65f8 from midflight-live. For each open escalation, show me both sides word for word and wait for my decision.
```

**What to show:** the two sentences side by side.

Then the ruling, which is neither side's:

```text
Resolve that escalation with request_revision and this reason: Cancelling a delivery keeps a cancellation fee of 25% of the delivery's total, rounded half up to the cent. The customer's refund is the rest. The fee counts as revenue in the report. A cancelled delivery's total stays what was charged.
```

Each agent picks the ruling up at its next check-in. Teammate:

```text
Call the midflight check_in tool for task T3 in project pigeonpost-65f8 and show me what the lead decided. The lead's decision stands: revise my claim to match it, submit it, and show me the verdict word for word.
```

Somesh:

```text
Check in with midflight-live for task T4 in project pigeonpost-65f8 and show me what the lead decided. The lead's decision stands: revise my claim to match it, submit it, and show me the verdict word for word.
```

**What to show:** both `APPROVED`, and the decision recorded in the project status with
who made it.

If Midflight approves both claims in this scene without raising the question, the AI
reviewer missed it on that take. Reset (below) and run the scene again.

## After the demo: build it

The claims are approved, so the code can follow. Use the build prompts in
[pigeonpost-lead-prompts.md](pigeonpost-lead-prompts.md) and
[pigeonpost-codex-prompts.md](pigeonpost-codex-prompts.md), starting each with "your
claim is already approved; check in and build".

## Reset for another take

A repository can have only one Midflight project, and a project can't be deleted, so a
new take reuses this one.

1. **Somesh puts the first plan back** (the demo left the plan at the express version):

   ```text
   Read PLAN.md. Using midflight-live, propose it to project pigeonpost-65f8 as the next plan version, exactly as written: requirements R-1 to R-7 only, the nine contracts with only the fields in PLAN.md (no express fields), and the six tasks with the same branches and owners as now (SomeshAgrawal1318 owns T1, T2 and T4; Trexz14 owns T3, T5 and T6). Approve it with the reason "Back to the first plan". Then show me the project status.
   ```

   The plan's version number keeps counting up (v3, v5, and so on). Its content is the
   first plan again. Decisions end by themselves once the claims they were about are
   withdrawn.

2. **Then each of you answers the directives that caused, withdraws your claims, and
   clears your branches.** Somesh:

   ```text
   Using midflight-live, in project pigeonpost-65f8: acknowledge any open directives for T1, T2 and T4, then withdraw every claim I have on those tasks with the reason "another take". Then switch to main and delete my local branches t2-pricing and t4-billing.
   ```

   Teammate:

   ```text
   Using the midflight tools, in project pigeonpost-65f8: acknowledge any open directives for T3, T5 and T6, then withdraw every claim I have on those tasks with the reason "another take". Then switch to main and delete my local branch t3-dispatch.
   ```

3. **Check:** the status shows no approved claims and no open directives, escalations, or
   decisions.

If you pushed branches to GitHub, `python reset.py` in the `pigeonpost` folder deletes
them there too and puts `main` back to the starter.
