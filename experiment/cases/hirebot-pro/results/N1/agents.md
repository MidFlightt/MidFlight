# What each agent did and said in run N1

## 01. t1 (p1): 8 turns

Tools: Read x2, Bash x4, Write x1

Built `app/catalog.py` with `GET /agents` (optional `?skill=`), `GET /agents/{handle}` (404 if unknown), the six README agents, and a `get_agent(handle)` helper. I tested it with FastAPI's test client and committed it on `t1-catalog`.

Tell the team: I chose the routes (`/agents`, `/agents/{handle}`) and the JSON fields (`handle`, `name`, `skills`, `rate`, `capacity`) myself, because the README doesn't define them. The CLI should call those routes and read those fields. Pricing and bookings can import `get_agent` from `app.catalog` for rates and capacity.

## 02. t2 (p1): 8 turns

Tools: Read x2, Bash x4, Write x1

I built `POST /quote` in `app/pricing.py` and committed it on `t2-pricing`. It takes `{"lines":[{"agent","hours"}], "promo"?}` and returns `subtotal`, `volume_discount`, `promo_discount`, `tax` and `total`. Unknown agents, hours of 0 or less, or a bad promo code return a 400. I checked one order by hand (meeting-ghost 10h, rubber-duck 25h, BEEPBOOP), which gave a total of 2538. I didn't run the HTTP endpoint.

Things the team should know:
- **Request format:** the README doesn't define it, so I chose the one above. The CLI and bookings need to send and read the same shape.
- **Rates:** the rates are hardcoded in `pricing.py` from the README table, because I can't import `catalog.py`. If catalog changes a rate, pricing won't follow.
- **Bookings:** `price_order(lines, promo)` can be imported to price an order directly, so bookings doesn't need to call the endpoint.
- **Rounding:** each line's discount and the tax are rounded half up separately.
- **Promo cap:** the promo discount is capped so the net amount never goes below 0. The README doesn't say what should happen in that case.

## 03. t3 (p1): 11 turns

Tools: Read x7, Glob x1, Write x1, Bash x1

I built the bookings API in `app/bookings.py` and committed it on `t3-bookings`. I tested it only with a short in-process script: a priced booking, a refused over-capacity booking, and a cancel that restored the hours.

The endpoints are `POST /bookings` (body `{lines:[{agent,hours}], promo}`), `GET /bookings/{id}`, `POST /bookings/{id}/cancel` (also `DELETE`), and `GET /agents/{handle}/availability`. An agent without enough hours left refuses the whole booking with a 409 and reserves nothing.

Things the team should know:
- **Duplicated data:** I couldn't import the other parts, so `bookings.py` has its own copy of the agent rates and capacities and its own pricing, promo code and rounding. Once the real pricing and catalog parts exist, these copies could be swapped for calls to them.
- **Reports:** `app.bookings.BOOKINGS` is a dict of booking id to booking. Each booking has `status`, `total`, and `hours` per agent. Reports can read it for rule 9.
- **Promo cap:** I cap the promo discount so an order can't go below zero. Pricing may handle that differently.
- **CLI mapping:** The CLI should read `booking: <id>` from `id`, and `status` and `total` from the same-named fields.
- **Errors:** Errors come back as `{"detail": ...}`: 400 for a bad agent, hours or promo, 404 for an unknown booking or agent, and 409 for not enough hours.

## 04. t4 (p1): 10 turns

Tools: Read x5, Glob x1, Grep x1, Write x1, Bash x1

I built `GET /report` in `app/reports.py` and committed it on `t4-reports`. It returns `revenue`, `confirmed`, `cancelled` and `hours` (a map of agent to hours, confirmed bookings only). I haven't run it: fastapi isn't installed here, so my quick check of `build_report` failed on import.

The team should know three things:
- **Bookings data:** I couldn't see the bookings part, so `app/reports.py` assumes `app.bookings` exposes `BOOKINGS` (a dict or list) or a `list_bookings()` function. Each booking needs `status`, `total` and `lines` (each line with `agent` and `hours`). If the bookings part names these differently, the report will come back empty until the names are aligned.
- **Revenue:** it counts only confirmed bookings, so a cancelled booking earns nothing. The README doesn't say this, so please confirm it.
- **CLI:** the `report` command should read `revenue`, `confirmed`, `cancelled` and `hours` from the JSON, then print one `hours: <handle>=<n>` line per agent.

## 05. t5 (p1): 9 turns

Tools: Read x3, Glob x1, Bash x3, Write x1

I built all seven commands in `cli/hirebot.py` and committed them on `t5-cli`. I only ran bad input, which prints `error: …` as intended. Nothing here was run against a live API.

