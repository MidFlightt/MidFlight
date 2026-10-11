# Benchmark: PigeonPost

A third experiment case, built and first run on October 10, 2026. This page explains the
scenario, how a trial works, what the first three trials showed, and how to run it on
your own laptop. The first two cases and their results are in
[experiment.md](experiment.md).

## First results

One trial per approach, so read this as a first look.

| | N: no channel | A: team chat | B: Midflight |
| --- | --- | --- | --- |
| Checks passing right after merging | 13 of 20 | 18 of 20 | **20 of 20** |
| Mid-flight events held | 3 of 6 | 5 of 6 | 6 of 6 |
| Fix rounds to pass all | 2 | 1 | 0 |
| Cost of the agents and the fixer | $2.06 | $1.88 | $2.69 |
| Agent turns | 126 | 105 | 177 |
| The lead answered | never (nobody could ask) | 5 posts | 3 escalations |

1. **No channel shipped three wrong rules, and nothing crashed.** The roost served
   payloads in grams, so a 6 kg parcel was accepted; pricing charged tax before the promo
   discount; dispatch refunded a cancellation in full while billing kept 4.00. Each agent
   told only its own developer.
2. **The team chat fixed two of those three.** The agents posted their developers' notes,
   the lead answered, and the grams and the tax were changed back before the merge. It was
   also the cheapest run.
3. **The team chat lost the cancellation fee.** The lead's 25% decision reached both
   agents. Each kept its own developer's instruction, wrote "CONFLICT for lead" again, and
   waited. The lead, whose instructions say to answer what it hasn't answered yet, didn't
   repeat itself. The refund and the revenue were merged wrong.
4. **Midflight passed every check at merge.** The same second round happened there:
   dispatch still refunded in full after the lead's first ruling. Midflight raised it
   again as an open question, the lead ruled again, and both parts built the 25% fee.
   Midflight settled the tax and the grams itself ("the plan stands"), and no false alarm
   reached the lead.
5. **Midflight cost the most:** 43% more agent spend than the team chat, 72 more turns,
   and four more minutes of agent time. The repair round it avoided cost the team chat
   $0.12.

What this does and doesn't show:

- **The difference between A and B is one event, in one trial each.** It rests on what
  happens when an agent is told one thing by its developer and another by the lead. A
  lead who repeated the decision in the chat might have closed it. In Midflight the
  repeat wasn't left to the lead noticing: the question stayed open until it was decided.
- **The team chat is still a strong approach.** It held five of six events on a case
  built to be hard for it.
- **This case leans toward Midflight on purpose** (see below). It says Midflight can win
  on its home ground, not that it wins in general. In both earlier cases the team chat
  won or tied.
- **B's cost leaves out** the lead's own agent ($0.37, against $0.14 in the team chat),
  the harness's warm-up calls ($0.64), and Midflight's reviewer on AWS. Five agent starts
  came up without Midflight's tools and were restarted by the driver.

Every message, reply, and check is in
[`experiment/cases/pigeonpost/results/`](../experiment/cases/pigeonpost/results/).

## What it compares

Six AI agents build one small product together. Each agent belongs to a different
developer, works on that developer's laptop, and can't see the others' code until
everything is merged. We run the same build three times and change only how the agents
can coordinate:

| Run letter | Approach | How the agents coordinate |
| --- | --- | --- |
| **N** | No channel | They can't. Each agent hears only from its own developer, and from the lead when the lead writes to everyone. |
| **A** | Team chat | A `CHAT.md` file in the team's repository. Every agent can read it and post to it, and the lead reads it. |
| **B** | Midflight | Agents claim before coding and check in; Midflight compares claims with the plan and with each other. |

## The scenario

**PigeonPost: parcels by pigeon.** A customer picks a destination, gets a quote, sends a
parcel, and can track or cancel it.

| Agent | Part | Does |
| --- | --- | --- |
| T1 | Roost | The birds (payload, speed, flights per day) and the destinations |
| T2 | Pricing | What a parcel costs: fee, promo code, tax |
| T3 | Dispatch | Picks a bird, sends, shows, and cancels deliveries |
| T4 | Billing | The revenue report |
| T5 | Command line | What the customer types |
| T6 | Tracking | Where a delivery is and when it lands |

