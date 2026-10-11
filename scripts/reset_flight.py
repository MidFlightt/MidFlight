#!/usr/bin/env python3
"""Reset the hosted flight with a retry journal. Config and journal contain credentials."""

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def save_private(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def api(config, path, payload=None):
    url = config["url"].rstrip("/")
    if not url.startswith("https://"):
        raise RuntimeError("Hosted reset requires HTTPS.")
    request = urllib.request.Request(
        url + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + config["token"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Hosted reset HTTP {error.code}; no local reset performed.") from None


def reset_hosted(config_path, journal_path):
    config_path, journal_path = Path(config_path), Path(journal_path)
    if not config_path.exists():
        raise RuntimeError(
            "Missing hosted-reset.json. Configure url, project_id and a lead script token first."
        )
    if journal_path.exists():
        journal = json.loads(journal_path.read_text())
    else:
        config = json.loads(config_path.read_text())
        state = api(config, f"/projects/{config['project_id']}/state")
        project = state["project"]
        journal = {
            "source": config,
            "request_id": str(uuid.uuid4()),
            "expected_coord_rev": project["coord_rev"],
        }
        save_private(journal_path, journal)
    if "result" not in journal:
        source = journal["source"]
        result = api(
            source,
            f"/projects/{source['project_id']}/flights",
            {
                "request_id": journal["request_id"],
                "expected_coord_rev": journal["expected_coord_rev"],
                "source_plan_version": source.get("source_plan_version"),
            },
        )
        journal["result"] = result
        save_private(journal_path, journal)
    result = journal["result"]
    updated = dict(
        journal["source"],
        project_id=result["project"]["id"],
        token=result["token"],
        source_plan_version=1,
    )
    save_private(config_path, updated)
    plan = api(updated, f"/projects/{updated['project_id']}/plans/current")
    return {"project": result["project"], "plan": plan}
