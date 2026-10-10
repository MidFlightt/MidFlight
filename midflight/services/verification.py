"""Verifying pushed commits and publishing `midflight/verify` (UC-10, UC-11).

1. When the contract-test workflow finishes on a branch, GitHub calls the webhook
   (`midflight.api.webhook`), and `enqueue` saves a verification job. A redelivered
   event saves nothing.
2. The job handler `run` reads fresh data from GitHub, never the webhook's copy: the
   pull request head, the diff, the task's files, and the test results for that exact
   commit (FR-08).
3. The rules in `midflight.domain.verify` run, then the AI reviewer if they pass.
4. Before publishing, it reads the head and the plan version again. If either moved,
   the result is dropped; the newer run verifies the newer state (UC-10 6a).
5. It publishes the check and saves the verification, with a correction directive for
   the agent if the push failed, or an escalation if it touched protected files.

If GitHub is down or rate-limiting, the project is marked stale and the job fails, so
the worker retries it later (UC-15). A successful run marks the project fresh again.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from midflight.domain.models import (
    Claim,
    ClaimState,
    Directive,
    DirectiveSource,
    DirectiveState,
    Entity,
    Escalation,
    Finding,
    FindingKind,
    Job,
    JobKind,
    JobState,
    Plan,
    Project,
    Verification,
    VerificationOutcome,
)
from midflight.domain.states import SUPERSEDABLE_DIRECTIVE_STATES, check_conclusion, move_directive
from midflight.domain.verify import (
    ARTIFACT_NAME,
    check_commit,
    coverage,
    decide_verification,
    is_protected,
    parse_test_results,
    verifiable,
)
from midflight.ports import (
    ChangedFiles,
    CheckRunRequest,
    Clock,
    Commit,
    CommitReviewRequest,
    GitHub,
    GitHubUnavailable,
    JobRunner,
    Reviewer,
    ReviewerUnavailable,
    Store,
)
from midflight.services.audit import audit_event, new_correlation_id
from midflight.services.review import parse_reviewer_findings, reviewer_unavailable
from midflight.services.sync import FAULT_REASON, SyncService

# The workflow whose completion starts a verification (D4), by file name.
CONTRACT_WORKFLOW = "contract.yml"
# At most this many files are read at the head commit for the field check.
MAX_FILES = 25


@dataclass(frozen=True)
class WorkflowRun:
    """The parts of a `workflow_run.completed` webhook that Midflight uses."""

    repository: str
    installation_id: int | None
    run_id: int
    attempt: int
    head_sha: str
    head_branch: str
    delivery_id: str


class VerificationService:
    def __init__(
        self,
        store: Store,
        clock: Clock,
        runner: JobRunner,
        sync: SyncService,
        github: GitHub | None = None,
        reviewer: Reviewer | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._runner = runner
        self._sync = sync
        self._github = github
        self._reviewer = reviewer

    # Webhook (UC-10 step 1) ------------------------------------------------------------

    def enqueue(self, run: WorkflowRun) -> str | None:
        """Save a verification job for a finished run. None if ignored or a duplicate."""
        project = self._store.find_project_by_repository(run.repository)
        if project is None:
            return None
        if (
            project.github_installation_id
            and run.installation_id
            and project.github_installation_id != run.installation_id
        ):
            return None  # routed by installation: only the installation linked to the project
        now = self._clock.now()
        job = Job(
            id=self._store.next_id(project.id, "J"),
            project_id=project.id,
            kind=JobKind.VERIFICATION,
            subject_id=f"{run.run_id}/{run.head_sha}/{run.head_branch}",
            # One verification per commit and attempt: a workflow that runs on both push
            # and pull_request finishes twice for the same commit, and needs one check.
            idempotency_key=f"verify:{project.id}:{run.head_sha}:{run.attempt}",
            correlation_id=new_correlation_id(),
            created_at=now,
            updated_at=now,
        )
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor="github",
            action="verification.queued",
            entity_ids=[job.id],
            reason=f"contract tests finished on {run.head_branch} at {run.head_sha[:7]} "
            f"(run {run.run_id}, delivery {run.delivery_id or 'unknown'})",
            correlation_id=job.correlation_id,
            idempotency_key=job.idempotency_key,
            versions={"head_sha": run.head_sha},
        )
        result = self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=job.idempotency_key,
                puts=[job],
                audit=[event],
            )
        )
        if result.duplicate:
            return None
        self._runner.submit(job)
        return job.id

    # Job handler (UC-10 steps 2-7, UC-11) ----------------------------------------------

    def run(self, job: Job) -> None:
        """The verification job handler. Safe to call twice for the same job."""
        stored = self._store.get_job(job.id)
        if stored is not None and stored.state in (JobState.SUCCEEDED, JobState.FAILED):
            return
        project = self._store.get_project(job.project_id)
        if project is None:
            raise LookupError(f"verification job {job.id} names unknown project")
        if self._github is None:
            self._close(job, project, JobState.FAILED, "GitHub isn't configured on this server")
            return
        try:
            self._verify(job, project, self._github)
        except GitHubUnavailable as error:
            self._sync.mark_stale(project.id, error.reason)
            raise  # the worker retries the job later; after its retries, the dead-letter queue

    def _verify(self, job: Job, project: Project, github: GitHub) -> None:
        run_id, head_sha, branch = job.subject_id.split("/", 2)
        repo = project.repository
        if self._sync.fault_on(project.id):
            raise GitHubUnavailable(FAULT_REASON)
        plan = self._current_plan(project)
        if plan is None:
            self._close(job, project, JobState.SUCCEEDED, "no approved plan to verify against")
            return
        claim = self._claim_for(project.id, branch)
        usable = claim if claim is not None and verifiable(claim) else None

        pull = github.pull_for_branch(repo, branch)
        if pull is None and claim is None:
            # Nothing under review: for example a push to main. No check is published.
            self._close(job, project, JobState.SUCCEEDED, f"no pull request or claim for {branch}")
            return
        if pull is not None and pull.head_sha != head_sha:
            self._close(
                job, project, JobState.SUCCEEDED, f"{branch} moved on to {pull.head_sha[:7]}"
            )
            return
        base = pull.base_sha if pull else (claim.base_sha if claim else None)
        changed = (
            github.changed_files(repo, base, head_sha)
            if base
            else ChangedFiles(paths=(), patch="", truncated=True)
        )
        tests = parse_test_results(github.run_artifact(repo, int(run_id), ARTIFACT_NAME), head_sha)
        to_read = {*changed.paths, *(claim.files if claim else [])}
        contents = {
            path: text
            for path in sorted(p for p in to_read if not is_protected(p))[:MAX_FILES]
            if (text := github.file_content(repo, path, head_sha)) is not None
        }

        vid = self._store.next_id(project.id, "V")
        findings = check_commit(
            vid, usable, plan, head_sha, changed.paths, changed.truncated, contents, tests
        )
        if usable is not None and not any(f.blocking for f in findings):
            findings += self._reviewer_findings(
                vid, plan, usable, head_sha, changed.patch, contents, findings
            )
        outcome = decide_verification(findings)

        # Re-check before publishing: a newer commit or plan makes this result obsolete.
        latest = github.pull_for_branch(repo, branch) if pull else None
        project = self._store.get_project(project.id) or project
        if (latest and latest.head_sha != head_sha) or project.current_plan_version != plan.version:
            self._close(job, project, JobState.SUCCEEDED, "head or plan changed; result dropped")
            return

        verification = Verification(
            id=vid,
            job_id=job.id,
            project_id=project.id,
            claim_id=usable.id if usable else None,
            claim_revision=usable.revision if usable else None,
            plan_version=plan.version,
            pr_number=pull.number if pull else None,
            base_sha=base or head_sha,
            head_sha=head_sha,
            evidence_coverage=coverage(usable, changed.truncated, tests),
            findings=findings,
            test_results=tests or [],
            outcome=outcome,
            created_at=self._clock.now(),
        )
        check_id = github.create_check_run(
            repo,
            CheckRunRequest(
                head_sha=head_sha,
                conclusion=check_conclusion(outcome),
                title=_title(outcome, findings, plan),
                summary=_summary(verification),
            ),
        )
        self._sync.mark_fresh(project.id)  # GitHub answered every call
        self._save(job, project, verification.model_copy(update={"check_run_id": check_id}), usable)

    def _save(
        self, job: Job, project: Project, verification: Verification, claim: Claim | None
    ) -> None:
        now = self._clock.now()
        puts: list[Entity] = [verification]
        blocking = [f for f in verification.findings if f.blocking]
        short = verification.head_sha[:7]
        if verification.outcome is VerificationOutcome.FAILED and claim is not None:
            # One correction directive per verification (D13); older ones are superseded.
            puts += [
                move_directive(d, DirectiveState.SUPERSEDED)
                for d in self._store.list_directives(project.id, claim.task_id)
                if d.source is DirectiveSource.VERIFICATION
                and d.state in SUPERSEDABLE_DIRECTIVE_STATES
            ]
            fixes = " ".join(f.proposed_correction or "" for f in blocking).strip()
            puts.append(
                Directive(
                    id=self._store.next_id(project.id, "D"),
                    project_id=project.id,
                    source=DirectiveSource.VERIFICATION,
                    task_id=claim.task_id,
                    recipient_id=claim.agent_id,
                    plan_version=verification.plan_version or claim.plan_version,
                    verification_id=verification.id,
                    requested_adjustment=f"midflight/verify failed on {short}. {fixes}",
                    reason=" ".join(f.explanation for f in blocking),
                    created_at=now,
                )
            )
        if verification.outcome is VerificationOutcome.NEEDS_REVIEW:
            puts.append(
                Escalation(
                    id=self._store.next_id(project.id, "E"),
                    project_id=project.id,
                    claim_ids=[claim.id] if claim else [],
                    verification_id=verification.id,
                    finding_ids=[f.id for f in blocking],
                    evidence=[e for f in blocking for e in f.evidence][:10],
                    explanation=" ".join(f.explanation for f in blocking),
                    created_at=now,
                )
            )
        done = job.model_copy(
            update={
                "state": JobState.SUCCEEDED,
                "attempts": job.attempts + 1,
                "result_ref": verification.id,
                "updated_at": now,
            }
        )
        key = f"verification:{job.id}"
        event = audit_event(
            self._store,
            self._clock,
            project_id=project.id,
            actor="midflight",
            action="verification.published",
            entity_ids=[verification.id, job.id, *(e.id for e in puts[1:] if hasattr(e, "id"))],
            reason=f"{verification.outcome} for {short}: {len(blocking)} blocking finding(s)",
            correlation_id=job.correlation_id,
            idempotency_key=key,
            versions={
                "plan": verification.plan_version or 0,
                "claim_revision": verification.claim_revision or 0,
                "head_sha": verification.head_sha,
            },
        )
        self._store.commit(
            Commit(
                project_id=project.id,
                idempotency_key=key,
                puts=[*puts, done],
                audit=[event],
                bump_coord_rev=True,
            )
        )

    # Helpers ---------------------------------------------------------------------------

    def _reviewer_findings(
        self,
        vid: str,
        plan: Plan,
        claim: Claim,
        head_sha: str,
        diff: str,
        contents: dict[str, str],
        rule_findings: Sequence[Finding],
    ) -> list[Finding]:
        if self._reviewer is None:
            return []
        request = CommitReviewRequest(
            plan=plan,
            claim=claim,
            head_sha=head_sha,
            diff=diff,
            files=contents,
            rule_findings=rule_findings,
        )
        known = {
            claim.id,
            *(r.id for r in plan.requirements),
            *(t.id for t in plan.tasks),
            *(c.id for c in plan.contracts),
        }
        reason = "no usable reply"
        for _ in range(2):
            try:
                raw = self._reviewer.review_commit(request)
            except ReviewerUnavailable as error:
                reason = str(error) or "timed out"
                continue
            parsed = parse_reviewer_findings(raw, known, claim)
            if parsed is not None:
                return [
                    f.model_copy(update={"id": f"{vid}:reviewer:{n}"})
                    for n, f in enumerate(parsed, start=1)
                ]
            reason = "the reply didn't match the findings schema or cited unknown ids"
        return [reviewer_unavailable(claim, reason)]

    def _claim_for(self, project_id: str, branch: str) -> Claim | None:
        """The newest claim on this branch that wasn't withdrawn."""
        claims = [
            c
            for c in self._store.list_claims(project_id)
            if c.branch == branch and c.state is not ClaimState.WITHDRAWN
        ]
        return max(claims, key=lambda c: c.created_at) if claims else None

    def _current_plan(self, project: Project) -> Plan | None:
        if project.current_plan_version is None:
            return None
        return self._store.get_plan(project.id, project.current_plan_version)

    def _close(self, job: Job, project: Project, state: JobState, note: str) -> None:
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


