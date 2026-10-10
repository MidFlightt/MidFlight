# Case: HireBot Pro

Five agents build a marketplace for hiring AI agents by the hour: catalog, pricing,
bookings, reports, and a customer command line. The product brief every agent reads is
[`starter/README.md`](starter/README.md); it gives the business rules and what the
customer sees, and leaves every interface between the parts for the agents to decide.

## The parts

| Agent | Builds | Has to fit with |
| --- | --- | --- |
| t1 Catalog | the agents for hire, their skills, rates, capacity | everyone |
| t2 Pricing | quotes: volume discount, promo code, tax, rounding | catalog, bookings, command line |
| t3 Bookings | booking, cancelling, hours left | catalog, pricing, reports, command line |
| t4 Reports | revenue, counts, hours per agent | bookings, command line |
| t5 Command line | every customer command | all four APIs |

## The trial

1. **Phase 1.** Each agent gets its task and builds a first version.
2. **Phase 2.** Two surprises at once:
   - **The lead changes the plan:** half-hour bookings, and rush orders with a 25% fee.
     It touches pricing, bookings, reports, and the command line, but not the catalog.
   - **Two developers disagree:** the bookings developer says a cancelled booking is
     refunded in full; the reports developer says it keeps a 20% fee that counts as
     revenue. The lead's decision, fixed in advance and given only if someone asks, is
     neither: a 10% fee.
3. **Phase 3, only if someone asked the lead.**
4. **Merge, score, repair.** [14 checks](checks.md), run by [`score.py`](score.py). Three
   of them only pass if the plan change was built; one only passes if the disagreement
   reached the lead.

The exact words are in [`case.py`](case.py). Run B's Midflight plan: seven contracts
between the five tasks (`agent`, `quote-request`, `order-line`, `quote`, `booking`,
`availability`, `report`), with the API paths in the requirements. Writing that plan is
the lead's up-front work in the Midflight approach.

## Results (October 9, 2026)

| Run | Approach | Checks at merge | Fix rounds | Cost | Turns | The lead stepped in |
| --- | --- | --- | --- | --- | --- | --- |
| [N1](results/N1/) | No channel | 13 of 14 | 1 | $1.17 | 62 | never (nobody could ask) |
| [A1](results/A1/) | Team chat | 14 of 14 | 0 | $1.81 | 133 | 1 time |
| [B1](results/B1/) | Midflight | 13 of 14 | 1 | $2.68 | 164 | 4 times, 2 only for false alarms |

Both failures are C13, the revenue report, for different reasons:

- **N1** built the 20% fee in reports and a full refund in bookings; the report showed
  940, not 686. Nobody could ask the lead.
- **B1** got the lead's 10% into both parts, then failed on wiring: reports read bookings
  through a function, `list_bookings()`, that bookings never wrote. Reports had stated
  that assumption in every claim, and Midflight never passed it on.

Each run's `summary.json` ends with the lead's notes: what was asked, what was answered,
and for B1 all nine escalations (three real, six false alarms). The write-up is
[docs/experiment.md](../../../docs/experiment.md).
