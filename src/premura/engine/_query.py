"""Shared Stage 2 warehouse-query helpers.

These helpers are **local to Stage 2** descriptive signals. They read the
user's own facts through a DuckDB connection and answer two narrow needs that
the descriptive signals (``resting_hr_status`` / ``resting_hr_trend`` /
``steps_trend`` / ``weight_trend``) all share:

* find the *latest usable value* and judge its freshness against the metric's
  ``validity_window`` (T006 — status answers);
* extract an *ordered window* of points for trends, distinguishing observed
  points from carried-forward (imputed) ones, but only where the metric's
  ``missing_data_policy`` actually allows carry-forward (T006 — trend answers).

Design rules honored here:

* Respect each metric's ``validity_window`` and ``missing_data_policy`` as
  seeded in ``hp.dim_metric``. Nothing is hard-coded per metric.
* Carry-forward is applied **only** when the metric policy is
  ``last_observation_carried_forward``. A ``none`` policy (e.g. ``steps``) never
  produces an imputed point — gaps stay gaps.
* No schema changes. ``aggregate``/``instantaneous`` metrics are read from
  ``hp.fact_measurement``; ``interval`` metrics from ``hp.fact_interval``.
* All warehouse timestamps are timezone-naive UTC (DuckDB ``TIMESTAMP``), so we
  compare against a naive-UTC "now" consistently. Freshness and window/bucket
  math stay naive-UTC throughout. Each row's ``local_tz`` descriptor is now
  carried alongside ``ts`` (without altering any UTC math) so a downstream
  consumer such as ``correlate`` can resolve the *local* calendar day for
  same-local-day pairing; see :mod:`premura.engine._localtime`.

This module imports nothing from MCP and persists nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ._results import FreshnessState

if TYPE_CHECKING:
    import duckdb

# Policy string seeded in hp.dim_metric.missing_data_policy that permits a
# stale-but-within-window value to be carried forward as the "current" point.
_CARRY_FORWARD_POLICY = "last_observation_carried_forward"


@dataclass(frozen=True)
class MetricPolicy:
    """The Stage-2-relevant facts about a metric, read from ``hp.dim_metric``."""

    metric_id: str
    display_name: str
    unit: str
    value_kind: str
    validity_window_text: str | None
    missing_data_policy: str | None

    @property
    def validity_window(self) -> timedelta | None:
        if self.validity_window_text is None:
            return None
        return parse_iso8601_duration(self.validity_window_text)

    @property
    def carries_forward(self) -> bool:
        """True only when the metric policy explicitly allows LOCF."""
        return self.missing_data_policy == _CARRY_FORWARD_POLICY

    @property
    def is_interval(self) -> bool:
        return self.value_kind == "interval"


@dataclass(frozen=True)
class Observation:
    """One observed warehouse point, normalized across the two fact tables.

    ``local_tz`` is the row's stored local-timezone descriptor (an offset string,
    an IANA zone name, or ``None``); it is carried verbatim for local-calendar-day
    resolution downstream and never used in this module's naive-UTC math.
    """

    ts: datetime
    value: float
    local_tz: str | None = None


@dataclass(frozen=True)
class LatestValue:
    """Result of :func:`latest_usable_value`.

    ``freshness_state`` is the honest trust verdict:

    * ``CURRENT``     — newest observation is within the validity window.
    * ``STALE``       — an observation exists but is older than the window.
    * ``UNAVAILABLE`` — no observation exists at all (``observation`` is None).
    """

    freshness_state: FreshnessState
    observation: Observation | None
    age: timedelta | None


def load_metric_policy(
    conn: duckdb.DuckDBPyConnection,
    metric_id: str,
) -> MetricPolicy | None:
    """Read a metric's display/unit/value_kind and Stage 2 policy fields.

    Returns None when the metric is not registered in ``hp.dim_metric``.
    """
    row = conn.execute(
        """
        SELECT display_name, canonical_unit, value_kind,
               validity_window, missing_data_policy
        FROM hp.dim_metric
        WHERE metric_id = ?
        """,
        [metric_id],
    ).fetchone()
    if row is None:
        return None
    return MetricPolicy(
        metric_id=metric_id,
        display_name=str(row[0]),
        unit=str(row[1]),
        value_kind=str(row[2]),
        validity_window_text=None if row[3] is None else str(row[3]),
        missing_data_policy=None if row[4] is None else str(row[4]),
    )


def fetch_observations(
    conn: duckdb.DuckDBPyConnection,
    policy: MetricPolicy,
    *,
    since: datetime | None = None,
) -> list[Observation]:
    """Return numeric observations for ``policy``'s metric, oldest-first.

    Interval metrics (``steps``) are read from ``hp.fact_interval`` keyed by
    ``end_utc``; point metrics from ``hp.fact_measurement`` keyed by ``ts_utc``.
    Rows with a NULL numeric value are skipped (no fabrication). When ``since``
    is given, only observations at or after it are returned.
    """
    ts_column = "end_utc" if policy.is_interval else "ts_utc"
    table = "hp.fact_interval" if policy.is_interval else "hp.fact_measurement"
    sql = (
        f"SELECT {ts_column} AS ts, value_num AS value, local_tz "  # noqa: S608 - column/table are fixed literals
        f"FROM {table} "
        f"WHERE metric_id = ? AND value_num IS NOT NULL"
    )
    params: list[object] = [policy.metric_id]
    if since is not None:
        sql += f" AND {ts_column} >= ?"
        params.append(since)
    sql += " ORDER BY ts"
    rows = conn.execute(sql, params).fetchall()
    return [
        Observation(
            ts=row[0],
            value=float(row[1]),
            local_tz=None if row[2] is None else str(row[2]),
        )
        for row in rows
    ]


def latest_usable_value(
    conn: duckdb.DuckDBPyConnection,
    policy: MetricPolicy,
    *,
    now: datetime | None = None,
) -> LatestValue:
    """Find the newest observation and judge its freshness.

    Freshness is judged against ``policy.validity_window``. When the window is
    None (no policy seeded) any present value is treated as ``CURRENT`` because
    the metric declares no staleness expectation.

    This refuses to relabel a stale value as current: a present-but-old value is
    returned with ``freshness_state == STALE`` and the caller decides how to
    surface it.
    """
    reference = _naive_utc_now() if now is None else now
    observations = fetch_observations(conn, policy)
    if not observations:
        return LatestValue(
            freshness_state=FreshnessState.UNAVAILABLE,
            observation=None,
            age=None,
        )
    latest = observations[-1]
    age = reference - latest.ts
    window = policy.validity_window
    if window is None or age <= window:
        state = FreshnessState.CURRENT
    else:
        state = FreshnessState.STALE
    return LatestValue(freshness_state=state, observation=latest, age=age)


@dataclass(frozen=True)
class WindowPoint:
    """One point in an ordered trend window.

    ``is_imputed`` is True only for carried-forward points produced under a LOCF
    metric policy. Observed points are always ``is_imputed=False``.

    ``local_tz`` is carried from the source observation (for a carried-forward
    point, from the observation being carried) so a downstream consumer can
    resolve the local calendar day; it never affects this module's UTC math.
    """

    ts: datetime
    value: float
    is_imputed: bool
    local_tz: str | None = None


@dataclass(frozen=True)
class TrendWindow:
    """Ordered window extraction result for trend signals.

    * ``points`` — time-ordered observed (and, for LOCF metrics, carried-forward)
      points within ``[window_start, window_end]``.
    * ``observed_count`` — number of genuinely observed points.
    * ``imputed_count`` — number of carried-forward points (always 0 for a
      ``none`` policy metric such as steps).
    * ``gap_count`` — calendar days inside the window with no observation, NOT
      filled by carry-forward. This is how missing days stay visible as gaps.
    * ``latest_freshness`` — freshness verdict for the newest observed point
      relative to ``window_end``.
    """

    window_start: datetime
    window_end: datetime
    points: list[WindowPoint]
    observed_count: int
    imputed_count: int
    gap_count: int
    latest_freshness: FreshnessState


def ordered_window(
    conn: duckdb.DuckDBPyConnection,
    policy: MetricPolicy,
    *,
    span: timedelta,
    now: datetime | None = None,
    bucket: timedelta = timedelta(days=1),
) -> TrendWindow:
    """Extract an ordered window of points for a trend.

    The window is ``[now - span, now]``, bucketed by ``bucket`` (daily by
    default). Within each bucket the latest observation wins. Buckets with no
    observation become:

    * a **carried-forward** point (``is_imputed=True``) *only* when the metric's
      policy is LOCF **and** a prior observed value is still within the metric's
      ``validity_window`` of that bucket — never beyond the freshness window;
    * otherwise a **gap** (counted in ``gap_count``, no point emitted) so missing
      data stays visible and is never invented.

    A ``none``-policy metric (e.g. steps) therefore yields zero imputed points:
    every missing bucket is a gap.
    """
    reference = _naive_utc_now() if now is None else now
    window_end = reference
    window_start = reference - span

    observations = [
        obs for obs in fetch_observations(conn, policy) if window_start <= obs.ts <= window_end
    ]
    # Latest observation per bucket (bucket keyed by integer index from start).
    by_bucket: dict[int, Observation] = {}
    for obs in observations:
        idx = int((obs.ts - window_start) // bucket)
        existing = by_bucket.get(idx)
        if existing is None or obs.ts >= existing.ts:
            by_bucket[idx] = obs

    bucket_count = int(span // bucket) + 1
    window = policy.validity_window

    points: list[WindowPoint] = []
    observed_count = 0
    imputed_count = 0
    gap_count = 0
    carried: Observation | None = None

    for idx in range(bucket_count):
        bucket_ts = window_start + (idx * bucket)
        bucket_obs = by_bucket.get(idx)
        if bucket_obs is not None:
            points.append(
                WindowPoint(
                    ts=bucket_obs.ts,
                    value=bucket_obs.value,
                    is_imputed=False,
                    local_tz=bucket_obs.local_tz,
                )
            )
            observed_count += 1
            carried = bucket_obs
            continue
        # No observation in this bucket. Carry forward only under LOCF policy and
        # only while the last observed value is still inside its validity window.
        if (
            policy.carries_forward
            and carried is not None
            and (window is None or bucket_ts - carried.ts <= window)
        ):
            points.append(
                WindowPoint(
                    ts=bucket_ts,
                    value=carried.value,
                    is_imputed=True,
                    local_tz=carried.local_tz,
                )
            )
            imputed_count += 1
        else:
            gap_count += 1

    latest_freshness = _window_latest_freshness(observations, window=window, window_end=window_end)

    return TrendWindow(
        window_start=window_start,
        window_end=window_end,
        points=points,
        observed_count=observed_count,
        imputed_count=imputed_count,
        gap_count=gap_count,
        latest_freshness=latest_freshness,
    )


def _window_latest_freshness(
    observations: list[Observation],
    *,
    window: timedelta | None,
    window_end: datetime,
) -> FreshnessState:
    if not observations:
        return FreshnessState.UNAVAILABLE
    latest = max(observations, key=lambda obs: obs.ts)
    if window is None or window_end - latest.ts <= window:
        return FreshnessState.CURRENT
    return FreshnessState.STALE


def _naive_utc_now() -> datetime:
    """Naive-UTC now, matching DuckDB's timezone-naive TIMESTAMP storage."""
    return datetime.now(tz=UTC).replace(tzinfo=None)


def parse_iso8601_duration(value: str) -> timedelta:
    """Parse the small ISO-8601 duration subset used in ``hp.dim_metric``.

    Mirrors the engine's own parser (years≈365d, months≈30d) so Stage 2
    freshness math agrees with :func:`premura.engine.check_inputs_available`.
    """
    match = re.fullmatch(
        r"P(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<weeks>\d+)W)?"
        r"(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?)?",
        value,
    )
    if match is None or not any(match.groupdict().values()):
        raise ValueError(f"unsupported ISO-8601 duration: {value}")
    parts = {name: int(raw) if raw is not None else 0 for name, raw in match.groupdict().items()}
    return timedelta(
        days=(parts["years"] * 365) + (parts["months"] * 30) + (parts["weeks"] * 7) + parts["days"],
        seconds=(parts["hours"] * 3600) + (parts["minutes"] * 60) + parts["seconds"],
    )


__all__ = [
    "MetricPolicy",
    "Observation",
    "LatestValue",
    "WindowPoint",
    "TrendWindow",
    "load_metric_policy",
    "fetch_observations",
    "latest_usable_value",
    "ordered_window",
    "parse_iso8601_duration",
]
