"""StayFree `.xls` export parser tests.

The real StayFree export is a legacy binary `.xls`; per AGENTS.md real
operator exports are never copied into the repo (personal app-usage data).
Most coverage below exercises the pure row-processing functions
(`process_app_sheet`, `process_device_unlocks_sheet`, `parse_duration_seconds`,
`parse_date_header`) directly against synthetic in-memory row data, which needs
no `.xls` file at all. One end-to-end test builds a small synthetic `.xls`
fixture in-memory with `xlwt` (never touching disk, never real usage data) to
cover the `xlrd`-reading wrapper (`StayFreeParser.parse`).
"""

from __future__ import annotations

import io
from pathlib import Path

import xlwt

from premura.parsers.lookup import metric_definition
from premura.parsers.stayfree import (
    METRIC_DEVICE_UNLOCKS,
    METRIC_USAGE_COUNT,
    METRIC_USAGE_TIME,
    StayFreeParser,
    _parse_count,
    parse_date_header,
    parse_duration_seconds,
    process_app_sheet,
    process_device_unlocks_sheet,
)

# --------------------------------------------------------------------------- #
# Duration / date parsing.
# --------------------------------------------------------------------------- #


def test_parse_duration_seconds_handles_all_observed_formats():
    assert parse_duration_seconds("0s") == 0.0
    assert parse_duration_seconds("22s") == 22.0
    assert parse_duration_seconds("5m") == 300.0
    assert parse_duration_seconds("5m 12s") == 312.0
    assert parse_duration_seconds("1h 5m") == 3900.0
    assert parse_duration_seconds("1h 5s") == 3605.0
    assert parse_duration_seconds("1h 5m 3s") == 3903.0


def test_parse_duration_seconds_rejects_garbage():
    assert parse_duration_seconds("") is None
    assert parse_duration_seconds("not a duration") is None
    assert parse_duration_seconds("Total Usage") is None


def test_parse_date_header_roundtrips_stayfree_format():
    parsed = parse_date_header("October 31, 2025")
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == (2025, 10, 31)


def test_parse_date_header_rejects_non_date_labels():
    assert parse_date_header("") is None
    assert parse_date_header("Device") is None
    assert parse_date_header("Created by “StayFree”.") is None
    assert parse_date_header("Creation date: 9/11/26 09:33:24") is None


def test_parse_count_helper():
    assert _parse_count("0") == 0.0
    assert _parse_count("3") == 3.0
    assert _parse_count("not a number") is None


# --------------------------------------------------------------------------- #
# process_app_sheet (Usage Time / Usage Count layout).
# --------------------------------------------------------------------------- #

_APP_HEADER = ["", "Device", "October 31, 2025", "November 1, 2025"]


def test_process_app_sheet_emits_one_measurement_per_nonzero_cell():
    rows = [
        _APP_HEADER,
        ["com.example.app", "Google Pixel 9", "5m 12s", "0s"],
    ]
    measurements, skipped, descriptors = process_app_sheet(
        rows, METRIC_USAGE_TIME, "s", parse_duration_seconds
    )

    assert len(measurements) == 1
    m = measurements[0]
    assert m.metric_id == METRIC_USAGE_TIME
    assert m.unit == "s"
    assert m.value_num == 312.0
    assert m.value_text == "com.example.app"
    assert m.raw_payload == {"device": "Google Pixel 9"}
    assert m.ts_utc.day == 31
    assert not skipped
    assert "stayfree:google-pixel-9" in descriptors


def test_process_app_sheet_skips_zero_cells_without_recording_skipped_row():
    rows = [
        _APP_HEADER,
        ["example-fitness.app", "Google Pixel 9", "0s", "0s"],
    ]
    measurements, skipped, _descriptors = process_app_sheet(
        rows, METRIC_USAGE_TIME, "s", parse_duration_seconds
    )
    assert measurements == []
    assert skipped == []  # legitimate "no usage" is not an error


