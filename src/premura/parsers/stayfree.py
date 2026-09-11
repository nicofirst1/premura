"""StayFree (Android digital-wellbeing app) legacy `.xls` export parser.

StayFree exports a **legacy binary `.xls`** workbook (not `.xlsx`; `openpyxl`
cannot read it, hence the `xlrd` dependency) with three sheets, each a wide
pivot table with one column per calendar day:

    Usage Time     - per-app/per-domain screen-time duration, one row per
                     tracked activity, e.g. "5m 12s" / "1h 5m 3s" / "0s".
    Usage Count    - same row/column layout, integer open-count strings.
    Device Unlocks - device-level daily unlock count, no per-app breakdown
                     and no Device column (dates start at column 1, not 2).

All three sheets share a trailing block of non-data rows (a "Total Usage"
column-sum row, a blank row, then two footer text rows: "Created by
..." / "Creation date: ..."). Rather than hardcoding row-count offsets (export
size varies), a row is treated as data only if its column-0 value is
non-empty and not a recognized footer label, keyed off whether the header
date columns actually parse as dates for that row shape.

Field resolution (CONTRACT.md decision tree, stop at first match): none of
"screen time", "app usage", "device unlocks" resolve via `suggest_metric()`
(verified against dim_metric.yaml at authoring time), and screen-time /
digital-wellbeing tracking is not a LOINC lab marker nor an IEEE 1752.1
wearable/physiological signal. It lands at rung 4: bare English canonical
names for a concept common to many apps (Android Digital Wellbeing, iOS
Screen Time, RescueTime, StayFree) rather than vendor-specific:

    screen_time_usage    (unit: s,     aggregate, P1D) <- Usage Time
    app_open_count       (unit: count, aggregate, P1D) <- Usage Count
    device_unlock_count  (unit: count, aggregate, P1D) <- Device Unlocks

Per DOCTRINE.md rule 2 ("guide, don't enumerate"), the ~1450 distinct
apps/domains in the source do NOT each get their own metric_id. Instead
`screen_time_usage` / `app_open_count` are one canonical metric per sheet with
the app/domain identifier carried in `Measurement.value_text` (mirroring
`daylio.py`'s `mood_score` -> qualitative label pattern) and the device name in
`raw_payload`.

Zero-duration/zero-count cells (the large majority - ~1453 apps x ~255 days)
are skipped without emitting a `Measurement` AND without recording a
`SkippedRow`: a legitimate "no usage that day" is not an error, and recording
it as a skip would flood `IngestBatch.skipped_rows` with ~370k non-actionable
entries for what is expected, common data shape. This mirrors the spirit of
`missing_data_policy: none` on these metrics - absence just means no usage.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import xlrd  # type: ignore[import-untyped]

from .base import IngestBatch, Measurement, SkippedRow, SourceDescriptor

SOURCE_KIND = "stayfree"

METRIC_USAGE_TIME = "screen_time_usage"
METRIC_USAGE_COUNT = "app_open_count"
METRIC_DEVICE_UNLOCKS = "device_unlock_count"

_DECLARED_METRICS = [METRIC_USAGE_TIME, METRIC_USAGE_COUNT, METRIC_DEVICE_UNLOCKS]

_SHEET_USAGE_TIME = "Usage Time"
_SHEET_USAGE_COUNT = "Usage Count"
_SHEET_DEVICE_UNLOCKS = "Device Unlocks"

_DATE_FORMAT = "%B %d, %Y"

_DURATION_RE = re.compile(r"^(?:(?P<h>\d+)h)?\s*(?:(?P<m>\d+)m)?\s*(?:(?P<s>\d+)s)?$")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "device"


def _dedupe_token(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_duration_seconds(text: str) -> float | None:
    """Parse a StayFree duration string ("5m 12s", "1h 5m 3s", "0s", ...) to seconds.

    Returns ``None`` if the string does not match any recognized duration shape
    (each of h/m/s is optional, but at least one component must be present).
    """
    stripped = text.strip()
    if not stripped:
        return None
    match = _DURATION_RE.match(stripped)
    if not match or not any(match.groups()):
        return None
    hours = int(match.group("h") or 0)
    minutes = int(match.group("m") or 0)
    seconds = int(match.group("s") or 0)
    return float(hours * 3600 + minutes * 60 + seconds)


def parse_date_header(text: str) -> datetime | None:
    """Parse a StayFree column header ("October 31, 2025") to a naive local-midnight
    datetime, or ``None`` if it is not a date (a footer/label cell)."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return datetime.strptime(stripped, _DATE_FORMAT)
    except ValueError:
        return None


