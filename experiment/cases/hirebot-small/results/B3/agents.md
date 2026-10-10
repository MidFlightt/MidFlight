# What each agent did and said in run B3

## 01. t1 (p1): 11 turns

Tools: Read x2, ToolSearch x1, check_in x2, Bash x2, submit_claim x1, Grep x1, Write x1

Checking in on where things stand: the work is finished and committed, so I'm just wrapping up.

- Built `GET /api/agents` in `app/catalog.py`. It returns the six README agents with `id` (slug), `name`, `tagline` and integer `hourly_rate`, matching the Midflight `agent-catalog` v1 contract. A test request returned 200 with 6 agents.
- Committed on `t1-catalog` as `47a936d`. Midflight approved claim C-3 and reported the task ready to push. I didn't push, and I didn't set up the pre-push hook.

One of the assumptions in my claim turned out wrong. `main.py` mounts the router with no prefix, so the route is defined as the full `/api/agents`. I didn't revise the claim, since the contract itself didn't change.

## 02. t2 (p1): 10 turns

Tools: Read x4, Glob x1, ToolSearch x1, check_in x1, Bash x1, submit_claim x1

I've stopped without writing any code. Midflight returned `human_review_required` on my claim C-4, and its rules say I shouldn't guess past that.

**The conflict:** the catalog is T1's part, and the README doesn't say what agent ids it will use. I need those ids to look up hourly rates. Midflight says my two claims contradict each other:
- **C-2 (withdrawn):** assumed I'd resolve agent ids with a rate table of my own inside `hiring.py`.
- **C-4 (blocked):** assumed T1's catalog will use the same ids as that table. These are lowercase slugs of the README names, such as `intern-o-tron-3000` and `rubber-duck-pro`.

**Decision for the lead:**
1. Fix the agent id format, for example the slugs above, and tell T1.
2. Say whether `hiring.py` should hardcode the README rates or read them from T1's catalog. The catalog is empty on my branch, so I can't import it.

Once the lead decides, I'll revise the claim and build `POST /api/hire` and `GET /api/bookings/{id}` in `app/hiring.py`, then commit. Nothing is committed yet, so there is no two-line summary.

## 03. t3 (p1): 7 turns

Tools: Read x1, ToolSearch x1, check_in x1, Bash x1, submit_claim x2

I stopped before writing any code, because Midflight's verdict on my T3 claim (C-6) was `human_review_required`. Nothing is built or committed, and `web/index.html` is unchanged.

**The conflict:** my claim has the storefront work out subtotal, 8% tax and total itself as a live preview. Claim C-4 (the hiring part) assumes tax is round-half-up of 8% of the subtotal. Midflight flags this as a blocking requirement conflict with R-2, which says customers see subtotal, tax and total in whole credits. It says your lead has to decide which side calculates the price.

**Options for the lead:**
1. **Server prices:** the storefront shows only the hourly rates and hours. Subtotal, tax and total come from the `/api/hire` booking response, so there is no live preview before checkout. This is the safest option.
2. **Local preview:** the storefront previews the price itself. That needs the lead to confirm the exact rounding rule (round-half-up to whole credits) so the preview matches what T2 charges.

Once the lead picks one, I'll revise the claim and build the page. The page will list agents from `GET /api/agents`, let customers set hours per agent, hire via `POST /api/hire`, and show the booking id and total. If you'd rather I start on the parts that don't touch pricing in the meantime, say so.

## 04. t2 (say1): 6 turns

Tools: check_in x2, Write x1, Bash x2

I built and committed the hiring part in `app/hiring.py` (commit 73ae440 on `t2-hiring`). `POST /api/hire` takes `items` of `{agent_id, hours}` and returns `booking_id`, `subtotal`, `tax` (8%, rounded half up) and `total` in whole credits. `GET /api/bookings/{id}` returns the stored booking.
I tested both endpoints with a test client, and a pre-push Midflight check-in said ready to push; I haven't pushed. Unknown agents and unknown booking ids return 404. Rates come from a table in `hiring.py` keyed by name slugs (e.g. `rubber-duck-pro`), so T1's catalog ids must match those slugs.

## 05. t3 (say1): 5 turns

Tools: check_in x2, Write x1, Bash x1

