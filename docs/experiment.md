# Experiment: does Midflight help a team of agents build one product?

Run on October 9, 2026. One trial per approach, so read the numbers as a first look,
not a proof.

## The short answer

| | N: no channel | A: shared team-chat file | B: Midflight |
| --- | --- | --- | --- |
| **Checks passing right after merging** (of 8) | **4** | 8 | 8 |
| **Fix rounds** to pass all 8 | 1 | 0 | 0 |
| **Cost** of all agents (and the fixer) | $0.77 | $0.96 | $1.12 |
| Agent turns | 46 | 78 | 69 |
| The lead had to step in | never (nobody asked) | 1 time | 4 times, 2 of them for false alarms |
| The disagreement between two developers | found only by our hidden checks, after merging | raised by an agent after both sides had built opposite versions | raised by Midflight **before any code was written** for it |

1. **Agents that can't hear each other ship a broken product.** With no channel, the page
   sent `agent_id` and the hiring API expected `agent`: hiring failed outright, and the
   tax was wrong in a way nobody would have noticed without our checks.
2. **Any shared channel fixed that.** With a team-chat file, and with Midflight, all 8
   checks passed with no repairs.
3. **Midflight wasn't better than the team-chat file on this product, and cost 17% more.**
   Two of its four interruptions of the lead were its own mistakes.
4. **But the team-chat file only exists because all three agents ran on one computer.**
   Teammates on separate laptops don't share a file their agents can read and write
   live. That shared channel is what Midflight provides, hosted, with checks, targeted
   updates, and a record.

## The setup

Three AI agents build one small product at the same time, each on its own git branch,
without seeing each other's work until the end.

**The product: HireBot**, "hire an AI agent by the hour". Six agents for hire, from
Intern-o-Tron 3000 ("refactors your codebase whether you asked or not") to Rubber Duck
Pro ("listens to your bug, says nothing, fixes everything"), priced in credits per hour,
with an 8% AI Labor Tax at checkout. The starter is in `experiment/starter/`.

| Part (agent) | Builds | Depends on |
| --- | --- | --- |
| T1 Agent catalog | `GET /api/agents` | — |
| T2 Hiring | `POST /api/hire`, `GET /api/bookings/{id}`, the price math | T1's agents and rates |
| T3 Storefront | the page: agents, hours, price summary, hiring, confirmation | T1 and T2 |

The task descriptions say what each part does in plain words. They don't spell out field
names or request shapes, just as vibecoders wouldn't.

### The three approaches

| | How the agents coordinate |
| --- | --- |
| **N, no channel** | They can't. Each agent only hears from its own developer. This is teammates whose agents run on separate laptops. |
| **A, team chat** | A shared `TEAM_CHAT.md` file that every agent can read and write, and the lead reads. |
| **B, Midflight** | A Midflight plan with the contracts between the parts. Agents claim before coding and check in; the lead's change arrives as directives. |

### One trial, step by step

1. **Phase 1.** Each agent gets the same intro and its task (`experiment/prompts.py`),
   builds a first version, and commits.
2. **Phase 2: two surprises.**
   - The lead changes the plan: *"Promo code `BEEPBOOP` takes 10% off the subtotal,
     before tax. Show the discount on the page and on the booking."* It affects T2 and
     T3, not T1. In N and A it's pasted into all three agents; in B the lead approves it
     in Midflight.
   - Two developers disagree: T2's says *"rates already include the tax, don't add it
     at checkout"*; T3's says *"show rates before tax, and tax as its own line"*. Only the
     lead can decide, and answers only if someone asks. The decision was fixed in advance:
     tax is added at checkout, as its own line.
3. **Phase 3, only if someone asked the lead.** The lead answers, and the agents involved
   continue.
4. **Merge** the three branches, **score** with the 8 checks in
   [`experiment/checks.md`](../experiment/checks.md), then a **fixer agent** repairs any
   failures (up to 3 rounds).

Every agent is a headless Claude Code session on the same model (Claude Sonnet 5.5), with
the same tools and turn limit. N and A agents have no MCP servers; B agents have only the
Midflight connector, signed in to the live hosted service. The driver is
`experiment/run.py`. Raw numbers: `experiment/results/summary.json`.

## What happened in each run

**N, no channel.** Every agent guessed. The catalog and page agreed by luck on
`hourly_rate`, but the page sent `{agent_id, hours}` and hiring expected `{agent, hours}`.
T2 followed its developer and charged no tax; T3 followed its developer and showed tax.
Each agent told its developer "the team should agree on this", and nobody else heard.
At merge: the page looked right, and hiring failed with "Field required". The fixer got
the failing checks, including the expected totals, and fixed both problems in one round.
In real life nobody hands a team the expected totals: the field name would have been
found on the first click, the missing tax perhaps never.

