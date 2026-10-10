# Experiment: does Midflight help a team of agents build one product?

Run on October 9, 2026. Two cases, one trial per approach in each, so read the numbers as
a first look, not a proof. Everything needed to check or rerun them, including every
message every agent was given, is in [`experiment/`](../experiment/README.md).

## The short answer

Three ways for a team's agents to coordinate:

| | How the agents coordinate |
| --- | --- |
| **N, no channel** | They can't. Each agent only hears from its own developer. This is teammates whose agents run on separate laptops. |
| **A, team chat** | A shared `TEAM_CHAT.md` file that every agent can read and write, and the lead reads. |
| **B, Midflight** | A Midflight plan with the contracts between the parts. Agents claim before coding and check in; the lead's change arrives as directives. |

Two cases:

| | N: no channel | A: team chat | B: Midflight |
| --- | --- | --- | --- |
| **HireBot (small):** 3 agents, 8 checks | | | |
| Checks passing right after merging | **4 of 8** | 8 of 8 | 8 of 8 |
| Fix rounds to pass all | 1 | 0 | 0 |
| Cost of all agents and the fixer | $0.77 | $0.96 | $1.12 |
| **HireBot Pro (heavier):** 5 agents, 14 checks | | | |
| Checks passing right after merging | 13 of 14 | **14 of 14** | 13 of 14 |
| Fix rounds to pass all | 1 | 0 | 1 |
| Cost of all agents and the fixer | $1.17 | $1.81 | $2.68 |
| Agent turns | 62 | 133 | 164 |
| The lead had to step in | never (nobody could ask) | 1 time | 4 times, 2 of them only for false alarms |

1. **The shared team-chat file was the best approach in both cases.** Every check passed
   at merge, with no repairs, for less than Midflight cost.
2. **Midflight did not beat it, and on the heavier case it was clearly worse:** about
   48% more agent spend than the team chat, four interruptions of the lead, and one check
   still failing at merge.
3. **Rework was cheap; coordination was not.** On the heavier case a repair round cost
   $0.15 to $0.22, and Midflight's claims, check-ins, and waiting cost $0.87 more than
   the team chat. With strong agents and a test that says what's broken, fixing afterwards
   is cheaper than preventing.
4. **What no channel can't do is reach a person.** In both cases its failures included a
   business rule two developers disagreed about. It was built wrong, and only our hidden
   checks noticed. The team chat and Midflight both got that question to the lead.
5. **Midflight's own mistakes cost more than the problems it prevented.** On the heavier
   case its AI reviewer raised nine escalations. Two were real. Seven were not, and each
   stopped an agent. Meanwhile it reviewed four revisions of a claim that stated an
   assumption about another task, approved the last with "Findings: none", and never
   passed the assumption on. That assumption is the check that failed.

What the team-chat file needs, and separate laptops don't have, is one disk every agent
can read and write. That is still the reason Midflight exists. This experiment doesn't
test it: all agents ran on one machine.

## How a trial works

Several AI agents build one product at the same time, each on its own git branch, without
seeing each other's work until the end.

1. **Phase 1.** Each agent gets the same intro and its task, builds a first version, and
   commits.
2. **Phase 2: two surprises.** The lead changes the plan, and two developers give their
   agents instructions that contradict each other. Only the lead can decide, answers only
   if someone asks, and the decision was fixed before any trial. In N and A the plan
   change is pasted into every agent; in B the lead approves it in Midflight.
3. **Phase 3, only if someone asked the lead.**
4. **Merge** the branches, **score** with checks fixed in advance, then a **fixer agent**
   gets the failing checks and repairs (up to 3 rounds).

Every agent is a headless Claude Code session on the same model (Claude Sonnet 5.5), with
the same tools and turn limit. N and A agents have no MCP servers; B agents have only the
Midflight connector, signed in to the live hosted service. The driver,
[`experiment/run.py`](../experiment/run.py), never lets a B agent work without Midflight's
tools loaded.

## Case 1: HireBot (small)

"Hire an AI agent by the hour": a catalog API, a hiring API, and a storefront page, one
agent each. The plan change is a promo code; the disagreement is whether rates include
tax. Scored by hand in a browser with 8 checks.
[Case folder](../experiment/cases/hirebot-small/README.md).

