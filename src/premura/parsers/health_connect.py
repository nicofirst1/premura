"""Health Connect (`.db`, SQLite v3, `user_version=20`) parser.

Tactics:
  - Open the file via stdlib sqlite3 (DuckDB's sqlite_scanner is fast for table-scans but
    has fewer affordances for the row-by-row work we do per series).
  - PRAGMA user_version + PRAGMA table_info per table: warn-and-skip on schema drift.
  - JOIN application_info_table + device_info_table once, cache
    (app_info_id, device_info_id) -> source_id.

Critical conversions (PLAN.md):
  - `time` / `start_time` / `end_time` are milliseconds since epoch (UTC).
  - `zone_offset` is in **seconds** (NOT ms).
  - `uuid` is a 16-byte BLOB; hex-encode for source_uuid.
  - `weight` is in **grams** (HC convention) → divide by 1000 for kg.
  - `*_mass` (lean/water/bone) likewise grams → kg.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .base import IngestBatch, Interval, Measurement, SourceDescriptor

log = logging.getLogger(__name__)

SOURCE_KIND = "health_connect"
EXPECTED_USER_VERSION = 20

SLEEP_STAGE_LABELS = {
    0: "unknown",
    1: "awake",
    2: "sleeping",
    3: "out_of_bed",
    4: "light",
    5: "deep",
    6: "rem",
    7: "awake_in_bed",
}

EXERCISE_TYPE_LABELS = {
    0: "other",
    8: "biking",
    9: "biking_stationary",
    13: "calisthenics",
    25: "elliptical",
    26: "exercise_class",
    34: "guided_breathing",
    35: "gymnastics",
    37: "hiking",
    46: "martial_arts",
    52: "pilates",
    54: "rowing_machine",
    55: "running",
    56: "running_treadmill",
    58: "scuba_diving",
    63: "skiing",
    66: "snowboarding",
    79: "stair_climbing",
    80: "stair_climbing_machine",
    81: "strength_training",
    82: "stretching",
    83: "surfing",
    84: "swimming_open_water",
    85: "swimming_pool",
    87: "tennis",
    93: "walking",
    97: "weightlifting",
    100: "yoga",
}


@dataclass(slots=True)
class _SimpleSpec:
    table: str
    metric_id: str
    value_col: str
    unit: str
    transform: float = 1.0


@dataclass(slots=True)
class _IntervalSpec:
    table: str
    metric_id: str
    value_col: str | None
    unit: str
    transform: float = 1.0


SIMPLE_SPECS: list[_SimpleSpec] = [
    _SimpleSpec("weight_record_table", "weight", "weight", "kg", 1 / 1000),
    _SimpleSpec("body_fat_record_table", "body_fat_pct", "percentage", "pct"),
    _SimpleSpec("lean_body_mass_record_table", "lean_body_mass", "mass", "kg", 1 / 1000),
    _SimpleSpec(
        "body_water_mass_record_table", "body_water_mass", "body_water_mass", "kg", 1 / 1000
    ),
    _SimpleSpec("bone_mass_record_table", "bone_mass", "mass", "kg", 1 / 1000),
    _SimpleSpec("height_record_table", "height", "height", "m"),
    _SimpleSpec("oxygen_saturation_record_table", "spo2", "percentage", "pct"),
    _SimpleSpec("respiratory_rate_record_table", "resp_rate", "rate", "breaths_per_min"),
    _SimpleSpec(
        "heart_rate_variability_rmssd_record_table",
        "hrv_rmssd",
        "heart_rate_variability_millis",
        "ms",
    ),
    _SimpleSpec("resting_heart_rate_record_table", "resting_hr", "beats_per_minute", "bpm"),
    _SimpleSpec(
        "vo2_max_record_table",
        "vo2_max",
        "vo2_milliliters_per_minute_kilogram",
        "ml_per_kg_per_min",
    ),
    _SimpleSpec(
        "basal_metabolic_rate_record_table",
        "bmr",
        "basal_metabolic_rate",
        "kcal_per_day",
    ),
    _SimpleSpec("blood_glucose_record_table", "blood_glucose", "level", "mmol_per_l"),
    _SimpleSpec("body_temperature_record_table", "body_temperature", "temperature", "celsius"),
]

INTERVAL_SPECS: list[_IntervalSpec] = [
    _IntervalSpec("steps_record_table", "steps", "count", "count"),
    _IntervalSpec("distance_record_table", "distance", "distance", "m"),
    _IntervalSpec("active_calories_burned_record_table", "active_kcal", "energy", "kcal"),
    _IntervalSpec("total_calories_burned_record_table", "total_kcal", "energy", "kcal"),
    _IntervalSpec("hydration_record_table", "hydration", "volume", "l"),
]


def _ts(ms: int) -> datetime:
    """ms since epoch → naïve-UTC datetime (DuckDB TIMESTAMP wants naïve)."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(tzinfo=None)


