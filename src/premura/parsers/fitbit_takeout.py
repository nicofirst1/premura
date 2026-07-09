"""Fitbit Google Takeout data-export parser (observation seam).

Fitbit's "Export Your Account Archive" / Google Takeout ships an **unzipped
folder tree** (or a `.zip` of the same tree) laid out as
``MyFitbitData/<User>/<Category>/`` with categories such as Sleep, Heart,
Biometrics, Physical Activity, Stress and Menstrual Health. This parser accepts
either a directory (the common case: the operator's own already-unzipped export)
or a `.zip` of that tree, and dispatches by **filename pattern** rather than by
path, so a re-organized export or a partial category still routes correctly (the
same posture ``garmin_gdpr`` takes).

Scope and altitude decision (recorded here per AGENTS.md "record the decision in
the module docstring"): Fitbit ships two shapes of the same signal - a
**daily/summary** file and a **raw intraday** per-minute / per-second stream. We
parse the daily/summary files and deliberately **skip the intraday streams**
(``steps-*.json``, ``distance-*.json``, ``calories-*.json``,
``heart_rate-*.json``, ``Active Zone Minutes - *.csv``, ``Minute SpO2 *.csv``,
``Heart Rate Variability Details/Histogram *.csv``). Intraday streams are tens of
thousands of rows per file and carry the same signal the daily rollup already
aggregates; the daily rollup is the loadable, analysis-ready row. Skipped files
are surfaced in ``IngestBatch.notes`` (unrouted members) so a future decision to
ingest intraday is a visible, deliberate change rather than a silent gap.

Non-signal categories (Social, Programs, Application, Personal & Account, Google
Data, Other) are not routed at all and appear in ``notes`` as unhandled members.

Daily/summary members handled, with the file shape observed:

    Sleep/Daily Heart Rate Variability Summary - <date>.csv
        timestamp,rmssd,nremhr,entropy                     -> hrv_rmssd_overnight
    Sleep/Daily Respiratory Rate Summary - <date>.csv
        timestamp,daily_respiratory_rate                   -> respiratory_rate_sleep
    Sleep/Daily SpO2 - <range>.csv
        timestamp,average_value,lower_bound,upper_bound    -> spo2
    Sleep/Computed Temperature - <date>.csv
        type,sleep_start,sleep_end,...,nightly_temperature -> skin_temperature
    Sleep/sleep_score.csv
        ...,timestamp,overall_score,...,resting_heart_rate -> sleep_rating (+ resting_hr)
    Sleep/sleep-<date>.json
        per-night summary logs           -> sleep_session (interval) + sleep_efficiency
    Physical Activity/{very,moderately,lightly}_active_minutes-<date>.json
        [{dateTime, value}] one per day                    -> active_minutes_{very,moderate,light}
    Physical Activity/sedentary_minutes-<date>.json         -> sedentary_minutes
    Physical Activity/resting_heart_rate-<date>.json
        [{dateTime, value:{date,value,error}}] one per day -> resting_hr
    Stress/Stress Score.csv
        DATE,...,STRESS_SCORE,...,STATUS,CALCULATION_FAILED -> stress
    Stress/Mindfulness Sessions.csv
        session_id,...,start_date_time,end_date_time,...    -> mindfulness_session (interval)
    Menstrual Health/menstrual_health_cycles.csv
        id,...,period_start_date,period_end_date
                                         -> vendor:fitbit:menstrual_period (interval)

Field resolution (CONTRACT.md decision tree, stop at first match):
    resting_hr, spo2, hrv_rmssd_overnight, respiratory_rate_sleep, stress,
    sleep_session, sleep_rating, sleep_efficiency, skin_temperature,
    mindfulness_session      -> rung 1, existing dim_metric.yaml alias/metric_id.
    active_minutes_very, active_minutes_moderate, active_minutes_light,
    sedentary_minutes        -> rung 4, bare English canonical (reusable
                                cross-vendor intensity-bucket concept, not
                                Fitbit-specific; new dim_metric.yaml rows).
    vendor:fitbit:menstrual_period -> rung 5, vendor fallback (Fitbit-shaped
                                cycle record with no standard coverage).
    sleep_score.restlessness, HRV nremhr/entropy, Stress subscores, menstrual
    non-period fields -> structural/derived vendor detail with no metric home
                         -> unmapped_metrics.

Blank/sentinel cells are "unknown", never fabricated as zero (Fitbit uses a
``0.0`` sentinel with ``date: null`` for a missing resting-HR day and a
``NO_DATA`` status for a missing stress day; both are dropped, not stored as 0).
A present-but-unparseable cell becomes a ``skipped_rows`` entry with a reason
instead of being dropped silently.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import zipfile
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .base import IngestBatch, Interval, Measurement, RoutingPreview, SkippedRow, SourceDescriptor

log = logging.getLogger(__name__)
SOURCE_KIND = "fitbit_takeout"
SOURCE_ID = "fitbit_takeout:account"

_MENSTRUAL_PERIOD_METRIC = "vendor:fitbit:menstrual_period"


# ------------------------------- helpers --------------------------------- #


def _synth_uuid(*parts: object) -> str:
    seed = "|".join(str(p) for p in parts if p is not None)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()  # noqa: S324


def _parse_iso(raw: str | None) -> datetime | None:
    """Fitbit ISO timestamp (naive local, ``Z``-suffixed, or offset) -> naive UTC."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _parse_slashdate(raw: str | None) -> datetime | None:
    """Fitbit intraday-JSON ``MM/DD/YY HH:MM:SS`` stamp -> naive datetime."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%y %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _parse_date(raw: str | None) -> datetime | None:
    """Fitbit ``YYYY-MM-DD`` date -> naive datetime at midnight."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _parse_float(raw: Any) -> float | None:
    """None for a blank cell (unknown); raises ValueError for a bad cell."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None
    return float(text)


# --------------------------- member dispatch ----------------------------- #
#
# Order matters: specific patterns before general. Each entry maps a filename
# regex to a handler name. Intraday streams are intentionally absent so they
# route to nothing and surface in notes (see module docstring scope decision).

_HANDLERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Daily Heart Rate Variability Summary - .*\.csv$", re.I), "_handle_daily_hrv"),
    (re.compile(r"Daily Respiratory Rate Summary - .*\.csv$", re.I), "_handle_daily_resp"),
    (re.compile(r"Daily SpO2 - .*\.csv$", re.I), "_handle_daily_spo2"),
    (re.compile(r"Computed Temperature - .*\.csv$", re.I), "_handle_computed_temp"),
    (re.compile(r"sleep_score\.csv$", re.I), "_handle_sleep_score"),
    (re.compile(r"(?:^|/)sleep-\d{4}-\d{2}-\d{2}\.json$", re.I), "_handle_sleep_json"),
    (re.compile(r"very_active_minutes-.*\.json$", re.I), "_handle_active_minutes_very"),
    (re.compile(r"moderately_active_minutes-.*\.json$", re.I), "_handle_active_minutes_moderate"),
    (re.compile(r"lightly_active_minutes-.*\.json$", re.I), "_handle_active_minutes_light"),
    (re.compile(r"sedentary_minutes-.*\.json$", re.I), "_handle_sedentary_minutes"),
    (re.compile(r"resting_heart_rate-.*\.json$", re.I), "_handle_resting_hr"),
    (re.compile(r"Stress Score\.csv$", re.I), "_handle_stress_score"),
    (re.compile(r"Mindfulness Sessions\.csv$", re.I), "_handle_mindfulness"),
    (re.compile(r"menstrual_health_cycles\.csv$", re.I), "_handle_menstrual_cycles"),
]


class FitbitTakeoutParser:
    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return sorted(
            {
                "hrv_rmssd_overnight",
                "respiratory_rate_sleep",
                "spo2",
                "skin_temperature",
                "resting_hr",
                "sleep_session",
                "sleep_rating",
                "sleep_efficiency",
                "active_minutes_very",
                "active_minutes_moderate",
                "active_minutes_light",
                "sedentary_minutes",
                "stress",
                "mindfulness_session",
                _MENSTRUAL_PERIOD_METRIC,
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
            device_manufacturer="Fitbit",
        )
        unmapped: set[str] = set()
        unhandled: dict[str, int] = {}
        matched_any = False
        for member_name, raw in self._iter_members(path):
            handler_name = self._dispatch_name(member_name)
            if handler_name is None:
                stem = member_name.split("/")[-1]
                unhandled[stem] = unhandled.get(stem, 0) + 1
                continue
            matched_any = True
            try:
                getattr(self, handler_name)(member_name, raw, result, unmapped)
            except Exception:
                log.exception("Fitbit: handler %s failed on %s", handler_name, member_name)

        if not matched_any:
            raise ValueError(
                f"{path.name}: no recognized Fitbit Takeout export member "
                "(expected a MyFitbitData folder or zip with Sleep/Heart/"
                "Physical Activity/Stress/Menstrual Health daily-summary files)"
            )
        if unhandled:
            # Collapse per-date file families to their pattern so the note stays
            # bounded (e.g. ~6k intraday files become a handful of lines).
            collapsed: dict[str, int] = {}
            for stem, n in unhandled.items():
                key = _collapse_stem(stem)
                collapsed[key] = collapsed.get(key, 0) + n
            note = "unhandled files: " + ", ".join(
                f"{name} ({n})" for name, n in sorted(collapsed.items())
            )
            result.notes = (result.notes + "; " if result.notes else "") + note

        result.unmapped_metrics = sorted(unmapped)
        result.validate()
        return result

    # ---------------------------- member iteration ----------------------- #

    def _iter_members(self, path: Path) -> Iterator[tuple[str, bytes]]:
        """Yield ``(member_name, raw_bytes)`` for every file in the export.

        Accepts a directory (already-unzipped Takeout, the common case) or a
        ``.zip`` of the same tree. Directory walking streams file bytes lazily
        so the 1 GB+ export is never held in memory at once.
        """
        if path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    yield str(file_path.relative_to(path)), file_path.read_bytes()
        elif path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as zf:
                    for info in zf.infolist():
                        if not info.is_dir():
                            yield info.filename, zf.read(info)
            except (OSError, zipfile.BadZipFile) as exc:
                raise ValueError(f"{path.name}: expected a Fitbit Takeout zip") from exc
        else:
            raise ValueError(
                f"{path.name}: expected a Fitbit Takeout folder or .zip, "
                f"got {path.suffix or 'a non-directory path'}"
            )

    def _dispatch_name(self, member_name: str) -> str | None:
        for pattern, handler_name in _HANDLERS:
            if pattern.search(member_name):
                return handler_name
        return None

    def preview_routing(self, member_names: Sequence[str]) -> RoutingPreview:
        """Name-based dry-run routing preview -- read-only twin of ingest dispatch."""
        return RoutingPreview(entries=[(name, self._dispatch_name(name)) for name in member_names])

    # ------------------------------- CSV handlers ------------------------ #

    def _rows(self, raw: bytes) -> list[dict[str, str]]:
        return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))

    def _emit_point_csv(
        self,
        *,
        member_name: str,
        raw: bytes,
        result: IngestBatch,
        ts_col: str,
        value_col: str,
        metric_id: str,
        unit: str,
        family: str,
    ) -> None:
        """Shared daily-CSV path: one measurement per row from a timestamp + value column."""
        for row in self._rows(raw):
            ts = _parse_iso(row.get(ts_col))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field=f"{family}.{ts_col}",
                        reason=f"unparseable timestamp: {row.get(ts_col)!r}",
                    )
                )
                continue
            try:
                value = _parse_float(row.get(value_col))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field=f"{family}.{value_col}",
                        reason=f"non-numeric value: {row.get(value_col)!r}",
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
                    source_uuid=_synth_uuid(family, ts.isoformat()),
                )
            )

    def _handle_daily_hrv(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_point_csv(
            member_name=member_name,
            raw=raw,
            result=result,
            ts_col="timestamp",
            value_col="rmssd",
            metric_id="hrv_rmssd_overnight",
            unit="ms",
            family="daily_hrv",
        )
        # nremhr (sleeping HR) and entropy are Fitbit-specific derived detail with
        # no canonical home; declare them rather than drop silently.
        unmapped.add("vendor:fitbit:daily_hrv.nremhr")
        unmapped.add("vendor:fitbit:daily_hrv.entropy")

    def _handle_daily_resp(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_point_csv(
            member_name=member_name,
            raw=raw,
            result=result,
            ts_col="timestamp",
            value_col="daily_respiratory_rate",
            metric_id="respiratory_rate_sleep",
            unit="breaths_per_min",
            family="daily_resp",
        )

    def _handle_daily_spo2(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_point_csv(
            member_name=member_name,
            raw=raw,
            result=result,
            ts_col="timestamp",
            value_col="average_value",
            metric_id="spo2",
            unit="pct",
            family="daily_spo2",
        )
        # lower_bound / upper_bound describe the confidence band, not a metric.
        unmapped.add("vendor:fitbit:daily_spo2.lower_bound")
        unmapped.add("vendor:fitbit:daily_spo2.upper_bound")

    def _handle_computed_temp(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in self._rows(raw):
            ts = _parse_iso(row.get("sleep_start"))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="computed_temp.sleep_start",
                        reason=f"unparseable timestamp: {row.get('sleep_start')!r}",
                    )
                )
                continue
            try:
                value = _parse_float(row.get("nightly_temperature"))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="computed_temp.nightly_temperature",
                        reason=f"non-numeric value: {row.get('nightly_temperature')!r}",
                    )
                )
                continue
            if value is None:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id="skin_temperature",
                    unit="celsius",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    source_uuid=_synth_uuid("computed_temp", ts.isoformat()),
                )
            )
        # baseline_relative_* columns are Fitbit's internal deviation statistics.
        unmapped.add("vendor:fitbit:computed_temp.baseline_relative_statistics")

    def _handle_sleep_score(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in self._rows(raw):
            ts = _parse_iso(row.get("timestamp"))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="sleep_score.timestamp",
                        reason=f"unparseable timestamp: {row.get('timestamp')!r}",
                    )
                )
                continue
            base = _synth_uuid("sleep_score", row.get("sleep_log_entry_id"), ts.isoformat())
            try:
                overall = _parse_float(row.get("overall_score"))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="sleep_score.overall_score",
                        reason=f"non-numeric value: {row.get('overall_score')!r}",
                    )
                )
                overall = None
            if overall is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="sleep_rating",
                        unit="score",
                        source_id=SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=overall,
                        source_uuid=f"{base}:rating",
                    )
                )
            try:
                rhr = _parse_float(row.get("resting_heart_rate"))
            except ValueError:
                rhr = None
            if rhr is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="resting_hr",
                        unit="bpm",
                        source_id=SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=rhr,
                        source_uuid=f"{base}:resting_hr",
                    )
                )
        # Composition/revitalization/duration subscores and restlessness are
        # Fitbit-proprietary breakdowns with no canonical metric home.
        unmapped.add("vendor:fitbit:sleep_score.subscores")
        unmapped.add("vendor:fitbit:sleep_score.restlessness")

    def _handle_mindfulness(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in self._rows(raw):
            start = _parse_iso(row.get("start_date_time"))
            end = _parse_iso(row.get("end_date_time"))
            if start is None or end is None or end < start:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="mindfulness.start/end",
                        reason=(
                            f"unparseable or inverted session: "
                            f"start={row.get('start_date_time')!r} end={row.get('end_date_time')!r}"
                        ),
                    )
                )
                continue
            result.intervals.append(
                Interval(
                    start_utc=start,
                    end_utc=end,
                    metric_id="mindfulness_session",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_text=(row.get("activity_name") or None),
                    value_num=(end - start).total_seconds() / 60.0,
                    source_uuid=_synth_uuid(
                        "mindfulness", row.get("session_id") or start.isoformat()
                    ),
                )
            )
        # Per-session HR and the proprietary stress_metrics blob are detail.
        unmapped.add("vendor:fitbit:mindfulness.stress_metrics")

    def _handle_stress_score(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in self._rows(raw):
            ts = _parse_iso(row.get("DATE"))
            if ts is None:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="stress_score.DATE",
                        reason=f"unparseable timestamp: {row.get('DATE')!r}",
                    )
                )
                continue
            # NO_DATA / calculation_failed days carry a 0 sentinel; drop, not store 0.
            status = (row.get("STATUS") or "").strip().upper()
            failed = (row.get("CALCULATION_FAILED") or "").strip().lower() == "true"
            if status == "NO_DATA" or failed:
                continue
            try:
                value = _parse_float(row.get("STRESS_SCORE"))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="stress_score.STRESS_SCORE",
                        reason=f"non-numeric value: {row.get('STRESS_SCORE')!r}",
                    )
                )
                continue
            if value is None:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id="stress",
                    unit="score_0_100",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    value_text=status or None,
                    source_uuid=_synth_uuid("stress_score", ts.isoformat()),
                )
            )
        # Point breakdowns (sleep/responsiveness/exertion) are proprietary detail.
        unmapped.add("vendor:fitbit:stress_score.point_breakdown")

    def _handle_menstrual_cycles(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        for row in self._rows(raw):
            start = _parse_date(row.get("period_start_date"))
            end = _parse_date(row.get("period_end_date"))
            if start is None:
                # A cycle row with no period start carries no loadable interval;
                # cycle-level dates without a period boundary are detail.
                continue
            # A period with no recorded end: treat as a single-day marker rather
            # than fabricating a length.
            end_utc = end + timedelta(days=1) if end is not None else start + timedelta(days=1)
            if end_utc < start:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="menstrual.period_start/end",
                        reason=f"inverted period: start={start.date()} end={end}",
                    )
                )
                continue
            result.intervals.append(
                Interval(
                    start_utc=start,
                    end_utc=end_utc,
                    metric_id=_MENSTRUAL_PERIOD_METRIC,
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    source_uuid=_synth_uuid("menstrual_period", row.get("id") or start.isoformat()),
                )
            )
        # ovulation/fertile windows and cycle boundaries are separate vendor
        # concepts we do not yet map.
        unmapped.add("vendor:fitbit:menstrual.ovulation_fertile_windows")

    # ------------------------------- JSON handlers ----------------------- #

    def _emit_daily_minutes(
        self, raw: bytes, result: IngestBatch, *, metric_id: str, family: str
    ) -> None:
        """Daily active/sedentary-minutes JSON: ``[{dateTime, value}]`` one per day."""
        try:
            docs = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            result.skipped_rows.append(
                SkippedRow(raw_field=f"{family}.json", reason="malformed JSON")
            )
            return
        for rec in docs if isinstance(docs, list) else []:
            if not isinstance(rec, dict):
                continue
            ts = _parse_slashdate(rec.get("dateTime"))
            if ts is None:
                continue
            try:
                value = _parse_float(rec.get("value"))
            except ValueError:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field=f"{family}.value",
                        reason=f"non-numeric value: {rec.get('value')!r}",
                    )
                )
                continue
            if value is None:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id=metric_id,
                    unit="min",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    source_uuid=_synth_uuid(family, ts.isoformat()),
                )
            )

    def _handle_active_minutes_very(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_daily_minutes(
            raw, result, metric_id="active_minutes_very", family="active_minutes_very"
        )

    def _handle_active_minutes_moderate(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_daily_minutes(
            raw, result, metric_id="active_minutes_moderate", family="active_minutes_moderate"
        )

    def _handle_active_minutes_light(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_daily_minutes(
            raw, result, metric_id="active_minutes_light", family="active_minutes_light"
        )

    def _handle_sedentary_minutes(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        self._emit_daily_minutes(
            raw, result, metric_id="sedentary_minutes", family="sedentary_minutes"
        )

    def _handle_resting_hr(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        """resting_heart_rate JSON: ``[{dateTime, value:{date, value, error}}]``.

        A day with no measurement carries ``date: null`` and ``value: 0.0`` -- a
        sentinel, dropped rather than stored as a real 0 bpm reading.
        """
        try:
            docs = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            result.skipped_rows.append(
                SkippedRow(raw_field="resting_hr.json", reason="malformed JSON")
            )
            return
        for rec in docs if isinstance(docs, list) else []:
            if not isinstance(rec, dict):
                continue
            ts = _parse_slashdate(rec.get("dateTime"))
            inner = rec.get("value")
            if ts is None or not isinstance(inner, dict):
                continue
            if inner.get("date") is None:
                continue  # sentinel non-measured day
            try:
                value = _parse_float(inner.get("value"))
            except ValueError:
                continue
            if value is None or value <= 0:
                continue
            result.measurements.append(
                Measurement(
                    ts_utc=ts,
                    metric_id="resting_hr",
                    unit="bpm",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_num=value,
                    source_uuid=_synth_uuid("resting_hr", ts.isoformat()),
                )
            )

    def _handle_sleep_json(
        self, member_name: str, raw: bytes, result: IngestBatch, unmapped: set[str]
    ) -> None:
        """Per-night sleep summary logs -> sleep_session interval + sleep_efficiency."""
        try:
            docs = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            result.skipped_rows.append(SkippedRow(raw_field="sleep.json", reason="malformed JSON"))
            return
        for rec in docs if isinstance(docs, list) else []:
            if not isinstance(rec, dict):
                continue
            start = _parse_iso(rec.get("startTime"))
            end = _parse_iso(rec.get("endTime"))
            if start is None or end is None or end < start:
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field="sleep.startTime/endTime",
                        reason=(
                            f"unparseable or inverted session: "
                            f"start={rec.get('startTime')!r} end={rec.get('endTime')!r}"
                        ),
                    )
                )
                continue
            log_id = rec.get("logId")
            base = _synth_uuid("sleep", log_id, start.isoformat())
            result.intervals.append(
                Interval(
                    start_utc=start,
                    end_utc=end,
                    metric_id="sleep_session",
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    value_text=(rec.get("dateOfSleep") or None),
                    value_num=(end - start).total_seconds() / 3600.0,
                    source_uuid=f"{base}:session",
                )
            )
            try:
                efficiency = _parse_float(rec.get("efficiency"))
            except ValueError:
                efficiency = None
            if efficiency is not None:
                result.measurements.append(
                    Measurement(
                        ts_utc=start,
                        metric_id="sleep_efficiency",
                        unit="pct",
                        source_id=SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=efficiency,
                        source_uuid=f"{base}:efficiency",
                    )
                )


def _collapse_stem(stem: str) -> str:
    """Collapse a per-date/per-id filename to a stable family label for notes."""
    s = re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", stem)
    s = re.sub(r"\d{6,}", "<id>", s)
    s = re.sub(r"-\d+\.json$", "-<n>.json", s)
    return s


__all__ = ["SOURCE_ID", "SOURCE_KIND", "FitbitTakeoutParser"]