def test_process_app_sheet_skips_footer_rows_structurally():
    rows = [
        _APP_HEADER,
        ["example-fitness.app", "Google Pixel 9", "1m", "0s"],
        ["Total Usage", "", "1h 49m 49s", "2h"],
        ["", "", "", ""],
        ["Created by “StayFree”.", "", "", ""],
        ["Creation date: 9/11/26 09:33:24", "", "", ""],
    ]
    measurements, skipped, descriptors = process_app_sheet(
        rows, METRIC_USAGE_TIME, "s", parse_duration_seconds
    )
    # Only the one real data row produces a measurement; footer/total rows
    # (blank device or blank app label) are never treated as data.
    assert len(measurements) == 1
    assert measurements[0].value_text == "example-fitness.app"
    assert skipped == []
    assert list(descriptors) == ["stayfree:google-pixel-9"]


def test_process_app_sheet_usage_count_emits_integer_values():
    rows = [
        _APP_HEADER,
        ["com.example.app", "Google Pixel 9", "3", "0"],
    ]
    measurements, skipped, _descriptors = process_app_sheet(
        rows, METRIC_USAGE_COUNT, "count", _parse_count
    )
    assert len(measurements) == 1
    assert measurements[0].metric_id == METRIC_USAGE_COUNT
    assert measurements[0].unit == "count"
    assert measurements[0].value_num == 3.0
    assert skipped == []


def test_process_app_sheet_records_skipped_row_for_unparseable_value():
    rows = [
        _APP_HEADER,
        ["com.example.app", "Google Pixel 9", "garbage", "0s"],
    ]
    measurements, skipped, _descriptors = process_app_sheet(
        rows, METRIC_USAGE_TIME, "s", parse_duration_seconds
    )
    assert measurements == []
    assert len(skipped) == 1
    assert "garbage" in skipped[0].reason


# --------------------------------------------------------------------------- #
# process_device_unlocks_sheet (no Device column, dates start at column 1).
# --------------------------------------------------------------------------- #


def test_process_device_unlocks_sheet_emits_daily_counts():
    rows = [
        ["", "October 31, 2025", "November 1, 2025"],
        ["Device Unlocks", "42", "0"],
        ["", "", ""],
        ["Created by “StayFree”.", "", ""],
        ["Creation date: 9/11/26 09:33:24", "", ""],
    ]
    measurements, skipped, descriptors = process_device_unlocks_sheet(rows)

    assert len(measurements) == 1  # the "0" day is skipped, not an error
    m = measurements[0]
    assert m.metric_id == METRIC_DEVICE_UNLOCKS
    assert m.unit == "count"
    assert m.value_num == 42.0
    assert m.ts_utc.day == 31
    assert skipped == []
    assert list(descriptors) == ["stayfree:device"]


def test_process_device_unlocks_sheet_handles_unparseable_value():
    rows = [
        ["", "October 31, 2025"],
        ["Device Unlocks", "not-a-number"],
    ]
    measurements, skipped, _descriptors = process_device_unlocks_sheet(rows)
    assert measurements == []
    assert len(skipped) == 1


# --------------------------------------------------------------------------- #
# Ontology declarations.
# --------------------------------------------------------------------------- #


def test_declared_metrics_all_registered_in_ontology():
    parser = StayFreeParser()
    for metric_id in parser.declares_metrics():
        assert metric_definition(metric_id) is not None, metric_id


# --------------------------------------------------------------------------- #
# End-to-end: synthetic in-memory .xls fixture through StayFreeParser.parse().
# --------------------------------------------------------------------------- #


