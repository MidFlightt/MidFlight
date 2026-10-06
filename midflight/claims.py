"""Compare declarations without pretending to understand code or intentions."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Claim:
    id: str
    owner: str
    goal: str
    # None means unknown; an empty tuple explicitly declares no items.
    files: tuple[str, ...] | None = None
    interfaces: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        for field in ("id", "owner", "goal"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        for field in ("files", "interfaces"):
            value = getattr(self, field)
            if value is not None and (
                not isinstance(value, tuple)
                or any(not isinstance(item, str) or not item.strip() for item in value)
            ):
                raise ValueError(f"{field} must contain non-empty strings")

    @classmethod
    def from_dict(cls, data: dict) -> "Claim":
        if not isinstance(data, dict):
            raise ValueError("each claim must be an object")
        unknown = set(data) - {"id", "owner", "goal", "files", "interfaces"}
        if unknown:
            raise ValueError(f"unexpected claim fields: {', '.join(sorted(unknown))}")
        values = {}
        for field in ("files", "interfaces"):
            value = data.get(field)
            if value is not None and not isinstance(value, list):
                raise ValueError(f"{field} must be a list or null")
            values[field] = None if value is None else tuple(value)
        return cls(data.get("id"), data.get("owner"), data.get("goal"), **values)


@dataclass(frozen=True)
class Question:
    claim_ids: tuple[str, ...]
    reason: str
    question: str


@dataclass(frozen=True)
class Review:
    claim_id: str
    status: Literal["needs_clarification", "unknown", "no_declared_overlap"]
    questions: tuple[Question, ...]
    compared_with: tuple[str, ...]
    limitations: str = (
        "Exact declared names only; no plan, code, or semantic verification. "
        "No declared overlap is not approval to proceed."
    )


class ClaimBoard:
    """In-memory open claims. Resubmitting an ID replaces its declaration."""

    def __init__(self) -> None:
        self._claims: dict[str, Claim] = {}

    def submit(self, claim: Claim) -> Review:
        previous = self._claims.get(claim.id)
        if previous and previous.owner != claim.owner:
            raise ValueError("a revised claim must retain its owner")
        peers = [peer for peer in self._claims.values() if peer.id != claim.id]
        questions: list[Question] = []
        overlap_found = False
        missing_found = False

        # Check the new claim even when there are no peers yet.
        missing = [field for field in ("files", "interfaces") if getattr(claim, field) is None]
        if missing:
            missing_found = True
            questions.append(Question(
                (claim.id,),
                f"Unknown declarations: {', '.join(missing)}.",
                "As you learn more, which files or shared interfaces might this task touch? "
                "You can leave them unknown for now.",
            ))

        for peer in peers:
            for field in ("files", "interfaces"):
                ours, theirs = getattr(claim, field), getattr(peer, field)
                if ours is None or theirs is None:
                    missing_found = True
                    # The new claim's missing details were already noted above.
                    if theirs is None:
                        questions.append(Question(
                            (claim.id, peer.id),
                            f"Claim {peer.id} has not declared {field}.",
                            f"Could {peer.owner}'s task ({peer.goal}) share {field} "
                            f"with {claim.owner}'s task ({claim.goal})?",
                        ))
                    continue
                shared = sorted(set(ours) & set(theirs))
                if shared:
                    overlap_found = True
                    questions.append(Question(
                        (claim.id, peer.id),
                        f"Shared {field}: {', '.join(shared)}.",
                        f"What does each task need from {', '.join(shared)}, "
                        "and can both changes coexist? Overlap alone is not a conflict.",
                    ))

        self._claims[claim.id] = claim
        status = (
            "needs_clarification" if overlap_found
            else "unknown" if missing_found
            else "no_declared_overlap"
        )
        return Review(claim.id, status, tuple(questions), tuple(peer.id for peer in peers))
