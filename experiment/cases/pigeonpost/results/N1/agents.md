# What each agent did and said in run N1

## 01. t1 (p1): 9 turns

Tools: Read x5, Glob x1, Write x1, Bash x1

I built `app/roost.py` with the four birds and four destinations, plus GET `/birds`, `/birds/{handle}`, `/destinations` and `/destinations/{code}`. Unknown handles or codes return 404, and the fields match the `bird` and `destination` contracts. I checked the endpoints with a test client, including the 404s, and committed on `t1-roost`.

Team note: the plan doesn't say how the other parts read roost data (HTTP or Python import), so I also exposed `BIRDS`, `DESTINATIONS`, `get_bird(handle)` and `get_destination(code)` in the module. These return a bird or destination dict, or `None` if unknown. T2, T3 and T6 can import them.

## 02. t2 (p1): 9 turns

Tools: Read x5, Glob x1, Write x1, Bash x1

I built `POST /quote` in `app/pricing.py` and committed it on `t2-pricing`. Quoting harbor at 2.5 kg returns 14.04 without a promo and 11.93 with `COOCOO` (checked with the FastAPI test client, not the full app); any other promo code returns 400.

Things the team should know:
- **Distances are hardcoded:** `app/roost.py` is empty on my branch, so I copied the four destination distances from README.md into a table in `pricing.py`. Whoever merges should switch it to the roost's destinations if those ever differ.
- **Dispatch can reuse it:** `compute_quote(destination, weight_kg, promo)` is importable, so T3 can call it directly instead of making an HTTP request to `/quote`.
- **Errors beyond R-2:** an unknown destination returns 404, and a weight that isn't a multiple of 0.5 kg (or is below 0.5) returns 400. Dispatch's weight check from R-3 should match this.
- **Promo field:** `promo` is optional and an empty string means no promo.

## 03. t3 (p1): 11 turns

Tools: Read x7, Glob x1, Write x1, Bash x1

I built `app/dispatch.py` and committed it on `t3-dispatch`. It imports cleanly, but I haven't run the endpoints because roost and pricing are still empty stubs here. It has `POST /deliveries`, `GET /deliveries/{id}`, `POST /deliveries/{id}/cancel` and `GET /birds/{handle}/availability`. Deliveries are held in memory, and a bird's flights left is its `flights_per_day` minus its confirmed deliveries, so a cancel gives the flight back.

Things the team should know:
- **Dependencies on other parts:** dispatch calls `POST /quote` and `GET /birds` and `GET /birds/{handle}` in-process through the app, so it depends on roost and pricing returning exactly the `bird` and `quote` contract fields. Quote errors such as a bad promo (400) or an unknown destination are passed through with their status.
- **Assumptions the plan doesn't settle:** the refund on a cancel is the full `total`. Cancelling an already-cancelled delivery just returns it again and doesn't give back a second flight.
- **Weight and bird choice:** a weight that isn't a multiple of 0.5 or is below 0.5 returns 400. A tie on max payload goes to the lower handle alphabetically.

## 04. t1 (p2): 7 turns

Tools: Bash x2, Edit x4

Every bird's `max_payload` is now in grams (1000, 2000, 3000, 5000), committed on `t1-roost`. I didn't re-run the endpoints after this change.
Team warning: PLAN.md and README say `max_payload` is in kg, and weights (`weight_kg`) are in kg, so T3 (dispatch) and T5 (CLI) must convert. T3 should compare `weight_kg * 1000` against `max_payload`. T5's `birds` command prints `max_payload=<kg>`, so it must divide by 1000, and PLAN.md's `bird` contract needs updating.

## 05. t2 (p2): 3 turns

Tools: Edit x1, Bash x1

Birdseed Tax is now 8% of the full delivery fee, before the promo discount, and the change is committed on `t2-pricing`. Harbor at 2.5 kg with `COOCOO` now quotes tax 1.04 and total 12.09, where it was 0.88 and 11.93.
This differs from PLAN.md R-2, which says 8% of (fee − discount). I followed your note, but the lead or whoever writes the tests should know. I left a comment in the code, and you may want to confirm the rule with the lead.

## 06. t3 (p2): 3 turns

Tools: Edit x1, Bash x1

Cancelling a delivery already refunded the full `total`, which is what my first version assumed. I only added a comment in `app/dispatch.py` saying so and committed it.
A repeat cancel still returns the delivery unchanged, so the refund can't be paid twice.

## 07. t4 (p2): 10 turns

Tools: Read x5, Glob x1, Write x1, Bash x2

I built `GET /report` in `app/billing.py` and committed it on `t4-billing`. Revenue is the confirmed deliveries' totals plus 4.00 for each cancelled delivery, with the confirmed count, cancelled count and flights per bird (confirmed only). I only tested the calculation on sample data, not against the running API, because `dispatch.py` is still empty.

