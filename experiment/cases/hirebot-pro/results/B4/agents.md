# What each agent did and said in run B4

## 01. t1 (p1): 11 turns

Tools: Read x2, ToolSearch x1, check_in x3, Bash x2, submit_claim x1, Write x1

I built the catalog in `app/catalog.py`. `GET /api/agents` lists the six README agents, with an optional `?skill=` filter. `GET /api/agents/{handle}` returns one agent, or a 404 for an unknown handle.
Each agent has `handle`, `name`, `skills`, `hourly_rate` and `weekly_capacity`, matching the Midflight contract. I checked the list, the skill filter, the single lookup and the 404 with a test client. Midflight approved the claim, and the work is committed on `t1-catalog` as 8547774, not yet pushed.

I didn't set up Midflight's pre-push hook (`hook_setup`) and didn't push.

## 02. t2 (p1): 10 turns

Tools: Read x2, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Write x1

I've committed the pricing API on branch `t2-pricing`: `POST /api/quote` prices an order by rules 1–6 and returns subtotal, volume discount, promo discount, tax and total. Unknown agents, non-positive hours and bad promo codes return HTTP 400.
I only ran the pricing function once, on the CLI example order with `BEEPBOOP`: it gave 2500 / 100 / 50 / 188 / 2538. I haven't started the server or tested the HTTP endpoint. Midflight claim C-2 is approved and `check_in` says ready to push, but I haven't pushed.

One thing to know: the catalog (T1) has no endpoints yet, so pricing keeps its own copy of the README rate table. If T1's rates differ from the README, the quotes will be wrong. I listed this as an assumption in my claim.

## 03. t3 (p1): 21 turns

Tools: Read x5, Glob x1, ToolSearch x1, check_in x2, Bash x3, submit_claim x1, Write x2, PowerShell x4, Edit x1

I built the bookings API in `app/bookings.py` and committed it on `t3-bookings` (c285ac3). I haven't run it: my test script needed approval, so the code is untested.
- **Endpoints:** `POST /api/bookings`, `GET /api/bookings/{id}`, `POST /api/bookings/{id}/cancel` and `GET /api/agents/{handle}/availability`. A booking reserves hours per agent and refuses the whole order with 409 if any agent is short, and cancelling gives the hours back (twice is harmless). Errors return 400 or 404 with `{detail}`.
- **Assumptions to check at merge:** pricing comes from T2's `price_order(items, promo_code)`, which doesn't exist yet in this branch. Weekly capacities are hardcoded from the README table, and bookings are held in memory. Midflight approved claim C-3, and its last check-in said ready to push.

## 04. t4 (p1): 13 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Write x1

I built `GET /api/report` in `app/reports.py` and committed it on `t4-reports` (73cc8a8). I haven't run it, because the bookings part isn't merged yet.

The endpoint returns `revenue` (the sum of totals of confirmed bookings), `confirmed` and `cancelled` counts, and `hours` per agent for confirmed bookings only. It reads the `BOOKINGS` dict in `app/bookings.py`, which T3 has agreed to provide. Midflight approved the claim and shows it ready to push.

## 05. t5 (p1): 14 turns

Tools: Read x1, ToolSearch x1, check_in x2, Bash x6, submit_claim x2, Write x1

I built all seven commands (`agents`, `quote`, `book`, `show`, `cancel`, `availability`, `report`) in `cli/hirebot.py`, using only the standard library, and committed them on `t5-cli`. Each prints the README keys and exits 0, and any error prints `error: <message>` and exits 1.
Against the other agents' API parts I only tested the error paths: a missing order line and an unreachable server both print `error:` and exit 1. The success paths are untested, because none of the API parts exist on my branch yet. I also didn't push; Midflight's pre-push check-in said ready, and my claim C-6 is approved.

## 06. t1 (p2): 3 turns

Tools: check_in x1, submit_claim x1

The check-in needed no changes to `app/catalog.py`, so I made no new commit. The v1 commit (8547774) already matches what the other tasks expect.

