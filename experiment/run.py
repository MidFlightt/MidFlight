"""Run one trial of the experiment (docs/experiment.md), step by step.

    python experiment/run.py setup A1        # fresh repo, one branch and folder per agent
    python experiment/run.py phase A1 1      # the three agents build, in parallel
    python experiment/run.py phase A1 2      # the plan change and the developer notes
    python experiment/run.py say A1 t2 "..." # one more message to one agent
    python experiment/run.py merge A1        # merge the three branches
    python experiment/run.py fix A1 "..."    # the fixer agent repairs failing checks
    python experiment/run.py stats A1        # tokens, cost, turns, tool calls

A run named A... uses the usual approach; B... uses Midflight. Runs live in
../experiment-runs/<run>/. Every agent is a headless Claude Code session on the same
model; each call's full event stream is saved in logs/ for the numbers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import prompts

HERE = Path(__file__).resolve().parent
RUNS = HERE.parents[1] / "experiment-runs"
MODEL = "sonnet"
MAX_TURNS = "40"
BRANCHES = {"t1": "t1-catalog", "t2": "t2-hiring", "t3": "t3-storefront"}
TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(uv run:*)", "Bash(python:*)", "Bash(curl:*)", "Bash(ls:*)", "Bash(cat:*)",
    "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)", "Bash(git diff:*)",
    "Bash(git log:*)", "Bash(git rev-parse:*)", "Bash(git branch:*)",
]
MIDFLIGHT_TOOLS = [
    f"mcp__midflight-live__{name}"
    for name in ("check_in", "submit_claim", "acknowledge_directive", "project_status")
]


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def setup(run: str) -> None:
    root = RUNS / run
    if root.exists():
        sys.exit(f"{root} already exists")
    main = root / "main"
    shutil.copytree(HERE / "starter", main)
    git(main, "init", "-q", "-b", "main")
    git(main, "add", "-A")
    git(main, "-c", "user.name=HireBot", "-c", "user.email=hirebot@example.com",
        "commit", "-q", "-m", "HireBot starter")
    for task, branch in BRANCHES.items():
        git(main, "worktree", "add", "-q", "-b", branch, str(root / task))
    (root / "logs").mkdir()
    (root / "TEAM_CHAT.md").write_text("# HireBot team chat\n\n", encoding="utf-8")
    save_state(run, {"approach": run[0], "sessions": {}})
    print(f"set up {root}")


def phase(run: str, number: int) -> None:
    state = load_state(run)
    chat = str(RUNS / run / "TEAM_CHAT.md")

    def one(task: str) -> tuple[str, dict]:
        if number == 1:
            prompt = prompts.first_prompt(state["approach"], task, chat)
            return task, call(run, task, f"p1", prompt)
        prompt = prompts.second_prompt(state["approach"], task)
        return task, call(run, task, f"p{number}", prompt, state["sessions"][task])

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, BRANCHES))
    for task, result in results:
        state["sessions"][task] = result["session_id"]
        print(f"{task}: {result['num_turns']} turns, ${result['cost']:.2f}: "
              f"{result['text'][-300:]}")
    save_state(run, state)


def say(run: str, task: str, message: str) -> None:
    state = load_state(run)
    label = f"say{int(time.time())}"
    result = call(run, task, label, message, state["sessions"][task])
    print(f"{task}: {result['num_turns']} turns, ${result['cost']:.2f}: {result['text'][-400:]}")


def merge(run: str) -> None:
    main = RUNS / run / "main"
    report = []
    for task, branch in BRANCHES.items():
        done = git(main, "-c", "user.name=HireBot", "-c", "user.email=hirebot@example.com",
                   "merge", "--no-edit", branch, check=False)
        if done.returncode != 0:
            conflicted = git(main, "diff", "--name-only", "--diff-filter=U").stdout.split()
            git(main, "add", "-A")
            git(main, "-c", "user.name=HireBot", "-c", "user.email=hirebot@example.com",
                "commit", "-q", "-m", f"merge {branch} (conflicts left for the fixer)")
            report.append(f"{branch}: CONFLICT in {', '.join(conflicted)}")
        else:
            report.append(f"{branch}: merged")
    print("\n".join(report))
    state = load_state(run)
    state["merge"] = report
    save_state(run, state)


def fix(run: str, message: str) -> None:
    state = load_state(run)
    label = f"fix{len([k for k in state if k.startswith('fix')]) + 1}"
    session = state.get("fixer")
    prompt = message if session else (
        "You are fixing HireBot (read README.md) after three parts, built separately by "
        "three agents, were merged. Make the app work as a whole. " + message +
        " Commit when done and finish with a two-line summary."
    )
    result = call(run, "main", label, prompt, session, midflight=False)
    state["fixer"] = result["session_id"]
    state[label] = True
    save_state(run, state)
    print(f"fixer: {result['num_turns']} turns, ${result['cost']:.2f}: {result['text'][-400:]}")


def call(run: str, task: str, label: str, prompt: str, session: str | None = None,
         midflight: bool | None = None) -> dict:
    """One headless Claude Code call in the task's folder; the stream is saved to logs/."""
    state = load_state(run)
    use_midflight = state["approach"] == "B" if midflight is None else midflight
    args = [shutil.which("claude") or "claude", "-p", "--model", MODEL,
            "--max-turns", MAX_TURNS, "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits",
            "--allowedTools", *TOOLS, *(MIDFLIGHT_TOOLS if use_midflight else [])]
    # Only the MCP servers named here: none for approach A, only Midflight for B (other
    # servers slow the start, and Midflight must be connected before the first turn).
    args += ["--strict-mcp-config"]
    if use_midflight:
        args += ["--mcp-config", str(HERE / "midflight-only.mcp.json")]
    if session:
        args += ["--resume", session]
    cwd = RUNS / run / task
    log = RUNS / run / "logs" / f"{task}-{label}.jsonl"
    with log.open("w", encoding="utf-8") as out:
        subprocess.run(args, input=prompt, cwd=cwd, stdout=out, stderr=subprocess.STDOUT,
                       text=True, encoding="utf-8", timeout=3600)
    return summarize(log)


