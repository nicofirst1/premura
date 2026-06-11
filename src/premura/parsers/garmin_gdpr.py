"""Garmin GDPR data-export (`.zip`) parser.

The dump is a zip-of-zips and JSONs organized into folders. We dispatch by **filename
pattern** rather than path because Garmin reorganizes the layout between exports.

Real-world filenames observed (and now handled):
    UDSFile_<from>_<to>.json                       — daily wellness rollup
    <range>_<userId>_sleepData.json                — per-night sleep summaries
    <range>_<userId>_healthStatusData.json         — daily HRV / HR / SpO2 / skin-temp / respiration
    BloodPressureFile_<from>_<to>.json             — BP measurements
    HydrationLogFile_<from>_<to>.json              — hydration / sweat loss
    MetricsAcuteTrainingLoad_<range>_<userId>.json — training-load time series
    MetricsMaxMetData_<range>_<userId>.json        — VO2 max
    TrainingReadinessDTO_<range>_<userId>.json     — training readiness DTOs
    *_summarizedActivities.json                    — per-activity summaries

Timestamp shapes encountered:
    * ms-epoch int   (e.g. 1777268238000)
    * ISO local      (e.g. "2026-04-27T05:37:18.0")
    * ISO UTC        (e.g. "2026-02-10T21:29:40.0" labeled *GMT)
    * ISO date       (e.g. "2026-04-27")
    * LocalDateTime  (e.g. [2026, 5, 19, 5, 37, 39, 806000000])

Unknown patterns are surfaced in IngestBatch.notes so future format drift is visible
without a code change being required to *detect* it.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .base import IngestBatch, Interval, Measurement, SourceDescriptor

log = logging.getLogger(__name__)
SOURCE_KIND = "garmin_gdpr"
DEFAULT_SOURCE_ID = "garmin_gdpr:device"


# ----------------------------- timestamp helpers -----------------------------


def _ts_from_seconds(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, tz=UTC).replace(tzinfo=None)


def _ts_from_iso(s: str) -> datetime | None:
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def _ts_from_localdt_array(arr: list) -> datetime | None:
    """Java LocalDateTime array: [Y, M, D, h, m, s, nanos] (length 3..7)."""
    try:
        if len(arr) < 3:
            return None
        y, mo, d = int(arr[0]), int(arr[1]), int(arr[2])
        h = int(arr[3]) if len(arr) > 3 else 0
        mi = int(arr[4]) if len(arr) > 4 else 0
        s = int(arr[5]) if len(arr) > 5 else 0
        us = (int(arr[6]) // 1000) if len(arr) > 6 else 0
        return datetime(y, mo, d, h, mi, s, us)
    except (TypeError, ValueError):
        return None


def _coerce_ts(value: Any) -> datetime | None:
    """Best-effort timestamp parse from any Garmin field shape."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # heuristic: > 1e12 ⇒ milliseconds, > 1e9 ⇒ seconds.
        if value > 1e12:
            return _ts_from_seconds(value / 1000.0)
        if value > 1e9:
            return _ts_from_seconds(float(value))
        return None
    if isinstance(value, str):
        return _ts_from_iso(value)
    if isinstance(value, list):
        return _ts_from_localdt_array(value)
    return None


# Probe these keys in order; first non-None wins.
_TS_KEYS_PREFERRED = (
    "startTimeGmt",
    "timestampGmt",
    "sleepStartTimestampGMT",
    "persistedTimestampGMT",
    "createTimestampUTC",
    "updateTimestampUTC",
    "timestamp",
    "startTimeInSeconds",
    "epochSeconds",
    "epochMillis",
    "startTimeGmtInMillis",
    "calendarDate",
)


def _extract_record_ts(rec: dict[str, Any]) -> datetime | None:
    for key in _TS_KEYS_PREFERRED:
        if key in rec:
            t = _coerce_ts(rec[key])
            if t is not None:
                return t
    # metaData.calendarDate (BP file shape)
    meta = rec.get("metaData") or {}
    if isinstance(meta, dict):
        t = _coerce_ts(meta.get("calendarDate"))
        if t is not None:
            return t
    return None


