"""BMT parser — synthetic CSV with kg + lb config, custom column."""

from __future__ import annotations

from pathlib import Path

from premura.parsers.bmt import BMTParser
from premura.parsers.lookup import metric_definition


def _write_csv(tmp_path: Path) -> Path:
    csv = (
        "Date,Time,Weight,BodyFat,Muscle,Water,BMI,BoneMass,Notes,WaistCm\n"
        "2024-04-01,07:30,82.5,18.4,58.1,55.2,24.6,3.1,morning,82.0\n"
        "2024-04-02,07:32,82.3,18.2,58.2,55.1,24.5,3.1,,81.7\n"
    )
    p = tmp_path / "bmt.csv"
    p.write_text(csv, encoding="utf-8")
    return p


def test_kg_default_preserves_weight(tmp_path):
    p = _write_csv(tmp_path)
    res = BMTParser().parse(p)
    w = [m for m in res.measurements if m.metric_id == "weight"]
    assert len(w) == 2
    assert w[0].unit == "kg"
    assert abs(w[0].value_num - 82.5) < 1e-6


def test_lb_config_converts_to_kg(tmp_path, monkeypatch):
    from premura.config import settings

    monkeypatch.setattr(settings.parsers.bmt, "weight_unit", "lb")
    p = _write_csv(tmp_path)
    res = BMTParser().parse(p)
    w = next(m for m in res.measurements if m.metric_id == "weight")
    assert abs(w.value_num - 82.5 * 0.45359237) < 1e-6


def test_custom_column_becomes_bmt_custom(tmp_path):
    p = _write_csv(tmp_path)
    res = BMTParser().parse(p)
    customs = [m.metric_id for m in res.measurements if m.metric_id.startswith("bmt_custom:")]
    assert customs == []
    assert "waistcm" in res.unmapped_metrics


def test_dedupe_key_format(tmp_path):
    p = _write_csv(tmp_path)
    res = BMTParser().parse(p)
    assert all(m.dedupe_key.startswith("bmt:") for m in res.measurements)


def _write_long_csv(tmp_path: Path, rows: str) -> Path:
    csv = "Measurement,Date,Value,Unit,Notes,DefinedKey,MeasurementType,LeftRight\n" + rows
    p = tmp_path / "bmt_long.csv"
    p.write_text(csv, encoding="utf-8")
    return p


def test_long_format_circumference_rows_map_to_cm(tmp_path):
    rows = (
        "waist,2024-04-01,82.0,cm,,,,\nneck,2024-04-01,38.0,cm,,,,\nhips,2024-04-01,98.0,cm,,,,\n"
    )
    p = _write_long_csv(tmp_path, rows)
    res = BMTParser().parse(p)
    waist = next(m for m in res.measurements if m.metric_id == "waist_circumference")
    neck = next(m for m in res.measurements if m.metric_id == "neck_circumference")
    hip = next(m for m in res.measurements if m.metric_id == "hip_circumference")
    assert waist.unit == "cm"
    assert abs(waist.value_num - 82.0) < 1e-6
    assert neck.unit == "cm"
    assert abs(neck.value_num - 38.0) < 1e-6
    assert hip.unit == "cm"
    assert abs(hip.value_num - 98.0) < 1e-6


def test_long_format_inches_converts_to_cm(tmp_path):
    p = _write_long_csv(tmp_path, "waist,2024-04-01,32.0,in,,,,\n")
    res = BMTParser().parse(p)
    waist = next(m for m in res.measurements if m.metric_id == "waist_circumference")
    assert waist.unit == "cm"
    # 32 in, hand-computed: 81.28 cm
    assert abs(waist.value_num - 81.28) < 1e-6


def test_wide_format_circumference_columns_map_to_cm(tmp_path):
    csv = "Date,Time,Weight,Waist,Neck,Hip,Notes\n2024-04-01,07:30,82.5,82.0,38.0,98.0,morning\n"
    p = tmp_path / "bmt_wide.csv"
    p.write_text(csv, encoding="utf-8")
    res = BMTParser().parse(p)
    waist = next(m for m in res.measurements if m.metric_id == "waist_circumference")
    neck = next(m for m in res.measurements if m.metric_id == "neck_circumference")
    hip = next(m for m in res.measurements if m.metric_id == "hip_circumference")
    assert waist.unit == "cm"
    assert abs(waist.value_num - 82.0) < 1e-6
    assert neck.unit == "cm"
    assert abs(neck.value_num - 38.0) < 1e-6
    assert hip.unit == "cm"
    assert abs(hip.value_num - 98.0) < 1e-6


def test_circumference_metrics_registered_in_ontology():
    for metric_id in ("waist_circumference", "neck_circumference", "hip_circumference"):
        definition = metric_definition(metric_id)
        assert definition is not None
        assert definition["canonical_unit"] == "cm"


def test_declares_metrics_includes_circumferences():
    declared = BMTParser().declares_metrics()
    assert "waist_circumference" in declared
    assert "neck_circumference" in declared
    assert "hip_circumference" in declared


def test_unknown_long_measurement_stays_unmapped(tmp_path):
    p = _write_long_csv(tmp_path, "chest,2024-04-01,100.0,cm,,,,\n")
    res = BMTParser().parse(p)
    assert res.measurements == []
    assert "chest" in res.unmapped_metrics
