"""Write docs/pages/scenarios.html: every scenario step, traced through the review.

    uv run python tests/scenario_report.py

It replays tests/scenarios/*.yaml with recording switched on and shows, per step, what
the agent sent, what the rules found, what the AI reviewer was asked and answered,
how the verdict was decided and saved (including rejected stale saves), what went
back to the agent, and the audit trail. Everything runs locally with fakes.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from scenario_runner import Play, Scenario, Step, all_scenarios, load  # noqa: E402

from midflight.domain.models import (  # noqa: E402
    AuditEvent,
    Claim,
    ClaimState,
    Finding,
    FindingKind,
    FindingSource,
    Job,
)
from midflight.ports import ClaimReviewRequest, Commit, CommitResult, RevisionConflict  # noqa: E402
from midflight.services.claims import Verdict  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "pages" / "scenarios.html"


# Recording -----------------------------------------------------------------------------


@dataclass
class SaveAttempt:
    key: str
    puts: list[str]
    expected_rev: int | None
    outcome: str
    ok: bool


@dataclass
class ReviewCall:
    claim_id: str
    revision: int
    other_claims: list[str]
    rule_findings: list[str]
    reply: Any
    raised: str | None = None


@dataclass
class ClaimTrace:
    claim: Claim
    verdict: Verdict
    rule_findings: list[Finding]
    reviewer_findings: list[Finding]
    reviewer_calls: list[ReviewCall]
    saves: list[SaveAttempt]
    decided_because: str


@dataclass
class StepTrace:
    number: int
    title: str
    say: str | None
    expected: dict[str, Any]
    passed: bool
    failure: str | None
    error: str | None
    rev_before: int
    rev_after: int
    claims: list[ClaimTrace] = field(default_factory=list)
    saves: list[SaveAttempt] = field(default_factory=list)
    audit: list[AuditEvent] = field(default_factory=list)


class TracingPlay(Play):
    def __init__(self, scenario: Scenario) -> None:
        super().__init__(scenario)
        self.steps: list[StepTrace] = []
        self._saves: list[SaveAttempt] = []
        self._calls: list[ReviewCall] = []
        commit, review = self.store.commit, self.reviewer.review_claim

        def recording_commit(c: Commit) -> CommitResult:
            attempt = SaveAttempt(c.idempotency_key, [_describe(e) for e in c.puts], None, "", True)
            attempt.expected_rev = c.expected_coord_rev
            self._saves.append(attempt)
            try:
                result = commit(c)
            except RevisionConflict as conflict:
                attempt.ok = False
                attempt.outcome = (
                    f"rejected: coord_rev is {conflict.actual}, the review read "
                    f"{conflict.expected}. Another change landed first, so it reruns."
                )
                raise
            attempt.outcome = (
                "skipped: already applied (retry-safe)"
                if result.duplicate
                else f"saved, coord_rev is now {result.coord_rev}"
            )
            return result

        def recording_review(request: ClaimReviewRequest) -> Any:
            call = ReviewCall(
                request.claim.id,
                request.claim.revision,
                [f"{o.id} ({o.task_id}, {o.state})" for o in request.other_claims],
                [f.kind.value for f in request.rule_findings],
                None,
            )
            self._calls.append(call)
            try:
                call.reply = review(request)
            except Exception as error:
                call.raised = f"{type(error).__name__}: {error}"
                raise
            return call.reply

        self.store.commit = recording_commit  # type: ignore[method-assign]
        self.reviewer.review_claim = recording_review  # type: ignore[method-assign]

    def run(self) -> None:
        for number, step in enumerate(self.scenario.steps, start=1):
            self._saves, self._calls = [], []
            project = self.store.get_project("demo")
            rev_before = project.coord_rev if project else 0
            audit_before = len(self.store.list_audit("demo"))
            failure = None
            try:
                self._step(step)
            except AssertionError as error:
                failure = str(error)
            project = self.store.get_project("demo")
            trace = StepTrace(
                number=number,
                title=_title(step, self),
                say=step.say,
                expected=step.expect.model_dump(exclude_defaults=True) if step.expect else {},
                passed=failure is None,
                failure=failure,
                error=f"{type(self.last_error).__name__}: {self.last_error.detail}"
                if self.last_error
                else None,
                rev_before=rev_before,
                rev_after=project.coord_rev if project else 0,
                saves=self._saves,
                audit=self.store.list_audit("demo")[audit_before:],
            )
            trace.claims = self._claim_traces(trace)
            self.steps.append(trace)
            if failure:
                break

    def _claim_traces(self, trace: StepTrace) -> list[ClaimTrace]:
        reviewed: dict[tuple[str, int], None] = {}
        for save in self._saves:
            for put in save.puts:
                if put.startswith("Claim "):
                    claim_id, revision = put.split()[1].split("/")
                    reviewed[(claim_id, int(revision))] = None
        traces = []
        for claim_id, revision in reviewed:
            claim = self.store.get_claim(claim_id, revision)
            assert claim is not None
            reasons = [
                e.reason
                for e in trace.audit
                if e.action == "claim.reviewed" and claim_id in e.entity_ids
            ]
            traces.append(
                ClaimTrace(
                    claim=claim,
                    verdict=self.service.verdict(claim_id, revision),
                    rule_findings=[
                        f
                        for f in claim.findings
                        if f.source is FindingSource.RULE
                        and f.kind is not FindingKind.REVIEWER_UNAVAILABLE
                    ],
                    reviewer_findings=[
                        f
                        for f in claim.findings
                        if f.source is FindingSource.REVIEWER
                        or f.kind is FindingKind.REVIEWER_UNAVAILABLE
                    ],
                    reviewer_calls=[
                        c for c in self._calls if (c.claim_id, c.revision) == (claim_id, revision)
                    ],
                    saves=[
                        s
                        for s in self._saves
                        if any(p.startswith(f"Claim {claim_id}/") for p in s.puts)
                    ],
                    decided_because=reasons[-1] if reasons else "",
                )
            )
        return traces


def _describe(entity: Any) -> str:
    if isinstance(entity, Claim):
        return f"Claim {entity.id}/{entity.revision} → {entity.state}"
    if isinstance(entity, Job):
        return f"Job {entity.id} ({entity.kind}) → {entity.state}"
    name = type(entity).__name__
    return f"{name} {getattr(entity, 'id', '')}".strip()


def _title(step: Step, play: Play) -> str:
    if step.submit:
        s = step.submit
        what = f"a revision of claim “{s.revise}”" if s.revise else "a new claim"
        return f"{s.as_}'s agent submits {what}"
    if step.withdraw:
        return f"{step.withdraw.as_}'s agent withdraws “{step.withdraw.claim}”"
    if step.close:
        return f"{step.close.as_}'s agent closes “{step.close.claim}”"
    if step.race:
        return f"Two {step.race.as_} claims arrive at the same moment"
    if step.go_stale:
        return f"GitHub data goes stale: {step.go_stale}"
    return "Check claim states: " + ", ".join(f"{k} = {v}" for k, v in (step.claims or {}).items())


# Rendering -----------------------------------------------------------------------------

E = html.escape
STATE_CLASS = {
    ClaimState.APPROVED: "ok",
    ClaimState.NEEDS_REVISION: "warn",
    ClaimState.HUMAN_REVIEW_REQUIRED: "lead",
    ClaimState.PENDING: "wait",
    ClaimState.DRAFT: "muted",
    ClaimState.WITHDRAWN: "muted",
    ClaimState.CLOSED: "muted",
}


def badge(state: ClaimState) -> str:
    return f'<span class="badge {STATE_CLASS[state]}">{E(state.value)}</span>'


def uses(claim: Claim) -> str:
    rows = []
    for side, items in (("provides", claim.provides), ("consumes", claim.consumes)):
        for use in items:
            fields = ", ".join(f"{n}: {t}" for n, t in use.fields.items())
            rows.append(f"<code>{side} {E(use.contract_id)} {{{E(fields)}}}</code>")
    if claim.no_interfaces:
        rows.append("<code>no_interfaces: true</code>")
    return "<br>".join(rows) or '<span class="dim">no interfaces listed</span>'


def finding_list(findings: list[Finding], empty: str) -> str:
    if not findings:
        return f'<p class="dim">{E(empty)}</p>'
    items = []
    for f in findings:
        sev = "block" if f.blocking else "info"
        fix = (
            f'<div class="fix">Fix: {E(f.proposed_correction)}</div>'
            if f.proposed_correction
            else ""
        )
        evidence = "".join(
            f"<li><b>{E(e.kind.value)}</b> {E(e.ref)}"
            + (f" — <code>{E(e.excerpt)}</code>" if e.excerpt else "")
            + "</li>"
            for e in f.evidence
        )
        items.append(
            f'<li class="finding"><span class="sev {sev}">{sev}</span> '
            f"<b>{E(f.kind.value)}</b> <span class='dim'>({E(f.source.value)})</span>"
            f"<div>{E(f.explanation)}</div>{fix}"
            f"<details><summary>evidence and id</summary><ul>{evidence}</ul>"
            f"<code class='dim'>{E(f.id)}</code></details></li>"
        )
    return f"<ul class='findings'>{''.join(items)}</ul>"


def reviewer_stage(ct: ClaimTrace) -> str:
    if not ct.reviewer_calls:
        if not ct.claim.is_complete:
            why = "Skipped: the claim is incomplete, so there is nothing to review yet."
        elif any(f.blocking for f in ct.rule_findings):
            why = "Skipped: the rules already found a blocking problem (rules first, AI second)."
        elif ct.claim.state is ClaimState.PENDING and not ct.claim.findings:
            why = "Not reached: GitHub data is stale, so no approval is possible yet (INV-09)."
        else:
            why = "Not called in this step."
        return f'<p class="dim">{E(why)}</p>'
    parts = []
    for n, call in enumerate(ct.reviewer_calls, start=1):
        sent = (
            f"claim {E(call.claim_id)} rev {call.revision}; other active claims: "
            f"{E(', '.join(call.other_claims) or 'none')}; rule findings: "
            f"{E(', '.join(call.rule_findings) or 'none')}"
        )
        if call.raised:
            got = f"<code>{E(call.raised)}</code>"
        elif callable(call.reply):
            got = "<code>(scenario hook)</code>"
        else:
            got = f"<pre>{E(json.dumps(call.reply, indent=2, default=str))}</pre>"
        parts.append(
            f"<div class='call'><b>Call {n}</b><div>Sent: {sent}</div><div>Reply: {got}</div></div>"
        )
    used = [f for f in ct.reviewer_findings if f.source is FindingSource.REVIEWER]
    unavailable = [f for f in ct.reviewer_findings if f.kind is FindingKind.REVIEWER_UNAVAILABLE]
    if unavailable:
        verdict = (
            "<p class='alert'>Reply discarded: it didn't fit the Finding schema, wasn't from "
            "the reviewer, or cited ids that don't exist (INV-01). The claim can't be "
            "approved without a usable review.</p>"
        )
    elif used:
        verdict = "<p>Reply accepted: every finding fit the schema and cited real ids.</p>"
    else:
        verdict = "<p>Reply accepted: no findings.</p>"
    return "".join(parts) + verdict + finding_list(ct.reviewer_findings, "")


def saves_list(saves: list[SaveAttempt]) -> str:
    if not saves:
        return '<p class="dim">Nothing written.</p>'
    rows = []
    for s in saves:
        cas = f"only if coord_rev is {s.expected_rev}" if s.expected_rev is not None else "-"
        rows.append(
            f"<tr class='{'' if s.ok else 'bad'}'><td><code>{E(s.key)}</code></td>"
            f"<td>{'<br>'.join(E(p) for p in s.puts) or '-'}</td><td>{E(cas)}</td>"
            f"<td>{E(s.outcome)}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Write</th><th>Saves</th><th>Condition</th><th>Result</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def claim_card(ct: ClaimTrace) -> str:
    c, v = ct.claim, ct.verdict
    contracts = (
        "".join(
            f"<li><code>{E(k.id)} v{k.version}</code> (provider {E(k.provider_task)}): "
            + ", ".join(f"<code>{E(n)}: {E(t)}</code>" for n, t in k.fields.items())
            + "</li>"
            for k in v.contracts
        )
        or "<li class='dim'>none</li>"
    )
    assumptions = "".join(f"<li>{E(a)}</li>" for a in c.assumptions) or "<li class='dim'>none</li>"
    basis = ct.decided_because.partition(": ")[2] or "no review in this step"
    return f"""
