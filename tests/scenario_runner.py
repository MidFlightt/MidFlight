"""Plays the YAML scenarios in tests/scenarios/ against the real services and fakes.

A scenario reads like a demo script: who submits what, and what Midflight must
answer. Claims list only what differs from the demo defaults in demo_fixture.py.
The schema below is strict, so a typo in a scenario fails instead of passing quietly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from demo_fixture import NOW, PROJECT, seed, submission
from midflight.adapters.clock import FixedClock
from midflight.adapters.memory_store import MemoryStore
from midflight.domain.models import ClaimState, FindingKind, Job, JobKind, Participant, SyncState
from midflight.ports import ClaimReviewRequest, Commit, JobHandler, ReviewerUnavailable
from midflight.services.claims import ClaimService
from midflight.services.errors import ServiceError

SCENARIO_DIR = Path(__file__).parent / "scenarios"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Schema --------------------------------------------------------------------------------


class Expect(Strict):
    state: ClaimState | None = None
    revision: int | None = None
    findings: list[FindingKind] | None = None
    blocking: list[FindingKind] | None = None
    correction: str | None = None
    contracts: list[str] | None = None
    review_complete: bool | None = None
    error: str | None = None
    hint_contains: str | None = None
    nothing_saved: bool = False


class Submit(Strict):
    as_: str = Field(alias="as")
    name: str | None = None
    revise: str | None = None
    claim: dict[str, Any] = {}


class Finish(Strict):
    as_: str = Field(alias="as")
    claim: str
    reason: str | None = None


class Race(Strict):
    """Two claims submitted at once. The first review is still running when the second
    one saves its verdict, so the first must reread and rerun (INV-02)."""

    as_: str = Field(alias="as")
    names: list[str] = Field(min_length=2, max_length=2)
    claims: list[dict[str, Any]] = [{}, {}]


class Step(Strict):
    say: str | None = None
    submit: Submit | None = None
    withdraw: Finish | None = None
    close: Finish | None = None
    race: Race | None = None
    go_stale: str | None = None
    claims: dict[str, ClaimState] | None = None
    expect: Expect | None = None

    @model_validator(mode="after")
    def _one_action(self) -> Self:
        actions = [self.submit, self.withdraw, self.close, self.race, self.go_stale, self.claims]
        if sum(a is not None for a in actions) != 1:
            raise ValueError("each step needs exactly one action")
        return self


class Scenario(Strict):
    name: str
    requirement: str
    use_cases: list[str]
    plan_version: int = 1
    # Scripted AI reviewer replies, in order. Once they run out it finds nothing.
    reviewer: list[Any] = []
    steps: list[Step] = Field(min_length=1)


# Fakes ---------------------------------------------------------------------------------


class ScenarioReviewer:
    """Replies in order. `{raise: unavailable}` simulates a timeout; a callable runs."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)

    def review_claim(self, request: ClaimReviewRequest) -> Any:
        reply = self.replies.pop(0) if self.replies else []
        if callable(reply):
            return reply(request)
        if reply == {"raise": "unavailable"}:
            raise ReviewerUnavailable("timed out (scenario)")
        return reply

    def review_commit(self, request: object) -> Any:
        raise NotImplementedError


class HoldingRunner:
    """Runs jobs immediately, or holds them while `holding` is set."""

    def __init__(self) -> None:
        self.handlers: dict[JobKind, JobHandler] = {}
        self.holding = False
        self.held: list[Job] = []

    def register(self, kind: JobKind, handler: JobHandler) -> None:
        self.handlers[kind] = handler

    def submit(self, job: Job) -> None:
        if self.holding:
            self.held.append(job)
        else:
            self.handlers[job.kind](job)

    def run_held(self) -> None:
        if self.held:
            job = self.held.pop(0)
            self.handlers[job.kind](job)


# Runner --------------------------------------------------------------------------------


def load(path: Path) -> Scenario:
    return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def all_scenarios() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("*.yaml"))