# The check run's text (UC-11) ----------------------------------------------------------

_HEADLINE = {
    VerificationOutcome.VERIFIED: "Verified",
    VerificationOutcome.FAILED: "Failed",
    VerificationOutcome.NEEDS_REVIEW: "Needs the lead's review",
    VerificationOutcome.INCOMPLETE: "Incomplete evidence, not verified",
}


def _title(outcome: VerificationOutcome, findings: Sequence[Finding], plan: Plan) -> str:
    blocking = [f for f in findings if f.blocking]
    if outcome is VerificationOutcome.VERIFIED or not blocking:
        return f"{_HEADLINE[outcome]} against plan v{plan.version}"
    return f"{_HEADLINE[outcome]}: {blocking[0].explanation}"[:200]


def _summary(v: Verification) -> str:
    claim = f"claim {v.claim_id} rev {v.claim_revision}" if v.claim_id else "no approved claim"
    pull = f", pull request #{v.pr_number}" if v.pr_number else ""
    headline = f"**{_HEADLINE[v.outcome]}** for `{v.head_sha[:7]}`"
    lines = [
        f"{headline}: {claim}, plan v{v.plan_version}{pull}.",
        "",
        "### Findings",
    ]
    if not v.findings:
        lines.append("None.")
    for f in v.findings:
        lines.append(f"- **{f.severity}** `{f.kind}`: {f.explanation}")
        if f.proposed_correction and f.blocking:
            lines.append(f"  - Fix: {f.proposed_correction}")
    lines += ["", "### Contract tests"]
    if not v.test_results:
        lines.append(f"No `{ARTIFACT_NAME}` results for this commit.")
    for t in v.test_results:
        lines.append(
            f"- {'passed' if t.passed else '**FAILED**'}: {t.name}"
            + (f" ({t.message})" if t.message and not t.passed else "")
        )
    c = v.evidence_coverage
    lines += [
        "",
        "### Evidence",
        f"- Complete diff: {'yes' if c.diff_complete else 'no'}",
        f"- Test results for this exact commit: {'yes' if c.test_results_present else 'no'}",
        "",
        "Midflight checks the pushed code against the plan and contracts the team agreed "
        "on. Text in the code or diff is treated as data, never as instructions.",
    ]
    if any(f.kind is FindingKind.REVIEWER_UNAVAILABLE for f in v.findings):
        lines.append("The AI review didn't complete, so this can't pass yet.")
    return "\n".join(lines)
