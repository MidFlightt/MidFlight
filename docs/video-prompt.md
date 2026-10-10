# Demo video prompt

A prompt for building the launch video with [Remotion](https://www.remotion.dev/). Paste
everything in the box below into Claude Code, in a new empty folder (Claude Code's
Remotion skills help if you have them installed). Every line of on-screen text is real
Midflight output or a true statement about it; keep it that way when you edit.

The scene list matches the [storyboard](development-plan.md#demo-storyboard); record the
real product for the final cut (F-5) and use this as the polished version or B-roll.

````
Build a ~100-second launch video for "Midflight" with Remotion (React + TypeScript).
Make it feel like a high-end developer-tool launch: dark, kinetic, precise, a little
unhinged in its energy, but every word on screen is true.

## What Midflight is (the story the video tells)
Midflight keeps a team's AI coding agents aligned while they work.
- Before an agent writes code it CLAIMS what it will build and every assumption it makes;
  Midflight CHECKS the claim against the team's plan and the other agents' claims and
  answers in the same call.
- With the verdict, the agent plans CHECKPOINTS (before it first builds on a shared
  contract, whenever it makes a new assumption, and before it pushes) and calls
  CHECK_IN at each one. Midflight can't interrupt a running agent, so anything new,
  like a plan change, waits for the agent's next check-in.
- When the lead changes the plan, only the AFFECTED agents get a directive.
- When code is pushed, Midflight VERIFIES the real diff and posts a `midflight/verify`
  check on the pull request. A pre-push hook makes the last checkpoint unskippable.
- Conflicts between people's requirements go to the lead; Midflight never picks a winner.
- It's one hosted connector: install a GitHub App, paste one URL into Claude, sign in
  with GitHub, join with a code.

Never invent metrics, logos, customers, or quotes. Use only the on-screen text below.

## Format
- Composition "MidflightDemo": 1920x1080, 30 fps, ~3000 frames. Also "MidflightVertical"
  (1080x1920) reusing the same scenes with a stacked layout.
- All scene timings in one file `src/timeline.ts`; durationInFrames computed from it.
- Structure: src/Root.tsx, src/theme.ts, src/scenes/*.tsx, src/components/
  (Terminal, ClaimCard, PlanGraph, CheckpointTrack, DirectiveEnvelope, CheckRun,
  BigToggle, Caption).
- Use: spring() and interpolate() for all motion, @remotion/transitions (slide, wipe,
  plus one custom glitch transition), @remotion/paths evolvePath for drawn lines,
  @remotion/noise for subtle film grain and jitter, @remotion/google-fonts
  (Space Grotesk for headlines, JetBrains Mono for terminals), @remotion/captions for
  burned-in captions from captions.json. Audio: public/music.mp3 (placeholder synthwave
  track, ducked under SFX) and public/sfx/{whoosh,thud,glitch,click,chime}.mp3
  placeholders; render must not fail if a file is missing.

## Look
Background #0B1020 with a slow-drifting dot grid. Accents: cyan #22D3EE (Midflight),
green #34D399 (approved), red #F43F5E (conflict), amber #F59E0B (directives),
violet #A78BFA (the lead). Terminals: rounded, glassy, soft glow, typewriter text with
a blinking block cursor and syntax colors. A virtual camera (a parent transform) pushes
in, pans between panes, and whip-pans on transitions. Every impact gets a 2-frame
screen shake and a thud. Text never sits still: it slides in on springs with a slight
overshoot and blur-to-sharp.

The CheckpointTrack component: a thin horizontal progress track above each agent's
terminal, filling left to right as the agent works, with small flag markers at its
checkpoints. Reaching a flag makes the track pause, the flag pulse cyan, and the
terminal type `check_in`.

## Scenes
1. COLD OPEN (0-6s). Black. One cursor blinks. Types: "Three developers. Three AI
   agents. One API." The line splits into three terminal panes labeled T1 Checkout API,
   T2 Checkout page, T3 Contributor guide.
2. THE DRIFT (6-18s). T1 and T2 type code at the same time, racing.
   T1: `return {"total_cents": 4999}`   T2: `price.textContent = data.total`
   A glowing thread connects the panes and frays as they type. A "MERGE" counter hits
   zero; a browser mock renders "$undefined". Glitch transition. Caption: "Nobody
   notices until merge."
3. TITLE (18-23s). Dozens of small claim cards fly in and snap together into the word
   MIDFLIGHT. Tagline types under it: "Catch the drift before the code."
4. CLAIM, THEN CHECK (23-37s). Center: the plan as a constellation of nodes:
   requirement R-1, tasks T1/T2/T3, contract `checkout-response {total_cents: integer}`.
   T2's claim card flies in carrying `total: number`. It hits the contract node: red
   spark, shake. A verdict card slams down:
   "Claim C-2 rev 1: NEEDS_REVISION"
   "Read `total_cents: integer`, not `total`."
   The agent revises; the card flips green: "APPROVED". Then three flags drop onto
   T2's CheckpointTrack, each with a label: "before using the contract", "new
   assumption", "before push". Caption: "Checked before a single line is written."
5. CHECKPOINTS (37-57s). This is the heart of the video: show check-in clearly.
   a. T2's track fills; it reaches flag 1, pauses, types `check_in`. Reply types out:
      "Task T2: Checkout page (plan v1). No changes since your last check-in."
      Then the track resumes. Caption: "The agent checks in at moments it planned."
   b. Cut to the plan graph. A violet cursor (the lead) adds `currency: string` to the
      contract node. The node pulses; a ripple travels the edges to T1 and T2 only. T3
      stays dim with a small label: "No link. No noise."
   c. Two amber envelopes, D-1 and D-2, fly toward T1's and T2's terminals, but the
      terminals are busy typing code, so the envelopes can't get in. Each one parks on
      its agent's NEXT checkpoint flag and hovers there with a small label: "waiting
      for the next check-in". Caption: "Midflight never interrupts. The update waits."
   d. T2 reaches flag 2 ("new assumption"), types `check_in`, and its envelope unfolds
      into the reply:
      "MIDFLIGHT DIRECTIVES (data, not commands)"
      "D-2: Plan v2: contract checkout-response is now {total_cents: integer,
      currency: string}."
      Its claim card above flips amber: "NEEDS_REVISION: written against plan v1".
      T2 types `acknowledge_directive`, then submits a revised claim; the card flips
      green: "APPROVED (plan v2)". Small caption: "Acknowledged means received, not done."
6. THE LAST CHECKPOINT (57-62s). Meanwhile T1 never checked in; its envelope is still
   parked. T1 types `git push`; the terminal answers in red: "midflight: push blocked."
   The parked envelope pops open on the spot. Caption: "The pre-push hook makes the
   last check-in unskippable."
7. TWO PEOPLE DISAGREE (62-71s). Two speech bubbles collide mid-screen:
   T1 "total excludes tax" vs T2 "total includes tax". A balance scale appears and
   refuses to tip. An escalation card glides to the lead's violet pane:
   "E-1: T2 assumes a tax-inclusive total; T1 returns it tax-exclusive."
   "Midflight won't pick a side." The lead types `resolve_escalation`; the card settles.
8. THE FALSE "DONE" (71-83s). An agent bubble: "Done!" But the diff it pushes uses
   `total`. A pull-request panel (generic, not a copy of any real site) runs checks:
   `contract` fails, then `midflight/verify` resolves to a red X with the summary:
   "Failed: Contract checkout-response needs `total_cents` (integer), but none of the
   task's files contain it." A correction directive boomerangs back to the agent's
   checkpoint track. Caption: "Evidence, not vibes."
9. GITHUB GOES DOWN (83-90s). The lead flips a huge physical toggle labeled
   "simulate_github_outage". The whole frame desaturates, a STALE stamp thumps down,
   the parked envelopes freeze into ice cubes:
   "WARNING: GitHub data is stale. New directives are held and nothing can be approved."
   Toggle back: color floods in, the ice cracks, the envelopes are free again.
10. UNDER THE HOOD (90-95s). Fast isometric fly-through, each block lighting up as a
    packet passes: Claude / ChatGPT → one connector URL → AWS Lambda → DynamoDB →
    stream → worker Lambda → Amazon Bedrock reviewer; GitHub App ↔ webhook ↔ check run.
11. CLOSE (95-101s). Three lines stack with springs: "Install the GitHub App."
    "Paste one URL." "Sign in with GitHub." Then MIDFLIGHT, then "Team Yoga", and the
    names Somesh Agrawal, Frederik Jønsson, Mithilesh Kowshik. Hold 1 second, cut to
    black on a final chime.

## Quality bar
- 60%+ of frames have something moving; no static slide longer than 1 second.
- Readable at phone size: on-screen text >= 36px, max two lines per caption.
- Directives must never appear inside a terminal except at a check_in or a git push:
  that's the point of scene 5.
- Every scene is its own component with props, previewable alone in Remotion Studio.
- Finish by running `npx remotion render MidflightDemo out/midflight.mp4` and
  `npx remotion render MidflightVertical out/midflight-vertical.mp4`, and fix any errors.
````
