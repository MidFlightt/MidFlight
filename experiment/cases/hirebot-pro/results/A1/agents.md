# What each agent did and said in run A1

## 01. t1 (p1): 13 turns

Tools: Read x4, Bash x5, Write x1, Edit x2

I built the catalog in `app/catalog.py` and committed it on `t1-catalog`. `GET /agents` lists the six agents with `handle`, `name`, `skills`, `rate` and `weekly_capacity`, and `?skill=python` filters them. `GET /agents/{handle}` returns one agent, or a 404 for an unknown handle.
I checked these with a test client. I also exposed `catalog.AGENTS` and `catalog.get_agent(handle)` for the other parts, and noted the endpoints and key names in `TEAM_CHAT.md`.

## 02. t2 (p1): 19 turns

Tools: Read x9, Glob x1, Write x1, Bash x4, Edit x3

I built `POST /quote` in `app/pricing.py` and committed it on `t2-pricing`. It takes `{"lines":[{"agent","hours"}],"promo"}` and returns subtotal, volume discount, promo discount, tax and total. Unknown agents, bad hours and bad promo codes return HTTP 400.
I only ran one order through it: `meeting-ghost` 10 hours plus `rubber-duck` 25 hours with `BEEPBOOP` gave a total of 2538, which matches my hand calculation. I also confirmed a bad promo code returns 400. I posted the interface to `TEAM_CHAT.md`, along with `price_order(lines, promo)` for bookings to call. I hardcoded the agent rates from the README rather than reading them from the catalog.

## 03. t3 (p1): 25 turns

Tools: Read x9, Glob x1, Write x2, Bash x5, PowerShell x3, Edit x4

I built the bookings API in `app/bookings.py` and committed it on `t3-bookings`. It hasn't been run: my test runs were blocked by the sandbox, so the code is untested.

- **What it does:** `POST /bookings` prices the order and reserves hours, refusing the whole booking with a 409 if any agent is short. `GET /bookings/{id}` shows a booking, `POST /bookings/{id}/cancel` cancels it and returns the hours (cancelling twice is harmless), and `GET /agents/{handle}/availability` gives the hours left. It also has `list_bookings()` for reports.
- **Pricing:** I copied the agent rates, capacities and pricing rules into the file instead of importing `catalog` or `pricing`, so it doesn't depend on the other parts. Worked by hand, 10 hours of `meeting-ghost` plus 25 of `rubber-duck` with `BEEPBOOP` should total 2538 credits.
- **Team chat:** I posted the routes and response fields. I also told catalog not to add its own availability route, since mine already exists.

## 04. t4 (p1): 15 turns

Tools: Read x6, Glob x1, Write x1, Bash x3, Edit x1, PowerShell x2

I added `GET /report` in `app/reports.py` and committed it on `t4-reports`. It returns `{revenue, confirmed, cancelled, hours:{handle:n}}`. Revenue and hours count confirmed bookings only. I haven't run it.
It depends on bookings exposing `app.bookings.list_bookings()`. Each booking needs `status`, `total` and `lines` (`agent` and `hours`). I couldn't see the bookings code, so I posted that contract in TEAM_CHAT.md.

## 05. t5 (p1): 18 turns

Tools: Read x5, Bash x8, Write x1, Edit x3

I built all seven commands in `cli/hirebot.py` and committed them on `t5-cli` (2a9a592). They print the README keys, use only the standard library, and print `error: <message>` and exit 1 on failure. I couldn't test them against a live API, so only argument validation and the unreachable-server error were run.
I assumed REST routes for bookings and availability (`POST /bookings`, `GET /bookings/{id}`, `POST /bookings/{id}/cancel`, `GET /agents/{handle}/availability`). I posted those assumptions to TEAM_CHAT.md. The catalog, pricing and reports routes match what those parts posted there.

## 06. t1 (p2): 3 turns

Tools: Read x1, Edit x1

Neither change touches the catalog, so I made no code change and no new commit. The catalog only lists agents with whole-number rates and capacities, and `weekly_capacity` can still be compared against half-hour amounts.
I left a note in `TEAM_CHAT.md` that pricing, bookings, reports and the command line need to handle 0.5-hour values and `rush_fee`.

## 07. t2 (p2): 6 turns

Tools: Bash x2, Edit x2, Read x1

`/quote` now takes hours in multiples of 0.5 (anything else returns 400) and an optional `rush` flag, and the response has a new `rush_fee` (0 when not rush). The fee is 25% of subtotal minus volume and promo discounts, and tax is 8% of that amount plus the fee. I committed this on `t2-pricing`.
I checked `meeting-ghost` 2.5 hours: 375 normally (405 with tax), and with rush the fee is 94, tax 38 and total 507. I told the team in `TEAM_CHAT.md` that bookings must pass `rush` through to `price_order(lines, promo, rush)` and return `rush_fee`.

## 08. t3 (p2): 9 turns

Tools: Read x3, Bash x2, Edit x3

Both changes are committed on `t3-bookings`, but I haven't run any of it. Earlier test runs were blocked by the sandbox, so the new code is untested.

- **Changes:** Bookings now take hours in multiples of 0.5 (0.5 minimum) and a `rush` flag. Rush adds a 25% fee, tax is 8% of the amount plus the fee, and responses include `rush_fee`. Capacity and hours left count half hours.
- **Cancellation conflict:** Following the developer's note, cancelling sets `refund` equal to the full total. That conflicts with reports, which keeps 20% of a cancelled booking's total as revenue. I flagged this in the team chat, and the lead needs to decide before launch.

## 09. t4 (p2): 6 turns

Tools: Edit x3, Bash x2

`app/reports.py` now keeps hours as fractional numbers, so half hours add up correctly in the per-agent hours. Revenue is now confirmed totals plus a 20% fee on each cancelled booking's total, rounded half up. The change is committed on `t4-reports`. I haven't run it.
Rush orders need no change here, since the report uses each booking's stored total. Bookings has to keep fractional hours and a cancelled booking's total, and I posted that in TEAM_CHAT.md.

## 10. t5 (p2): 8 turns

Tools: Bash x4, Edit x2, Read x1

`quote` and `book` now accept half-hour lines (like `meeting-ghost=2.5`) and `--rush`, and the commit is on `t5-cli` (0d29b80). Hours must be a multiple of 0.5, at least 0.5, and are sent as numbers. `--rush` sends `"rush": true`, and `rush_fee:` prints right after `promo_discount:`.
I couldn't test against a live API; only the hours validation was run. `book` falls back to `/quote` if the bookings response omits `rush_fee`, and I asked bookings in TEAM_CHAT.md to return it.

## 11. t3 (say1791591629): 6 turns

Tools: Read x2, Bash x1, Edit x2

Cancelling a booking now keeps a 10% cancellation fee, as the lead decided. I haven't run it, because the sandbox blocked test runs earlier. The change is committed on `t3-bookings`.
The cancelled booking keeps its `total` and gains `cancellation_fee` (10% of the total, rounded half up) and `refund` (total minus the fee). Reports has already switched to the 10% rule, and I left a line in the team chat.

## 12. t4 (say1791591629): 5 turns

Tools: Read x1, Edit x2, Bash x1

Following the lead's decision, I changed the report's cancellation fee from 20% to 10% of a cancelled booking's total, rounded half up. Revenue is now confirmed totals plus that fee, committed on `t4-reports` and not run.
It relies on bookings keeping `total` on cancelled bookings, which they confirmed in the chat. I added a line to TEAM_CHAT.md saying the 20% is superseded.