def _write_synthetic_xls(tmp_path: Path) -> Path:
    """Build a small synthetic (non-real) StayFree-shaped .xls export."""
    wb = xlwt.Workbook()

    usage_time = wb.add_sheet("Usage Time")
    usage_time.write(0, 0, "")
    usage_time.write(0, 1, "Device")
    usage_time.write(0, 2, "October 31, 2025")
    usage_time.write(0, 3, "November 1, 2025")
    usage_time.write(1, 0, "com.example.testapp")
    usage_time.write(1, 1, "Test Phone")
    usage_time.write(1, 2, "5m 12s")
    usage_time.write(1, 3, "0s")
    usage_time.write(2, 0, "example.test.domain")
    usage_time.write(2, 1, "Test Phone")
    usage_time.write(2, 2, "1h 5m 3s")
    usage_time.write(2, 3, "22s")
    usage_time.write(3, 0, "Total Usage")
    usage_time.write(3, 2, "1h 10m 15s")
    usage_time.write(3, 3, "22s")
    usage_time.write(4, 0, "")
    usage_time.write(5, 0, "Created by “StayFree”.")
    usage_time.write(6, 0, "Creation date: 9/11/26 09:33:24")

    usage_count = wb.add_sheet("Usage Count")
    usage_count.write(0, 0, "")
    usage_count.write(0, 1, "Device")
    usage_count.write(0, 2, "October 31, 2025")
    usage_count.write(0, 3, "November 1, 2025")
    usage_count.write(1, 0, "com.example.testapp")
    usage_count.write(1, 1, "Test Phone")
    usage_count.write(1, 2, "3")
    usage_count.write(1, 3, "0")
    usage_count.write(2, 0, "example.test.domain")
    usage_count.write(2, 1, "Test Phone")
    usage_count.write(2, 2, "1")
    usage_count.write(2, 3, "1")
    usage_count.write(3, 0, "Total Usage")
    usage_count.write(3, 2, "4")
    usage_count.write(3, 3, "1")
    usage_count.write(4, 0, "")
    usage_count.write(5, 0, "Created by “StayFree”.")
    usage_count.write(6, 0, "Creation date: 9/11/26 09:33:25")

    device_unlocks = wb.add_sheet("Device Unlocks")
    device_unlocks.write(0, 0, "")
    device_unlocks.write(0, 1, "October 31, 2025")
    device_unlocks.write(0, 2, "November 1, 2025")
    device_unlocks.write(1, 0, "Device Unlocks")
    device_unlocks.write(1, 1, "42")
    device_unlocks.write(1, 2, "0")
    device_unlocks.write(2, 0, "")
    device_unlocks.write(3, 0, "Created by “StayFree”.")
    device_unlocks.write(4, 0, "Creation date: 9/11/26 09:33:25")

    buf = io.BytesIO()
    wb.save(buf)
    path = tmp_path / "stayfree_export.xls"
    path.write_bytes(buf.getvalue())
    return path


def test_stayfree_parser_end_to_end_synthetic_fixture(tmp_path):
    path = _write_synthetic_xls(tmp_path)
    batch = StayFreeParser().parse(path)

    assert batch.source_kind == "stayfree"
    assert set(batch.declared_metrics) == {
        METRIC_USAGE_TIME,
        METRIC_USAGE_COUNT,
        METRIC_DEVICE_UNLOCKS,
    }
    assert batch.emitted_metrics <= set(batch.declared_metrics)

    usage_time = [m for m in batch.measurements if m.metric_id == METRIC_USAGE_TIME]
    usage_count = [m for m in batch.measurements if m.metric_id == METRIC_USAGE_COUNT]
    unlocks = [m for m in batch.measurements if m.metric_id == METRIC_DEVICE_UNLOCKS]

    # 2 apps x 2 days = 4 cells, minus one "0s" zero-skip -> 3 measurements.
    assert len(usage_time) == 3
    # 2 apps x 2 days = 4 cells, minus one "0" zero-skip -> 3 measurements.
    assert len(usage_count) == 3
    # 2 days, minus one "0" zero-skip -> 1 measurement.
    assert len(unlocks) == 1

    # No footer/total rows leaked through as data.
    assert all(m.value_text != "Total Usage" for m in usage_time + usage_count)

    batch.validate()  # re-run the same validation the loader will run
