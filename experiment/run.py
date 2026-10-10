"""Run one trial of an experiment case, step by step (see experiment/README.md).

    python experiment/run.py <case> <run> <step> [args]

    setup              a fresh repo with one branch and folder per agent
    phase 1            every agent builds its first version, in parallel
    phase 2            the surprises (plan change, developer notes)
    say <agent> "..."  one more message to one agent
    merge              merge every agent's branch into main
    score              run the case's checks (cases with a score.py)
    fix "..."          the fixer agent repairs what the message describes
    repair             score, then fix the failing checks, up to 3 rounds
    stats              tokens, cost, turns, tool calls
    record             write the run's results into the case's results/ folder

The run's first letter picks the approach: N (no channel), A (shared team-chat file),
B (Midflight). Runs live outside the repository, in ../experiment-runs/<case>/<run>/.
Every agent is a headless Claude Code session on the same model. Each message sent to an
agent is saved in the run's prompts/ folder, and each call's event stream in logs/.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
RUNS = HERE.parents[1] / "experiment-runs"
MODEL = "sonnet"
MAX_TURNS = "50"
MAX_FIX_ROUNDS = 3
TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(uv run:*)", "Bash(python:*)", "Bash(curl:*)", "Bash(ls:*)", "Bash(cat:*)",
    "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)", "Bash(git diff:*)",
    "Bash(git log:*)", "Bash(git rev-parse:*)", "Bash(git branch:*)",
]  # fmt: skip
MIDFLIGHT_TOOLS = [
    f"mcp__midflight-live__{name}"
    for name in ("check_in", "submit_claim", "acknowledge_directive", "project_status")
]
GIT_ID = ["-c", "user.name=HireBot", "-c", "user.email=hirebot@example.com"]
LIMIT_TEXT = "hit your session limit"
STATE_LOCK = threading.Lock()  # agents run in parallel threads and share one state file


class UsageLimit(Exception):
    """The Claude plan's usage limit was reached; nothing more can run until it resets."""


