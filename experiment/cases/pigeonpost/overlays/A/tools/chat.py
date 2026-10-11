"""The team chat: one file, CHAT.md, on the `chat` branch of the team's repository.

    python tools/chat.py read              print the chat
    python tools/chat.py post "<message>"  add a message at the end

Every teammate's laptop has its own copy of the repository, so reading fetches the chat
from the shared repository first, and posting pushes to it (trying again if someone else
posted in the meantime). Your own branch and files aren't touched.
"""

import subprocess
import sys

BRANCH = "chat"
FILE = "CHAT.md"


def git(*args: str, data: str | None = None) -> tuple[bool, str]:
    """Run git; bytes in and out, so line endings are the same on every laptop."""
    done = subprocess.run(["git", *args], input=None if data is None else data.encode("utf-8"),
                          capture_output=True)  # fmt: skip
    if done.returncode != 0:
        return False, done.stderr.decode("utf-8", errors="replace").strip()
    return True, done.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def must(*args: str, data: str | None = None) -> str:
    ok, out = git(*args, data=data)
    if not ok:
        sys.exit(f"git {' '.join(args)} failed: {out}")
    return out


def read() -> str:
    must("fetch", "--quiet", "origin", BRANCH)
    return must("show", f"FETCH_HEAD:{FILE}")


def post(message: str) -> None:
    for _ in range(8):
        chat = read()
        tip = must("rev-parse", "FETCH_HEAD").strip()
        blob = must("hash-object", "-w", "--stdin", data=chat + message.strip() + "\n").strip()
        tree = must("mktree", data=f"100644 blob {blob}\t{FILE}\n").strip()
        commit = must("commit-tree", tree, "-p", tip, "-m", "chat").strip()
        pushed, _ = git("push", "--quiet", "origin", f"{commit}:refs/heads/{BRANCH}")
        if pushed:
            print("posted")
            return
    sys.exit("couldn't post: the chat kept changing; try again")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:] == ["read"]:
        print(read())
    elif len(sys.argv) == 3 and sys.argv[1] == "post":
        post(sys.argv[2])
    else:
        sys.exit(__doc__)