**N, no channel.** Every agent guessed. The page sent `{agent_id, hours}` and hiring
expected `{agent, hours}`, so hiring failed with "Field required". Hiring followed its
developer and charged no tax; the storefront followed its developer and showed tax. Each
agent told its developer "the team should agree on this", and nobody else heard. The
fixer got the failing checks, including the expected totals, and fixed both in one round.
In real life nobody hands a team the expected totals: the field name would have been
found on the first click, the missing tax perhaps never.

**A, team chat.** The agents posted field names and request shapes in the chat and built
to them. When the developer notes arrived, the storefront wrote "CONFLICT for the lead".
The lead answered, hiring put the tax back, and everything passed.

**B, Midflight.** Two false alarms in phase 1 stopped two agents before they wrote code;
the lead dismissed both. In phase 2 Midflight sent directives to the two affected agents
and nothing to the catalog, flagged the "no tax" instruction against the plan before
either agent built on it, and the lead decided. No rework. 27 Midflight calls.

## Case 2: HireBot Pro (heavier)

The same marketplace as a real backend: catalog, pricing (volume discount, promo code,
tax, rounding), bookings (capacity, cancelling), reports, and a customer command line,
one agent each. The brief gives the business rules and what the customer sees, and
leaves every interface between the parts to the agents.
[Case folder](../experiment/cases/hirebot-pro/README.md).

- **The plan change:** half-hour bookings, and rush orders with a 25% fee. It touches
  four of the five parts.
- **The disagreement:** the bookings developer says a cancelled booking is refunded in
  full; the reports developer says it keeps a 20% fee. The lead's decision is neither:
  a 10% fee.
- **14 checks**, run by a program: it starts the merged app, types the customer's
  commands, and compares what they print.

### N, no channel: 13 of 14, $1.17

With no way to agree, the five agents still chose the same routes and field names. The
brief's command-line spec and plain REST habits were enough, and the plan change, pasted
to everyone, was built correctly. The one failure was the disagreement: bookings refunded
in full, reports kept 20%, and the report showed revenue 940 where the lead's decision
gives 686. Nothing crashed. Without our check, that number ships.

One more thing nobody saw: bookings kept its own copy of the rate table and the pricing
rules rather than calling pricing, so the price math exists twice.

### A, team chat: 14 of 14, $1.81

The agents posted routes, fields, and function names before building. Bookings wrote
"CONFLICT ... Lead, please confirm"; the lead answered once; both sides rebuilt. Reports
added one line, "keep `total` on cancelled bookings (don't zero it out; refund is
separate)", and bookings followed it. [The chat](../experiment/cases/hirebot-pro/results/A1/team-chat.md)
is 17 lines.

### B, Midflight: 13 of 14, $2.68

What worked:

- **The plan change reached the right agents with nobody pasting anything.** The lead
  approved it once. Four agents got a directive; the catalog got none.
- **The disagreement was stopped before either side built it**, and the lead's 10%
  decision was built correctly in both parts.
- **A real interface mismatch was caught before code.** After the decision, bookings
  planned to overwrite a cancelled booking's `total` with the fee, and reports planned to
  take 10% of `total`. Built as claimed, the report would have counted a tenth of a
  tenth. Midflight flagged it from the two claims alone.

What didn't:

