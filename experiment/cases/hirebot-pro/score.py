"""The 14 checks for HireBot Pro, run automatically against a merged app.

`score(folder)` starts the app, runs the customer command line as a customer would, and
compares what it prints with the expected values. The checks and their expected values
were fixed before any trial; they are listed in checks.md.

Each check crosses at least one boundary between two agents' parts.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEPS = ["--with", "fastapi", "--with", "uvicorn", "--with", "httpx", "--with", "requests"]
RATES = {
    "intern-o-tron": (120, 40),
    "lgtm": (80, 60),
    "meeting-ghost": (150, 30),
    "overconfident-junior": (60, 50),
    "hallucination-detective": (200, 20),
    "rubber-duck": (40, 80),
}


def score(folder: Path) -> dict:
    port = free_port()
    log = folder.parent / "server.log"
    with log.open("w", encoding="utf-8") as out:
        server = subprocess.Popen(
            ["uv", "run", *DEPS, "uvicorn", "app.main:app", "--port", str(port)],
            cwd=folder, stdout=out, stderr=subprocess.STDOUT,
        )  # fmt: skip
    try:
        up = wait_until_up(port)
        crash = "" if up else "the app didn't start: " + log.read_text(encoding="utf-8")[-600:]
        checks = run_checks(folder, port, crash)
    finally:
        stop(server)
    return {"checks": checks}


def run_checks(folder: Path, port: int, crash: str) -> list[dict]:
    env = {**os.environ, "HIREBOT_URL": f"http://127.0.0.1:{port}"}
    checks: list[dict] = []

    def cli(*args: str) -> tuple[int, dict[str, list[str]], str]:
        """Run one customer command; return its exit code, its `key: value` lines, and
        everything it printed."""
        if crash:
            return 1, {}, crash
        done = subprocess.run(
            ["uv", "run", *DEPS, "python", "-m", "cli.hirebot", *args],
            cwd=folder, env=env, capture_output=True, text=True, timeout=120,
        )  # fmt: skip
        printed = (done.stdout + done.stderr).strip()
        lines: dict[str, list[str]] = {}
        for line in done.stdout.splitlines():
            key, colon, value = line.partition(":")
            if colon:
                lines.setdefault(key.strip(), []).append(value.strip())
        return done.returncode, lines, printed

    def check(number: int, name: str, command: str, expected: str, ok: bool, saw: str) -> None:
        checks.append({"id": f"C{number}", "name": name, "command": command,
                       "expected": expected, "passed": bool(ok),
                       "observed": saw[:700]})  # fmt: skip

    def numbers_match(lines: dict[str, list[str]], want: dict[str, float]) -> bool:
        return all(number(lines.get(key, [""])[0]) == value for key, value in want.items())

    # 1. The catalog, as the customer sees it.
    _, lines, saw = cli("agents")
    listed = {}
    for entry in lines.get("agent", []):
        handle, *pairs = entry.split()
        values = dict(p.split("=", 1) for p in pairs if "=" in p)
        listed[handle] = (number(values.get("rate", "")), number(values.get("capacity", "")))
    check(1, "agents lists all six agents with their rates and capacity", "agents",
          "six `agent:` lines with the README's rates and capacities",
          listed == RATES, saw)  # fmt: skip

    # 2. Filtering by skill.
    _, lines, saw = cli("agents", "--skill", "code-review")
    handles = sorted(entry.split()[0] for entry in lines.get("agent", []) if entry)
    check(2, "agents --skill filters by skill", "agents --skill code-review",
          "only hallucination-detective and lgtm",
          handles == ["hallucination-detective", "lgtm"], saw)  # fmt: skip

    # 3 and 4. A quote with a volume discount, then with the promo code.
    cart = ["meeting-ghost=10", "rubber-duck=25"]
    _, lines, saw = cli("quote", *cart)
    want = {"subtotal": 2500, "volume_discount": 100, "promo_discount": 0, "tax": 192,
            "total": 2592}  # fmt: skip
    check(3, "quote with a volume discount", "quote " + " ".join(cart),
          "subtotal 2500, volume_discount 100, promo_discount 0, tax 192, total 2592",
          numbers_match(lines, want), saw)  # fmt: skip
    _, lines, saw = cli("quote", *cart, "--promo", "BEEPBOOP")
    want = {"subtotal": 2500, "volume_discount": 100, "promo_discount": 50, "tax": 188,
            "total": 2538}  # fmt: skip
    check(4, "quote with promo code BEEPBOOP", "quote " + " ".join(cart) + " --promo BEEPBOOP",
          "promo_discount 50, tax 188, total 2538", numbers_match(lines, want), saw)  # fmt: skip

    # 5 and 6. The lead's plan change: half hours and rush orders.
    _, lines, saw = cli("quote", "meeting-ghost=2.5")
    check(5, "half-hour quote (plan change)", "quote meeting-ghost=2.5",
          "subtotal 375, tax 30, total 405",
          numbers_match(lines, {"subtotal": 375, "tax": 30, "total": 405}), saw)  # fmt: skip
    _, lines, saw = cli("quote", "meeting-ghost=10", "--rush")
    check(6, "rush order (plan change)", "quote meeting-ghost=10 --rush",
          "subtotal 1500, rush_fee 375, tax 150, total 2025",
          numbers_match(lines, {"subtotal": 1500, "rush_fee": 375, "tax": 150, "total": 2025}),
          saw)  # fmt: skip

    # 7 and 8. Booking, and reading the booking back.
    code, lines, saw = cli("book", *cart, "--promo", "BEEPBOOP")
    booking = lines.get("booking", [""])[0]
    check(7, "booking an order", "book " + " ".join(cart) + " --promo BEEPBOOP",
          "a booking id, status confirmed, total 2538",
          code == 0 and bool(booking) and lines.get("status") == ["confirmed"]
          and numbers_match(lines, {"total": 2538}), saw)  # fmt: skip
    _, lines, saw = cli("show", booking or "missing")
    check(8, "show returns the booking", "show <booking id>",
          "status confirmed, total 2538",
          lines.get("status") == ["confirmed"] and numbers_match(lines, {"total": 2538}),
          saw)  # fmt: skip

    # 9 and 10. Capacity: hours left go down, and an order that doesn't fit is refused.
    _, ghost, saw_a = cli("availability", "meeting-ghost")
    _, duck, saw_b = cli("availability", "rubber-duck")
    check(9, "booking reserves hours", "availability meeting-ghost; availability rubber-duck",
          "available 20, then available 55",
          numbers_match(ghost, {"available": 20}) and numbers_match(duck, {"available": 55}),
          f"{saw_a} | {saw_b}")  # fmt: skip
    code, lines, saw_a = cli("book", "hallucination-detective=25")
    _, left, saw_b = cli("availability", "hallucination-detective")
    check(10, "an order over capacity is refused", "book hallucination-detective=25",
          "an `error:` line and exit code 1; hallucination-detective still has 20 hours",
          code != 0 and "error" in lines and numbers_match(left, {"available": 20}),
          f"exit {code}: {saw_a} | {saw_b}")  # fmt: skip

    # 11 and 12. Cancelling.
    _, lines, saw_a = cli("cancel", booking or "missing")
    _, shown, saw_b = cli("show", booking or "missing")
    check(11, "cancelling a booking", "cancel <booking id>; show <booking id>",
          "status cancelled both times",
          lines.get("status") == ["cancelled"] and shown.get("status") == ["cancelled"],
          f"{saw_a} | {saw_b}")  # fmt: skip
    _, ghost, saw = cli("availability", "meeting-ghost")
    check(12, "cancelling gives the hours back", "availability meeting-ghost", "available 30",
          numbers_match(ghost, {"available": 30}), saw)  # fmt: skip

    # 13. The report, which depends on the lead's decision about cancellations: a 10% fee
    # (254 of the cancelled 2538) counts as revenue, next to one confirmed booking of 432.
    _, lines, saw_a = cli("book", "lgtm=5")
    _, report, saw_b = cli("report")
    hours = dict(entry.split("=", 1) for entry in report.get("hours", []) if "=" in entry)
    booked = {handle: number(value) for handle, value in hours.items() if number(value)}
    check(13, "the revenue report, with the cancellation fee the lead decided",
          "book lgtm=5; report",
          "revenue 686 (432 + a 10% fee of 254), confirmed 1, cancelled 1, hours: lgtm=5 only",
          numbers_match(report, {"revenue": 686, "confirmed": 1, "cancelled": 1})
          and booked == {"lgtm": 5}, f"{saw_a} | {saw_b}")  # fmt: skip

    # 14. Booking half an hour reserves half an hour.
    code, lines, saw_a = cli("book", "meeting-ghost=2.5")
    _, ghost, saw_b = cli("availability", "meeting-ghost")
    check(14, "a half-hour booking reserves half hours (plan change)",
          "book meeting-ghost=2.5; availability meeting-ghost",
          "status confirmed, total 405, then available 27.5",
          code == 0 and numbers_match(lines, {"total": 405})
          and numbers_match(ghost, {"available": 27.5}), f"{saw_a} | {saw_b}")  # fmt: skip
    return checks


def number(text: str) -> float | None:
    try:
        return float(text.replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_up(port: int, seconds: int = 60) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=2)
            return True
        except OSError:
            time.sleep(1)
    return False


def stop(server: subprocess.Popen) -> None:
    if sys.platform == "win32":  # uv starts uvicorn as a child; stop the whole tree
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(server.pid)], capture_output=True)
    else:
        server.terminate()
    server.wait(timeout=20)


if __name__ == "__main__":
    import json

    print(json.dumps(score(Path(sys.argv[1])), indent=2))
