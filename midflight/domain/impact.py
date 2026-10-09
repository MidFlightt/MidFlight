"""What changed between two plan versions, and which tasks that touches (UC-03, UC-08).

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence

from midflight.domain.models import Plan


def changed_ids(old: Plan | None, new: Plan) -> list[str]:
    """Ids of requirements, tasks, and contracts added, removed, or changed, sorted."""
    if old is None:
        return []
    changed: set[str] = set()
    for attr in ("requirements", "tasks", "contracts"):
        before = {item.id: _content(item, attr) for item in getattr(old, attr)}
        after = {item.id: _content(item, attr) for item in getattr(new, attr)}
        changed |= before.keys() ^ after.keys()
        changed |= {i for i in before.keys() & after.keys() if before[i] != after[i]}
    return sorted(changed)


def affected_tasks(old: Plan, new: Plan, changed: Sequence[str]) -> dict[str, list[str]]:
    """Each task in `new` that the change touches, with the changed ids that touch it.

    A task is affected when it changed itself, implements a changed requirement, or
    provides or consumes a changed contract, in either version (UC-08 step 2). A task
    with no link to the change isn't in the result and gets nothing (step 6).
    """
    changed_set = set(changed)
    affected: dict[str, list[str]] = {}
    for task in new.tasks:
        links = {task.id, *task.requirement_ids, *task.provides, *task.consumes}
        before = old.task(task.id)
        if before is not None:
            links |= {*before.requirement_ids, *before.provides, *before.consumes}
        for plan in (old, new):
            links |= {
                c.id
                for c in plan.contracts
                if task.id == c.provider_task or task.id in c.consumer_tasks
            }
        hits = sorted(links & changed_set)
        if hits:
            affected[task.id] = hits
    return affected


def _content(item: object, attr: str) -> dict[str, object]:
    # A contract's version number follows the plan, so it isn't a change by itself.
    exclude = {"version"} if attr == "contracts" else set()
    return item.model_dump(exclude=exclude)  # type: ignore[attr-defined]
