from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

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


def test_loader_auto_computes_matching_ratios(empty_warehouse, tmp_path: Path) -> None:
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
    assert rows == [
        ("derived:ldl_hdl_ratio", 3.0),
        ("derived:tg_hdl_ratio", 2.0),
    ]


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
