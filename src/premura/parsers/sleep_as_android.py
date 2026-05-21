"""Sleep as Android CSV parser.

Format (one logical row per night, but written as two physical CSV rows: header + values):
    header_row:    Id, Tz, From, To, Sched, Hours, Rating, Comment, Framerate, Snore,
                   Noise, Cycles, DeepSleep, LenAdjust, Geo, "HH:MM", "HH:MM", ...
    values_row:    <one value per header column>
    (optional 'Event' rows interleaved)

Times in headers like 'From'/'To' are local wall-clock in the Tz column's IANA zone,
format 'dd. MM. yyyy H:mm'. Tz is authoritative across all 4 feeds (PLAN.md §"Sleep as Android").
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from dateutil import tz

from .base import Interval, Measurement, ParseResult, file_sha256

log = logging.getLogger(__name__)
SOURCE_KIND = "sleep_as_android"

HEADER_REQUIRED = {"Id", "Tz", "From", "To"}
RE_HHMM = re.compile(r"^\d{1,2}:\d{2}$")
RE_SAA_DATETIME = re.compile(r"^\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\s+(\d{1,2}):(\d{2})\s*$")


@dataclass(slots=True)
class _Session:
    row: dict[str, str]
    per_minute: list[tuple[str, str]]


class SleepAsAndroidParser:
    source_kind = SOURCE_KIND

    def parse(self, path: Path) -> ParseResult:
        result = ParseResult(source_path=path, source_sha256=file_sha256(path))
        for s in self._iter_sessions(path):
            self._emit(s, result)
        return result

    def _iter_sessions(self, path: Path):
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header: list[str] | None = None
            for row in reader:
                if not row:
                    continue
                if HEADER_REQUIRED.issubset(set(row)):
                    header = row
                    continue
                if header is not None and len(row) == len(header) and row[0].isdigit():
                    per_min = [(c, v) for c, v in zip(header, row, strict=False) if RE_HHMM.match(c)]
                    yield _Session(row=dict(zip(header, row, strict=False)), per_minute=per_min)

    def _emit(self, s: _Session, result: ParseResult) -> None:
        tz_name = s.row.get("Tz") or "UTC"
        tzinfo = tz.gettz(tz_name) or tz.UTC
        try:
            t_from = self._parse_saa_dt(s.row["From"], tzinfo)
            t_to = self._parse_saa_dt(s.row["To"], tzinfo)
        except (KeyError, ValueError) as exc:
            log.warning("SAA: bad session row, skipping: %s", exc)
            return

        sid = s.row.get("Id") or self._fallback_id(s.row)
        source_uuid = f"saa:{sid}"
        source_id = "saa:device"  # SAA exports don't carry device metadata in the CSV
        rating = _float_or_none(s.row.get("Rating"))
        deep = _float_or_none(s.row.get("DeepSleep"))
        hours = _float_or_none(s.row.get("Hours"))

        result.intervals.append(
            Interval(
                start_utc=_to_utc(t_from),
                end_utc=_to_utc(t_to),
                metric_id="sleep_session",
                unit="enum",
                source_id=source_id,
                source_kind=SOURCE_KIND,
                value_text=s.row.get("Comment") or "session",
                value_num=hours,
                local_tz=tz_name,
                source_uuid=source_uuid,
                raw_payload={
                    k: v for k, v in s.row.items()
                    if not RE_HHMM.match(k) and v not in ("", None)
                },
            )
        )

        if rating is not None:
            result.measurements.append(
                Measurement(
                    ts_utc=_to_utc(t_from),
                    metric_id="sleep_rating",
                    unit="score",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_num=rating,
                    local_tz=tz_name,
                    source_uuid=f"{source_uuid}:rating",
                )
            )

        if deep is not None:
            result.measurements.append(
                Measurement(
                    ts_utc=_to_utc(t_from),
                    metric_id="sleep_deep_pct",
                    unit="pct",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_num=deep * 100 if deep <= 1 else deep,
                    local_tz=tz_name,
                    source_uuid=f"{source_uuid}:deep_pct",
                )
            )

        # Per-minute actigraphy: walk the clock forward, handling midnight wrap.
        prev_mod: int | None = None
        cursor_local = t_from
        for col, val in s.per_minute:
            v = _float_or_none(val)
            if v is None:
                continue
            hh, mm = (int(x) for x in col.split(":"))
            mod = hh * 60 + mm
            if prev_mod is None:
                cursor_local = _align_local_to_clock(t_from, hh, mm)
            else:
                delta = (mod - prev_mod) % (24 * 60)
                if delta == 0:
                    delta = 1
                cursor_local = cursor_local + timedelta(minutes=delta)
            prev_mod = mod
            result.measurements.append(
                Measurement(
                    ts_utc=_to_utc(cursor_local),
                    metric_id="sleep_actigraphy",
                    unit="index",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_num=v,
                    local_tz=tz_name,
                    source_uuid=f"{source_uuid}:act:{col}",
                )
            )

    @staticmethod
    def _parse_saa_dt(s: str, tzinfo) -> datetime:
        m = RE_SAA_DATETIME.match(s)
        if not m:
            raise ValueError(f"unrecognized SAA datetime: {s!r}")
        d, mo, y, hh, mm = (int(g) for g in m.groups())
        return datetime(y, mo, d, hh, mm, tzinfo=tzinfo)

    @staticmethod
    def _fallback_id(row: dict[str, str]) -> str:
        seed = "|".join((row.get("From", ""), row.get("To", ""), row.get("Tz", "")))
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def _align_local_to_clock(start: datetime, hh: int, mm: int) -> datetime:
    candidate = start.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate < start:
        candidate += timedelta(days=1)
    return candidate


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(tz.UTC).replace(tzinfo=None)


def _float_or_none(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


__all__ = ["SleepAsAndroidParser", "SOURCE_KIND"]
