---
work_package_id: WP01
title: Parser runtime intake support
dependencies: []
requirement_refs:
- FR-007
- NFR-002
- NFR-004
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-usable-intake-dimensions-01KT950A
base_commit: a35ab44e591a85d0a92e9516fcd98fb0e39d2922
created_at: '2026-06-04T12:38:01.682360+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
shell_pid: "19912"
agent: "claude:opus:python-reviewer:reviewer"
history:
- 2026-06-04T11:52:07Z created by /spec-kitty.tasks
authoritative_surface: src/premura/parsers/
execution_mode: code_change
owned_files:
- src/premura/parsers/base.py
- src/premura/parsers/CONTRACT.md
- src/premura/cli.py
- src/premura/harness/ingest_runner.py
- src/premura/harness/live_trial_ollama.py
- tests/fixtures/session_log/test_fixtures.py
- tests/test_intake_parser_runtime.py
tags: []
---

# WP01 — Parser runtime intake support

## Objective

Make a parser able to emit **intake** output and have the runtime persist it
through `persist_intake_batch(...)`, **without breaking any existing
observation-only parser** and **without leaving any parser call site behind**.
This is the foundation of the build chain (WP02 depends on it) and it satisfies
the contract/protocol half of **FR-007**.

## Why this WP exists (read before coding)

Today the parser protocol is **observation-only**: `Parser.parse(self, path) ->
IngestBatch` (`src/premura/parsers/base.py:414-430`), and every call site treats
the return as an `IngestBatch`. `IntakeBatch` and `persist_intake_batch(...)`
exist (`parsers/base.py`, `store/profile_intake.py`) but **nothing connects a
parser to them** — `persist_intake_batch` is reachable only by hand-constructing
a batch in a test. So there is no intake parser path to run or to document.

**`IntakeBatch` also lacks a gap surface.** `IngestBatch` carries `unmapped_metrics`
/ `skipped_rows` so a parser can honestly declare fields it could not map;
`IntakeBatch` (`base.py:282`) carries **none**. WP02's reference parser and the
spec's "unmapped field surfaced as a gap" edge case both need it, so **this WP
adds an unmapped/skipped gap surface to `IntakeBatch`** — review metadata that
rides on the batch, exactly like `IngestBatch.unmapped_metrics`, never loadable
rows.

