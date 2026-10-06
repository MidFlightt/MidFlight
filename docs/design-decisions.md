# Open design decisions

The project brief proposes Strands, Bedrock AgentCore, DynamoDB, and Lambda.
The first local prototype uses Python and in-memory state. AWS architecture
and model reasoning remain undecided.

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

- Shared plan format, revisioning, and ownership.
- Claim lifecycle and atomic handling of simultaneous claims.
- GitHub authentication, webhook verification, event deduplication, and permissions.
- Evidence needed to verify an interface contract from an actual diff.
- Stale-state scope and the conditions for safely resuming suggestions.
- Suggestion delivery to each teammate's agent without treating it as a command.
- Bounded model tools, audit records, and human escalation.
- Runtime language, local demo harness, and AWS deployment approach.

Resolve these through small, reviewable design and implementation steps.
