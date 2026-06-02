# Contract: session-log writer (`premura.session_log.store`)

The session log's own file + the **sole** writer surface. Connection-agnostic in
the same spirit as `premura.trace` (caller owns the conn), but it owns its own
**file** and **schema bootstrap** — it does NOT use the warehouse migration
runner (D1).

## Connection + schema

```python
def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection
def init_schema(conn: duckdb.DuckDBPyConnection) -> None   # idempotent CREATE IF NOT EXISTS
```

- `init_schema` applies `schema.sql` (the three tables, D1/data-model). Idempotent.
- The harness opens **one** writable connection for the run and is the **sole
  writer** (FR-021). The subprocess runner never opens this file.

## Writer functions

```python
def open_session(
    conn, *, operator_model: str, driver_model: str,
    premura_version: str, isolation_tag: str, run_kind: str,
) -> str: ...                                  # returns session_id

def record_step(
    conn, *, session_id: str, parent_step_id: str | None,
    kind: str, name: str, tool_name: str | None,
    request_summary: str | None, request_hash: str | None,
    result_status: str, result_summary: str | None, result_hash: str | None,
) -> str: ...                                  # returns step_id

def record_ingest_provenance(
    conn, *, step_id: str, batch_id: str, parser_kind: str,
    load_stats: LoadStatsLike,                 # rows_inserted / _dup / _priority
    declared_metrics: list[str], emitted_metric_ids: list[str],
    unmapped_metrics: list[str], skipped_rows: list[dict],
    contract_pass: bool,                       # GRADER output only (FR-065)
) -> None: ...

def finish_session(conn, *, session_id: str) -> None: ...
```

## Invariants

- `result_status` ∈ {`available`,`missing`,`stale`,`insufficient`,`refused`,`error`}.
- `run_kind` ∈ {`repeatable_check`,`live_trial`}.
- `record_ingest_provenance.contract_pass` is set **only** by the grader's
  recomputation, never by the parser/runner (FR-061/FR-065).
- No code path syncs/exports the file (NFR-004). PHI-safe summaries only.

## Black-box test obligations

- After a recorded run, a query against the session-log file returns exactly the
  expected `log_session`/`log_step`/`log_ingest_provenance` rows (assert on
  DuckDB row counts/values, not on internal calls).
- Two writers cannot open the file at once (single-writer); the runner subprocess
  has no handle to it.