<div class="claim">
  <div class="claim-head"><b>Claim {E(c.id)}</b> rev {c.revision} · task {E(c.task_id)} ·
    plan v{c.plan_version} · {badge(c.state)}</div>
  <ol class="pipeline">
    <li><h4>1 · What the agent sent</h4>
      <div class="kv"><span>Interfaces</span><div>{uses(c)}</div>
      <span>Files</span><div>{E(", ".join(c.files)) or "-"}</div>
      <span>Assumptions</span><ul>{assumptions}</ul>
      <span>Criteria</span><div>{E("; ".join(c.acceptance_criteria)) or "-"}</div>
      {f"<span>Reason</span><div>{E(c.reason)}</div>" if c.reason else ""}</div></li>
    <li><h4>2 · Rules (deterministic, <code>domain/rules.py</code>)</h4>
      {finding_list(ct.rule_findings, "No problems found by the rules.")}</li>
    <li><h4>3 · AI reviewer (scripted here, checked by <code>services/review.py</code>)</h4>
      {reviewer_stage(ct)}</li>
    <li><h4>4 · Decision (<code>domain/decide.py</code>)</h4>
      <p>{badge(c.state)} from {E(basis)}</p></li>
    <li><h4>5 · Saved (race-safe, <code>Store.commit</code>)</h4>{saves_list(ct.saves)}</li>
    <li><h4>6 · Sent back to the agent (<code>verdict()</code>)</h4>
      <p>{badge(v.state)} {"" if v.review_complete else "<b>review incomplete</b>"}</p>
      <div class="kv"><span>Build against</span><ul>{contracts}</ul>
      <span>Directives</span><div>{len(v.directives) or "none"}</div>
      <span>Note</span><div class="dim">{E(v.note)}</div></div></li>
  </ol>
