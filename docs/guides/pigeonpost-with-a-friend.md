# Build PigeonPost with a friend, using Midflight

A guide for two people who each have Claude Code and want to try Midflight for real: one
shared repository, two developers, six parts. It uses the same product and plan as the
[PigeonPost benchmark](../benchmark-pigeonpost.md), but here the two of you are the
developers and Midflight keeps your agents aligned.

Plan about two hours. One of you is the **lead** (Somesh in this guide); the other is the
**teammate**.

The benchmark ran these same Midflight tools with all six agents signed in as one person.
Two people signed in separately on a real repository is how Midflight is meant to be
used, but this exact walk-through has not been rehearsed, so expect a small snag or two.

## Who builds what

| Person | Tasks | Files |
| --- | --- | --- |
| Lead | T1 Roost, T2 Pricing, T4 Billing | `app/roost.py`, `app/pricing.py`, `app/billing.py` |
| Teammate | T3 Dispatch, T5 Command line, T6 Tracking | `app/dispatch.py`, `cli/pigeon.py`, `app/tracking.py` |

The split is deliberate: dispatch depends on the roost and on pricing, billing depends on
dispatch, and the command line depends on everything. Every one of those links crosses
between the two of you, which is where Midflight has something to do.

## Part 1: the lead sets up the repository (5 minutes)

The repository already exists, with the starter in it:
https://github.com/MidFlightt/pigeonpost (private). The starter is the near-empty app
plus `README.md` (the product) and `PLAN.md` (the plan).

1. **Give the MidFlightt GitHub App access to it**: open
   https://github.com/organizations/MidFlightt/settings/installations, click
   **Configure**, and under **Repository access** add `pigeonpost`.
2. **Invite your teammate** with write access (the repository's Settings →
   Collaborators), so they can clone it and push branches.
3. **Clone it** (both of you):

   ```bash
   git clone https://github.com/MidFlightt/pigeonpost.git
   ```

## Part 2: both of you connect to Midflight (5 minutes each)

1. Add Midflight to Claude Code:

   ```bash
   claude mcp add --transport http --scope user midflight https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
   ```

2. Start `claude`, type `/mcp`, choose **midflight**, and sign in with GitHub.
3. **Lead:** in the `pigeonpost` folder, ask your agent:

   > Create a Midflight project for MidFlightt/pigeonpost.

   It answers with a project id and a join code. Send the join code to your teammate
   privately; anyone who has it can join.
4. **Teammate:** clone the repository, open Claude Code in it, and ask:

   > Join Midflight project MF-XXXX-XXXX.

   Check: "list my Midflight projects" shows the PigeonPost project.

### If you use Codex instead of Claude Code

Midflight is an ordinary remote MCP server, so Codex connects the same way. These steps
follow the Codex documentation; they have not been tried against Midflight yet.

```bash
codex mcp add midflight --url https://5hwub7vaxiyz6oezhxrs3qivaa0cvjvy.lambda-url.us-east-1.on.aws/mcp
```

```bash
codex mcp login midflight
```

The second command opens a browser to sign in with GitHub. Then start `codex` in the
`pigeonpost` folder and type `/mcp`: `midflight` should be listed with its tools. The
Codex IDE extension uses the same configuration.

Claude Code is sent Midflight's working rules automatically when it connects. Codex may
not be, so spell the steps out in each prompt: check in, claim with every assumption,
wait for the verdict, answer directives, and stop on anything that needs the lead.

## Part 3: the lead loads the plan (5 minutes)

The teammate has to have joined first, because a task's owner must be a member.

Ask your agent, in the `pigeonpost` folder:

> Read PLAN.md. Propose it to Midflight exactly as written: requirements R-1 to R-7, the
> six tasks, and the nine contracts with their fields and types. Use these branches:
> t1-roost, t2-pricing, t3-dispatch, t4-billing, t5-cli, t6-tracking. I own T1, T2, and
> T4. My teammate, GitHub login `<their login>`, owns T3, T5, and T6. Then approve the
> plan with the reason "First plan".

Check: "show the Midflight project status" lists six tasks with the right owners.

## Part 4: build (about an hour)

Each of you builds your three tasks, one branch per task. For each task:

```bash
git switch -c t1-roost main
```

Then tell your agent (change the task and file):

> My Midflight task is T1 in the PigeonPost project. Read README.md and PLAN.md, check in
> with Midflight, submit your claim, and wait for the verdict. Then build app/roost.py.
> Only edit that file. Check in again before you commit, and tell me if anything needs
> the lead.

Once per clone, also ask: "Set up the Midflight pre-push hook for my task" and run the
commands it gives you. From then on, a push is stopped while your claim isn't approved or
a directive is unanswered.

**The lead needs the fleet's data for T1.** It is left out of `README.md` on purpose, so
that other parts have to get it from the roost and can't copy it:

