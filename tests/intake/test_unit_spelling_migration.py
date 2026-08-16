"""Migration-level verification for 010_unit_spelling_backfill.sql.

Vetting rule under test: a (stored, canonical) pair is only relabeled when
units.normalize_unit(stored) == canonical — spelling-equal, magnitude-identical.
Values are never rescaled; a magnitude-wrong pairing must be left untouched.
Synthetic rows only, no PHI.
"""

from __future__ import annotations

from pathlib import Path

from premura.store import duck
from premura.units import normalize_unit


def _seed_source(conn, source_id: str = "src_test") -> str:
    duck.upsert_dim_source(conn, source_id=source_id, source_kind="bmt")
    return source_id


def _insert_measurement(conn, *, metric_id: str, unit: str, value: float, dedupe_key: str) -> None:
    conn.execute(
        """
        INSERT INTO hp.fact_measurement
            (ts_utc, metric_id, value_num, unit, source_id, dedupe_key)
        VALUES (TIMESTAMP '2026-01-01 08:00:00', ?, ?, ?, 'src_test', ?)
        """,
        [metric_id, value, unit, dedupe_key],
    )


def _unit(conn, dedupe_key: str) -> tuple[str, float]:
    row = conn.execute(
        "SELECT unit, value_num FROM hp.fact_measurement WHERE dedupe_key = ?",
        [dedupe_key],
    ).fetchone()
    return row[0], row[1]


def _metric_for_canonical_unit(conn, canonical_unit: str) -> str:
    row = conn.execute(
        "SELECT metric_id FROM hp.dim_metric WHERE canonical_unit = ? LIMIT 1",
        [canonical_unit],
    ).fetchone()
    return row[0]


def test_spelling_variant_row_is_relabeled_value_unchanged(empty_warehouse) -> None:
    """u/l is a pure spelling variant of U_per_l (glucose-style lab metric)."""
    conn = empty_warehouse
    _seed_source(conn)
    canonical_unit = "U_per_l"
    metric_id = _metric_for_canonical_unit(conn, canonical_unit)
    assert normalize_unit("u/l") == canonical_unit

    _insert_measurement(conn, metric_id=metric_id, unit="u/l", value=42.0, dedupe_key="spell-1")

    # Re-run migrations (the loader is idempotent; re-applying 010 is the point).
    duck.run_migrations(conn)

    unit, value = _unit(conn, "spell-1")
    assert unit == canonical_unit
    assert value == 42.0


def test_magnitude_wrong_row_is_untouched(empty_warehouse) -> None:
    """mg/dl stored under a metric whose canonical_unit is mmol_per_l must NOT
    be relabeled — that is a real unit conversion, not a spelling variant, and
    this migration never rescales values."""
    conn = empty_warehouse
    _seed_source(conn)
    canonical_unit = "mmol_per_l"
    metric_id = _metric_for_canonical_unit(conn, canonical_unit)
    # Sanity: mg/dl is never a spelling-equivalent of mmol_per_l.
    assert normalize_unit("mg/dl") != canonical_unit

    _insert_measurement(
        conn, metric_id=metric_id, unit="mg/dl", value=90.0, dedupe_key="magwrong-1"
    )

    duck.run_migrations(conn)

    unit, value = _unit(conn, "magwrong-1")
    assert unit == "mg/dl", "magnitude-wrong row must be left untouched by the allowlist"
    assert value == 90.0


def test_migration_is_idempotent_on_double_run(empty_warehouse) -> None:
    conn = empty_warehouse
    _seed_source(conn)
    canonical_unit = "pct"
    metric_id = _metric_for_canonical_unit(conn, canonical_unit)
    assert normalize_unit("%") == canonical_unit

    _insert_measurement(conn, metric_id=metric_id, unit="%", value=5.5, dedupe_key="idem-1")

    duck.run_migrations(conn)
    unit_after_first, value_after_first = _unit(conn, "idem-1")
    assert unit_after_first == canonical_unit
    assert value_after_first == 5.5

    duck.run_migrations(conn)
    duck.run_migrations(conn)
    unit_after_more, value_after_more = _unit(conn, "idem-1")
    assert unit_after_more == canonical_unit
    assert value_after_more == 5.5


def test_migration_is_idempotent_through_fresh_initialize(tmp_path: Path) -> None:
    """The normal loader path (initialize) applies 010 once already; re-running
    run_migrations on top must not error or churn the table inventory."""
    db = tmp_path / "idem_fresh.duckdb"
    conn = duck.initialize(db)
    try:
        before = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'hp'"
        ).fetchall()
        duck.run_migrations(conn)
        duck.run_migrations(conn)
        after = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'hp'"
        ).fetchall()
        assert before == after
    finally:
        conn.close()
