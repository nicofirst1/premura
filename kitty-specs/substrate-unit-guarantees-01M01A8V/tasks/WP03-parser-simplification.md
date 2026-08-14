---
work_package_id: WP03
title: Parsers stop converting (lab_pdf, bmt emit unit-as-observed)
dependencies:
- WP02
requirement_refs:
- FR-004
- NFR-001
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this mission were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Simplification
history:
- timestamp: '2026-08-15T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/parsers/
create_intent: []
execution_mode: code_change
owned_files:
- src/premura/parsers/lab_pdf.py
- src/premura/parsers/bmt.py
- tests/test_parsers/test_lab_pdf.py
- tests/test_parsers/test_bmt.py
- tests/intake/test_measurement_unit_ingest.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Parsers stop converting

## Objective

Delete both parser-local conversion ladders; parsers emit `Measurement.unit` as observed and rely on WP02's boundary. `lab_pdf.py` and `bmt.py` must each get strictly smaller (NFR-001).

## Read first

WP02's merged loader change; `src/premura/parsers/lab_pdf.py` (`_UNIT_ALIASES` 41-95, `_normalize_unit` 374, `_convert_value_to_canonical` 387-446, `_measurement_from_row` 209-280), `src/premura/parsers/bmt.py` (`_convert_to_canonical` 75-109, `_emit_long_row` 166-208).

## Subtasks

- **T007**: `lab_pdf.py` — delete `_UNIT_ALIASES` and `_convert_value_to_canonical`; `_normalize_unit` becomes a thin call to `units.normalize_unit`; `_measurement_from_row` emits the normalized observed unit unconditionally and drops its local `unit_mismatch` skip branch (the loader decides now). Keep `original_unit` in `raw_payload`.
- **T008**: `bmt.py` — delete `_convert_to_canonical` (its silent pass-through and its claim-canonical-without-converting branch die with it); long-format emits raw value + observed unit. Wide-format keeps its config-declared unit toggle (no per-row unit string exists) with a one-line comment naming it the documented scope exception.
- **T009**: rewrite the now-obsolete parser conversion assertions as emits-observed-unit assertions; extend `tests/intake/test_measurement_unit_ingest.py` with e2e runs through the REAL simplified `LabPdfParser` and `BMTParser` fixtures asserting the two-step pipeline (parser observes → loader converts) yields the same canonical warehouse rows the old one-step pipeline did.

## Done criteria

All parser tests + intake tests green; `git diff --stat` shows `lab_pdf.py` and `bmt.py` net-negative; full suite + lint/type gates clean.

## Constraints

No behavior-preserving rewrites beyond the deletions (shortest diff). No PHI in fixtures. C-005 gate: this WP must shrink the codebase — a reviewer seeing net growth in parsers rejects.