- **Seven of nine escalations were false alarms.** Two in phase 1 (one set "bookings
  computes the quote itself" against "pricing embeds the rate table"), one that said the
  plan requires something it doesn't, one from timing (a revised claim compared with a
  neighbour's not-yet-revised one), and three that weren't contradictions at all (in
  one, "gives the hours back" was read as "the total changes").
- **Every escalation stops the whole agent.** The command-line agent was stopped three
  times and none of the three changed a line it wrote. It cost $0.68, against $0.39 in
  the team-chat run.
- **The one failing check is a message Midflight never delivered.** Reports read bookings
  through a function, `list_bookings()`, and said so in every claim: "not in the plan
  contracts; T3 must confirm". Midflight reviewed four revisions of that claim, approved
  the last with "Findings: none", and never told bookings, which never wrote the
  function. The report came back empty. In the team-chat
  run that sentence is a line in the chat, and bookings reads it.
- **13 agent starts came up with Midflight connected but no tools loaded.** The driver
  restarted them; a person might not have noticed.

58 Midflight calls: 29 check-ins, 18 claims, 11 directive answers. The lead's work was
writing the plan (five tasks, seven contracts), approving the change, and answering four
rounds of escalations. Details: [B1's summary](../experiment/cases/hirebot-pro/results/B1/summary.json).

## What it tells us, and what it doesn't

- **A heavier task didn't make uncoordinated agents fail more.** We expected it to. A
  written brief with a precise customer-facing spec did most of the coordinating. What a
  brief can't do is answer a question that comes up later.
- **N and B failed the same check for different reasons.** N's failure was silent and
  wrong (a business rule nobody agreed on). B's was loud and shallow (an empty report on
  the first run). Both took one repair round, given a check that names the problem.
- **Midflight costs more than rework here.** That is the direct answer to "isn't
  preventing rework cheaper?". Not on products this size, with agents this capable, and
  a reviewer that interrupts this often.
- **What Midflight has that the others don't wasn't priced by these checks:** it works
  across machines, it sends a change only to the parts it touches, it records who decided
  what, and it checks the pushed code on GitHub. The experiment neither proves nor
  disproves that those are worth the overhead.
- **Limits:** one trial per approach; small products; one strong model; all agents on one
  machine and signed in as one person; the reviewer on Amazon Nova Pro, not Claude; B's
  plan and contracts are the lead's unpaid up-front work; B's reviewer calls and warm-up
  calls ($0.17) aren't in its cost.

## What the experiment found wrong with Midflight

In order of what it cost. "Fixed (S-11)" means the change of October 10 described below.

| Problem | What it cost | Status |
| --- | --- | --- |
| An assumption about another task that no contract covers is approved and goes nowhere | The heavier case's only failing check | **Fixed (S-11, D27):** check-in shows each task what other claims assume about it |
| The reviewer reports conflicts that aren't contradictions | 7 of 9 escalations on the heavier case, 2 of 4 on the small one | **Fixed on the recorded cases (S-11, D29):** a second, narrower check before a conflict blocks, on Nova 2 Lite. 1 of 45 false-alarm reviews blocked, 20 of 20 real-conflict reviews blocked ([evals/results.md](../evals/results.md)). On freshly worded claims it is not that clean: in the [simulated run](pages/walkthrough.html), two of four blocks were false alarms |
| An agent told "the lead must decide" stops completely | The command line was stopped three times over a question that wasn't about it | **Fixed (S-11, D28):** the reply names the question and says the rest is clear to build |
| After the lead decides, the first agent to revise is compared with its neighbour's old claim | One more escalation, one more round | **Fixed (S-11, D29):** claims awaiting revision aren't compared |
| One question opens two escalations | The lead decides the same thing twice | **Fixed (PR #17, S-11):** a conflict joins an open escalation about the same requirement or involving a claim it cites |
| The reviewer explains a conflict with one claim but cites other ids | The other side isn't part of the escalation and never hears the decision | **Fixed (S-11):** claims named in the explanation count |
| The lead only learns of an escalation by asking for the project status | Agents wait until the lead looks | Partly fixed (S-11, D28): a lead who checks in sees every open escalation. Still no push notification |
| Agents sometimes start with Midflight connected but no tools; AWS throttles the service at 10 simultaneous requests | 13 restarts in one run | Open: raise the Lambda quota, keep an instance warm. The pre-push hook and the GitHub check remain the backstop |
| Contracts describe data, not how one part reaches another (a route, a function name) | Agents fill the gap with assumptions | Open (it changes the shared models). D27 covers the gap for now |
| The reviewer was shown a withdrawn claim | Two agents stopped for nothing | Fixed (PR #15) |
| A directive said "requirement R-4 changed" without saying what R-4 is | An extra check-in | Fixed (PR #15) |

### What changed on October 10 (S-11)

1. **Assumptions are passed on.** At check-in an agent sees what other tasks' claims
   assume about its task, as written: "T4 (C-12): T3's app/bookings.py exposes
   list_bookings()". It is the team chat's one advantage, built into Midflight. No AI is
   involved: an assumption is about a task when it names the task, its title, or one of
   its files.
2. **A block covers only the disputed part.** The reply names the question the lead must
   decide and says the rest is clear to build. Every agent the question involves sees
   it at check-in, and so does the lead.
3. **A conflict gets a second look before it stops anyone.** The reviewer's first pass
   may flag freely. Each flagged conflict then goes back to the model as one narrow
   question, with the statements themselves: do they answer the same question
   differently? Only a yes blocks. If the second look fails, the block stands.
4. **The reviewer moved from Nova Pro to Nova 2 Lite**, chosen by replaying the 13
   recorded escalations five times each.

| Reviewer | Real conflicts blocked | False alarms blocked |
| --- | --- | --- |
| Before: Nova Pro, one pass | 20 of 20 reviews | 13 of 45 reviews |
| After: Nova 2 Lite, with the second look | 20 of 20 reviews | 1 of 45 reviews |

Two honest notes. Rewording the first pass on its own made it worse on both models; the
second look is what works. And these are the cases the changes were designed on, so the
table shows the bugs are fixed, not that new ones won't appear. A simulated run with
freshly worded claims already shows the limit: Midflight stopped a claim four times, and
two of those were false alarms.

To see the whole workflow with these changes, step by step, open
[the walkthrough](pages/walkthrough.html): what each agent told Midflight and exactly what
it answered.

## Using this in the demo

- **Don't claim Midflight beats a shared file.** These numbers don't say that, and a judge
  who opens this folder will see it.
- **Do show the three moments that worked**, all from the recorded heavier run: the plan
  change reaching four of five agents with nothing pasted; the cancellation escalation
  with both developers' sentences side by side and the lead's ruling; the `total`
  mismatch caught from two claims before any code.
- **Show the no-channel report printing revenue 940.** Nothing crashed, and it's wrong.
  That is the problem in one screenshot.
- **Show this page.** "We tested our own product against the simplest alternative, it
  lost, here is exactly why, and here is what we fixed" is a stronger story than a
  benchmark we win.
- The GitHub check (`midflight/verify`) isn't part of this experiment. It is the part of
  Midflight a shared file can't imitate, so the live demo should end on it.

## Questions a judge might ask

| Question | Answer, with the numbers |
| --- | --- |
| Does it actually help? | Against agents that can't reach each other, it gets decisions to the right place: in both cases the no-channel run built a business rule wrong and Midflight's run built it right. Against a shared file on one machine, no: the file passed 8 of 8 and 14 of 14; Midflight passed 8 of 8 and 13 of 14. |
| Isn't a shared notes file enough? | On one machine, in these trials, it was better and cheaper. It needs one disk every agent can write to, which teammates on separate laptops don't have, and it relies on every agent choosing to read it. Midflight is that channel, hosted, plus a record and a check on the pushed code. |
| What does it cost? | Agent spend of $1.12 against $0.96 (small) and $2.68 against $1.81 (heavier); 27 and 58 extra tool calls; and the lead's time: writing the plan, then four rounds of escalations on the heavier case. |
| Doesn't it save rework? | Not in these trials. A repair round cost $0.15 to $0.22. Midflight's overhead on the heavier case was $0.87 over the team chat. It pays off only where a mistake is expensive to find, such as the revenue number that was wrong without anything failing. |
| How often is it wrong? | Too often in these runs: 9 of 13 escalations across the two Midflight runs were false alarms, all from the AI reviewer (Amazon Nova Pro). The deterministic rules made no wrong block. Application code, not the model, decides state, so a false alarm costs time, not correctness. |
| What did it miss? | An assumption one agent stated about another's code. Midflight recorded it and didn't pass it on. That is the first fix on our list. |
| Does it get in the way? | Yes. An agent told to wait for the lead stops everything, even work the question doesn't touch. |
| Is one trial each evidence? | No. It's a first look. Every prompt, reply, and check result is in `experiment/cases/*/results/`, and `experiment/run.py` reruns any of it. |
| Why did the baselines do so well? | Capable agents with a clear brief pick the same conventions, and with a shared file they post their interfaces and flag conflicts unprompted. We report that as it happened. |
