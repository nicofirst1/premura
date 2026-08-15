"""Migration-level verification for 009_ingest_skip.sql (m8 WP04).

Black-box stance mirrors test_interval_unit_migration.py: the warehouse is
always initialized through the public ``premura.store.duck`` path. Assertions
target the storage contract WP04 owns: ``hp.ingest_skip`` exists with the
documented columns, and re-running migrations is idempotent (no dupes, no
errors).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from premura.store import duck


def _columns(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, table],
    ).fetchall()
    return {r[0] for r in rows}


def test_ingest_skip_table_exists(empty_warehouse) -> None:
    columns = _columns(empty_warehouse, "hp", "ingest_skip")
    assert columns == {
        "skip_id",
        "batch_id",
        "kind",
        "raw_field",
        "metric_id",
        "from_unit",
        "to_unit",
        "reason",
        "recorded_at",
    }


def test_migration_is_idempotent(tmp_path: Path) -> None:
    """Running migrations twice on a warehouse that already has the table
    (with a row in it) must not error or duplicate the row."""
    db = tmp_path / "idem.duckdb"
    conn = duck.initialize(db)
    try:
        conn.execute(
            """
            INSERT INTO hp.ingest_run (batch_id, source_kind, source_path, source_sha256)
            VALUES ('run1', 'bmt', '/tmp/x.csv', 'deadbeef')
            """
        )
        conn.execute(
            """
            INSERT INTO hp.ingest_skip (skip_id, batch_id, kind, reason)
            VALUES ('skip1', 'run1', 'parser_skip', 'no home for this field')
            """
        )
        cols_before = _columns(conn, "hp", "ingest_skip")

        duck.run_migrations(conn)
        duck.run_migrations(conn)

        cols_after = _columns(conn, "hp", "ingest_skip")
        assert cols_before == cols_after
        rows = conn.execute("SELECT COUNT(*) FROM hp.ingest_skip").fetchone()
        assert rows == (1,)
    finally:
        conn.close()
