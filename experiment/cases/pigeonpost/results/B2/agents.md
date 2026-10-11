# What each agent did and said in run B2

## 01. lead (plan): 5 turns

Tools: ToolSearch x1, project_status x1, propose_plan x1, approve_plan x1

Approved plan version 1.

## 02. t1 (p1): 13 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Write x1

I built `app/roost.py` with the four birds and four destinations, plus `GET /birds`, `/birds/{handle}`, `/destinations` and `/destinations/{code}`. An unknown handle or code returns 404, and the fields match the `bird` and `destination` contracts.
I checked it with a quick test client (4 birds, one bird and one destination fetched, 404 on an unknown code) and committed it on `t1-roost` as c6daf2b. Midflight approved my claim C-50, and its last check-in said ready to push.

## 03. t2 (p1): 14 turns

Tools: Read x5, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Write x1

T2 is built and committed on `t2-pricing` (b7b17ec). It adds `POST /quote` in `app/pricing.py`, plus `compute_quote()` for T3 to import. The fee is 4.00 + 0.50 per km + 2.00 per kg, COOCOO takes 15% off, other promo codes return 400, tax is 8%, and rounding is half-up to the cent. In a test run, harbor at 2.5 kg gave 14.04 with no promo and 11.93 with COOCOO. An unknown promo gave 400.

Distances come from `roost.DESTINATIONS`. `roost.py` is still empty here, so for now it falls back to the README table. An unknown destination returns 404, which the plan doesn't specify. I haven't pushed. Midflight approved the claim (C-51) and showed ready to push, and the shared quote and destination contracts are unchanged.

## 04. t3 (p1): 13 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Write x1

I built `app/dispatch.py` and committed it on `t3-dispatch`. I couldn't run or test it, because `fastapi` isn't installed here and the other parts are still empty stubs. The Midflight claim was approved and my last check-in said ready to push, but I haven't pushed.

- **Endpoints:** `POST /deliveries`, `GET /deliveries/{id}`, `POST /deliveries/{id}/cancel` and `GET /birds/{handle}/availability`. Dispatch picks the smallest-payload bird that fits and still has a flight left, returns 400 for bad weights, parcels that are too heavy or no free bird, and 404 for an unknown delivery or bird. Cancelling gives the bird its flight back and sets the refund to the full total.
- **Assumptions:**
  - Dispatch gets birds and quotes by calling the app's own `/birds` and `/quote` endpoints.
  - It keeps deliveries and flights used in memory.
  - A second cancel returns 400.

## 05. t1 (p2): 12 turns

Tools: check_in x2, submit_claim x1, Bash x3, Edit x4, PowerShell x1

`app/roost.py` now gives each bird's `max_payload` in grams: budget-bob 1000, express-edna 2000, sir-flaps-a-lot 3000, cargo-carl 5000. It's committed on `t1-roost`. I didn't re-run the endpoint test after this change.

This conflicts with README and PLAN, which say kg. Midflight approved the revised claim but flagged a conflict with T3's claim C-52, which assumes kg. T3 must compare `weight_kg * 1000` to `max_payload`, and T5's `birds` command, which prints `max_payload=<kg>`, must convert back. Please settle the unit with the lead and the T3 and T5 developers before merging, or the bird choice will be wrong (a 2 kg parcel against 1000 would look light enough for any bird).

## 06. t2 (p2): 3 turns

Tools: check_in x1, submit_claim x1

I made no code change. Midflight rejected the tax change as a blocking conflict with the plan, so the commit (b7b17ec) still has the plan's tax rule.

- **What conflicts:** R-2 says Birdseed Tax is 8% of (delivery fee − promo discount). Your note says 8% of the full fee. My revised claim (C-51 rev 2) was marked NEEDS_REVISION, and it affects T3's `delivery.total` and the T5 output.
- **What changes in the numbers:** harbor at 2.5 kg with COOCOO would be tax 1.04 and total 12.09 under your reading. The committed code gives tax 0.88 and total 11.93.
- **What I need from you:** either the lead amends R-2 (or rules on it), and then I change one line and recommit, or you want me to follow the plan as written. I'm not building the changed rule until one of those happens.

## 07. t3 (p2): 5 turns

Tools: check_in x1, Bash x2, submit_claim x1

Cancel already refunded the full `delivery.total` with nothing kept, so I left that logic alone and wrote the full-refund ruling into my Midflight claim. I also changed dispatch to read `max_payload` in either grams or kg, as T1's developer said it would be grams. I committed that as 5d3e4bb and haven't run any of it, since `fastapi` isn't installed here.

Two things still need the lead's decision. The `max_payload` unit conflicts with PLAN, and Midflight's check flagged my "either unit" handling against T1's grams claim. T2 also taxes the full fee, where PLAN R-2 taxes the fee after the promo discount, so `delivery.total` will follow whichever T2 ships.

## 08. t4 (p2): 13 turns

Tools: Read x5, Glob x1, ToolSearch x1, check_in x1, Bash x2, submit_claim x1, Write x1

