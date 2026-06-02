---
work_package_id: WP01
title: Session-log store (own file, schema, writers, config path)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-010
- FR-011
- FR-012
- FR-013
- FR-021
- FR-031
- FR-032
- FR-070
- FR-080
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-session-log-substrate-01KT45S1
base_commit: d0f8c4dde808db148b9649faff8a91bb7af2163d
created_at: '2026-06-02T13:11:44.945236+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
shell_pid: '4816'
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/session_log/
execution_mode: code_change
owned_files:
- src/premura/session_log/**
- src/premura/config.py
- tests/test_session_log_store.py
tags: []
---

# WP01 — Session-log store (own file, schema, writers, config path)

## Objective

Build the **session log's own local DuckDB file** and its **sole-writer** API.
This is the foundation everything else depends on. It adopts the OpenTelemetry
GenAI vocabulary/tree shape **by hand** (no OTel library, no server) in the same
idiom as `src/premura/trace.py`, but in its **own file** with its **own schema
bootstrap** — it must **not** touch the warehouse migration runner and must
**not** fold into the `trace.*` tables (ADR 0011, spec C-001/C-002, FR-070).

Read first: `kitty-specs/session-log-substrate-01KT45S1/data-model.md`,
`contracts/session-log-writer.md`, and ADR
`docs/building/adr/0011-session-log-otel-shape-no-library.md`.

## Context / grounding (existing code)

- `src/premura/trace.py` is **connection-agnostic**: callers pass an open
  `duckdb.DuckDBPyConnection`; the module never opens/closes it. Mirror that —
  but this WP owns its own `connect()` for the log file.
- `src/premura/store/duck.py:connect()` shows the connect idiom
  (`duckdb.connect(str(path), read_only=...)`, makes parent dir). `run_migrations`
  applies `CREATE ... IF NOT EXISTS` SQL — reuse the **idempotent-DDL idiom**, but
  apply our **own** `schema.sql`, not the warehouse migrations.
- `src/premura/config.py` exposes `warehouse_path` as a property off `duck_dir`.
  Add a sibling `session_log_path`.
- IDs: use `python-ulid` (already a dependency, used elsewhere) for `session_id` /
  `step_id`.

## Subtasks

### T001 — `session_log/schema.sql` (three tables, own file)

**Purpose**: Define the OTel-shaped tables in our own file. Idempotent DDL.

**Steps**:
1. Create `src/premura/session_log/schema.sql` with three tables exactly per
   `data-model.md`:
   - `log_session(session_id PK, started_at, finished_at, operator_model,
     driver_model, premura_version, isolation_tag, run_kind)`
   - `log_step(step_id PK, session_id, parent_step_id, kind, name, tool_name,
     request_summary, request_hash, result_status, result_summary, result_hash,
     started_at, finished_at)`
   - `log_ingest_provenance(step_id, batch_id, parser_kind, rows_inserted,
     rows_skipped_dup, rows_skipped_priority, declared_metrics_json,
     emitted_metric_ids_json, unmapped_metrics_json, skipped_rows_json,
     contract_pass BOOLEAN)`
2. Use `CREATE TABLE IF NOT EXISTS`. Do **not** put these in a `trace` schema or
   the warehouse; this is a standalone file. (A bare/default schema is fine.)

**Validation**: file loads via `conn.execute(schema_sql)` twice without error
(idempotent).

### T002 — `connect()` + `init_schema()`

**Purpose**: Open the log file and apply the schema idempotently.

**Steps**:
1. `src/premura/session_log/store.py`:
   ```python
   def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection
   def init_schema(conn: duckdb.DuckDBPyConnection) -> None
   ```
2. `connect` makes the parent dir and opens DuckDB (mirror `store/duck.py:connect`).
3. `init_schema` reads `schema.sql` (via `importlib.resources`) and executes it.

**Validation**: `init_schema` run twice on the same conn is a no-op (idempotent).

### T003 — session/step writers

**Purpose**: The recording API the harness calls (sole writer).

**Steps**: implement, per `contracts/session-log-writer.md`:
- `open_session(conn, *, operator_model, driver_model, premura_version,
  isolation_tag, run_kind) -> str` — insert one `log_session`, return `session_id`.
- `record_step(conn, *, session_id, parent_step_id, kind, name, tool_name,
  request_summary, request_hash, result_status, result_summary, result_hash) ->
  str` — insert one `log_step`, return `step_id`.
- `finish_session(conn, *, session_id) -> None` — set `finished_at`.
- Validate enums at the boundary (runtime input validation lives at this seam,
  per charter): `result_status` ∈ {available, missing, stale, insufficient,
  refused, error} (FR-003); `run_kind` ∈ {repeatable_check, live_trial} (FR-032);
  `kind` ∈ {agent_turn, model_call, tool_call}. Raise `ValueError` otherwise.
- Timestamps via DuckDB `now()` or a passed-in value; they are **not** consumed by
  the grader, so a plain wall-clock is fine here.

**Validation**: inserting then `SELECT`-ing returns the exact field values; bad
enum raises `ValueError`.

### T004 — `record_ingest_provenance` writer (two-origin + grader-only contract_pass)

**Purpose**: Persist ingest provenance with the source-of-truth split intact.

**Steps**:
1. Implement `record_ingest_provenance(conn, *, step_id, batch_id, parser_kind,
   load_stats, declared_metrics, emitted_metric_ids, unmapped_metrics,
   skipped_rows, contract_pass) -> None`.
2. Persist loader-measured ints (`rows_inserted`, `rows_skipped_dup`,
   `rows_skipped_priority`) as columns; persist the four list fields as JSON
   strings (`*_json`).
3. `contract_pass` is a parameter the **grader** supplies — document in the
   docstring that it is the grader's recomputed result, **never** a parser/runner
   self-report (FR-061/FR-065). This WP only persists it.

**Validation**: round-trip JSON fields; assert columns vs JSON are distinct and
readable back.

### T005 — `config.session_log_path`

**Purpose**: A configurable default path for real runs (sandboxes override it).

**Steps**: in `src/premura/config.py`, add a `session_log_path` property
returning `self.duck_dir / "session_log.duckdb"` (sibling of `warehouse_path`).
Keep the change additive; do not alter `warehouse_path` or other settings.

**Validation**: `settings.session_log_path` resolves; default suite still green.

### T006 — store tests

**Purpose**: Black-box proof through the public writer API (DIRECTIVE_036).

**Steps** — `tests/test_session_log_store.py` (test-first; write these before the
code they motivate, per DIRECTIVE_034):
- `test_session_and_steps_round_trip`: open file at `tmp_path`, init schema,
  `open_session`, `record_step` (a parent `agent_turn` + child `tool_call`
  `ingest_run`), `finish_session`; query the file and assert exact rows + the
  parent/child tree.
- `test_ingest_provenance_round_trip`: `record_ingest_provenance` then assert
  loader ints and the `*_json` fields decode to the inputs; assert `contract_pass`
  stored as given.
- `test_result_status_vocab` / `test_run_kind_vocab`: bad values raise `ValueError`.
- `test_single_writer`: document/enforce that only one writable connection is
  opened by the caller; assert the API never opens a second handle to the file
  (NFR-008). (Black-box: open one writable conn, do all writes through it.)

## Definition of Done

- [ ] `src/premura/session_log/{__init__.py,schema.sql,store.py}` exist; schema is
      its own file (not a warehouse migration, not `trace.*`).
- [ ] All six subtasks complete; `tests/test_session_log_store.py` green.
- [ ] `config.session_log_path` added (additive only).
- [ ] No new third-party dependency (NFR-003) — only stdlib + existing deps.
- [ ] `uv run ruff check src/premura/session_log tests/test_session_log_store.py`,
      `ruff format --check`, `uv run mypy src/premura/session_log`,
      `uv run pytest -q tests/test_session_log_store.py` all green.

## Risks / reviewer guidance

- **Do not** route this through `store/duck.run_migrations` or add a `006_*.sql`
  warehouse migration — that reintroduces the contention the separate file exists
  to remove (R-review point).
- Confirm `contract_pass` has no value source inside this WP other than the
  caller's parameter (it must remain the grader's output).
- Reviewer: assert the tests read **the file** (DuckDB rows), not internal call
  spies.

## Implementation command

```bash
spec-kitty agent action implement WP01 --agent <name>
```
