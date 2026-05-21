"""Cross-source priority dedupe (tier 2)."""
from __future__ import annotations

from datetime import datetime

from premura.loader import attach_source_metadata, load
from premura.parsers.base import Measurement, ParseResult


def _result_with_one(measurement: Measurement, path) -> ParseResult:
    r = ParseResult(measurements=[measurement])
    path.write_text("dummy")
    attach_source_metadata(r, path)
    return r


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
        _result_with_one(g_m, tmp_path / "g.bin"),
        source_kind="garmin_gdpr",
    )
    stats = load(
        empty_warehouse,
        _result_with_one(hc_m, tmp_path / "hc.bin"),
        source_kind="health_connect",
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
        _result_with_one(hc_m, tmp_path / "hc.bin"),
        source_kind="health_connect",
    )
    stats = load(
        empty_warehouse,
        _result_with_one(g_m, tmp_path / "g.bin"),
        source_kind="garmin_gdpr",
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
    load(empty_warehouse, _result_with_one(m, tmp_path / "a.bin"), source_kind="bmt")
    stats = load(empty_warehouse, _result_with_one(m, tmp_path / "b.bin"), source_kind="bmt")
    assert stats.rows_inserted == 0
    assert stats.rows_skipped_dup == 1
