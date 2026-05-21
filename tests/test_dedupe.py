"""Cross-source priority dedupe (tier 2)."""

from __future__ import annotations

from datetime import datetime

from premura.loader import load
from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor


def _batch_with_one(measurement: Measurement, path) -> IngestBatch:
    path.write_text("dummy")
    batch = IngestBatch(
        source_kind=measurement.source_kind,
        declared_metrics=[measurement.metric_id],
        measurements=[measurement],
        source_descriptors={
            measurement.source_id: SourceDescriptor(
                source_id=measurement.source_id,
                source_kind=measurement.source_kind,
            )
        },
    ).attach_source_artifact(path)
    batch.validate()
    return batch


def test_garmin_gdpr_wins_over_health_connect(empty_warehouse, tmp_path):
    ts = datetime(2026, 4, 1, 8, 0, 0)
    hc_m = Measurement(
        ts_utc=ts,
        metric_id="heart_rate",
        unit="bpm",
        source_id="hc:com.garmin.android.apps.connectmobile|TestDevice",
        source_kind="health_connect",
        value_num=72.0,
        source_uuid="hc-uuid-1",
    )
    g_m = Measurement(
        ts_utc=ts,
        metric_id="heart_rate",
        unit="bpm",
        source_id="garmin_gdpr:device",
        source_kind="garmin_gdpr",
        value_num=72.0,
        source_uuid="garmin:hr:1",
    )

    load(
        empty_warehouse,
        _batch_with_one(g_m, tmp_path / "g.bin"),
    )
    stats = load(
        empty_warehouse,
        _batch_with_one(hc_m, tmp_path / "hc.bin"),
    )
    assert stats.rows_skipped_priority == 1
    assert stats.rows_inserted == 0
    n = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    assert n == 1
    src = empty_warehouse.execute("SELECT source_id FROM hp.fact_measurement").fetchone()[0]
    assert src == "garmin_gdpr:device"


def test_garmin_after_hc_still_inserts(empty_warehouse, tmp_path):
    """Garmin GDPR is top priority; it bypasses any HC row."""
    ts = datetime(2026, 4, 1, 8, 0, 0)
    hc_m = Measurement(
        ts_utc=ts,
        metric_id="heart_rate",
        unit="bpm",
        source_id="hc:fitness|Pixel",
        source_kind="health_connect",
        value_num=72.0,
        source_uuid="hc-uuid-2",
    )
    g_m = Measurement(
        ts_utc=ts,
        metric_id="heart_rate",
        unit="bpm",
        source_id="garmin_gdpr:device",
        source_kind="garmin_gdpr",
        value_num=72.0,
        source_uuid="garmin:hr:2",
    )
    load(
        empty_warehouse,
        _batch_with_one(hc_m, tmp_path / "hc.bin"),
    )
    stats = load(
        empty_warehouse,
        _batch_with_one(g_m, tmp_path / "g.bin"),
    )
    assert stats.rows_inserted == 1
    assert stats.rows_skipped_priority == 0
    n = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    assert n == 2


def test_native_dedupe_within_one_file(empty_warehouse, tmp_path):
    """Same dedupe_key twice = idempotent."""
    ts = datetime(2026, 4, 1, 8, 0, 0)
    m = Measurement(
        ts_utc=ts,
        metric_id="weight",
        unit="kg",
        source_id="bmt:device",
        source_kind="bmt",
        value_num=85.0,
        source_uuid="abc",
    )
    load(empty_warehouse, _batch_with_one(m, tmp_path / "a.bin"))
    stats = load(empty_warehouse, _batch_with_one(m, tmp_path / "b.bin"))
    assert stats.rows_inserted == 0
    assert stats.rows_skipped_dup == 1
