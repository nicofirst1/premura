"""Daylio CSV parser.

Daylio exports one row per journal entry with a local date/time, a five-level
mood label, optional activity tags, and optional free-text note fields. The
parser stores the mood label as a point-in-time observation with a numeric
ordinal score for analysis while preserving the original label and activity tags
in the row payload. Free-text notes are stored as clinical notes so they remain
queryable through the existing narrative-note home, never printed by the parser.
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

SOURCE_KIND = "daylio"
SOURCE_ID = "daylio:app"

MOOD_SCORE: dict[str, int] = {
    "awful": 1,
    "bad": 2,
    "meh": 3,
    "good": 4,
    "rad": 5,
}

REQUIRED_COLUMNS = {"full_date", "time", "mood"}
_DECLARED_METRICS = ["mood_score"]


def _dedupe_token(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _split_activities(value: str | None) -> list[str]:
    raw = _clean(value)
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def _parse_timestamp(date_value: str, time_value: str) -> datetime:
    return datetime.strptime(f"{date_value.strip()} {time_value.strip()}", "%Y-%m-%d %H:%M")


class DaylioParser:
    """Parse Daylio's CSV export into mood observations and narrative notes."""

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
            app_name="Daylio",
        )

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing = REQUIRED_COLUMNS - fieldnames
            if missing:
                raise ValueError(f"{path.name}: missing Daylio columns: {sorted(missing)}")
            for index, row in enumerate(reader):
                self._parse_row(index, row, batch)

        batch.validate()
        return batch

    def _parse_row(self, index: int, row: dict[str, str], batch: IngestBatch) -> None:
        date_raw = _clean(row.get("full_date"))
        time_raw = _clean(row.get("time"))
        if not date_raw or not time_raw:
            batch.skipped_rows.append(
                SkippedRow(raw_field=f"rows[{index}]:timestamp", reason="missing full_date or time")
            )
            return
        try:
            ts = _parse_timestamp(date_raw, time_raw)
        except ValueError:
            batch.skipped_rows.append(
                SkippedRow(
                    raw_field=f"rows[{index}]:timestamp",
                    reason=f"unparseable Daylio timestamp {date_raw!r} {time_raw!r}",
                )
            )
            return

        mood_label = _clean(row.get("mood")).lower()
        score = MOOD_SCORE.get(mood_label)
        if score is None:
            batch.skipped_rows.append(
                SkippedRow(
                    raw_field=f"rows[{index}]:mood",
                    reason=f"unknown Daylio mood label {mood_label!r}",
                )
            )
            return

        activities = _split_activities(row.get("activities"))
        source_uuid = _dedupe_token(date_raw, time_raw, mood_label, _clean(row.get("activities")))
        batch.measurements.append(
            Measurement(
                ts_utc=ts,
                metric_id="mood_score",
                unit="score_1_5",
                source_id=SOURCE_ID,
                source_kind=SOURCE_KIND,
                value_num=float(score),
                value_text=mood_label,
                source_uuid=f"mood:{source_uuid}",
                raw_payload={
                    "mood": mood_label,
                    "activities": activities,
                    "activity_count": len(activities),
                    "weekday": _clean(row.get("weekday")) or None,
                    "scales_present": bool(_clean(row.get("scales"))),
                },
            )
        )

        note_title = _clean(row.get("note_title"))
        note = _clean(row.get("note"))
        if note_title or note:
            text = f"{note_title}\n\n{note}" if note_title and note else note_title or note
            batch.clinical_notes.append(
                ClinicalNote(
                    ts_utc=ts,
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    text=text,
                    raw_payload={"mood": mood_label, "activity_count": len(activities)},
                )
            )


__all__ = ["DaylioParser"]
