---
work_package_id: "WP02"
title: "Load-boundary unit enforcement for measurements"
dependencies:
  - "WP01"
requirement_refs:
  - "FR-002"
  - "NFR-002"
planning_base_branch: "master"
merge_target_branch: "master"
branch_strategy: "Planning artifacts were generated on master; completed changes must merge back into master."
owned_files:
  - "src/premura/store/loader.py"
  - "src/premura/parsers/base.py"
  - "tests/intake/test_measurement_unit_ingest.py"
subtasks:
  - "T004"
  - "T005"
  - "T006"
phase: "Phase 1 - Substrate"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2026-08-15T00:00:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP02 – Load-boundary unit enforcement for measurements

## Objective

`loader.load()` becomes the sole unit decision-maker for measurements: every row is converted to `dim_metric.canonical_unit` via `premura.units.convert` or refused row-level. Extends the existing interval pattern (`loader.py:164-187`, "the warehouse is the single source of unit truth") to `fact_measurement`.

## Read first

`kitty-specs/substrate-unit-guarantees-01M01A8V/contracts/load-boundary.md`; `src/premura/store/loader.py` (esp. `_persist_plan` 147-187, `LoadStats`), `src/premura/store/dedupe.py` (frame schemas), precedent test `tests/intake/test_interval_unit_ingest.py`.

## Subtasks

- **T004**: in `_persist_plan`, before the measurement INSERT: fetch canonical units for the batch's metric_ids; run a Python/polars pass over `plan.measurement_rows` — per row `units.normalize_unit`, identity → keep; convertible → rewrite `value_num` + `unit` to canonical; no rule → drop the row into a refusals list. Insert only surviving rows. Keep dedupe untouched (unit pass is post-dedupe; orthogonal concerns). Return refusals on the load outcome; `LoadStats` gains `rows_skipped_unit`.
- **T005**: document `Measurement.unit` as "unit as observed" in `parsers/base.py` (docstring only — field stays required); observed unit must remain available in `raw_payload` (parsers already do this; do not add new plumbing here).
- **T006**: `tests/intake/test_measurement_unit_ingest.py`, structural mirror of the interval precedent: (a) `test_ingested_measurement_carries_canonical_unit` — batch through real `loader.load()` with a row in a convertible non-canonical unit (e.g. `lb` against a `kg` metric) → value converted, stored unit == canonical for EVERY row; (b) `test_unrecognized_unit_refuses_row_not_batch` — one unconvertible row + one good row → good lands, bad absent, `rows_skipped_unit == 1`, `load()` does not raise.

## Done criteria

New tests green; `tests/intake/test_dedupe.py` and all parser tests pass UNMODIFIED (parsers untouched until WP03 proves the change is additive); full suite + lint/type gates clean.

## Constraints

Values are converted, never merely relabeled (relabeling is the incident bug). No changes to `dedupe.py` logic. No PHI. Spec C-005 over-engineering gate applies: one boundary function, no new abstraction layers.
