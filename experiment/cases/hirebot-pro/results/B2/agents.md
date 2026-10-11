# What each agent did and said in run B2

## 01. t1 (p1): 11 turns

Tools: Read x2, ToolSearch x1, check_in x3, Bash x2, submit_claim x1, Write x1

I built the catalog in `app/catalog.py`: `GET /api/agents` lists all 6 agents from the README, and `?skill=` filters them by exact, case-insensitive skill. `GET /api/agents/{handle}` returns one agent, or a 404 for an unknown handle. Each agent has `handle`, `name`, `skills`, `hourly_rate` and `weekly_capacity`, matching the Midflight `agent` contract (v5).
I checked it with a quick test client: 6 agents listed, 2 for `skill=python`, 200 for `lgtm` and 404 for an unknown handle. It's committed on `t1-catalog` as `09bb2c1`. Midflight approved the claim (C-27) and says it's ready to push. I haven't pushed, and I haven't run it through `app/main.py` or the pre-push hook, which I didn't set up.

## 02. t2 (p1): 13 turns

Tools: Read x3, Glob x1, ToolSearch x1, check_in x2, Bash x3, submit_claim x1, Write x1

I built `POST /api/quote` in `app/pricing.py` and committed it on `t2-pricing`. It takes `items` (each `{agent, hours}`) and an optional `promo_code`, and returns integer `subtotal`, `volume_discount`, `promo_discount`, `tax` and `total` under rules 1–6. A sample order (meeting-ghost 10h, rubber-duck 25h, `BEEPBOOP`) gave a total of 2538, which matches my hand calculation, and a bad promo code returned 400. I checked only those two requests, not unknown agents or non-positive hours.

Two choices of mine to flag:
- **Rates:** they are hardcoded from the README table, because I couldn't see T1's catalog interface. I declared this as an assumption to T1 in Midflight.
- **Errors:** an unknown agent, non-positive hours or a bad promo code returns HTTP 400. The promo discount is capped so the total can't go negative.

Midflight approved the claim (C-28) and `check_in` showed ready to push. I haven't pushed.

## 03. t3 (p1): 21 turns

Tools: Read x5, Glob x1, ToolSearch x1, check_in x3, Bash x5, submit_claim x3, Write x2

I built the bookings API in `app/bookings.py` and committed it on `t3-bookings` (c464e50). A local test booking, an over-capacity refusal and a cancel all behaved correctly, but I haven't run it against the other parts. Midflight approved the claim and the pre-push check-in says ready to push; I haven't pushed.
- **Endpoints:** `POST /api/bookings` books an order and refuses the whole booking with a 409 if any agent is short on hours. `GET /api/bookings/{id}` returns it, `POST /api/bookings/{id}/cancel` cancels it and gives the hours back, and `GET /api/agents/{handle}/availability` returns the hours left.
- **Dependencies:** It prices with `pricing.compute_quote(items, promo_code)` when that exists and uses its own copy of the pricing rules until then. Capacity comes from a copy of the README table rather than the catalog module, so merge-time wiring is still open.

## 04. t4 (p1): 13 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Write x1

I added `GET /api/report` in `app/reports.py` and committed it on `t4-reports`. I haven't run it, because `app/bookings.py` is still the empty starter file and there's no `BOOKINGS` data to test against.

The endpoint reads T3's `BOOKINGS` dict and returns `revenue`, `confirmed`, `cancelled` and `hours`. Revenue and hours count confirmed bookings only. Cancelled bookings only add to the `cancelled` count.

It depends on T3 providing `BOOKINGS` with items shaped `{agent, hours}`. Midflight approved my claim and says it's ready to push.

## 05. t5 (p1): 16 turns

Tools: Read x3, ToolSearch x1, Glob x1, check_in x2, Bash x3, submit_claim x1, Write x1, PowerShell x3

I built every README command in `cli/hirebot.py` using the standard library only. They are agents (with `--skill`), quote and book (with `--promo`), show, cancel, availability and report. Errors print `error: <message>` and exit 1, and the commit is on `t5-cli`.

I haven't run it: my smoke-test commands were blocked by permission prompts, and no API was running to test against. It's written against the T1–T4 contracts that Midflight approved (claim C-31), and the pre-push check-in said it's ready to push.

## 06. t1 (p2): 2 turns

Tools: check_in x1

Midflight moved the plan to v6, but the `agent` contract has the same five fields and types. The other tasks' assumptions about the catalog already hold, so I changed nothing and there's nothing new to commit:

- **Response shape:** `GET /api/agents[?skill=]` returns a JSON array of agent objects with `handle`, `hourly_rate` and `weekly_capacity`, as T5 expects.
- **Rates and capacity:** `hourly_rate` is in whole credits per hour. `weekly_capacity` is the static weekly total, and T3 tracks hours left itself.
- **Module data:** `app/catalog.py` exposes `AGENTS` (a list) and `AGENTS_BY_HANDLE` (keyed by handle) for T3 to read.

