"""Migration-level verification for 005_trace_audit.sql (WP01).

Black-box stance: the warehouse is always initialized through the public
``premura.store.duck`` initialization path (``initialize`` / ``run_migrations``),
never by feeding raw SQL fragments or importing migration internals. The
assertions target the storage-shape contract WP01 owns:

  * the dedicated ``trace`` schema and its tables exist after init,
  * the pre-existing ``hp.*`` fact/note tables survive untouched (the trace
    migration replaces nothing in ``hp.*``),
  * the migration re-runs idempotently through the normal loader,
  * schema-ownership boundary: the trace migration creates NO new ``hp.*``
    provenance table (FR-007 / NFR-002 boundary guardrail),
  * append-only shaping: stable primary keys, no mutable aggregate/disclosure
    cache table, and result/mark rows attach to immutable call ids.

WP01 does not implement the Python trace service or MCP tools (WP02/WP03), so
these tests exercise the schema directly, not a public write API.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from premura.store import duck

# Tables this migration is responsible for creating, under the trace schema.
TRACE_TABLES = {
    "research_session",
    "tool_call",
    "tool_result",
    "surfaced_mark",
}

# Pre-existing hp.* homes that must NOT be disturbed or replaced by this WP.
EXISTING_HP_TABLES = {
    "dim_metric",
    "dim_source",
    "fact_measurement",
    "fact_interval",
    "fact_clinical_note",
}


def _schema_tables(conn: duckdb.DuckDBPyConnection, schema: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = ?
        """,
        [schema],
    ).fetchall()
    return {r[0] for r in rows}


def _schemas(conn: duckdb.DuckDBPyConnection) -> set[str]:
    rows = conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
    return {r[0] for r in rows}


