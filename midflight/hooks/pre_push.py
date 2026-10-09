"""The git pre-push hook Midflight hands out (task M-4, UC-16, D8).

Nobody clones this repository to get it: the `hook_setup` tool tells the agent to
download it from `<Midflight URL>/hook/pre-push` into `.git/hooks/pre-push`, and to
store the project, a personal hook token, and optionally the task in `.git/config`.

Before each push, the hook asks `POST /projects/{pid}/push-check`:

- 200: ready (an approved claim, no unanswered blocking directive). The push goes on.
- 409: blocked. The hook prints why and stops the push.
- Midflight unreachable or any other answer: warn and push anyway (D8). The
  `midflight/verify` check on GitHub still verifies the code.

The script is kept here as a string, not a file, so it always has Unix line endings.
"""

SCRIPT = """#!/bin/sh
# Midflight pre-push hook (UC-16). Asks Midflight whether this task is ready to push:
# an approved claim and no unanswered blocking directive. If Midflight can't be
# reached, it warns and lets the push through; midflight/verify still checks the code.
#
# Set up by Midflight's hook_setup tool, which stores these in .git/config:
#   midflight.url, midflight.project, midflight.token, and optionally midflight.task
url=$(git config --get midflight.url)
project=$(git config --get midflight.project)
token=$(git config --get midflight.token)
task=$(git config --get midflight.task)
if [ -z "$url" ] || [ -z "$project" ] || [ -z "$token" ]; then
  echo "midflight: hook not set up (ask your agent to call hook_setup); pushing anyway." >&2
  exit 0
fi
if [ -n "$task" ]; then body="{\\"task_id\\": \\"$task\\"}"; else body="{}"; fi
reply=$(curl -sS -m 20 -X POST "$url/projects/$project/push-check" \\
  -H "Authorization: Bearer $token" -H "Content-Type: application/json" \\
  -d "$body" -w "\\n%{http_code}" 2>/dev/null) || {
  echo "midflight: can't reach Midflight; pushing anyway (midflight/verify still checks)." >&2
  exit 0
}
code=$(printf '%s\\n' "$reply" | tail -n 1)
text=$(printf '%s\\n' "$reply" | sed '$d')
case "$code" in
  200) exit 0 ;;
  409) printf 'midflight: push blocked.\\n%s\\n' "$text" >&2; exit 1 ;;
  *) printf 'midflight: unexpected answer (%s); pushing anyway.\\n%s\\n' "$code" "$text" >&2
     exit 0 ;;
esac
"""
