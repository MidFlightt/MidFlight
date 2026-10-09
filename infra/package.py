"""Build `build/lambda.zip`: Midflight's code and dependencies, ready for AWS Lambda.

    uv run python infra/package.py

Lambda runs Linux on arm64 with Python 3.12, so dependencies are fetched for that
platform (uv can do this from Windows or macOS; no Docker needed). The zip is written
here rather than by SAM so `run.sh` keeps its execute permission and Unix line endings,
which zips made on Windows lose.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
SITE = BUILD / "lambda"
ZIP = BUILD / "lambda.zip"

# The web Lambda's start command. Lambda Web Adapter (a layer) runs it and forwards
# HTTP requests from the Function URL to port 8080.
RUN_SH = """#!/bin/bash
export PYTHONPATH=/var/task:$PYTHONPATH
cd /var/task
exec python3 -m uvicorn --factory midflight.main:create_app_from_env \\
    --host 0.0.0.0 --port 8080 --log-level warning
"""


def main() -> None:
    shutil.rmtree(BUILD, ignore_errors=True)
    SITE.mkdir(parents=True)
    # Commands run from the repository root, so these short relative paths are safe
    # even when the checkout's own path has spaces.
    run("uv export --no-dev --no-hashes --no-emit-project --frozen -o build/requirements.txt")
    run(
        "uv pip install --quiet -r build/requirements.txt --target build/lambda "
        "--python-platform aarch64-manylinux2014 --python-version 3.12"
    )
    shutil.copytree(
        ROOT / "midflight", SITE / "midflight", ignore=shutil.ignore_patterns("__pycache__")
    )

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SITE.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(SITE).as_posix())
        script = zipfile.ZipInfo("run.sh")
        script.external_attr = 0o100755 << 16  # a regular file, executable
        archive.writestr(script, RUN_SH)
    print(f"built {ZIP.relative_to(ROOT)} ({ZIP.stat().st_size // 1_000_000} MB)")


def run(command: str) -> None:
    subprocess.run(shlex.split(command, posix=True), check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
