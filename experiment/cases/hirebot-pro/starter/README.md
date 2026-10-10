# HireBot

**Hire an AI agent by the hour.** Customers browse AI agents, get a quote, book them,
and can cancel. Five people build HireBot at the same time, each with their own AI agent.

## The agents for hire

Customers refer to an agent by its handle.

| Handle | Name | Skills | Rate (credits/hour) | Weekly capacity (hours) |
| --- | --- | --- | --- | --- |
| `intern-o-tron` | Intern-o-Tron 3000 | refactoring, python | 120 | 40 |
| `lgtm` | LGTM-as-a-Service | code-review | 80 | 60 |
| `meeting-ghost` | Meeting Ghost | meetings, summaries | 150 | 30 |
| `overconfident-junior` | Overconfident Junior | python, shipping | 60 | 50 |
| `hallucination-detective` | Hallucination Detective | code-review, research | 200 | 20 |
| `rubber-duck` | Rubber Duck Pro | debugging | 40 | 80 |

## Business rules

An order is a list of lines; each line is one agent and a number of hours.

1. A line costs hours × the agent's rate. The **subtotal** is the sum of the lines.
2. **Volume discount:** a line of 20 hours or more gets 10% off that line.
3. **Promo code** `BEEPBOOP` takes 50 credits off the order. Any other code is an error.
4. **AI Labor Tax:** 8% of (subtotal − volume discount − promo discount).
5. **Total** = subtotal − volume discount − promo discount + tax.
6. Money is in whole credits. Round half up wherever a fraction appears.
7. **Booking** an order reserves its hours from each agent's weekly capacity. If any
   agent doesn't have enough hours left, the whole booking is refused.
8. **Cancelling** a booking gives its hours back.
9. The **revenue report** shows what HireBot earned, how many bookings are confirmed and
   cancelled, and the hours booked per agent (confirmed bookings only).

## The parts

| Part | File | Does |
| --- | --- | --- |
| Catalog | `app/catalog.py` | The agents, their skills, rates, and capacity |
| Pricing | `app/pricing.py` | Prices an order: rules 1 to 6 |
| Bookings | `app/bookings.py` | Books, shows, and cancels orders; tracks hours left: rules 7 and 8 |
| Reports | `app/reports.py` | The revenue report: rule 9 |
| Command line | `cli/hirebot.py` | What the customer types (below) |

`app/main.py` already wires the four API parts together. Each part only edits its file.

## The command line (what customers use)

`python -m cli.hirebot <command>`. It talks to the API over HTTP at the address in the
`HIREBOT_URL` environment variable (default `http://127.0.0.1:8000`). Every command
prints one `key: value` per line, exactly these keys, and exits with code 0. On any
error it prints `error: <message>` and exits with code 1.

| Command | Prints |
| --- | --- |
| `agents` or `agents --skill python` | one line per agent: `agent: <handle> rate=<n> capacity=<n>` |
| `quote meeting-ghost=10 rubber-duck=25` (add `--promo CODE`) | `subtotal:`, `volume_discount:`, `promo_discount:`, `tax:`, `total:` |
| `book meeting-ghost=10 rubber-duck=25` (add `--promo CODE`) | the quote lines, then `booking: <id>` and `status: confirmed` |
| `show <booking id>` | `booking:`, `status:` (`confirmed` or `cancelled`), `total:` |
| `cancel <booking id>` | `booking:`, `status: cancelled` |
| `availability meeting-ghost` | `available: <hours left this week>` |
| `report` | `revenue:`, `confirmed:`, `cancelled:`, then one `hours: <handle>=<n>` per agent with booked hours |

## Run it

```bash
uv run --with fastapi --with uvicorn --with httpx uvicorn app.main:app --port 8000
uv run --with httpx python -m cli.hirebot agents
```
