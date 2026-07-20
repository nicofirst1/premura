from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl

from premura.parsers.lab_xlsx import LabXlsxParser


def _write_workbook(tmp_path: Path, name: str = "labs.xlsx") -> Path:
    """Synthetic wide-layout xlsx: 3 tests x 2 dates, matching the real shape.

    - ``Colesterolo HDL`` maps via suggest_metric -> lab:hdl.
    - ``Trigliceridi`` maps via suggest_metric -> lab:triglycerides, and has
      one blank cell (date 2) plus one qualitative value (date 1).
    - ``Misterioso Marcatore XYZ`` has no alias and must surface as unmapped,
      never silently dropped or mis-mapped.
    """
    wb = openpyxl.Workbook()
    it = wb.active
    it.title = "Italian"
    date1 = datetime(2020, 1, 10)
    date2 = datetime(2021, 6, 15)
    it.append(["test_name", "unit", "reference_range", date1, date2])
    it.append(["Colesterolo HDL", "mg/dl", "> 40", 55.0, 60.0])
    it.append(["Trigliceridi", "mg/dl", "0 - 160", "negativ", None])
    it.append(["Misterioso Marcatore XYZ", "U/l", "0 - 10", 3.5, None])

    de = wb.create_sheet("German")
    de.append(["test_name", "unit", "reference_range"])
    de.append(["HDL Cholesterin", "mg/dl", "> 40"])
    de.append(["Triglyceride", "mg/dl", "0 - 160"])
    de.append(["Loading...", "U/l", "0 - 10"])

    path = tmp_path / name
    wb.save(path)
    return path


def test_lab_xlsx_parser_unpivots_and_maps_known_tests(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path)

    result = LabXlsxParser().parse(path)

    # 4 loadable cells: HDL x2 dates, Trigliceridi qualitative x1 date (blank
    # skipped), unmapped marker contributes 0 measurements.
    assert len(result.measurements) == 3

    by_key = {(m.metric_id, m.ts_utc.date().isoformat()): m for m in result.measurements}

    hdl_date1 = by_key[("lab:hdl", "2020-01-10")]
    assert hdl_date1.value_num == 55.0
    assert hdl_date1.unit == "mg/dl"
    assert hdl_date1.raw_payload is not None
    assert hdl_date1.raw_payload["original_test_name"] == "Colesterolo HDL"
    assert hdl_date1.raw_payload["reference_range"] == "> 40"

    hdl_date2 = by_key[("lab:hdl", "2021-06-15")]
    assert hdl_date2.value_num == 60.0

    trig_date1 = by_key[("lab:triglycerides", "2020-01-10")]
    assert trig_date1.value_num is None
    assert trig_date1.value_text == "negativ"

    assert ("lab:triglycerides", "2021-06-15") not in by_key  # blank cell skipped


def test_lab_xlsx_parser_surfaces_unknown_test_as_unmapped(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path)

    result = LabXlsxParser().parse(path)

    assert "vendor:labsheet:misterioso-marcatore-xyz" in result.unmapped_metrics
    mapped_metrics = {m.metric_id for m in result.measurements}
    assert "vendor:labsheet:misterioso-marcatore-xyz" not in mapped_metrics


def test_lab_xlsx_parser_dedupe_key_is_stable_and_source_overlap_collapses(
    tmp_path: Path,
) -> None:
    path_a = _write_workbook(tmp_path, name="a.xlsx")
    path_b = _write_workbook(tmp_path, name="b.xlsx")

    result_a = LabXlsxParser().parse(path_a)
    result_b = LabXlsxParser().parse(path_b)

    keys_a = {m.dedupe_key for m in result_a.measurements}
    keys_b = {m.dedupe_key for m in result_b.measurements}
    assert keys_a == keys_b  # same (metric, date, value) -> same dedupe_key
