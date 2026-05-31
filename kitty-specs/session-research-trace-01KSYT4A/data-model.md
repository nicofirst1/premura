# Data Model: Session Research Trace and Multiplicity Disclosure

## Storage Boundary

Trace data persists in the existing local DuckDB warehouse under a dedicated `trace.*` schema. No trace table belongs to `hp.*`; no trace write stores a health fact. The schema is append-only in normal operation.

## Entity: Research Session

Represents one explicit analytical investigation session opened at the MCP boundary.

Fields:

- `session_id`: stable generated identifier, primary key.
- `started_at_utc`: timestamp recorded by the boundary.
- `client_label`: optional caller-provided label for the operating agent/client.
- `warehouse_fingerprint`: stable reference to the warehouse state/context used for reproduction.
- `schema_version`: warehouse user version or trace schema version.
- `created_by`: optional boundary/client identifier if available.

Validation rules:

- `session_id` is non-empty and unique.
- `started_at_utc` is present.
- Unknown sessions return explicit not-found outcomes.

## Entity: Recorded Analytical Call

Represents one analytical invocation observed by the MCP boundary.

Fields:

- `call_id`: stable generated identifier, primary key.
- `session_id`: foreign key to `trace.session`.
- `tool_name`: analytical tool name, e.g. `change_point`, `smoothed_average`, `correlate`.
- `request_hash`: deterministic hash of the normalized request reference.
- `hypothesis_identity`: deterministic normalized identity used for deduplication and `N`.
- `started_at_utc`: timestamp before dispatch.
- `finished_at_utc`: timestamp after dispatch or exception.
- `terminal_status`: `available`, `refused`, or `error`.
- `refusal_reason`: machine-readable reason for refused calls, nullable otherwise.
- `error_kind`: machine-readable exception/error class for dispatch failures, nullable otherwise.

Validation rules:

- Exactly one recorded call row exists per dispatched analytical call in an open session.
- Exact retries share `hypothesis_identity` but have distinct `call_id` and usually distinct timestamps.
- Pre-question validation failures that never become analytical requests are not recorded as analytical calls.

## Entity: Recorded Result Reference

Represents the stable reference to a non-refusal analytical result.

Fields:

- `result_id`: stable generated identifier, primary key.
- `call_id`: foreign key to `trace.tool_call`.
- `result_hash`: deterministic hash of the serialized result envelope.
- `result_summary`: compact machine-readable envelope subset when safe and useful.
- `created_at_utc`: timestamp after dispatch.

Validation rules:

- Non-refusal calls should have one result reference.
- Refused calls do not need a result reference but must carry `refusal_reason` on the call row.
- Result references must avoid storing raw health fact dumps.

## Entity: Surfaced Mark

Represents the agent's explicit declaration that a recorded call was used in the user-facing answer.

Fields:

- `mark_id`: stable generated identifier, primary key.
- `session_id`: foreign key to `trace.session`.
- `call_id`: foreign key to `trace.tool_call`.
- `role`: short closed or validated label for how the result was used, e.g. `claim`, `summary`, `recommendation`, `next_step`, `caveat`.
- `rationale`: short free-text explanation from the agent.
- `marked_at_utc`: timestamp recorded by the boundary.

Validation rules:

- `call_id` must belong to the same `session_id`.
- A call may be marked surfaced at most once per role unless the implementation deliberately allows multiple rationales and reports them deterministically.
- Surfaced means selected for presentation, never statistically significant.

## Entity: Disclosure

Derived view over one research session.

Fields:

- `session_id`.
- `raw_analytical_call_count`.
- `unique_hypothesis_count`: `N`.
- `surfaced_count`: `K`, nullable when unavailable.
- `surfaced_status`: `available` or `unavailable`.
- `surfaced_message`: explicit message when marks are absent.
- `refusal_breakdown`: counts by refusal reason.
- `call_references`: stable call/result references for audit consumers.

Validation rules:

- `raw_analytical_call_count >= unique_hypothesis_count`.
- If `surfaced_status == available`, `unique_hypothesis_count >= surfaced_count`.
- If a session has analytical calls and no surfaced marks, `surfaced_status == unavailable` and `surfaced_count` is null.
- Disclosure text uses `user-facing findings` and `unique hypotheses examined`, never `significant results` or `tests`.

## Normalized Hypothesis Identity

Each analytical tool declares the fields that define a unique examined hypothesis.

Initial identities:

- `change_point`: metric id and analysis parameters such as `min_side_observations` after defaults are normalized.
- `smoothed_average`: metric id, window, and `min_coverage` after defaults are normalized.
- `correlate`: left metric id, right metric id, lag, expected direction, lag justification presence/normalized declared params, and common-cause declaration shape where relevant to the hypothesis.
- Future `paired_t_test`: outcome metric, grouping/event definition, windows, contrast/direction, and analysis parameters.

The implementation should expose this as a declaration per tool, not as a hardcoded disclosure switch.

## State Transitions

Research session:

```text
opened -> records calls/marks -> disclosure requested
```

Recorded analytical call:

```text
started -> available
started -> refused
started -> error
```

Normal operation does not update or delete completed records; terminal data may be written as part of the before/after recording transaction if the implementation stores an initial attempt then finalizes it.
