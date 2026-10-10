# What each agent did and said in run N1

## 01. t1 (p1): 7 turns

Tools: Read x2, Bash x3, Write x1

I built `GET /api/agents` in `app/catalog.py` and committed it on `t1-catalog`. It returns all six agents as a JSON list with `id`, `name`, `tagline` and `hourly_rate` in credits. I didn't run the endpoint, so it's untested.

For the team: ids are slugs like `intern-o-tron-3000` and `rubber-duck-pro`, and the rate field is `hourly_rate`. The storefront and hiring parts should use those exact names, and hiring should take the rate from this catalog.

## 02. t2 (p1): 10 turns

Tools: Read x4, Glob x1, Write x1, Bash x3

Committed on `t2-hiring`: `POST /api/hire` takes `{"items":[{"agent","hours"}]}` and returns the booking (id, line items, subtotal, 8% tax rounded half-up, total, in credits). `GET /api/bookings/{id}` returns it, with 404 for an unknown agent or booking. I tested both with a test client, but only `hiring.py` alone; I haven't run the merged app.
Team notes: `catalog.py` is empty, so I copied the hourly rates from the README into `hiring.py`. Agents are matched by name or slug (e.g. `meeting-ghost`), so the storefront should send one of those, and the rates need to match the catalog. Bookings are held in memory and are lost on restart.

## 03. t3 (p1): 9 turns

Tools: Read x5, Glob x1, Write x1, Bash x1

I built `web/index.html` and committed it on `t3-storefront`. It lists agents from `/api/agents` with hour inputs, shows a price summary with the 8% tax, hires via `POST /api/hire`, and shows the booking id and total. I haven't run it, because the other two APIs are still empty stubs here.

For the team: the README doesn't define the API shapes, so I guessed.
- **Agents:** I read `id`, `name`, `tagline` and `rate` from each agent, and also accept `hourly_rate`.
- **Hire:** I send `{"items":[{"agent_id":…,"hours":…}]}` and read `id` and `total` from the response.
- **Tax rounding:** the price summary is an estimate, and I round the tax to whole credits. The confirmation shows the server's total, so hiring's rounding should match or the two numbers will differ.

The team should agree on these shapes before merging.

## 04. t1 (p2): 1 turns

Tools: none

I made no changes and no new commit. The promo is a pricing and display change, and the catalog only lists agents and their hourly rates.

The work falls to the other two parts. Hiring needs to take 10% off the subtotal before the 8% AI Labor Tax and store the discount on the booking. The storefront needs to show the discount, and the code BEEPBOOP should be validated in hiring, not hardcoded in the page.

## 05. t3 (p2): 2 turns

Tools: Bash x1

The storefront now has a promo code field: BEEPBOOP takes 10% off the subtotal before tax, shown as its own discount line. The 8% tax line is calculated on the discounted subtotal, and the page and booking confirmation both show the discount. I haven't run it in a browser or against the real APIs. The change is committed, and the hourly rates were already shown before tax.

For the team: the page sends `promo_code` (uppercased, or null) in the `POST /api/hire` body and reads `discount` from the response, falling back to its own figure. Hiring must apply the same order (discount first, then 8% tax) and the same rounding to whole credits, or the totals will differ.

## 06. t2 (p2): 2 turns

Tools: Bash x1

`POST /api/hire` now takes an optional `promo_code`. `BEEPBOOP` takes 10% off the subtotal, and the booking carries `promo_code` and `discount`. An unknown code returns a 400. I tested with a test client only, and the commit is on `t2-hiring`.
Two things for the team:
- **Tax:** per your developer's note, no tax is added (`tax` is always 0, so `total = subtotal - discount`). This contradicts the README and the lead's "before tax" wording, so someone should confirm it and fix the README.
- **Page:** showing the discount on the page is the storefront's job. It needs to send `promo_code` and display `discount` from the response.

## 07. fixer (fix1): 15 turns

Tools: Bash x7, Edit x4, Write x1, PowerShell x2

The fixes are committed, and checks 5–8 now pass in an API-level test with your cart. I didn't load the page in a browser.
- **What was wrong:** the storefront sends `agent_id`, but hiring required `agent`. Hiring had also set tax to 0, but the README says checkout adds 8% AI Labor Tax. The fix, in `app/hiring.py`, accepts either field name, takes rates from the catalog, and adds the 8% after the discount.
- **Results:** with BEEPBOOP, the hire returned total 2,430 and discount 250, and `GET /api/bookings/{id}` returned 2,430. The same cart without the code returned 2,700.
