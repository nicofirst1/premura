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
- `client_label`: the supplied label (or null when none was given).

Errors:

- Invalid `client_label` shape returns a structured validation error.

## Analytical Tool Recording

When an analytical call is dispatched with tracing active, the boundary records it before/after dispatch.

Tracing association (as implemented):

- Each analytical tool (`change_point`, `smoothed_average`, `correlate`) takes an optional `session_id` parameter. Pass the `session_id` returned by `research_trace_open` to record the call in that research session's trace.
- If no `session_id` is supplied, the analytical tool behaves exactly as before, writes no trace row, and returns a byte-identical engine envelope (no `trace` key is added).

Recording guarantees:

- Every dispatched analytical call in an open session yields exactly one recorded call row.
- Refusals are recorded with machine-readable refusal reasons.
- Engine result envelopes are unchanged by tracing (NFR-001).

Wrapper-layer `trace` metadata:

- When a `session_id` is supplied, the response carries a top-level `trace` object **beside** the unchanged engine envelope — the engine envelope itself is never mutated. On success `trace` holds `session_id`, `call_id`, `terminal_status`, and (for an available call) `result_id`; if recording could not start (e.g. an unknown session) the analytical answer is still returned with a structured `trace` error (`status`/`message`/`field`).

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
- `rationale`.
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
- `schema_version`: audit-consumer contract version string.
- `session_id`.
- `started_at_utc`: ISO timestamp the session opened at.
- `warehouse_fingerprint`: warehouse context reference the disclosure was computed against.
- `raw_analytical_call_count`: count of all recorded raw analytical calls in the session.
- `unique_hypothesis_count`: `N`, the count of unique hypotheses examined.
- `surfaced`: object with `status`, `count`, `message`, and `marks` (the marked call references). When no marks exist, `status` is `surfaced unavailable` (`unavailable`), `count` is null, and `message` explains the absence — never a guessed `0`.
- `refusal_breakdown`: object keyed by refusal reason.
- `disclosure_text`: string framed as `K user-facing findings among N unique hypotheses examined` when surfaced is available.
- `calls`: bounded list of call/result references for audit consumers (omitted when `include_calls` is false).
- `calls_truncated`: boolean flag set when the bounded call list was capped.

When `format="markdown"`, a generated `disclosure_markdown` export string is added beside the structured counts. The Markdown export is generated on demand from the structured disclosure and is never the canonical record.

Required framing:

- Use `user-facing findings`, not `significant results`.
- Use `unique hypotheses examined`, not `tests`, in the user-facing disclosure sentence.
- Show raw analytical-call count separately from `N`.

Errors:

- Unknown session returns explicit `not_found`, not an empty successful disclosure.
