# Experiments

Measured comparisons of three ways a team's AI agents can build one product together.
The findings are written up in [docs/experiment.md](../docs/experiment.md); this folder
has everything needed to check them or run them again.

## The three approaches

| Run letter | Approach | How the agents coordinate |
| --- | --- | --- |
| **N** | No channel | They can't. Each agent only hears from its own developer. |
| **A** | Team chat | A shared `TEAM_CHAT.md` file every agent can read and write. |
| **B** | Midflight | A Midflight plan with contracts; agents claim, check in, and get directives. |

## What's here

| Path | What it is |
| --- | --- |
| `run.py` | The driver: sets up a trial, runs the agents, merges, scores, records |
| `midflight-only.mcp.json` | The MCP configuration run B's agents get: only Midflight |
| `walkthrough.py` | One simulated run of the whole workflow, written to `docs/pages/walkthrough.html` |
| `cases/<case>/README.md` | The case: the product, the parts, the surprises |
| `cases/<case>/case.py` | **The exact words every agent is given**, per approach and phase |
| `cases/<case>/starter/` | The near-empty repository every trial starts from |
| `cases/<case>/checks.md` | The checks, fixed before any trial |
| `cases/<case>/score.py` | The checks as a program (cases scored automatically) |
| `cases/<case>/results/<run>/` | One folder per trial (below) |

### What a results folder holds

| File | Contents |
| --- | --- |
| `summary.json` | Checks passed at merge and after each fix round, cost, turns, tokens, tool calls, Midflight calls, notes |
| `prompts.md` | Every message sent to every agent, in order, word for word |
| `agents.md` | What each agent replied each time, and the tools it used |
| `checks.json` | Every check in every scoring round: the command, what was expected, what came back |
| `team-chat.md` | Run A only: the team chat as the agents left it |

## The cases

| Case | Agents | Scored | What it stresses |
| --- | --- | --- | --- |
| [`hirebot-small`](cases/hirebot-small/README.md) | 3 | by hand, 8 checks | field names between a page and two small APIs |
| [`hirebot-pro`](cases/hirebot-pro/README.md) | 5 | automatically, 14 checks | real business rules, a change touching four parts, a decision only the lead can make |

## Running a trial

Every agent is a headless Claude Code session (`claude -p`), all on the same model, each
in its own git worktree. Run B's agents use the live hosted Midflight, signed in as
whoever runs the trial; the lead's part (approving the plan change, answering
escalations) is done by that person through their own Midflight tools.

```bash
python experiment/run.py hirebot-pro N1 setup
python experiment/run.py hirebot-pro N1 phase 1     # every agent builds
python experiment/run.py hirebot-pro N1 phase 2     # the plan change and developer notes
python experiment/run.py hirebot-pro N1 merge
python experiment/run.py hirebot-pro N1 repair      # score, then fix rounds until all pass
python experiment/run.py hirebot-pro N1 record      # write results/N1/
```

The driver never lets a run B agent work without Midflight: it reads each agent's
start-up message and restarts the agent if Midflight's tools aren't loaded. If the Claude
plan's usage limit is reached, the phase stops and can be run again later; agents that
already finished are skipped.

A trial's working folders live outside the repository, in `../experiment-runs/`.
