---
work_package_id: WP01
title: Shared units module + read-only connection default
dependencies: []
requirement_refs:
- FR-001
- NFR-001
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this mission were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Substrate
history:
- timestamp: '2026-08-15T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/units.py
create_intent: []
execution_mode: code_change
owned_files:
- src/premura/units.py
- src/premura/store/duck.py
- tests/test_units.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared units module + read-only connection default

## Objective

Create `src/premura/units.py` — the single home for unit spelling normalization and value conversion — and flip `duck.connect`'s default to read-only. No parser or loader behavior changes in this WP.

## Read first

`kitty-specs/substrate-unit-guarantees-01M01A8V/{spec.md,plan.md,contracts/load-boundary.md}`; source logic at `src/premura/parsers/lab_pdf.py:374-446` (`_normalize_unit`, `_convert_value_to_canonical`, `_UNIT_ALIASES` at 41-95) and `src/premura/parsers/bmt.py:75-109` (`_convert_to_canonical`).

## Subtasks

- **T001**: `units.py` with `normalize_unit(raw: str) -> str` and `convert(value: float, *, from_unit: str, to_unit: str, metric_id: str) -> float | None`. Table-driven module dicts: `_ALIASES` (union of lab_pdf's alias dict + bmt's spellings; keep the case-sensitive German CBC entries `G/l`→`10^9_per_l`, `T/l`→`10^12_per_l` BEFORE lowercasing), `_SIMPLE_FACTORS` (metric-agnostic (from,to)→factor, incl. lb/g→kg, in/cm/mm length, mg_per_l↔mg_per_dl etc.), `_METRIC_SCOPED` ((from,to)→{metric_id: factor-or-divisor}: mEq≡mmol for lab:sodium/lab:potassium, molar Na/K (divisor), Ca/Mg/P mmol→mg_per_dl, B12 pmol→pg ×1.355), `_AFFINE` ((from,to)→{metric_id: (a,b)}: HbA1c mmol_per_mol→pct = 0.09148x+2.152). Dispatch: identity → simple → metric-scoped → affine → `None`. Behavior must be a byte-identical port, not a redesign. State the rule for adding entries in a short module docstring.
- **T002**: `store/duck.py`: `connect(..., read_only: bool = True)`; `initialize()` passes `read_only=False` explicitly. Verify no other caller relied on the old default (grep `duck.connect|duck.initialize`).
- **T003**: `tests/test_units.py`: (a) parametrize `normalize_unit` over EVERY entry of the old `lab_pdf._UNIT_ALIASES` (import the expectation pairs into the test as literals — the old dict is deleted in WP03); (b) reproduce every conversion case currently asserted in `tests/test_parsers/test_lab_pdf.py:137` and `test_bmt.py:31,79` (same inputs → same outputs); (c) unknown pair → `None`; (d) `connect(path)` with no kwarg is read-only, `initialize(path)` still writes.

## Done criteria

`uv run pytest tests/test_units.py -q` green; full `uv run pytest -q` green (blast-radius check for the default flip); `ruff check`, `ruff format --check`, `mypy src/` clean.

## Constraints

No new dependencies. No classes — data tables + functions only (spec C-005 review gate will check). No PHI in fixtures. Do not modify parsers or loader in this WP.
