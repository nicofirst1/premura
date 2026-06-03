---
work_package_id: WP02
title: Kept run record + capability-floor scoreboard
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-011
- FR-012
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-06-03T12:45:00Z'
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
history:
- timestamp: '2026-06-03T12:45:00Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/scoreboard.py
execution_mode: code_change
owned_files:
- src/premura/harness/scoreboard.py
- tests/test_scoreboard.py
- .gitignore
tags: []
---

# WP02 — Kept run record + capability-floor scoreboard

## Objective

Build the durable local outputs of a live trial: a **per-run kept record**
(session log + verdict) and an **append-only capability-floor scoreboard** that
records, per operator model tier, the **first-attempt** and **final** verdicts
across runs over time. All artifacts live under a **git-ignored**
`data/live_trials/`. A run pointed at **real data persists nothing**.

## Why it matters

This is what turns one-off runs into a measurement that climbs over time
(issue #10's capability floor). FR-014's first-attempt-vs-final signal lives here
— it is the scoreboard's sharp job and the reason the scoreboard earns its scope.
The real-data no-persist guard is a hard PHI boundary (NFR-002 / C-001).

## Required reading

- `kitty-specs/cheap-operator-live-trial-01KT6PSA/contracts/scoreboard.md` and
  `data-model.md` (the `ScoreboardEntry`, `LiveTrialRunRecord` shapes).
- `src/premura/harness/grader.py` — the `Verdict` type you serialize (three rules,
  no ids/timestamps).
- `src/premura/session_log/store.py` — how the kept session-log DuckDB file is
  produced (the harness writes it; WP02 only *moves/keeps* the file, never writes
  log rows).
- Existing `.gitignore` (append, do not reorder).

## Subtasks

### T004 — Structures

**Purpose**: typed records (see `data-model.md`).

**Steps**: in `src/premura/harness/scoreboard.py`, define slots dataclasses:
- `LiveTrialRunRecord(operator_model, driver_model, attempts_used,
  first_attempt_verdict, final_verdict, run_kind="live_trial")` where verdicts are
  the slice-one `Verdict` dict.
- `ScoreboardEntry(ts, operator_model, driver_model, attempts_used,
  first_attempt_pass: bool, final_pass: bool)` with a `to_json_line()` /
  `from_json(obj)` pair. `*_pass` is `verdict["passed"]`.

### T005 — `persist_run()` (synthetic-only)

**Purpose**: keep the per-run artifacts, but ONLY for synthetic-fixture runs.

**Steps**:
1. `def persist_run(record, *, kept_session_log: Path, verdict: dict, is_synthetic: bool, runs_dir: Path = DATA_DIR) -> Path | None:`
2. If `not is_synthetic`: **return `None` and write nothing** (FR-012/NFR-002). No
   directory creation, no copy.
3. If synthetic: create `data/live_trials/<ts>-<model_slug>/`, copy/move the kept
   session-log DuckDB to `session_log.duckdb`, write `verdict.json`
   (`json.dumps(verdict, sort_keys=True)` — the verdict carries no ids/timestamps,
   so this stays stable). Return the run dir path.
4. `DATA_DIR = <repo>/data/live_trials` resolved relative to the package, matching
   the seam's existing data-dir convention.

**Edge cases**: model slug must be filesystem-safe (replace `:` `/`).

### T006 — Scoreboard append/read

**Purpose**: append-only JSONL with integrity (NFR-005).

**Steps**:
1. `def append_scoreboard(entry: ScoreboardEntry, *, path: Path = SCOREBOARD_PATH) -> None:`
   — open in append mode, write exactly one `entry.to_json_line() + "\n"`. Never
   rewrite existing lines. Create the parent dir + file if missing.
2. `def read_scoreboard(*, path = SCOREBOARD_PATH) -> list[ScoreboardEntry]:` —
   parse line by line; **skip a malformed line with a `logging.warning`**, never
   drop the rest or raise.
3. `SCOREBOARD_PATH = DATA_DIR / "scoreboard.jsonl"`.

### T007 — `current_floor()` + CLI

**Purpose**: answer "what is the current capability floor" (FR-011).

**Steps**:
1. `def current_floor(entries) -> dict[str, dict]:` group by `operator_model`,
   report `{runs, final_pass_runs, first_attempt_pass_runs, last_ts,
   reaches_final_pass: bool}`.
2. Add a module `__main__` (`if __name__ == "__main__":`) that reads the
   scoreboard and prints a compact per-tier floor table, so
   `uv run python -m premura.harness.scoreboard` works (quickstart.md).

### T008 — `.gitignore`

**Purpose**: never commit kept logs / verdicts / scoreboard (C-001).

**Steps**: append `data/live_trials/` to the repo-root `.gitignore` (one line;
keep existing entries intact).

### T009 — Unit test (default-collected)

**Purpose**: prove integrity + the no-persist guard without any model server.

**Steps**: in `tests/test_scoreboard.py` (use `tmp_path` for all paths):
1. **Append/order integrity**: append N entries → `read_scoreboard` returns N in
   order.
2. **Malformed line tolerated**: write a junk line between valid ones → read skips
   it, returns the valid ones, does not raise.
3. **Real-data no-persist**: `persist_run(..., is_synthetic=False)` returns `None`
   and creates **zero** files under `tmp_path`.
4. **Synthetic persist**: `is_synthetic=True` creates the run dir with
   `session_log.duckdb` + `verdict.json`.
5. **Floor query**: craft entries across two models with mixed first/final pass →
   assert `current_floor` reports the right `reaches_final_pass` and
   first-vs-final counts.

**Files**: `tests/test_scoreboard.py` (new).

## Definition of Done

- `scoreboard.py` provides `persist_run`, `append_scoreboard`, `read_scoreboard`,
  `current_floor`, and a working `__main__`.
- Real-data runs persist nothing; synthetic runs persist run dir + scoreboard line.
- `.gitignore` excludes `data/live_trials/`.
- `tests/test_scoreboard.py` passes in the default suite; `ruff`/`mypy` clean.

## Risks & reviewer guidance

- **Hard PHI boundary**: reviewer must confirm `persist_run(is_synthetic=False)`
  writes nothing (test 3) and that no function uploads/exports anything off-disk.
- **Append-only**: confirm `append_scoreboard` never truncates/rewrites; a crash
  mid-run must not corrupt prior lines.
- Keep this module free of any model/operator logic — it is pure storage.

## Branch strategy

Planning happened on `master`; this WP merges back into `master`. Execution
worktrees are allocated per computed lane from `lanes.json`.

Implement command: `spec-kitty agent action implement WP02 --agent <name>`
