---
work_package_id: WP01
title: Self-reconciliation gate (raw-header honesty twin)
dependencies: []
requirement_refs:
- FR-003
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cheap-operator-live-trial-01KT6PSA
base_commit: 0a89c892ff27e9dc9d6caebbd7538bd733358bba
created_at: '2026-06-03T13:33:41.502494+00:00'
subtasks:
- T001
- T002
- T003
shell_pid: "30098"
agent: "claude:opus:python-implementer:implementer"
history:
- timestamp: '2026-06-03T12:45:00Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/self_reconcile.py
execution_mode: code_change
owned_files:
- src/premura/harness/self_reconcile.py
- tests/test_self_reconcile.py
tags: []
---

# WP01 — Self-reconciliation gate

## Objective

Build the **manifest-blind honesty gate** the operator retry loop uses. It checks
that **every raw column present in the source file's header/structure** is either
mapped to a declared metric or declared in `unmapped_metrics` / `skipped_rows`.
It is the **answer-key-free reconstruction of the grader's `honest_about_gaps`
rule** — `grader.honest_about_gaps` (`src/premura/harness/grader.py:153-184`) uses
the committed fixture manifest **only to enumerate source-field names**, and those
names are readable directly from the file header. So this gate needs **no**
ground-truth manifest and must never read one (C-005).

## Why it matters

The precursor spike (`docs/history/audits/2026-06-03-live-trial-first-real-model-spike.md`)
showed a cheap model ships *loadable-but-dishonest* parsers (it silently dropped
`confidence` / `altitude_m`). A loop that only checks "does it load" never fixes
this. This gate gives the loop a runtime-faithful honesty signal — the only
honesty signal that exists at real runtime, where there is no manifest or grader.

## Required reading before you start

- `src/premura/harness/grader.py:153-184` (`_grade_honest_about_gaps`) — the rule
  you are reconstructing. Note: it passes a field iff it was **loaded** OR
  **declared**; anything else is a `silent_drop`.
- `src/premura/parsers/base.py` — `IngestBatch` fields: `declared_metrics`,
  `measurements` (each has a `source_*`), `unmapped_metrics`, `skipped_rows`
  (each `SkippedRow` has `raw_field`).
- `kitty-specs/cheap-operator-live-trial-01KT6PSA/contracts/self-reconciliation.md`
  and `data-model.md` (the `SelfReconciliationResult` shape).
- `tests/fixtures/session_log/fitbit_heart_rate_synthetic.csv` (the fixture) and
  `tests/fixtures/session_log/fixture_fields.yaml` (the manifest — used ONLY in
  the test to assert equivalence, NEVER imported by the gate).

## Subtasks

### T001 — `SelfReconciliationResult` structure

**Purpose**: the value object the gate returns (see `data-model.md`).

**Steps**:
1. In a new module `src/premura/harness/self_reconcile.py`, define a
   frozen/slots dataclass `SelfReconciliationResult` with fields:
   - `passed: bool`
   - `source_columns: list[str]` — the full ground set from the file header
   - `accounted: frozenset[str]` (or `set[str]`) — columns mapped or declared
   - `unaccounted: list[str]` — sorted `source_columns − accounted`
2. Invariant: `passed == (not unaccounted)`. Keep arrays sorted for determinism.

**Files**: `src/premura/harness/self_reconcile.py` (new).

### T002 — `self_reconcile()` gate

**Purpose**: compute the result from the source file + the parser's own batch,
with no manifest.

**Steps**:
1. Signature (mapped columns are an **explicit input**, never guessed):
   `def self_reconcile(source_path: Path, batch: IngestBatch, mapped_columns: Iterable[str]) -> SelfReconciliationResult:`
   where `mapped_columns` is the set of source columns the parser consumed to emit
   its metrics. The caller (the operator in WP03) supplies it; tests pass it
   explicitly. This removes the ambiguity of inferring mapped columns from the
   batch.
2. **Source columns (the ground set)** — read them from the file's
   header/structure, NOT from what the parser chose to read:
   - For the CSV fixture: open `source_path` and read the header row
     (`csv.reader` → first row) to get the column names.
   - Keep this a small, focused reader; slice scope is the heart-rate CSV. If the
     file has no header / is unreadable, return `passed=False` (an empty ground
     set is not a silent pass — see edge cases).
3. **Accounted set** — exactly: `accounted = set(mapped_columns) |
   set(batch.unmapped_metrics) | {r.raw_field for r in batch.skipped_rows}`. No
   inference, no fallback. (This is the answer-key-free analogue of the grader's
   "loaded OR declared".)
4. Compute `unaccounted = sorted(set(source_columns) - accounted)`, set
   `passed = not unaccounted`.

**Edge cases**:
- A column read as a metric source AND also listed in `unmapped` → still
  accounted (don't double-penalize).
- Empty/headerless file → `passed=False` (cannot prove honesty); never a silent
  pass.

**Files**: `src/premura/harness/self_reconcile.py`.

### T003 — Unit test (default-collected, no model server)

**Purpose**: prove the gate is correct AND equivalent to the grader on the fixture.

**Steps**: in `tests/test_self_reconcile.py` (pass `mapped_columns` explicitly):
1. **Honest parser passes**: `mapped_columns={"bpm"}`, batch declares
   `timestamp`/`confidence`/`altitude_m` as unmapped → `passed True`,
   `unaccounted == []`.
2. **Silent drop fails**: same but omit `altitude_m` from unmapped →
   `passed False`, `unaccounted == ["altitude_m"]`.
3. **Loophole closed**: `mapped_columns={"bpm"}` and `confidence` is neither
   mapped nor declared → FAILS, `confidence` ∈ `unaccounted`. The ground set is the
   FILE header, not the columns the parser read.
4. **Grader equivalence**: for the honest batch, assert `self_reconcile(...).passed`
   matches `grader._grade_honest_about_gaps(...)["passed"]` computed against the
   committed `fixture_fields.yaml`. (The test may import the manifest; the gate
   must not.)

**Files**: `tests/test_self_reconcile.py` (new).

## Definition of Done

- `self_reconcile.py` exists; `self_reconcile()` reads the **file header** as the
  ground set and never imports the manifest.
- `tests/test_self_reconcile.py` passes in the **default** suite
  (`uv run pytest tests/test_self_reconcile.py`), including the loophole and
  grader-equivalence cases.
- `ruff check`, `ruff format --check`, and `mypy` clean on the new files.

## Risks & reviewer guidance

- **Biggest risk**: re-introducing the loophole by deriving the ground set from
  the parser's behaviour instead of the file header. Reviewer: confirm the column
  set comes from reading `source_path`, and that test case 3 fails for a parser
  that ignores a column.
- **C-005**: grep the module for any reference to `fixture_fields` / manifest —
  there must be none.
- Reviewer should confirm the docstring documents the exact "accounted" rule and
  that it matches `honest_about_gaps` semantics (loaded-or-declared).

## Branch strategy

Planning happened on `master`; this WP merges back into `master`. Execution
worktrees are allocated per computed lane from `lanes.json` during
`/spec-kitty.implement` — do not create worktrees by hand.

Implement command: `spec-kitty agent action implement WP01 --agent <name>`

## Activity Log

- 2026-06-03T13:33:42Z – claude:opus:python-implementer:implementer – shell_pid=30098 – Assigned agent via action command
- 2026-06-03T13:39:04Z – claude:opus:python-implementer:implementer – shell_pid=30098 – Ready for review: self_reconcile gate + unit tests green
