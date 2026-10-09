"""Job runners: run a background job now (laptops, tests) or later (AWS)."""

from __future__ import annotations

from midflight.domain.models import Job, JobKind
from midflight.ports import JobHandler


class _Dispatch:
    def __init__(self) -> None:
        self._handlers: dict[JobKind, JobHandler] = {}

    def register(self, kind: JobKind, handler: JobHandler) -> None:
        self._handlers[kind] = handler

    def _run(self, job: Job) -> None:
        handler = self._handlers.get(job.kind)
        if handler is None:
            raise LookupError(f"no handler registered for {job.kind} jobs")
        handler(job)


class InlineRunner(_Dispatch):
    """Runs each job as soon as it is submitted, in the caller's thread.

    Handler errors propagate, so a test sees them instead of a silent failed job.
    """

    def submit(self, job: Job) -> None:
        self._run(job)


class DeferredRunner(_Dispatch):
    """Holds jobs until a test runs them, so tests can control the order."""

    def __init__(self) -> None:
        super().__init__()
        self.pending: list[Job] = []

    def submit(self, job: Job) -> None:
        self.pending.append(job)

    def run_next(self) -> Job:
        job = self.pending.pop(0)
        self._run(job)
        return job

    def run_all(self) -> None:
        while self.pending:
            self.run_next()


class StreamRunner:
    """AWS: do nothing here. The job was saved in the same commit as its claim, and the
    DynamoDB stream hands new job items to the worker Lambda (`midflight.aws.worker`)."""

    def submit(self, job: Job) -> None:
        return None
