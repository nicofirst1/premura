---
work_package_id: WP04
title: Structured skip persistence (hp.ingest_skip)
dependencies:
- WP02
- WP03
requirement_refs:
- FR-003
- NFR-002
- NFR-004
planning_base_branch: mission/substrate-unit-guarantees
merge_target_branch: mission/substrate-unit-guarantees
branch_strategy: Planning artifacts for this mission were generated on mission/substrate-unit-guarantees. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into mission/substrate-unit-guarantees unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 2 - Closed loops
history:
- timestamp: '2026-08-15T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/store/
create_intent:
- src/premura/store/migrations/009_ingest_skip.sql
- tests/intake/test_ingest_skip_migration.py
- tests/intake/test_measurement_unit_ingest.py
execution_mode: code_change
owned_files:
- src/premura/store/migrations/009_ingest_skip.sql
- src/premura/store/loader.py
- tests/intake/test_ingest_skip_migration.py
- tests/intake/test_measurement_unit_ingest.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Structured skip persistence

## Objective

Nothing computed is dropped: unit refusals (WP02), `batch.skipped_rows`, and `batch.unmapped_metrics` persist to a new queryable `hp.ingest_skip` table, joined to their ingest run.

## Read first

`kitty-specs/substrate-unit-guarantees-01M01A8V/data-model.md` (authoritative column spec); migration precedent `src/premura/store/migrations/005_trace_audit.sql`; idempotency-test precedent `tests/intake/test_interval_unit_migration.py` (shape); `store/loader.py` (`finish_ingest_run`, `_persist_plan`).

## Subtasks

- **T010**: `009_ingest_skip.sql` per data-model.md (CREATE TABLE IF NOT EXISTS + two indexes; append-only; idempotent).
- **T011**: loader `_persist_skips(conn, batch, batch_id, unit_refusals)` called before `finish_ingest_run`, writing kinds `unit_unconvertible` (from WP02's refusals, with from/to units), `parser_skip` (from `batch.skipped_rows`), `unmapped_metric` (from `batch.unmapped_metrics`). `dup_priority` stays count-only on `ingest_run` (stretch goal only — do NOT restructure dedupe for row detail). `finish_ingest_run` and `ingest_run` columns unchanged.
- **T012**: tests — migration exists/idempotent (double-run, no dupes/errors); extend WP02's refusal test: after `load()`, exactly one `hp.ingest_skip` row for the batch with `kind='unit_unconvertible'` and correct `from_unit`/`to_unit`/`metric_id`; loader-reported refusal count equals persisted rows (NFR-002).

## Done criteria

New + existing intake tests green; full suite + lint/type gates clean.

## Constraints

Additive migration only (C-002). No PHI. C-005 gate: one table, one helper — no skip-reporting framework.
