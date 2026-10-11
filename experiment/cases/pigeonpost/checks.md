# The 20 checks for PigeonPost (fixed before any trial)

`score.py` runs them automatically: it starts the merged app, types the customer
commands, and compares what they print. The reference build in `reference/` scores 20 of
20 (`python experiment/run.py pigeonpost X selftest`).

All commands are `python -m cli.pigeon ...`, run in this order against a fresh app. Money
matches to the cent.

Eight checks are a **plain build**: the plan alone is enough to pass them. The other
twelve each sit on a **mid-flight event**, something that happens after the plan was
written, and only pass if the news reached every part it concerns.

| # | Event | Command | Expected |
| --- | --- | --- | --- |
| C1 | plain build | `destinations` | four destinations with the README's distances |
| C2 | plain build | `quote harbor 2.5` | delivery_fee 13.00, promo_discount 0.00, tax 1.04, total 14.04 |
| C3 | plain build | `quote campus 1 --promo PIGEON` | an `error:` line, exit code 1 |
| C4 | plain build | `send downtown 1` | a delivery id, bird budget-bob, status confirmed, total 8.10 |
| C5 | plain build | `show <first id>` | bird budget-bob, status confirmed, total 8.10 |
| C6 | plain build | `availability budget-bob` | flights_left 1 |
| C7 | plain build | `send campus 0.5`, `send campus 1`, `availability budget-bob` | budget-bob (11.88), then express-edna (12.96) because budget-bob is out, then flights_left 0 |
| C8 | plain build | `cancel <second id>`, `show <second id>`, `availability budget-bob` | status cancelled both times, then flights_left 1 |
| C9 | two developers disagree | the `cancel` of C8 | refund 8.91 |
| C10 | nobody planned it | `report` | confirmed 2, cancelled 1, flights budget-bob=1 and express-edna=1 only |
| C11 | two developers disagree | the `report` of C10 | revenue 24.03 |
| C12 | a note against the plan | `quote harbor 2.5 --promo COOCOO` | delivery_fee 13.00, promo_discount 1.95, tax 0.88, total 11.93 |
| C13 | a note against the plan | `send harbor 1 --promo COOCOO`, `show <id>` | promo_discount 1.50, tax 0.68, total 9.18, and show says 9.18 |
| C14 | plan change | `quote harbor 2.5 --express` | delivery_fee 13.00, express_fee 6.50, tax 1.56, total 21.06 |
| C15 | plan change | `send harbor 0.5 --express`, `show <id>` | delivery_fee 9.00, express_fee 4.50, tax 1.08, total 14.58, and show says 14.58 |
| C16 | late joiner | `track <first id>`, `track <third id>` | budget-bob with eta_minutes 5, then express-edna with eta_minutes 8 |
| C17 | late joiner | `track <second id>` | status cancelled, eta_minutes 0 |
| C18 | a unit quietly changed | `birds` | max_payload 1, 2, 3, 5 (kg), with the fleet's speeds and flights |
| C19 | a unit quietly changed | `send airport 4` | bird cargo-carl, total 23.76 |
| C20 | a unit quietly changed | `send harbor 6` | an `error:` line, exit code 1, no delivery |

## The events, and what a miss looks like

| Event | What happens | Checks | If the news doesn't travel |
| --- | --- | --- | --- |
| Plan change | The lead adds express delivery. It concerns pricing, dispatch, and the command line. | C14, C15 | No express fee anywhere, or only in some parts |
| Two developers disagree | Dispatch's developer: refund a cancelled delivery in full. Billing's developer: keep the 4.00 base fee. The lead's decision is neither: a 25% fee (2.97 of 11.88). | C9, C11 | Refund 11.88 and revenue 25.06: nothing crashes, both numbers are wrong |
| A note against the plan | Pricing's developer wants tax before the promo discount. The plan says after, and the lead, if asked, says the plan stands. | C12, C13 | Tax 1.04 where the plan gives 0.88 |
| A unit quietly changed | The roost's developer wants max payloads in grams. | C18 to C20 | Every parcel "fits" the smallest bird, and a 6 kg parcel is accepted |
| Late joiner | Tracking starts two phases after everyone else, and its developer wants the field called `eta_min`; the contract says `eta_minutes`. | C16, C17 | `track` prints no ETA or fails |
| Nobody planned it | Billing needs every delivery. The plan says what a delivery looks like, not how billing gets them all. | C10 | An empty report |

Each event was checked against the reference build with only that event missed: it fails
exactly its own checks. One overlap: if billing can't read deliveries at all (C10), the
revenue in C11 is wrong too.

The checks marked "unit" run last, so a parcel that lands on the wrong bird there can't
disturb the earlier checks: every earlier parcel weighs 1 kg or less, which picks the
same bird whether payloads are in kg or grams.

After scoring at merge, a fixer agent gets each failing check (the command, what was
expected, and what it printed) and repairs; the checks run again after each round, up to
3 rounds. The number that matters is the first one, at merge: nobody hands a real team
the expected totals.
