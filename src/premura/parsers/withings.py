"""Withings "Download your data" CSV export parser (observation seam).

Withings' GDPR data-export delivers a **zip of one CSV per data category** (the
same zip-of-CSVs shape MyFitnessPal's export uses, but for the observation
seam rather than intake). Real-world member filenames handled:

    weight.csv               — Date,Weight (kg),Fat mass (kg),Fat free mass (kg),
                                Fat Ratio (%),Bone mass (kg),Muscle mass (kg),
                                Hydration (kg),Comments,Category
    bp.csv                    — Date,Systolic (mmHg),Diastolic (mmHg),
                                Heart rate (bpm),Pulse wave velocity (m/s)
    raw_tracker_hr.csv        — Date,Heart rate (bpm)
    aggregates_steps.csv      — Date,Steps
    sleep.csv                 — from,to,deep (s),light (s),rem (s),wakeup (s)

No live Withings export was available to validate against at authoring time
(Phase 4 issue #33 note: "real vendor *format*, synthetic *data*"); these
headers are this parser's documented contract surface, built from Withings'
public export documentation. A follow-up against a real export is tracked
separately and does not block this parser (unmapped/skipped-row surfaces exist
precisely so a header drift is caught and declared, never silently dropped).

Field resolution (CONTRACT.md decision tree, stop at first match):
    weight, bp_systolic, bp_diastolic, heart_rate, steps, sleep_session,
    sleep_deep_pct, body_fat_pct, lean_body_mass, muscle_mass, bone_mass,
    body_water_mass  -> step 1, existing dim_metric.yaml aliases/metric_ids.
    fat_mass          -> step 4, bare English canonical name (new; a reusable
                          cross-vendor body-composition concept, not Withings-
                          specific).
    vendor:withings:pulse_wave_velocity -> step 5, vendor fallback (Withings
                          BPM Core-specific vascular reading with no existing
                          alias, LOINC, or IEEE 1752.1 coverage in this
                          ontology).
    weight.Category    -> structural provenance metadata, no metric home ->
                          unmapped_metrics.

Blank cells are "unknown", never fabricated as zero; a present-but-unparseable
cell becomes a `skipped_rows` entry with a reason instead of being dropped
silently.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import zipfile
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from dateutil import parser as dtparser

from .base import IngestBatch, Interval, Measurement, RoutingPreview, SkippedRow, SourceDescriptor

log = logging.getLogger(__name__)
SOURCE_KIND = "withings"
SOURCE_ID = "withings:account"

_PWV_METRIC = "vendor:withings:pulse_wave_velocity"


def _parse_ts(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        ts = dtparser.parse(raw, dayfirst=False)
    except (ValueError, TypeError, OverflowError):
        return None
    if ts.tzinfo is not None:
        ts = ts.astimezone().replace(tzinfo=None)
    return ts


def _parse_float(raw: str | None) -> float | None:
    """None for a blank cell (unknown); raises ValueError for a bad cell."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return float(raw)


def _synth_uuid(*parts: object) -> str:
    seed = "|".join(str(p) for p in parts if p is not None)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()  # noqa: S324


# --------------------------- zip member dispatch --------------------------- #

_HANDLERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"weight\.csv$", re.IGNORECASE), "_handle_weight"),
    (re.compile(r"bp\.csv$", re.IGNORECASE), "_handle_bp"),
    (re.compile(r"raw_tracker_hr\.csv$", re.IGNORECASE), "_handle_heart_rate"),
    (re.compile(r"aggregates_steps\.csv$", re.IGNORECASE), "_handle_steps"),
    (re.compile(r"sleep\.csv$", re.IGNORECASE), "_handle_sleep"),
]