The v2 `agent` contract has the same fields. T5 expects `GET /api/agents?skill=X` to return an unwrapped JSON array, which it does. T2 and T3 keep their own copies of the README rates and capacities, and those match the catalog.

I revised my claim to plan v2 (C-1 rev 2), and Midflight approved it. Nothing is pushed.

## 07. t2 (p2): 6 turns

Tools: check_in x1, ToolSearch x1, acknowledge_directive x1, submit_claim x1, Bash x1

Pricing is updated for plan v2 and committed on `t2-pricing` (052f79f): `POST /api/quote` now accepts half-hour `hours` (multiples of 0.5) and a `rush` flag, and returns `rush_fee` between `promo_discount` and `tax`. I tested `price_order` directly on a sample order (rush with promo, and plain) and it gave the expected numbers. I haven't called the HTTP endpoint, and I haven't re-run `check_in` or pushed.

Midflight: I acknowledged directive D-1 and resubmitted claim C-2 against plan v2, which was approved.

## 08. t3 (p2): 13 turns

Tools: check_in x2, acknowledge_directive x3, submit_claim x1, Edit x5, Bash x1

I updated `app/bookings.py` for plan v2 and the full-refund note, and committed it as c310a84 on `t3-bookings`. I haven't run it, because my test run needed approval. Midflight approved claim C-3 rev 2 and says the branch is ready to push.
- **Plan v2:** bookings now take half-hour amounts, pass `rush` through to pricing, and include `rush_fee`. Availability is a number.
- **Refund:** cancelling gives the hours back and adds a `refund` field equal to the booking total, which isn't in the booking contract. T4's report should count revenue from confirmed bookings only.

## 09. t4 (p2): 8 turns

Tools: check_in x1, submit_claim x1, acknowledge_directive x3, Edit x1, Bash x1

I committed half-hour support in the report, but not the 20% cancellation fee, so I can't push yet.

- **Half hours:** the report now counts half-hour bookings, with whole numbers kept as ints (commit 02a7e06).
- **Cancellation fee on hold:** your 20% fee contradicts T3's assumption that cancelled bookings are refunded in full. Midflight flagged it as `human_review_required`, so the lead has to decide. Revenue still counts confirmed bookings only, and I can add the fee once the lead rules.

## 10. t5 (p2): 8 turns

Tools: check_in x2, ToolSearch x1, acknowledge_directive x1, submit_claim x1, Bash x2

The CLI now follows plan v2: half-hour hours like `meeting-ghost=2.5`, `--rush` on `quote` and `book`, and a `rush_fee:` line right after `promo_discount:`. It's committed on `t5-cli`, not pushed, and my revised Midflight claim (C-6 rev 2) is approved.
I tested only the argument parsing, not against a running API. Escalation E-20 (whether a cancelled booking keeps a fee or is refunded in full) is open for the lead; it affects the report, not my commands.

## 11. t3 (say1791729812): 6 turns

Tools: check_in x1, Edit x1, submit_claim x1, acknowledge_directive x1, Bash x1

Cancelling a booking now keeps a 10% fee, rounded half up, and refunds the rest. I committed it as 4af80d6 on `t3-bookings`. The lead's ruling replaces your full-refund note, and Midflight approved claim C-3 rev 3. I haven't run the code.
- **Cancel response:** a cancelled booking gets integer `cancellation_fee` and `refund` fields, and `total` is unchanged. T4's report must count the fee as revenue. T4 had assumed 20%, and I named that mismatch in my claim.

## 12. t4 (say1791729831): 7 turns

Tools: check_in x2, submit_claim x1, acknowledge_directive x1, Edit x1, Bash x1

The report now counts the lead's 10% cancellation fee as revenue (not your 20%). It's committed on `t4-reports` (b310af9), and I haven't run it.
Revenue is the totals of confirmed bookings plus a fee of (total+5)//10 for each cancelled booking, or the booking's `cancellation_fee` if T3 provides one. Midflight approved the revised claim and shows it ready to push.
