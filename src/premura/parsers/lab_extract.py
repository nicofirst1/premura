"""Lab-report extraction helpers.

Real PDFs are extracted locally with docling when available. Non-PDF inputs are
treated as already-normalized text so the parser contract stays easy to test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_report_text(path: Path) -> str:
    """Return extractor-normalized text for one lab report artifact."""
    data = path.read_bytes()
    if not data:
        raise ValueError(f"empty lab report: {path}")
    if _looks_like_pdf(data):
        return _extract_pdf_text_with_docling(path)
    text = data.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise ValueError(f"empty lab report: {path}")
    return text


def _looks_like_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def _extract_pdf_text_with_docling(path: Path) -> str:
    converter = _build_docling_converter()
    result = converter.convert(str(path))
    text = result.document.export_to_markdown().strip()
    if not text:
        raise ValueError(f"docling returned no text for {path}")
    return text


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
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise RuntimeError(
            "docling is required for real PDF lab ingestion; install it before using "
            "`hpipe ingest --source lab` on PDFs"
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


__all__ = ["extract_report_text"]
