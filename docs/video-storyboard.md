# Demo video storyboard (3:00)

The submission video for the "Hand it off" challenge. It replaces the `total` /
`total_cents` storyboard in [demo.md](demo.md) with the HireBot Pro case from the
[experiment](experiment.md), because the small case doesn't show what Midflight is for.

Every line of on-screen text is real output or a true statement. Where a scene is rebuilt
from the October 9 logs, it carries a corner label saying so.

## What the judges check, and where the video shows it

| Requirement | Scene | How |
| --- | --- | --- |
| 1. Name the person and what the task costs them | 1 | The lead of a vibecoding team. Agents write the code and agents review it; the lead's hand work is carrying messages between them. The task and its cost are on screen. |
| 2. Call a tool we didn't build; the agent acts | 3, 4, 6 | GitHub (reads commits, publishes the `midflight/verify` check) and Amazon Bedrock (reviews claims). Midflight delivers directives, blocks a push, and fails a pull request. |
| 3. Failure path: the tool fails, returns garbage, or disagrees with the model | 6, 7, 8 | One scene for each of the three, each with a banner naming it. |

## Scenes

### 1. The person (0:00–0:22)

How a vibecoding team really works: nobody reads the code. Each person's agent writes it,
and the lead's agent reviews it. What the agents can't do is reach each other, so a
person carries what one agent said into another agent's chat.

- **Proves:** requirement 1.
- **Picture, the team (6s):** a name card: "Somesh, lead of a vibecoding team. Three
  people. Everyone builds by prompting an AI agent." Agent replies from the test run fill
  the screen, and one line in each lights up: "Tell the team: I chose the routes and the
  JSON fields myself", "so I guessed them", "please confirm it". Caption: "Every agent knew
  what to tell the team. None of them could."
- **Picture, the lead (8s):** the lead asks his own agent to review the team's branches
  against the plan. It answers with a list. He copies the list into the team chat; a
  teammate copies it into their agent. A cost card: "**30 minutes a day. 2.5 hours every
  week.**" (Somesh's own figure, over a five-day week.)
- **Picture, the miss (8s):** a terminal from the no-channel run: the `report` command
  prints `revenue: 940`.
- **On-screen text:** "Test run: five agents, one prompt each, no way to reach the lead."
  Then: "Nothing crashed. The right number is 686."
- **Voiceover:** "On a vibecoding team, nobody reads the code. Agents write it, and agents
  review it. What agents can't do is talk to each other. So the lead carries the messages,
  thirty minutes a day, by hand. When one doesn't get carried, this ships."
- **Careful:** the agent replies and the 940 come from the five-agent test run, not from
  our own team's work. The label has to say so. Copy the "tell the team" lines from
  `experiment-runs/hirebot-pro/N1/logs`.
- **Source:** the lead's part is drawn as a diagram (lead's agent, lead, team chat,
  teammate, their agent), not a screen capture, so it shows the routine without faking a
  chat. The 940 is a live terminal capture of the N1 build before its fix (see recording
  notes). Frame-level detail is in [video-remotion.md](video-remotion.md).
- **Hold** the 940 for two seconds with no voice.

### 2. The hand-off (0:22–0:30)

- **Picture:** the title animation (`Title` scene), with the tagline changed to "Hand off
  the relaying. Keep the deciding."
- **Voiceover:** "Midflight takes that job over. It's the line between the team's agents."

### 3. Setup, and the tools it calls (0:30–0:42)

- **Proves:** requirement 2.
- **Picture:** sped-up live capture: install the GitHub App on the repo, paste the
  connector URL into Claude Code, sign in with GitHub, a join code appears. Then the plan
  as a graph: five tasks (catalog, pricing, bookings, reports, command line) joined by
  seven contracts.
- **On-screen text:** a lower third that stays for the whole scene: "Tools Midflight calls
  that we didn't build: **GitHub API** (reads commits, publishes checks), **Amazon
  Bedrock** (reviews claims)."
- **Voiceover:** "Teammates paste one URL and join with a code. Behind it, two tools we
  didn't build: GitHub, and a reviewer model on Amazon Bedrock."

