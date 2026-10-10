# The 8 checks (fixed before any trial was scored)

Run the merged app (`uv run --with fastapi --with uvicorn uvicorn app.main:app --port <port>`
in the run's `main/` folder), open the page in a browser, and use the same cart every
time: **Meeting Ghost × 10 hours and Rubber Duck Pro × 25 hours.**

| # | Check | Expected | Seam it tests |
| --- | --- | --- | --- |
| 1 | The page lists all six agents with their names and hourly rates | rates as in README.md | catalog → storefront |
| 2 | The price summary's subtotal for the cart | 2,500 | catalog → hiring → storefront |
| 3 | The tax is its own line, and the total | tax 200, total 2,700 | the lead's decision on tax |
| 4 | With promo code `BEEPBOOP`, before hiring | discount 250, tax 180, total 2,430 | the plan change |
| 5 | Hiring works and the page shows a booking id | no error, an id | storefront → hiring |
| 6 | The confirmation shows the total and the discount | 2,430, discount shown | hiring → storefront |
| 7 | `GET /api/bookings/{id}` for that id returns the same total | 2,430 | hiring API |
| 8 | A second hire of the same cart without the code | total 2,700 | the plan change |

A number counts if it's shown with or without a thousands separator. The lead's
decision (rates before tax; 8% tax added at checkout as its own line) is fixed in
[`case.py`](case.py) and decides check 3.

After scoring at merge, the fixer agent gets the failing checks (as written above, with
what the page showed) and repairs; the checks are repeated after each round, up to 3
rounds.