</div>"""


def step_card(st: StepTrace) -> str:
    expected = (
        ", ".join(f"{k}: {E(json.dumps(v, default=str))}" for k, v in st.expected.items()) or "-"
    )
    status = "ok" if st.passed else "bad"
    error = f"<p class='alert'>Refused: {E(st.error)}</p>" if st.error else ""
    failure = f"<p class='alert'>{E(st.failure)}</p>" if st.failure else ""
    claims = "".join(claim_card(c) for c in st.claims)
    other = "" if st.claims else f"<h4>Writes</h4>{saves_list(st.saves)}"
    audit = "".join(
        f"<li><code>{E(a.id)}</code> <b>{E(a.action)}</b> by {E(a.actor)} on "
        f"{E(', '.join(a.entity_ids))}: {E(a.reason)}</li>"
        for a in st.audit
    )
    return f"""
<section class="step">
  <header><span class="num">{st.number}</span><div><h3>{E(st.title)}</h3>
    {f"<p class='say'>{E(st.say)}</p>" if st.say else ""}</div>
    <span class="check {status}">{"✓ as expected" if st.passed else "✗ failed"}</span></header>
  <p class="meta">Expected: {expected} · coord_rev {st.rev_before} → {st.rev_after}</p>
  {error}{failure}{claims}{other}
  <details><summary>Audit trail for this step ({len(st.audit)})</summary>
    <ul class="audit">{audit or "<li class='dim'>none</li>"}</ul></details>