**Team note:** README.md doesn't define the HTTP routes or JSON shapes, and the other parts are still empty stubs, so I guessed them. The guesses are:
- `GET /agents?skill=`
- `POST /quote` and `POST /bookings`, both with `{lines:[{agent,hours}], promo, promo_code}`
- `GET /bookings/{id}`
- `POST /bookings/{id}/cancel`
- `GET /agents/{handle}/availability`
- `GET /report`

The CLI accepts a few alternate key names in responses. When the parts merge, check these routes against the real ones; each is a one-line change in the `cmd_*` functions.

## 06. t1 (p2): 1 turns

Tools: none

I made no code changes, so there's nothing new to commit. `app/catalog.py` only holds each agent's handle, name, skills, rate and weekly capacity (whole numbers like 40). It doesn't handle hours or fees. Half-hour bookings and rush fees land in the pricing, bookings, reports and CLI parts.

Tell the team:
- **Bookings and reports:** track hours as numbers that can be fractional (for example 2.5), not integers. Compare against `capacity` from `get_agent`, and `capacity` from `get_agent` is still a whole number.
- **CLI:** parse `meeting-ghost=2.5` as a float, check it's a multiple of 0.5 and at least 0.5, and print `rush_fee:` right after `promo_discount:`.

## 07. t2 (p2): 2 turns

Tools: Bash x1

Both changes are in `app/pricing.py` and committed. I only ran `price_order` directly, not the HTTP endpoint.
- **Half hours:** hours must be a multiple of 0.5, so 0.3 returns a 400.
- **Rush:** `POST /quote` now accepts `"rush": true` and returns `rush_fee` (0 when not rush) between `promo_discount` and `tax`. The fee is 25% of the net amount, and tax is 8% of net plus rush fee. A test order with rush and a promo priced as expected.

The CLI should send `rush` in the request body and print `rush_fee:` after `promo_discount:`. Bookings and reports need to store and count half hours as decimals.

## 08. t3 (p2): 2 turns

Tools: Bash x1

Half-hour bookings, rush orders and full refunds on cancel are in `app/bookings.py` and committed on `t3-bookings`. A script run covered a 2.5-hour booking with rush and promo, a 1.3-hour request (refused with 400), a booking that used up the remaining capacity, and a cancel (hours came back, full refund). I didn't run it through the CLI.
- **Half hours and rush:** hours must be a multiple of 0.5 (at least 0.5), and capacity, hours left and the booking's `hours` are tracked and returned in half-hours. `POST /bookings` takes `rush: true`, and the response adds `rush_fee` (25% of the amount after discounts); tax is 8% of that amount plus the rush fee, and `total` includes both.
- **Team note on refunds:** cancelling sets `refunded` to the full `total`. Cancelled bookings still show their `total`, so Reports must count only `status == "confirmed"` bookings as revenue (and sum `hours` for those). The CLI should print `rush_fee:` right after `promo_discount:`, and the CLI quote path needs the same rush rule in Pricing.

## 09. t4 (p2): 2 turns

Tools: Bash x1

I updated `app/reports.py` and committed it on `t4-reports`; I haven't run it. Revenue now adds a 20% cancellation fee for each cancelled booking, rounded half up to whole credits, and the per-agent hours now handle half hours, showing whole numbers without a trailing `.0`.

Rush orders change only the booking `total` that I read, so nothing else changed here. The CLI `report` command needs no change for either update, but bookings must store half hours as numbers and not round them.

## 10. t5 (p2): 2 turns

Tools: Bash x1

Half-hour hours (`meeting-ghost=2.5`) and `--rush` on `quote` and `book` are in `cli/hirebot.py`, committed on `t5-cli`. I only ran input checks, because no API is running here. The checks confirmed that 0.3 is rejected with an error. The server-side rush and tax math is the API's job.
The CLI sends `"rush": true` in the order JSON, prints `rush_fee:` after `promo_discount:` (0 if the server omits it), and prints whole or half-hour numbers exactly as the server returns them. The pricing and bookings agents need to accept `rush` and fractional hours, and `rush_fee` has to appear in their responses.

## 11. fixer (fix1): 7 turns

Tools: Bash x4, Edit x2

The revenue report was charging a 20% cancellation fee instead of the lead's 10%. I changed `app/reports.py` to 10%. Your scenario should now give 432 + 10% of the cancelled booking's total = 686. I didn't re-run the scenario, so that figure comes from the arithmetic, not a run.

I also made `app/bookings.py` refund the total minus the 10% fee on cancel. It had been refunding in full, which contradicted the report. Both changes are committed.
