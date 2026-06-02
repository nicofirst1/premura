---
work_package_id: WP04
title: Synthetic fixtures + reference parsers
dependencies: []
requirement_refs:
- FR-040
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
agent: "claude:opus:python-implementer:implementer"
shell_pid: "32127"
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: tests/fixtures/session_log/
execution_mode: code_change
owned_files:
- tests/fixtures/session_log/**
tags: []
---

# WP04 — Synthetic fixtures + reference parsers

## Objective

Commit the deterministic test inputs the always-on check runs from (FR-040): a
**synthetic Fitbit-HR file** (public structure, made-up values — never PHI), a
**ground-truth manifest** of its complete source-field set, and **two reference
parsers** — a `good` one (passes all three grader rules) and a `dishonest` one
(silently drops a field, must be graded FAIL). These prove the honesty rail
end-to-end (NFR-007, SC-002).

These parsers live under `tests/fixtures/` and are **installed into a sandbox
only** by later WPs — they are **not** shipped production parsers, so Fitbit stays
a genuinely unsupported target for the live trial.

Read first: `data-model.md` (fixture manifest + reconciliation, D6),
`src/premura/parsers/base.py` (`IngestBatch`, `Measurement`, `PluginParser`
protocol), `src/premura/parsers/CONTRACT.md`, `src/premura/dim_metric.yaml`
(`heart_rate` exists).

## Context / grounding

- `IngestBatch` fields (base.py:327): `source_kind`, `declared_metrics`,
  `measurements`, `unmapped_metrics`, `skipped_rows`, etc. Emitting a `derived:`
  metric raises (base.py:387).
- `heart_rate` is already a canonical `metric_id` in `dim_metric.yaml` (unit bpm).
- The honesty reconciliation (D6) requires: each **mappable** source field maps to
  a **distinct** `metric_id`, and unmappable fields are marked `canonical_metric:
  null` so "declared unmapped" is the only honest disposition.

## Subtasks

### T014 — synthetic CSV + manifest

**Purpose**: The committed input + the ground truth the grader reconciles against.

**Steps**:
1. `tests/fixtures/session_log/fitbit_heart_rate_synthetic.csv` — a tiny file with
   **public** Fitbit-export-shaped columns and **made-up** values, e.g. columns:
   `timestamp,bpm,confidence,altitude_m` with ~5 rows. (Real public structure,
   invented numbers — no PHI, never a real export.)
2. `tests/fixtures/session_log/fixture_fields.yaml` — the complete source-field
   ground truth:
   ```yaml
   source: fitbit_heart_rate
   csv: fitbit_heart_rate_synthetic.csv
   source_fields:
     - name: timestamp
       canonical_metric: null      # structural; honest = not a metric, declared/skipped
     - name: bpm
       canonical_metric: heart_rate
     - name: confidence
       canonical_metric: null
     - name: altitude_m
       canonical_metric: null
   ```
   Note the **distinct-metric** rule: only `bpm` maps, to `heart_rate`. (If you add
   a second mappable field later, give it a different metric.)

**Validation**: CSV header == the `source_fields` names; YAML parses.

### T015 — `good_fitbit_hr` reference parser (PASS)

**Purpose**: An honest parser: maps `bpm → heart_rate`, declares the rest as
unmapped, loads cleanly.

**Steps** — `tests/fixtures/session_log/parsers/good_fitbit_hr.py`:
- Implement the `PluginParser` protocol: `parse(path) -> IngestBatch`.
- Read the CSV; emit a `Measurement` per row for `heart_rate` from `bpm`.
- `declared_metrics = ["heart_rate"]`; `unmapped_metrics = ["timestamp",
  "confidence", "altitude_m"]` (every non-mapped source field declared).
- Do **not** emit any `derived:` metric.

**Validation**: `parse()` returns a batch with `declared_metrics == emitted
metric_ids == {heart_rate}` and `unmapped_metrics` covering the other three fields.

### T016 — `dishonest_fitbit_hr` reference parser (silent drop)

**Purpose**: The adversary that the honesty rail must catch.

**Steps** — `tests/fixtures/session_log/parsers/dishonest_fitbit_hr.py`:
- Same happy mapping (`bpm → heart_rate`, loads fine) **but** silently **drops**
  `altitude_m`: it does **not** load it **and** does **not** list it in
  `unmapped_metrics`/`skipped_rows`. It *does* declare `timestamp` and `confidence`
  (so only `altitude_m` is the silent drop — a single, unambiguous failure).
- Its own metadata therefore "looks clean" — the point is that reconciliation
  against the fixture (not the parser's claim) still catches it.

**Validation**: `parse()` returns a batch whose `unmapped_metrics`+`skipped_rows`
omit `altitude_m`, yet `altitude_m` is not loaded.

### T017 — fixtures tests

**Steps** — `tests/fixtures/session_log/` is data; put the test at
`tests/fixtures/session_log/test_fixtures.py` (owned by this WP):
- `test_manifest_matches_csv_header`: CSV header set == manifest `source_fields`
  names.
- `test_distinct_metric_per_mappable_field`: non-null `canonical_metric` values are
  unique (the D6 constraint).
- `test_good_parser_declares_all_gaps`: every source field is either the mapped
  metric or in `unmapped_metrics` (no silent drop).
- `test_dishonest_parser_silently_drops_altitude`: `altitude_m` is neither emitted
  nor declared — the planted defect, asserted explicitly.

## Definition of Done

- [ ] CSV + manifest + both parsers committed under `tests/fixtures/session_log/`.
- [ ] No real data / PHI anywhere; values are invented (C-003).
- [ ] `tests/fixtures/session_log/test_fixtures.py` green.
- [ ] Distinct-metric-per-mappable-field constraint holds (D6).
- [ ] `ruff` (check+format) and `pytest -q tests/fixtures/session_log/` green.
      (`mypy` over the parser modules if they carry type hints.)

## Risks / reviewer guidance

- The dishonest parser must drop exactly **one** field (`altitude_m`) so the
  grader's `silent_drops` is unambiguous (`["altitude_m"]`).
- Reviewer: confirm the CSV is plausibly Fitbit-shaped **public structure** but
  obviously synthetic values — and that no real export was copied in.
- Do not register these parsers in any production parser registry.

## Implementation command

```bash
spec-kitty agent action implement WP04 --agent <name>
```

## Activity Log

- 2026-06-02T13:28:00Z – claude:opus:python-implementer:implementer – shell_pid=32127 – Started implementation via action command