Before anyone starts, the lead writes a plan: seven short requirements, who builds what,
and nine contracts (the exact fields one part hands another). **Every approach gets this
same plan.** In runs N and A it is the file `PLAN.md` in the repository. In run B it is
also loaded into Midflight. Both come from one file,
[`plan.py`](../experiment/cases/pigeonpost/plan.py), so neither says more than the other.

### What the case is really about: six things that happen after the plan

The first two cases showed that capable agents with a clear plan build matching parts
without talking. So this case is about what a plan can't cover: news that appears while
people are already building. There are six such events.

| Event | What happens | The Midflight feature it tests |
| --- | --- | --- |
| **Plan change** | The lead adds express delivery. It concerns pricing, dispatch, and the command line, and not the other three parts. | A change is sent only to the tasks it touches |
| **Two developers disagree** | Dispatch's developer says a cancelled delivery is refunded in full. Billing's developer says keep the 4.00 base fee. The lead's decision is neither: a 25% fee. | A product question goes to the lead, with both sides |
| **A note against the plan** | Pricing's developer wants tax charged before the promo discount. The plan says after. | A claim is checked against the plan |
| **A unit quietly changed** | The roost's developer wants bird payloads in grams. Everyone else thinks in kg. | Agents state their assumptions, and Midflight settles a technical question itself |
| **Late joiner** | Tracking starts long after everyone else, and its developer wants a field called `eta_min` where the contract says `eta_minutes`. | A contract's field names are checked by a rule, with no AI |
| **Nobody planned it** | Billing needs the list of all deliveries. The plan describes a delivery, not how billing gets them all. | An assumption about another task is shown to that task's agent |

The developer notes are private: each is given only to that developer's own agent, the
way a teammate tells their own agent something and nobody else hears it. The notes are the
same, word for word, in all three approaches.

### A trial, step by step

| Step | What happens |
| --- | --- |
| Phase 1 | Roost, pricing, and dispatch build their first version. |
| Phase 2 | Billing and the command line start. Roost, pricing, dispatch, and billing each get their developer's note. |
| The lead's turn | The lead answers whatever it was asked. |
| The lead's change | The lead announces express delivery. |
| Phase 3 | Tracking starts, with its developer's note. Everyone else gets a turn to react. |
| The lead's turn | The lead answers again. |
| Phase 4 | Last call: every agent gets one more turn. |
| Merge and score | The six branches are merged, and 20 checks run against the result. |
| Repair | A fixer agent is given the failing checks and repairs them, up to three rounds. |

**The lead is an agent too**, so that a trial runs the same way on any laptop. It has a
decision sheet written before any trial (three decisions; they are in
[`case.py`](../experiment/cases/pigeonpost/case.py)). It answers what it is asked, word
for word from the sheet, and never brings up a decision nobody asked for. In run A it
reads the chat and posts answers. In run B it decides the questions Midflight sends it. In
run N nobody can reach it.

How the lead's change travels: in run N the lead writes to all six developers and each
pastes it to their agent. In run A the lead posts it once in the chat. In run B the lead
approves a new plan version in Midflight.

## What is the same in every approach

- The plan, the task each agent is given, and the developer notes.
- The model (Claude Sonnet), the tools, and the turn limit.
- How many turns each agent gets, and when.
- A reminder at the start of each turn to look at the channel first: "Read the team chat
  first" in run A, "Check in with Midflight first" in run B.
- The lead's decision sheet.
- The 20 checks and their expected values, which were fixed first and confirmed with a
  reference build.

## Where this case leans toward Midflight

It leans on purpose, and anyone reading the results should know how. This is Midflight's
home ground, not a neutral sample of software projects.

1. **Twelve of the 20 checks sit on a mid-flight event.** The earlier, heavier case had 4
   of 14. A project where nothing changes after the plan would show no difference between
   the approaches.
2. **The developer notes are written to collide.** In a real week most private
   instructions don't contradict anyone.
3. **Every agent has its own copy of the repository**, as on separate laptops. The chat
   has to be fetched and pushed. In the earlier trials it was a file on one shared disk,
   which real teams don't have.
4. **The lead announces a change once, in the channel.** Earlier, the change was also
   pasted into every agent, in every approach.
