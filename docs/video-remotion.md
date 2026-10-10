# Remotion build sheet for the 3:00 video

The exact build of [video-storyboard.md](video-storyboard.md) in
[Remotion](https://www.remotion.dev/). The storyboard says what each scene proves and
where its text comes from; this page says what is on screen at which frame.

The project is the `midflight-video` folder next to this repository. The new video lives
in `src/handoff/`, beside the older 100-second launch video, which stays as it is.

**Built so far:** scene 1, beats 1 to 4 (the first 15 seconds). Composition `HandoffHook`,
file `src/handoff/Hook.tsx`, rendered to `out/handoff-hook.mp4`.

## Format

| | |
| --- | --- |
| Size | 1920 × 1080 |
| Frame rate | 30 fps |
| Length | 5400 frames (3:00) |
| Main composition | `Handoff` (to add once every scene exists) |
| Scene compositions | one per scene in the Studio folder `Handoff`, so each can be previewed alone |

## Look: clean

The launch video was loud on purpose: screen shake, glitch cuts, film grain, a drifting
grid. This one is the opposite.

| Rule | Value |
| --- | --- |
| Background | flat `#0B1020`, with one soft cyan light fixed at the top left. No grid, grain, or vignette. |
| Text | `#E6EAF2`; secondary `#94A3B8`; source labels `#64748B` |
| Cyan `#22D3EE` | agents, and Midflight |
| Amber `#F59E0B` | work a person does by hand, and the thing being carried |
| Violet `#A78BFA` | the lead's decisions |
| Red `#F43F5E` | wrong results only: the 940, a failed check |
| Green `#34D399` | a passed check only |
| Panels | `#111933`, 1px border `rgba(148,163,184,0.22)`, corner radius 24, no glow |
| Headline | Space Grotesk 700, 88px, at left 120, top 120. One line. |
| Big number | Space Grotesk 700, 164px |
| Body | Space Grotesk 500, 34 to 60px |
| Agent and terminal text | JetBrains Mono, 34px, line height 1.5 |
| Smallest text | 28px (pills and source labels) |
| Safe area | 120px left and right, 100px top and bottom |

Motion:

- **Enter:** fade in over 14 frames while rising 24 to 32px, easing
  `Easing.bezier(0.16, 1, 0.3, 1)`. No overshoot.
- **Leave:** fade out over 10 to 12 frames. Nothing flies off screen.
- **Travel** (a message moving, a group shifting): `Easing.bezier(0.65, 0, 0.35, 1)`.
- **One thing moves at a time.** Stagger siblings by 6 to 8 frames.
- **Between scenes:** a 12-frame fade through the background color. No slides, wipes, or
  glitches.
- **Holds:** the three silent holds (the 940, the red check, the lead's ruling) are 60
  frames with nothing moving.

The headline is the narration. Each headline is the spoken line, or a shorter form of it,
so the video reads with the sound off and needs no separate caption strip.

## Code rules

From the Remotion skill, so every value can be edited in Studio:

- Animate with `useCurrentFrame()` and `interpolate()`, written inline in the `style`
  prop with hardcoded keyframes. No CSS transitions.
- Use the `scale`, `translate`, and `rotate` properties, not a `transform` string.
- Wrap each element worth editing in `Interactive.Div` with a fixed `name`.
- Stagger with `<Sequence from={n} layout="none">`, so a child's frame 0 is its entrance.
- Screen recordings go in `public/` and play through `<Video>` from `@remotion/media`.

Shared parts in `src/handoff/parts.tsx`: `Mark` (a marker swept behind a phrase),
`AgentGlyph`, `PersonGlyph`, `ChatGlyph`. To add as scenes need them: `Window` (a plain
frame around a screen recording, with a crop and a slow push-in), `Banner` (the failure
path label), `SourceLabel`, `CheckRow`.

## Timeline

| # | Scene | Composition | Starts | Frames | Seconds |
| --- | --- | --- | --- | --- | --- |
| 1 | The person | `HandoffHook` + `HandoffMiss` | 0 | 660 | 0:00–0:22 |
| 2 | The hand-off | `HandoffTitle` | 660 | 240 | 0:22–0:30 |
| 3 | Setup and tools | `HandoffSetup` | 900 | 360 | 0:30–0:42 |
| 4 | The plan change | `HandoffPlanChange` | 1260 | 660 | 0:42–1:04 |
| 5 | Agents find it, Midflight carries it | `HandoffCarry` | 1920 | 900 | 1:04–1:34 |
| 6 | Failure 1: disagrees | `HandoffFailDisagree` | 2820 | 600 | 1:34–1:54 |
| 7 | Failure 2: fails | `HandoffFailOutage` | 3420 | 540 | 1:54–2:12 |
| 8 | Failure 3: garbage | `HandoffFailGarbage` | 3960 | 600 | 2:12–2:32 |
| 9 | Under the hood | `HandoffUnderHood` | 4560 | 360 | 2:32–2:44 |
| 10 | What the lead gets back | `HandoffClose` | 4920 | 480 | 2:44–3:00 |

Frames below are counted from the start of each scene.

## Scene 1: the person (660 frames)

Beats 1 to 4 are built. Beat 5 is next.

| Beat | Frames | On screen |
| --- | --- | --- |
| 1. Premise | 0–75 | Left-aligned, vertically centered. Cyan line, 38px: "Somesh leads a vibecoding team of three" (in at 4). Two 108px lines: "On a vibecoding team," in grey (in at 10), "nobody reads the code." in white (in at 18). All out at 64–75. |
| 2. Agents | 75–150 | Headline: "Agents write it. Agents review it." Three reply cards rise in at 85, 93, 101: 540 × 470, at left 120, 690, 1260, top 340. Each has a cyan dot, the agent's name, and its real words in mono. Source label at 105, bottom left: "From our test run: five agents, one prompt each". |
| 3. They can't talk | 150–240 | Headline cross-fades to "But they can't talk to each other." An amber marker sweeps behind one phrase per card, at 169, 181, 193: "Tell the team:", "please confirm it.", "so I guessed them." All out at 229–240. |
| 4. Relay and cost | 240–450 | Headline: "So the lead carries the messages." Five stops on one line, at x 240, 600, 960, 1320, 1680: Lead's agent, Lead, Team chat, Teammate, Their agent. Agents are cyan squares, people amber circles. An amber message chip travels above them: it leaves at 276, waits on the Lead 294–304, passes the chat at 322, waits on the Teammate 340–350, arrives at 368. A "by hand" pill appears under each person when the chip reaches them. At 375 the chain dims to 25% and drops 190px; "30 minutes a day." (164px, the number in amber) comes in at 383, and "2.5 hours every week, by hand." (60px) at 397. Hold to 450. |
| 5. The miss | 450–660 | Fade to a terminal `Window` showing the real `report` output from the no-channel build. Push in slowly on `revenue: 940`, which turns red at 510. Label: "Test run: five agents, one prompt each, no way to reach the lead." At 540: "Nothing crashed. The right number is 686." Hold 600–660. |

Card text, copied from the run's logs:

- **Catalog agent:** "Tell the team: I chose the routes … and the JSON fields … myself,
  because the README doesn't define them."
- **Reports agent:** "… a cancelled booking earns nothing. The README doesn't say this, so
  please confirm it."
- **Command-line agent:** "Team note: README.md doesn't define the HTTP routes or JSON
  shapes … so I guessed them."

## Scene 2: the hand-off (240 frames)

| Frames | On screen |
| --- | --- |
| 0–60 | The relay chain from scene 1 returns at full strength, centered. |
| 60–120 | The two people and the team chat fade out. A cyan line draws straight from "Lead's agent" to "Their agent", and a cyan node labelled "Midflight" appears at its middle. The amber chip crosses in 20 frames without stopping. |
| 120–240 | The chain shrinks to the top third. Wordmark "Midflight", 164px, then the 60px line "Hand off the relaying. Keep the deciding." |

## Scene 3: setup and the tools it calls (360 frames)

| Frames | On screen |
| --- | --- |
| 0–210 | Headline: "One URL. One join code." A `Window` plays the sped-up screen recording: the GitHub App install, the connector URL pasted into Claude Code, sign-in, the join code. Crop to the part that matters in each step. |
| 30–360 | A lower third stays for the whole scene, two cyan pills: "GitHub API: reads commits, publishes checks" and "Amazon Bedrock: reviews claims". Above them, in grey 28px: "Tools Midflight calls that we didn't build". |
| 210–360 | The window gives way to the plan: five task nodes in a row (Catalog, Pricing, Bookings, Reports, Command line), with seven thin contract lines drawn between them one at a time, 8 frames apart. |

## Scene 4: the plan change (660 frames)

Corner label for the whole scene: "Recorded run, October 9".

| Frames | On screen |
| --- | --- |
| 0–150 | Headline: "The lead changes the plan once." The five task nodes sit in a row. Above them, a violet card for the lead: "Plan v4: half-hour bookings. Rush orders, 25% fee." A violet "Approved" pill appears at 110. |
| 150–420 | Four amber chips leave the lead's card, one every 20 frames, and each stops above its node: Pricing, Bookings, Reports, Command line. Each waits until a small "check-in" tick appears on that node, then drops in, and the node's border turns amber. |
| 300–420 | The Catalog node stays grey. Under it: "no directive". |
| 420–660 | Headline changes to "Four agents get it. The fifth gets nothing." Under the row, 60px: "Approved once. Nothing pasted." Hold from 560. |

## Scene 5: the agents find it, Midflight carries it (900 frames)

Corner label: "Recorded run, October 9".

| Frames | On screen |
| --- | --- |
| 0–210 | Headline: "Two teammates prompted opposite rules." Two cards, left and right: Bookings, "refund in full on cancel"; Reports, "keep a 20% fee, and count it as revenue". At 120 a thin red line joins them and a cyan Midflight node appears between them. |
| 210–390 | Headline: "Midflight doesn't pick. It asks the lead." A chip rises from the Midflight node to a violet lead card at the top. The lead's answer types in: "10%". Hold 330–390, nothing moving. |
| 390–660 | Both cards update. Bookings: "on cancel, `total` becomes the fee kept". Reports: "revenue adds 10% of a cancelled booking's `total`". The red line returns at 520. Between the cards, in red, 60px: "A tenth of a tenth." |
| 660–900 | The lead card answers: "`total` never changes." Both cards turn green. Headline: "Caught from two claims, before any code." Hold from 810. |

## Scene 6: failure 1, the tool disagrees with the model (600 frames)

| Frames | On screen |
| --- | --- |
| 0–90 | `Banner`, full width, top: "Failure path 1: GitHub disagrees with the agent". It shrinks to a tab at the top left and stays. |
| 90–240 | Left half: a card with the agent's words, "Done: rush orders are built." Right half: a `Window` with the pull request recording, checks running. |
| 240–420 | The window takes the full width and pushes in on the `midflight/verify` row as it turns red, with its summary line. Hold 330–390, no voice. |
| 420–600 | The fix is pushed; the row turns green. Headline: "The diff wins." |

## Scene 7: failure 2, the tool fails (540 frames)

A red-outlined "SIMULATED" tag sits at the top right for the whole scene.

| Frames | On screen |
| --- | --- |
| 0–75 | `Banner`: "Failure path 2: GitHub is down". Shrinks to a tab. |
| 75–210 | `Window`: the lead calls `simulate_github_outage` with `on`. The GitHub pill from scene 3 appears beside it and turns grey with a line through it. |
| 210–390 | `Window`: an agent's `check_in` reply. A `Mark` sweeps behind "GitHub data is stale" and then "nothing can be approved until it's fresh". An amber chip sits beside the window with the label "held". |
| 390–540 | The switch goes `off`. The pill turns cyan again and the chip drops into the window. Headline: "Unknown stays unknown." |

## Scene 8: failure 3, the tool returns garbage (600 frames)

| Frames | On screen |
| --- | --- |
| 0–75 | `Banner`: "Failure path 3: the reviewer model is wrong". Shrinks to a tab. |
| 75–270 | Left: a card for the reviewer's reply, with an id that doesn't exist marked in red. Right: a `Window` with the unit test passing, labelled "test". Between them: "A bad reply can't approve anything." |
| 270–480 | Corner label "Recorded run, October 9". A card with the reviewer's false alarm, and under it the command-line agent's own words: "looks like a checker error. It's still Midflight's call, not mine, so I stopped." A violet lead pill: "Dismissed". |
| 480–600 | Big number: "6 of 9", 164px, with the 60px line "alarms in that run were false." Hold. |

## Scene 9: under the hood (360 frames)

| Frames | On screen |
| --- | --- |
| 0–240 | One row of blocks, drawn left to right, 30 frames apart: AI client, Connector URL, AWS Lambda, DynamoDB, Stream, Worker Lambda, Amazon Bedrock (Nova Pro). A cyan dot travels the row once. |
| 150–300 | A second row under it: GitHub App, Webhook, Check run, joined to the Lambda blocks by two thin lines. |
| 240–360 | Headline: "The model proposes. Rules in code decide." |

## Scene 10: what the lead gets back (480 frames)

| Frames | On screen |
| --- | --- |
| 0–210 | Headline: "The lead only decides." Three rows fade in, 40 frames apart: the plan change (who approved it), the 10% ruling (who decided, and why), a green `midflight/verify` row. |
| 210–360 | Three 60px lines, one at a time: "Install the app." "Paste one URL." "Sign in." |
| 360–480 | Wordmark "Midflight", then "Team Yoga" and the three names. The last 30 frames fade to the background color. |

## Commands

Run from the `midflight-video` folder.

```bash
npm run dev
```

```bash
node scripts/stills.mjs HandoffHook 40,215,345,449
```

```bash
npx remotion render HandoffHook out/handoff-hook.mp4
```
