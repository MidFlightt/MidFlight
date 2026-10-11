"""How much of a trial's context came from Midflight, read from the trial's own logs.

    python experiment/midflight_share.py ../experiment-runs/pigeonpost/B1/logs

For each agent: its Midflight calls by tool, the characters Midflight sent back, and how
many of its check-ins passed the marker of an earlier reply (`since`). The lead's agent
and the warm-up calls are listed apart, as in the trial's summary. Nothing is estimated:
these are the replies the agents really got.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PREFIX = "mcp__midflight-live__"


def text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def read(logs: Path) -> dict[str, dict]:
    agents: dict[str, dict] = {}
    for log in sorted(logs.glob("*.jsonl")):
        name = "warm-up" if log.name.startswith("warmup") else log.stem.split("-")[1]
        mine = agents.setdefault(
            name, {"calls": Counter(), "sent": 0, "received": 0, "check_ins": 0, "since": 0}
        )
        asked: dict[str, str] = {}  # tool_use id -> tool
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = event.get("message") if isinstance(event, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name", "").startswith(PREFIX):
                    tool = block["name"].removeprefix(PREFIX)
                    if block["id"] in asked:
                        continue
                    asked[block["id"]] = tool
                    mine["calls"][tool] += 1
                    mine["sent"] += len(json.dumps(block.get("input", {})))
                    if tool == "check_in":
                        mine["check_ins"] += 1
                        mine["since"] += bool(block.get("input", {}).get("since"))
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in asked:
                    mine["received"] += len(text_of(block.get("content")))
                    asked[block["tool_use_id"]] = ""  # a resumed log repeats nothing twice
    return agents


def main() -> None:
    logs = Path(sys.argv[1])
    agents = read(logs)
    builders = {name: a for name, a in agents.items() if name not in ("lead", "warm-up")}
    print(
        f"{'agent':8} {'calls':>5} {'sent':>8} {'received':>9} {'check-ins':>9} {'with marker':>11}"
    )
    for name, a in sorted(agents.items()):
        calls = sum(a["calls"].values())
        print(
            f"{name:8} {calls:5} {a['sent']:8} {a['received']:9} {a['check_ins']:9} {a['since']:11}"
        )
    total = Counter()
    for a in builders.values():
        total.update({k: a[k] for k in ("sent", "received", "check_ins", "since")})
        total["calls"] += sum(a["calls"].values())
    print(
        f"\nthe building agents: {total['calls']} calls, {total['sent']:,} characters sent, "
        f"{total['received']:,} received ({total['received'] // max(total['calls'], 1):,} a call), "
        f"marker passed in {total['since']} of {total['check_ins']} check-ins"
    )
    by_tool = Counter()
    for a in builders.values():
        by_tool.update(a["calls"])
    print("by tool: " + ", ".join(f"{tool} {n}" for tool, n in by_tool.most_common()))


if __name__ == "__main__":
    main()