def _pk_columns(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT constraint_column_names
        FROM duckdb_constraints()
        WHERE schema_name = ? AND table_name = ? AND constraint_type = 'PRIMARY KEY'
        """,
        [schema, table],
    ).fetchall()
    cols: list[str] = []
    for (names,) in rows:
        cols.extend(names)
    return cols


# --------------------------------------------------------------------------- #
# T002 — the trace schema/tables exist via the public init path; hp.* survives.
# --------------------------------------------------------------------------- #
def test_trace_schema_exists_after_initialize(empty_warehouse) -> None:
    assert "trace" in _schemas(empty_warehouse), "trace schema was not created"


def test_trace_tables_exist_after_initialize(empty_warehouse) -> None:
    present = _schema_tables(empty_warehouse, "trace")
    missing = TRACE_TABLES - present
    assert not missing, f"migration did not create expected trace tables: {sorted(missing)}"


def test_existing_hp_tables_survive(empty_warehouse) -> None:
    present = _schema_tables(empty_warehouse, "hp")
    missing = EXISTING_HP_TABLES - present
    assert not missing, f"existing hp.* tables were lost/replaced: {sorted(missing)}"


def test_migration_is_idempotent_through_the_normal_loader(tmp_path: Path) -> None:
    """Re-running run_migrations on an initialized warehouse must not error and
    must not change the table inventory (no duplicated schema objects)."""
    db = tmp_path / "idem.duckdb"
    conn = duck.initialize(db)
    try:
        before_trace = _schema_tables(conn, "trace")
        before_hp = _schema_tables(conn, "hp")
        # Normal loader path, run a second (and third) time.
        duck.run_migrations(conn)
        duck.run_migrations(conn)
        after_trace = _schema_tables(conn, "trace")
        after_hp = _schema_tables(conn, "hp")
        assert before_trace == after_trace
        assert before_hp == after_hp
        assert TRACE_TABLES.issubset(after_trace)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# T003 — schema-ownership guardrail: trace provenance never lands in hp.*.
# --------------------------------------------------------------------------- #
def test_trace_migration_adds_no_new_hp_provenance_tables(empty_warehouse) -> None:
    """The trace migration must not create any new table under hp.*.

    `trace.*` contains tool-use provenance; `hp.*` contains health facts. This
    migration must not add trace/provenance tables to hp.* (FR-007 / NFR-002
    boundary). After init, every hp.* table must be one of the known
    health-fact homes from migrations 001-004 — nothing trace-shaped sneaks in.
    """
    hp_tables = _schema_tables(empty_warehouse, "hp")
    # Known hp.* homes created by migrations 001 (init), 002 (ontology cols on
    # dim_metric, no new table), 003 (clinical notes), 004 (profile + intake),
    # 007 (condition episodes — a health-fact home, not provenance).
    known_hp = EXISTING_HP_TABLES | {
        "ingest_run",
        "profile_capture_session",
        "profile_context_assertion",
        "nutrition_intake_event",
        "nutrition_intake_item",
        "nutrition_quantity",
        "supplement_intake_event",
        "supplement_item",
        "supplement_dose",
        "condition_episode",
    }
    unexpected = hp_tables - known_hp
    assert not unexpected, (
        "trace migration introduced unexpected hp.* table(s) — provenance must "
        f"live under trace.*, not hp.*: {sorted(unexpected)}"
    )
    # And no trace-named table leaked into hp.*.
    assert TRACE_TABLES.isdisjoint(hp_tables), (
        "a trace table was created under hp.* instead of trace.*"
    )


def test_trace_tables_are_only_under_trace_schema(empty_warehouse) -> None:
    """The four trace tables exist under `trace`, and nowhere under `hp`."""
    trace_tables = _schema_tables(empty_warehouse, "trace")
    assert TRACE_TABLES.issubset(trace_tables)
    hp_tables = _schema_tables(empty_warehouse, "hp")
    assert TRACE_TABLES.isdisjoint(hp_tables)


# --------------------------------------------------------------------------- #
# T004 — append-only shaping at the storage boundary.
# --------------------------------------------------------------------------- #
def test_every_trace_table_has_a_stable_primary_key(empty_warehouse) -> None:
    """Stable PKs prevent accidental duplicate rows for the same identity."""
    expected_pk = {
        "research_session": "session_id",
        "tool_call": "call_id",
        "tool_result": "result_id",
        "surfaced_mark": "mark_id",
    }
    for table, pk in expected_pk.items():
        cols = _pk_columns(empty_warehouse, "trace", table)
        assert cols == [pk], f"trace.{table} primary key is {cols}, expected [{pk!r}]"


def test_no_mutable_aggregate_or_disclosure_cache_table(empty_warehouse) -> None:
    """Disclosure (N/K counts) must stay a derived query, not a stored cache.

    A persisted aggregate table would be a second source of truth that can drift
    from the canonical call/result/mark rows. WP01 must not ship one.
    """
    trace_tables = _schema_tables(empty_warehouse, "trace")
    cache_like = {
        t
        for t in trace_tables
        if any(tok in t for tok in ("disclosure", "aggregate", "count", "summary_cache", "cache"))
    }
    assert not cache_like, (
        "trace schema contains a mutable aggregate/disclosure-cache-like table; "
        f"disclosure must be derived: {sorted(cache_like)}"
    )
    # Exactly the four canonical append-only tables, nothing more.
    assert trace_tables == TRACE_TABLES, (
        f"unexpected extra trace table(s): {sorted(trace_tables - TRACE_TABLES)}"
    )


def test_results_and_marks_link_to_immutable_call_ids(empty_warehouse) -> None:
    """Result and mark rows append against an immutable call_id rather than
    updating a call payload blob — proves the append-only attachment shape."""
    conn = empty_warehouse
    conn.execute(
        "INSERT INTO trace.research_session (session_id, started_at_utc) "
        "VALUES ('sess-1', TIMESTAMP '2026-01-01 10:00:00')"
    )
    conn.execute(
        """
        INSERT INTO trace.tool_call
            (call_id, session_id, tool_name, hypothesis_identity,
             started_at_utc, finished_at_utc, terminal_status)
        VALUES ('call-1', 'sess-1', 'change_point',
                '{"metric_id":"hr","min_side_observations":5}',
                TIMESTAMP '2026-01-01 10:00:01', TIMESTAMP '2026-01-01 10:00:02',
                'available')
        """
    )
    # A result references the immutable call id.
    conn.execute(
        "INSERT INTO trace.tool_result (result_id, call_id, result_hash, created_at_utc) "
        "VALUES ('res-1', 'call-1', 'abc123', TIMESTAMP '2026-01-01 10:00:02')"
    )
    # A surfaced mark also references the immutable call id (own row, not an
    # update to the call).
    conn.execute(
        "INSERT INTO trace.surfaced_mark "
        "(mark_id, session_id, call_id, role, rationale, marked_at_utc) "
        "VALUES ('mark-1', 'sess-1', 'call-1', 'claim', 'used in answer', "
        "TIMESTAMP '2026-01-01 10:05:00')"
    )

    joined = conn.execute(
        """
        SELECT c.call_id, r.result_hash, m.role
        FROM trace.tool_call c
        JOIN trace.tool_result r ON r.call_id = c.call_id
        JOIN trace.surfaced_mark m ON m.call_id = c.call_id
        """
    ).fetchall()
    assert joined == [("call-1", "abc123", "claim")]

    # FKs keep results/marks attached to a recorded call: a dangling call_id is
    # rejected.
    with pytest.raises(duckdb.ConstraintException):
        conn.execute(
            "INSERT INTO trace.tool_result (result_id, call_id, created_at_utc) "
            "VALUES ('res-x', 'no-such-call', TIMESTAMP '2026-01-01 10:00:02')"
        )


def test_duplicate_call_id_is_rejected(empty_warehouse) -> None:
    """Stable PK blocks a duplicate call row for the same identity."""
    conn = empty_warehouse
    conn.execute(
        "INSERT INTO trace.research_session (session_id, started_at_utc) "
        "VALUES ('sess-2', TIMESTAMP '2026-01-01 10:00:00')"
    )
    conn.execute(
        "INSERT INTO trace.tool_call (call_id, session_id, tool_name, started_at_utc) "
        "VALUES ('dup-call', 'sess-2', 'correlate', TIMESTAMP '2026-01-01 10:00:01')"
    )
    with pytest.raises(duckdb.ConstraintException):
        conn.execute(
            "INSERT INTO trace.tool_call (call_id, session_id, tool_name, started_at_utc) "
            "VALUES ('dup-call', 'sess-2', 'correlate', TIMESTAMP '2026-01-01 10:00:09')"
        )
