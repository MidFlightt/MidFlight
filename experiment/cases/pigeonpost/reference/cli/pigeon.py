"""The PigeonPost command line: what the customer types (see README.md)."""

import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("PIGEON_URL", "http://127.0.0.1:8000")


class Refused(Exception):
    pass


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(URL + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as problem:
        try:
            detail = json.loads(problem.read()).get("detail", problem.reason)
        except ValueError:
            detail = problem.reason
        raise Refused(str(detail)) from problem
    except OSError as problem:
        raise Refused(f"can't reach PigeonPost at {URL}: {problem}") from problem


def money(amount: float) -> str:
    return f"{amount:.2f}"


def number(value: float) -> str:
    return f"{value:g}"


def parcel(args: list[str]) -> dict:
    """`<destination> <kg> [--promo CODE] [--express]` as a request body."""
    words, promo, express = [], None, False
    rest = iter(args)
    for word in rest:
        if word == "--promo":
            promo = next(rest, None)
            if promo is None:
                raise Refused("--promo needs a code")
        elif word == "--express":
            express = True
        else:
            words.append(word)
    if len(words) != 2:
        raise Refused("usage: <destination> <kg> [--promo CODE] [--express]")
    try:
        weight = float(words[1])
    except ValueError:
        raise Refused(f"{words[1]} is not a weight in kg") from None
    return {"destination": words[0], "weight_kg": weight, "promo": promo, "express": express}


def print_quote(quote: dict) -> None:
    print(f"delivery_fee: {money(quote['delivery_fee'])}")
    print(f"promo_discount: {money(quote['promo_discount'])}")
    print(f"express_fee: {money(quote['express_fee'])}")
    print(f"tax: {money(quote['tax'])}")
    print(f"total: {money(quote['total'])}")


def run(command: str, args: list[str]) -> None:
    if command == "destinations":
        for place in call("GET", "/destinations"):
            print(f"destination: {place['code']} distance={number(place['distance_km'])}")
    elif command == "birds":
        for bird in call("GET", "/birds"):
            print(f"bird: {bird['handle']} max_payload={number(bird['max_payload'])} "
                  f"speed={number(bird['speed'])} flights={bird['flights_per_day']}")  # fmt: skip
    elif command == "quote":
        print_quote(call("POST", "/quote", parcel(args)))
    elif command == "send":
        body = parcel(args)
        quote = call("POST", "/quote", body)
        delivery = call("POST", "/deliveries", body)
        print_quote(quote)
        print(f"delivery: {delivery['id']}")
        print(f"bird: {delivery['bird']}")
        print(f"status: {delivery['status']}")
    elif command in ("show", "cancel", "track") and len(args) == 1:
        if command == "show":
            delivery = call("GET", f"/deliveries/{args[0]}")
            print(f"delivery: {delivery['id']}")
            print(f"bird: {delivery['bird']}")
            print(f"status: {delivery['status']}")
            print(f"total: {money(delivery['total'])}")
        elif command == "cancel":
            delivery = call("POST", f"/deliveries/{args[0]}/cancel")
            print(f"delivery: {delivery['id']}")
            print(f"status: {delivery['status']}")
            print(f"refund: {money(delivery['refund'])}")
        else:
            tracking = call("GET", f"/deliveries/{args[0]}/tracking")
            print(f"delivery: {tracking['delivery']}")
            print(f"status: {tracking['status']}")
            print(f"bird: {tracking['bird']}")
            print(f"eta_minutes: {tracking['eta_minutes']}")
    elif command == "availability" and len(args) == 1:
        print(f"flights_left: {call('GET', f'/birds/{args[0]}/availability')['flights_left']}")
    elif command == "report":
        report = call("GET", "/report")
        print(f"revenue: {money(report['revenue'])}")
        print(f"confirmed: {report['confirmed']}")
        print(f"cancelled: {report['cancelled']}")
        for handle, flights in report["flights"].items():
            print(f"flights: {handle}={flights}")
    else:
        raise Refused(f"unknown command: {command} {' '.join(args)}".strip())


def main() -> int:
    if len(sys.argv) < 2:
        print("error: give a command (see README.md)")
        return 1
    try:
        run(sys.argv[1], sys.argv[2:])
    except Refused as problem:
        print(f"error: {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
