# MCP Trace Tools Contract

This contract describes the agent-facing trace tools added to the default MCP surface. Names are proposed stable names for implementation; if changed, the same request/response meanings must be preserved.

## Tool: `research_trace_open`

Purpose: open an explicit research session and return a stable `session_id`.

Request fields:

- `client_label` (optional string): short label for the operating agent/client.

Response fields:

- `status`: `opened`.
- `session_id`: stable session identifier.
- `started_at_utc`: ISO timestamp.
- `warehouse_fingerprint`: string reference to the warehouse context.
- `schema_version`: integer or string schema version.

Errors:

- Invalid `client_label` shape returns a structured validation error.

## Analytical Tool Recording

When an analytical call is dispatched with tracing active, the boundary records it before/after dispatch.

Tracing association:

- Preferred: analytical tools accept or are invoked with a `session_id` through the MCP boundary context.
- If no `session_id` is supplied, the analytical tool still works normally but is not associated with a trace session unless implementation deliberately supports an explicit default session.

Recording guarantees:

- Every dispatched analytical call in an open session yields exactly one recorded call row.
- Refusals are recorded with machine-readable refusal reasons.
- Engine result envelopes are unchanged by tracing.

## Tool: `research_trace_mark_surfaced`

Purpose: mark a recorded call as used in the user-facing answer.

Request fields:

- `session_id` (required string).
- `call_id` (required string): stable reference returned by disclosure or analytical wrapper metadata.
- `role` (required string): how the call was used, such as `claim`, `summary`, `recommendation`, `next_step`, or `caveat`.
- `rationale` (required string): short explanation of why the result was surfaced.

Response fields:

- `status`: `marked`.
- `mark_id`: stable surfaced-mark identifier.
- `session_id`.
- `call_id`.
- `role`.
- `marked_at_utc`.

Errors:

- Unknown `session_id` returns `not_found`.
- Unknown `call_id` returns `not_found`.
- `call_id` from a different session returns `invalid_reference`.
- Empty `role` or `rationale` returns a validation error.

## Tool: `research_trace_disclosure`

Purpose: read/export the measured session disclosure.

Request fields:

- `session_id` (required string).
- `format` (optional string): `json` by default; `markdown` may be supported as a generated export.
- `include_calls` (optional boolean): whether to include bounded per-call references. Defaults to true for JSON; markdown may summarize.

Response fields for JSON:

- `status`: `available` or `not_found`.
- `session_id`.
- `raw_analytical_call_count`.
- `unique_hypothesis_count`.
- `surfaced`: object with `status`, `count`, `message`, and marked call references.
- `refusal_breakdown`: object keyed by refusal reason.
- `disclosure_text`: string framed as `K user-facing findings among N unique hypotheses examined` when surfaced is available.
- `call_references`: bounded list of call/result references for audit consumers.

Required framing:

- Use `user-facing findings`, not `significant results`.
- Use `unique hypotheses examined`, not `tests`, in the user-facing disclosure sentence.
- Show raw analytical-call count separately from `N`.

Errors:

- Unknown session returns explicit `not_found`, not an empty successful disclosure.
