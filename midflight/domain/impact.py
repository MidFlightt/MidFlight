"""What changed between two plan versions (UC-03 step 3). Pure: no I/O.

S-6 extends this with the tasks a change affects (UC-08).
"""

from __future__ import annotations

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


def _content(item: object, attr: str) -> dict[str, object]:
    # A contract's version number follows the plan, so it isn't a change by itself.
    exclude = {"version"} if attr == "contracts" else set()
    return item.model_dump(exclude=exclude)  # type: ignore[attr-defined]