I built `GET /report` in `app/billing.py` and committed it on `t4-billing`. It returns revenue from confirmed deliveries, the confirmed and cancelled counts, and flights per bird (confirmed only). I haven't run it, because T3's dispatch code isn't there yet.

The cancelled-delivery base fee isn't counted yet, so revenue is wrong for any cancelled delivery. Midflight blocked claim C-54: your instruction is to keep the 4.00 base fee on every cancelled delivery, but T3's claim assumes a full refund. The lead has to decide that. Once they do, set `CANCELLED_REVENUE` in `app/billing.py` to 4.00 (currently 0.00). You can't push until then.

The report reads deliveries from a dict named `deliveries` in `app/dispatch.py`, which T3 hasn't confirmed.

## 09. t5 (p2): 13 turns

Tools: Read x2, Glob x1, ToolSearch x1, check_in x2, Bash x3, submit_claim x2, Write x1

I built `cli/pigeon.py` with every command in README's command-line section, using httpx and `PIGEON_URL`. Errors print `error: <message>` and exit 1, and `send` prints the `/quote` result before posting to `/deliveries`. It's committed on `t5-cli` (6f2ae78). I never ran it against a live API because the other parts weren't merged. The only thing I ran was a bad command, which gave the expected `error:` line.

Two things to confirm with the lead:
- **Grams:** Midflight decision E-150 says bird `max_payload` is in grams, so `birds` converts to kg for printing. I followed that.
- **Promo:** the `--promo` field is left out of the request when it isn't given, rather than sent as an empty string.

I did not rule on Midflight's open question E-156 (do cancelled deliveries keep a 4.00 base fee or get a full refund?). `cancel` just prints the `refund` the API returns.

## 10. lead (answer): 4 turns

Tools: project_status x1, ToolSearch x1, resolve_escalation x1

I decided 1 escalation.

## 11. lead (change): 4 turns

Tools: project_status x1, propose_plan x1, approve_plan x1

Approved plan version 2.

## 12. t1 (p3): 3 turns

Tools: check_in x1, Bash x1

No code change was needed this round, so there's nothing new to commit. The grams version is already committed as a85ab53 on `t1-roost`, and the working tree is clean.
Midflight is now on plan v2 with no directives. T3 and T5 each say they treat `max_payload` values of 100 or more as grams, so the unit conflict is covered on their side. The lead still hasn't confirmed grams, and README and PLAN still say kg.

## 13. t2 (p3): 7 turns

Tools: check_in x1, acknowledge_directive x3, submit_claim x1, Bash x1

`POST /quote` now supports plan v2 express delivery. It takes `express` (default false) and returns `express_fee`, 50% of the delivery fee before promo. It's committed as 73d4863, and I haven't pushed.
Tax is 8% of (fee − promo + express). I did not apply your tax-on-full-fee note, because Midflight blocked it as a conflict with R-2 and plan v2 keeps the plan's rule. Midflight approved the revised claim (C-51 rev 3). Directive D-59 is acknowledged. If the lead rules for your reading, it's a one-line change.

Test run, harbor at 2.5 kg: 14.04 with no promo. With COOCOO and express it gives fee 13.00, discount 1.95, express 6.50, tax 1.40 and total 18.95.

## 14. t3 (p3): 8 turns

Tools: check_in x1, Bash x2, acknowledge_directive x3, submit_claim x1

Committed b0f5de7 with express delivery, but I haven't pushed, and I haven't run it (no `fastapi` here). Midflight put my claim on `human_review_required` because T4 and I disagree on the cancellation fee, and the lead has to settle that before I push.

**Your note conflicts with the lead.** You said to refund in full, but the lead ruled (E-156) that a cancellation keeps 25% of the total. I coded the lead's rule, so the refund is the total minus that fee, rounded half up. If you want full refunds, set `CANCEL_FEE_RATE` to 0 in `app/dispatch.py`. T4 assumed a fixed 4.00 fee instead, and Midflight flagged that.

**Other changes in this commit:**
- Deliveries and quotes now accept `express` (plan v2).
- Bird payload is read as grams, as the lead settled.
- `app.dispatch.deliveries` is exposed for T4's report.

## 15. t4 (p3): 10 turns

Tools: check_in x2, Edit x2, acknowledge_directive x3, submit_claim x1, Bash x1

`GET /report` in `app/billing.py` now counts a cancelled delivery as 25% of its total (rounded half up to the cent) in revenue, per the lead's ruling E-156. This replaces your 4.00 base fee, which conflicted with it. Revenue is confirmed totals plus those fees, with confirmed/cancelled counts and flights per bird for confirmed deliveries only.
Midflight approved claim C-54 rev 2 and says it's ready to push; it's committed as `dcd6826`. I haven't run it, because T3's dispatch code isn't there yet, and it assumes `app.dispatch.deliveries` is a dict of all deliveries, which T3 hasn't confirmed.

## 16. t5 (p3): 8 turns

Tools: check_in x1, acknowledge_directive x3, submit_claim x1, Bash x2

