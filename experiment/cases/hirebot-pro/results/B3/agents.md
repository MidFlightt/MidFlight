# What each agent did and said in run B3

## 01. t1 (p1): 13 turns

Tools: Read x2, ToolSearch x1, check_in x3, Bash x3, submit_claim x2, Write x1

I built the catalog in `app/catalog.py` and committed it on `t1-catalog`. `GET /api/agents` lists the six README agents and accepts `?skill=`. `GET /api/agents/{handle}` returns one agent, or a 404 for an unknown handle.
A quick test client run returned 6 agents, `?skill=python` gave `intern-o-tron` and `overconfident-junior`, `rubber-duck` returned 200 and an unknown handle returned 404. Midflight approved the claim (C-2) and the last check-in said ready to push. I haven't pushed, and I didn't set up the pre-push hook.

I also added a `get_agent(handle)` function that other parts can import, and declared it as an assumption in the Midflight claim.

## 02. t2 (p1): 18 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x3, Bash x3, submit_claim x2, Write x2, PowerShell x1

I built `POST /api/quote` in `app/pricing.py` and committed it on `t2-pricing` as 587ebbe. I couldn't run it: the test run needed approval, so it's untested, and the catalog on my branch is still empty. By hand, 10h `meeting-ghost` + 25h `rubber-duck` with `BEEPBOOP` should give subtotal 2500, volume discount 100, promo 50, tax 188, total 2538.
It prices rules 1–6: 10% off any line of 20+ hours, `BEEPBOOP` takes 50 off, tax is 8% of the net, and everything rounds half up. It rejects unknown promo codes, unknown agents and bad hours with an error, and exposes `compute_quote()` for the bookings code to reuse. It needs T1's `catalog.get_agent(handle)` to return a dict with `hourly_rate`, or `None` for an unknown handle (my claim C-4 is approved, with that as an assumption).

## 03. t3 (p1): 20 turns

Tools: Read x5, Glob x1, ToolSearch x1, check_in x3, Bash x4, submit_claim x2, Write x2, PowerShell x1

I built the bookings API in `app/bookings.py` and committed it on `t3-bookings` (f349019). It has `POST /api/bookings`, `GET /api/bookings/{id}`, `POST /api/bookings/{id}/cancel` and `GET /api/agents/{handle}/availability`. A booking is priced through `compute_quote`. If any agent has too few hours left, it refuses the whole booking with a 409. Cancelling gives the hours back, and cancelling twice doesn't double-restore them.
I tested it only with stubbed `catalog.get_agent` and `pricing.compute_quote`, because the real catalog and pricing files are empty on my branch. It books, refuses an over-capacity booking, and restores hours on cancel. The state is in memory, in a `BOOKINGS` dict that T4 (reports) can read. My Midflight claim C-6 was approved, and the final check-in said ready to push. I haven't pushed.

## 04. t4 (p1): 14 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x2, Bash x2, submit_claim x2, Write x1

I built `GET /api/report` in `app/reports.py`. It returns `revenue`, `confirmed`, `cancelled` and `hours`. Revenue and per-agent hours count confirmed bookings only. It reads T3's `app.bookings.BOOKINGS` dict when called.
I tested it with stub bookings only, because T3's code isn't merged yet. I committed it on `t4-reports` (02426f1). The Midflight claim C-8 is approved and the last check-in said ready to push, but I haven't pushed.

## 05. t5 (p1): 16 turns

Tools: Read x2, ToolSearch x1, check_in x2, Bash x4, submit_claim x3, Write x1, PowerShell x2

I built all seven commands in `cli/hirebot.py` and committed them on `t5-cli` (a453d42). I haven't run it. The sandbox blocked every test command I tried, so nothing, not even the error paths, was exercised against the API or a stub.

The commands are `agents` (with `--skill`), `quote` and `book` (with `--promo`), `show`, `cancel`, `availability` and `report`. They use only the standard library, read `HIREBOT_URL` (default `http://127.0.0.1:8000`), and print exactly the README keys. Any error prints `error: <message>` and exits 1.

Midflight approved my T5 claim (C-11) and the last check-in said ready to push. The CLI depends on the other tasks' endpoints and response fields, as listed in my claim, so it needs a real run once everything is merged.

## 06. t1 (p2): 3 turns

Tools: check_in x1, submit_claim x1

Midflight moved to plan v2. The agent contract has the same five fields, and what T2, T3 and T5 assume of my part already matches the code. I changed nothing, so there was nothing new to commit. The existing commit `73589e5` on `t1-catalog` stands.

