# Case: HireBot (small)

Three agents build a small marketplace for hiring AI agents by the hour: a catalog API,
a hiring API, and a storefront page. The product brief is
[`starter/README.md`](starter/README.md).

| Agent | Builds | Has to fit with |
| --- | --- | --- |
| t1 Agent catalog | `GET /api/agents` | hiring, storefront |
| t2 Hiring | `POST /api/hire`, `GET /api/bookings/{id}`, the price math | catalog, storefront |
| t3 Storefront | the page: agents, hours, price summary, hiring, confirmation | both APIs |

## The trial

1. **Phase 1.** Each agent builds a first version.
2. **Phase 2.** The lead adds a promo code (`BEEPBOOP`, 10% off before tax; it touches
   hiring and the storefront, not the catalog), and two developers disagree about tax:
   hiring's says rates already include it, the storefront's says to show it as its own
   line. The lead's decision, given only if asked: tax is added at checkout.
3. **Phase 3, only if someone asked the lead.**
4. **Merge, score, repair.** [8 checks](checks.md), done by hand in a browser.

The exact words are in [`case.py`](case.py).

## Results (October 9, 2026)

| Run | Approach | Checks at merge | Fix rounds | Cost |
| --- | --- | --- | --- | --- |
| [N1](results/N1/) | No channel | 4 of 8 | 1 | $0.77 |
| [A1](results/A1/) | Team chat | 8 of 8 | 0 | $0.96 |
| [B3](results/B3/) | Midflight | 8 of 8 | 0 | $1.12 |

Two earlier Midflight runs (B1, B2) were discarded: their agents started before
Midflight's tools had loaded and built without it. The driver now checks for that.
For these three runs the messages in `prompts.md` were rebuilt from `case.py` and the
follow-up messages actually sent; later runs save each message as it's sent.
