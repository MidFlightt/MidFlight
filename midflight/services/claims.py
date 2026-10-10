"""Claims: submit, revise, withdraw, close, and review (UC-04, UC-05, UC-06).

`submit` saves the claim and its review job in one commit, then hands the job to the
runner. `run_review` is the job handler: rules first, then the AI reviewer, then a
pure decision, saved only if the project's coord_rev hasn't moved since the review
read it (INV-02). If it moved, the review reruns from a fresh read.

A conflict between people's requirements opens an escalation for the lead in the same
commit (UC-12); `midflight.services.escalations` resolves it (UC-13).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from midflight.domain.decide import decide_claim
from midflight.domain.models import (
    Claim,
    ClaimState,
    Contract,
    Directive,
    Entity,
    Escalation,
    EscalationState,
    Evidence,
    EvidenceKind,
    Finding,
    FindingKind,
    FindingSeverity,
    Id,
    InterfaceUse,
    Job,
    JobKind,
    JobState,
    Model,
    Participant,
    Plan,
    Project,
    Resolution,
    Role,
    Sha,
    SyncState,
    Text,
    Version,
)
from midflight.domain.rules import check_claim, has_blocking, stale_plan, unknown_references
from midflight.domain.states import (
    ACTIVE_CLAIM_STATES,
    CLAIM_TRANSITIONS,
    OPEN_DIRECTIVE_STATES,
    IllegalTransition,
    check_claim_transition,
    move_claim,
)
from midflight.ports import (
    ClaimReviewRequest,
    Clock,
    Commit,
    JobRunner,
    Reviewer,
    ReviewerUnavailable,
    RevisionConflict,
    Store,
)
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.errors import InvalidRequest, NotFound, PermissionDenied, StateConflict
from midflight.services.review import parse_reviewer_findings, reviewer_unavailable

# How many times a review rereads and reruns when another change lands first (UC-05 6a).
MAX_REVIEW_RUNS = 3
# How many times the reviewer is asked before the review counts as incomplete (UC-05 4a).
MAX_REVIEWER_ATTEMPTS = 2

# The claims the AI reviewer compares a new claim with.
_COMPARED_STATES = ACTIVE_CLAIM_STATES - {ClaimState.NEEDS_REVISION}

INTENT_NOTE = (
    "Midflight checked your declared intent against the plan and other claims, not your "
    "code. Build against the contracts listed here; midflight/verify checks the code. "
    "What you assume about another task is shown to that task's agent at its next "
    "check-in; an approval doesn't mean they agreed to it."
)


class ClaimSubmission(Model):
    """What an agent sends with `submit_claim`. Leave `claim_id` empty for a new claim."""

    claim_id: Id | None = None
    task_id: Id
    branch: Text
    base_sha: Sha
    plan_version: Version
    requirement_ids: list[Id] = []
    files: list[Text] = []
    provides: list[InterfaceUse] = []
    consumes: list[InterfaceUse] = []
    no_interfaces: bool = False
    assumptions: list[Text] = []
    acceptance_criteria: list[Text] = []
    reason: str | None = None


@dataclass(frozen=True)
class SubmitResult:
    claim_id: str
    revision: int
    job_id: str
    state: ClaimState


@dataclass(frozen=True)
class Verdict:
    """What the agent gets back: the decision, why, and what to build against."""

    claim_id: str
    revision: int
    state: ClaimState
    findings: Sequence[Finding]
    contracts: Sequence[Contract]
    directives: Sequence[Directive]
    note: str = INTENT_NOTE
    review_complete: bool = True


class ClaimService:
    def __init__(
        self,
        store: Store,
        runner: JobRunner,
        clock: Clock,
        reviewer: Reviewer | None = None,
    ) -> None:
        self._store = store
        self._runner = runner
        self._clock = clock
        self._reviewer = reviewer

    # Submit and revise (UC-04, UC-06) --------------------------------------------------

    def submit(
        self,
        actor: Participant,
        submission: ClaimSubmission,
        correlation_id: str | None = None,
    ) -> SubmitResult:
        """Save a new claim or revision with its review job, then start the review."""
        correlation_id = correlation_id or new_correlation_id()
        # Any active member may claim a task they own, the lead included: in a hosted
        # project the lead is usually a developer too. Ownership is checked below.
        if not actor.active:
            raise PermissionDenied("you were removed from this project")
        project = self._project(actor.project_id)
        plan = self._current_plan(project)

        task = plan.task(submission.task_id)
        if task is None:
            valid = ", ".join(t.id for t in plan.tasks)
            raise InvalidRequest(
                f"plan v{plan.version} has no task {submission.task_id}", f"Use one of: {valid}."
            )
        if task.owner != actor.id:
            raise PermissionDenied(f"task {task.id} is assigned to another agent")

        claim_id, revision = self._next_revision(actor, submission)
        now = self._clock.now()
        values = submission.model_dump(exclude={"claim_id"})
        try:
            claim = Claim(
                **values,
                id=claim_id,
                revision=revision,
                project_id=project.id,
                agent_id=actor.id,
                state=ClaimState.PENDING,
                created_at=now,
            )
        except ValidationError as error:
            raise InvalidRequest(f"the claim is not valid: {error}") from error
        if not claim.is_complete:
            claim = claim.model_copy(update={"state": ClaimState.DRAFT})

        # Unknown ids and an old plan version are refused outright (UC-04 2a, 2b).
        refusals = [*stale_plan(claim, plan), *unknown_references(claim, plan)]
        if refusals:
            raise InvalidRequest(
                "the claim cites an old plan version or ids that don't exist; nothing was saved",
                " ".join(f.proposed_correction or "" for f in refusals).strip(),
                refusals,
            )

        job = Job(
            id=self._store.next_id(project.id, "J"),
            project_id=project.id,
            kind=JobKind.CLAIM_REVIEW,
            subject_id=review_subject(claim_id, revision),
            idempotency_key=f"claim:{claim_id}:{revision}",
            correlation_id=correlation_id,
            created_at=now,
            updated_at=now,
        )
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor=actor.id,
            action="claim.submitted" if revision == 1 else "claim.revised",
            entity_ids=[claim_id, job.id],
            reason=submission.reason or ("new claim" if revision == 1 else "revised claim"),
            correlation_id=correlation_id,
            idempotency_key=job.idempotency_key,
            versions={"plan": plan.version, "claim_revision": revision},
        )
        result = self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=job.idempotency_key,
                puts=[claim, job],
                audit=[event],
                bump_coord_rev=True,
            )
        )
        if result.duplicate:
            raise StateConflict(
                f"revision {revision} of {claim_id} was already submitted",
                "Check in for the latest revision, then submit again.",
            )
        self._runner.submit(job)
        saved = self._store.get_claim(claim_id, revision)
        assert saved is not None
        return SubmitResult(claim_id, revision, job.id, saved.state)

    def _next_revision(self, actor: Participant, submission: ClaimSubmission) -> tuple[str, int]:
        if submission.claim_id is None:
            return self._store.next_id(actor.project_id, "C"), 1
        previous = self._store.get_claim(submission.claim_id)
        if previous is None or previous.project_id != actor.project_id:
            raise NotFound(f"no claim {submission.claim_id}")
        if previous.agent_id != actor.id:
            raise PermissionDenied(f"claim {previous.id} belongs to another agent (UC-06 1b)")
        if previous.task_id != submission.task_id:
            raise InvalidRequest(
                f"claim {previous.id} is for task {previous.task_id}",
                "Submit a new claim for a different task.",
            )
        if previous.state in (ClaimState.WITHDRAWN, ClaimState.CLOSED):
            raise StateConflict(
                f"claim {previous.id} is {previous.state}", "Submit a new claim instead."
            )
        return previous.id, previous.revision + 1

    # Withdraw and close (UC-06 1a, D11) ------------------------------------------------

    def withdraw(self, actor: Participant, claim_id: str, reason: str | None = None) -> Claim:
        return self._finish(actor, claim_id, ClaimState.WITHDRAWN, reason or "withdrawn")

    def close(self, actor: Participant, claim_id: str, reason: str | None = None) -> Claim:
        return self._finish(actor, claim_id, ClaimState.CLOSED, reason or "work done")

    def _finish(self, actor: Participant, claim_id: str, target: ClaimState, reason: str) -> Claim:
        claim = self._store.get_claim(claim_id)
        if claim is None or claim.project_id != actor.project_id:
            raise NotFound(f"no claim {claim_id}")
        if claim.agent_id != actor.id:
            raise PermissionDenied(f"claim {claim_id} belongs to another agent")
        if claim.state is target:
            return claim
        try:
            updated = move_claim(claim, target)
        except IllegalTransition as error:
            hint = "Only an approved claim can be closed." if target is ClaimState.CLOSED else ""
            raise StateConflict(str(error), hint) from error
        key = f"{target}:{claim_id}:{claim.revision}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=claim.project_id,
            actor=actor.id,
            action=f"claim.{target}",
            entity_ids=[claim_id],
            reason=reason,
            correlation_id=new_correlation_id(),
            idempotency_key=key,
            versions={"plan": claim.plan_version, "claim_revision": claim.revision},
        )
        self._store.commit(
            Commit(
                project_id=claim.project_id,
                idempotency_key=key,
                puts=[updated],
                audit=[event],
                bump_coord_rev=True,
            )
        )
        saved = self._store.get_claim(claim_id, claim.revision)
        assert saved is not None
        return saved

    # Review (UC-05) --------------------------------------------------------------------

    def run_review(self, job: Job) -> None:
        """The claim_review job handler. Safe to call twice for the same job."""
        stored_job = self._store.get_job(job.id)
        if stored_job is not None and stored_job.state in (JobState.SUCCEEDED, JobState.FAILED):
            return
        claim_id, revision = parse_review_subject(job.subject_id)
        for run in range(1, MAX_REVIEW_RUNS + 1):
            project = self._project(job.project_id)
            claim = self._store.get_claim(claim_id, revision)
            latest = self._store.get_claim(claim_id)
            if claim is None or latest is None:
                raise LookupError(f"review job {job.id} names unknown claim {claim_id}")
            if latest.revision != revision or claim.state not in (
                ClaimState.PENDING,
                ClaimState.DRAFT,
            ):
                self._close_job(job, project, JobState.SUCCEEDED, "superseded or no longer open")
                return
            plan = self._current_plan(project)
            others = self._store.list_claims(project.id)
            findings = check_claim(claim, plan, others)
            if claim.is_complete and not has_blocking(findings):
                findings += self._reviewer_findings(claim, plan, others, findings)
                findings = self._set_aside_dismissed(project, claim, findings)
            target = decide_claim(claim, findings, stale=project.sync_state is SyncState.STALE)
            if target is not claim.state:
                check_claim_transition(claim.state, target)
            reviewed = Claim.model_validate(
                claim.model_dump() | {"state": target, "findings": findings}
            )
            escalated = (
                self._escalation(project, plan, claim, findings, others)
                if target is ClaimState.HUMAN_REVIEW_REQUIRED
                else []
            )
            incomplete = any(f.kind is FindingKind.REVIEWER_UNAVAILABLE for f in findings)
            done = job.model_copy(
                update={
                    "state": JobState.FAILED if incomplete else JobState.SUCCEEDED,
                    "attempts": job.attempts + run,
                    "error": "review incomplete: the AI reviewer was unavailable"
                    if incomplete
                    else None,
                    "result_ref": job.subject_id,
                    "updated_at": self._clock.now(),
                }
            )
            blocking = sum(f.blocking for f in findings)
            event = audit_event(
                self._store,
                self._clock,
                project_id=project.id,
                actor="midflight",
                action="claim.reviewed",
                entity_ids=[claim_id, job.id, *(e.id for e in escalated)],
                reason=f"{target}: {blocking} blocking, {len(findings) - blocking} info",
                correlation_id=job.correlation_id,
                idempotency_key=f"review:{job.id}",
                versions={
                    "plan": plan.version,
                    "claim_revision": revision,
                    "coord_rev": project.coord_rev,
                },
            )
            try:
                self._store.commit(
                    Commit(
                        project_id=project.id,
                        idempotency_key=f"review:{job.id}",
                        puts=[reviewed, done, *escalated],
                        audit=[event],
                        expected_coord_rev=project.coord_rev,
                        bump_coord_rev=True,
                    )
                )
                return
            except RevisionConflict:
                continue  # another change landed first: reread and rerun (UC-05 6a)
        project = self._project(job.project_id)
        self._close_job(
            job,
            project,
            JobState.FAILED,
            f"other changes kept landing; review gave up after {MAX_REVIEW_RUNS} runs",
        )

    def _reviewer_findings(
        self, claim: Claim, plan: Plan, others: Sequence[Claim], rule_findings: Sequence[Finding]
    ) -> list[Finding]:
        if self._reviewer is None:
            return []
        # Only claims that say what someone is building now. A withdrawn or closed claim
        # doesn't, and neither does one waiting to be revised: its agent has been told to
        # change it, so a conflict with it is a conflict with yesterday's intent (D29).
        related = [o for o in others if o.id != claim.id and o.state in _COMPARED_STATES]
        request = ClaimReviewRequest(
            plan=plan, claim=claim, other_claims=related, rule_findings=rule_findings
        )
        known = _known_ids(plan, claim, related)
        reason = "no usable reply"
        for _ in range(MAX_REVIEWER_ATTEMPTS):
            try:
                raw = self._reviewer.review_claim(request)
            except ReviewerUnavailable as error:
                reason = str(error) or "timed out"
                continue
            parsed = parse_reviewer_findings(raw, known, claim)
            if parsed is not None:
                return [_only_between_people(f, plan, claim, related) for f in parsed]
            reason = "the reply didn't match the findings schema or cited unknown ids"
        return [reviewer_unavailable(claim, reason)]

    def _escalation(
        self,
        project: Project,
        plan: Plan,
        claim: Claim,
        findings: Sequence[Finding],
        others: Sequence[Claim],
    ) -> list[Entity]:
        """An escalation for the lead, plus the other claims it involves (UC-12).

        Nothing new if an escalation for this claim is already open. If one is open about
        the same requirement, or already involves a claim this conflict cites, this claim
        joins it, so the lead decides one question once.
        """
        conflicts = [
            f for f in findings if f.blocking and f.kind is FindingKind.REQUIREMENT_CONFLICT
        ]
        still_open = [
            e for e in self._store.list_escalations(project.id) if e.state is EscalationState.OPEN
        ]
        if not conflicts or any(claim.id in e.claim_ids for e in still_open):
            return []
        cited = {i for f in conflicts for i in f.affected_ids}
        involved = [claim, *(o for o in others if o.id in cited and o.id != claim.id)]
        requirements = {i for i in cited if plan.requirement(i)}
        claim_ids = {c.id for c in involved}
        same_question = next(
            (
                e
                for e in still_open
                if requirements & set(e.competing_requirement_ids) or claim_ids & set(e.claim_ids)
            ),
            None,
        )
        if same_question is not None:
            joined = Escalation.model_validate(
                same_question.model_dump()
                | {
                    "claim_ids": list(
                        dict.fromkeys([*same_question.claim_ids, *(c.id for c in involved)])
                    ),
                    "finding_ids": [*same_question.finding_ids, *(f.id for f in conflicts)],
                }
            )
            return [joined]
        escalation = Escalation(
            id=self._store.next_id(project.id, "E"),
            project_id=project.id,
            competing_requirement_ids=sorted(i for i in cited if plan.requirement(i)),
            claim_ids=[c.id for c in involved],
            finding_ids=[f.id for f in conflicts],
            evidence=[
                *(e for f in conflicts for e in f.evidence),
                *(
                    Evidence(
                        kind=EvidenceKind.CLAIM,
                        ref=f"{c.id} rev {c.revision} ({c.task_id})",
                        excerpt="Assumes: " + "; ".join(c.assumptions)[:480],
                    )
                    for c in involved
                    if c.assumptions
                ),
            ],
            explanation=" ".join(f.explanation for f in conflicts),
            created_at=self._clock.now(),
        )
        # The other side's claims wait for the lead too (D14).
        waiting = ClaimState.HUMAN_REVIEW_REQUIRED
        moved = [
            move_claim(c, waiting) for c in involved[1:] if waiting in CLAIM_TRANSITIONS[c.state]
        ]
        return [escalation, *moved]

    def _set_aside_dismissed(
        self, project: Project, claim: Claim, findings: list[Finding]
    ) -> list[Finding]:
        """Keep a conflict the lead dismissed as `info`, so it no longer blocks (UC-13).

        Applies to claim revisions written before the lead decided; a later revision gets
        a fresh review.
        """
        dismissed = [
            e
            for e in self._store.list_escalations(project.id)
            if e.resolution is Resolution.DISMISS
            and claim.id in e.claim_ids
            and e.resolved_at is not None
            and claim.created_at <= e.resolved_at
        ]
        if not dismissed:
            return findings
        note = "; ".join(f"{e.id}: {e.reason}" for e in dismissed)
        return [
            Finding.model_validate(
                f.model_dump()
                | {
                    "severity": FindingSeverity.INFO,
                    "explanation": f"{f.explanation} (Set aside: the lead dismissed this "
                    f"conflict, {note})",
                }
            )
            if f.kind is FindingKind.REQUIREMENT_CONFLICT and f.blocking
            else f
            for f in findings
        ]

    def _close_job(self, job: Job, project: Project, state: JobState, note: str) -> None:
        done = job.model_copy(
            update={
                "state": state,
                "error": None if state is JobState.SUCCEEDED else note,
                "updated_at": self._clock.now(),
            }
        )
        key = f"job-closed:{job.id}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor="midflight",
            action=f"job.{state}",
            entity_ids=[job.id],
            reason=note,
            correlation_id=job.correlation_id,
            idempotency_key=key,
        )
        self._store.commit(
            Commit(project_id=project.id, idempotency_key=key, puts=[done], audit=[event])
        )

    def retry_review(self, lead: Participant, job_id: str) -> Job:
        """Rerun a failed claim review as a new job (UC-14 4a). Lead only."""
        if lead.role is not Role.LEAD:
            raise PermissionDenied("only the lead can retry jobs (INV-08)")
        job = self._store.get_job(job_id)
        if job is None or job.project_id != lead.project_id:
            raise NotFound(f"no job {job_id}")
        if job.kind is not JobKind.CLAIM_REVIEW or job.state is not JobState.FAILED:
            raise StateConflict(f"job {job_id} is a {job.kind} job in state {job.state}")
        now = self._clock.now()
        retry = job.model_copy(
            update={
                "id": self._store.next_id(job.project_id, "J"),
                "state": JobState.QUEUED,
                "attempts": 0,
                "error": None,
                "result_ref": None,
                "idempotency_key": f"retry:{job.id}",
                "created_at": now,
                "updated_at": now,
            }
        )
        event = audit_event(
            self._store,
            self._clock,
            project_id=job.project_id,
            actor=lead.id,
            action="job.retried",
            entity_ids=[job.id, retry.id],
            reason=f"retry of failed job {job.id}",
            correlation_id=job.correlation_id,
            idempotency_key=retry.idempotency_key,
        )
        result = self._store.commit(
            Commit(
                project_id=job.project_id,
                idempotency_key=retry.idempotency_key,
                puts=[retry],
                audit=[event],
            )
        )
        if result.duplicate:
            raise StateConflict(f"job {job_id} was already retried")
        self._runner.submit(retry)
        saved = self._store.get_job(retry.id)
        assert saved is not None
        return saved

    # Verdict ---------------------------------------------------------------------------

    def verdict(self, claim_id: str, revision: int | None = None) -> Verdict:
        """The reply `submit_claim` and `check_in` give the agent for a claim."""
        claim = self._store.get_claim(claim_id, revision)
        if claim is None:
            raise NotFound(f"no claim {claim_id}")
        project = self._project(claim.project_id)
        plan = self._current_plan(project)
        task = plan.task(claim.task_id)
        contract_ids = [*task.provides, *task.consumes] if task else []
        contracts = [c for c in (plan.contract(i) for i in contract_ids) if c is not None]
        directives = [
            d
            for d in self._store.list_directives(project.id, claim.task_id)
            if d.state in OPEN_DIRECTIVE_STATES
        ]
        complete = not any(f.kind is FindingKind.REVIEWER_UNAVAILABLE for f in claim.findings)
        return Verdict(
            claim_id=claim.id,
            revision=claim.revision,
            state=claim.state,
            findings=claim.findings,
            contracts=contracts,
            directives=directives,
            review_complete=complete,
        )

    # Helpers ---------------------------------------------------------------------------

    def _project(self, project_id: str) -> Project:
        project = self._store.get_project(project_id)
        if project is None:
            raise NotFound(f"no project {project_id}")
        return project

    def _current_plan(self, project: Project) -> Plan:
        plan = (
            self._store.get_plan(project.id, project.current_plan_version)
            if project.current_plan_version
            else None
        )
        if plan is None:
            raise StateConflict(
                "the project has no approved plan yet", "The lead approves plan v1 first."
            )
        return plan


def review_subject(claim_id: str, revision: int) -> str:
    """A claim review job's subject: which claim revision it reviews."""
    return f"{claim_id}/{revision}"


