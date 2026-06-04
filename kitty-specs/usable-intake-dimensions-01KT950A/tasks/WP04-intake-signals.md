---
work_package_id: WP04
title: Intake descriptive signals
dependencies:
- WP03
requirement_refs:
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-006
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
- T021
- T022
history:
- 2026-06-04T11:52:07Z created by /spec-kitty.tasks
authoritative_surface: src/premura/engine/descriptive_signals.py
execution_mode: code_change
owned_files:
- src/premura/engine/descriptive_signals.py
- src/premura/engine/comparative_signals.py
- tests/test_intake_signals.py
tags: []
---

# WP04 — Intake descriptive signals

## Objective

Ship one descriptive, **non-diagnostic** signal per intake domain, reading
through the WP03 resolvers, with positive-path, refusal-path, and local-midnight
fixtures. Satisfies **FR-003, FR-004, FR-005, NFR-001**, the reported-basis half
of **NFR-006**, and **SC-001/SC-002/SC-003**.

## Context (no `__init__.py` edit — important for ownership)

- Add both signals into the **already-registered** signal modules:
  `descriptive_signals.py` and/or `comparative_signals.py`. They register via
  each module's `register_builtin_signals()` (which appends `SignalSpec(...)` to
  `REGISTRY`). Because these modules are already in `_BUILTIN_SIGNAL_MODULES`,
  **you do not touch `engine/__init__.py`** (WP03 owns it).
- The load guard at `engine/__init__.py:597` is a **subset** check
  (`_BUILTIN_SIGNAL_NAMES <= set(REGISTRY)`), so a new signal **not** listed in
  `_BUILTIN_SIGNAL_NAMES` still works. Intentionally leave the two new signals out
  of that frozenset (it is a load guard, not the authoritative registry; the
  authoritative registry is `REGISTRY`). Note this in your PR so the reviewer
  knows it is deliberate, not an omission.
- Signals declare their dependency and call `resolve_dependency(...)` for their
  domain (import it as `descriptive_signals.resolve_dependency` so tests can
  monkeypatch, mirroring the existing pattern at `descriptive_signals.py:45`).
- These signals are **parameterized** (a matcher/key + a window). The existing
  zero-arg signal path `compute(name, conn)` passes no params, and `correlate` is
  **not** the model (it is an *analytical tool* on a separate door —
  `invoke_analytical_tool` — not a registered signal). Instead, your signal `fn`
  receives caller params through the **WP03-extended `compute()` seam** (T031).
  Register the signals via `register_builtin_signals()` as normal; their `fn`
  accepts the threaded params.
- Use the supplement matcher semantics **pinned by WP03** (T012) — do not invent a
  second matching rule.

## Subtasks

### T017 — `supplement_intake_adherence` (status/coverage family)
- Declares a `supplement_intake` dependency; takes a caller-declared **matcher**
  and a bounded **window_days** (repo default).
- Returns the standard envelope (`available` / `missing_input` / `stale_input` /
  `insufficient_data`) plus `logged_day_count` (K), `window_day_count` (N),
  `coverage_fraction` (K/N), `latest_logged_at`, descriptive `caveats`.
- **No recommendation/normative language** ("you should take…" is forbidden).

### T018 — `nutrition_intake_trend` (trend family)
- Declares a `nutrition_intake` dependency; takes a caller-declared **nutrient/
  energy key** and a bounded **window_days**.
- Returns `trend_direction` (`up`/`down`/`flat`/`unknown`), visible `points`,
  `days_with_data`, `window_day_count`, `latest_logged_at`, `caveats`.
- **Never imputes missing days** — gaps stay visible; no carry-forward.

### T019 — Positive-path fixtures (data present → answer surfaced)
- For **both** signals, a fixture where the requested intake data is present and a
  real answer is surfaced — **distinct** from the refusal tests. (This is the D5
  drift control: a missingness-only suite would let an always-empty path look
  compliant.)

### T020 — Refusal-path tests (structurally distinct states)
- `missing_input` — declared-but-empty domain / no matching rows (distinct from
  "domain unsupported").
- `stale_input` — matching history exists but latest usable data is outside the
  freshness rule.
- `insufficient_data` — some rows but not enough to answer honestly.

### T021 — Local-midnight divergence fixture (NFR-006 / D4)
- An event whose `local_tz` puts it on a different local day than its UTC date.
- Assert the **reported** day/window metadata uses the **same local-day basis**
  the computation uses (no second path recomputing from raw UTC).

### T022 — Non-diagnostic assertion test (NFR-001)
- Assert no envelope/caveat contains a reference range, "should", a p-value,
  "significant", or causal language, across both signals.

## Branch Strategy

Plan/base branch **master**; final merge target **master**. Worktree per lane in
`lanes.json`. Implement with: `spec-kitty agent action implement WP04 --agent <name>`
(after WP03 is approved).

## Test Strategy (test-first)

Write `tests/test_intake_signals.py` first: positive-path, the three refusal
states, no-imputation, local-midnight, and non-diagnostic assertions — all
failing — then implement T017/T018. Seed rows via `persist_intake_batch`; assert
through the signal envelopes (black-box).

## Definition of Done (incl. D7 edge-case fixtures)

- [ ] Both signals answer when data is present (SC-001/SC-002) — positive-path fixtures (D5).
- [ ] Three refusal states are structurally distinct (SC-003) — **declared-but-empty domain** fixture present (D7).
- [ ] Nutrition trend never imputes missing days — **gap-visibility** fixture present (D7).
- [ ] **Stale** refusal fixture present (D7).
- [ ] Local-midnight divergence fixture green: reported basis == computed local-day basis (NFR-006 / D4).
- [ ] Non-diagnostic assertion green (NFR-001).
- [ ] No `engine/__init__.py` edit; new signals registered via `register_builtin_signals()`.
- [ ] ruff + ruff format + mypy + pytest green.

## Risks

- **R2 / D5 — missingness-only tests mask an unimplemented positive path.**
  Mitigation: T019 ships a distinct data-present fixture per signal.
- **R3 / D4 — UTC-date reporting diverges from local-day compute.** Mitigation:
  T021 crosses local midnight and asserts equal bases.
- **Ownership** — adding a new signal module would force an `__init__.py` edit and
  collide with WP03. Mitigation: put signals in the already-registered modules.

## Reviewer Guidance

- Confirm the positive-path fixtures actually surface an answer (not just "no
  error").
- Confirm the local-midnight test would fail if the report path recomputed from
  raw UTC.
- Confirm no `__init__.py` change crept in.