def process_app_sheet(
    rows: list[list[Any]],
    metric_id: str,
    unit: str,
    parse_value: Any,
) -> tuple[list[Measurement], list[SkippedRow], dict[str, SourceDescriptor]]:
    """Process an already-extracted ``Usage Time`` / ``Usage Count`` sheet.

    ``rows`` is the full sheet as a list of row-value lists (row 0 = header:
    ``['', 'Device', <date>, <date>, ...]``). Pure function, no xlrd
    dependency, so it is unit-testable without a real `.xls` fixture.
    """
    measurements: list[Measurement] = []
    skipped: list[SkippedRow] = []
    descriptors: dict[str, SourceDescriptor] = {}

    header = rows[0]
    date_cols: list[tuple[int, datetime]] = []
    for col_index, header_value in enumerate(header[2:], start=2):
        parsed_date = parse_date_header(str(header_value))
        if parsed_date is not None:
            date_cols.append((col_index, parsed_date))

    for row_index, row in enumerate(rows[1:], start=1):
        app_label = str(row[0]).strip() if len(row) > 0 else ""
        device = str(row[1]).strip() if len(row) > 1 else ""
        if not app_label or not device:
            # Footer / total rows ("Total Usage", blank row, "Created by
            # ...", "Creation date: ...") never carry both an app label and a
            # device, so this is the structural (not hardcoded-index) skip.
            continue

        source_id = f"{SOURCE_KIND}:{_slug(device)}"
        descriptors.setdefault(
            source_id,
            SourceDescriptor(source_id=source_id, source_kind=SOURCE_KIND, device_model=device),
        )

        for col_index, ts in date_cols:
            if col_index >= len(row):
                continue
            raw_value = str(row[col_index]).strip()
            value = parse_value(raw_value)
            if value is None:
                skipped.append(
                    SkippedRow(
                        raw_field=f"rows[{row_index}]:{ts.date().isoformat()}",
                        reason=f"unparseable {metric_id} value {raw_value!r} for {app_label!r}",
                    )
                )
                continue
            if value == 0:
                # ponytail: legitimate "no usage" is not an error - skip
                # silently rather than emit ~370k zero rows or skip entries.
                continue

            measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id=metric_id,
                    unit=unit,
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    value_text=app_label,
                    source_uuid=_dedupe_token(metric_id, ts.date().isoformat(), app_label, device),
                    raw_payload={"device": device},
                )
            )

    return measurements, skipped, descriptors


def process_device_unlocks_sheet(
    rows: list[list[Any]],
) -> tuple[list[Measurement], list[SkippedRow], dict[str, SourceDescriptor]]:
    """Process an already-extracted ``Device Unlocks`` sheet.

    Layout differs from the app sheets: no Device column, dates start at
    column 1, and there is exactly one data row (row 1, labeled
    ``Device Unlocks``). Pure function, unit-testable without a fixture.
    """
    measurements: list[Measurement] = []
    skipped: list[SkippedRow] = []
    source_id = f"{SOURCE_KIND}:device"
    descriptors = {
        source_id: SourceDescriptor(source_id=source_id, source_kind=SOURCE_KIND),
    }

    header = rows[0]
    date_cols: list[tuple[int, datetime]] = []
    for col_index, header_value in enumerate(header[1:], start=1):
        parsed_date = parse_date_header(str(header_value))
        if parsed_date is not None:
            date_cols.append((col_index, parsed_date))

    if len(rows) < 2:
        return measurements, skipped, descriptors

    data_row = rows[1]
    row_label = str(data_row[0]).strip() if data_row else ""
    if row_label != "Device Unlocks":
        return measurements, skipped, descriptors

    for col_index, ts in date_cols:
        if col_index >= len(data_row):
            continue
        raw_value = str(data_row[col_index]).strip()
        try:
            value = float(int(raw_value))
        except ValueError:
            skipped.append(
                SkippedRow(
                    raw_field=f"device_unlocks:{ts.date().isoformat()}",
                    reason=f"unparseable device_unlock_count value {raw_value!r}",
                )
            )
            continue
        if value == 0:
            continue
        measurements.append(
            Measurement(
                ts_utc=ts,
                metric_id=METRIC_DEVICE_UNLOCKS,
                unit="count",
                source_id=source_id,
                source_kind=SOURCE_KIND,
                value_num=value,
                source_uuid=_dedupe_token(METRIC_DEVICE_UNLOCKS, ts.date().isoformat()),
            )
        )

    return measurements, skipped, descriptors


def _parse_count(raw: str) -> float | None:
    try:
        return float(int(raw))
    except ValueError:
        return None


def _sheet_rows(book: xlrd.book.Book, sheet_name: str) -> list[list[Any]]:
    sheet = book.sheet_by_name(sheet_name)
    return [sheet.row_values(r) for r in range(sheet.nrows)]


class StayFreeParser:
    """Parse a StayFree Android digital-wellbeing `.xls` export."""

    source_kind = SOURCE_KIND
    language_hint: str | None = "en"

    def declares_metrics(self) -> list[str]:
        return list(_DECLARED_METRICS)

    def parse(self, path: Path) -> IngestBatch:
        batch = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)

        book = xlrd.open_workbook(str(path))

        usage_time_measurements, usage_time_skipped, usage_time_sources = process_app_sheet(
            _sheet_rows(book, _SHEET_USAGE_TIME),
            METRIC_USAGE_TIME,
            "s",
            parse_duration_seconds,
        )
        usage_count_measurements, usage_count_skipped, usage_count_sources = process_app_sheet(
            _sheet_rows(book, _SHEET_USAGE_COUNT),
            METRIC_USAGE_COUNT,
            "count",
            _parse_count,
        )
        unlock_measurements, unlock_skipped, unlock_sources = process_device_unlocks_sheet(
            _sheet_rows(book, _SHEET_DEVICE_UNLOCKS)
        )

        batch.measurements.extend(usage_time_measurements)
        batch.measurements.extend(usage_count_measurements)
        batch.measurements.extend(unlock_measurements)
        batch.skipped_rows.extend(usage_time_skipped)
        batch.skipped_rows.extend(usage_count_skipped)
        batch.skipped_rows.extend(unlock_skipped)
        batch.source_descriptors.update(usage_time_sources)
        batch.source_descriptors.update(usage_count_sources)
        batch.source_descriptors.update(unlock_sources)

        batch.validate()
        return batch


__all__ = ["StayFreeParser", "parse_date_header", "parse_duration_seconds"]