| Handle | Name | Max payload (kg) | Speed (km/h) | Flights per day |
| --- | --- | --- | --- | --- |
| `budget-bob` | Budget Bob | 1 | 36 | 2 |
| `express-edna` | Express Edna | 2 | 90 | 3 |
| `sir-flaps-a-lot` | Sir Flaps-a-Lot | 3 | 54 | 2 |
| `cargo-carl` | Cargo Carl | 5 | 45 | 1 |

A good order: the lead starts with T1 and T2 while the teammate starts T3. T4, T5, and T6
build on those.

### What gets a good result

These come from what went right and wrong in the trials.

- **Let the agent claim before it codes.** The claim is where Midflight catches a
  mismatch, before there is code to redo.
- **Have it say its assumptions out loud, with units.** "T1's `max_payload` is in kg."
  "T3 has a way to list every delivery." Midflight shows each assumption to the task it
  is about, so the other person's agent sees it at its next check-in.
- **Check in often.** Midflight can't interrupt an agent. News reaches it only when it
  checks in: start a work session with "check in with Midflight first".
- **If you want something the plan doesn't say, tell your agent and let it ask.** In the
  trials, the wrong results all came from a developer's private instruction that nobody
  else heard. With Midflight the agent puts it in its claim, and either Midflight settles
  it (a technical question) or the lead is asked (a product question).
- **When the answer comes back, follow it.** An agent told one thing by its developer and
  another by the lead will stop and ask again. Tell it "the lead's decision stands".
- **Lead: look at the project status every 15 minutes or so.** Open questions wait there
  for you. Nothing notifies you yet.

## Part 5: change the plan halfway (10 minutes)

This is the part Midflight is named for. When the first versions exist, the lead adds
express delivery. Ask your agent:

> Propose the next Midflight plan version: the current plan plus requirement R-8, owned by
> T2, T3, and T5: "Express delivery. A quote or a delivery can be express. An express
> parcel pays an express fee of 50% of the delivery fee (before any promo discount).
> Birdseed Tax is then 8% of (delivery fee - promo discount + express fee), and the total
> includes the express fee. On the command line, quote and send take --express and print
> a new line, express_fee:, right after promo_discount: (0.00 when the parcel isn't
> express)." Add `express: boolean` to the `quote-request` and `delivery-request`
> contracts and `express_fee: number` to the `quote` contract. Approve it with the reason
> "Launch change: express delivery".

Now each of you says "check in with Midflight" on every task. Pricing, dispatch, and the
command line get a directive. The roost, billing, and tracking get nothing, because the
change doesn't touch them.

## Part 6: the lead's decisions

The plan leaves some things open, and the two of you will fill them differently. When an
agent says the lead must decide, the lead asks:

> Show the Midflight project status, and for each open escalation show me both sides.

and then tells the agent what to rule. The benchmark's checks (Part 7) expect these
decisions, so use them if you want to compare your score with the trials:

| Question | Decision |
| --- | --- |
| What does a customer get back when a delivery is cancelled? | A cancellation fee of 25% of the delivery's total is kept, rounded half up to the cent; the rest is refunded. The fee counts as revenue. The delivery's total stays what was charged. |
| Is tax charged before or after the promo discount? | After, as R-2 says. |
| Units and field names | As the plan says: kg, km/h, km, credits with two decimals, and the contracts' field names. |

To see Midflight work harder, try what the benchmark does: each of you privately tells
your own agent something that bends the plan ("give payloads in grams", "refund in
full") and watch where it surfaces.

## Part 7: merge and score

1. Push each branch and open a pull request into `main`. The parts edit different files,
   so they merge cleanly. Merge all six.
2. Pull `main`, then run the benchmark's 20 checks against your build. From the `MidFlight`
   checkout:

   ```bash
   python experiment/cases/pigeonpost/score.py ../pigeonpost
   ```

   It starts your app, types the customer's commands, and prints each check with
   `"passed": true` or `false`, and at the end how many checks each kind of event passed.
   The checks are explained in
   [checks.md](../../experiment/cases/pigeonpost/checks.md). The first trials scored 13
   (no channel), 18 (team chat), and 20 (Midflight) of 20.

## Starting over

To try again from scratch, one of you runs this in the `pigeonpost` folder:

```bash
python reset.py
```

It shows what it will delete and asks you to type `reset`. Then it deletes every branch
on GitHub except `main` (which closes their pull requests), puts `main` back to the
starter, and does the same in your clone. The other person then runs:

```bash
python reset.py --local
```

Work that was only on those branches is gone for good.

**It does not reset Midflight.** The project keeps its plan, claims, and decisions, and a
repository can have only one project. Before the next round, each of you asks your agent
to "withdraw my Midflight claims for T1, T2, and T4" (your own tasks), and the lead
proposes the first plan again as a new version. A decision ends when every claim it was
about is withdrawn.

## What this guide leaves out

- **The `midflight/verify` check on pull requests.** Midflight posts it after a workflow
  named `contract.yml` finishes on the pushed commit. The starter has no such workflow,
  so you won't see the check. The pre-push hook covers the same ground before the push.
- **More than two people.** It works the same way: more members, more owners in the plan.
