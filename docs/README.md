# Documentation

Everything in this folder, grouped by what you came for. The project's front page is the
[README](../README.md).

## Start here

| Document | What it covers |
| --- | --- |
| [code-guide.md](code-guide.md) | How the code is organized, file by file, and what happens when people use it |
| [architecture.md](architecture.md) | Where everything runs on AWS, with sequence diagrams |
| [pages/walkthrough.html](pages/walkthrough.html) | One simulated run, step by step: what each agent told Midflight and what it answered (open in a browser after cloning) |

## What we measured

| Document | What it covers |
| --- | --- |
| [experiment.md](experiment.md) | HireBot and HireBot Pro: no channel, a shared team chat, and Midflight on the same task; what the runs found wrong with Midflight, and the rerun after the fixes |
| [benchmark-pigeonpost.md](benchmark-pigeonpost.md) | PigeonPost: six agents on separate laptops and six things that happen after the plan is written |
| [benchmark-pigeonpost-markers.md](benchmark-pigeonpost-markers.md) | PigeonPost again after check-in markers (S-13): same result, less text and cost |
| [../evals/results.md](../evals/results.md) | The AI reviewer measured on the experiment's own escalations, by model |
| [../experiment/README.md](../experiment/README.md) | The driver, the cases, and every recorded prompt, reply, and check |

## Reference

| Document | What it covers |
| --- | --- |
| [domain.md](domain.md) | Exact names, states, MCP tools, REST paths, and invariants |
| [use-cases.md](use-cases.md) | UC-01 to UC-16 with sequence diagrams ([visual version](pages/use-cases.html)) |
| [requirements.md](requirements.md) | Requirements, demo scenarios, definition of done |
| [design-decisions.md](design-decisions.md) | Decisions D1 to D34 and open questions |
| [pages/scenarios.html](pages/scenarios.html) | Every demo scenario traced through the code, written by `tests/scenario_report.py` |

## Try it with a teammate

| Document | What it covers |
| --- | --- |
| [guides/pigeonpost-with-a-friend.md](guides/pigeonpost-with-a-friend.md) | Two people, one repository, six parts: building PigeonPost with Midflight in about two hours |
| [guides/pigeonpost-lead-prompts.md](guides/pigeonpost-lead-prompts.md) | The lead's prompts, in order, for Claude Code |
| [guides/pigeonpost-codex-prompts.md](guides/pigeonpost-codex-prompts.md) | The teammate's prompts, in order, for Codex |
| [guides/pigeonpost-demo-script.md](guides/pigeonpost-demo-script.md) | A short repeatable demo of three Midflight moments on PigeonPost |

## Demo and video

| Document | What it covers |
| --- | --- |
| [demo.md](demo.md) | The acceptance scenarios on the small checkout project |
| [video/video-storyboard.md](video/video-storyboard.md) | Storyboard of the 3:00 submission video |
| [video/video-remotion.md](video/video-remotion.md) | The Remotion build sheet for that storyboard |
| [video/video-prompt.md](video/video-prompt.md) | Prompt that builds the earlier 100-second launch video |
| [video/benchmark-explainer-script.md](video/benchmark-explainer-script.md) | Spoken script explaining the PigeonPost benchmark |

## How we built it

| Document | What it covers |
| --- | --- |
| [development-plan.md](development-plan.md) | Tasks, owners, and gates for the hackathon week ([visual version](pages/development-plan.html)) |
| [step-by-step.md](step-by-step.md) | Each team member's steps during the build |
| [archive/](archive/) | Earlier design notes. Superseded where they disagree with the files above |
