# What each agent did and said in run A1

## 01. t1 (p1): 8 turns

Tools: Read x2, Bash x4, Write x1

I built `app/roost.py` with the four birds and four destinations, and the four GET routes (`/birds`, `/birds/{handle}`, `/destinations`, `/destinations/{code}`). Each route returns exactly the `bird` or `destination` contract fields, and an unknown handle or code gives a 404. I committed it on `t1-roost`. I didn't run the app or test the routes, and the chat was empty, so I posted nothing.

The module also has helpers other parts can import: `list_birds`, `get_bird`, `list_destinations` and `get_destination`. The two `get_` helpers return `None` for an unknown handle or code.

## 02. t2 (p1): 10 turns

Tools: Read x2, Bash x6, Write x1

I built `POST /quote` in `app/pricing.py` and committed it on `t2-pricing`. It follows R-2: fee, COOCOO 15% discount, 8% tax and total, with half-up rounding to the cent. I checked it through the app with a test client: harbor 2.5 kg with COOCOO gives a total of 11.93, downtown 0.5 kg gives 7.02, and a bad promo returns 400.

The roost isn't built yet, so I hardcoded the four README distances (swap to the roost at merge). An unknown destination returns 404 and a weight of 0 or less returns 400, which R-2 doesn't specify; I posted both choices in the team chat. Other parts can call `app.pricing.price(destination, weight_kg, promo)`.

## 03. t3 (p1): 9 turns

Tools: Read x2, Bash x5, Write x1

I built `app/dispatch.py` with POST /deliveries, GET /deliveries/{id}, POST /deliveries/{id}/cancel and GET /birds/{handle}/availability, and committed it on `t3-dispatch`. I haven't run it. The roost and pricing parts aren't built here yet, so it was only syntax-checked, and it will only work once their /birds, /destinations and /quote endpoints exist at merge.
- **Booking and flights:** It picks the smallest-payload bird that can carry the weight and has a flight left. It works out flights left from the confirmed deliveries, so cancelling gives the bird its flight back. Cancel refunds the full delivery total. The plan doesn't say what the refund should be, so I posted that assumption in the team chat.

## 04. t1 (p2): 5 turns

Tools: Bash x4

Every bird's `max_payload` in `app/roost.py` is now in grams (1000, 2000, 3000, 5000), committed on `t1-roost`. I didn't run the app or the routes.
PLAN.md and README.md say the field is in kg, so T3's weight check and T5's `max_payload=<kg>` output will be wrong unless they convert. I posted that to the team chat and asked the lead to say if it should go back to kg.

## 05. t3 (p2): 3 turns

Tools: Bash x2

The chat has nothing new for dispatch, and `app/dispatch.py` already refunds the full delivery total on cancel, so I made no code change and have nothing new to commit.
I posted a line in the team chat confirming the full refund, and the working tree is clean.

## 06. t2 (p2): 10 turns

Tools: Bash x5, Edit x1, PowerShell x3

Birdseed Tax is now 8% of the full delivery fee, before the promo discount, and I committed it on `t2-pricing`. For harbor at 2.5 kg with COOCOO, the tax is 1.04 and the total is 12.09.

This differs from PLAN R-2, which taxes the fee minus the discount, so results only differ when a promo is used. I posted that in the team chat and asked the lead to confirm. Dispatch's chat note says refunds equal the delivery total, so a cancelled promo order refunds the higher total.

## 07. t4 (p2): 8 turns

Tools: Read x2, Bash x4, Write x1

I built `GET /report` in `app/billing.py` and committed it on `t4-billing`. I couldn't run it because fastapi isn't installed here, so it's untested.
It reads deliveries from `GET /deliveries/1,2,…` and stops at the first 404. Revenue is the confirmed totals plus the 4.00 base fee for each cancelled delivery, and `flights` counts confirmed deliveries only.

I posted a note to the team chat asking T3 to keep delivery ids sequential from 1, because the plan has no endpoint that lists deliveries.

## 08. t5 (p2): 5 turns

Tools: Bash x3, Write x1

I built `cli/pigeon.py` with all nine commands from README's "The command line" section and committed it on `t5-cli`. It uses only the standard library, and `send` prints the quote before it posts the delivery.

I only checked an unknown command and an unreachable API, and both print `error: …` and exit 1. No API was running, so none of the real commands has been tried against live endpoints.

I posted on the team chat that the CLI divides `max_payload` by 1000 when it's 100 or more (T1 said the roost now reports grams) and leaves smaller values as kg.

## 09. lead (answer): 3 turns

Tools: Bash x2

I posted 4 answers.

## 10. t1 (p3): 3 turns

Tools: Bash x2

The lead ruled that payloads stay in kg, so I changed `max_payload` in `app/roost.py` back to 1, 2, 3 and 5 and committed it. I didn't run the app or the routes.
I posted the revert to the team chat. R-8 (express delivery) doesn't change the roost, and T5's CLI already handles either unit.

## 11. t2 (p3): 4 turns

Tools: Bash x3

Tax is back to 8% of (delivery fee − promo discount), as the lead ruled. `POST /quote` now takes `express` (default false) and returns `express_fee`, which is 50% of the delivery fee before promo and 0.00 when not express.
With express, tax is 8% of (fee − discount + express fee), and the total includes the express fee. Harbor at 2.5 kg with COOCOO and express gives a total of 18.95. It's committed and posted to the chat.

