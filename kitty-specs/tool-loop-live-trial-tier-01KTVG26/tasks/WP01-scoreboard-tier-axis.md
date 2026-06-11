---
work_package_id: WP01
title: Scoreboard tier axis
dependencies: []
requirement_refs:
- C-002
- FR-007
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history:
- date: '2026-06-11T14:19:42Z'
  action: created
  by: /spec-kitty.tasks
authoritative_surface: src/premura/harness/scoreboard.py
execution_mode: code_change
owned_files:
- src/premura/harness/scoreboard.py
- tests/test_scoreboard.py
tags: []
---

# WP01 — Scoreboard tier axis

## Objective

Add a back-compatible `tier` axis to the live-trial result records so a
tool-loop trial can be recorded **alongside — never overwriting —** the
one-shot floor results, comparable per operator model (spec FR-007, SC-002).
After this WP, `LiveTrialRunRecord` and `ScoreboardEntry` carry
`tier: str = "one_shot"`, every pre-existing scoreboard line still parses, and
the capability-floor view groups by `(operator_model, tier)`.

## Context you need

- Read first: `docs/shared/DOCTRINE.md` (two governing rules), then
  `kitty-specs/tool-loop-live-trial-tier-01KTVG26/spec.md` (FR-007, SC-002),
  `data-model.md` (exact field tables), and `contracts/tool-loop-tier.md` §5
  (the binding record shapes).
- The file you change: `src/premura/harness/scoreboard.py`. It is **pure
  storage** (no model logic) with two hard boundaries you must not weaken:
  real-data no-persist (`persist_run` returns `None`, writes nothing when
  `is_synthetic=False`) and append-only integrity (`append_scoreboard` only
  appends; `read_scoreboard` skips malformed lines with a warning).
- The one-shot writer (`live_trial_ollama.run_live_trial_ollama`) constructs
  `LiveTrialRunRecord(...)` and `ScoreboardEntry(...)` **without** a `tier`
  argument. You do not edit that file: the default value must make it write
  `"one_shot"` automatically. WP04 (a later package) will pass
  `tier="tool_loop"` explicitly.
- Charter gates: test-first (DIRECTIVE_034 — failing test precedes production
  code), black-box (DIRECTIVE_036 — assert on observable outputs: parsed
  entries, JSON lines, rendered table strings), smallest viable diff
  (DIRECTIVE_024).

## Subtasks

### T001 — Failing tests: tier round-trip + legacy-line parse

**Purpose**: define the contract before code (DIRECTIVE_034).

**Steps**:
1. Open `tests/test_scoreboard.py` (it exists — extend it; follow its current
   fixture style and imports).
2. Add failing tests, all through public interfaces only:
   - `ScoreboardEntry(..., tier="tool_loop").to_json_line()` produces a JSON
     object containing `"tier": "tool_loop"` (parse the line with `json.loads`
     and assert the key; do not string-match the whole line).
   - `ScoreboardEntry.from_json` on a dict **without** a `tier` key returns an
     entry with `tier == "one_shot"` (legacy-line rule — contract §5).
   - `ScoreboardEntry.from_json` round-trips `tier` when present.
   - Constructing `ScoreboardEntry(...)`/`LiveTrialRunRecord(...)` without
     `tier` yields `tier == "one_shot"` (this is what keeps the untouched
     one-shot writer correct).
   - `read_scoreboard` over a temp JSONL containing one legacy line (no
     `tier`) and one `tool_loop` line returns both entries with the right
     tiers (write the temp file via `path` kwarg; never touch `data/`).