def summarize(log: Path) -> dict:
    result: dict = {"session_id": None, "num_turns": 0, "cost": 0.0, "text": "", "usage": {}}
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            result.update(
                session_id=event.get("session_id"),
                num_turns=event.get("num_turns", 0),
                cost=event.get("total_cost_usd", 0.0) or 0.0,
                text=event.get("result", "") or "",
                usage=event.get("usage", {}),
            )
        elif event.get("session_id") and not result["session_id"]:
            result["session_id"] = event["session_id"]
    return result


def stats(run: str) -> None:
    totals = {"cost": 0.0, "turns": 0, "input": 0, "output": 0, "cache_read": 0,
              "cache_write": 0, "tool_calls": 0, "midflight_calls": {}}
    for log in sorted((RUNS / run / "logs").glob("*.jsonl")):
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "result":
                usage = event.get("usage", {})
                totals["cost"] += event.get("total_cost_usd", 0.0) or 0.0
                totals["turns"] += event.get("num_turns", 0)
                totals["input"] += usage.get("input_tokens", 0)
                totals["output"] += usage.get("output_tokens", 0)
                totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
                totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
            if event.get("type") == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        totals["tool_calls"] += 1
                        name = block.get("name", "")
                        if name.startswith("mcp__midflight-live__"):
                            short = name.removeprefix("mcp__midflight-live__")
                            totals["midflight_calls"][short] = (
                                totals["midflight_calls"].get(short, 0) + 1
                            )
    print(json.dumps(totals, indent=2))
    state = load_state(run)
    state["stats"] = totals
    save_state(run, state)


def load_state(run: str) -> dict:
    return json.loads((RUNS / run / "state.json").read_text(encoding="utf-8"))


def save_state(run: str, state: dict) -> None:
    (RUNS / run / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


if __name__ == "__main__":
    command, run, *rest = sys.argv[1:]
    match command:
        case "setup":
            setup(run)
        case "phase":
            phase(run, int(rest[0]))
        case "say":
            say(run, rest[0], rest[1])
        case "merge":
            merge(run)
        case "fix":
            fix(run, rest[0])
        case "stats":
            stats(run)
        case _:
            sys.exit(__doc__)