class WithingsParser:
    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return sorted(
            {
                "weight",
                "fat_mass",
                "body_fat_pct",
                "lean_body_mass",
                "muscle_mass",
                "bone_mass",
                "body_water_mass",
                "bp_systolic",
                "bp_diastolic",
                "heart_rate",
                _PWV_METRIC,
                "steps",
                "sleep_session",
                "sleep_deep_pct",
            }
        )

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)
        result.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID,
            source_kind=SOURCE_KIND,
        )
        unmapped: set[str] = set()
        unhandled: dict[str, int] = {}
        matched_any = False
        for member_name, text in self._iter_csv_members(path):
            handler_name = self._dispatch_name(member_name)
            if handler_name is None:
                stem = member_name.split("/")[-1]
                unhandled[stem] = unhandled.get(stem, 0) + 1
                continue
            matched_any = True
            rows = list(csv.DictReader(io.StringIO(text)))
            getattr(self, handler_name)(rows, result, unmapped)

        if not matched_any:
            raise ValueError(
                f"{path.name}: no recognized Withings export member "
                "(expected one of weight.csv, bp.csv, raw_tracker_hr.csv, "
                "aggregates_steps.csv, sleep.csv)"
            )
        if unhandled:
            note = "unhandled files: " + ", ".join(
                f"{name} ({n})" for name, n in sorted(unhandled.items())
            )
            result.notes = (result.notes + "; " if result.notes else "") + note

        result.unmapped_metrics = sorted(unmapped)
        result.validate()
        return result

    def _iter_csv_members(self, path: Path) -> list[tuple[str, str]]:
        try:
            with zipfile.ZipFile(path) as zf:
                return [
                    (info.filename, zf.read(info).decode("utf-8-sig"))
                    for info in zf.infolist()
                    if not info.is_dir()
                ]
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError(f"{path.name}: expected a Withings export zip") from exc

    def _dispatch_name(self, member_name: str) -> str | None:
        for pattern, handler_name in _HANDLERS:
            if pattern.search(member_name):
                return handler_name
        return None

    def preview_routing(self, member_names: Sequence[str]) -> RoutingPreview:
        """Name-based dry-run routing preview — read-only twin of ingest dispatch."""
        return RoutingPreview(entries=[(name, self._dispatch_name(name)) for name in member_names])

    # ------------------------------- handlers ------------------------------ #

    def _handle_weight(
        self, rows: list[dict[str, str]], result: IngestBatch, unmapped: set[str]
    ) -> None:
        field_map = (
            ("Weight (kg)", "weight", "kg"),
            ("Fat mass (kg)", "fat_mass", "kg"),
            ("Fat free mass (kg)", "lean_body_mass", "kg"),
            ("Fat Ratio (%)", "body_fat_pct", "pct"),
            ("Bone mass (kg)", "bone_mass", "kg"),
            ("Muscle mass (kg)", "muscle_mass", "kg"),
            ("Hydration (kg)", "body_water_mass", "kg"),
        )
        for row in rows:
            ts = _parse_ts(row.get("Date", ""))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="weight.Date",
                        reason=f"unparseable Date: {row.get('Date')!r}",
                    )
                )
                continue
            uuid_base = _synth_uuid("weight", ts.isoformat())
            comments = (row.get("Comments") or "").strip() or None
            for col, metric_id, unit in field_map:
                try:
                    value = _parse_float(row.get(col))
                except ValueError:
                    result.skipped_rows.append(
                        SkippedRow(
                            raw_field=f"weight.{col}",
                            reason=f"non-numeric value: {row.get(col)!r}",
                        )
                    )
                    continue
                if value is None:
                    continue  # blank cell: unknown, not zero
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id=metric_id,
                        unit=unit,
                        source_id=SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=value,
                        value_text=comments if metric_id == "weight" else None,
                        source_uuid=f"{uuid_base}:{metric_id}",
                    )
                )
            category = (row.get("Category") or "").strip()
            if category:
                unmapped.add(f"vendor:{SOURCE_KIND}:weight.Category")

    def _handle_bp(
        self, rows: list[dict[str, str]], result: IngestBatch, unmapped: set[str]
    ) -> None:
        field_map = (
            ("Systolic (mmHg)", "bp_systolic", "mmHg"),
            ("Diastolic (mmHg)", "bp_diastolic", "mmHg"),
            ("Heart rate (bpm)", "heart_rate", "bpm"),
            ("Pulse wave velocity (m/s)", _PWV_METRIC, "m/s"),
        )
        for row in rows:
            ts = _parse_ts(row.get("Date", ""))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(raw_field="bp.Date", reason=f"unparseable Date: {row.get('Date')!r}")
                )
                continue
            uuid_base = _synth_uuid("bp", ts.isoformat())
            for col, metric_id, unit in field_map:
                try:
                    value = _parse_float(row.get(col))
                except ValueError:
                    result.skipped_rows.append(
                        SkippedRow(
                            raw_field=f"bp.{col}", reason=f"non-numeric value: {row.get(col)!r}"
                        )
                    )
                    continue
                if value is None:
                    continue
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id=metric_id,
                        unit=unit,
                        source_id=SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=value,
                        source_uuid=f"{uuid_base}:{metric_id}",
                    )
                )

    def _handle_heart_rate(
        self, rows: list[dict[str, str]], result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in rows:
            ts = _parse_ts(row.get("Date", ""))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="raw_tracker_hr.Date",
                        reason=f"unparseable Date: {row.get('Date')!r}",
                    )
                )
                continue
            try:
                value = _parse_float(row.get("Heart rate (bpm)"))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="raw_tracker_hr.Heart rate (bpm)",
                        reason=f"non-numeric value: {row.get('Heart rate (bpm)')!r}",
                    )
                )
                continue
            if value is None:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id="heart_rate",
                    unit="bpm",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    source_uuid=_synth_uuid("raw_tracker_hr", ts.isoformat()),
                )
            )

    def _handle_steps(
        self, rows: list[dict[str, str]], result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in rows:
            day = _parse_ts(row.get("Date", ""))
            if day is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="aggregates_steps.Date",
                        reason=f"unparseable Date: {row.get('Date')!r}",
                    )
                )
                continue
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            try:
                value = _parse_float(row.get("Steps"))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="aggregates_steps.Steps",
                        reason=f"non-numeric value: {row.get('Steps')!r}",
                    )
                )
                continue
            if value is None:
                continue
            result.intervals.append(
                Interval(
                    start_utc=start,
                    end_utc=start + timedelta(days=1),
                    metric_id="steps",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    source_uuid=_synth_uuid("steps", start.isoformat()),
                )
            )

    def _handle_sleep(
        self, rows: list[dict[str, str]], result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in rows:
            start = _parse_ts(row.get("from", ""))
            end = _parse_ts(row.get("to", ""))
            if start is None or end is None or end < start:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="sleep.from/to",
                        reason=(
                            f"unparseable or inverted session: "
                            f"from={row.get('from')!r} to={row.get('to')!r}"
                        ),
                    )
                )
                continue
            uuid_base = _synth_uuid("sleep", start.isoformat())
            result.intervals.append(
                Interval(
                    start_utc=start,
                    end_utc=end,
                    metric_id="sleep_session",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=(end - start).total_seconds() / 3600.0,
                    source_uuid=f"{uuid_base}:session",
                )
            )

            stage_cols = ("deep (s)", "light (s)", "rem (s)", "wakeup (s)")
            try:
                stage_values = [_parse_float(row.get(c)) for c in stage_cols]
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="sleep.stage_durations",
                        reason="non-numeric stage duration; sleep_deep_pct not derived",
                    )
                )
                continue
            if any(v is None for v in stage_values):
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="sleep.stage_durations",
                        reason="incomplete stage durations; sleep_deep_pct not derived",
                    )
                )
                continue
            deep_s, light_s, rem_s, wakeup_s = stage_values
            total_s = (deep_s or 0.0) + (light_s or 0.0) + (rem_s or 0.0) + (wakeup_s or 0.0)
            if total_s <= 0:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=start,
                    metric_id="sleep_deep_pct",
                    unit="pct",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=100.0 * (deep_s or 0.0) / total_s,
                    source_uuid=f"{uuid_base}:deep_pct",
                )
            )


__all__ = ["SOURCE_ID", "SOURCE_KIND", "WithingsParser"]
