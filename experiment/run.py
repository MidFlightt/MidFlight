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

    with_midflight = state["approach"] == "B"
    if with_midflight:
        warm_up(run)

    def one(indexed: tuple[int, str]) -> tuple[str, dict]:
        index, task = indexed
        if with_midflight:
            time.sleep(20 * index)  # start one at a time, so start-up requests don't pile up
        if number == 1:
            prompt = prompts.first_prompt(state["approach"], task, chat)
            return task, call(run, task, "p1", prompt)
        prompt = prompts.second_prompt(state["approach"], task)
        return task, call(run, task, f"p{number}", prompt, state["sessions"][task])

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, enumerate(BRANCHES)))
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
    args = [claude_exe(), "-p", "--model", MODEL,
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
    for attempt in range(1, 9):
        if run_agent(args, prompt, cwd, log, needs_midflight=use_midflight):
            return summarize(log)
        # Midflight's tools weren't loaded when the agent started: it was stopped before
        # doing any work. Wait and start it again.
        print(f"{task}: Midflight wasn't ready (attempt {attempt}); retrying in 20 s", flush=True)
        time.sleep(20)
    sys.exit(f"{task}: Midflight never initialized; nothing was run")


def run_agent(args: list[str], prompt: str, cwd: Path, log: Path, needs_midflight: bool) -> bool:
    """Run one agent to the end, saving its event stream. With `needs_midflight`, the
    agent is stopped at once (returning False) unless its start-up message lists every
    Midflight tool, so no agent ever works without Midflight by accident."""
    with log.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        assert proc.stdin and proc.stdout
        proc.stdin.write(prompt)
        proc.stdin.close()
        ready = not needs_midflight
        for line in proc.stdout:
            out.write(line)
            if ready:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "system" and event.get("subtype") == "init":
                loaded = set(event.get("tools", []))
                if set(MIDFLIGHT_TOOLS) <= loaded:
                    ready = True
                else:
                    proc.kill()
                    break
        proc.wait()
    return ready


def claude_exe() -> str:
    """The Claude Code program itself (not the .cmd wrapper), so it can be stopped."""
    found = shutil.which("claude") or "claude"
    exe = Path(found).parent / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    return str(exe) if exe.exists() else found


def warm_up(run: str) -> None:
    """Before a Midflight phase: one small call that wakes the server and refreshes the
    sign-in, so three agents starting together don't race to do either."""
    root = RUNS / run
    args = [claude_exe(), "-p", "--model", MODEL, "--max-turns", "3",
            "--output-format", "stream-json", "--verbose", "--strict-mcp-config",
            "--mcp-config", str(HERE / "midflight-only.mcp.json"),
            "--allowedTools", "mcp__midflight-live__my_projects", *MIDFLIGHT_TOOLS]
    log = root / "logs" / f"warmup-{int(time.time())}.jsonl"
    prompt = "Call the Midflight my_projects tool once and reply with one word: ready."
    for attempt in range(1, 6):
        ok = run_agent(args, prompt, root, log, needs_midflight=True)
        if ok:
            print("Midflight is warm and connected", flush=True)
            return
        print(f"warm-up: Midflight not ready (attempt {attempt})", flush=True)
        time.sleep(20)
    sys.exit("Midflight didn't connect during warm-up")


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
    """Totals for a run. Claude Code reports a session's cost cumulatively across
    resumed calls, so cost is the highest value per agent; turns, tokens, and time are
    per call and are summed. Warm-up calls exist only in this harness and are listed
    apart."""
    totals = {"cost": 0.0, "warmup_cost": 0.0, "turns": 0, "input": 0, "output": 0,
              "cache_read": 0, "cache_write": 0, "agent_minutes": 0.0, "tool_calls": 0,
              "midflight_calls": {}, "cost_by_agent": {}}
    for log in sorted((RUNS / run / "logs").glob("*.jsonl")):
        agent = log.name.split("-")[0]
        warmup = agent == "warmup"
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "result":
                usage = event.get("usage", {})
                cost = event.get("total_cost_usd", 0.0) or 0.0
                if warmup:
                    totals["warmup_cost"] += cost
                    continue
                by_agent = totals["cost_by_agent"]
                by_agent[agent] = max(by_agent.get(agent, 0.0), cost)
                if not usage.get("output_tokens"):
                    continue  # a call that did nothing (for example, a usage limit)
                totals["turns"] += event.get("num_turns", 0)
                totals["input"] += usage.get("input_tokens", 0)
                totals["output"] += usage.get("output_tokens", 0)
                totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
                totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
                totals["agent_minutes"] += (event.get("duration_ms", 0) or 0) / 60000
            if event.get("type") == "assistant" and not warmup:
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        totals["tool_calls"] += 1
                        name = block.get("name", "")
                        if name.startswith("mcp__midflight-live__"):
                            short = name.removeprefix("mcp__midflight-live__")
                            totals["midflight_calls"][short] = (
                                totals["midflight_calls"].get(short, 0) + 1
                            )
    totals["cost"] = round(sum(totals["cost_by_agent"].values()), 4)
    totals["agent_minutes"] = round(totals["agent_minutes"], 1)
    print(json.dumps(totals, indent=2))
    state = load_state(run)
    state["stats"] = totals
    save_state(run, state)


def load_state(run: str) -> dict:
    return json.loads((RUNS / run / "state.json").read_text(encoding="utf-8"))


def save_state(run: str, state: dict) -> None:
    (RUNS / run / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # agents write any character
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
