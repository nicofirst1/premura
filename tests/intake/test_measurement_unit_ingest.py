"""Load-boundary unit enforcement for measurements (m8 WP02).

Structural mirror of test_interval_unit_ingest.py: after a real
`loader.load()`, every persisted fact_measurement row's unit must equal its
metric's canonical_unit, with the VALUE rescaled to match (never merely
relabeled). A row whose observed unit has no registered conversion rule is
refused row-level, not batch-level.
"""

from __future__ import annotations

from datetime import datetime

from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor
from premura.store.loader import load


def _batch(measurements: list[Measurement], path) -> IngestBatch:
    path.write_text("dummy")
    descriptors = {
        m.source_id: SourceDescriptor(source_id=m.source_id, source_kind=m.source_kind)
        for m in measurements
    }
    batch = IngestBatch(
        source_kind=measurements[0].source_kind,
        declared_metrics=sorted({m.metric_id for m in measurements}),
        measurements=measurements,
        source_descriptors=descriptors,
    ).attach_source_artifact(path)
    batch.validate()
    return batch


def test_ingested_measurement_carries_canonical_unit(empty_warehouse, tmp_path):
    # weight's canonical_unit is kg; observed lb must be converted, not relabeled.
    m = Measurement(
        ts_utc=datetime(2026, 4, 1, 8, 0, 0),
        metric_id="weight",
        unit="lb",
        source_id="bmt:manual",
        source_kind="bmt",
        value_num=154.0,
        source_uuid="bmt:weight:1",
    )

    stats = load(empty_warehouse, _batch([m], tmp_path / "lb.bin"))

    assert stats.rows_inserted == 1
    assert stats.rows_skipped_unit == 0
    rows = empty_warehouse.execute(
        """
        SELECT fm.unit, dm.canonical_unit, fm.value_num
        FROM hp.fact_measurement fm
        JOIN hp.dim_metric dm ON dm.metric_id = fm.metric_id
        """
    ).fetchall()
    assert rows, "expected at least one ingested measurement row"
    for got_unit, canonical_unit, _value_num in rows:
        assert got_unit == canonical_unit

    got_unit, canonical_unit, value_num = rows[0]
    assert got_unit == "kg"
    # 154 lb -> ~69.85 kg (converted, not the raw 154 relabeled as kg).
    assert value_num == 154.0 * 0.45359237


def test_unrecognized_unit_refuses_row_not_batch(empty_warehouse, tmp_path):
    good = Measurement(
        ts_utc=datetime(2026, 4, 1, 8, 0, 0),
        metric_id="weight",
        unit="kg",
        source_id="bmt:manual",
        source_kind="bmt",
        value_num=70.0,
        source_uuid="bmt:weight:good",
    )
    bad = Measurement(
        ts_utc=datetime(2026, 4, 1, 9, 0, 0),
        metric_id="heart_rate",
        unit="furlongs_per_fortnight",
        source_id="bmt:manual",
        source_kind="bmt",
        value_num=72.0,
        source_uuid="bmt:hr:bad",
    )

    stats = load(empty_warehouse, _batch([good, bad], tmp_path / "mixed.bin"))

    assert stats.rows_skipped_unit == 1
    assert stats.rows_inserted == 1

    n = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    assert n == 1
    surviving = empty_warehouse.execute(
        "SELECT source_uuid, unit, value_num FROM hp.fact_measurement"
    ).fetchone()
    assert surviving == ("bmt:weight:good", "kg", 70.0)

    absent = empty_warehouse.execute(
        "SELECT 1 FROM hp.fact_measurement WHERE source_uuid = 'bmt:hr:bad'"
    ).fetchone()
    assert absent is None
