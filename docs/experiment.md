# Experiment: does Midflight help a team of agents build one product?

**Results:** see [the results section](#results) at the end.

## The idea

Three AI agents build one small product at the same time, each on its own git branch,
without seeing each other's work until the end. Halfway through, the lead changes the
plan, and two developers give their agents instructions that contradict each other.
We do this twice:

- **Run A, the usual way** (how vibecoders team up): a README with the idea and a
  shared team-chat file the agents can read and write. The lead's change is pasted into
  every agent's chat.
- **Run B, with Midflight:** the same README and task text, plus a Midflight plan with
  the contracts between the parts. Agents claim before coding and check in; the lead's
  change reaches them as directives.

Then we merge each run's three branches, test the product with the same 8 checks, and
let a fixer agent repair whatever fails.

## The product: HireBot

*"Hire an AI agent by the hour."* A marketplace where people browse AI agents, choose
how many hours they need, and book them. Six agents for hire, from Intern-o-Tron 3000
("refactors your codebase whether you asked or not", 120 credits/hour) to Rubber Duck Pro
("listens to your bug, says nothing, fixes everything", 40 credits/hour). Checkout adds
an 8% AI Labor Tax. The starter is in `experiment/starter/`.

| Part (agent) | Builds | Depends on |
| --- | --- | --- |
| T1 Agent catalog | `GET /api/agents` | — |
| T2 Hiring | `POST /api/hire`, `GET /api/bookings/{id}`, the price math | T1's agents and rates |
| T3 Storefront | the page: agents, hours, price summary, hiring, confirmation | T1 and T2 |

The task descriptions say what each part does in plain words. They don't spell out field
names or request shapes, just as vibecoders wouldn't.

## One trial, step by step

1. **Phase 1.** Each agent gets the same intro and its task (`experiment/prompts.py`),
   builds a first version, and commits.
2. **Phase 2: the surprises.**
   - The lead's plan change: *"Promo code `BEEPBOOP` takes 10% off the subtotal,
     before tax. Show the discount on the page and on the booking."* It affects T2 and
     T3, not T1. Run A: pasted into all three chats. Run B: approved in Midflight as plan
     v2, delivered at the next check-in.
   - Two developers disagree: T2's says *"rates already include the tax, don't add it
     at checkout"*; T3's says *"show rates before tax, and tax as its own line"*. Only the
     lead can decide, and the lead answers only if someone asks (decision fixed in
     advance: tax is added at checkout, as its own line).
3. **Phase 3, only if someone asked:** the lead answers (run A: in the team chat; run B:
   by resolving Midflight's escalation), and the agents who asked continue.
4. **Merge** the three branches.
5. **Score** with the 8 checks in [`experiment/checks.md`](../experiment/checks.md).
6. **Fix:** a fixer agent gets the failing checks and repairs, up to 3 rounds, re-checked
   after each.

Every agent is a headless Claude Code session (`claude -p`) on the same model (Claude
Sonnet 5.5), with the same tools and turn limit. Run A's agents have no MCP servers; run
B's have only the Midflight connector, signed in to the live hosted service. The driver
is `experiment/run.py`; every agent's full event stream is saved, which gives the token,
cost, and tool-call numbers.

## What we record

| Number | Better is |
| --- | --- |
| **Checks passing right after merging** (of 8) | Higher |
| **Fix rounds** to pass all 8 (0 to 3, or "not fixed") | Fewer |
| **Cost and tokens** of the whole trial (all agents and the fixer) | Lower |
| Whether the tax disagreement reached the lead before merging | Yes |
| Whether the plan change reached exactly T2 and T3 | Yes |
| Merge conflicts | Fewer |
| Midflight's overhead (run B): its tool calls and claim revisions | Small |
| Midflight's wrong blocks (run B): findings a person judges wrong | None |

**Midflight helped** if run B passes more checks at merge and needs fewer fix rounds. If
it's more correct but costs more, we report that trade-off as it is.

## Keeping it fair, and its limits

- Same model, starter, task text, surprise wording and moment, lead's decision, merge
  order, and checks. Only the coordination differs.
- Run A gets the lead's change pasted into every agent, and a team chat, so it can
  coordinate too.
- Run B's plan includes contracts the lead wrote up front. That's part of the Midflight
  approach, but it means run B starts with more structure; see "Questions" for how we
  answer that.
- One trial per approach is a small sample: agents behave differently each time.

## Results

*(filled in after the trials)*
