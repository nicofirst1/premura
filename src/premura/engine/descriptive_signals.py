"""Built-in descriptive Stage 2 signals (WP02).

The first wave of grounded, freshness-aware answers that replace raw-table
direct reads:

* ``resting_hr_status`` — status family: "What is my resting HR right now, and
  can I trust it?"
* ``resting_hr_trend``  — trend family: "Is my resting HR going up/down/flat?"
* ``steps_trend``       — trend family: "Are my daily steps trending?" (steps
  has ``missing_data_policy: none`` so it NEVER imputes — gaps stay gaps).
* ``weight_trend``      — trend family: "Is my weight rising/falling/flat?"
  (weight allows carry-forward within its freshness window; carried-forward
  points are visible and caveated).

Each function reads only the user's own warehouse data through the shared
Stage 2 query helpers in :mod:`premura.engine._query`, and returns one of the
shared result envelopes from :mod:`premura.engine._results`. They are
**descriptive only**: no reference ranges, no diagnosis, no significance, no
BMI/body-composition or profile-dependent behavior. Freshness, gaps, and
carried-forward points are made explicit so Stage 3 never overstates trust.

Registration follows the built-in module contract (CONTRACT.md): this module
exposes :func:`register_builtin_signals`, which the engine's static built-in
loader calls. See the WP02 report note about ``_BUILTIN_SIGNAL_MODULES``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from . import _query
from ._registry import REGISTRY, SignalSpec
from ._results import (
    FreshnessState,
    StatusResult,
    TrendDirection,
    TrendPoint,
    TrendResult,
)

if TYPE_CHECKING:
    import duckdb

# Default trend span: a few weeks of daily points, enough to read direction
# without overreaching. Plain, descriptive — not a clinical window.
_TREND_SPAN = timedelta(days=28)

# Minimum genuinely-observed points before we will name a direction at all.
# Below this we report UNKNOWN rather than turn a sparse series into a claim.
_MIN_TREND_OBSERVATIONS = 3

# Relative deadband: |last - first| must exceed this fraction of the baseline
# magnitude to count as up/down rather than flat. Keeps tiny wobble honest.
_FLAT_REL_TOLERANCE = 0.02


# --------------------------------------------------------------------------- #
# T007 — resting_hr_status
# --------------------------------------------------------------------------- #
def resting_hr_status(conn: duckdb.DuckDBPyConnection) -> StatusResult:
    """Latest usable resting HR with an honest freshness verdict.

    Refuses to present stale data as current: a present-but-old value comes back
    as ``STALE`` (value retained, but caveated), and an absent value as
    ``UNAVAILABLE`` (value omitted). No trend, reference-range, or training
    interpretation.
    """
    return _status("resting_hr_status", "resting_hr", conn)


# --------------------------------------------------------------------------- #
# T008 — resting_hr_trend
# --------------------------------------------------------------------------- #
def resting_hr_trend(conn: duckdb.DuckDBPyConnection) -> TrendResult:
    """Direction of resting HR over recent weeks, with carried-forward visible.

    resting_hr is a LOCF metric, so within-window missing days appear as
    carried-forward (imputed) points and are counted/caveated; days beyond the
    freshness window stay gaps. Sparse series report ``UNKNOWN`` direction.
    """
    return _trend("resting_hr_trend", "resting_hr", conn)


# --------------------------------------------------------------------------- #
# T009 — steps_trend
# --------------------------------------------------------------------------- #
def steps_trend(conn: duckdb.DuckDBPyConnection) -> TrendResult:
    """Direction of daily steps, with ZERO imputed points.

    steps has ``missing_data_policy: none`` — the shared helper therefore never
    carries a value forward. Missing days are visible as gaps, never invented
    continuity. (steps is an interval metric, read from hp.fact_interval.)
    """
    return _trend("steps_trend", "steps", conn)


# --------------------------------------------------------------------------- #
# T010 — weight_trend
# --------------------------------------------------------------------------- #
def weight_trend(conn: duckdb.DuckDBPyConnection) -> TrendResult:
    """Direction of body weight over the last month, carry-forward made visible.

    weight is a LOCF metric with a P1W validity window: a recent reading may be
    carried forward across in-between days (flagged as imputed + caveated), but
    a reading older than the window is NOT presented as current — those days
    become gaps. No BMI / body-composition / profile-dependent behavior.
    """
    return _trend("weight_trend", "weight", conn)


# --------------------------------------------------------------------------- #
# Shared implementation
# --------------------------------------------------------------------------- #
def _status(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
) -> StatusResult:
    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        # Metric not in dim_metric at all — nothing usable to report.
        return StatusResult(
            signal_name=signal_name,
            metric_id=metric_id,
            display_name=metric_id,
            unit="",
            freshness_state=FreshnessState.UNAVAILABLE,
            validity_window="unknown",
            value=None,
            observed_at=None,
            caveats=[f"No metric definition found for {metric_id!r}."],
        ).validate()

    window_text = policy.validity_window_text or "unspecified"
    latest = _query.latest_usable_value(conn, policy)

    if latest.freshness_state is FreshnessState.UNAVAILABLE:
        return StatusResult(
            signal_name=signal_name,
            metric_id=metric_id,
            display_name=policy.display_name,
            unit=policy.unit,
            freshness_state=FreshnessState.UNAVAILABLE,
            validity_window=window_text,
            value=None,
            observed_at=None,
            caveats=[f"No {policy.display_name.lower()} value has been recorded."],
        ).validate()

    assert latest.observation is not None  # narrow for type-checkers
    caveats: list[str] = []
    if latest.freshness_state is FreshnessState.STALE:
        caveats.append(
            f"Latest {policy.display_name.lower()} reading is older than its "
            f"{window_text} freshness window; it may no longer reflect now."
        )

    return StatusResult(
        signal_name=signal_name,
        metric_id=metric_id,
        display_name=policy.display_name,
        unit=policy.unit,
        freshness_state=latest.freshness_state,
        validity_window=window_text,
        value=latest.observation.value,
        observed_at=latest.observation.ts,
        caveats=caveats,
    ).validate()


def _trend(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
) -> TrendResult:
    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        now = _query._naive_utc_now()
        return TrendResult(
            signal_name=signal_name,
            metric_id=metric_id,
            window_start=now - _TREND_SPAN,
            window_end=now,
            trend_direction=TrendDirection.UNKNOWN,
            current_freshness_state=FreshnessState.UNAVAILABLE,
            points=[],
            imputed_point_count=0,
            gap_count=0,
            caveats=[f"No metric definition found for {metric_id!r}."],
        ).validate()

    window = _query.ordered_window(conn, policy, span=_TREND_SPAN)
    points = [
        TrendPoint(ts=p.ts, value=p.value, is_imputed=p.is_imputed)
        for p in window.points
    ]

    direction = _direction(window.observed_count, window.points)
    caveats = _trend_caveats(policy, window, direction)

    return TrendResult(
        signal_name=signal_name,
        metric_id=metric_id,
        window_start=window.window_start,
        window_end=window.window_end,
        trend_direction=direction,
        current_freshness_state=window.latest_freshness,
        points=points,
        imputed_point_count=window.imputed_count,
        gap_count=window.gap_count,
        caveats=caveats,
    ).validate()


def _direction(
    observed_count: int,
    points: list[_query.WindowPoint],
) -> TrendDirection:
    """Plain up/down/flat direction; UNKNOWN when too sparse to trust.

    Uses only genuinely observed points to decide first/last; imputed
    (carried-forward) points must not manufacture a direction on their own.
    """
    if observed_count < _MIN_TREND_OBSERVATIONS:
        return TrendDirection.UNKNOWN
    observed = [p for p in points if not p.is_imputed]
    if len(observed) < 2:
        return TrendDirection.UNKNOWN
    first = observed[0].value
    last = observed[-1].value
    delta = last - first
    tolerance = abs(first) * _FLAT_REL_TOLERANCE
    if abs(delta) <= tolerance:
        return TrendDirection.FLAT
    return TrendDirection.UP if delta > 0 else TrendDirection.DOWN


def _trend_caveats(
    policy: _query.MetricPolicy,
    window: _query.TrendWindow,
    direction: TrendDirection,
) -> list[str]:
    caveats: list[str] = []
    if direction is TrendDirection.UNKNOWN:
        caveats.append(
            "Not enough observed points in this window to describe a direction."
        )
    if window.imputed_count > 0:
        caveats.append(
            f"{window.imputed_count} point(s) are carried forward from an earlier "
            "reading (no new measurement that day), not freshly observed."
        )
    if window.gap_count > 0:
        caveats.append(
            f"{window.gap_count} day(s) in this window have no measurement and are "
            "left as gaps rather than filled in."
        )
    if window.latest_freshness is FreshnessState.STALE:
        caveats.append(
            "The most recent reading is older than its freshness window, so the "
            "latest point may not reflect now."
        )
    elif window.latest_freshness is FreshnessState.UNAVAILABLE:
        caveats.append("No readings fall within the requested window.")
    return caveats


# --------------------------------------------------------------------------- #
# Built-in registration (CONTRACT.md built-in loading contract)
# --------------------------------------------------------------------------- #
def register_builtin_signals() -> None:
    """Register WP02's descriptive signals into :data:`REGISTRY`.

    Called by the engine's static built-in loader for every module listed in
    ``premura.engine._BUILTIN_SIGNAL_MODULES``. See the WP02 report: this module
    must be added to that list (one line, in WP01-owned ``__init__.py``) for
    production auto-discovery; until then tests invoke this function directly.
    """
    _register(
        SignalSpec(
            name="resting_hr_status",
            domain=["cardiovascular", "recovery"],
            inputs=["resting_hr"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=resting_hr_status,
            question="What is my resting heart rate right now, and can I trust it?",
            family="status",
            missing_input_hint=(
                "Connect a wearable that records daily resting heart rate to "
                "answer this."
            ),
        )
    )
    _register(
        SignalSpec(
            name="resting_hr_trend",
            domain=["cardiovascular", "recovery"],
            inputs=["resting_hr"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=resting_hr_trend,
            question="Is my resting heart rate going up, down, or flat recently?",
            family="trend",
            missing_input_hint=(
                "Connect a wearable that records daily resting heart rate to "
                "answer this."
            ),
        )
    )
    _register(
        SignalSpec(
            name="steps_trend",
            domain=["activity"],
            inputs=["steps"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=steps_trend,
            question="Are my daily steps trending up or down?",
            family="trend",
            missing_input_hint=(
                "Connect a step-tracking source to answer this."
            ),
            caveat_summary=(
                "Step days with no record are shown as gaps, not zero days.",
            ),
        )
    )
    _register(
        SignalSpec(
            name="weight_trend",
            domain=["body_composition"],
            inputs=["weight"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=weight_trend,
            question="Is my weight rising, falling, or flat over the last month?",
            family="trend",
            missing_input_hint=(
                "Record body weight (e.g. from a smart scale) to answer this."
            ),
            caveat_summary=(
                "Days without a new weigh-in reuse the last reading within its "
                "freshness window and are flagged as carried forward.",
            ),
        )
    )


def _register(spec: SignalSpec) -> None:
    REGISTRY[spec.name] = spec


__all__ = [
    "resting_hr_status",
    "resting_hr_trend",
    "steps_trend",
    "weight_trend",
    "register_builtin_signals",
]