`quote` and `send` now take `--express`, and both print `express_fee:` right after `promo_discount:`. Both print `0.00` for a non-express parcel. This is R-8 from plan v2, committed on `t5-cli` as 7a9afca.
Midflight approved my revised claim C-55 against plan v2 and I acknowledged D-61. I have only checked that `quote --help` lists the new flag, because the API parts aren't merged yet. Midflight also flagged an open conflict between T4's and my assumptions about `report.flights`: whether cancelled deliveries are excluded. The lead has to decide it, and the CLI prints whatever `flights` the API returns.

## 17. t6 (p3): 14 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x2, Write x1

I added `GET /deliveries/{id}/tracking` in `app/tracking.py` and committed it on `t6-tracking`. It returns `delivery`, `status`, `bird` and `eta_minutes`. The ETA is distance / speed × 60, rounded half up, and 0 for a cancelled delivery. An unknown delivery gives a 404. I haven't run it or tested it, because T1 and T3 aren't merged yet.
I named the ETA field `eta_minutes`, not your `eta_min`. The PLAN.md contract and T5's CLI both use `eta_minutes`, and Midflight blocked my claim when I tried `eta_min`. If you still want `eta_min`, the lead has to change the contract. It also leans on two guesses about the others' code: `app.dispatch.deliveries` as a dict keyed by id, and `app.roost.BIRDS` and `app.roost.DESTINATIONS` as lists of dicts. Midflight approved the claim with those assumptions.

## 18. lead (answer): 3 turns

Tools: project_status x1, resolve_escalation x1

I decided 1 escalation.

## 19. t1 (p4): 2 turns

Tools: check_in x1

No code change was needed. Everything the other tasks expect from the roost matches what's already committed (a85ab53 on `t1-roost`): `BIRDS` and `DESTINATIONS` are importable lists of dicts, the endpoints return lists, unknown handles and codes give 404, and `max_payload` is in grams.
Midflight says ready to push, with no directives. T3 and T5 now both assume grams and convert themselves, but README and PLAN still say kg, so the lead should update them at merge.

## 20. t2 (p4): 3 turns

Tools: check_in x1, Bash x1

Midflight shows no new changes, so I made no code changes and committed nothing new. The last commit (73d4863) stands, the working tree is clean, and Midflight shows ready to push.
`app/pricing.py` serves `POST /quote` per plan v2: the delivery fee, the COOCOO promo (other codes give 400), `express_fee`, and tax on fee − promo + express, rounded half-up to the cent. T3's and T5's assumptions about my part match what I built.

The tax-on-full-fee change from your earlier note is not in the code, because Midflight blocked it as a conflict with the plan. It's a one-line change if the lead rules for it.

## 21. t4 (p4): 5 turns

Tools: check_in x1, submit_claim x1, acknowledge_directive x1, Bash x1

`GET /report` in `app/billing.py` needed no change this round, so there is no new commit; the last one is still `dcd6826`. It counts confirmed totals plus 25% of each cancelled delivery's total (half up to the cent) as revenue, with confirmed/cancelled counts and flights per bird for confirmed deliveries only. I haven't run it against T3's code.
The new directive D-65 repeated the lead's 25% fee ruling, so I acknowledged it and resubmitted the claim. Midflight approved C-54 rev 3, and T3 has confirmed that `app.dispatch.deliveries` is a dict of all deliveries. T3 must set the refund to total minus the same half-up fee, or the refund and my revenue figure will disagree.

## 22. t3 (p4): 4 turns

Tools: check_in x1, submit_claim x1, acknowledge_directive x1

The code needed no changes, so there is nothing new to commit. The latest commit, b0f5de7, already matches the lead's cancellation ruling (E-167), and my working tree is clean. I haven't pushed, and I never ran the code, since `fastapi` isn't installed here.

Midflight approved my revised claim C-52 (rev 4) and I acknowledged D-64. A cancel keeps 25% of the total, rounded half up, and refunds the rest. This overrides your earlier "refund in full" note, so if you want full refunds, set `CANCEL_FEE_RATE` to 0 in `app/dispatch.py`.

## 23. t5 (p4): 3 turns

Tools: check_in x1, Bash x1

Midflight shows no new changes for T5, so I made no code edits; the working tree is clean and the last commit is 7a9afca on `t5-cli`. My claim C-55 is approved and Midflight says it's ready to push.
`cli/pigeon.py` covers every README command plus `--express` with the `express_fee:` line. I never ran it against a live API, because the API parts weren't merged here.

## 24. t6 (p4): 2 turns

Tools: check_in x1

Midflight reports nothing new for T6, so I made no code changes and the existing commit (`ee55468` on `t6-tracking`) stands. My claim C-57 is still approved, and the settled decisions confirm my assumptions: `app.dispatch.deliveries` is a dict keyed by integer id, and `roost.BIRDS` and `roost.DESTINATIONS` are lists of dicts. The bird payload unit change to grams doesn't affect me, since I only use speed.
`GET /deliveries/{id}/tracking` returns `delivery`, `status`, `bird` and `eta_minutes`, with the ETA rounded half up, 0 once cancelled, and a 404 for an unknown delivery. I still used `eta_minutes` instead of your `eta_min`, because the contract and T5's CLI use that name. I haven't run it, because T1 and T3 aren't merged yet.