def _offset_str(zone_offset_seconds: int | None) -> str | None:
    """HC zone_offset is seconds → '+HH:MM'."""
    if zone_offset_seconds is None:
        return None
    sign = "+" if zone_offset_seconds >= 0 else "-"
    abs_s = abs(zone_offset_seconds)
    hh, rem = divmod(abs_s, 3600)
    mm = rem // 60
    return f"{sign}{hh:02d}:{mm:02d}"


def _uuid_hex(b: bytes | None) -> str | None:
    return None if b is None else b.hex()


class HealthConnectParser:
    source_kind = SOURCE_KIND

    def __init__(self) -> None:
        self._app_cache: dict[int, tuple[str | None, str | None]] = {}
        self._device_cache: dict[int, tuple[str | None, str | None]] = {}

    def declares_metrics(self) -> list[str]:
        return sorted(
            {spec.metric_id for spec in SIMPLE_SPECS}
            | {spec.metric_id for spec in INTERVAL_SPECS}
            | {
                "bp_diastolic",
                "bp_systolic",
                "exercise_session",
                "heart_rate",
                "mindfulness_session",
                "sleep_session",
                "sleep_stage",
            }
        )

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            self._check_version(con, result)
            self._load_dim_caches(con)
            self._parse_simple(con, result)
            self._parse_intervals(con, result)
            self._parse_blood_pressure(con, result)
            self._parse_heart_rate_series(con, result)
            self._parse_sleep(con, result)
            self._parse_exercise(con, result)
            self._parse_mindfulness(con, result)
        result.validate()
        return result

    # --- helpers ---

    def _check_version(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        ver = con.execute("PRAGMA user_version").fetchone()[0]
        if ver != EXPECTED_USER_VERSION:
            note = f"HC user_version={ver} (expected {EXPECTED_USER_VERSION})"
            log.warning(note)
            result.notes = (result.notes + "; " if result.notes else "") + note

    def _table_columns(self, con: sqlite3.Connection, table: str) -> set[str]:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        return {r["name"] for r in rows}

    def _load_dim_caches(self, con: sqlite3.Connection) -> None:
        for r in con.execute("SELECT row_id, package_name, app_name FROM application_info_table"):
            self._app_cache[r["row_id"]] = (r["package_name"], r["app_name"])
        for r in con.execute("SELECT row_id, manufacturer, model FROM device_info_table"):
            self._device_cache[r["row_id"]] = (r["manufacturer"], r["model"])

    def _source_id(
        self,
        result: IngestBatch,
        app_info_id: int | None,
        device_info_id: int | None,
    ) -> str:
        pkg, app = self._app_cache.get(app_info_id or -1, (None, None))
        mfr, model = self._device_cache.get(device_info_id or -1, (None, None))
        pkg_part = pkg or "unknown"
        device_part = model or mfr or "unknown"
        source_id = f"hc:{pkg_part}|{device_part}"
        result.source_descriptors.setdefault(
            source_id,
            SourceDescriptor(
                source_id=source_id,
                source_kind=SOURCE_KIND,
                app_package=pkg,
                app_name=app,
                device_manufacturer=mfr,
                device_model=model,
            ),
        )
        return source_id

    # --- simple instantaneous tables ---

    def _parse_simple(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        for spec in SIMPLE_SPECS:
            cols = self._table_columns(con, spec.table)
            if not cols:
                continue
            required = {
                "uuid",
                "time",
                "zone_offset",
                spec.value_col,
                "app_info_id",
                "device_info_id",
            }
            missing = required - cols
            if missing:
                log.warning("HC: %s missing cols %s — skipping", spec.table, missing)
                continue
            q = f"""
                SELECT uuid, time, zone_offset, {spec.value_col} AS v, app_info_id, device_info_id
                FROM {spec.table}
                WHERE {spec.value_col} IS NOT NULL
            """
            for r in con.execute(q):
                if r["v"] is None:
                    continue
                source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
                result.measurements.append(
                    Measurement(
                        ts_utc=_ts(r["time"]),
                        metric_id=spec.metric_id,
                        unit=spec.unit,
                        source_id=source_id,
                        source_kind=SOURCE_KIND,
                        value_num=float(r["v"]) * spec.transform,
                        local_tz=_offset_str(r["zone_offset"]),
                        source_uuid=_uuid_hex(r["uuid"]),
                    )
                )

    # --- simple intervals ---

    def _parse_intervals(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        for spec in INTERVAL_SPECS:
            cols = self._table_columns(con, spec.table)
            if not cols:
                continue
            required = {
                "uuid",
                "start_time",
                "end_time",
                "start_zone_offset",
                "app_info_id",
                "device_info_id",
            }
            if spec.value_col:
                required.add(spec.value_col)
            missing = required - cols
            if missing:
                log.warning("HC: %s missing cols %s — skipping", spec.table, missing)
                continue
            value_select = f", {spec.value_col} AS v" if spec.value_col else ""
            q = f"""
                SELECT uuid, start_time, end_time, start_zone_offset,
                       app_info_id, device_info_id {value_select}
                FROM {spec.table}
            """
            for r in con.execute(q):
                source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
                v_raw = r["v"] if spec.value_col else None
                v = None if v_raw is None else float(v_raw) * spec.transform
                result.intervals.append(
                    Interval(
                        start_utc=_ts(r["start_time"]),
                        end_utc=_ts(r["end_time"]),
                        metric_id=spec.metric_id,
                        unit=spec.unit,
                        source_id=source_id,
                        source_kind=SOURCE_KIND,
                        value_num=v,
                        local_tz=_offset_str(r["start_zone_offset"]),
                        source_uuid=_uuid_hex(r["uuid"]),
                    )
                )

    # --- blood pressure (two metrics per row) ---

    def _parse_blood_pressure(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        cols = self._table_columns(con, "blood_pressure_record_table")
        if not {"uuid", "time", "zone_offset", "systolic", "diastolic"}.issubset(cols):
            return
        q = """
            SELECT uuid, time, zone_offset, systolic, diastolic, body_position,
                   measurement_location, app_info_id, device_info_id
            FROM blood_pressure_record_table
        """
        for r in con.execute(q):
            source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
            uuid_hex = _uuid_hex(r["uuid"])
            ts_utc = _ts(r["time"])
            local_tz = _offset_str(r["zone_offset"])
            raw_payload = {
                "body_position": r["body_position"],
                "measurement_location": r["measurement_location"],
            }
            if r["systolic"] is not None:
                result.measurements.append(
                    Measurement(
                        metric_id="bp_systolic",
                        value_num=float(r["systolic"]),
                        source_uuid=f"{uuid_hex}:sys",
                        ts_utc=ts_utc,
                        unit="mmHg",
                        source_id=source_id,
                        source_kind=SOURCE_KIND,
                        local_tz=local_tz,
                        raw_payload=raw_payload,
                    )
                )
            if r["diastolic"] is not None:
                result.measurements.append(
                    Measurement(
                        metric_id="bp_diastolic",
                        value_num=float(r["diastolic"]),
                        source_uuid=f"{uuid_hex}:dia",
                        ts_utc=ts_utc,
                        unit="mmHg",
                        source_id=source_id,
                        source_kind=SOURCE_KIND,
                        local_tz=local_tz,
                        raw_payload=raw_payload,
                    )
                )

    # --- heart rate series (parent + per-sample series) ---

    def _parse_heart_rate_series(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        parent_cols = self._table_columns(con, "heart_rate_record_table")
        series_cols = self._table_columns(con, "heart_rate_record_series_table")
        if not parent_cols or not series_cols:
            return
        if not {"row_id", "uuid", "app_info_id", "device_info_id", "start_zone_offset"}.issubset(
            parent_cols
        ):
            return
        if not {"parent_key", "beats_per_minute", "epoch_millis"}.issubset(series_cols):
            return
        q = """
            SELECT p.uuid, p.app_info_id, p.device_info_id, p.start_zone_offset,
                   s.beats_per_minute AS bpm, s.epoch_millis AS ms
            FROM heart_rate_record_series_table s
            JOIN heart_rate_record_table p ON p.row_id = s.parent_key
        """
        for r in con.execute(q):
            source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
            parent_uuid = _uuid_hex(r["uuid"])
            result.measurements.append(
                Measurement(
                    ts_utc=_ts(r["ms"]),
                    metric_id="heart_rate",
                    unit="bpm",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_num=float(r["bpm"]),
                    local_tz=_offset_str(r["start_zone_offset"]),
                    source_uuid=f"{parent_uuid}:{r['ms']}",
                )
            )

    # --- sleep (session + stages) ---

    def _parse_sleep(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        sess_cols = self._table_columns(con, "sleep_session_record_table")
        if not sess_cols:
            return
        q_sess = """
            SELECT row_id, uuid, start_time, end_time, start_zone_offset,
                   app_info_id, device_info_id, title, notes
            FROM sleep_session_record_table
        """
        sess_map: dict[int, tuple[str | None, str, str | None]] = {}
        for r in con.execute(q_sess):
            source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
            uuid_hex = _uuid_hex(r["uuid"])
            tz = _offset_str(r["start_zone_offset"])
            sess_map[r["row_id"]] = (uuid_hex, source_id, tz)
            result.intervals.append(
                Interval(
                    start_utc=_ts(r["start_time"]),
                    end_utc=_ts(r["end_time"]),
                    metric_id="sleep_session",
                    unit="enum",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_text=r["title"] or "session",
                    local_tz=tz,
                    source_uuid=uuid_hex,
                    raw_payload={"notes": r["notes"]} if r["notes"] else None,
                )
            )

        stage_cols = self._table_columns(con, "sleep_stages_table")
        if not {"parent_key", "stage_start_time", "stage_end_time", "stage_type"}.issubset(
            stage_cols
        ):
            return
        q_st = """
            SELECT parent_key, stage_start_time, stage_end_time, stage_type
            FROM sleep_stages_table
        """
        for r in con.execute(q_st):
            parent = sess_map.get(r["parent_key"])
            if parent is None:
                continue
            parent_uuid, source_id, tz = parent
            label = SLEEP_STAGE_LABELS.get(r["stage_type"], f"stage_{r['stage_type']}")
            result.intervals.append(
                Interval(
                    start_utc=_ts(r["stage_start_time"]),
                    end_utc=_ts(r["stage_end_time"]),
                    metric_id="sleep_stage",
                    unit="enum",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_text=label,
                    value_num=float(r["stage_type"]),
                    local_tz=tz,
                    parent_uuid=parent_uuid,
                    source_uuid=f"{parent_uuid}:stage:{r['stage_start_time']}",
                    raw_payload={"stage_type": r["stage_type"]},
                )
            )

    # --- exercise sessions ---

    def _parse_exercise(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        cols = self._table_columns(con, "exercise_session_record_table")
        if not cols:
            return
        if not {"uuid", "start_time", "end_time", "start_zone_offset", "exercise_type"}.issubset(
            cols
        ):
            return
        q = """
            SELECT uuid, start_time, end_time, start_zone_offset,
                   app_info_id, device_info_id, exercise_type, title,
                   session_rate_of_perceived_exertion AS rpe
            FROM exercise_session_record_table
        """
        for r in con.execute(q):
            source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
            label = EXERCISE_TYPE_LABELS.get(r["exercise_type"], f"type_{r['exercise_type']}")
            result.intervals.append(
                Interval(
                    start_utc=_ts(r["start_time"]),
                    end_utc=_ts(r["end_time"]),
                    metric_id="exercise_session",
                    unit="enum",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_text=label,
                    value_num=float(r["exercise_type"]),
                    local_tz=_offset_str(r["start_zone_offset"]),
                    source_uuid=_uuid_hex(r["uuid"]),
                    raw_payload={
                        "title": r["title"],
                        "rpe": r["rpe"],
                        "exercise_type": r["exercise_type"],
                    },
                )
            )

    # --- mindfulness sessions ---

    def _parse_mindfulness(self, con: sqlite3.Connection, result: IngestBatch) -> None:
        cols = self._table_columns(con, "mindfulness_session_record_table")
        if not cols:
            return
        if not {"uuid", "start_time", "end_time", "start_zone_offset"}.issubset(cols):
            return
        q = """
            SELECT uuid, start_time, end_time, start_zone_offset,
                   app_info_id, device_info_id, type, title
            FROM mindfulness_session_record_table
        """
        for r in con.execute(q):
            source_id = self._source_id(result, r["app_info_id"], r["device_info_id"])
            result.intervals.append(
                Interval(
                    start_utc=_ts(r["start_time"]),
                    end_utc=_ts(r["end_time"]),
                    metric_id="mindfulness_session",
                    unit="enum",
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    value_text=r["title"] or "session",
                    value_num=float(r["type"]) if r["type"] is not None else None,
                    local_tz=_offset_str(r["start_zone_offset"]),
                    source_uuid=_uuid_hex(r["uuid"]),
                )
            )


__all__ = ["HealthConnectParser", "SOURCE_KIND"]