def _extract_offset_str(rec: dict[str, Any]) -> str | None:
    """Build '+HH:MM' from any Garmin offset hint."""
    off = rec.get("offsetInSeconds") or rec.get("gmtOffsetInSeconds")
    if off is None:
        # Compare local vs gmt ISO strings if both present.
        local = rec.get("timestampLocal") or rec.get("startTimeLocal")
        gmt = rec.get("timestamp") or rec.get("startTimeGmt")
        if isinstance(local, str) and isinstance(gmt, str):
            lt, gt = _ts_from_iso(local), _ts_from_iso(gmt)
            if lt and gt:
                off = int((lt - gt).total_seconds())
    if off is None:
        return None
    sign = "+" if off >= 0 else "-"
    abs_s = abs(off)
    hh, rem = divmod(abs_s, 3600)
    mm = rem // 60
    return f"{sign}{int(hh):02d}:{int(mm):02d}"


def _synthesize_uuid(record_type: str, *key_parts: Any) -> str:
    clean = "|".join(str(k) for k in key_parts if k is not None)
    return f"garmin:{record_type}:{clean or 'unknown'}"


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


# ----------------------------- dispatcher --------------------------------


_HANDLERS: list[tuple[re.Pattern[str], str]] = []


def _register(pattern: str, handler_name: str) -> None:
    _HANDLERS.append((re.compile(pattern, re.IGNORECASE), handler_name))


# Order matters — first match wins. Specific before general.
_register(r"healthStatusData\.json$", "_handle_health_status")
_register(r"sleepData\.json$", "_handle_sleep_data")
_register(r"BloodPressureFile.*\.json$", "_handle_blood_pressure")
_register(r"HydrationLogFile.*\.json$", "_handle_hydration")
_register(r"MetricsAcuteTrainingLoad.*\.json$", "_handle_training_load")
_register(r"MetricsMaxMetData.*\.json$", "_handle_vo2_max")
_register(r"TrainingReadiness.*\.json$", "_handle_training_readiness")
_register(r"UDSFile.*\.json$", "_handle_daily_wellness")
_register(r"summarizedActivit.*\.json$", "_handle_activity_summary")


# ----------------------------- parser ------------------------------------


