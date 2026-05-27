from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path

import pytest
import yaml

from premura import engine
from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor
from premura.store.loader import load


def _batch_with_measurements(
    path: Path,
    source_kind: str,
    measurements: list[Measurement],
) -> IngestBatch:
    path.write_text("dummy", encoding="utf-8")
    source_descriptors = {
        measurement.source_id: SourceDescriptor(
            source_id=measurement.source_id,
            source_kind=measurement.source_kind,
        )
        for measurement in measurements
    }
    batch = IngestBatch(
        source_kind=source_kind,
        declared_metrics=sorted({measurement.metric_id for measurement in measurements}),
        measurements=measurements,
        source_descriptors=source_descriptors,
    ).attach_source_artifact(path)
    batch.validate()
    return batch


def test_list_by_domain_and_list_auto_safe_expose_builtin_lab_ratios() -> None:
    liver = {spec.name for spec in engine.list_by_domain("liver")}
    assert "ast_alt_ratio" in liver

    auto_safe = {spec.name for spec in engine.list_auto_safe()}
    assert {"ast_alt_ratio", "ldl_hdl_ratio", "tg_hdl_ratio"} <= auto_safe


def test_check_inputs_available_respects_validity_windows(empty_warehouse) -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    source_id = "lab_pdf:testlab"
    empty_warehouse.execute(
        """
        INSERT INTO hp.dim_source (source_id, source_kind, first_seen, last_seen)
        VALUES (?, ?, now(), now())
        """,
        [source_id, "lab_pdf"],
    )
    empty_warehouse.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES
            (?, 'lab:ast', 22.0, 'U_per_l', ?, 'ast-recent', 'ast-recent'),
            (?, 'lab:alt', 20.0, 'U_per_l', ?, 'alt-stale', 'alt-stale')
        """,
        [now - timedelta(days=10), source_id, now - timedelta(days=120), source_id],
    )

    assert engine.check_inputs_available(["lab:ast"], empty_warehouse) is True
    assert engine.check_inputs_available(["lab:alt"], empty_warehouse) is False
    assert (
        engine.check_inputs_available(
            ["lab:ast"],
            empty_warehouse,
            within=timedelta(days=1),
        )
        is False
    )


def test_compute_persists_ast_alt_ratio(empty_warehouse, tmp_path: Path) -> None:
    ts = datetime(2026, 4, 1, 8, 0, 0)
    source_id = "lab_pdf:testlab"
    measurements = [
        Measurement(
            ts_utc=ts,
            metric_id="lab:ast",
            unit="U_per_l",
            source_id=source_id,
            source_kind="lab_pdf",
            value_num=30.0,
            source_uuid="ast-1",
        ),
        Measurement(
            ts_utc=ts,
            metric_id="lab:alt",
            unit="U_per_l",
            source_id=source_id,
            source_kind="lab_pdf",
            value_num=20.0,
            source_uuid="alt-1",
        ),
    ]
    load(
        empty_warehouse,
        _batch_with_measurements(tmp_path / "liver.pdf", "lab_pdf", measurements),
    )

    rows = engine.compute("ast_alt_ratio", empty_warehouse)
    assert len(rows) == 1
    assert rows[0]["value_num"] == 1.5

    stored = empty_warehouse.execute(
        """
        SELECT metric_id, value_num, unit, source_id, raw_payload
        FROM hp.fact_measurement
        WHERE metric_id = 'derived:ast_alt_ratio'
        """
    ).fetchone()
    assert stored is not None
    assert stored[0] == "derived:ast_alt_ratio"
    assert stored[1] == 1.5
    assert stored[2] == "ratio"
    assert stored[3] == source_id
    assert json.loads(stored[4])["revision"] == "1"


def test_loader_does_not_auto_compute_matching_ratios(empty_warehouse, tmp_path: Path) -> None:
    ts = datetime(2026, 4, 1, 8, 0, 0)
    source_id = "lab_pdf:testlab"
    load(
        empty_warehouse,
        _batch_with_measurements(
            tmp_path / "lipids.pdf",
            "lab_pdf",
            [
                Measurement(
                    ts_utc=ts,
                    metric_id="lab:ldl",
                    unit="mg_per_dl",
                    source_id=source_id,
                    source_kind="lab_pdf",
                    value_num=120.0,
                    source_uuid="ldl-1",
                ),
                Measurement(
                    ts_utc=ts,
                    metric_id="lab:hdl",
                    unit="mg_per_dl",
                    source_id=source_id,
                    source_kind="lab_pdf",
                    value_num=40.0,
                    source_uuid="hdl-1",
                ),
                Measurement(
                    ts_utc=ts,
                    metric_id="lab:triglycerides",
                    unit="mg_per_dl",
                    source_id=source_id,
                    source_kind="lab_pdf",
                    value_num=80.0,
                    source_uuid="tg-1",
                ),
            ],
        ),
    )

    rows = empty_warehouse.execute(
        """
        SELECT metric_id, value_num
        FROM hp.fact_measurement
        WHERE metric_id IN ('derived:ldl_hdl_ratio', 'derived:tg_hdl_ratio')
        ORDER BY metric_id
        """
    ).fetchall()
    assert rows == []

    engine.compute("ldl_hdl_ratio", empty_warehouse)
    engine.compute("tg_hdl_ratio", empty_warehouse)
    rows = empty_warehouse.execute(
        """
        SELECT metric_id, value_num
        FROM hp.fact_measurement
        WHERE metric_id IN ('derived:ldl_hdl_ratio', 'derived:tg_hdl_ratio')
        ORDER BY metric_id
        """
    ).fetchall()
    assert rows == [
        ("derived:ldl_hdl_ratio", 3.0),
        ("derived:tg_hdl_ratio", 2.0),
    ]


def test_compute_rejects_wrong_derived_row_shape(empty_warehouse) -> None:
    from premura.engine import REGISTRY, SignalSpec

    name = "_broken_signal"
    REGISTRY[name] = SignalSpec(
        name=name,
        domain=["test"],
        inputs=[],
        output="derived:broken",
        revision="7",
        fn=lambda conn: ["not-a-row"],
    )
    try:
        with pytest.raises(TypeError, match="row 0"):
            engine.compute(name, empty_warehouse)
    finally:
        REGISTRY.pop(name, None)


def test_list_unavailable_reports_signals_with_missing_inputs(
    empty_warehouse,
    tmp_path: Path,
) -> None:
    load(
        empty_warehouse,
        _batch_with_measurements(
            tmp_path / "partial.pdf",
            "lab_pdf",
            [
                Measurement(
                    ts_utc=datetime(2026, 4, 1, 8, 0, 0),
                    metric_id="lab:ast",
                    unit="U_per_l",
                    source_id="lab_pdf:testlab",
                    source_kind="lab_pdf",
                    value_num=30.0,
                    source_uuid="ast-only",
                )
            ],
        ),
    )

    missing = {spec.name for spec in engine.list_unavailable("liver", empty_warehouse)}
    assert missing == {"ast_alt_ratio"}


def test_parse_iso8601_duration_accepts_seeded_validity_windows() -> None:
    from premura.engine import _parse_iso8601_duration

    rows = yaml.safe_load(files("premura").joinpath("dim_metric.yaml").read_text(encoding="utf-8"))
    windows = {row["validity_window"] for row in rows if row.get("validity_window")}

    for window in windows:
        assert _parse_iso8601_duration(window) > timedelta(0)


def test_parse_iso8601_duration_rejects_fractional_formats() -> None:
    from premura.engine import _parse_iso8601_duration

    with pytest.raises(ValueError, match="unsupported"):
        _parse_iso8601_duration("PT0.5S")


# ---------------------------------------------------------------------------
# T004 — Stage 2 catalog and summary helper semantics
# ---------------------------------------------------------------------------

def _insert_source(conn, source_id: str, source_kind: str = "lab_pdf") -> None:
    conn.execute(
        """
        INSERT INTO hp.dim_source (source_id, source_kind, first_seen, last_seen)
        VALUES (?, ?, now(), now())
        """,
        [source_id, source_kind],
    )


def _insert_measurement(
    conn,
    metric_id: str,
    value_num: float,
    ts_utc: datetime,
    source_id: str,
    dedupe_key: str,
    source_uuid: str | None = None,
    unit: str = "bpm",
) -> None:
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [ts_utc, metric_id, value_num, unit, source_id, source_uuid or dedupe_key, dedupe_key],
    )


def test_list_metric_catalog_fresh_metric_returns_current(empty_warehouse) -> None:
    """A metric with a recent observation yields validity_status=current."""
    from premura import engine

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    source_id = "wearable:garmin"
    _insert_source(empty_warehouse, source_id, source_kind="wearable")
    # resting_hr has validity_window P1D — insert data 6 hours ago -> current
    _insert_measurement(
        empty_warehouse,
        metric_id="resting_hr",
        value_num=58.0,
        ts_utc=now - timedelta(hours=6),
        source_id=source_id,
        dedupe_key="rhr-fresh",
    )

    entries = engine.list_metric_catalog(["resting_hr"], empty_warehouse)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.metric_id == "resting_hr"
    assert entry.validity_status.value == "current"
    assert entry.latest_value == 58.0
    assert entry.latest_observation_at is not None
    assert entry.unit == "bpm"
    # No fabricated data for known-good entries
    assert entry.message is None


def test_list_metric_catalog_stale_metric_returns_stale(empty_warehouse) -> None:
    """A metric with an old observation yields validity_status=stale."""
    from premura import engine

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    source_id = "wearable:garmin"
    _insert_source(empty_warehouse, source_id, source_kind="wearable")
    # resting_hr has validity_window P1D — insert data 3 days ago -> stale
    _insert_measurement(
        empty_warehouse,
        metric_id="resting_hr",
        value_num=62.0,
        ts_utc=now - timedelta(days=3),
        source_id=source_id,
        dedupe_key="rhr-stale",
    )

    entries = engine.list_metric_catalog(["resting_hr"], empty_warehouse)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.validity_status.value == "stale"
    # Value is still present for stale (caller decides how to surface)
    assert entry.latest_value == 62.0
    assert entry.latest_observation_at is not None


def test_list_metric_catalog_empty_metric_returns_unavailable(empty_warehouse) -> None:
    """A registered metric with no observations yields validity_status=unavailable."""
    from premura import engine

    entries = engine.list_metric_catalog(["resting_hr"], empty_warehouse)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.validity_status.value == "unavailable"
    # No fabricated numeric fields
    assert entry.latest_value is None
    assert entry.latest_observation_at is None
    assert entry.message is not None


def test_list_metric_catalog_unknown_metric_returns_unavailable(empty_warehouse) -> None:
    """An unregistered metric ID yields unavailable with no fabricated numeric fields."""
    from premura import engine

    entries = engine.list_metric_catalog(["metric:does_not_exist"], empty_warehouse)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.validity_status.value == "unavailable"
    assert entry.latest_value is None
    assert entry.latest_observation_at is None
    assert entry.unit == ""
    assert entry.validity_window is None
    assert entry.message is not None
    # Message distinguishes unknown from known-but-empty
    assert "not registered" in entry.message


def test_list_metric_catalog_distinguishes_unknown_from_empty(empty_warehouse) -> None:
    """Unknown and empty metrics both yield unavailable but with distinct messages."""
    from premura import engine

    results = engine.list_metric_catalog(
        ["metric:does_not_exist", "resting_hr"], empty_warehouse
    )
    unknown_entry = next(e for e in results if e.metric_id == "metric:does_not_exist")
    empty_entry = next(e for e in results if e.metric_id == "resting_hr")

    assert unknown_entry.validity_status.value == "unavailable"
    assert empty_entry.validity_status.value == "unavailable"
    # Messages must differ
    assert unknown_entry.message != empty_entry.message


def test_metric_summary_fresh_metric_returns_window_stats(empty_warehouse) -> None:
    """A metric with recent data yields sample_size, imputed_proportion, gap_count."""
    from premura import engine

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    source_id = "wearable:garmin"
    _insert_source(empty_warehouse, source_id, source_kind="wearable")
    # Insert 5 observations within the 30-day window.
    # Most recent is 6 hours ago (well within P1D validity_window -> current).
    offsets = [timedelta(hours=6), timedelta(days=2), timedelta(days=5),
               timedelta(days=10), timedelta(days=20)]
    for i, offset in enumerate(offsets):
        _insert_measurement(
            empty_warehouse,
            metric_id="resting_hr",
            value_num=60.0 + i,
            ts_utc=now - offset,
            source_id=source_id,
            dedupe_key=f"rhr-summary-{i}",
        )

    summary = engine.metric_summary("resting_hr", empty_warehouse)
    assert summary.metric_id == "resting_hr"
    assert summary.validity_status.value == "current"
    assert summary.window_days == 30
    assert summary.sample_size == 5
    assert summary.imputed_proportion is not None
    assert summary.gap_count is not None
    assert summary.latest_value is not None
    assert summary.latest_observation_at is not None
    # resting_hr allows LOCF — imputed_proportion may be > 0 but not fabricated
    assert 0.0 <= summary.imputed_proportion <= 1.0


def test_metric_summary_no_imputation_policy_yields_zero_imputed(empty_warehouse) -> None:
    """A metric with missing_data_policy=none always has imputed_proportion==0.0."""
    from premura import engine

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    source_id = "lab_pdf:testlab"
    _insert_source(empty_warehouse, source_id)
    # lab:ast has missing_data_policy: none
    _insert_measurement(
        empty_warehouse,
        metric_id="lab:ast",
        value_num=25.0,
        ts_utc=now - timedelta(days=5),
        source_id=source_id,
        dedupe_key="ast-no-impute",
        unit="U_per_l",
    )

    summary = engine.metric_summary("lab:ast", empty_warehouse)
    assert summary.imputed_proportion == 0.0
    assert summary.gap_count is not None
    assert summary.sample_size is not None


def test_metric_summary_empty_metric_returns_unavailable(empty_warehouse) -> None:
    """A metric with no data yields unavailable with no fabricated numeric fields."""
    from premura import engine

    summary = engine.metric_summary("resting_hr", empty_warehouse)
    assert summary.validity_status.value == "unavailable"
    assert summary.sample_size is None
    assert summary.imputed_proportion is None
    assert summary.gap_count is None
    assert summary.latest_value is None
    assert summary.latest_observation_at is None
    assert summary.message is not None


def test_metric_summary_unknown_metric_returns_unavailable(empty_warehouse) -> None:
    """An unknown metric yields unavailable with no fabricated fields."""
    from premura import engine

    summary = engine.metric_summary("metric:does_not_exist", empty_warehouse)
    assert summary.validity_status.value == "unavailable"
    assert summary.sample_size is None
    assert summary.imputed_proportion is None
    assert summary.gap_count is None
    assert summary.unit == ""
    assert summary.validity_window is None
    assert "not registered" in (summary.message or "")


def test_metric_summary_stale_metric_returns_stale(empty_warehouse) -> None:
    """A metric with only old data yields stale status with window stats."""
    from premura import engine

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    source_id = "lab_pdf:testlab"
    _insert_source(empty_warehouse, source_id)
    # lab:ast has validity_window P3M; insert data 6 months ago -> stale
    _insert_measurement(
        empty_warehouse,
        metric_id="lab:ast",
        value_num=28.0,
        ts_utc=now - timedelta(days=180),
        source_id=source_id,
        dedupe_key="ast-stale",
        unit="U_per_l",
    )

    summary = engine.metric_summary("lab:ast", empty_warehouse)
    assert summary.validity_status.value == "stale"
    # No fabricated fields; numeric window stats are None because the
    # observation is outside the 30-day summary window
    assert summary.latest_value == 28.0  # latest_value from latest_usable_value (stale)
    assert summary.sample_size == 0  # nothing in 30-day window