</section>"""


def render(plays: list[tuple[Path, TracingPlay]]) -> str:
    passed = sum(all(s.passed for s in p.steps) for _, p in plays)
    nav = "".join(
        f"<a href='#{path.stem}' class='{'ok' if all(s.passed for s in p.steps) else 'bad'}'>"
        f"{E(p.scenario.name)}</a>"
        for path, p in plays
    )
    body = "".join(
        f"""<article id="{path.stem}" class="scenario">
  <h2>{E(p.scenario.name)}</h2>
  <p class="meta"><code>tests/scenarios/{path.name}</code> · {E(p.scenario.requirement)} ·
    {E(", ".join(p.scenario.use_cases))} · plan v{p.scenario.plan_version} current</p>
  {"".join(step_card(s) for s in p.steps)}
</article>"""
        for path, p in plays
    )
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sha = "unknown"
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return PAGE.format(
        passed=passed, total=len(plays), sha=E(sha), when=E(when), nav=nav, body=body
    )


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Midflight Scenario Trace</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --ink:#1c1c1a; --dim:#6b6b66; --line:#e2e1dc;
  --ok:#1f7a45; --ok-bg:#e3f4ea; --warn:#9a5b00; --warn-bg:#fdf0d8; --bad:#b42318;
  --bad-bg:#fde7e4; --wait:#1f5fa8; --wait-bg:#e3eefb; --lead:#6b3fa0; --lead-bg:#efe6fa;
  --code:#f0efea; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141413; --card:#1e1e1c; --ink:#ecebe6;
  --dim:#a09f98; --line:#33332f; --ok:#6fd39a; --ok-bg:#16301f; --warn:#f0b65a;
  --warn-bg:#33270f; --bad:#ff8a7a; --bad-bg:#3a1a16; --wait:#8fbcf5; --wait-bg:#172a42;
  --lead:#c5a3f0; --lead-bg:#2a1f3a; --code:#2a2a27; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif }}
.wrap {{ max-width:1100px; margin:0 auto; padding:24px 16px 80px }}
h1 {{ font-size:1.7rem; margin:0 0 4px }} h2 {{ margin:0 0 4px; font-size:1.3rem }}
h3 {{ margin:0; font-size:1.02rem }} h4 {{ margin:0 0 6px; font-size:.9rem }}
code, pre {{ font:13px ui-monospace,Consolas,monospace; background:var(--code);
  padding:1px 5px; border-radius:4px }}
pre {{ padding:8px; overflow:auto; white-space:pre-wrap }}
.dim {{ color:var(--dim) }} .meta {{ color:var(--dim); font-size:.86rem; margin:4px 0 12px }}
.flow {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:14px 0 18px;
  font-size:.9rem }}
.flow span {{ background:var(--card); border:1px solid var(--line); border-radius:6px;
  padding:4px 9px }}
nav {{ display:flex; flex-wrap:wrap; gap:6px; margin:16px 0 24px }}
nav a {{ text-decoration:none; color:var(--ink); background:var(--card);
  border:1px solid var(--line); border-left:4px solid var(--ok); border-radius:6px;
  padding:5px 9px; font-size:.85rem }}
nav a.bad {{ border-left-color:var(--bad) }}
.scenario {{ margin:36px 0 }}
.step {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; margin:12px 0 }}
.step header {{ display:flex; gap:12px; align-items:flex-start }}
.step header div {{ flex:1 }}
.num {{ background:var(--code); border-radius:50%; min-width:28px; height:28px;
  display:grid; place-items:center; font-weight:600 }}
.say {{ margin:2px 0 0; color:var(--dim) }}
.check {{ font-size:.82rem; font-weight:600; padding:2px 8px; border-radius:999px;
  white-space:nowrap }}
.check.ok {{ color:var(--ok); background:var(--ok-bg) }}
.check.bad {{ color:var(--bad); background:var(--bad-bg) }}
.badge {{ font-size:.78rem; font-weight:600; padding:1px 8px; border-radius:999px }}
.badge.ok {{ color:var(--ok); background:var(--ok-bg) }}
.badge.warn {{ color:var(--warn); background:var(--warn-bg) }}
.badge.wait {{ color:var(--wait); background:var(--wait-bg) }}
.badge.lead {{ color:var(--lead); background:var(--lead-bg) }}
.badge.muted {{ color:var(--dim); background:var(--code) }}
.claim {{ border:1px solid var(--line); border-radius:8px; margin:10px 0; overflow:hidden }}
.claim-head {{ background:var(--code); padding:8px 12px }}
.pipeline {{ list-style:none; margin:0; padding:0 }}
.pipeline > li {{ padding:10px 12px; border-top:1px solid var(--line) }}
.kv {{ display:grid; grid-template-columns:110px 1fr; gap:4px 12px; font-size:.9rem }}
.kv > span {{ color:var(--dim) }} .kv ul {{ margin:0; padding-left:18px }}
.findings {{ list-style:none; padding:0; margin:0 }}
.finding {{ border-left:3px solid var(--line); padding:4px 10px; margin:6px 0 }}
.sev {{ font-size:.72rem; font-weight:700; text-transform:uppercase; padding:1px 6px;
  border-radius:4px }}
.sev.block {{ color:var(--bad); background:var(--bad-bg) }}
.sev.info {{ color:var(--wait); background:var(--wait-bg) }}
.fix {{ margin-top:3px; color:var(--ok) }}
.alert {{ background:var(--bad-bg); color:var(--bad); padding:8px 10px; border-radius:6px }}
.call {{ border:1px dashed var(--line); border-radius:6px; padding:6px 10px; margin:6px 0;
  font-size:.9rem }}
table {{ width:100%; border-collapse:collapse; font-size:.86rem }}
th, td {{ text-align:left; padding:5px 6px; border-bottom:1px solid var(--line);
  vertical-align:top }}
tr.bad td {{ background:var(--bad-bg) }}
details summary {{ cursor:pointer; color:var(--dim); font-size:.86rem; margin-top:8px }}
.audit {{ font-size:.86rem }}
@media (max-width:640px) {{ .kv {{ grid-template-columns:1fr }} th:nth-child(1), td:nth-child(1)
  {{ display:none }} }}
</style></head><body><div class="wrap">
<h1>Midflight scenario trace</h1>
<p class="meta">{passed} of {total} scenarios passed · commit {sha} · generated {when} ·
  all local: in-memory store, scripted AI reviewer, no AWS or GitHub</p>
<p>Each step below is one line of a scenario in <code>tests/scenarios/</code>, played
  against the real claim service (S-1 to S-4). A claim goes through the same six
  stages every time:</p>
<div class="flow"><span>1 · agent sends a claim</span>→<span>2 · rules</span>→
  <span>3 · AI reviewer (only if rules pass)</span>→<span>4 · decision</span>→
  <span>5 · save if nothing changed meanwhile</span>→<span>6 · verdict back to agent</span></div>
<p class="dim">Regenerate with <code>uv run python tests/scenario_report.py</code>.</p>
<nav>{nav}</nav>
{body}
</div></body></html>
"""


def main() -> None:
    plays = []
    for path in all_scenarios():
        play = TracingPlay(load(path))
        play.run()
        plays.append((path, play))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(plays), encoding="utf-8")
    passed = sum(all(s.passed for s in p.steps) for _, p in plays)
    print(f"{passed}/{len(plays)} scenarios passed; wrote {OUT}")


if __name__ == "__main__":
    main()
