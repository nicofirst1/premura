"""BMT parser — synthetic CSV with kg + lb config, custom column."""
from __future__ import annotations

from pathlib import Path

from premura.parsers.bmt import BMTParser


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
    assert "bmt_custom:waistcm" in customs
    # Custom columns carry unit='unknown'.
    waist = next(m for m in res.measurements if m.metric_id == "bmt_custom:waistcm")
    assert waist.unit == "unknown"


def test_dedupe_key_format(tmp_path):
    p = _write_csv(tmp_path)
    res = BMTParser().parse(p)
    assert all(m.dedupe_key.startswith("bmt:") for m in res.measurements)
