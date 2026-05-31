---
work_package_id: WP02
title: Trace Service And Disclosure
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- FR-014
- FR-015
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
- T012
history:
- timestamp: '2026-05-31T10:54:25Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/trace.py
execution_mode: code_change
owned_files:
- src/premura/trace.py
- tests/test_trace_store.py
tags: []
---

# Work Package Prompt: WP02 – Trace Service And Disclosure

## Implement Command

```bash
spec-kitty agent action implement WP02 --agent <name> --mission session-research-trace-01KSYT4A
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Build the pure Python trace service over the `trace.*` schema. This service opens explicit sessions, records analytical calls/results, marks surfaced calls, computes disclosure counts, and generates JSON/Markdown exports. It must be independent from MCP so it can be tested directly.

## Dependencies

Depends on WP01 because the trace service writes to the `trace.*` schema.

## Authoritative Inputs

- `kitty-specs/session-research-trace-01KSYT4A/spec.md`
- `kitty-specs/session-research-trace-01KSYT4A/data-model.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`
- `docs/adr/0009-session-research-trace-and-multiplicity-disclosure.md`

## Owned Files

- `src/premura/trace.py`
- `tests/test_trace_store.py`

Do not edit `src/premura/mcp/entrypoint.py`, migration files, live docs, or analytical engine code in this WP.

## Subtasks

### T006: Add `premura.trace` public dataclasses/result shapes for sessions, calls, marks, and disclosures

Create `src/premura/trace.py` with typed public result shapes.

Suggested shapes:

- `TraceSession` or serialized dict equivalent.
- `RecordedCall`.
- `SurfacedMark`.
- `TraceDisclosure`.
- Small status/result helper shapes for `opened`, `marked`, `available`, `not_found`, and validation failures.

Keep the public API narrow and boring. The service should expose functions usable by MCP wrappers without making MCP a dependency.

### T007: Implement explicit session opening with warehouse fingerprint/schema-version capture

Add a public function such as `open_research_session(...)`.

Inputs:

- `warehouse_path` or connection context matching project conventions.
- Optional `client_label`.

Outputs:

- `status="opened"`.
- `session_id`.
- `started_at_utc`.
- `warehouse_fingerprint`.
- `schema_version`.

Use existing project patterns for DuckDB access and generated ids. Keep all data local. The warehouse fingerprint can be pragmatic but stable enough for reproduction context; do not overbuild cryptographic inventory of the full warehouse unless existing helpers already make that cheap.

### T008: Implement deterministic request/result hashing and normalized hypothesis identity declarations

Add a deterministic normalization path for analytical requests.

Rules:

- Equivalent requests with reordered JSON/dict fields should hash the same.
- Defaults should be normalized where the wrapper/service knows the default.
- Exact retries in the same session should share `hypothesis_identity`.
- Different metrics, lags, windows, directions, or analysis parameters should produce distinct identities.

Initial tool identity declarations:

- `change_point`: metric id plus `min_side_observations` after default handling.
- `smoothed_average`: metric id, `window`, and `min_coverage` after default handling.
- `correlate`: left metric, right metric, lag, expected direction, lag justification/declaration shape, and common-cause declaration shape where it affects the hypothesis.

Preserve the doctrine rule: adding a future tool should mean declaring its identity, not editing a counting switch throughout the disclosure code.

### T009: Implement call/result recording APIs with refusal and error terminal states

Add public functions for recording analytical calls around dispatch.

The API can be a pair of calls (`start_recorded_call` / `finish_recorded_call`) or a context-style helper if that stays simple. Requirements:

- One recorded call row per dispatched analytical call in an open session.
- Available results get a stable result reference/hash.
- Refusals get a machine-readable refusal reason.
- Exceptions/errors get a terminal status that keeps disclosure internally consistent.
- Unknown sessions return explicit not-found/validation errors.

Do not compute statistics here. Do not inspect raw `hp.*` health facts.

### T010: Implement surfaced-mark APIs with same-session validation

Add a function such as `mark_surfaced(session_id, call_id, role, rationale, ...)`.

Validation:

- Unknown session -> `not_found`.
- Unknown call -> `not_found`.
- Call belongs to a different session -> `invalid_reference`.
- Empty role/rationale -> validation error.

Semantics:

- Surfaced means selected for presentation in the user-facing answer.
- It never means statistically significant.
- The service should not infer marks from effect size or status.

### T011: Implement disclosure computation and generated JSON/Markdown export shapes

Add a function such as `get_research_disclosure(session_id, format="json", include_calls=True, ...)`.

The disclosure must include:

- Raw analytical call count.
- Unique hypothesis count `N`.
- Surfaced count `K` when marks exist.
- Surfaced `unavailable` with explicit message when analytical calls exist but no marks exist.
- Refusal breakdown by reason.
- Stable call/result references for audit consumers.
- Disclosure text using `user-facing findings among unique hypotheses examined`.

Bound the query/read shape for large sessions. Do not return an unbounded dump by default.

### T012: Add trace-service tests for deduplication, refusals, surfaced fallback, consistency, and 500-call performance

Add `tests/test_trace_store.py` tests that drive the trace service directly.

Test cases:

- Open session returns stable required fields.
- Exact retry: raw count increases, `N` does not.
- Distinct identities: `N` increases.
- Refused call counts toward raw and `N`, appears in refusal breakdown.
- No surfaced marks: surfaced status unavailable with message.
- Surfaced marks: `K` equals mark count and includes roles/rationales.
- Unknown session disclosure returns `not_found`.
- Consistency invariant: raw >= N >= K when K is available.
- A 500-call session disclosure returns under the specified bound. Keep this as a sanity performance test, not a brittle benchmark.

## Test Strategy

Run focused tests:

```bash
uv run pytest tests/test_trace_store.py -q
```

Then run with migration tests:

```bash
uv run pytest tests/test_trace_migration.py tests/test_trace_store.py -q
```

## Definition Of Done

- `src/premura/trace.py` exposes a small, typed trace service API.
- Sessions, calls, results, marks, and disclosures work through public service functions.
- `N`, raw count, refusal breakdown, `K`, and surfaced unavailable behavior match the spec.
- Tests prove deterministic identity and disclosure invariants.
- No MCP or engine files are modified in this WP.

## Reviewer Guidance

Review for semantic honesty. The biggest risks are counting retries incorrectly, inferring surfaced status, storing too much health data in trace payloads, or coupling the trace service to engine internals.
