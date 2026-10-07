# Open design decisions

The [proposed system architecture](../systemarchitecture.md) expands the project
brief into an AWS service layout, with a technology guide and workflow diagrams.
The [draft requirements](../PROJECT_REQUIREMENTS.md) describe the intended MVP;
the [extended reading guide](architecture-reading-guide.md) explains the tradeoffs.
These documents are proposals for team review. The first local prototype uses
Python and in-memory state; the cloud design and model reasoning are unimplemented.

## Confirmed: lightweight claims

Start with broad claims and ask targeted questions when tasks may interact.
Exact changes are not mandatory upfront; claims can be refined during work.
The local prototype compares exact declared files and shared interface names.
Overlap requests clarification; missing information remains unknown. It does
not determine semantic incompatibility or approve tasks.

## Open: evaluating semantic compatibility

How should Midflight determine that two claims are incompatible, and which
decisions require the model versus deterministic checks or a human?

Consider the distinction between editing the same file and changing an interface
in incompatible ways. Separate evidence gathering from permission to proceed.

## Subsequent decisions

- Whether incomplete claims remain drafts until their dependencies and acceptance
  criteria are sufficient for approval; the current prototype accepts broad claims.
- One canonical demo change: adding currency or a subtotal/tax breakdown. The
  requirements and workflow diagrams currently illustrate different changes.
- The two coding-agent hosts, AWS account/region, model access, and whether the
  submission requires AgentCore Runtime or a publicly hosted dashboard.
- Shared plan format, revisioning, and ownership.
- Claim lifecycle and atomic handling of simultaneous claims.
- GitHub authentication, webhook verification, event deduplication, and permissions.
- Evidence needed to verify an interface contract from an actual diff.
- Stale-state scope and the conditions for safely resuming suggestions.
- Suggestion delivery to each teammate's agent without treating it as a command.
- Bounded model tools, audit records, and human escalation.
- Runtime language, local demo harness, and AWS deployment approach.

Resolve these through small, reviewable design and implementation steps.
