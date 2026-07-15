"""Migration-level verification for 006_interval_unit.sql (m7 WP3).

Black-box stance mirrors test_trace_migration / test_profile_intake_migration:
the warehouse is always initialized through the public ``premura.store.duck``
path, never by feeding migration internals. The assertions target the storage
contract WP3 owns:

  * ``hp.fact_interval`` gains a nullable ``unit VARCHAR`` column;
  * the backfill sets ``unit`` from the owning ``dim_metric.canonical_unit`` for
    pre-existing interval rows whose ``unit`` is NULL (E3.2);
  * re-running the migrations leaves the column and the backfilled values stable
    and does not error (E3.1 idempotency).

The single source of unit truth is the metric registry (``dim_metric``), never a
parser-supplied string — these tests pin that invariant at the warehouse seam.
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


def _seed_source(conn: duckdb.DuckDBPyConnection, source_id: str, source_kind: str) -> None:
    conn.execute(
        """
        INSERT INTO hp.dim_source (source_id, source_kind, first_seen, last_seen)
        VALUES (?, ?, now(), now())
        """,
        [source_id, source_kind],
    )


def _insert_interval(
    conn: duckdb.DuckDBPyConnection,
    *,
    metric_id: str,
    source_id: str,
    dedupe_key: str,
    unit: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO hp.fact_interval
            (metric_id, start_utc, end_utc, source_id, dedupe_key, unit)
        VALUES (?, TIMESTAMP '2026-01-01 00:00:00', TIMESTAMP '2026-01-01 01:00:00', ?, ?, ?)
        """,
        [metric_id, source_id, dedupe_key, unit],
    )


def test_fact_interval_gains_unit_column(empty_warehouse) -> None:
    assert "unit" in _columns(empty_warehouse, "hp", "fact_interval")


def test_backfill_sets_unit_from_canonical_unit(empty_warehouse) -> None:
    """E3.2 — a pre-006 interval row with NULL unit is backfilled from the
    owning metric's canonical_unit when migrations run."""
    conn = empty_warehouse
    _seed_source(conn, "saa:dev", "sleep_as_android")
    # sleep_session canonical_unit is 'enum' in dim_metric.yaml.
    _insert_interval(
        conn, metric_id="sleep_session", source_id="saa:dev", dedupe_key="k1", unit=None
    )

    # Re-running migrations applies the idempotent backfill UPDATE.
    duck.run_migrations(conn)

    row = conn.execute("SELECT unit FROM hp.fact_interval WHERE dedupe_key = 'k1'").fetchone()
    assert row is not None
    assert row[0] == "enum"


def test_backfill_does_not_overwrite_existing_unit(empty_warehouse) -> None:
    """Backfill targets only NULL units; an already-populated value is stable."""
    conn = empty_warehouse
    _seed_source(conn, "saa:dev", "sleep_as_android")
    _insert_interval(
        conn, metric_id="sleep_session", source_id="saa:dev", dedupe_key="k2", unit="enum"
    )

    duck.run_migrations(conn)

    row = conn.execute("SELECT unit FROM hp.fact_interval WHERE dedupe_key = 'k2'").fetchone()
    assert row is not None
    assert row[0] == "enum"


def test_migration_is_idempotent(tmp_path: Path) -> None:
    """E3.1 — run_migrations twice on a warehouse that already has the column +
    backfilled rows: no error, values stable, no duplicate column."""
    db = tmp_path / "idem.duckdb"
    conn = duck.initialize(db)
    try:
        _seed_source(conn, "saa:dev", "sleep_as_android")
        _insert_interval(
            conn, metric_id="sleep_session", source_id="saa:dev", dedupe_key="k3", unit=None
        )
        duck.run_migrations(conn)
        first = conn.execute("SELECT unit FROM hp.fact_interval WHERE dedupe_key = 'k3'").fetchone()
        cols_before = _columns(conn, "hp", "fact_interval")

        # Second and third re-run must not error or churn.
        duck.run_migrations(conn)
        duck.run_migrations(conn)

        second = conn.execute(
            "SELECT unit FROM hp.fact_interval WHERE dedupe_key = 'k3'"
        ).fetchone()
        cols_after = _columns(conn, "hp", "fact_interval")
        assert first == second == ("enum",)
        assert cols_before == cols_after
    finally:
        conn.close()
