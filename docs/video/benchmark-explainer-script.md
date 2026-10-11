# Script: how the PigeonPost benchmark works

A spoken explanation of the benchmark and its result, about two minutes at a normal pace
(roughly 300 words). Each scene has what to show and what to say. The numbers are from
[benchmark-pigeonpost-markers.md](../benchmark-pigeonpost-markers.md) and
[benchmark-pigeonpost.md](../benchmark-pigeonpost.md); if a run is repeated, change them
here too.

## Scene 1: the question (15 seconds)

**Show:** six terminal windows, each with an AI agent working.

**Say:**

> Six developers, six AI agents, one product. Each agent only hears from its own
> developer. So what happens when plans change halfway through? We built a benchmark to
> find out.

## Scene 2: the task (20 seconds)

**Show:** the PigeonPost README, then the six parts: roost, pricing, dispatch, billing,
command line, tracking.

**Say:**

> The product is PigeonPost, a parcel service that delivers by pigeon. Six agents each
> build one part, on their own copy of the repository, as if on separate laptops. They
> all get the same brief and the same plan.

## Scene 3: the surprises (25 seconds)

**Show:** the six events, appearing one at a time.

**Say:**

> Then we make it hard. Six things happen after the plan is written. The lead changes the
> plan. Two developers give their agents opposite instructions about refunds. One
> developer quietly switches a unit from kilograms to grams. One agent joins late. These
> are scripted, so every run faces exactly the same surprises.

## Scene 4: three ways to coordinate (25 seconds)

**Show:** three columns: no channel, team chat, Midflight.

**Say:**

> We ran it three ways. First, no channel: agents can't talk to each other at all.
> Second, a shared chat file that every agent reads and writes. Third, Midflight: agents
> claim what they'll build before building it, check in at key points, and plan changes
> reach only the agents they affect. Same model, same instructions, same phases.

## Scene 5: how it's scored (15 seconds)

**Show:** the merge, then 20 checks ticking green or red.

**Say:**

> At the end we merge all six branches and run twenty automated checks on the finished
> product. No human judgement. We also record every token and every dollar the agents
> spent.

## Scene 6: the result (30 seconds)

**Show:** the results table.

| | No channel | Team chat | Midflight |
| --- | --- | --- | --- |
| Checks passing at merge | 13 of 20 | 18 of 20 | 20 of 20 |
| Fix rounds needed | 2 | 1 | 0 |
| Cost of the agents | $2.06 | $1.88 | $2.35 |

**Say:**

> With no channel, thirteen of twenty checks passed. With the team chat, eighteen. With
> Midflight, all twenty, with nothing to fix afterwards. Midflight costs more: about a
> quarter more than the chat. That gap used to be forty-three percent. Our new check-in
> markers mean an agent is only sent what changed since it last asked, which cut what
> Midflight sends by a quarter.

## Scene 7: the honest part (15 seconds)

**Show:** the line "One trial each. A case built around Midflight's strengths."

**Say:**

> Two things to know. This is one run of each approach, and we designed this case around
> the problem Midflight solves. On simpler projects, a shared chat file did just as well
> for less.
> Midflight earns its cost when plans change mid-flight.

## If you only have 30 seconds

> Six AI agents build one product on separate laptops, and six surprises hit them
> mid-build: a plan change, conflicting instructions, a unit quietly switched. We merge
> their work and run twenty automated checks. With no way to coordinate, thirteen pass.
> With a shared chat file, eighteen. With Midflight, all twenty, for about a quarter more
> in agent cost. One run each, on a case built around Midflight's strengths.

## Facts behind each line

| Line in the script | Where it comes from |
| --- | --- |
| Six agents, separate copies, same brief and plan | `experiment/cases/pigeonpost/README.md` |
| Six scripted events, twenty checks | `experiment/cases/pigeonpost/checks.md` |
| 13, 18 and 20 of 20; fix rounds; costs | runs N1, A1 (October 10) and B2 (October 11) |
| "A quarter more than the chat" | $2.35 against $1.88 |
| "Used to be forty-three percent" | run B1, $2.69 against $1.88 |
| "Cut what Midflight sends by a quarter" | 144,788 to 107,612 characters |
| "A shared chat file did just as well" | the two HireBot cases in `docs/experiment.md` |
