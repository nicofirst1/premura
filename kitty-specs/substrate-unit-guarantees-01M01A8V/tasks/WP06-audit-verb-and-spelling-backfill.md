---
work_package_id: WP06
title: audit-integrity CLI verb + spelling-variant backfill migration
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-008
- NFR-004
planning_base_branch: mission/substrate-unit-guarantees
merge_target_branch: mission/substrate-unit-guarantees
branch_strategy: Planning artifacts for this mission were generated on mission/substrate-unit-guarantees. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into mission/substrate-unit-guarantees unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
phase: Phase 3 - Detection
history:
- timestamp: '2026-08-15T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/cli.py
create_intent:
- src/premura/store/migrations/010_unit_spelling_backfill.sql
- tests/intake/test_unit_spelling_migration.py
- tests/test_cli_audit_integrity.py
execution_mode: code_change
owned_files:
- src/premura/cli.py
- src/premura/store/migrations/010_unit_spelling_backfill.sql
- tests/intake/test_unit_spelling_migration.py
- tests/test_cli_audit_integrity.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 – Detection + legacy spelling cleanup

## Objective

The closed detection loop: `premura audit-integrity` reports (a) `fact_measurement` rows whose unit differs from `dim_metric.canonical_unit` and (b) `ingest_run.source_kind` values outside the registered vocabulary. Plus the one-time idempotent relabel of legacy spelling-only unit variants.

## Read first

Migration precedent `src/premura/store/migrations/006_interval_unit.sql` (guarded idempotent UPDATE); `cli.py` command conventions; `parsers/registry.py` (`registered_source_kinds`); `units.py` (WP01) for the spelling vocabulary.

## Subtasks

- **T017**: `audit-integrity` CLI verb — two read-only queries (unit mismatches grouped by metric/unit/canonical with counts; distinct out-of-vocabulary source kinds), plain text output, exit 0 with findings listed (detection, not a gate). Open the warehouse read-only.
- **T018**: `010_unit_spelling_backfill.sql` — UPDATE ... SET unit = canonical FROM dim_metric WHERE the (stored, canonical) pair is in a hand-vetted allowlist baked into the SQL. Author the allowlist by running T017's query against a seeded fixture of the known variant classes (spelling-equal pairs like `U/l`→`U_per_l`, `%`→`pct`, `µg/l`→`ug_per_l`, `mg/dl`→`mg_per_dl`, `ng/ml`→`ng_per_ml`, `UI/ml`→`IU_per_ml`; use `units.normalize_unit` equivalence as the vetting rule: pair qualifies iff normalize(stored) == canonical). Values never rescaled. Comment block explains the rule and why magnitude-wrong rows are excluded.
- **T019**: tests — spelling-variant row relabeled with value unchanged; magnitude-wrong row (e.g. mg/dl stored under mmol_per_l canonical) UNTOUCHED (allowlist must not over-fire); double-run idempotent; audit verb reports seeded bad rows and reports nothing on a clean warehouse.

## Done criteria

New tests green; full suite + lint/type gates clean.

## Constraints

Migration stays replay-forever idempotent (C-002). Audit verb is read-only. No PHI (synthetic fixtures only; the real-warehouse audit run happens post-merge, outside the repo). C-005: two queries and one UPDATE — no reporting framework.