**The chosen approach is backward-compatible (decided at tasks time, delegated by
the plan's data-model).** Do **not** force-rewrite the five existing parsers.
Pick the *smallest* shape that lets a parser optionally carry intake while every
existing `parse() -> IngestBatch` parser keeps working unchanged. Two acceptable
shapes (pick one, justify in the contract):

- **Union return** — `parse()` may return `IngestBatch` *or* a small result
  object carrying observation and/or intake batches; the runtime normalizes a
  bare `IngestBatch` exactly as today.
- **Optional second method** — keep `parse() -> IngestBatch`; add an optional
  `parse_intake(path) -> IntakeBatch | None` the runtime calls when present.

Whichever you pick, the acceptance is the same: **existing parsers are
untouched and still load; an intake-emitting parser persists to the intake
tables.** This is the charter "smallest diff" gate — a breaking return-type
swap that rewrites five parsers is **not** the smallest viable shape.

## Context — every call site (do not miss one)

The single biggest risk (R1 / drift dimension D1) is updating `base.py` but
leaving a call site on the old path. There are **four** call sites plus the
session-log fixtures; the planning docs only named two. You own all of them:

- `src/premura/cli.py:113` — `batch = parser.parse(candidate)`
- `src/premura/harness/ingest_runner.py:85` — `batch = parser.parse(source)`
- `src/premura/harness/live_trial_ollama.py:296` — `batch = _Parser().parse(...)`
  (the live-trial harness — must keep working; recent live-trial spikes depend on it)
- `tests/fixtures/session_log/test_fixtures.py:73,92` — `GoodFitbitHrParser`/
  `DishonestFitbitHrParser` call `.parse()` and stay valid observation parsers.

Existing parsers that must remain untouched and green: `garmin_gdpr.py`,
`health_connect.py`, `sleep_as_android.py`, `bmt.py`, `lab_pdf.py`.

## Subtasks

### T001 — Smallest backward-compatible parser output shape (`parsers/base.py`)
- Implement the chosen shape (union return or optional `parse_intake`).
- Add a single runtime **normalize/dispatch helper** (e.g. `normalize_parse_output(...)`)
  that maps any parser output to `(observation_batch | None, intake_batch | None)`,
  so call sites do not each re-implement routing.
- A bare `IngestBatch` (today's parsers) normalizes to observation-only — no
  behavior change for them.
- **Add an unmapped/skipped gap surface to `IntakeBatch`** (e.g.
  `unmapped_metrics: list[str]` and `skipped_rows: list[SkippedRow]`, mirroring
  `IngestBatch`) so an intake parser can honestly declare fields it could not map.
  These are **review metadata carried on the batch, not loadable rows** —
  `persist_intake_batch` need not load them (same posture as
  `IngestBatch.unmapped_metrics`).
- Files: `src/premura/parsers/base.py`. Keep it typed (mypy clean).

### T002 — Reconcile the parser contract (`parsers/CONTRACT.md`)
- Document the now-**implemented** intake parser path and the runtime dispatch.
- **Fix the contradiction**: the runtime contract currently promises "existing
  observation-only parsers remain supported" while earlier prose implied
  replacing `parse() -> IngestBatch`. State plainly that observation-only parsers
  are unchanged and intake is additive.
- Keep the two-seam / one-home rule explicit: intake never becomes
  `Measurement`/`Interval`/`ClinicalNote` rows.
- Document the new `IntakeBatch` gap surface (`unmapped_metrics` / `skipped_rows`):
  intake parsers declare unmapped fields the same way observation parsers do.

### T003 — Route each output to its seam at every call site
- In `cli.py`, `harness/ingest_runner.py`, `harness/live_trial_ollama.py`: use the
  T001 helper to send observation output to the existing loader path and intake
  output to `persist_intake_batch(...)`.
- Observation-only inputs must behave exactly as before (same loader call, same
  result).

### T004 — Reconcile the session-log fixture parsers
- `tests/fixtures/session_log/test_fixtures.py` `GoodFitbitHrParser` /
  `DishonestFitbitHrParser` remain valid observation parsers under the new shape
  (they should need no change if the shape is backward-compatible — confirm and,
  if the union shape requires it, adapt minimally).

### T005 — Regression + dispatch test (`tests/test_intake_parser_runtime.py`)
- New test: a tiny in-test observation parser and a tiny in-test intake parser
  both dispatch to the correct seam; a "both" parser persists to both.
- Assert the **full existing parser suite and the live-trial seam stay green**
  (run `tests/test_parsers/`, `tests/test_live_trial_seam.py`,
  `tests/fixtures/session_log/test_fixtures.py`).

### T006 — Types, lint, no-network
- `ruff check`, `ruff format --check`, `mypy` clean on all owned files.
- Confirm no new network path is introduced (NFR-002).

## Branch Strategy

Plan/base branch **master**; final merge target **master**. The execution
worktree for this WP is allocated per its computed lane in `lanes.json` after
`finalize-tasks`. Implement with: `spec-kitty agent action implement WP01 --agent <name>`.

## Test Strategy (test-first)

Start from failing public-interface tests: write `test_intake_parser_runtime.py`
asserting (a) an intake parser persists intake rows via the runtime path, (b) an
observation parser is unchanged, before implementing T001/T003. Black-box only —
assert via parser outputs, the dispatch helper's result, and warehouse rows; do
not patch inside-boundary internals.

## Definition of Done

- [ ] An intake-emitting parser persists to the intake tables through the runtime path.
- [ ] `IntakeBatch` has an unmapped/skipped gap surface; an intake parser can declare a gap (unblocks WP02's honesty fixtures).
- [ ] All five existing parsers + the session-log fixtures + the live-trial seam are green, unchanged.
- [ ] All four call sites route through the T001 helper; none left on the old path.
- [ ] `CONTRACT.md` documents the implemented path and contains no "replace vs remain-supported" contradiction.
- [ ] ruff + ruff format + mypy + pytest green; no new network path.

## Risks

- **R1 / D1 — a missed call site.** Mitigation: T003 enumerates all four; T005
  asserts the live-trial seam green. A reviewer must grep `\.parse(` across
  `src/` and `tests/` and confirm each resolved call site is handled.
- **Over-large diff.** If you find yourself editing all five parsers, you picked
  the wrong (breaking) shape — stop and use a backward-compatible one.

## Reviewer Guidance

- Confirm the shape is backward-compatible (existing parsers diff-free).
- Re-grep every `.parse(` call site and verify routing; the live-trial harness is
  the easy one to forget.
- Verify the contract no longer contradicts itself.

## Activity Log

- 2026-06-04T12:38:02Z – claude:opus:python-implementer:implementer – shell_pid=5646 – Assigned agent via action command
- 2026-06-04T12:53:15Z – claude:opus:python-implementer:implementer – shell_pid=5646 – Ready for review: union ParseOutput + normalize_parse_output dispatch; all 4 call sites routed; IntakeBatch gap surface added; existing parsers + live-trial seam green
- 2026-06-04T12:53:50Z – claude:opus:python-reviewer:reviewer – shell_pid=19912 – Started review via action command
- 2026-06-04T12:56:47Z – claude:opus:python-reviewer:reviewer – shell_pid=19912 – Review passed: union ParseOutput + normalize_parse_output dispatch helper; all 4 .parse() call sites (cli, ingest_runner, live_trial_ollama, session-log fixtures) correctly routed — observation->loader, intake->persist_intake_batch, no dead path; 5 production parsers + fixtures untouched and green; IntakeBatch gap surface (unmapped_metrics/skipped_rows) added as non-loadable review metadata; CONTRACT.md reconciled (no replace-vs-supported contradiction); 41 tests pass; ruff+format+mypy clean on owned files; no new network path. Scope: IntakeBatch.validate loop-var rename is a needed mypy fix, ingest_runner envelope schema unchanged (conditional population only). Pre-existing test_bmi_dispatches_through_compute failure confirmed unrelated (engine/freshness path, not in diff).
