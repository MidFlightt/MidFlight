# The 14 checks for HireBot Pro (fixed before any trial)

`score.py` runs them automatically: it starts the merged app, types the customer
commands, and compares what they print. A reference build scores 14 of 14.

All commands are `python -m cli.hirebot ...`, run in this order against a fresh app.

| # | Command | Expected | Crosses |
| --- | --- | --- | --- |
| C1 | `agents` | six agents with the README's rates and capacities | catalog → command line |
| C2 | `agents --skill code-review` | only `hallucination-detective` and `lgtm` | catalog → command line |
| C3 | `quote meeting-ghost=10 rubber-duck=25` | subtotal 2500, volume_discount 100, promo_discount 0, tax 192, total 2592 | catalog → pricing → command line |
| C4 | the same, with `--promo BEEPBOOP` | promo_discount 50, tax 188, total 2538 | pricing → command line |
| C5 | `quote meeting-ghost=2.5` | subtotal 375, tax 30, total 405 | **plan change** (half hours) |
| C6 | `quote meeting-ghost=10 --rush` | subtotal 1500, rush_fee 375, tax 150, total 2025 | **plan change** (rush) |
| C7 | `book meeting-ghost=10 rubber-duck=25 --promo BEEPBOOP` | a booking id, status confirmed, total 2538 | pricing → bookings → command line |
| C8 | `show <id>` | status confirmed, total 2538 | bookings → command line |
| C9 | `availability meeting-ghost`, `availability rubber-duck` | 20, then 55 | catalog → bookings |
| C10 | `book hallucination-detective=25` | an `error:` line, exit code 1, and still 20 hours left | catalog → bookings |
| C11 | `cancel <id>`, `show <id>` | status cancelled both times | bookings → command line |
| C12 | `availability meeting-ghost` | 30 | bookings |
| C13 | `book lgtm=5`, then `report` | revenue 686, confirmed 1, cancelled 1, hours only `lgtm=5` | bookings → reports, and **the lead's decision** |
| C14 | `book meeting-ghost=2.5`, `availability meeting-ghost` | confirmed, total 405, then 27.5 | **plan change** (half hours) |

C13's revenue is one confirmed booking (432) plus the cancellation fee the lead decided:
10% of the cancelled booking's 2538, rounded half up, 254. Neither developer's note says
10%: one says refund everything, the other says keep 20%. A team only gets C13 right if
the disagreement reaches the lead.

After scoring at merge, a fixer agent gets each failing check (the command, what was
expected, and what it printed) and repairs; the checks run again after each round, up to
3 rounds.