class Trial:
    """One run of one case: where it lives, its case definition, and its saved state."""

    def __init__(self, case: str, run: str) -> None:
        self.case_name, self.run = case, run
        self.case_dir = HERE / "cases" / case
        self.root = RUNS / case / run
        self.approach = run[0]
        self.case = load_module(self.case_dir / "case.py", f"case_{case.replace('-', '_')}")

    @property
    def agents(self) -> dict[str, str]:
        return self.case.BRANCHES  # agent -> branch

    @property
    def with_midflight(self) -> bool:
        return self.approach == "B"

    @property
    def chat(self) -> Path:
        return self.root / "TEAM_CHAT.md"

    def state(self) -> dict:
        return json.loads((self.root / "state.json").read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        (self.root / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


# Steps ---------------------------------------------------------------------------------


def setup(trial: Trial) -> None:
    if trial.root.exists():
        sys.exit(f"{trial.root} already exists")
    main = trial.root / "main"
    shutil.copytree(trial.case_dir / "starter", main)
    git(main, "init", "-q", "-b", "main")
    git(main, "add", "-A")
    git(main, *GIT_ID, "commit", "-q", "-m", "starter")
    for agent, branch in trial.agents.items():
        git(main, "worktree", "add", "-q", "-b", branch, str(trial.root / agent))
    for folder in ("logs", "prompts"):
        (trial.root / folder).mkdir()
    trial.chat.write_text("# Team chat\n\n", encoding="utf-8")
    trial.save({"approach": trial.approach, "sessions": {}, "calls": [], "done": {}})
    print(f"set up {trial.root}")


def phase(trial: Trial, number: int) -> None:
    """Every agent gets this phase's message. Agents that already finished it are skipped,
    so a phase interrupted by the usage limit can simply be run again."""
    state = trial.state()
    label = f"p{number}"
    todo = [a for a in trial.agents if not state["done"].get(label, {}).get(a)]
    if not todo:
        print(f"phase {number}: every agent already finished it")
        return
    if trial.with_midflight:
        warm_up(trial)

    def one(indexed: tuple[int, str]) -> tuple[str, dict | None]:
        index, agent = indexed
        if trial.with_midflight:
            time.sleep(20 * index)  # one at a time, so start-up requests don't pile up
        if number == 1:
            prompt = trial.case.first_prompt(trial.approach, agent, str(trial.chat))
        else:
            prompt = trial.case.second_prompt(trial.approach, agent)
        try:
            return agent, call(trial, agent, label, prompt)
        except UsageLimit:
            return agent, None

    with ThreadPoolExecutor(max_workers=len(todo)) as pool:
        results = list(pool.map(one, enumerate(todo)))
    blocked = [agent for agent, result in results if result is None]
    for agent, result in results:
        if result:
            print(f"{agent}: {result['num_turns']} turns: {result['text'][-260:]}")
    if blocked:
        sys.exit(f"USAGE LIMIT: {', '.join(blocked)} didn't run. Run this phase again later.")


def say(trial: Trial, agent: str, message: str) -> None:
    result = call(trial, agent, f"say{int(time.time())}", message)
    print(f"{agent}: {result['num_turns']} turns: {result['text'][-400:]}")


def merge(trial: Trial) -> None:
    main = trial.root / "main"
    report = []
    for branch in trial.agents.values():
        done = git(main, *GIT_ID, "merge", "--no-edit", branch, check=False)
        if done.returncode != 0:
            conflicted = git(main, "diff", "--name-only", "--diff-filter=U").stdout.split()
            git(main, "add", "-A")
            git(main, *GIT_ID, "commit", "-q", "-m", f"merge {branch} (conflicts left in)")
            report.append(f"{branch}: CONFLICT in {', '.join(conflicted)}")
        else:
            report.append(f"{branch}: merged")
    print("\n".join(report))
    state = trial.state()
    state["merge"] = report
    trial.save(state)


def score(trial: Trial) -> dict:
    """Run the case's checks against the merged app and save the result."""
    scorer = load_module(trial.case_dir / "score.py", "scorer")
    result = scorer.score(trial.root / "main")
    state = trial.state()
    rounds = state.setdefault("scores", [])
    rounds.append(result)
    trial.save(state)
    passed = sum(c["passed"] for c in result["checks"])
    print(f"score (after {len(rounds) - 1} fix round(s)): {passed} of {len(result['checks'])}")
    for check in result["checks"]:
        if not check["passed"]:
            print(f"  FAIL {check['id']} {check['name']}: {check['observed'][:200]}")
    return result


def fix(trial: Trial, message: str) -> None:
    state = trial.state()
    intro = (
        "You are fixing a product after its parts, built separately by different AI "
        "agents, were merged (read README.md). Make the app work as a whole. "
    )
    first = "fixer" not in state["sessions"]
    prompt = (intro if first else "") + message + " Commit when done; two-line summary."
    label = f"fix{sum(c['agent'] == 'main' for c in state['calls']) + 1}"
    result = call(trial, "main", label, prompt, midflight=False)
    print(f"fixer: {result['num_turns']} turns: {result['text'][-300:]}")


def repair(trial: Trial) -> None:
    """Score; while checks fail, give them to the fixer and score again."""
    result = score(trial)
    for _ in range(MAX_FIX_ROUNDS):
        failing = [c for c in result["checks"] if not c["passed"]]
        if not failing:
            return
        lines = [
            f"({c['id']}) {c['name']}. Ran: {c['command']}. Expected: {c['expected']}. "
            f"Got: {c['observed'][:400]}"
            for c in failing
        ]
        fix(trial, "These checks fail: " + " ".join(lines))
        result = score(trial)


# Calling an agent ----------------------------------------------------------------------


def call(trial: Trial, agent: str, label: str, prompt: str, midflight: bool | None = None) -> dict:
    """One headless Claude Code call in the agent's folder. The message is saved in
    prompts/, the event stream in logs/, and the call is noted in the run's state."""
    use_midflight = trial.with_midflight if midflight is None else midflight
    session_key = "fixer" if agent == "main" else agent
    with STATE_LOCK:
        state = trial.state()
        session = state["sessions"].get(session_key)
        order = len(state["calls"]) + len(state.get("pending", [])) + 1
        name = f"{order:02d}-{agent}-{label}"
        state.setdefault("pending", []).append(name)
        trial.save(state)
    args = [claude_exe(), "-p", "--model", MODEL, "--max-turns", MAX_TURNS,
            "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
            "--allowedTools", *TOOLS, *(MIDFLIGHT_TOOLS if use_midflight else []),
            # Only these MCP servers: none, or only Midflight (others slow the start).
            "--strict-mcp-config"]  # fmt: skip
    if use_midflight:
        args += ["--mcp-config", str(HERE / "midflight-only.mcp.json")]
    if session:
        args += ["--resume", session]
    (trial.root / "prompts" / f"{name}.txt").write_text(prompt, encoding="utf-8")
    log = trial.root / "logs" / f"{name}.jsonl"
    for attempt in range(1, 9):
        if run_agent(args, prompt, trial.root / agent, log, needs_midflight=use_midflight):
            break
        # Midflight's tools weren't loaded at start-up: the agent was stopped before it
        # did any work. Wait and start it again.
        print(f"{agent}: Midflight wasn't ready (attempt {attempt}); retrying", flush=True)
        with STATE_LOCK:
            state = trial.state()
            state["not_ready"] = state.get("not_ready", 0) + 1
            trial.save(state)
        time.sleep(20)
    else:
        sys.exit(f"{agent}: Midflight never initialized; nothing was run")
    result = summarize(log)
    limited = LIMIT_TEXT in result["text"]
    with STATE_LOCK:
        state = trial.state()
        state["pending"] = [p for p in state.get("pending", []) if p != name]
        if not limited:
            state["sessions"][session_key] = result["session_id"]
            state["calls"].append({"order": order, "agent": agent, "label": label, "file": name})
            state["done"].setdefault(label, {})[agent] = True
        trial.save(state)
    if limited:
        raise UsageLimit(agent)
    return result


def run_agent(args: list[str], prompt: str, cwd: Path, log: Path, needs_midflight: bool) -> bool:
    """Run one agent to the end, saving its event stream. With `needs_midflight`, the
    agent is stopped at once (returning False) unless its start-up message lists every
    Midflight tool, so no agent ever works without Midflight by accident."""
    with log.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8")  # fmt: skip
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
                if set(MIDFLIGHT_TOOLS) <= set(event.get("tools", [])):
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


def warm_up(trial: Trial) -> None:
    """Before a Midflight phase: one small call that wakes the server and refreshes the
    sign-in, so agents starting together don't race to do either."""
    args = [claude_exe(), "-p", "--model", MODEL, "--max-turns", "3",
            "--output-format", "stream-json", "--verbose", "--strict-mcp-config",
            "--mcp-config", str(HERE / "midflight-only.mcp.json"),
            "--allowedTools", "mcp__midflight-live__my_projects", *MIDFLIGHT_TOOLS]  # fmt: skip
    log = trial.root / "logs" / f"warmup-{int(time.time())}.jsonl"
    prompt = "Call the Midflight my_projects tool once and reply with one word: ready."
    for attempt in range(1, 6):
        if run_agent(args, prompt, trial.root, log, needs_midflight=True):
            if LIMIT_TEXT in summarize(log)["text"]:
                sys.exit("USAGE LIMIT reached during warm-up. Run this phase again later.")
            print("Midflight is warm and connected", flush=True)
            return
        print(f"warm-up: Midflight not ready (attempt {attempt})", flush=True)
        time.sleep(20)
    sys.exit("Midflight didn't connect during warm-up")


# Numbers and records -------------------------------------------------------------------


def summarize(log: Path) -> dict:
    result: dict = {"session_id": None, "num_turns": 0, "text": "", "tools": []}
    for event in events(log):
        if event.get("type") == "result":
            result.update(
                session_id=event.get("session_id"),
                num_turns=event.get("num_turns", 0),
                text=event.get("result", "") or "",
            )
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    result["tools"].append(block.get("name", ""))
        if event.get("session_id") and not result["session_id"]:
            result["session_id"] = event["session_id"]
    return result


def events(log: Path) -> list[dict]:
    found = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            found.append(json.loads(line))
        except ValueError:
            continue
    return found


def stats(trial: Trial, show: bool = True) -> dict:
    """Totals for a run. Claude Code reports a session's cost cumulatively across
    resumed calls, so cost is the highest value per agent; turns, tokens, and time are
    per call and are summed. Warm-up calls exist only in this harness and are listed
    apart."""
    totals: dict = {
        "cost": 0.0, "warmup_cost": 0.0, "turns": 0, "input": 0, "output": 0,
        "cache_read": 0, "cache_write": 0, "agent_minutes": 0.0, "tool_calls": 0,
        "midflight_calls": {}, "cost_by_agent": {},
    }  # fmt: skip
    for log in sorted((trial.root / "logs").glob("*.jsonl")):
        warmup = log.name.startswith("warmup")
        parts = log.stem.split("-")
        agent = "warmup" if warmup else (parts[1] if parts[0].isdigit() else parts[0])
        for event in events(log):
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
                            calls = totals["midflight_calls"]
                            calls[short] = calls.get(short, 0) + 1
    totals["cost"] = round(sum(totals["cost_by_agent"].values()), 4)
    totals["agent_minutes"] = round(totals["agent_minutes"], 1)
    state = trial.state()
    state["stats"] = totals
    trial.save(state)
    if show:
        print(json.dumps(totals, indent=2))
    return totals


def record(trial: Trial) -> None:
    """Write the run into the repository: experiment/cases/<case>/results/<run>/."""
    out = trial.case_dir / "results" / trial.run
    out.mkdir(parents=True, exist_ok=True)
    totals = stats(trial, show=False)
    state = trial.state()
    summary = {
        "case": trial.case_name,
        "run": trial.run,
        "approach": {"N": "no channel", "A": "team-chat file", "B": "Midflight"}[trial.approach],
        "model": MODEL,
        "merge": state.get("merge", []),
        "scores": [
            {
                "passed": sum(c["passed"] for c in s["checks"]),
                "of": len(s["checks"]),
                "failed": [c["id"] for c in s["checks"] if not c["passed"]],
            }
            for s in state.get("scores", [])
        ],
        "agent_starts_without_midflight": state.get("not_ready", 0),
        "stats": totals,
        "notes": state.get("notes", []),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if state.get("scores"):
        (out / "checks.json").write_text(json.dumps(state["scores"], indent=2), encoding="utf-8")

    prompts = [
        f"# Every message sent to an agent in run {trial.run}\n\n",
        "In order. The first message to an agent starts its session; later ones continue it.\n",
    ]
    replies = [f"# What each agent did and said in run {trial.run}\n"]
    for prompt_file in sorted((trial.root / "prompts").glob("*.txt")):
        order, agent, label = prompt_file.stem.split("-", 2)
        who = "fixer" if agent == "main" else agent
        text = prompt_file.read_text(encoding="utf-8").strip()
        prompts.append(f"\n## {order}. To {who} ({label})\n\n```\n{text}\n```\n")
        log = trial.root / "logs" / f"{prompt_file.stem}.jsonl"
        if log.exists():
            result = summarize(log)
            tools: dict[str, int] = {}
            for tool in result["tools"]:
                short = tool.removeprefix("mcp__midflight-live__")
                tools[short] = tools.get(short, 0) + 1
            used = ", ".join(f"{name} x{count}" for name, count in tools.items()) or "none"
            replies.append(
                f"\n## {order}. {who} ({label}): {result['num_turns']} turns\n\n"
                f"Tools: {used}\n\n{result['text'].strip()}\n"
            )
    (out / "prompts.md").write_text("".join(prompts), encoding="utf-8")
    (out / "agents.md").write_text("".join(replies), encoding="utf-8")
    if trial.approach == "A" and trial.chat.exists():
        shutil.copy(trial.chat, out / "team-chat.md")
    print(f"recorded {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # agents write any character
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    trial = Trial(sys.argv[1], sys.argv[2])
    step, rest = sys.argv[3], sys.argv[4:]
    match step:
        case "setup":
            setup(trial)
        case "phase":
            phase(trial, int(rest[0]))
        case "say":
            say(trial, rest[0], rest[1])
        case "merge":
            merge(trial)
        case "score":
            score(trial)
        case "fix":
            fix(trial, rest[0])
        case "repair":
            repair(trial)
        case "stats":
            stats(trial)
        case "record":
            record(trial)
        case _:
            sys.exit(__doc__)
