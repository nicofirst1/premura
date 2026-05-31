---
work_package_id: WP01
title: Trace Schema Foundation
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-004
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- timestamp: '2026-05-31T10:54:25Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/store/migrations/
execution_mode: code_change
owned_files:
- src/premura/store/migrations/005_trace_audit.sql
- tests/test_trace_migration.py
tags: []
---

# Work Package Prompt: WP01 – Trace Schema Foundation

## Implement Command

```bash
spec-kitty agent action implement WP01 --agent <name> --mission session-research-trace-01KSYT4A
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Create the durable local warehouse home for session research traces. This WP introduces the `trace.*` schema and proves it is separate from health facts in `hp.*`. It should not implement the Python trace service or MCP tools; those are WP02/WP03.

## Authoritative Inputs

- `kitty-specs/session-research-trace-01KSYT4A/spec.md`
- `kitty-specs/session-research-trace-01KSYT4A/plan.md`
- `kitty-specs/session-research-trace-01KSYT4A/data-model.md`
- `docs/adr/0009-session-research-trace-and-multiplicity-disclosure.md`

## Owned Files

- `src/premura/store/migrations/005_trace_audit.sql`
- `tests/test_trace_migration.py`

Do not edit MCP entrypoints, `src/premura/trace.py`, live docs, or existing analytical tool implementations in this WP.

## Subtasks

### T001: Add migration `005_trace_audit.sql` with `trace.*` tables and indexes

Create a new migration file under `src/premura/store/migrations/`.

Expected tables, preserving meaning even if exact names need SQL-safe variants:

- `trace.research_session`: explicit session id, start timestamp, client label, warehouse fingerprint, schema version.
- `trace.tool_call`: one row per analytical call attempt, including session id, call id, tool name, request hash, normalized hypothesis identity, timestamps, terminal status, refusal reason, and error kind.
- `trace.tool_result`: optional non-refusal result reference, including result id, call id, result hash, and compact summary field if needed.
- `trace.surfaced_mark`: explicit agent mark that a call was used in a user-facing answer, including role and rationale.

Guidance:

- Keep everything under `trace.*`, never `hp.*`.
- Use primary keys and foreign keys where the existing migration style supports them.
- Add indexes for bounded session disclosure queries: by `session_id`, by `(session_id, hypothesis_identity)`, and by `call_id` for marks/results.
- Keep the schema compact. Do not add a report table unless tests prove it is necessary; disclosures are derived.

### T002: Add migration tests proving `trace.*` exists outside `hp.*` and is idempotent

Add tests in `tests/test_trace_migration.py` that initialize a temporary warehouse through the public store initialization path.

Assertions should cover:

- The `trace` schema exists.
- The trace tables exist after initialization.
- The expected `hp.*` tables still exist and are not replaced.
- Re-running initialization/migrations is idempotent.

Avoid testing by importing migration internals directly. Use the same public initialization path other schema regression tests use.

### T003: Add schema-ownership tests proving trace writes cannot create health facts

Within the migration test file, add a focused test that inspects schemas/tables and confirms the trace migration did not create any new `hp.*` provenance tables.

The test should make the meaning boundary explicit:

- `trace.*` contains tool-use provenance.
- `hp.*` contains health facts.
- This migration must not add trace/provenance tables to `hp.*`.

This test is a guardrail for FR-007/NFR-002 style boundary drift.

### T004: Add append-only enforcement tests for trace rows at the storage boundary

At this stage, SQL-level append-only enforcement may be minimal because the public trace service lands in WP02. Still add tests that constrain the schema toward append-only use:

- Tables have stable primary keys.
- There is no table that looks like a mutable aggregate/disclosure cache.
- Result/mark rows link to immutable call ids rather than updating a call payload blob.

If the implementation uses an initial call row that is finalized with terminal status in WP02, do not over-constrain that here. The normal-operation append-only public API is tested in WP02.

### T005: Document migration assumptions in the WP handoff and keep schema compact

When finishing this WP, note any deliberate schema choices for downstream implementers:

- Exact table names if they differ from the planning nouns.
- Whether `hypothesis_identity` is stored as text JSON, canonical JSON, or hash plus payload.
- Whether compact result summaries are allowed in `trace.tool_result` or only hashes.

Do not edit docs in this WP. Put handoff notes in the WP completion summary.

## Test Strategy

Run the focused tests first:

```bash
uv run pytest tests/test_trace_migration.py -q
```

Then run the broader schema tests if touched behavior suggests it:

```bash
uv run pytest tests/test_schema_regression.py tests/test_store.py tests/test_trace_migration.py -q
```

## Definition Of Done

- `005_trace_audit.sql` exists and is idempotent through normal warehouse initialization.
- Trace tables live under `trace.*` only.
- No health fact table is created for trace/provenance data.
- Tests document the schema ownership boundary.
- No MCP or engine behavior changes are included.

## Reviewer Guidance

Reviewers should focus on schema meaning and future compatibility. The exact column types can be pragmatic, but the boundary cannot drift: tool-use provenance is not health data.