5. **The lead answers only what it is asked.** It doesn't read the chat looking for
   problems nobody flagged.
6. **The fleet's data exists only in the roost part.** Other parts can't copy it into
   their own code, as one agent did in an earlier trial. They have to depend on the roost.
7. **Agents start at different times**, so some news arrives after an agent's first
   version is finished.

What was not done: the team chat was not given a weaker prompt (it now has a ready-made
tool and a reminder every turn, which it didn't have before); no check was written after
seeing a result; and Midflight's higher cost is reported next to its score.

It can still lose. The team chat beat Midflight in both earlier cases, and agents that
post their notes and read the replies can pass every check here too.

## How it is scored

Four things, all reported:

1. **Checks passing right after the merge**, out of 20, before any repair. This is the
   main number. A fixer that is handed the expected totals can repair anything; a real
   team isn't handed them.
2. **Events held**, out of six. An event held if all of its checks pass. This shows which
   kind of news got lost.
3. **The lead's work**: how many times the lead had to answer.
4. **Cost**: agent spend, turns, and tool calls, plus the repair rounds.

Eight checks are a plain build that every approach should pass. If one of those fails, an
agent built its own part wrong, and the run says little about coordination.

The checks are listed in [`checks.md`](../experiment/cases/pigeonpost/checks.md). Each
event was tested against the reference build with only that event missed: it fails its
own checks and no others.

## Run it on your laptop

You need git, Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and
[Claude Code](https://claude.com/claude-code) signed in. On a Mac, type `python3` where
this page says `python`.

**1. Get the code and check your machine.** This spends no tokens.

```bash
git clone https://github.com/MidFlightt/MidFlight.git
```

```bash
cd MidFlight
```

Until the case is merged into `main`, it lives on its own branch:

```bash
git switch experiment-pigeonpost
```

```bash
python experiment/run.py pigeonpost X selftest
```

It should end with `reference build: 20 of 20 checks pass`.

**2. Run the no-channel trial.** One command does every step. Pick your own run name; its
first letter chooses the approach (N, A, or B).

```bash
python experiment/run.py pigeonpost N1 auto
```

**3. Run the team-chat trial.**

```bash
python experiment/run.py pigeonpost A1 auto
```

**4. Run the Midflight trial.** This one needs three things first, once:

- Add Midflight to Claude Code under the name `midflight-live`, then start `claude`, type
  `/mcp`, and sign in with GitHub:

  ```bash
  claude mcp add --transport http --scope user midflight-live https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
  ```

- Create an empty GitHub repository and install the **MidFlightt** GitHub App on it. The
  trial never pushes to it.
- In Claude Code, ask: "Create a Midflight project for `<you>/<that repository>`". It
  answers with a project id such as `midflight-1234`.

A project remembers earlier decisions, and a repository can have only one Midflight
project. So every Midflight trial needs its own new, empty repository.

Then give the project id to the run:

```bash
python experiment/run.py pigeonpost B1 auto midflight-1234
```

**5. See the three runs side by side.**

```bash
python experiment/run.py pigeonpost all table
```

Things to know:

- A trial is about 25 agent runs (six agents, up to four turns each, plus the lead and
  the fixer). If your Claude plan's usage limit is reached, the
  command stops. Run the same command again later and it continues where it stopped.
- At most three agents run at once.
- Trials work in a folder next to the repository, `../experiment-runs/pigeonpost/<run>/`.
  Don't switch git branches in the repository while a trial runs.
- The results are written to `experiment/cases/pigeonpost/results/<run>/`: every message
  each agent was given, what each replied, every check, the team chat (run A), and the
  totals in `summary.json`. Send that folder back, or open a pull request with it.

## Limits

- One trial per approach is a first look, not a proof. Run each approach several times
  before saying one is better.
- All six agents run on one machine and, in run B, are signed in as one person. The
  separate laptops are separate copies of the repository, not separate computers.
- The lead is an AI with a fixed sheet. A person would sometimes notice a problem nobody
  flagged, and would sometimes be slower.
- Midflight's check on pushed code (`midflight/verify`) is not part of this case.
- The driver's steps were tested without agents (set-up, the chat tool with six posts at
  once, merging, scoring, recording) and with two real turns of the lead in the team-chat
  approach, before the three trials above.
