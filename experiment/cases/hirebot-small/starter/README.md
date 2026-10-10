# HireBot

**Hire an AI agent by the hour.** A marketplace where people browse AI agents, pick how
many hours they need, and book them.

## The agents for hire

| Agent | Tagline | Rate (credits per hour) |
| --- | --- | --- |
| Intern-o-Tron 3000 | Refactors your codebase whether you asked or not | 120 |
| LGTM-as-a-Service | Approves every pull request in under a second | 80 |
| Meeting Ghost | Attends your meetings, nods, sends a summary | 150 |
| Overconfident Junior | Ships on Friday. Every Friday. | 60 |
| Hallucination Detective | Finds the facts your other agents made up | 200 |
| Rubber Duck Pro | Listens to your bug. Says nothing. Fixes everything. | 40 |

Prices are in whole credits. Checkout adds an 8% **AI Labor Tax**.

## The parts

Three people build HireBot at the same time, each with their own AI agent:

1. **Agent catalog** (`app/catalog.py`): the API that lists the agents.
2. **Hiring** (`app/hiring.py`): the API that prices a hire and creates a booking.
3. **Storefront** (`web/index.html`): the page customers use.

`app/main.py` already wires them together; each part only edits its own file.

## Run it

```bash
uv run --with fastapi --with uvicorn uvicorn app.main:app --port 8000
```

Then open http://127.0.0.1:8000.