## 12. t3 (p3): 3 turns

Tools: Bash x2

Dispatch now accepts `express` (default false) on the delivery request and passes it to the quote, so the total includes the express fee. I committed it but haven't run it, because the roost and pricing endpoints it calls aren't merged yet.
Two instructions conflict on cancel refunds: my developer said refund in full, but the lead's chat message says keep a 25% cancellation fee. I kept the full refund and posted the conflict in the team chat, so the lead and my developer need to settle it. Switching to the fee is a one-line change.

## 13. t4 (p3): 3 turns

Tools: Bash x2

I didn't change `app/billing.py`, so there's nothing new to commit. I couldn't run the report this session because fastapi isn't installed here.
Cancelled deliveries still count a flat 4.00 base fee as revenue. That is what my developer told me, and it conflicts with the lead's chat message of a 25%-of-total cancellation fee. I posted the conflict to the chat. Switching to the lead's rule is a one-line change in `app/billing.py` once the lead and my developer settle it.

## 14. t5 (p3): 3 turns

Tools: Bash x2

I added R-8 express delivery to `cli/pigeon.py`: `quote` and `send` now accept `--express` and print an `express_fee:` line right after `promo_discount:`. I committed it and posted a note on the team chat.
I only checked argument parsing and the quote output lines locally. Nothing ran against a live API, so `--express` isn't tested end to end.

The lead's later messages put payloads back in kg. The CLI's kg/gram handling still prints the right value either way, so I left it.

## 15. t6 (p3): 8 turns

Tools: Read x2, Bash x4, Write x1

I built `GET /deliveries/{id}/tracking` in `app/tracking.py` and committed it on `t6-tracking`. It looks up the delivery, bird and destination through the app's own endpoints and returns ETA = distance / speed × 60 in whole minutes, rounded half up. A cancelled delivery gets ETA 0 and an unknown delivery gets 404. I haven't run the endpoint: the other parts aren't on my branch, so I only checked that the file imports.

The response has both `eta_min` (your developer's name) and `eta_minutes` (PLAN's `tracking` contract, which the CLI reads), with the same value. Your developer's `eta_min` alone would break the CLI. I posted this to the team chat for the lead to decide which name stays.

## 16. lead (answer): 3 turns

Tools: Bash x2

I posted 1 answer.

## 17. t1 (p4): 2 turns

Tools: Bash x1

Nothing new affects the roost; it's already committed and clean.

`app/roost.py` is final: the four birds (max payload in kg) and four destinations, served by the four GET routes with 404s for unknown handles or codes. The working tree is clean and nothing new in the chat touches my part. I haven't run the app or the routes.

## 18. t2 (p4): 2 turns

Tools: Bash x1

Nothing in the chat changes pricing, and the tree is clean and committed, so I made no edits.

`POST /quote` follows R-2 plus R-8: tax is 8% of (delivery fee − promo + express fee), and `express_fee` is in the response. Unknown destination returns 404; a bad promo or weight ≤ 0 returns 400.
One thing to settle at merge: destination distances are still a hardcoded copy of the README table, not read from the roost.

## 19. t3 (p4): 2 turns

Tools: Bash x1

The chat has nothing new that changes dispatch, so I made no changes and have nothing new to commit. Express and kg payloads are already in the last commit.
The lead hasn't settled the cancel refund. Dispatch still refunds 100%, as my developer told me, against the lead's 25% fee and billing's flat 4.00, so those three need aligning at merge.

## 20. t4 (p4): 2 turns

Tools: Bash x1

I made no changes this round, so there's nothing new to commit. `GET /report` is committed on `t4-billing`, and I never ran it because fastapi isn't installed here.
The chat has no answer yet on the cancellation fee. Billing still counts a flat 4.00 per cancelled delivery, as my developer told me, not the lead's 25% of total, and dispatch refunds 100%, so these three must be reconciled at merge.

## 21. t5 (p4): 2 turns

Tools: Bash x1

Nothing new affects the CLI, and the working tree is clean, so I made no changes and no new commit.

- The CLI still reads `eta_minutes`, which T6 returns alongside `eta_min`, and the cancel `refund` comes straight from the API (the 25%, 100% and 4.00 disagreement is for T3/T4 and the lead to settle).
- Everything is committed on `t5-cli`: all nine commands, `--promo` and `--express`, and the `express_fee:` line. None of it has been run against a live API.

## 22. t6 (p4): 3 turns

Tools: Bash x2

I changed the tracking response to the contract's field names only. It now returns `delivery`, `status`, `bird` and `eta_minutes`, with `eta_min` dropped. The lead ruled in chat that field names must match the contracts exactly, and that overrides your developer's `eta_min` request. I haven't run the endpoint, since the other parts aren't on my branch.

The change is committed on `t6-tracking`, and I posted the change to the team chat.

## 23. fixer (fix1): 4 turns

Tools: Bash x3

I changed cancellation to keep a 25% fee, rounded half up to the cent, and refund the rest. A cancelled delivery with a total of 11.88 now refunds 8.91. I haven't run the app or the CLI checks, so C9 and C11 are untested.
The report now counts each cancelled delivery's fee (total less refund) as revenue instead of the flat 4.00, which should give 24.03 for your example. The changes are in `app/dispatch.py` and `app/billing.py`, and they're committed.
