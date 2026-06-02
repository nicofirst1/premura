"""Schema + dim_metric seed sanity."""

from __future__ import annotations


def test_schema_creates_expected_tables(empty_warehouse):
    rows = empty_warehouse.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'hp'
        ORDER BY table_name
        """
    ).fetchall()
    names = [r[0] for r in rows]
    assert names == [
        "dim_metric",
        "dim_source",
        "fact_clinical_note",
        "fact_interval",
        "fact_measurement",
        "ingest_run",
        "nutrition_intake_event",
        "nutrition_intake_item",
        "nutrition_quantity",
        "profile_capture_session",
        "profile_context_assertion",
        "supplement_dose",
        "supplement_intake_event",
        "supplement_item",
    ]


def test_dim_metric_seeded(empty_warehouse):
    n = empty_warehouse.execute("SELECT COUNT(*) FROM hp.dim_metric").fetchone()[0]
    assert n >= 30, f"expected >=30 metric rows, got {n}"
    for mid in ("hrv_rmssd_overnight", "body_battery", "stress", "resp_rate", "spo2"):
        row = empty_warehouse.execute(
            "SELECT canonical_unit FROM hp.dim_metric WHERE metric_id = ?", [mid]
        ).fetchone()
        assert row is not None, f"missing metric {mid}"


def test_seed_is_idempotent(empty_warehouse):
    from premura.store import duck

    before = empty_warehouse.execute("SELECT COUNT(*) FROM hp.dim_metric").fetchone()[0]
    duck.seed_dim_metric(empty_warehouse)
    after = empty_warehouse.execute("SELECT COUNT(*) FROM hp.dim_metric").fetchone()[0]
    assert before == after
