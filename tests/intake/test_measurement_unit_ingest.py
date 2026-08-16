"""Load-boundary unit enforcement for measurements (issue #113).

Structural mirror of test_interval_unit_ingest.py: after a real
`loader.load()`, every persisted fact_measurement row's unit must equal its
metric's canonical_unit, with the VALUE rescaled to match (never merely
relabeled). A row whose observed unit has no registered conversion rule is
refused row-level, not batch-level.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor
from premura.parsers.bmt import BMTParser
from premura.parsers.lab_pdf import LabPdfParser
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

    # Parity: the loader-reported refusal count matches exactly one
    # persisted hp.ingest_skip row, carrying the same from/to units and metric.
    assert len(stats.unit_refusals) == 1
    skip_rows = empty_warehouse.execute(
        """
        SELECT kind, metric_id, from_unit, to_unit
        FROM hp.ingest_skip
        WHERE batch_id = ?
        """,
        [stats.batch_id],
    ).fetchall()
    assert len(skip_rows) == len(stats.unit_refusals)
    assert skip_rows == [
        ("unit_unconvertible", "heart_rate", "furlongs_per_fortnight", "bpm"),
    ]


# --- e2e: real simplified parsers (observe) -> real loader (convert) ---
#
# Pins that the two-step pipeline (parser emits observed unit, loader converts
# to canonical) reproduces the same warehouse rows the old one-step pipeline
# (parser converted internally) used to produce.


def test_lab_pdf_e2e_unit_normalization_matches_pre_split_pipeline(empty_warehouse, tmp_path):
    report = tmp_path / "2026-04-12-unit-normalization.pdf"
    report.write_text(
        """
Laboratory: Centro Analisi Alfa
Accettazione del: 2026-04-12
Test | Value | Unit | Range
MCH | 30,1 | pg/eritr. | 26,0 - 32,0
Sideremia | 1.02 | mg/l | 0.6 - 1.7
Calcium | 2.50 | mmol/l | 2.15 - 2.55
TSH | 2.4 | microU/ml | 0.4 - 4.0
Leukozyten | 6.2 | G/l | 4.0 - 10.0
Albumin | 44 | g/l | 35 - 52
""",
        encoding="utf-8",
    )

    batch = LabPdfParser().parse(report)
    stats = load(empty_warehouse, batch)

    assert stats.rows_skipped_unit == 0
    rows = dict(
        empty_warehouse.execute(
            "SELECT metric_id, unit || ':' || value_num FROM hp.fact_measurement"
        ).fetchall()
    )
    # Same canonical unit + value the old one-step (parser-converts) pipeline produced.
    assert rows["lab:mch"] == "pg:30.1"
    assert rows["lab:iron"] == f"ug_per_dl:{102.0}"
    assert rows["lab:calcium"] == f"mg_per_dl:{2.50 * 4.008}"
    assert rows["lab:tsh"] == "mIU_per_l:2.4"
    assert rows["lab:wbc"] == "10^9_per_l:6.2"
    assert rows["lab:albumin"] == "g_per_dl:4.4"


def test_bmt_long_format_e2e_inches_and_kg_match_pre_split_pipeline(empty_warehouse, tmp_path):
    csv_path = tmp_path / "bmt_long.csv"
    csv_path.write_text(
        "Measurement,Date,Value,Unit,Notes,DefinedKey,MeasurementType,LeftRight\n"
        "waist,2024-04-01,32.0,in,,,,\n"
        "weight,2024-04-01,154.0,lb,,,,\n",
        encoding="utf-8",
    )

    batch = BMTParser().parse(csv_path)
    stats = load(empty_warehouse, batch)

    assert stats.rows_skipped_unit == 0
    rows = dict(
        empty_warehouse.execute(
            "SELECT metric_id, unit || ':' || value_num FROM hp.fact_measurement"
        ).fetchall()
    )
    assert rows["waist_circumference"] == f"cm:{32.0 * 2.54}"
    assert rows["weight"] == f"kg:{154.0 * 0.45359237}"


# --- source-kind vocabulary rail: the test that would have caught the incident
# (source-kind rail; issue #113) ---
#
# `validate_batch_against_warehouse` must refuse an unregistered `source_kind`
# BEFORE any write — not just skip the row, refuse the whole batch, and write
# zero rows to fact_measurement AND ingest_run.


def test_unregistered_source_kind_raises_and_writes_nothing(empty_warehouse, tmp_path):
    m = Measurement(
        ts_utc=datetime(2026, 4, 1, 8, 0, 0),
        metric_id="weight",
        unit="kg",
        source_id="labsheet:manual",
        source_kind="labsheet",  # not a registered parser source_kind, not the manual-load kind
        value_num=70.0,
        source_uuid="labsheet:weight:1",
    )
    batch = _batch([m], tmp_path / "labsheet.bin")

    with pytest.raises(ValueError, match="labsheet"):
        load(empty_warehouse, batch)

    n_measurements = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[
        0
    ]
    n_runs = empty_warehouse.execute("SELECT COUNT(*) FROM hp.ingest_run").fetchone()[0]
    assert n_measurements == 0
    assert n_runs == 0


def test_allow_unregistered_source_kind_flag_succeeds_and_stays_visible(empty_warehouse, tmp_path):
    """The ADR 0010 build-and-use escape hatch: opt-in widens vocabulary ONLY.

    With ``allow_unregistered_source_kind=True`` the same unregistered kind that
    ``test_unregistered_source_kind_raises_and_writes_nothing`` refuses now loads
    — and the unregistered kind is NOT laundered into a known one: it lands
    verbatim in ``hp.ingest_run.source_kind`` so audit-integrity can still see
    exactly what ran.
    """
    m = Measurement(
        ts_utc=datetime(2026, 4, 1, 8, 0, 0),
        metric_id="weight",
        unit="kg",
        source_id="labsheet:manual",
        source_kind="labsheet",
        value_num=70.0,
        source_uuid="labsheet:weight:1",
    )
    batch = _batch([m], tmp_path / "labsheet2.bin")

    stats = load(empty_warehouse, batch, allow_unregistered_source_kind=True)

    assert stats.rows_inserted == 1
    (stored_kind,) = empty_warehouse.execute(
        "SELECT source_kind FROM hp.ingest_run WHERE batch_id = ?", [stats.batch_id]
    ).fetchone()
    assert stored_kind == "labsheet"