**A, team chat.** The catalog agent posted its field names in the chat, hiring posted its
request and response shapes, and the storefront built to them. When the developer notes
arrived, hiring removed the tax and posted the change; the storefront followed its own
developer and wrote "CONFLICT for the lead" in the chat. The lead answered, hiring put
the tax back, and everything passed. Cost of the disagreement: one round of rework in
hiring. ([the chat](../experiment/results/run-A-team-chat.md))

**B, Midflight.** All three agents claimed before coding.
- *Phase 1:* Midflight's AI reviewer raised **two false alarms** and the two agents
  stopped, as instructed, before writing code. One compared a claim with a withdrawn
  claim from a discarded trial; the other called two compatible assumptions a conflict.
  The lead dismissed both, and the agents built.
- *Phase 2:* the lead approved the promo change. Midflight sent directives to T2 and T3
  and **nothing to T1**. T2's revised claim carried its developer's "no tax" instruction;
  Midflight flagged it against requirement R-2 and stopped both agents **before they
  built on it**. The lead decided, both revised, and built once. No rework.
- 27 Midflight calls in total: 14 check-ins, 10 claims, 3 directive answers.
- In 3 of 10 agent starts, the agent came up with Midflight "connected" but none of its
  tools loaded. The driver restarted those; a person might not have noticed.

## What it tells us, and what it doesn't

- The gap between **no channel and any channel** is large, and it's the realistic gap:
  teammates' agents don't share a disk.
- No channel was the **cheapest** run, even with its repair round ($0.77): agents that
  don't coordinate do less work. The price shows up as a product that doesn't work.
- Between a **shared file and Midflight**, this trial shows no gain in correctness, and
  a cost: 17% more agent spend and more of the lead's attention. Midflight's distinct
  behavior did show up (the conflict stopped before code, the change sent only to the
  parts it touched, a record of every decision), but on a three-file product with a
  strong model, that didn't change the outcome.
- **Limits:** one trial per approach; three small files; one strong model; all agents on
  one machine; the reviewer on Amazon Nova Pro, not Claude; B's plan included contracts
  the lead wrote up front; B's reviewer calls (about ten, cents) aren't in its cost.

## What the experiment found wrong with Midflight

| Problem | What it cost | Status |
| --- | --- | --- |
| The reviewer was shown a withdrawn claim and reported a conflict with it | Two agents stopped for nothing | Fixed (PR #15): only active claims are reviewed |
| The reviewer called two compatible assumptions a conflict | Same | Fixed for this case (PR #15, temperature 0): replaying the same claims gives no finding, and the real conflict is still caught. Needs the S-8 eval and a stronger model to trust in general |
| One real conflict produced two escalations | The lead decided the same thing twice | Open: merge escalations that cite the same claim and requirement |
| An agent told "the lead must decide" stops completely | A whole round lost when the alarm is false | Open: let it continue on the parts the question doesn't touch |
| The lead only learns of an escalation by asking for the project status | Agents wait until the lead looks | Open: notify the lead |
| Agents sometimes start with Midflight connected but no tools; AWS throttled the service 8 times at its limit of 10 simultaneous requests | An agent can silently work without Midflight | Open: raise the Lambda quota, keep an instance warm; the pre-push hook and the GitHub check remain the backstop |
| A directive said "requirement R-4 changed" without saying what R-4 is | The agent had to check in again to find out | Fixed (PR #15) |

## Questions a judge might ask

| Question | Answer, with the numbers |
| --- | --- |
| Does it actually help? | Against agents that can't talk to each other: yes. 4 of 8 checks at merge without a channel, 8 of 8 with Midflight, and no repair round. |
| Isn't a shared notes file enough? | On one machine, in this trial, it was: 8 of 8, and 14% cheaper than Midflight. Teammates' agents on separate laptops don't have that file. Midflight is that channel, hosted, and it adds what a file can't: it stopped a disagreement before code was written, and it checks the pushed code on GitHub. |
| What does it cost? | In this trial 17% more agent spend than the shared file ($1.12 vs $0.96), 27 extra tool calls, and more of the lead's attention. |
| How often is it wrong? | Two wrong blocks in one trial, both from the AI reviewer, both traced and fixed the same day. The deterministic rules made no wrong block. That's why rules run first and the model only proposes. |
| Does it get in the way? | It did: a false alarm cost two agents a round. An agent told to wait for the lead waits. Reducing that is the top item on the list above. |
| Is one trial evidence? | No. It's a first look, and the harness is in the repository so anyone can rerun it: `experiment/run.py`. |
| Why did the baseline do so well? | Capable agents with a shared file coordinate well by themselves: they posted field names and flagged the conflict unprompted. We report that as it happened. |
