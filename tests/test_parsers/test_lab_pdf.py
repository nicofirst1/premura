from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from premura.parsers import lab_extract
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
    assert result.clinical_notes == []
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

Beurteilung: stool markers remain stable.
""",
    )

    result = LabPdfParser().parse(report)

    by_metric = {measurement.metric_id: measurement for measurement in result.measurements}
    assert len(result.clinical_notes) == 1
    assert result.clinical_notes[0].raw_payload is not None
    assert result.clinical_notes[0].raw_payload["contains_diagnostic_language"] is True
    assert by_metric["lab:stool_culture"].value_num is None
    assert by_metric["lab:stool_culture"].value_text == "negativ"
    assert by_metric["lab:stool_ova_parasites"].value_text == "assenti"
    assert "lab:stool_white_blood_cells" not in by_metric
    assert [(row.raw_field, row.reason) for row in result.skipped_rows] == [
        ("Stool white blood cells", "deferred_result")
    ]
    assert result.notes is not None
    assert "deferred result marker 'folgt'" in result.notes


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
    assert result.unmapped_metrics == ["unknown-analyte"]
    assert result.skipped_rows == []


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
    assert [(row.raw_field, row.reason) for row in result.skipped_rows] == [("Hb", "unit_mismatch")]
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
    assert [(row.raw_field, row.reason) for row in result.skipped_rows] == [
        ("Stool culture", "unparseable_value")
    ]
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


def test_lab_pdf_parser_uses_docling_path_for_real_pdf_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "2026-04-12-docling.pdf"
    report.write_bytes(b"%PDF-1.7\n%fake-pdf")

    monkeypatch.setattr(
        lab_extract,
        "_extract_pdf_with_docling",
        lambda path: (
            """
Laboratory: Centro Analisi Alfa
Accettazione del: 2026-04-12
Test | Value | Unit | Range
Hb | 14.1 | g/dL | 13.0-17.0
""",
            "",
        ),
    )

    result = LabPdfParser().parse(report)

    assert [measurement.metric_id for measurement in result.measurements] == ["lab:hemoglobin"]


def test_lab_extract_dispatches_stool_reports_to_vlm_measurements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "stool-report.pdf"
    report.write_bytes(b"%PDF-1.7\n%fake-pdf")

    monkeypatch.setattr(
        lab_extract,
        "_extract_pdf_with_docling",
        lambda path: ("standard-markdown", "Pankreaselastase im Stuhl\nBeurteilung"),
    )
    monkeypatch.setattr(lab_extract, "_extract_pdf_text_with_vlm", lambda path: "vlm-table")

    extracted = lab_extract.extract_report(report)

    assert extracted.measurement_text == "vlm-table"
    assert extracted.commentary_text == "Pankreaselastase im Stuhl\nBeurteilung"
    assert extracted.measurement_extractor == "docling-vlm"
    assert extracted.commentary_extractor == "docling-standard"


def test_lab_extract_keeps_blood_reports_on_standard_docling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "blood-report.pdf"
    report.write_bytes(b"%PDF-1.7\n%fake-pdf")

    monkeypatch.setattr(
        lab_extract,
        "_extract_pdf_with_docling",
        lambda path: ("| Hb | 14.1 | g/dL |", "plain blood text"),
    )

    extracted = lab_extract.extract_report(report)

    assert extracted.measurement_text == "| Hb | 14.1 | g/dL |"
    assert extracted.commentary_text is None
    assert extracted.measurement_extractor == "docling-standard"


def test_lab_pdf_parser_handles_stool_vlm_rows_with_commentary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "20240131-stool-vlm.pdf"
    report.write_bytes(b"%PDF-1.7\n%fake-pdf")

    monkeypatch.setattr(
        "premura.parsers.lab_pdf.extract_report",
        lambda path: lab_extract.ExtractedLabReport(
            measurement_text="""
| Pankreaselastase im Stuhl | 91,32 | g/g | >200 | 137,86 | FE |
| Gallensauren im Stuhl | 46,85 | mollI | <70<fcel> | FE | |
| Hamoglobin im Stuhl immunologisch | <10<fcel> | <10<fcel> | | | |
| Calprotectin | <17,90<fcel> | <50<fcel> | FE | | |
| Alpha 1-Antitrypsin | 6,0 | mg/dl | <27,5<fcel> | FE | |
| Anti-Transglutaminase AK i. Stuhl | 60,76 | U/ | <100<fcel> | FE | |
| Quant. Nachweis von Stickstoff | 0,20 | g/100g | <1,0 | FE | |
| Quant. Nachweis von Zucker | 3,60 | g/100g | <2,5 | FE | |
| Quant. Nachweis von Wasser | 84,50 | g/100g | 75 - 85 | FE | |
""",
            commentary_text="Beurteilung: stool profile still abnormal but improved.",
            measurement_extractor="docling-vlm",
            commentary_extractor="docling-standard",
        ),
    )

    result = LabPdfParser().parse(report)

    metrics = {measurement.metric_id for measurement in result.measurements}
    assert {
        "lab:stool_elastase",
        "lab:stool_bile_acids",
        "lab:stool_hemoglobin_immunologic",
        "lab:stool_calprotectin",
        "lab:stool_alpha_1_antitrypsin",
        "lab:stool_anti_transglutaminase",
        "lab:stool_nitrogen",
        "lab:stool_sugar",
        "lab:stool_water",
    } <= metrics
    assert len(result.clinical_notes) == 1


def test_loader_persists_clinical_notes(empty_warehouse, tmp_path: Path) -> None:
    from premura.parsers.base import ClinicalNote, IngestBatch, SourceDescriptor
    from premura.store.loader import load

    path = tmp_path / "note.txt"
    path.write_text("placeholder", encoding="utf-8")
    batch = IngestBatch(
        source_kind="lab_pdf",
        declared_metrics=["lab:hemoglobin"],
        source_descriptors={
            "lab:testlab": SourceDescriptor(source_id="lab:testlab", source_kind="lab_pdf")
        },
        clinical_notes=[
            ClinicalNote(
                ts_utc=datetime(2026, 5, 10),
                source_id="lab:testlab",
                source_kind="lab_pdf",
                text="Diagnostic impression: mild abnormality remains.",
                raw_payload={"contains_diagnostic_language": True},
            )
        ],
    ).attach_source_artifact(path)
    batch.validate()

    stats = load(empty_warehouse, batch)

    assert stats.rows_inserted == 1
    row = empty_warehouse.execute(
        "SELECT text FROM hp.fact_clinical_note WHERE source_id = 'lab:testlab'"
    ).fetchone()
    assert row is not None
    assert "Diagnostic impression" in row[0]


def test_real_pdf_requires_docling_when_not_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "2026-04-12-docling-missing.pdf"
    report.write_bytes(b"%PDF-1.7\n%fake-pdf")

    def _raise() -> None:
        raise RuntimeError("docling is required for real PDF lab ingestion")

    monkeypatch.setattr(lab_extract, "_build_docling_converter", _raise)

    with pytest.raises(RuntimeError, match="docling is required"):
        LabPdfParser().parse(report)
