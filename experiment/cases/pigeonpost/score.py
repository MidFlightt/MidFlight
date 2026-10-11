"""The 20 checks for PigeonPost, run automatically against a merged app.

`score(folder)` starts the app, runs the customer command line as a customer would, and
compares what it prints with the expected values. The checks and their expected values
were fixed before any trial; they are listed in checks.md.

Every check has an `event`: "plain build" for the 8 that need no news to travel, or the
mid-flight event (EVENTS) it only passes after. The reference build in reference/ scores
20 of 20.
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
PLAIN = "plain build"
EVENTS = [
    "plan change",
    "two developers disagree",
    "a note against the plan",
    "a unit quietly changed",
    "late joiner",
    "nobody planned it",
]
BIRDS = {
    "budget-bob": (1, 36, 2),
    "express-edna": (2, 90, 3),
    "sir-flaps-a-lot": (3, 54, 2),
    "cargo-carl": (5, 45, 1),
}
DESTINATIONS = {"downtown": 3, "harbor": 8, "campus": 12, "airport": 20}


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
    return {"checks": checks, "events": by_event(checks)}


def by_event(checks: list[dict]) -> dict[str, dict]:
    """Per event: how many of its checks passed. An event held if all of them did."""
    summary: dict[str, dict] = {}
    for name in [PLAIN, *EVENTS]:
        mine = [c for c in checks if c["event"] == name]
        passed = sum(c["passed"] for c in mine)
        summary[name] = {"passed": passed, "of": len(mine), "held": passed == len(mine)}
    return summary


def run_checks(folder: Path, port: int, crash: str) -> list[dict]:
    env = {**os.environ, "PIGEON_URL": f"http://127.0.0.1:{port}"}
    checks: list[dict] = []

    def cli(*args: str) -> tuple[int, dict[str, list[str]], str]:
        """Run one customer command; return its exit code, its `key: value` lines, and
        everything it printed."""
        if crash:
            return 1, {}, crash
        done = subprocess.run(
            ["uv", "run", *DEPS, "python", "-m", "cli.pigeon", *args],
            cwd=folder, env=env, capture_output=True, text=True, timeout=120,
        )  # fmt: skip
        printed = (done.stdout + done.stderr).strip()
        lines: dict[str, list[str]] = {}
        for line in done.stdout.splitlines():
            key, colon, value = line.partition(":")
            if colon:
                lines.setdefault(key.strip(), []).append(value.strip())
        return done.returncode, lines, printed

    def check(event: str, name: str, command: str, expected: str, ok: bool, saw: str) -> None:
        checks.append({"id": f"C{len(checks) + 1}", "event": event, "name": name,
                       "command": command, "expected": expected, "passed": bool(ok),
                       "observed": saw[:700]})  # fmt: skip

    def match(lines: dict[str, list[str]], **want: float | str) -> bool:
        """Every wanted key is printed with the wanted value (numbers to the cent)."""
        for key, value in want.items():
            printed = lines.get(key, [""])[0]
            if isinstance(value, str):
                if printed != value:
                    return False
            elif not same(number(printed), value):
                return False
        return True

    def pairs(entries: list[str]) -> dict[str, dict[str, float | None]]:
        """`<name> a=1 b=2` lines as {name: {a: 1, b: 2}}."""
        found = {}
        for entry in entries:
            name, *rest = entry.split()
            found[name] = {k: number(v) for k, _, v in (p.partition("=") for p in rest)}
        return found

    # Plain build: nothing has to travel between agents after the plan is read. ----------

    _, lines, saw = cli("destinations")
    listed = {name: values.get("distance") for name, values in
              pairs(lines.get("destination", [])).items()}  # fmt: skip
    check(PLAIN, "destinations lists the four destinations", "destinations",
          "four `destination:` lines with the README's distances",
          listed == DESTINATIONS, saw)  # fmt: skip

    _, lines, saw = cli("quote", "harbor", "2.5")
    check(PLAIN, "a quote", "quote harbor 2.5",
          "delivery_fee 13.00, promo_discount 0.00, tax 1.04, total 14.04",
          match(lines, delivery_fee=13.00, promo_discount=0, tax=1.04, total=14.04),
          saw)  # fmt: skip

    code, lines, saw = cli("quote", "campus", "1", "--promo", "PIGEON")
    check(PLAIN, "an unknown promo code is refused", "quote campus 1 --promo PIGEON",
          "an `error:` line and exit code 1", code != 0 and "error" in lines,
          f"exit {code}: {saw}")  # fmt: skip

    code, lines, saw = cli("send", "downtown", "1")
    first = lines.get("delivery", [""])[0]
    check(PLAIN, "sending a parcel", "send downtown 1",
          "a delivery id, bird budget-bob, status confirmed, total 8.10",
          code == 0 and bool(first)
          and match(lines, bird="budget-bob", status="confirmed", total=8.10), saw)  # fmt: skip

    _, lines, saw = cli("show", first or "missing")
    check(PLAIN, "show returns the delivery", "show <first id>",
          "bird budget-bob, status confirmed, total 8.10",
          match(lines, bird="budget-bob", status="confirmed", total=8.10), saw)  # fmt: skip

    _, lines, saw = cli("availability", "budget-bob")
    check(PLAIN, "a delivery uses one of the bird's flights", "availability budget-bob",
          "flights_left 1", match(lines, flights_left=1), saw)  # fmt: skip

    _, second_lines, saw_a = cli("send", "campus", "0.5")
    second = second_lines.get("delivery", [""])[0]
    _, third_lines, saw_b = cli("send", "campus", "1")
    third = third_lines.get("delivery", [""])[0]
    _, left, saw_c = cli("availability", "budget-bob")
    check(PLAIN, "when a bird is out of flights, the next bird flies",
          "send campus 0.5; send campus 1; availability budget-bob",
          "budget-bob (total 11.88), then express-edna (total 12.96), then flights_left 0",
          match(second_lines, bird="budget-bob", total=11.88)
          and match(third_lines, bird="express-edna", total=12.96)
          and match(left, flights_left=0), f"{saw_a} | {saw_b} | {saw_c}")  # fmt: skip

    _, cancelled, saw_a = cli("cancel", second or "missing")
    _, shown, saw_b = cli("show", second or "missing")
    _, left, saw_c = cli("availability", "budget-bob")
    check(PLAIN, "cancelling gives the flight back",
          "cancel <second id>; show <second id>; availability budget-bob",
          "status cancelled both times, then flights_left 1",
          match(cancelled, status="cancelled") and match(shown, status="cancelled")
          and match(left, flights_left=1), f"{saw_a} | {saw_b} | {saw_c}")  # fmt: skip

    # Two developers disagree: one refunds everything, one keeps the 4.00 base fee. The
    # lead's decision is neither: a fee of 25% of the total (2.97 of 11.88).

    check("two developers disagree", "the refund after cancelling, as the lead decided",
          "cancel <second id> (the same command as C8)",
          "refund 8.91 (the total 11.88 less a 25% fee of 2.97)",
          match(cancelled, refund=8.91), saw_a)  # fmt: skip

    # Nobody planned it: the plan doesn't say how billing gets every delivery.

    _, report, saw = cli("report")
    flights = {name: number(value) for name, _, value in
               (entry.partition("=") for entry in report.get("flights", []))}  # fmt: skip
    flown = {name: value for name, value in flights.items() if value}
    check("nobody planned it", "the report counts every delivery", "report",
          "confirmed 2, cancelled 1, flights: budget-bob=1 and express-edna=1 only",
          match(report, confirmed=2, cancelled=1)
          and flown == {"budget-bob": 1, "express-edna": 1}, saw)  # fmt: skip

    check("two developers disagree", "revenue counts the cancellation fee the lead decided",
          "report (the same command as C10)",
          "revenue 24.03 (8.10 + 12.96 + the 2.97 fee)", match(report, revenue=24.03),
          saw)  # fmt: skip

    # A note against the plan: pricing's developer wants tax before the promo discount.
    # The plan says after, and the lead says the plan stands.

    cart = ["harbor", "2.5", "--promo", "COOCOO"]
    _, lines, saw = cli("quote", *cart)
    check("a note against the plan", "tax is charged after the promo discount",
          "quote " + " ".join(cart),
          "delivery_fee 13.00, promo_discount 1.95, tax 0.88, total 11.93",
          match(lines, delivery_fee=13.00, promo_discount=1.95, tax=0.88, total=11.93),
          saw)  # fmt: skip

    _, lines, saw_a = cli("send", "harbor", "1", "--promo", "COOCOO")
    _, shown, saw_b = cli("show", lines.get("delivery", ["missing"])[0])
    check("a note against the plan", "a delivery with a promo code is charged the same way",
          "send harbor 1 --promo COOCOO; show <id>",
          "promo_discount 1.50, tax 0.68, total 9.18, and show says total 9.18",
          match(lines, promo_discount=1.50, tax=0.68, total=9.18) and match(shown, total=9.18),
          f"{saw_a} | {saw_b}")  # fmt: skip

    # Plan change: the lead adds express delivery. It touches pricing, dispatch, and the
    # command line; not the roost, billing, or tracking.

    _, lines, saw = cli("quote", "harbor", "2.5", "--express")
    check("plan change", "an express quote", "quote harbor 2.5 --express",
          "delivery_fee 13.00, express_fee 6.50, tax 1.56, total 21.06",
          match(lines, delivery_fee=13.00, express_fee=6.50, tax=1.56, total=21.06),
          saw)  # fmt: skip

    _, lines, saw_a = cli("send", "harbor", "0.5", "--express")
    _, shown, saw_b = cli("show", lines.get("delivery", ["missing"])[0])
    check("plan change", "an express delivery", "send harbor 0.5 --express; show <id>",
          "delivery_fee 9.00, express_fee 4.50, tax 1.08, total 14.58, and show says 14.58",
          match(lines, delivery_fee=9.00, express_fee=4.50, tax=1.08, total=14.58)
          and match(shown, total=14.58), f"{saw_a} | {saw_b}")  # fmt: skip

    # Late joiner: tracking starts after everyone else built their first version.

    _, one, saw_a = cli("track", first or "missing")
    _, three, saw_b = cli("track", third or "missing")
    check("late joiner", "tracking a delivery", "track <first id>; track <third id>",
          "budget-bob eta_minutes 5 (3 km at 36 km/h), then express-edna eta_minutes 8",
          match(one, status="confirmed", bird="budget-bob", eta_minutes=5)
          and match(three, status="confirmed", bird="express-edna", eta_minutes=8),
          f"{saw_a} | {saw_b}")  # fmt: skip

    _, lines, saw = cli("track", second or "missing")
    check("late joiner", "tracking a cancelled delivery", "track <second id>",
          "status cancelled, eta_minutes 0", match(lines, status="cancelled", eta_minutes=0),
          saw)  # fmt: skip

    # A unit quietly changed: the roost's developer wants payloads in grams. These run
    # last, so a wrong bird here can't disturb the checks above.

    _, lines, saw = cli("birds")
    listed = {name: (v.get("max_payload"), v.get("speed"), v.get("flights"))
              for name, v in pairs(lines.get("bird", [])).items()}  # fmt: skip
    check("a unit quietly changed", "birds shows payloads in kg", "birds",
          "four `bird:` lines: max_payload 1, 2, 3, 5 kg with the fleet's speeds and flights",
          listed == BIRDS, saw)  # fmt: skip

    _, lines, saw = cli("send", "airport", "4")
    check("a unit quietly changed", "a heavy parcel goes to a bird that can carry it",
          "send airport 4", "bird cargo-carl, total 23.76",
          match(lines, bird="cargo-carl", total=23.76), saw)  # fmt: skip

    code, lines, saw = cli("send", "harbor", "6")
    check("a unit quietly changed", "a parcel too heavy for every bird is refused",
          "send harbor 6", "an `error:` line and exit code 1",
          code != 0 and "error" in lines and "delivery" not in lines,
          f"exit {code}: {saw}")  # fmt: skip
    return checks


def number(text: str) -> float | None:
    try:
        return float(text.replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None


def same(printed: float | None, wanted: float) -> bool:
    return printed is not None and abs(printed - wanted) < 0.005


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
