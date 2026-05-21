"""Body Measurement Tracker (cookapps) CSV parser.

Supports the **long format** export used by current versions of BMT — one row per
measurement, with the unit carried in a `Unit` column so the file is self-describing.

Long-format header (after any leading `#`-prefixed user-metadata lines):
    Measurement,Date,Value,Unit,Notes,DefinedKey,MeasurementType,LeftRight

A `Measurement` value of e.g. `weight | height | bodyfat | hips | waist | neck | ...`
maps to a stable metric_id; unknown ones become `bmt_custom:<slug>`. The `Unit`
column drives canonical conversion (kg, m, °C, etc.).

We also keep light support for the older **wide format** (one row per date with
`Weight,BodyFat,Muscle,...` columns) for backward compatibility with users still on
older app versions; in that mode we fall back to the config-driven kg/lb toggle.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

from dateutil import parser as dtparser

from ..config import settings
from .base import IngestBatch, Measurement, SourceDescriptor

log = logging.getLogger(__name__)
SOURCE_KIND = "bmt"

LB_TO_KG = 0.45359237
IN_TO_M = 0.0254
CM_TO_M = 0.01

# Long-format header signature.
LONG_HEADER = ("Measurement", "Date", "Value", "Unit")

# Map BMT's Measurement names (lowercase) → canonical (metric_id, canonical_unit).
LONG_METRIC_MAP: dict[str, tuple[str, str]] = {
    "weight": ("weight", "kg"),
    "height": ("height", "m"),
    "bodyfat": ("body_fat_pct", "pct"),
    "body_fat": ("body_fat_pct", "pct"),
    "musclemass": ("muscle_mass", "kg"),
    "muscle": ("muscle_mass", "kg"),
    "bodywater": ("body_water_mass", "kg"),
    "bonemass": ("bone_mass", "kg"),
    "bmi": ("bmi", "kg_per_m2"),
    "visceralfat": ("visceral_fat", "index"),
}


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "field"


def _parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return dtparser.parse(s, dayfirst=False)
    except (ValueError, TypeError):
        return None


def _convert_to_canonical(
    value: float, src_unit: str | None, target_unit: str
) -> tuple[float, str]:
    """Return (value_in_target, target_unit). Unknown conversions pass through."""
    if not src_unit:
        return value, target_unit
    u = src_unit.strip().lower()
    if target_unit == "kg":
        if u in ("kg",):
            return value, "kg"
        if u in ("lb", "lbs"):
            return value * LB_TO_KG, "kg"
        if u in ("g",):
            return value / 1000.0, "kg"
    elif target_unit == "m":
        if u in ("m",):
            return value, "m"
        if u in ("cm",):
            return value * CM_TO_M, "m"
        if u in ("in", "inch", "inches"):
            return value * IN_TO_M, "m"
    elif target_unit == "pct":
        if u in ("%", "pct"):
            return value, "pct"
    # Unknown: keep as-is and use the source unit so downstream code can see it.
    return value, src_unit


class BMTParser:
    source_kind = SOURCE_KIND

    def declares_metrics(self) -> list[str]:
        return sorted(
            {metric_id for metric_id, _unit in LONG_METRIC_MAP.values()}
            | {
                "bmi",
                "visceral_fat",
            }
        )

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)
        result.source_descriptors["bmt:device"] = SourceDescriptor(
            source_id="bmt:device",
            source_kind=SOURCE_KIND,
        )
        lines = self._read_data_lines(path)
        if not lines:
            result.validate()
            return result
        # Detect format by inspecting the header row.
        header = next(iter(csv.reader([lines[0]])))
        if all(h in header for h in LONG_HEADER):
            self._parse_long_format(lines, result)
        else:
            self._parse_wide_format(lines, result)
        result.validate()
        return result

    # --- shared file reader (strips '#'-prefix comments) ---

    @staticmethod
    def _read_data_lines(path: Path) -> list[str]:
        out: list[str] = []
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                out.append(line.rstrip("\n"))
        return out

    # --- long format (current BMT app exports) ---

    def _parse_long_format(self, lines: list[str], result: IngestBatch) -> None:
        reader = csv.DictReader(lines)
        for row in reader:
            self._emit_long_row(row, result)

    def _emit_long_row(self, row: dict[str, str], result: IngestBatch) -> None:
        date_str = (row.get("Date") or "").strip()
        if not date_str:
            return
        ts = _parse_date(date_str)
        if ts is None:
            log.warning("BMT: unparseable date %r", date_str)
            return
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        raw_val = (row.get("Value") or "").strip()
        try:
            value = float(raw_val)
        except (TypeError, ValueError):
            return
        unit_in = (row.get("Unit") or "").strip() or None
        m_name = (row.get("Measurement") or "").strip().lower()
        notes = (row.get("Notes") or "").strip() or None
        side = (row.get("LeftRight") or "").strip().lower()

        spec = LONG_METRIC_MAP.get(m_name)
        if spec:
            metric_id, target_unit = spec
            value, unit_out = _convert_to_canonical(value, unit_in, target_unit)
        else:
            unmapped = _slugify(m_name)
            if side in ("left", "right"):
                unmapped = f"{unmapped}_{side}"
            result.unmapped_metrics.append(unmapped)
            return

        result.measurements.append(
            Measurement(
                ts_utc=ts,
                metric_id=metric_id,
                unit=unit_out,
                source_id="bmt:device",
                source_kind=SOURCE_KIND,
                value_num=value,
                value_text=notes,
                source_uuid=_synthesize_uuid(date_str, m_name, raw_val, side or "none"),
            )
        )

    # --- legacy wide format ---

    def _parse_wide_format(self, lines: list[str], result: IngestBatch) -> None:
        reader = csv.DictReader(lines)
        w_unit = settings.parsers.bmt.weight_unit
        h_unit = settings.parsers.bmt.length_unit
        w_xform = (lambda v: v * LB_TO_KG) if w_unit == "lb" else (lambda v: v)
        h_xform = (lambda v: v * IN_TO_M) if h_unit == "in" else (lambda v: v / 100)

        known = {
            "Weight": ("weight", "kg", w_xform),
            "BodyFat": ("body_fat_pct", "pct", lambda v: v),
            "Muscle": ("muscle_mass", "kg", w_xform),
            "Water": ("body_water_mass", "kg", w_xform),
            "BMI": ("bmi", "kg_per_m2", lambda v: v),
            "Visceral": ("visceral_fat", "index", lambda v: v),
            "BoneMass": ("bone_mass", "kg", w_xform),
            "Height": ("height", "m", h_xform),
        }
        date_cands = ("Date", "date", "DATE")
        time_cands = ("Time", "time", "TIME")
        notes_cands = ("Notes", "notes", "Comment", "comment")

        for row in reader:
            date_str = next((row.get(c) for c in date_cands if row.get(c)), None)
            time_str = next((row.get(c) for c in time_cands if row.get(c)), "") or ""
            notes_val = next((row.get(c) for c in notes_cands if row.get(c)), None)
            if not date_str:
                continue
            ts = _parse_date((date_str + (" " + time_str if time_str else "")).strip())
            if ts is None:
                continue
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)

            for col, raw_val in row.items():
                if col in date_cands or col in time_cands or col in notes_cands:
                    continue
                if raw_val in (None, ""):
                    continue
                try:
                    value = float(raw_val)
                except (TypeError, ValueError):
                    continue
                spec = known.get(col)
                if spec is not None:
                    metric_id, unit, xform = spec
                    value = xform(value)
                else:
                    result.unmapped_metrics.append(_slugify(col))
                    continue
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id=metric_id,
                        unit=unit,
                        source_id="bmt:device",
                        source_kind=SOURCE_KIND,
                        value_num=value,
                        value_text=notes_val if metric_id == "weight" else None,
                        source_uuid=_synthesize_uuid(date_str, time_str, col, raw_val),
                    )
                )


def _synthesize_uuid(*parts: str) -> str:
    seed = "|".join(parts)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()  # noqa: S324


__all__ = ["BMTParser", "SOURCE_KIND"]
