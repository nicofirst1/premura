"""Clinical lab parser over extractor-normalized PDF text.

This parser intentionally stays extraction-engine-agnostic for now. It expects
the chosen extractor (docling or a fallback) to yield text where result-table
rows are preserved line-by-line, typically with ``|`` or tab separators.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import IngestBatch, Measurement, SourceDescriptor
from .lookup import metric_definition, metric_ids, suggest_metric

SOURCE_KIND = "lab_pdf"
_SKIP_VALUES = {"folgt", "to follow", "pending"}
_TEXT_VALUES = {"negativ", "negative", "assenti", "absent", "trace", "traces", "nr"}
_SOURCE_PATTERNS = (
    re.compile(r"^(?:lab|laboratory)\s*:\s*(?P<value>.*)$", re.IGNORECASE),
    re.compile(r"^laboratorio\s*:\s*(?P<value>.*)$", re.IGNORECASE),
)
_DATE_PATTERNS = (
    re.compile(
        r"(?:accettazione del|prelievo del|sample date|collection date)\s*:?\s*"
        r"(?P<value>\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:accettazione del|prelievo del|sample date|collection date)\s*:?\s*"
        r"(?P<value>\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    ),
    re.compile(r"(?:entnahmetag|eingang)\s*:?\s*(?P<value>\d{2}\.\d{2}\.\d{4})", re.IGNORECASE),
)
_FILENAME_DATE = re.compile(r"(?P<value>\d{4}[-_]?\d{2}[-_]?\d{2})")
_UNIT_ALIASES = {
    "%": "pct",
    "g/dl": "g_per_dl",
    "mg/dl": "mg_per_dl",
    "u/l": "U_per_l",
    "10^9/l": "10^9_per_l",
    "10^12/l": "10^12_per_l",
    "10e9/l": "10^9_per_l",
    "10e12/l": "10^12_per_l",
}


@dataclass(slots=True)
class _ParsedRow:
    test_name: str
    raw_value: str
    raw_unit: str | None
    reference_range: str | None
    lab_flag: str | None


@dataclass(slots=True)
class _RowIssue:
    reason: str
    message: str


class LabPdfParser:
    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return sorted(metric_ids(prefix="lab:"))

    def parse(self, path: Path) -> IngestBatch:
        text = self._extract_text(path)
        collection_dt = _extract_collection_datetime(text, path)
        source_id = _extract_source_id(text, path)

        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
            source_descriptors={
                source_id: SourceDescriptor(source_id=source_id, source_kind=SOURCE_KIND)
            },
        ).attach_source_artifact(path)

        parsed_any_row = False
        for row in _iter_rows(text):
            parsed_any_row = True
            metric_id = suggest_metric(row.test_name)
            if metric_id is None or not metric_id.startswith("lab:"):
                _record_row_issue(
                    result,
                    row,
                    reason="unknown_metric",
                    message=f"unmapped lab field: {row.test_name}",
                )
                continue

            measurement, issue = _measurement_from_row(
                row,
                metric_id=metric_id,
                source_id=source_id,
                collection_dt=collection_dt,
            )
            if measurement is not None:
                result.measurements.append(measurement)
            elif issue is not None:
                _record_row_issue(result, row, reason=issue.reason, message=issue.message)

        if not parsed_any_row:
            raise ValueError(
                "lab_pdf parser found no tabular lab rows; extractor-normalized text is required"
            )

        result.validate()
        return result

    def _extract_text(self, path: Path) -> str:
        data = path.read_bytes()
        text = data.decode("utf-8-sig", errors="replace").strip()
        if not text:
            raise ValueError(f"empty lab report: {path}")
        return text


def _iter_rows(text: str) -> list[_ParsedRow]:
    rows: list[_ParsedRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            parts = [part.strip() for part in line.split("|")]
        elif "\t" in line:
            parts = [part.strip() for part in line.split("\t")]
        else:
            continue
        if len(parts) < 2:
            continue
        if _looks_like_header(parts[0], parts[1]) or _looks_like_non_result_row(parts):
            continue
        rows.append(
            _ParsedRow(
                test_name=parts[0],
                raw_value=parts[1],
                raw_unit=parts[2] or None if len(parts) > 2 else None,
                reference_range=parts[3] or None if len(parts) > 3 else None,
                lab_flag=parts[4] or None if len(parts) > 4 else None,
            )
        )
    return rows


def _measurement_from_row(
    row: _ParsedRow,
    *,
    metric_id: str,
    source_id: str,
    collection_dt: datetime,
    ) -> tuple[Measurement | None, _RowIssue | None]:
    definition = metric_definition(metric_id)
    if definition is None:
        return None, _RowIssue("missing_metric_definition", f"missing ontology row: {metric_id}")

    parsed_num, parsed_text = _parse_value(row.raw_value)
    if parsed_num is None and parsed_text is None:
        return None, _RowIssue(
            "unparseable_value",
            f"skipped {row.test_name}: unsupported value {row.raw_value!r}",
        )

    canonical_unit = definition["canonical_unit"]
    normalized_unit = _normalize_unit(row.raw_unit) if row.raw_unit else canonical_unit
    if parsed_num is not None and normalized_unit != canonical_unit:
        return None, _RowIssue(
            "unit_mismatch",
            f"skipped {row.test_name}: unit {normalized_unit!r} does not match {canonical_unit!r}",
        )

    payload: dict[str, Any] = {
        "original_test_name": row.test_name,
        "original_unit": row.raw_unit,
        "reference_range_string": row.reference_range,
        "lab_flag": row.lab_flag,
    }

    return (
        Measurement(
            ts_utc=collection_dt,
            metric_id=metric_id,
            unit=canonical_unit if parsed_num is not None else normalized_unit,
            source_id=source_id,
            source_kind=SOURCE_KIND,
            value_num=parsed_num,
            value_text=parsed_text,
            source_uuid=_measurement_uuid(metric_id, source_id, collection_dt),
            raw_payload=payload,
        ),
        None,
    )


def _parse_value(raw_value: str) -> tuple[float | None, str | None]:
    value = raw_value.strip()
    if not value:
        return None, None

    lowered = _normalize_text(value)
    if lowered in _SKIP_VALUES:
        return None, None
    if lowered in _TEXT_VALUES:
        return None, lowered

    scientific = re.fullmatch(r"[<>]?\s*(\d+(?:[.,]\d+)?)\s*x\s*10\^(\d+)", lowered)
    if scientific is not None:
        mantissa = float(scientific.group(1).replace(",", "."))
        exponent = int(scientific.group(2))
        return mantissa * (10**exponent), None

    numeric = lowered.replace(",", ".")
    numeric = re.sub(r"^[<>]\s*", "", numeric)
    try:
        return float(numeric), None
    except ValueError:
        return None, None


def _extract_collection_datetime(text: str, path: Path) -> datetime:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        parsed = _parse_date(match.group("value"))
        if parsed is not None:
            return parsed
    match = _FILENAME_DATE.search(path.stem)
    if match is not None:
        parsed = _parse_date(match.group("value").replace("_", "-"))
        if parsed is not None:
            return parsed
    raise ValueError(f"could not infer collection date from {path.name}")


def _extract_source_id(text: str, path: Path) -> str:
    lines = [line.strip() for line in text.splitlines()]
    for index, stripped in enumerate(lines):
        for pattern in _SOURCE_PATTERNS:
            match = pattern.match(stripped)
            if match is not None:
                value = match.group("value").strip()
                if value:
                    return f"lab:{_slugify(value)}"
                for candidate in lines[index + 1 :]:
                    if candidate and ":" not in candidate:
                        return f"lab:{_slugify(candidate)}"
                break
    return f"lab:{_slugify(path.stem)}"


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _normalize_unit(value: str) -> str:
    normalized = _normalize_text(value)
    return _UNIT_ALIASES.get(normalized, value.strip())


def _measurement_uuid(metric_id: str, source_id: str, collection_dt: datetime) -> str:
    return f"{metric_id}:{source_id}:{collection_dt.isoformat(sep=' ')}"


def _looks_like_header(first: str, second: str) -> bool:
    header_left = _normalize_text(first)
    header_right = _normalize_text(second)
    return header_left in {"test", "parameter", "exam", "esame"} or header_right in {
        "value",
        "result",
        "risultato",
    }


def _looks_like_non_result_row(parts: list[str]) -> bool:
    normalized = [_normalize_text(part) for part in parts if part.strip()]
    if not normalized:
        return True
    joined = " | ".join(normalized)
    if re.fullmatch(r"page\s+\d+\s+of\s+\d+", normalized[0]):
        return True
    if any(part in {"page", "pagina"} for part in normalized):
        return True
    return "page " in joined and " of " in joined


def _record_row_issue(result: IngestBatch, row: _ParsedRow, *, reason: str, message: str) -> None:
    result.unmapped_metrics.append(f"{_slugify(row.test_name)}:{reason}")
    result.notes = f"{result.notes}; {message}" if result.notes else message


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "lab"


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized.lower()).strip()


__all__ = ["LabPdfParser"]
