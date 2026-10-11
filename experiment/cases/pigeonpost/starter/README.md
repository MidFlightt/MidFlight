# PigeonPost

**Parcels by pigeon.** A customer picks a destination, gets a quote, sends a parcel, and
can track or cancel it. Six people build PigeonPost, each with their own AI agent, each on
their own laptop. [PLAN.md](PLAN.md) is the lead's plan: the requirements, who builds
what, and the contracts between the parts.

## Destinations

Customers refer to a destination by its code.

| Code | Name | Distance from the roost (km) |
| --- | --- | --- |
| `downtown` | Downtown | 3 |
| `harbor` | The Harbor | 8 |
| `campus` | The Campus | 12 |
| `airport` | The Airport | 20 |

## The birds

Four birds fly for PigeonPost. Each has a handle (for example `budget-bob`), a max
payload in kg, a speed in km/h, and a number of flights per day. The fleet's data belongs
to the roost part and changes with the season, so it isn't copied here: every other part
gets it from the roost.

## The parts

| Part | File | Does |
| --- | --- | --- |
| Roost | `app/roost.py` | The birds and the destinations |
| Pricing | `app/pricing.py` | What a parcel costs |
| Dispatch | `app/dispatch.py` | Sends, shows, and cancels deliveries; each bird's flights left |
| Billing | `app/billing.py` | The revenue report |
| Tracking | `app/tracking.py` | Where a delivery is, and when it lands |
| Command line | `cli/pigeon.py` | What the customer types (below) |

`app/main.py` already wires the five API parts together. Each part only edits its file.

## The command line (what customers use)

`python -m cli.pigeon <command>`. It talks to the API over HTTP at the address in the
`PIGEON_URL` environment variable (default `http://127.0.0.1:8000`). Every command prints
one `key: value` per line, exactly these keys, and exits with code 0. Money is printed
with two decimals (`total: 14.04`). On any error it prints `error: <message>` and exits
with code 1.

| Command | Prints |
| --- | --- |
| `destinations` | one line per destination: `destination: <code> distance=<km>` |
| `birds` | one line per bird: `bird: <handle> max_payload=<kg> speed=<km/h> flights=<per day>` |
| `quote harbor 2.5` (destination, then kg; add `--promo CODE`) | `delivery_fee:`, `promo_discount:`, `tax:`, `total:` |
| `send harbor 2.5` (add `--promo CODE`) | the quote lines, then `delivery: <id>`, `bird: <handle>`, `status: confirmed` |
| `show <delivery id>` | `delivery:`, `bird:`, `status:` (`confirmed` or `cancelled`), `total:` |
| `cancel <delivery id>` | `delivery:`, `status: cancelled`, `refund: <credits>` |
| `availability budget-bob` | `flights_left: <flights left today>` |
| `report` | `revenue:`, `confirmed:`, `cancelled:`, then one `flights: <handle>=<n>` per bird that flew |
| `track <delivery id>` | `delivery:`, `status:`, `bird:`, `eta_minutes:` |

## Run it

```bash
uv run --with fastapi --with uvicorn --with httpx uvicorn app.main:app --port 8000
uv run --with httpx python -m cli.pigeon destinations
```