def parse_review_subject(subject_id: str) -> tuple[str, int]:
    claim_id, _, revision = subject_id.rpartition("/")
    return claim_id, int(revision)


def _only_between_people(
    finding: Finding, plan: Plan, claim: Claim, others: Sequence[Claim]
) -> Finding:
    """A requirement conflict needs two sides: claims of two different tasks, or a claim
    and a plan requirement. One that cites only one task's claims isn't a disagreement
    between people, so it's kept as a note instead of stopping the agent for the lead."""
    if finding.kind is not FindingKind.REQUIREMENT_CONFLICT or not finding.blocking:
        return finding
    cited = set(finding.affected_ids)
    tasks = {c.task_id for c in (claim, *others) if c.id in cited}
    cites_requirement = any(plan.requirement(i) is not None for i in cited)
    if len(tasks) >= 2 or cites_requirement:
        return finding
    return Finding.model_validate(
        finding.model_dump()
        | {
            "severity": FindingSeverity.INFO,
            "explanation": f"{finding.explanation} (Not escalated: it cites only one "
            "task's claims, so it isn't a conflict between people.)",
        }
    )


def _known_ids(plan: Plan, claim: Claim, others: Sequence[Claim]) -> set[str]:
    return {
        claim.id,
        *(o.id for o in others),
        *(r.id for r in plan.requirements),
        *(t.id for t in plan.tasks),
        *(c.id for c in plan.contracts),
    }