Claim C-27 is still approved and Midflight says ready to push. My work stays committed on `t1-catalog` as `09bb2c1`, and I haven't pushed.

## 07. t2 (p2): 9 turns

Tools: check_in x2, acknowledge_directive x3, submit_claim x1, Bash x2

I updated `POST /api/quote` in `app/pricing.py` for plan v6 and committed it as 307fb45 on `t2-pricing`. Midflight approved the revised claim (C-28 rev 2) and `check_in` shows ready to push, which I haven't done.
The quote now takes half-hour lines (multiples of 0.5, minimum 0.5) and an optional `rush` flag, and returns a `rush_fee` on top of the existing fields. Rush fee is 25% of the discounted amount, tax is 8% of that plus the fee, and both round half up. A sample order (meeting-ghost 2.5h, rubber-duck 25h, `BEEPBOOP`, rush) gave a total of 1653, which matches my hand calculation. Hours like 1.3 or 0 and a bad promo code each return 400.

Midflight shows T3 and T5 still describing the older `compute_quote(items, promo_code)` and a request body without `rush`. My version adds `rush` as an optional third argument (default `False`), so their calls still work. Midflight showed them my revised assumptions about `rush` and `rush_fee`.

## 08. t3 (p2): 16 turns

Tools: check_in x2, ToolSearch x1, acknowledge_directive x1, submit_claim x1, Bash x4, Write x3, PowerShell x2, Read x1

Bookings now support half-hour hours (e.g. 2.5, with availability returned as a number) and rush orders (`rush` flag, `rush_fee` in the booking). Cancelling gives the hours back and refunds the full total (`refunded` field, safe to repeat). It's committed on `t3-bookings` (60fc22d); my local test checked the rush maths and an over-capacity refusal, and Midflight shows ready to push.
Midflight's plan v6 added the half-hour and rush requirements, so I revised the claim and it was approved. `refunded` isn't in Midflight's booking contract; I listed it in my claim, so tell me if you'd rather drop it.

## 09. t4 (p2): 6 turns

Tools: ToolSearch x2, check_in x1, submit_claim x1, acknowledge_directive x1

I haven't built the 20% cancellation fee, so there's nothing new to commit. `app/reports.py` is unchanged since my last commit (52a6fa8), which already sums half-hour bookings correctly.
Midflight flagged your fee as contradicting T3's claim, which says cancelled bookings are refunded in full and earn nothing. The lead has to decide that, and I can't push until they do. Once they rule, the fee is a small change to revenue.

## 10. t5 (p2): 8 turns

Tools: ToolSearch x2, check_in x1, acknowledge_directive x1, submit_claim x1, Bash x2

I updated the CLI for plan v6 and committed it on `t5-cli`. Hours can now be multiples of 0.5, `--rush` works on quote and book, and `rush_fee:` prints right after `promo_discount:`. Fractional values like `2.5` print as is, and whole ones print without `.0`.

I haven't run it against a live API, and I can't push yet. Midflight set my revised claim (C-31 rev 2) to human_review_required, so the lead has to decide the open question (E-27). Two other agents' assumptions disagree: one expects a 20% cancellation fee on revenue, the other a full refund with nothing earned. It doesn't change the CLI's output keys.

## 11. t3 (say1791684574): 7 turns

Tools: ToolSearch x1, check_in x1, acknowledge_directive x1, Edit x1, submit_claim x1, Bash x1

Cancelling a booking now keeps a 10% cancellation fee (rounded half up) and refunds the rest, following the lead's decision (E-27). That replaces your earlier "refund in full" note. On a 1653-credit test booking the fee was 165 and the refund 1488, with hours given back. It's committed on `t3-bookings` (6be5b62), and Midflight approved the revised claim (C-29 rev 3); I didn't run the pre-push check-in or push.
A cancelled booking keeps its original `total` and gains `cancellation_fee` and `refunded` fields. These aren't in Midflight's booking contract, so I listed them in my claim for the reports task (T4) to see.

## 12. t4 (say1791684681): 7 turns

Tools: check_in x1, Edit x2, submit_claim x1, acknowledge_directive x1, Bash x1

`GET /api/report` now counts a 10% cancellation fee (rounded half up) on each cancelled booking as revenue, on top of confirmed totals. It's committed as 435e848 on `t4-reports`, and I haven't run it.
The lead's ruling (E-27) was 10%, not the 20% you gave me, so I used 10%. Midflight approved the revised claim, and `hours` still covers confirmed bookings only, half hours included.

## 13. t5 (say1791684733): 4 turns

Tools: check_in x1, acknowledge_directive x1, submit_claim x1

Nothing in the code needed to change, so there's nothing new to commit. The work is already committed at `8e1e319` on `t5-cli`.

The lead's decision (a 10% cancellation fee, counted as revenue) only adds fields to the cancel response. `cancel` still prints just `booking:` and `status: cancelled`, as the README says. Midflight has approved my revised claim (C-31 rev 3), and the pre-push check-in is clear. I haven't pushed.

I still haven't run the CLI against a live API, so that's the main remaining check.
