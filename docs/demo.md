# Hackathon demo

Use a synthetic repository with two coding agents and a human integration lead.
Demonstrate a coherent Claim → Check → Propagate → Verify workflow.

## Acceptance scenarios

| Scenario | Expected evidence |
| --- | --- |
| Two compatible claims | Both can proceed; decisions cite the plan and relevant claims. |
| Incompatible interface changes | Objection is raised before coding; human resolution is requested. |
| Requirement changes while work is active | Only affected tasks receive scoped suggestions; each has a logged reason. |
| Agent says done but diff breaks its contract | Actual diff overrides the completion statement; GitHub alignment status blocks. |
| Diff matches the agreed contract | GitHub alignment status passes with an explanation tied to that commit. |
| GitHub rate limit or API error | Affected state is visibly stale; no directives are emitted until refreshed. |
| Repository content includes malicious instructions | Content remains data and does not cause command execution or widen tool access. |

## Demo sequence

1. Show the shared plan and two claims.
2. Trigger an interface disagreement and show the escalation.
3. Resolve it as a human, then change a requirement and inspect suggestions.
4. Push a deliberately mismatched implementation and show the blocked status.
5. Push the corrected implementation and show the passing status.
6. Simulate a GitHub failure and show stale state suppressing suggestions.

The local claim prototype includes synthetic examples and tests for overlap,
independent declarations, refinements, and missing information. It implements
clarification questions, not the full acceptance scenarios above. Shared-plan
checks, model reasoning, GitHub integration, and AWS runtime remain unimplemented.
A convincing demo must distinguish simulated failures from live API behavior
and must not equate file overlap with semantic incompatibility.
