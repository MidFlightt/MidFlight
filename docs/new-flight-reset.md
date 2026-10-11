# Starting a fresh demo flight

Reuse the same GitHub repository and local workspaces. A fresh flight removes old
claims and decisions from the active coordination context while preserving history.
This feature must be deployed to both hosted web and worker functions before use.

The lead can call `start_new_flight` with the project ID, a unique request ID, and
the current `coord_rev` from project state. Reuse exactly that request ID after an
uncertain response. It returns the new project ID. Agents should discover the active
project by its exact repository; do not carry the archived project ID into new chats.

For the observer reset command, `scripts/reset_flight.py` supplies the hosted step.
Configure a private, gitignored `hosted-reset.json` in the observer folder:

```json
{
  "url": "https://YOUR-HOSTED-SERVICE",
  "project_id": "YOUR-CURRENT-PROJECT",
  "token": "YOUR-LEAD-SCRIPT-TOKEN",
  "source_plan_version": 4
}
```

Use the approved initial plan version for `source_plan_version`, not a later demo
policy change. Subsequent flights reset from version 1. Obtain the initial lead
script token through the existing authenticated hook setup. The helper rotates it
for the successor and writes credentials with mode 0600. Never commit the config,
`hosted-reset-pending.json`, or temporary credential files.

The helper retains its request journal until the local reset completes. A timeout
can therefore be retried without starting another flight. An interrupted local
reset must be recovered from its archive; do not discard the journal and reset
blindly. A coordination revision conflict requires inspecting the new work before
starting another reset request.

A reset cannot guarantee an interface disagreement: agents may independently choose
compatible interfaces. The observer must show actual claims, actual findings and
actual revisions, without inventing a conflict or a model explanation.
