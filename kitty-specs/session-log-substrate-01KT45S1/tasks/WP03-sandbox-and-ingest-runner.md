---
work_package_id: WP03
title: Sandbox + ingest runner
dependencies:
- WP01
requirement_refs:
- FR-020
- FR-021
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/
execution_mode: code_change
owned_files:
- src/premura/harness/__init__.py
- src/premura/harness/sandbox.py
- src/premura/harness/ingest_runner.py
- tests/test_sandbox.py
tags: []
---

# WP03 — Sandbox + ingest runner

## Objective

Build the **throwaway sandbox** (a full temp copy of the tracked repo tree, with
the warehouse and the session-log paths redirected to temp files) and the
**in-sandbox ingest runner** that executes one parser-build ingest **as a
subprocess** and emits a structured **JSON outcome envelope** on stdout. The
runner must **not** write the session log — it *returns* its outcome; the parent
harness (WP06/WP07) is the sole log writer (FR-021). This is the isolation
mechanism that lets an agent edit parser files without polluting the real repo
(FR-020) and that the live trial reuses.

Read first: `research.md` (D2), `contracts/ingest-outcome-envelope.schema.json`,
`data-model.md` (envelope), `src/premura/store/{duck.py,loader.py}`,
`src/premura/parsers/base.py`.

## Context / grounding

- The parser-build flow has an agent write parser modules into
  `src/premura/parsers/` and append to `dim_metric.yaml`. The sandbox must cover
  **source edits**, so it copies the tree (not just data files).
- Determinism (NFR-002): build the copy from **`git ls-files`** (tracked paths
  only) so the input is reproducible from a clean clone; exclude `.git`, `.venv`,
  `data/`, `kitty-specs/`, `.worktrees/` (none should appear in `ls-files` except
  `kitty-specs/`, so filter it).
- The subprocess gets its **own DuckDB handles** → no concurrency dance with the
  parent (this is why a subprocess, not in-process import of a 2nd package copy).
- `loader.load(conn, batch) -> LoadStats`; `validate_batch_against_warehouse`
  raises on missing `dim_metric`; `duck.initialize(path)` bootstraps a warehouse.

## Subtasks

### T010 — `sandbox.py` build temp copy + redirected paths

**Steps** — `src/premura/harness/sandbox.py`:
- A `Sandbox` dataclass/context-manager exposing: `root: Path` (the temp copy),
  `warehouse_path: Path` (temp), `session_log_path: Path` (temp),
  `isolation_tag: str`, `premura_version: str`.
- `build_sandbox(repo_root: Path) -> Sandbox`:
  - Resolve tracked files via `git -C <repo_root> ls-files` (subprocess);
    **filter out** `kitty-specs/` and anything under `.worktrees/`.
  - Copy each tracked file into a fresh `tmp_path`-style temp dir (use
    `tempfile.mkdtemp`), preserving relative structure.
  - Set `warehouse_path = root/"data/warehouse.duckdb"` and
    `session_log_path = root/"data/session_log.duckdb"` (temp; created on use).
  - Generate a unique `isolation_tag` (ulid). `premura_version` from the package
    metadata.

**Validation**: the copied tree contains `src/premura/...` but **not** `.git`,
`.venv`, `kitty-specs/`.

### T011 — teardown + `install_parser` helper

**Steps**:
- `Sandbox.teardown()` (and `__exit__`) recursively removes the temp dir; assert
  nothing under it persists (NFR-004 — no real data left behind).
- `install_parser(sandbox, parser_src: Path, dest_relpath: str) -> Path`: copy a
  reference parser module from `tests/fixtures/session_log/parsers/...` into the
  sandbox tree under `src/premura/parsers/<...>` (modelling the agent's file
  edit). Return the installed path. (For dim_metric: `heart_rate` already exists,
  so slice-one reference parsers need no dim_metric append; if a parser declares a
  new metric, document that the agent would also append to the sandbox's
  `dim_metric.yaml` — out of scope for the committed reference parsers.)

**Validation**: after `install_parser`, the module exists in the sandbox tree and
is importable **within a subprocess rooted at the sandbox** (not in the parent
process).

### T012 — `ingest_runner.py` subprocess → envelope

**Steps** — `src/premura/harness/ingest_runner.py`:
- A module runnable as `python -m premura.harness.ingest_runner` **inside the
  sandbox** (the parent invokes it via subprocess with `cwd=sandbox.root` and the
  sandbox's `src` on `PYTHONPATH`, and `--warehouse <sandbox.warehouse_path>`).
- CLI args: `--source <fixture.csv> --parser <import.path:ClassOrFactory>
  --warehouse <path>`.
- Behavior: initialize the temp warehouse (`duck.initialize`); import + run the
  named parser → `IngestBatch`; `validate_batch_against_warehouse`; `load` →
  `LoadStats`; collect `emitted_metric_ids` from the batch rows.
- Emit on stdout **exactly** the JSON envelope in
  `contracts/ingest-outcome-envelope.schema.json` — `status` ok/error,
  `parser_kind`, `batch_id`, `load_stats`, `declared_metrics`,
  `emitted_metric_ids`, `unmapped_metrics`, `skipped_rows`. On any raise: `status:
  "error"` + `error:{kind,message}` and a zeroed/empty payload, exit non-zero.
- **Never** open or write the session log (single-writer rule).

**Validation**: the printed JSON validates against the envelope schema for both
the good and a deliberately-raising parser.

### T013 — tests

**Steps** — `tests/test_sandbox.py` (test-first):
- `test_sandbox_contains_only_tracked_tree`: build a sandbox of the real repo;
  assert `src/premura/__init__.py` present, `.git`/`kitty-specs` absent.
- `test_teardown_removes_everything`: path gone after teardown.
- `test_runner_emits_valid_envelope_good`: install `good_fitbit_hr`, run the
  runner subprocess against the synthetic CSV, parse stdout, validate against the
  envelope schema, assert `status=="ok"`, `rows_inserted>0`, `declared_metrics`
  and `emitted_metric_ids` both `["heart_rate"]`.
- `test_runner_envelope_on_error`: a parser that raises → `status=="error"`,
  non-zero exit, schema-valid envelope.
- `test_runner_does_not_write_session_log`: assert no session-log file is created
  by the subprocess (only the parent writes it).

(Use the WP04 fixtures; this WP depends on WP01 for `config.session_log_path` and
the sandbox path wiring. If WP04 lands in parallel, gate these tests on the
fixtures existing.)

## Definition of Done

- [ ] `Sandbox` builds from tracked files only, redirects warehouse + session-log
      paths, and tears down cleanly.
- [ ] `ingest_runner` emits a schema-valid envelope for ok and error paths and
      never writes the log.
- [ ] `tests/test_sandbox.py` green.
- [ ] `ruff` (check+format), `mypy src/premura/harness`, `pytest -q
      tests/test_sandbox.py` green.

## Risks / reviewer guidance

- **R2 (plan)**: copy only tracked paths; reviewer confirms `.venv`/`data/` never
  copied (perf + cleanliness).
- Reviewer: confirm the runner truly runs as a **subprocess against the sandbox
  copy** (own DuckDB handles), not by importing the parent's already-loaded
  `premura` package.
- Confirm single-writer: grep the runner for any session-log import/open — there
  must be none.

## Implementation command

```bash
spec-kitty agent action implement WP03 --agent <name>
```
