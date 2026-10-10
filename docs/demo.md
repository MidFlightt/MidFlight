# Hackathon demo

> Frederik rewrites the demo sequence below in task F-1, starting from the
> [storyboard draft](development-plan.md#demo-storyboard). The full scenario list
> with expected results is [requirements §11](requirements.md#11-required-demonstration-and-evaluation),
> traced to use cases in [use-cases.md](use-cases.md#demo-traceability).
> An animated version can be generated with the Remotion prompt in
> [video-prompt.md](video-prompt.md).

Use the synthetic checkout project (`midflight-demo-shop`), two Claude Code sessions
(T1 backend, T2 frontend), and a human integration lead. Demonstrate a coherent
Claim → Check → Propagate → Verify workflow.

## Acceptance scenarios

The headline scenarios. Requirements §11 has the full list.

| Scenario | Expected evidence |
| --- | --- |
| Two compatible claims | Both approved; the verdict cites the plan and the contract. |
| T2 expects `total`, the contract has `total_cents` | `needs_revision` before coding, with the correction in the same call. The agent revises and is approved. |
| T2 wants a tax-inclusive total, T1 returns tax-exclusive | A conflict between people's requirements. Escalated to the lead, who resolves it; the audit trail records why. |
| Lead adds `currency` while work is active | Only T1 and T2 get directives, each with a logged reason. T3 gets nothing. |
| Agent says done but the diff breaks its contract | The diff overrides the completion message; `midflight/verify` fails and blocks merge. |
| Diff matches the agreed contract | `midflight/verify` passes, tied to that commit and plan version. |
| GitHub rate limit or API error (labeled `SIMULATED`) | State is visibly stale; no directives or passes until data is fresh. |
| Repository content includes instructions aimed at the AI | Treated as data; nothing runs and no permission changes. |

## Demo sequence

1. Show plan v1 and the two claims.
2. T2 claims `total`; Midflight answers `needs_revision` with the `total_cents`
   correction in the same call; the agent revises and is approved.
3. The lead approves plan v2 (`currency`); the directive reaches T1 and T2 at their
   next step, T3 stays quiet, and the pre-push hook blocks until it is acknowledged.
4. T1's agent says "done" but pushes the wrong field; `midflight/verify` fails with
   evidence.
5. Push the fix; the check passes and the timeline explains every step.
6. Quick cuts: an escalation resolved by the lead, the stale banner during a
   simulated rate limit, injected instructions ignored.

The local claim prototype (`midflight/claims.py`) only compares declared files and
interface names. Shared-plan checks, model reasoning, GitHub integration, and AWS
runtime are not implemented yet. A convincing demo must distinguish simulated
failures from live API behavior and must not equate file overlap with semantic
incompatibility.
