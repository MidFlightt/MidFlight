# Claim template

Start with an owner and intended outcome. Add expected files and shared
interfaces when known; exact code changes are not required upfront. Midflight
asks for more detail when tasks may interact. Refine the claim as you learn.

The sections below are prompts, not mandatory fields. For the local prototype's
JSON input, see examples/claims.json and README.md. This human-readable template
is not a finalized API or database schema.

```markdown
## Outcome
What will this task deliver?

## Plan requirement
Which agreed requirement and revision does this implement?

## Owner and branch
Human owner, coding agent, and branch:

## Files expected to change
Paths or bounded areas:

## Interfaces and contracts
What will be added or changed? Who consumes it?
Inputs, outputs, and compatibility expectations:

## Dependencies and overlapping work
Other claims or requirements this depends on:

## Verification
What observable evidence will show the claim is fulfilled?

## Open questions
What needs a human decision before coding?
```