class Play:
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.store = MemoryStore()
        self.runner = HoldingRunner()
        self.reviewer = ScenarioReviewer(scenario.reviewer)
        self.service = ClaimService(self.store, self.runner, FixedClock(NOW), self.reviewer)
        self.runner.register(JobKind.CLAIM_REVIEW, self.service.run_review)
        self.people = seed(self.store, scenario.plan_version)
        self.named: dict[str, str] = {}

    def run(self) -> None:
        for number, step in enumerate(self.scenario.steps, start=1):
            label = f"{self.scenario.name}, step {number}" + (f" ({step.say})" if step.say else "")
            try:
                self._step(step)
            except AssertionError as failure:
                raise AssertionError(f"{label}: {failure}") from None

    def _agent(self, task: str) -> Participant:
        return self.people[f"p-{task.lower()}"]

    def _step(self, step: Step) -> None:
        before = self.store.get_project(PROJECT), len(self.store.list_claims(PROJECT))
        claim_id: str | None = None
        error: ServiceError | None = None
        try:
            if step.submit:
                claim_id = self._submit(step.submit)
            elif step.withdraw:
                claim_id = self.named[step.withdraw.claim]
                self.service.withdraw(
                    self._agent(step.withdraw.as_), claim_id, step.withdraw.reason
                )
            elif step.close:
                claim_id = self.named[step.close.claim]
                self.service.close(self._agent(step.close.as_), claim_id, step.close.reason)
            elif step.race:
                self._race(step.race)
            elif step.go_stale:
                self._go_stale(step.go_stale)
            elif step.claims:
                for name, state in step.claims.items():
                    claim = self.store.get_claim(self.named[name])
                    assert claim is not None, f"no claim named {name}"
                    assert claim.state is state, f"{name} is {claim.state}, expected {state}"
        except ServiceError as raised:
            error = raised
        self._check(step.expect, claim_id, error, before)

    def _submit(self, action: Submit) -> str:
        overrides = dict(action.claim)
        if action.revise:
            overrides["claim_id"] = self.named[action.revise]
        sent = submission(action.as_, **overrides)
        result = self.service.submit(self._agent(action.as_), sent)
        if action.name:
            self.named[action.name] = result.claim_id
        return result.claim_id

    def _race(self, race: Race) -> None:
        agent = self._agent(race.as_)
        self.runner.holding = True
        for name, overrides in zip(race.names, race.claims, strict=True):
            result = self.service.submit(agent, submission(race.as_, **overrides))
            self.named[name] = result.claim_id
        self.runner.holding = False

        # The first review asks the reviewer; meanwhile the second review completes.
        def second_review_lands_first(_request: ClaimReviewRequest) -> list[Any]:
            self.runner.run_held()
            return []

        self.reviewer.replies[:0] = [second_review_lands_first]
        self.runner.run_held()

    def _go_stale(self, reason: str) -> None:
        project = self.store.get_project(PROJECT)
        assert project is not None
        stale = project.model_copy(update={"sync_state": SyncState.STALE, "sync_reason": reason})
        self.store.commit(Commit(project_id=PROJECT, idempotency_key="go-stale", puts=[stale]))

    def _check(
        self,
        expect: Expect | None,
        claim_id: str | None,
        error: ServiceError | None,
        before: tuple[Any, int],
    ) -> None:
        if expect is None or expect.error is None:
            assert error is None, f"unexpected {type(error).__name__}: {error}"
        if expect is None:
            return
        if expect.error is not None:
            assert error is not None, f"expected {expect.error}, but the step succeeded"
            assert type(error).__name__ == expect.error, f"got {type(error).__name__}: {error}"
            if expect.hint_contains:
                assert expect.hint_contains in error.hint, f"hint was {error.hint!r}"
        if expect.nothing_saved:
            after = self.store.get_project(PROJECT), len(self.store.list_claims(PROJECT))
            assert after == before, "something was saved"
        if claim_id is None or error is not None:
            return
        verdict = self.service.verdict(claim_id)
        kinds = [f.kind for f in verdict.findings]
        if expect.state is not None:
            assert verdict.state is expect.state, f"state is {verdict.state}, findings {kinds}"
        if expect.revision is not None:
            assert verdict.revision == expect.revision, f"revision is {verdict.revision}"
        if expect.findings is not None:
            assert sorted(kinds) == sorted(expect.findings), f"findings are {kinds}"
        if expect.blocking is not None:
            blocking = sorted(f.kind for f in verdict.findings if f.blocking)
            assert blocking == sorted(expect.blocking), f"blocking findings are {blocking}"
        if expect.correction is not None:
            corrections = [f.proposed_correction for f in verdict.findings]
            assert expect.correction in corrections, f"corrections are {corrections}"
        if expect.contracts is not None:
            contracts = [c.id for c in verdict.contracts]
            assert contracts == expect.contracts, f"contracts are {contracts}"
        if expect.review_complete is not None:
            assert verdict.review_complete is expect.review_complete
