from __future__ import annotations

from pathlib import Path

import pytest

from premura.parsers.lab_pdf import LabPdfParser
from premura.parsers.lookup import suggest_metric


def _write_report(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_suggest_metric_matches_aliases_and_display_names() -> None:
    assert suggest_metric("Resting Heart Rate") == "resting_hr"
    assert suggest_metric("Leukozyten") == "lab:wbc"
    assert suggest_metric("Hb") == "lab:hemoglobin"
    assert suggest_metric("Transaminasi GOT") == "lab:ast"


def test_lab_pdf_parser_emits_multilingual_rows(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        "2026-04-12-lab.pdf",
        """
Laboratory: Centro Analisi Alfa
Accettazione del: 2026-04-12
Test | Value | Unit | Range
Leukozyten | 6,2 | 10^9/L | 4.0-10.0
Hb | 14.1 | g/dL | 13.0-17.0
Triglyzeride | 88 | mg/dL | <150
Transaminasi GOT | 22 | U/L | <40
Transaminasi GPT | 18 | U/L | <40
""",
    )

    result = LabPdfParser().parse(report)

    assert result.source_descriptors["lab:centro-analisi-alfa"].source_kind == "lab_pdf"
    metrics = {measurement.metric_id for measurement in result.measurements}
    assert {"lab:wbc", "lab:hemoglobin", "lab:triglycerides", "lab:ast", "lab:alt"} <= metrics
    assert all(
        measurement.ts_utc.date().isoformat() == "2026-04-12"
        for measurement in result.measurements
    )


def test_lab_pdf_parser_handles_qualitative_values_and_skips_followups(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        "2026-05-10-stool.pdf",
        """
Lab: Gut Check
Collection date: 2026-05-10
Test | Value | Unit
Stool culture | negativ | enum
Stool ova and parasites | ASSENTI | enum
Stool white blood cells | folgt | enum
""",
    )

    result = LabPdfParser().parse(report)

    by_metric = {measurement.metric_id: measurement for measurement in result.measurements}
    assert by_metric["lab:stool_culture"].value_num is None
    assert by_metric["lab:stool_culture"].value_text == "negativ"
    assert by_metric["lab:stool_ova_parasites"].value_text == "assenti"
    assert "lab:stool_white_blood_cells" not in by_metric
    assert "stool-white-blood-cells:unparseable_value" in result.unmapped_metrics
    assert result.notes is not None
    assert "unsupported value 'folgt'" in result.notes


def test_lab_pdf_parser_falls_back_to_filename_date_and_tracks_unmapped(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        "20260415-mystery-lab.pdf",
        """
Lab: Mystery Labs
Parameter | Result | Unit
Unknown Analyte | 12.0 | mg/dL
WBC | <1.0 x 10^4 | 10^9/L
""",
    )

    result = LabPdfParser().parse(report)

    assert result.measurements[0].metric_id == "lab:wbc"
    assert result.measurements[0].value_num == 10000.0
    assert result.measurements[0].ts_utc.date().isoformat() == "2026-04-15"
    assert result.unmapped_metrics == ["unknown-analyte:unknown_metric"]


def test_lab_pdf_parser_records_unit_mismatches_instead_of_dropping_silently(
    tmp_path: Path,
) -> None:
    report = _write_report(
        tmp_path,
        "2026-04-12-unit-mismatch.pdf",
        """
Laboratory:
Centro Analisi Alfa
Accettazione del: 2026-04-12
Test | Value | Unit | Range
Hb | 14.1 | g/L | 13.0-17.0
""",
    )

    result = LabPdfParser().parse(report)

    assert result.measurements == []
    assert result.source_descriptors["lab:centro-analisi-alfa"].source_kind == "lab_pdf"
    assert result.unmapped_metrics == ["hb:unit_mismatch"]
    assert result.notes is not None
    assert "does not match 'g_per_dl'" in result.notes


def test_lab_pdf_parser_rejects_unrecognized_text_values(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        "2026-05-10-qualitative.pdf",
        """
Lab: Gut Check
Collection date: 2026-05-10
Test | Value | Unit
Stool culture | brown | enum
""",
    )

    result = LabPdfParser().parse(report)

    assert result.measurements == []
    assert result.unmapped_metrics == ["stool-culture:unparseable_value"]
    assert result.notes is not None
    assert "unsupported value 'brown'" in result.notes


def test_lab_pdf_parser_skips_page_footers(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        "2026-04-12-footer.pdf",
        """
Laboratory: Centro Analisi Alfa
Accettazione del: 2026-04-12
Test | Value | Unit | Range
Page 1 of 5 |  |  |
WBC | 6.2 | 10^9/L | 4.0-10.0
""",
    )

    result = LabPdfParser().parse(report)

    assert [measurement.metric_id for measurement in result.measurements] == ["lab:wbc"]


def test_lab_pdf_parser_rejects_non_tabular_text(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        "2026-04-12-empty.pdf",
        "Laboratory: No Tables\nCollection date: 2026-04-12",
    )

    with pytest.raises(ValueError, match="no tabular lab rows"):
        LabPdfParser().parse(report)
