"""Lab-report extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ExtractedLabReport:
    measurement_text: str
    commentary_text: str | None
    measurement_extractor: str
    commentary_extractor: str | None = None


def extract_report(path: Path) -> ExtractedLabReport:
    """Return the measurement/commentary extraction bundle for one report."""
    data = path.read_bytes()
    if not data:
        raise ValueError(f"empty lab report: {path}")
    if not _looks_like_pdf(data):
        text = data.decode("utf-8-sig", errors="replace").strip()
        if not text:
            raise ValueError(f"empty lab report: {path}")
        return ExtractedLabReport(
            measurement_text=text,
            commentary_text=_extract_commentary_text(text),
            measurement_extractor="fixture-text",
            commentary_extractor="fixture-text" if _extract_commentary_text(text) else None,
        )

    standard_markdown, standard_text = _extract_pdf_with_docling(path)
    commentary_text = _extract_commentary_text(standard_text)
    if _is_stool_report(path, standard_text):
        vlm_text = _extract_pdf_text_with_vlm(path)
        return ExtractedLabReport(
            measurement_text=vlm_text,
            commentary_text=commentary_text,
            measurement_extractor="docling-vlm",
            commentary_extractor="docling-standard" if commentary_text else None,
        )

    return ExtractedLabReport(
        measurement_text=standard_markdown,
        commentary_text=commentary_text,
        measurement_extractor="docling-standard",
        commentary_extractor="docling-standard" if commentary_text else None,
    )


def extract_report_text(path: Path) -> str:
    """Return the measurement-oriented extraction output for one report."""
    return extract_report(path).measurement_text


def _looks_like_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def _extract_pdf_with_docling(path: Path) -> tuple[str, str]:
    converter = _build_docling_converter()
    result = converter.convert(str(path))
    markdown = result.document.export_to_markdown().strip()
    text = result.document.export_to_text().strip()
    if not markdown and not text:
        raise ValueError(f"docling returned no text for {path}")
    return markdown, text


def _extract_pdf_text_with_docling(path: Path) -> str:
    markdown, _text = _extract_pdf_with_docling(path)
    if not markdown:
        raise ValueError(f"docling returned no table-friendly markdown for {path}")
    return markdown


def _extract_pdf_text_with_vlm(path: Path) -> str:
    converter = _build_docling_vlm_converter()
    result = converter.convert(str(path))
    text = result.document.export_to_text().strip()
    if not text:
        raise ValueError(f"docling VLM returned no text for {path}")
    return text


def _extract_commentary_text(text: str) -> str | None:
    if not contains_diagnostic_language(text):
        return None
    return text


def contains_diagnostic_language(text: str) -> bool:
    lowered = text.lower()
    commentary_tokens = ("beurteilung", "diagn", "therapie", "recommend", "hinweis")
    return any(token in lowered for token in commentary_tokens)


def _is_stool_report(path: Path, standard_text: str) -> bool:
    path_hint = any("stool" in part.lower() for part in path.parts)
    stool_tokens = ("stuhl", "floraindex", "pankreaselastase")
    text_hint = any(token in standard_text.lower() for token in stool_tokens)
    return path_hint or text_hint


def _build_docling_converter() -> Any:
    try:
        from docling.datamodel.accelerator_options import (  # type: ignore[import-not-found]
            AcceleratorDevice,
            AcceleratorOptions,
        )
        from docling.datamodel.base_models import InputFormat  # type: ignore[import-not-found]
        from docling.datamodel.pipeline_options import (  # type: ignore[import-not-found]
            PdfPipelineOptions,
        )
        from docling.document_converter import (  # type: ignore[import-not-found]
            DocumentConverter,
            PdfFormatOption,
        )
    except ImportError as exc:
        raise RuntimeError(
            "docling is required for real PDF lab ingestion; install it before using "
            "`premura ingest --source lab` on PDFs"
        ) from exc

    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4,
        device=AcceleratorDevice.CPU,
    )
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )


def _build_docling_vlm_converter() -> Any:
    try:
        from docling.datamodel import vlm_model_specs  # type: ignore[import-not-found]
        from docling.datamodel.base_models import InputFormat  # type: ignore[import-not-found]
        from docling.datamodel.pipeline_options import (  # type: ignore[import-not-found]
            VlmPipelineOptions,
        )
        from docling.document_converter import (  # type: ignore[import-not-found]
            DocumentConverter,
            PdfFormatOption,
        )
        from docling.pipeline.vlm_pipeline import VlmPipeline  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "mlx-vlm is required for the VLM lab extractor path; install the `lab` extra"
        ) from exc

    pipeline_options = VlmPipelineOptions(vlm_options=vlm_model_specs.GRANITEDOCLING_MLX)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=pipeline_options,
            )
        }
    )


__all__ = [
    "ExtractedLabReport",
    "contains_diagnostic_language",
    "extract_report",
    "extract_report_text",
]