3. Run `uv run pytest -q tests/test_scoreboard.py` — the new tests must FAIL
   (the field doesn't exist yet). Existing tests must still pass.

**Validation**: new tests red for the right reason (TypeError/KeyError on
`tier`), not collection errors.

### T002 — Add `tier` to `LiveTrialRunRecord` and `ScoreboardEntry`

**Purpose**: the data change (data-model.md tables are authoritative).

**Steps**:
1. `LiveTrialRunRecord`: add `tier: str = "one_shot"` after `run_kind`.
   Update the class docstring: `tier` is the comparison axis FR-007 introduces
   (`"one_shot"` = constrained floor; `"tool_loop"` = multiturn tool tier);
   `run_kind` stays `"live_trial"` for both because both ARE live trials.
2. `ScoreboardEntry`: add `tier: str = "one_shot"`.
   - `to_json_line`: include `"tier": self.tier` in the dict (it already uses
     `sort_keys=True` — keep that).
   - `from_json`: `tier=str(obj.get("tier", "one_shot"))`.
3. Note dataclass field-order rules: both classes use `slots=True` and have
   defaulted fields at the end already — keep `tier` with its default at the
   end to avoid breaking positional construction.

**Validation**: T001 tests go green. `uv run mypy src/premura/harness/scoreboard.py` clean.

### T003 — `current_floor` groups by `(operator_model, tier)`; CLI tier column

**Purpose**: SC-002 — the two tiers visible side by side, legacy rows intact.

**Steps**:
1. Change `current_floor` to key the floor dict by the `(operator_model,
   tier)` pair. Keep the return type JSON-friendly: key by a tuple is fine for
   the internal dict, but `_format_floor` renders it; alternatively key by the
   entry and carry `tier` inside the per-tier dict. Choose the smallest diff
   that keeps `_format_floor` simple and update both docstrings — document the
   grouping rule, not an enumerated tier list.
2. `_format_floor`: add a `tier` column between `operator_model` and `runs`.
   Sort rows by `(operator_model, tier)` for determinism.
3. Tests (add to `tests/test_scoreboard.py`, still black-box):
   - entries for the same model under both tiers yield two distinct floor
     rows;
   - a legacy entry (parsed from a tier-less line) lands under
     `(model, "one_shot")`;
   - the rendered table string contains both tier labels on separate lines.

**Validation**: floor tests green; rendering deterministic across runs.

### T004 — Back-compat verification: one-shot writer unchanged

**Purpose**: C-002 (one-shot floor untouched) and NFR-004 — prove it, don't
assume it.

**Steps**:
1. Add one test that constructs the record/entry exactly the way
   `live_trial_ollama.run_live_trial_ollama` does today (positionally/by
   keyword, no `tier` argument — mirror the call shape, do not import private
   helpers) and asserts the serialized line carries `"tier": "one_shot"`.
2. Run the full default suite: `uv run pytest -q`. Every pre-existing test —
   especially `tests/test_live_trial_ollama.py`, `tests/test_live_trial_seam.py`,
   `tests/test_live_trial_intake.py`, `tests/test_live_trial_edge_cases.py` —
   must pass with zero edits to those files. If any fails, your change is not
   back-compatible: fix `scoreboard.py`, never the callers.
3. Gates: `uv run ruff check src/premura/harness/scoreboard.py tests/test_scoreboard.py`,
   `uv run ruff format --check` on the same files, `uv run mypy` on the changed scope.

**Validation**: `uv run pytest -q` fully green; ruff + mypy clean.

## Definition of Done

- [ ] `tier` field on both record types, default `"one_shot"`, serialized and
      parsed per `contracts/tool-loop-tier.md` §5.
- [ ] A scoreboard line without `tier` parses as `one_shot`; the JSONL file is
      never rewritten (append-only behavior untouched).
- [ ] Floor view groups by `(operator_model, tier)`; CLI table renders the
      tier column.
- [ ] Zero edits outside `owned_files`; full default suite green; ruff +
      mypy clean.

## Risks / notes for the reviewer

- The grouping-key change in `current_floor` is the only behavior change a
  pre-existing consumer could notice (`_main` CLI output format). That is
  intended (SC-002); verify the table still renders legacy-only scoreboards
  sensibly (plan risk R3).
- Reviewer: check `to_json_line` keeps `sort_keys=True` and that no code path
  rewrites existing lines.
- Do NOT add a tier enum/whitelist — the tier is an open string axis (rule,
  not enumeration; DOCTRINE).