class GarminGDPRParser:
    source_kind = SOURCE_KIND

    def declares_metrics(self) -> list[str]:
        return [
            "activity_summary",
            "bp_diastolic",
            "bp_systolic",
            "daily_wellness",
            "heart_rate",
            "hrv_rmssd_overnight",
            "hydration",
            "intensity_minutes",
            "resp_rate",
            "resting_hr",
            "sleep_deep_pct",
            "sleep_rating",
            "sleep_session",
            "spo2",
            "stress",
            "training_load",
            "training_readiness",
            "vo2_max",
        ]

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)
        result.source_descriptors[DEFAULT_SOURCE_ID] = SourceDescriptor(
            source_id=DEFAULT_SOURCE_ID,
            source_kind=SOURCE_KIND,
        )
        unknown: dict[str, int] = {}
        for member_name, payload in self._iter_json_members(path):
            handler = self._dispatch(member_name)
            if handler is None:
                stem = member_name.split("/")[-1]
                unknown[stem] = unknown.get(stem, 0) + 1
                continue
            try:
                docs = json.loads(payload)
            except json.JSONDecodeError as exc:
                log.warning("Garmin: JSON decode failed for %s: %s", member_name, exc)
                continue
            try:
                handler(docs, result, member_name=member_name)
            except Exception:
                log.exception("Garmin: handler %s failed on %s", handler.__name__, member_name)
        if unknown:
            note = "unhandled files: " + ", ".join(
                f"{name} ({n})" for name, n in sorted(unknown.items())[:10]
            )
            result.notes = (result.notes + "; " if result.notes else "") + note
        result.validate()
        return result

    def _iter_json_members(self, path: Path) -> Iterator[tuple[str, bytes]]:
        with zipfile.ZipFile(path) as outer:
            for info in outer.infolist():
                if info.is_dir():
                    continue
                fname = info.filename.lower()
                if fname.endswith(".json"):
                    yield info.filename, outer.read(info)
                elif fname.endswith(".zip"):
                    with outer.open(info) as inner_fh, zipfile.ZipFile(inner_fh) as inner:
                        for inner_info in inner.infolist():
                            if not inner_info.is_dir() and inner_info.filename.lower().endswith(
                                ".json"
                            ):
                                yield inner_info.filename, inner.read(inner_info)

    def _dispatch(self, member_name: str):
        for pattern, handler_name in _HANDLERS:
            if pattern.search(member_name):
                return getattr(self, handler_name)
        return None

    @staticmethod
    def _iter_records(docs: Any) -> Iterable[dict[str, Any]]:
        if isinstance(docs, list):
            yield from (d for d in docs if isinstance(d, dict))
        elif isinstance(docs, dict):
            for key in ("items", "readings", "values", "data", "summarizedActivitiesExport"):
                v = docs.get(key)
                if isinstance(v, list):
                    yield from (d for d in v if isinstance(d, dict))
                    return
            yield docs

    # ----------------------------- handlers --------------------------------

    def _handle_health_status(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        """healthStatusData: one record per day with nested metric types."""
        type_to_metric = {
            "HRV": ("hrv_rmssd_overnight", "ms"),
            "HR": ("resting_hr", "bpm"),
            "SPO2": ("spo2", "pct"),
            "SKIN_TEMP_C": ("skin_temperature", "celsius"),
            "RESPIRATION": ("resp_rate", "breaths_per_min"),
        }
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            cal = rec.get("calendarDate")
            for entry in rec.get("metrics", []) or []:
                if not isinstance(entry, dict):
                    continue
                kind = entry.get("type")
                if not isinstance(kind, str):
                    continue
                spec = type_to_metric.get(kind)
                if spec is None:
                    continue
                metric_id, unit = spec
                v = _as_float(entry.get("value"))
                if v is None or v == 0.0:
                    # Garmin uses 0 as a sentinel for "not measured" on SPO2/skin-temp.
                    if kind in ("SPO2", "SKIN_TEMP_C"):
                        continue
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id=metric_id,
                        unit=unit,
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=v,
                        value_text=entry.get("status"),
                        local_tz=_extract_offset_str(rec),
                        source_uuid=_synthesize_uuid("health_status", cal, kind),
                        raw_payload=entry,
                    )
                )

    def _handle_sleep_data(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        """One sleep session per record plus related measurements."""
        for rec in self._iter_records(docs):
            start = _coerce_ts(rec.get("sleepStartTimestampGMT"))
            end = _coerce_ts(rec.get("sleepEndTimestampGMT"))
            cal = rec.get("calendarDate")
            if start is None or end is None:
                continue
            uuid = _synthesize_uuid("sleep_session", cal)
            tz = _extract_offset_str(rec)
            deep_s = _as_float(rec.get("deepSleepSeconds")) or 0.0
            light_s = _as_float(rec.get("lightSleepSeconds")) or 0.0
            rem_s = _as_float(rec.get("remSleepSeconds")) or 0.0
            awake_s = _as_float(rec.get("awakeSleepSeconds")) or 0.0
            total_s = deep_s + light_s + rem_s + awake_s

            result.intervals.append(
                Interval(
                    start_utc=start,
                    end_utc=end,
                    metric_id="sleep_session",
                    unit="enum",
                    source_id=DEFAULT_SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_text=cal,
                    value_num=(total_s / 3600.0) if total_s else None,
                    local_tz=tz,
                    source_uuid=uuid,
                    raw_payload=rec,
                )
            )

            # Sleep score (overall) as an aggregate measurement
            scores = rec.get("sleepScores") or {}
            overall = _as_float(scores.get("overallScore"))
            if overall is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=start,
                        metric_id="sleep_rating",
                        unit="score",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=overall,
                        local_tz=tz,
                        source_uuid=f"{uuid}:rating",
                    )
                )

            if total_s:
                result.measurements.append(
                    Measurement(
                        ts_utc=start,
                        metric_id="sleep_deep_pct",
                        unit="pct",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=100.0 * deep_s / total_s,
                        local_tz=tz,
                        source_uuid=f"{uuid}:deep_pct",
                    )
                )

            spo2_block = rec.get("spo2SleepSummary") or {}
            spo2_avg = _as_float(spo2_block.get("averageSPO2"))
            if spo2_avg is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=start,
                        metric_id="spo2",
                        unit="pct",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=spo2_avg,
                        local_tz=tz,
                        source_uuid=f"{uuid}:spo2_avg",
                    )
                )

            resp_avg = _as_float(rec.get("averageRespiration"))
            if resp_avg is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=start,
                        metric_id="resp_rate",
                        unit="breaths_per_min",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=resp_avg,
                        local_tz=tz,
                        source_uuid=f"{uuid}:resp_avg",
                    )
                )

            stress_avg = _as_float(rec.get("avgSleepStress"))
            if stress_avg is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=start,
                        metric_id="stress",
                        unit="score_0_100",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=stress_avg,
                        local_tz=tz,
                        source_uuid=f"{uuid}:stress_avg",
                    )
                )

    def _handle_blood_pressure(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        """BP file: metaData.calendarDate is a Java LocalDateTime array."""
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            bp = rec.get("bloodPressure") or {}
            seq = (rec.get("metaData") or {}).get("sequence")
            uuid = _synthesize_uuid("blood_pressure", seq, rec.get("version"))
            sys_v = _as_float(bp.get("systolic"))
            dia_v = _as_float(bp.get("diastolic"))
            pulse = _as_float(bp.get("pulse"))
            if sys_v is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="bp_systolic",
                        unit="mmHg",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=sys_v,
                        source_uuid=f"{uuid}:sys",
                        raw_payload=bp,
                    )
                )
            if dia_v is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="bp_diastolic",
                        unit="mmHg",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=dia_v,
                        source_uuid=f"{uuid}:dia",
                        raw_payload=bp,
                    )
                )
            if pulse is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="heart_rate",
                        unit="bpm",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=pulse,
                        source_uuid=f"{uuid}:pulse",
                    )
                )

    def _handle_hydration(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        for rec in self._iter_records(docs):
            ts = _coerce_ts(rec.get("persistedTimestampGMT")) or _coerce_ts(rec.get("calendarDate"))
            if ts is None:
                continue
            uuid = (
                (rec.get("uuid") or {}).get("uuid")
                if isinstance(rec.get("uuid"), dict)
                else rec.get("uuid")
            )
            sweat_ml = _as_float(rec.get("estimatedSweatLossInML"))
            if sweat_ml is not None and sweat_ml > 0:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="hydration",
                        unit="l",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=sweat_ml / 1000.0,
                        local_tz=_extract_offset_str(rec),
                        source_uuid=_synthesize_uuid("hydration", uuid),
                        raw_payload=rec,
                    )
                )

    def _handle_training_load(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            acute = _as_float(rec.get("dailyTrainingLoadAcute"))
            ts_ms = rec.get("timestamp")
            if acute is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="training_load",
                        unit="score",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=acute,
                        value_text=rec.get("acwrStatus"),
                        source_uuid=_synthesize_uuid("training_load", ts_ms),
                        raw_payload=rec,
                    )
                )

    def _handle_vo2_max(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            v = _as_float(rec.get("vo2MaxValue"))
            if v is None:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id="vo2_max",
                    unit="ml_per_kg_per_min",
                    source_id=DEFAULT_SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=v,
                    value_text=rec.get("sport"),
                    source_uuid=_synthesize_uuid(
                        "vo2_max", rec.get("calendarDate"), rec.get("sport")
                    ),
                    raw_payload=rec,
                )
            )

    def _handle_training_readiness(
        self, docs: Any, result: IngestBatch, *, member_name: str
    ) -> None:
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            score = _as_float(rec.get("score"))
            ts_ms = rec.get("timestamp")
            uuid = _synthesize_uuid("training_readiness", ts_ms)
            if score is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="training_readiness",
                        unit="score_0_100",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=score,
                        value_text=rec.get("level"),
                        source_uuid=uuid,
                        raw_payload=rec,
                    )
                )
            hrv_weekly = _as_float(rec.get("hrvWeeklyAverage"))
            if hrv_weekly is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="hrv_rmssd_overnight",
                        unit="ms",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=hrv_weekly,
                        source_uuid=f"{uuid}:hrv_weekly",
                    )
                )

    def _handle_daily_wellness(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        """UDS file: one record per day, deeply nested."""
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            cal = rec.get("calendarDate")
            uuid = _synthesize_uuid("daily_wellness", cal)
            tz = _extract_offset_str(rec)

            # Resting HR
            rhr = _as_float(rec.get("restingHeartRate"))
            if rhr is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="resting_hr",
                        unit="bpm",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=rhr,
                        local_tz=tz,
                        source_uuid=f"{uuid}:rhr",
                    )
                )

            # Daily stress / body battery aggregates if present
            all_day_stress = rec.get("allDayStress") or {}
            for agg in all_day_stress.get("aggregatorList", []) or []:
                if not isinstance(agg, dict):
                    continue
                if agg.get("type") == "TOTAL":
                    avg = _as_float(agg.get("averageStressLevel"))
                    if avg is not None and avg >= 0:
                        result.measurements.append(
                            Measurement(
                                ts_utc=ts,
                                metric_id="stress",
                                unit="score_0_100",
                                source_id=DEFAULT_SOURCE_ID,
                                source_kind=SOURCE_KIND,
                                value_num=avg,
                                local_tz=tz,
                                source_uuid=f"{uuid}:stress_avg",
                            )
                        )

            # Intensity minutes
            mod = _as_float(rec.get("moderateIntensityMinutes")) or 0.0
            vig = _as_float(rec.get("vigorousIntensityMinutes")) or 0.0
            if mod or vig:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="intensity_minutes",
                        unit="min",
                        source_id=DEFAULT_SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=mod + 2 * vig,  # Garmin's weighted score
                        local_tz=tz,
                        source_uuid=f"{uuid}:intensity",
                    )
                )

            # Daily wrapper interval (one full day)
            end = ts + timedelta(days=1)
            result.intervals.append(
                Interval(
                    start_utc=ts,
                    end_utc=end,
                    metric_id="daily_wellness",
                    unit="composite",
                    source_id=DEFAULT_SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_text=cal,
                    local_tz=tz,
                    source_uuid=uuid,
                    raw_payload=rec,
                )
            )

    def _handle_activity_summary(self, docs: Any, result: IngestBatch, *, member_name: str) -> None:
        for rec in self._iter_records(docs):
            ts = _extract_record_ts(rec)
            if ts is None:
                continue
            dur_s = _as_float(rec.get("durationInSeconds")) or _as_float(rec.get("duration")) or 0.0
            try:
                end = ts + timedelta(seconds=dur_s)
            except (TypeError, ValueError):
                end = ts
            label = (
                rec.get("activityType")
                or rec.get("activityTypeKey")
                or rec.get("sportType")
                or "activity"
            )
            summary_id = rec.get("summaryId") or rec.get("activityId")
            result.intervals.append(
                Interval(
                    start_utc=ts,
                    end_utc=end,
                    metric_id="activity_summary",
                    unit="enum",
                    source_id=DEFAULT_SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_text=str(label),
                    local_tz=_extract_offset_str(rec),
                    source_uuid=_synthesize_uuid("activity_summary", summary_id),
                    raw_payload=rec,
                )
            )


__all__ = ["GarminGDPRParser", "SOURCE_KIND"]
