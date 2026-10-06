"""Run with python3 -m midflight [check path/to/claims.json]."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .claims import Claim, ClaimBoard


def demo() -> list[dict]:
    return [
        {"id": "backend", "owner": "Somesh", "goal": "Build the user API",
         "files": ["api/users.py"], "interfaces": ["user-api"]},
        {"id": "screen", "owner": "Frederik", "goal": "Build the profile screen",
         "files": ["ui/profile.tsx"], "interfaces": ["user-api"]},
        {"id": "docs", "owner": "Mithilesh", "goal": "Write the demo instructions",
         "files": ["docs/demo.md"], "interfaces": []},
        {"id": "explore", "owner": "Frederik", "goal": "Explore activity history"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Midflight local claim demo")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="review four synthetic claims")
    check = sub.add_parser("check", help="review a JSON array of claims in order")
    check.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text()) if args.command == "check" else demo()
        if not isinstance(data, list):
            raise ValueError("input must be a JSON array of claims")
        claims = [Claim.from_dict(item) for item in data]
        board = ClaimBoard()
        reviews = [asdict(board.submit(claim)) for claim in claims]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(reviews, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
