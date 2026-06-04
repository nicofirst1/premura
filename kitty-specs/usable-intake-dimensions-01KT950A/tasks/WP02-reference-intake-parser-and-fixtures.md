---
work_package_id: WP02
title: Reference intake parser + synthetic fixtures
dependencies:
- WP01
requirement_refs:
- C-001
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
history:
- 2026-06-04T11:52:07Z created by /spec-kitty.tasks
authoritative_surface: tests/fixtures/intake/
execution_mode: code_change
owned_files:
- tests/fixtures/intake/**
tags: []
---

# WP02 — Reference intake parser + synthetic fixtures

## Objective

Prove the build path end-to-end — `parse → IntakeBatch → persist_intake_batch` —
with a **minimal reference parser** and **synthetic fixtures** that carry the
parser-side edge cases. This is a proof/contract anchor, **not** a production
vendor parser (C-005). Satisfies **FR-008**.

## Context

WP01 makes the runtime able to persist intake output. This WP is the first real
exercise of that path. Everything here is synthetic — real Fitbit/Cronometer/etc.
exports never enter the repo (C-001). Keep all artifacts under
`tests/fixtures/intake/` (your only owned surface). The reference parser lives
here as a fixture module, not under `src/premura/parsers/`, so it cannot be
mistaken for a shipped vendor parser.

The intake types and persistence you target already exist:
`NutritionIntakeInput`, `SupplementIntakeInput`, `IntakeBatch` in
`src/premura/parsers/base.py`; `persist_intake_batch(...)` in
`src/premura/store/profile_intake.py`. Intake tables:
`hp.nutrition_intake_event/_item`, `hp.nutrition_quantity`,
`hp.supplement_intake_event`, `hp.supplement_item`, `hp.supplement_dose`.

## Subtasks

### T007 — Synthetic nutrition fixture
A small real-shaped file (real-looking column names, **made-up values**) that
exercises:
- an **event-level** nutrition quantity (attached to the whole event)
- an **item-level** nutrition quantity (attached to a food item)
- one event whose **`local_tz` puts it on a different local calendar day than its
  UTC date** (e.g. a late-evening local time that is past midnight UTC)
- one **unmapped source field** (a column with no canonical home)

### T008 — Synthetic supplement fixture
A small real-shaped file exercising:
- a **text-only dose** (descriptive, no numeric amount)
- a **numeric dose**
- `local_tz` present
- one **unmapped source field**

### T009 — Reference intake parser
- A minimal parser (fixture module) that parses both synthetic fixtures and emits
  an `IntakeBatch` via the **WP01 protocol** (observation-free intake output).
- It **declares unmapped fields as gaps** (`unmapped_metrics` / `SkippedRow`) —
  never silently drops a column.
- Provenance on every row via `source_descriptors`; idempotent `dedupe_key`s.

### T010 — End-to-end test
- Parse → `persist_intake_batch` → assert rows land in the nutrition and
  supplement tables.
- Assert the unmapped fields were surfaced (not dropped).
- Assert the text-only dose persists, and that event-level vs item-level
  nutrition quantities persist **distinctly** (not double-counted).
- Re-run is idempotent (second persist inserts 0 new rows).

## Branch Strategy

Plan/base branch **master**; final merge target **master**. Worktree per lane in
`lanes.json`. Implement with: `spec-kitty agent action implement WP02 --agent <name>`
(after WP01 is approved).

## Test Strategy (test-first)

Write the T010 end-to-end assertions first (they will fail until the parser and
fixtures exist), then author fixtures (T007/T008) and the parser (T009) to make
them pass. Assert through persisted warehouse rows, not parser internals.

## Definition of Done (incl. D7 edge-case fixtures)

- [ ] Parsing the synthetic fixtures lands rows in the intake tables.
- [ ] **Unmapped field** surfaced as a gap, asserted (D7).
- [ ] **Text-only dose** persists, asserted (D7).
- [ ] **Event-level and item-level** nutrition quantities persist distinctly (D7).
- [ ] A **local_tz** event whose local day ≠ UTC date is present in the fixture (feeds WP03/WP04 divergence tests).
- [ ] No PHI / real export committed (C-001); all values made up.
- [ ] Idempotent re-persist.

## Risks

- **Fixture too clean to test the edges.** Mitigation: the DoD enumerates each
  edge case as a required assertion; a reviewer checks each is actually exercised.

## Reviewer Guidance

- Confirm the reference parser uses the WP01 protocol, not a side path.
- Confirm every edge-case row exists AND is asserted (not just present).
- Confirm nothing real/PHI leaked into the fixture values.