### 4. It relays the plan change (0:42–1:04)

- **Picture:** the lead approves plan v4: half-hour bookings, and rush orders with a 25%
  fee. Five terminal panes. At each agent's next `check_in`, a directive opens in the
  pricing, bookings, reports, and command-line panes. The catalog pane stays quiet with
  the label "no directive".
- **On-screen text:** "Approved once. Nothing pasted."
- **Voiceover:** "Mid-build, the lead changes the plan. On a vibecoding team, that means
  pasting it into every chat. Here it's approved once. Four agents get it at their next
  check-in. The fifth gets nothing."
- **Source:** rebuilt from the B1 logs. Corner label: "Recorded run, October 9".
- **Careful:** the catalog did see plan v4 and re-confirmed its claim. Say "no directive",
  not "no changes".

### 5. The agents find it; Midflight carries it (1:04–1:34)

The agents do the finding here, as they do today: each one states what it assumes.
Midflight's part is putting two agents' statements next to each other, which today only
happens if a person carries one to the other.

- **Picture, first half:** two teammates' instructions side by side. Bookings: "refund in
  full on cancel". Reports: "keep a 20% fee, and count it as revenue". The two cards
  collide; an escalation goes to the lead's pane. The lead answers: 10%.
- **Picture, second half:** both agents revise, and two new claim cards appear. Bookings:
  "on cancel, `total` becomes the fee kept". Reports: "revenue adds 10% of a cancelled
  booking's `total`". The cards collide again and a finding appears. The lead answers:
  "`total` never changes."
- **On-screen text:** "Midflight doesn't pick a side." Then: "A tenth of a tenth. Caught
  before any code."
- **Voiceover:** "Two teammates prompted opposite rules. Midflight doesn't pick. It asks the
  lead, who decides: ten percent. Then both agents revise, and their new plans would count
  the fee twice. Caught from two claims, before any code."
- **Source:** rebuilt from the B1 logs (escalations E-8 and E-10). Copy the wording from
  `experiment-runs/hirebot-pro/B1/logs`; don't paraphrase it.

### 6. Failure path 1: the tool disagrees with the model (1:34–1:54)

- **Proves:** requirement 3, "disagrees with the model".
- **Banner:** "Failure path 1: GitHub disagrees with the agent".
- **Picture:** the pricing agent says "Done: rush orders are built." It pushes. On the
  pull request, `midflight/verify` turns red, and its summary names the contract field the
  diff is missing. The fix is pushed and the check turns green.
- **Voiceover:** "Now the failures. A vibecoder trusts 'done'. The diff on GitHub says
  otherwise. The diff wins, and the check fails with the reason."
- **Source:** live capture of a real pull request. The wrong push is staged for the
  camera; the check is real. This is not part of the October 9 run, so no corner label.
- **Hold** the red check for two seconds with no voice.

### 7. Failure path 2: the tool fails (1:54–2:12)

- **Proves:** requirement 3, "fails".
- **Banner:** "Failure path 2: GitHub is down", with **SIMULATED** on screen for the whole
  scene.
- **Picture:** the lead calls `simulate_github_outage` with `on`. An agent's next
  `check_in` prints: "WARNING: Midflight's GitHub data is stale (...). New directives are
  held and nothing can be approved until it's fresh." A claim submitted now is not
  approved. The lead switches it off; the held directive is delivered.
- **Voiceover:** "GitHub goes down. Midflight says its data is stale, holds every
  directive, and approves nothing until it's fresh."
- **Source:** live capture against the hosted service.
- **Careful:** don't say an already-green check is revoked. The outage limitation in
  [requirements.md](requirements.md) says Midflight may be unable to update a published
  check while GitHub is down.

### 8. Failure path 3: the tool returns garbage (2:12–2:32)

- **Proves:** requirement 3, "returns garbage".
- **Banner:** "Failure path 3: the reviewer model is wrong".
- **Picture, first half:** a reviewer reply that cites an id that doesn't exist. The claim
  is held with a `reviewer_unavailable` finding: "the reply didn't match the findings
  schema or cited unknown ids". Caption: "A bad reply can't approve anything."