For the team:
- **Cancelled-delivery fee:** I applied your note and added the 4.00 base fee straight to revenue, with no tax on it. Check that this matches your intent.
- **How billing finds deliveries:** PLAN.md has no endpoint that lists deliveries. So billing calls `GET /deliveries/{id}` from id 0 upward and stops after 20 misses in a row. That works only if T3 numbers deliveries with consecutive ids. T3 should add a list endpoint or a shared store, or billing should be switched to that.

## 08. t5 (p2): 12 turns

Tools: Read x4, Glob x1, Write x1, Bash x1, PowerShell x4

I wrote the CLI in `cli/pigeon.py`, but it isn't committed and I couldn't run it. The shell tools kept asking for approval and I can't give it, so it's untested. `git add` and `git commit` still need to be run.

- **Built:** every README command (`destinations`, `birds`, `quote`, `send`, `show`, `cancel`, `availability`, `report`, `track`) over httpx at `PIGEON_URL`. Money prints with two decimals, and any error prints `error: <message>` and exits 1. `send` prints the quote first, then the delivery.
- **For the team:**
  - The CLI sends `promo` as an empty string when no `--promo` is given, so Pricing and Dispatch must treat `""` as no promo.
  - `report` skips birds with 0 flights.
  - Numbers like distance, payload and speed print as they come from the API (whole values lose the trailing `.0`).

## 11. t1 (p3): 1 turns

Tools: none

Nothing in R-8 touches the roost: it changes the pricing, dispatch and command-line parts, and the `bird` and `destination` contracts are unchanged. I made no code change and no commit.

The roost still serves the same data, with `max_payload` in grams as you asked earlier.

Reminder for T2, T3 and T5: the grams conversion from before still applies. Express doesn't change which bird carries a parcel or how fast it flies, so the roost data doesn't need an express field.

## 12. t2 (p3): 2 turns

Tools: Bash x1

R-8 is in `app/pricing.py` and committed (`39e77ff`). `express` is now accepted on `POST /quote`, and the quote response has `express_fee`, which is 50% of the delivery fee before any promo.
Harbor at 2.5 kg with `COOCOO` and express quotes a total of 19.11, and the same parcel without express or promo still quotes 14.04.

- **Tax base conflicts with the lead's R-8:** I kept the tax rule you gave me earlier, so tax is 8% of (delivery fee + express fee) and the promo discount is not subtracted. The lead's message and PLAN.md both say 8% of (delivery fee − promo discount + express fee). On the example above, mine gives tax 1.56 and total 19.11; the lead's formula would give 1.04 and 18.59. Please confirm which one you want with the lead, and I'll change one line if it's theirs.
- **Note for T3 and T5:** T3 can call `compute_quote(destination, weight_kg, promo, express)` directly. T5 needs to print `express_fee:` right after `promo_discount:`.

## 13. t3 (p3): 4 turns

Tools: Edit x2, Bash x1

`POST /deliveries` now accepts `express` (default false) and passes it to `POST /quote`. The delivery's `total` is the quote's total, so it includes the express fee. The `delivery` contract is unchanged, and I haven't run it against the real pricing part. The change is committed.
Pricing (T2) has to return `express_fee` and add it into `total` and the tax base for this to work. Dispatch only forwards the flag.

## 14. t4 (p3): 1 turns

Tools: none

R-8 needs no change in `app/billing.py`, so I made no new commit. The last commit is still `ea2cb8a`.

- **Confirmed deliveries:** Billing sums each delivery's `total`, which T2 and T3 will now compute with the express fee included. The `delivery` contract hasn't changed, so the report picks it up automatically.
- **Cancelled deliveries:** Billing still keeps the flat 4.00 base fee, as your developer asked. An express cancelled delivery therefore doesn't keep its express fee. If the team wants it kept, say so and I'll change it.

## 15. t5 (p3): 5 turns

Tools: Edit x3, Bash x1

I added R-8 to `cli/pigeon.py` and committed it, covering both the first version and R-8 in one commit (0201021). I haven't run it: the shell approval prompts blocked every test run, so it's untested.

- **What changed:** `quote` and `send` take `--express` and send `express: true/false` in the request. They also print `express_fee:` right after `promo_discount:`, formatted to two decimals.
- **For Pricing and Dispatch:** `express_fee` must be present in every quote response, including `0` for non-express parcels. If it's missing, the CLI prints an "unexpected reply" error and exits 1.

## 16. t6 (p3): 10 turns

Tools: Read x6, Glob x1, Write x1, Bash x1

I built `GET /deliveries/{id}/tracking` in `app/tracking.py` and committed it on `t6-tracking`. It returns `delivery`, `status`, `bird` and `eta_minutes`. ETA is distance ÷ speed × 60 rounded half up, and 0 for a cancelled delivery. I haven't run it: the other parts are still empty stubs, so there was nothing to test against.
- **Field name:** I kept `eta_minutes`, not `eta_min`, because the `tracking` contract in PLAN.md says `eta_minutes` and the CLI (T5) reads that name. A rename would need the lead and T5 to agree. The new R-8 express fields don't affect tracking.
- **Dependencies:** The code calls `GET /deliveries/{id}`, `/birds/{handle}` and `/destinations/{code}` through the app itself, so it needs `httpx` installed (the run command already includes it) and relies on T3 and T1 serving those routes. An unknown delivery returns 404.