I built the storefront in `web/index.html` and committed it on `t3-storefront` (3a1798f). It lists agents from `/api/agents` with their hourly rates and takes hours per agent. It shows a live subtotal, 8% tax and total, hires via `/api/hire`, and shows the booking id and total.
I haven't run it against the real APIs, since the catalog and hiring parts aren't merged yet. It assumes `/api/agents` returns a plain array and `/api/hire` returns the booking at top level. The tax preview rounds half up. The final check-in said ready to push, and I haven't pushed.

## 06. t1 (p2): 4 turns

Tools: check_in x1, submit_claim x1, Bash x1

Midflight moved the plan to v2, but the `agent-catalog` fields are unchanged, so `app/catalog.py` needed no edit and I made no new commit. My work is still committed as `47a936d` on `t1-catalog`.
I revised claim C-3 against plan v2 with the corrected route assumption (`/api/agents` defined in full, since `main.py` adds no prefix), and Midflight approved it with no findings.

## 07. t2 (p2): 3 turns

Tools: check_in x1, submit_claim x1

I haven't changed or committed anything this round. Midflight returned `human_review_required` on my revised claim, so I've stopped.

**The conflict:** your note says the hourly rates already include the AI Labor Tax, so no tax gets added. Plan requirement R-2 and the README say checkout adds a separate 8% tax. R-2 is still in plan v2, and Midflight flagged the two as contradictory. The lead has to pick one:
- **Your note wins:** `tax` stays in the booking but is always 0, and `total = subtotal - discount`. R-2 and the README need updating to match.
- **R-2 wins:** `tax = 8%` of the discounted subtotal and `total = subtotal - discount + tax`, as the plan says.

**Plan v2 also adds a promo code (R-4):** `BEEPBOOP` takes 10% off the subtotal before tax. The booking gets a `discount` field and the request gets an optional `promo_code`. I haven't built this either, because the revised claim isn't approved. It doesn't depend on the tax decision, so once the lead rules, I'll build both in `app/hiring.py` and commit. The current commit (73ae440) is still the plan-v1 version with 8% tax and no promo.

## 08. t3 (p2): 5 turns

Tools: check_in x1, submit_claim x1, ToolSearch x1, acknowledge_directive x1

I haven't changed or committed anything this round. Midflight's verdict on my revised claim (C-6 rev 2) is `human_review_required`, so the pricing work is paused until your lead decides.

- **Plan v2 added a promo code:** BEEPBOOP takes 10% off the subtotal before tax. `/api/hire` now takes `promo_code` and returns a `discount` field, and the page and booking must show the discount. I acknowledged that directive (D-4).
- **The blocker:** Midflight says T2's claim (C-4) sets tax to 0 instead of adding the 8% AI Labor Tax that R-2 requires. My storefront shows whatever tax the booking returns. Building the summary and confirmation before the lead settles this could display wrong totals.
- **Your note:** the committed page already lists hourly rates before tax and shows the 8% tax as its own line, so that part needs no change. I'd add a discount line and a promo-code field when I build the v2 update.

Once the lead rules on the tax, I'll resubmit the claim and build the discount line and promo field.

## 09. t2 (say2): 12 turns

Tools: ToolSearch x1, check_in x2, acknowledge_directive x1, submit_claim x2, Edit x3, Bash x2

I followed the lead's ruling: rates are before tax, and the 8% AI Labor Tax is added at checkout as its own line. That overrides your earlier note that rates already include the tax. I committed it as 3328fc5 on `t2-hiring` and haven't pushed. Midflight approved the revised claim and said it's ready to push.

`POST /api/hire` now takes an optional `promo_code`. `BEEPBOOP` (any capitalisation) takes 10% off the subtotal, then tax is 8% of the discounted amount, and the booking returns `subtotal`, `discount`, `tax` and `total`. A test run with a 270-credit subtotal gave 27 discount, 19 tax and 262 total, and `GET /api/bookings/{id}` returned the same booking.

## 10. t3 (say2): 6 turns

Tools: ToolSearch x1, check_in x1, submit_claim x1, Bash x1, acknowledge_directive x1

I updated the storefront and committed it on `t3-storefront` (309d580). Hourly rates are labelled "before tax", and the summary now has subtotal, a discount line (shown when the promo applies), the 8% AI Labor Tax on its own line, and the total. There is also a promo code field: BEEPBOOP gives 10% off before tax, and `promo_code` is sent to `/api/hire`. The booking confirmation shows the discount too.
I haven't run it against the real APIs, and I haven't pushed. Midflight approved the revised claim (C-6 rev 3) and I acknowledged directive D-6 (the lead's decision on tax); I didn't run a check-in after committing.
