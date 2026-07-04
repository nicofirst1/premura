# Design note (SUPERSEDED): orchestrated operating-agent roles

> Status: **superseded 2026-06-12 — kept for history, not authoritative.**
> This pre-spec draft was promoted to the authoritative specification at
> [`docs/building/architecture/OPERATING_ROLES.md`](../architecture/OPERATING_ROLES.md)
> in a maintainer design-interview that locked five decisions (decision note
> [0013](../adr/0013-operating-roles-promotion-decisions.md), on the concept
> locked by [0010](../adr/0010-runtime-orchestrator-and-operating-roles.md)).
> **Read the spec, not this note**, for the current design (roles, the
> answer-audit gate, the improvement queue, share packets, traceability).
>
> The one exception: `OPERATING_ROLES.md` explicitly inherits the "Settled
> vocabulary" list below **verbatim, without restating it** — so that section
> stays live here as the definitions' only home. Everything else in this note
> (runtime shape, reference-role detail, answer-audit mechanics, queue/sharing
> mechanics, traceability) has since been restated and superseded in the spec.

## Settled vocabulary

- **Bootstrap agent**: setup-time agent for a freshly cloned repo. It reads docs,
  checks or installs dependencies and skills, and tells the user if a session reload
  is needed. It is separate from this plan.
- **Orchestrator**: runtime dispatcher for a human's health-data goal.
- **Operating role**: bounded runtime responsibility dispatched by the
  orchestrator.
- **Improvement candidate**: a concrete gap found during operation that may turn
  into an issue or dev-time workflow.
- **Improvement queue**: private global JSON queue for one user, storing
  sanitized improvement candidates across sessions.
- **Share packet**: the exact public issue/PR content shown to the human before
  posting.
- **Lifestyle context**: user-declared habits or circumstances that may matter
  later, but are not baseline profile context and need their own future capture
  design.

Avoid `operator` in this design. The repo already has an operator MCP surface
for lower-guarantee raw SQL, and `CONTEXT.md` uses human/operator language for
the person whose facts are being captured.