- **Picture, second half:** a real false alarm from the recorded run (E-13). The reviewer
  said that giving hours back on a cancel implies the total changes. The command-line
  agent's own words: "looks like a checker error. It's still Midflight's call, not mine,
  so I stopped." The lead dismisses it.
- **On-screen text:** "October 9 run: 6 of 9 alarms were false."
- **Voiceover:** "The reviewer model gets things wrong too. A malformed reply can never
  approve anything. A wrong one goes to a person, not into the code. In our test run, six
  of nine alarms were false."
- **Source:** first half is the unit test
  `tests/unit/test_bedrock.py::test_a_reply_citing_unknown_ids_is_discarded` running in a
  terminal, labelled "test"; there is no live fault switch for the reviewer. Second half
  is rebuilt from the B1 logs.

### 9. Under the hood (2:32–2:44)

- **Picture:** the `UnderHood` fly-through, each block lighting as a packet passes: AI
  client, one connector URL, AWS Lambda, DynamoDB, its stream, the worker Lambda, Amazon
  Bedrock (Nova Pro); and GitHub App, webhook, check run.
- **Voiceover:** "It runs on AWS Lambda and DynamoDB. The model proposes findings. Rules
  in code decide."

### 10. What the lead gets back (2:44–3:00)

- **Picture:** the project's record: each decision with who made it and why, and a green
  `midflight/verify` on the pull request. Then three lines: "Install the app. Paste one
  URL. Sign in." Then the logo, "Team Yoga", and the three names.
- **Voiceover:** "The agents do the finding. Midflight does the carrying. The lead only
  decides. Midflight, by Team Yoga."

## Voiceover

About 260 words. Record it first, in one sitting, and cut the picture to it. Burn in a
caption for every spoken line. Bring the music down under the voice and back up in the
three silent holds (scenes 1, 6, and the lead's ruling in scene 5).

## Recording notes

| Scene | How to get it |
| --- | --- |
| 1, the 940 | In `experiment-runs/hirebot-pro/N1/main`, commit `6d1e800` is the merged build before the fixer's commit. Add a separate worktree at that commit, start the app, and run checks C7 to C13 from `experiment/cases/hirebot-pro/checks.md`. |
| 3 | Live, with a fresh project so the join code is on screen. |
| 4, 5, 8 (second half) | The October 9 agents ran headless, so there is no screen recording. Rebuild them as Remotion terminals from the logs, with the corner label. |
| 6 | Push a HireBot Pro branch to a repo with the App installed. Pick a field that is in a plan v4 contract, so the check's summary names it. |
| 7 | Live, as the lead, with `simulate_github_outage`. |
| 8 (first half) | `uv run pytest tests/unit/test_bedrock.py -k unknown_ids -v` |

The Remotion scenes `ColdOpen`, `Drift`, `ClaimCheck`, `PlanChange`, `Disagree`, and
`FalseDone` are written around three panes and `total_cents`; they need five panes and the
HireBot text. `Title`, `Outage`, `UnderHood`, and `Close` need only wording changes.

## Open items

- **The cost number in the writeup.** Use the same figure as scene 1: 30 minutes a day,
  2.5 hours a week, spent reading agents' output and relaying changes.
- **"What we fixed" claims.** The fixes for the false alarms and the undelivered
  assumption are on the `S-11-experiment-fixes` branch. Mention them in the video only if
  they are merged and deployed when scene 8 is recorded.
- **The hook promises more than the October 9 run delivered.** Scene 1 says agents' "tell
  the team" notes don't get carried. In that run Midflight carried the plan change and the
  disagreement, but not one agent's assumption about another task (`list_bookings()`),
  which is why its report check failed. Passing assumptions on is part of S-11. If S-11
  isn't deployed, scene 1's caption should be about plan changes and conflicting
  instructions only.
- **Scene 1's routine has to be Somesh's real one.** The storyboard assumes he asks his
  agent to review the branches and then copies its findings into the team chat. Change the
  shots to whatever he really does.
- **The shared-file comparison** (the team chat won both cases) belongs in the writeup,
  with a link to [experiment.md](experiment.md). The video's honest number is the six
  false alarms in scene 8.