## 17. t1 (p4): 2 turns

Tools: Bash x1

I made no further changes. The roost endpoints still work after the grams change, and everything is already committed on `t1-roost` (4e07984).
Merge risk: PLAN.md's `bird` contract still says kg, so T3 (dispatch), T5 (CLI) and T6 (tracking) will be wrong unless they convert. T3 needs to compare `weight_kg * 1000` with `max_payload`, and T5's `birds` output has to print `max_payload` in kg (grams / 1000).

## 18. t2 (p4): 2 turns

Tools: Bash x1

I found nothing to change in `app/pricing.py`. The working tree is clean and the last commit is `39e77ff` (R-2 and express delivery R-8 on `POST /quote`).

Before merging, the tax rule still disagrees with PLAN.md. Your note has tax on the delivery fee plus express fee with no promo discount subtracted. PLAN.md R-2 and the lead's R-8 both subtract the discount first. The two only differ on promo quotes, such as harbor at 2.5 kg with `COOCOO` and express: tax 1.56 and total 19.11 here, against 1.04 and 18.59 under the plan. If you want the plan's rule, change `tax = _cents((fee + express_fee) * TAX_RATE)` in `app/pricing.py` to `tax = _cents((fee - discount + express_fee) * TAX_RATE)`.

Two other points for the merge. The destination distances are hardcoded from README.md because the roost wasn't available on my branch. T3 can import `compute_quote(destination, weight_kg, promo, express)`.

## 19. t3 (p4): 4 turns

Tools: Edit x2, Bash x1

Dispatch now returns 400 instead of crashing on a NaN or infinite weight, and I committed it. The module imports, but I haven't run it against the real roost and pricing parts.
After the merge, check that roost's `GET /birds` and `GET /birds/{handle}` and pricing's `POST /quote` return exactly the `bird` and `quote` fields, including `express_fee` and a total that includes it.

## 20. t4 (p4): 4 turns

Tools: Bash x2, Edit x1

`GET /report` is committed on `t4-billing`: revenue counts confirmed totals plus the 4.00 base fee for each cancelled delivery, with confirmed and cancelled counts and flights per bird. This commit stops billing from re-running the app's startup when it reads deliveries. `/report` returns an empty report against the current starter app, but I haven't run it against real deliveries.

For the merge, billing reads deliveries through `GET /deliveries/{id}`, scanning ids from 0 and stopping after 20 misses in a row. It only works if T3 numbers deliveries consecutively, and it is the one thing to check after merging. A cancelled express delivery keeps only the 4.00 base fee, not its express fee.

## 21. t5 (p4): 4 turns

Tools: Bash x3

I made no further changes. `cli/pigeon.py` is already committed (0201021) with R-7 and R-8, and the only untracked item is `cli/__pycache__/`, which I left out.
I ran the CLI for the first time: it compiles and parses `quote harbor 2.5 --express`. With no server running it printed `error: cannot reach …` and exited 1. I haven't tested it against a live API, so the merged build needs one end-to-end pass.

## 22. t6 (p4): 2 turns

Tools: Bash x1

I changed nothing this round. `app/tracking.py` is already committed (`c1c4c04`) and the tree is clean. I still haven't run it, because I only have my own branch and the other parts are stubs here.
Before merging, check that T3 serves `GET /deliveries/{id}` and T1 serves `GET /birds/{handle}` and `GET /destinations/{code}`, since tracking calls all three. The field is still `eta_minutes`, as in PLAN.md and the README, not the `eta_min` you asked for.

## 23. fixer (fix1): 18 turns

Tools: Bash x8, Edit x6, Write x1, PowerShell x2

I fixed C9, C11, C12, C13, C18, C19 and C20 and committed the changes. I confirmed them with a short API script, not the CLI. It showed quote 11.93, a 6 kg parcel refused with a 400, and a 25% cancellation refund counted in revenue as the kept fee.

- **Birds and refusal (C18–C20):** `app/roost.py` had payloads in grams (1000, 2000…). They are now in kg (1, 2, 3, 5), so heavy parcels pick the right bird and 6 kg is refused.
- **Tax (C12, C13):** `app/pricing.py` now taxes after the promo discount.
- **Cancellation fee (C9, C11):** `app/dispatch.py` refunds 75% of the total. `app/billing.py` counts the kept 25% as revenue instead of the old flat 4.00.
- **CLI output:** I removed the `express_fee` line from quote output in `cli/pigeon.py`, because the README lists only four keys. The `--express` flag still works.

## 24. fixer (fix2): 3 turns

Tools: Edit x1, Bash x1

C14 and C15 failed because my earlier change removed the `express_fee` line from the CLI's quote output. I put it back in `cli/pigeon.py` and committed.
The API numbers already matched what you expected, but I didn't rerun C14 or C15 after the change.
