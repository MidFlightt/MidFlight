# What each agent did and said in run A1

## 01. t1 (p1): 9 turns

Tools: Read x4, Write x1, Bash x2, Edit x1

I built `GET /api/agents` in `app/catalog.py`. It returns all six agents from the README as a JSON list, each with `id`, `name`, `tagline` and `hourly_rate` in whole credits. I committed it on `t1-catalog` but haven't run the server or called the endpoint.
The `id` is a slug (for example `rubber-duck-pro`), and I posted that field naming in `TEAM_CHAT.md` so the other two parts can match it.

## 02. t2 (p1): 15 turns

Tools: Read x6, Glob x1, Write x1, Bash x4, Edit x2

I built `POST /api/hire` and `GET /api/bookings/{id}` in `app/hiring.py` and committed them on `t2-hiring` (11d7a75). `POST /api/hire` takes `{"items":[{"agent_id","hours"}]}` and returns the booking id, line items, subtotal, 8% tax (rounded to whole credits, half up) and total. `GET /api/bookings/{id}` returns the stored booking, and unknown agents or bookings give a 404.
I hardcoded the README hourly rates because the catalog is empty on my branch. I tested only the hiring router on its own, with one two-agent booking (total 529 credits) and the 404 for an unknown agent. The full app wasn't run because `main.py` needs a `web/` folder that isn't on my branch. Bookings are kept in memory and are lost on restart. I left a note for the team in `TEAM_CHAT.md`; the catalog agent's slug ids match mine.

## 03. t3 (p1): 20 turns

Tools: Read x7, Glob x2, Write x1, Bash x3, PowerShell x2, Edit x4

I built `web/index.html` and committed it on `t3-storefront`. It lists the agents from `/api/agents` with hourly rates and has an hours input per agent. It shows a live summary (subtotal, 8% AI Labor Tax rounded half up to whole credits, total) and posts to `/api/hire`. After a hire it shows the booking id and the server's total.
I wrote it to the field names the catalog and hiring agents posted in TEAM_CHAT.md, but I haven't run it against the real API, since the branches aren't merged.

## 04. t1 (p2): 4 turns

Tools: Read x1, Bash x1, Edit x1

I changed no code and made no new commit. The BEEPBOOP promo is about pricing and the booking, and the catalog only lists agents and their rates, which haven't changed.
I added a note to `TEAM_CHAT.md` that the discount belongs in hiring (10% off the subtotal, before tax, with a discount field on the booking) and in the storefront display. I also suggested those two parts agree on the rounding and the field name.

## 05. t2 (p2): 4 turns

Tools: Bash x2, Edit x1

Committed on `t2-hiring` (51920e6). `POST /api/hire` now takes an optional `promo_code`: BEEPBOOP gives 10% off the subtotal in whole credits, and any other code returns a 400. The booking shows `promo_code` and `discount`, and `total` is the subtotal minus the discount.
Following your developer's note, no tax is added: the booking has `tax: 0` and `tax_included: true`, which contradicts the README's "checkout adds 8%". The page display belongs to the storefront part, so I left a note in `TEAM_CHAT.md` asking them to drop the 8% from the estimate and show a discount line. I tested the router on its own: BEEPBOOP on 450 credits gives a 45 discount and a 405 total, and no code gives 450.

## 06. t3 (p2): 15 turns

Tools: Read x3, Edit x10, Bash x1

I added the BEEPBOOP promo to `web/index.html` and committed it as `c6df7b1`. The page has a promo code box, a 10% discount line (rounded half up, taken before tax), rates labelled "before tax", and the 8% tax as its own line. The booking confirmation shows the server's subtotal, discount, tax and total, and I haven't run it against the real API.
**Conflict:** The hiring agent says your developer told them rates already include the tax, so their API adds none (`tax: 0`). Your developer's note to me says the opposite, and I followed mine. Until the lead and developer settle it, the page's estimated total won't match the server's total. I posted this in TEAM_CHAT.md.

## 07. t3 (say1): 4 turns

Tools: Read x1, Edit x1, Bash x1

The lead's decision is rates before tax with the 8% tax as its own line. That's what the page already does, so I changed no code and made no new commit; the last commit is still `c6df7b1`.
I posted a note in TEAM_CHAT.md asking hiring to return tax as 8% of (subtotal − discount) and total as subtotal − discount + tax. I haven't tested the page against the real API.

## 08. t2 (say1): 7 turns

Tools: Read x2, Bash x2, Edit x2

I followed the lead's decision: hourly rates are before tax, and the 8% AI Labor Tax is added at checkout. Tax is 8% of (subtotal − discount), rounded to whole credits (half up), returned as `booking.tax`, and `total` is subtotal − discount + tax. I removed `tax_included`. This is committed on `t2-hiring` (c4ec932).
I tested the router on its own: 450 credits with BEEPBOOP gives discount 45, tax 32 and total 437, and 450 without a promo gives tax 36 and total 486. The storefront's page already does the same math, and I posted a note in `TEAM_CHAT.md`.
