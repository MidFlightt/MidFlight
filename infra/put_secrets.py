"""Store the GitHub App's secrets in AWS Secrets Manager, straight from your machine.

    uv run python infra/put_secrets.py

Reads from your local `.env` (git-ignored):

- `MIDFLIGHT_GITHUB_CLIENT_SECRET`: the App's client secret (Sign in with GitHub)
- `MIDFLIGHT_GITHUB_PRIVATE_KEY_PATH`: path to the App's `.pem` private key
- `MIDFLIGHT_GITHUB_WEBHOOK_SECRET`: the App's webhook secret (verification, M-6)

and writes them to the secret the `midflight` stack created. Nothing is printed, so the
secrets never appear on screen or in chat. Uses your AWS CLI sign-in and region.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from midflight.config import load_dotenv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stack", default="midflight", help="CloudFormation stack name")
    args = parser.parse_args()

    load_dotenv()
    key_path = os.environ.get("MIDFLIGHT_GITHUB_PRIVATE_KEY_PATH")
    secret = {
        "github_client_secret": os.environ.get("MIDFLIGHT_GITHUB_CLIENT_SECRET", ""),
        "github_private_key": Path(key_path).expanduser().read_text() if key_path else "",
        "github_webhook_secret": os.environ.get("MIDFLIGHT_GITHUB_WEBHOOK_SECRET", ""),
    }
    missing = [name for name, value in secret.items() if not value]
    if missing:
        sys.exit(f"missing in .env: {', '.join(missing)} (see .env.example)")

    outputs = boto3.client("cloudformation").describe_stacks(StackName=args.stack)["Stacks"][0]
    secret_arn = next(o["OutputValue"] for o in outputs["Outputs"] if o["OutputKey"] == "SecretArn")
    boto3.client("secretsmanager").put_secret_value(
        SecretId=secret_arn, SecretString=json.dumps(secret)
    )
    print(f"stored 3 secrets in {secret_arn.split(':')[-1]} (values not shown)")


if __name__ == "__main__":
    main()
