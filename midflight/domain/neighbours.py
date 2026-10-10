"""Which of the other agents' assumptions are about a given task (D27). Pure: no I/O.

Contracts say what data crosses between tasks. They can't say everything: which function
one part calls in another, which route it posts to. Agents write those down as
assumptions. Midflight shows each one to the task it is about at that task's next
check-in, so the agent who has to make it true hears about it.

An assumption is about a task when it names the task's id ("T3"), its title
("Bookings"), or a file only that task's claim lists ("app/bookings.py"). Nothing here
judges whether the assumption is right; it is passed on as written.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from midflight.domain.models import Claim, Task
from midflight.domain.states import ACTIVE_CLAIM_STATES

# Keeps a check-in reply short however much the neighbours wrote.
MAX_ASSUMPTIONS = 12
MAX_LENGTH = 300


@dataclass(frozen=True)
class NeighbourAssumption:
    """One thing another task's claim takes for granted about this task."""

    task_id: str
    claim_id: str
    text: str


def assumptions_about(
    task: Task, own_files: Collection[str], claims: Sequence[Claim], by_title: bool = True
) -> list[NeighbourAssumption]:
    """What the other tasks' active claims assume about `task`, oldest claim first.

    A title is often an ordinary word ("Bookings", "Reports"). That is fine for passing
    an assumption on, where a stray match costs one extra line. Recording one as agreed
    needs more, so `by_title=False` counts only the task's id and files (D30).
    """
    found = []
    for claim in sorted(claims, key=lambda c: c.created_at):
        if claim.task_id == task.id or claim.state not in ACTIVE_CLAIM_STATES:
            continue
        # A file both claims list (a shared README) doesn't point at either task.
        files = [f for f in own_files if f not in claim.files]
        found += [
            NeighbourAssumption(claim.task_id, claim.id, text[:MAX_LENGTH])
            for text in claim.assumptions
            if _mentions(text, task, files, by_title)
        ]
    return found[:MAX_ASSUMPTIONS]


def _mentions(text: str, task: Task, files: Collection[str], by_title: bool) -> bool:
    if re.search(rf"\b{re.escape(task.id)}\b", text):
        return True
    if by_title and re.search(rf"\b{re.escape(task.title)}\b", text, re.IGNORECASE):
        return True
    return any(path in text or _name(path) in text for path in files)


def _name(path: str) -> str:
    """The file's name without its folders: `app/bookings.py` is also `bookings.py`."""
    return path.rsplit("/", 1)[-1]