I re-filed my claim against plan v2 and it was approved (C-2, rev 2). Midflight says I'm ready to push, but I haven't pushed.

## 07. t2 (p2): 9 turns

Tools: check_in x2, acknowledge_directive x3, submit_claim x1, Bash x2

I updated `app/pricing.py` for plan v2 and committed it on `t2-pricing` as 5905159. I haven't run it, so it's untested. Midflight approved the revised claim and nothing is blocking the push.

- **Half hours:** `hours` can now be any multiple of 0.5, and each line cost rounds half up to whole credits.
- **Rush:** `POST /api/quote` and `compute_quote` take `rush`. The quote now includes `rush_fee`, which is 25% of the net, or 0 when it isn't a rush order. Tax is 8% of the net plus the rush fee, and the total includes the fee.

## 08. t3 (p2): 12 turns

Tools: check_in x2, submit_claim x1, acknowledge_directive x3, Bash x4, Write x1

The v2 bookings work is committed on `t3-bookings` (4e559f6), but I can't push yet. The lead has to settle a conflict over what happens to a booking's money when it's cancelled.

- **Built:** half-hour hours, `rush_fee` on bookings, and `available` as a number. Cancelling now marks the booking cancelled, gives the hours back and sets `refund` to the full `total`. A second cancel does nothing. I tested it with stubbed catalog and pricing, since those parts aren't merged here.
- **Blocked:** T4's agent says its developer wants a 20% cancellation fee that HireBot keeps. Your note says refund in full and keep nothing. Midflight raised this as E-20 and set my claim C-6 to human review, so the push is blocked until the lead decides. I haven't answered E-20 myself. If the lead picks the 20% fee, I only need to change the `refund` line in `cancel_booking` (`app/bookings.py`), and the stored `total` already stays unchanged for T4.

## 09. t4 (p2): 10 turns

Tools: check_in x1, submit_claim x1, acknowledge_directive x3, Edit x3, Bash x1

I did not add the 20% cancellation fee to revenue. Midflight flagged it as `human_review_required`, so it's waiting on the lead. T3's claim says cancelled bookings are refunded in full and HireBot earns nothing, which contradicts your note. Revenue still counts confirmed bookings only, and I can't push until the lead decides.
I did add half-hour support, so hours like 2.5 are summed and reported correctly. I checked it with a stub only, since T3's code isn't merged. It's committed as 51e177a on `t4-reports`.

## 10. t5 (p2): 12 turns

Tools: check_in x2, submit_claim x1, acknowledge_directive x3, Edit x4, Bash x1

I updated the CLI for plan v2 (half-hour hours, `--rush`, a `rush_fee:` line after `promo_discount:`) and committed it as 0cfe91d. Midflight shows claim C-11 rev 2 approved and ready to push.
I still haven't run it end to end (no API available here, and the sandbox blocked my earlier test runs). The only check was that `meeting-ghost=2.5`-style order lines parse. Escalation E-20, the cancellation-fee vs. full-refund conflict between T3 and T4, is waiting for the lead and doesn't touch my part.

## 11. t3 (say1791730275): 8 turns

Tools: check_in x2, Bash x3, submit_claim x1, acknowledge_directive x1

Cancelling a booking now keeps a 10% fee (rounded half up) and refunds the rest, as the lead ruled in E-20. I committed it on `t3-bookings` (dfc55b4), and Midflight approved the revised claim C-6 and says ready to push. The booking now also carries `cancellation_fee` and `refund`. I re-ran the stubbed test: a 100-credit booking cancels with a 10 fee and a 90 refund, and the hours come back. I haven't pushed.

T4's settled assumptions (E-24/E-25) still say HireBot keeps 20% on cancel, which contradicts the lead's 10% ruling (E-20). I flagged that to T4 in my claim, but the lead should confirm T4 switches, or the report's revenue will be off.

## 12. t4 (say1791730304): 7 turns

Tools: check_in x2, submit_claim x1, acknowledge_directive x1, Edit x1, Bash x1

Revenue in `GET /api/report` now includes the lead's cancellation fee: 10% of each cancelled booking's total, rounded half up. It adds that to confirmed totals. The earlier 20% from your note is gone.
I tested it with stub bookings only, since T3's code isn't merged: a confirmed 100 plus a cancelled 105 gave revenue 111. It's committed as 71eeb93 on `t4-reports`. Midflight claim C-8 rev 3 is approved and the check-in says ready to push; I haven't pushed.
