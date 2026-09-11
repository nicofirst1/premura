"""FeelingsJournal CSV parser.

FeelingsJournal exports one row per journal entry with a naive local
timestamp and a hierarchical "feelings wheel" emotion label (Primary /
Secondary / Tertiary Feeling), plus an optional free-text comment and an
optional tags field. The parser stores the primary feeling as a point-in-time
categorical observation, keeping the secondary/tertiary labels and tags in
the row payload so the hierarchy isn't lost even though only the primary
feeling is the canonical value. Free-text comments are stored as clinical
notes, exactly like Daylio's note fields.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

from .base import (
    ClinicalNote,
    IngestBatch,
    Measurement,
    SkippedRow,
    SourceDescriptor,
)

SOURCE_KIND = "feelings_journal"
SOURCE_ID = "feelings_journal:app"

REQUIRED_COLUMNS = {"Date", "Primary Feeling"}
_DECLARED_METRICS = ["feeling"]
_FEELING_UNIT = "feeling_label"


def _dedupe_token(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _split_tags(value: str | None) -> list[str]:
    raw = _clean(value)
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.strip())


class FeelingsJournalParser:
    """Parse FeelingsJournal's CSV export into feeling observations and notes."""

    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return list(_DECLARED_METRICS)

    def parse(self, path: Path) -> IngestBatch:
        batch = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)
        batch.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID,
            source_kind=SOURCE_KIND,
            app_name="FeelingsJournal",
        )

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing = REQUIRED_COLUMNS - fieldnames
            if missing:
                raise ValueError(f"{path.name}: missing FeelingsJournal columns: {sorted(missing)}")
            for index, row in enumerate(reader):
                self._parse_row(index, row, batch)

        batch.validate()
        return batch

    def _parse_row(self, index: int, row: dict[str, str], batch: IngestBatch) -> None:
        date_raw = _clean(row.get("Date"))
        if not date_raw:
            batch.skipped_rows.append(
                SkippedRow(raw_field=f"rows[{index}]:Date", reason="missing Date")
            )
            return
        try:
            ts = _parse_timestamp(date_raw)
        except ValueError:
            batch.skipped_rows.append(
                SkippedRow(
                    raw_field=f"rows[{index}]:Date",
                    reason=f"unparseable FeelingsJournal timestamp {date_raw!r}",
                )
            )
            return

        primary = _clean(row.get("Primary Feeling"))
        if not primary:
            batch.skipped_rows.append(
                SkippedRow(
                    raw_field=f"rows[{index}]:Primary Feeling",
                    reason="missing Primary Feeling",
                )
            )
            return

        secondary = _clean(row.get("Secondary Feeling")) or None
        tertiary = _clean(row.get("Tertiary Feeling")) or None
        tags_raw = _clean(row.get("Tags"))
        tags = _split_tags(row.get("Tags"))

        source_uuid = _dedupe_token(date_raw, primary, secondary or "", tertiary or "", tags_raw)
        batch.measurements.append(
            Measurement(
                ts_utc=ts,
                metric_id="feeling",
                unit=_FEELING_UNIT,
                source_id=SOURCE_ID,
                source_kind=SOURCE_KIND,
                value_text=primary,
                local_tz=None,
                source_uuid=f"feeling:{source_uuid}",
                raw_payload={
                    "primary_feeling": primary,
                    "secondary_feeling": secondary,
                    "tertiary_feeling": tertiary,
                    "tags": tags,
                },
            )
        )

        comment = _clean(row.get("Comment"))
        if comment:
            batch.clinical_notes.append(
                ClinicalNote(
                    ts_utc=ts,
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    text=comment,
                    raw_payload={"primary_feeling": primary},
                )
            )


__all__ = ["FeelingsJournalParser"]
