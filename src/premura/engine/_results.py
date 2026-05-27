"""Shared Stage 2 result envelopes — the output vocabulary for grounded signals.

The six grounded Stage 2 functions land in this mission cluster into four
logical result families. Rather than each function inventing an ad-hoc dict,
they return one of the typed envelopes below. Stage 3 MCP wrappers can then
serialize any of them with :meth:`Result.to_dict` instead of reverse-engineering
each function's shape.

Families (see ``data-model.md`` and CONTRACT.md):

* :class:`StatusResult`             — "what is X right now?"
* :class:`TrendResult`              — "which way has X been going?"
* :class:`BaselineComparisonResult` — "how does the latest X compare to my own normal?"
* :class:`ChangeAroundDateResult`   — "did X change around this date?"

Plus the cross-cutting :class:`MissingInputReport` for when a tool cannot
produce a grounded answer at all.

Design notes
------------
* These are plain frozen dataclasses, easy to serialize for MCP — every
  envelope exposes ``to_dict()`` returning JSON-friendly primitives.
* The families are deliberately distinct, not collapsed into one catch-all
  object: the fields a trend needs differ from the fields a before/after
  comparison needs.
* Every family carries a ``caveats`` list and (where the family has a "latest"
  value) a freshness state, so Stage 3 never has to guess about trust.
* This module imports nothing from MCP and nothing from the warehouse layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


def _iso(value: datetime | date | None) -> str | None:
    """Serialize a datetime/date to ISO-8601, passing through None."""
    if value is None:
        return None
    return value.isoformat()


class FreshnessState(StrEnum):
    """Primary trust signal for a "latest value" result.

    ``current`` — the value is within its freshness expectation.
    ``stale``   — present but older than the validity window allows.
    ``unavailable`` — no usable value exists.
    """

    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class TrendDirection(StrEnum):
    """Plain direction of a trend. Never a significance claim."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class ComparisonState(StrEnum):
    """Relative position of the latest value versus the user's own baseline."""

    BELOW = "below"
    WITHIN = "within"
    ABOVE = "above"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StatusResult:
    """"What is X right now?" — used by e.g. ``resting_hr_status``."""

    signal_name: str
    metric_id: str
    display_name: str
    unit: str
    freshness_state: FreshnessState
    validity_window: str
    value: float | None = None
    """Latest usable value. MUST be None when ``freshness_state`` is
    ``unavailable`` (see :meth:`validate`)."""
    observed_at: datetime | None = None
    caveats: list[str] = field(default_factory=list)

    def validate(self) -> StatusResult:
        if self.freshness_state is FreshnessState.UNAVAILABLE:
            if self.value is not None:
                raise ValueError("StatusResult.value must be None when unavailable")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "status",
            "signal_name": self.signal_name,
            "metric_id": self.metric_id,
            "display_name": self.display_name,
            "unit": self.unit,
            "value": self.value,
            "observed_at": _iso(self.observed_at),
            "freshness_state": self.freshness_state.value,
            "validity_window": self.validity_window,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class TrendPoint:
    """One ordered point used to build a :class:`TrendResult`."""

    ts: datetime
    value: float
    is_imputed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": _iso(self.ts),
            "value": self.value,
            "is_imputed": self.is_imputed,
        }


@dataclass(frozen=True)
class TrendResult:
    """"Which way has X been going?" — used by trend signals (HR / steps / weight)."""

    signal_name: str
    metric_id: str
    window_start: datetime
    window_end: datetime
    trend_direction: TrendDirection
    current_freshness_state: FreshnessState
    points: list[TrendPoint] = field(default_factory=list)
    imputed_point_count: int = 0
    gap_count: int = 0
    caveats: list[str] = field(default_factory=list)

    def validate(self) -> TrendResult:
        ordered = all(
            self.points[i].ts <= self.points[i + 1].ts
            for i in range(len(self.points) - 1)
        )
        if not ordered:
            raise ValueError("TrendResult.points must be time-ordered")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "trend",
            "signal_name": self.signal_name,
            "metric_id": self.metric_id,
            "window_start": _iso(self.window_start),
            "window_end": _iso(self.window_end),
            "trend_direction": self.trend_direction.value,
            "points": [point.to_dict() for point in self.points],
            "current_freshness_state": self.current_freshness_state.value,
            "imputed_point_count": self.imputed_point_count,
            "gap_count": self.gap_count,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class BaselineComparisonResult:
    """"How does the latest X compare to my own normal?" — used by ``sleep_deep_pct_baseline``.

    ``comparison_state`` describes own-baseline position ONLY, never any
    population interpretation. ``baseline_mean`` must be derived from the
    user's own prior values.
    """

    signal_name: str
    metric_id: str
    baseline_window: str
    comparison_state: ComparisonState
    freshness_state: FreshnessState
    latest_value: float | None = None
    """Latest usable value. MUST be None when ``freshness_state`` is
    ``unavailable`` (see :meth:`validate`)."""
    baseline_mean: float | None = None
    """Mean of the user's own prior values. MUST be None when
    ``comparison_state`` is ``unknown`` — no trustworthy baseline was formed
    (see :meth:`validate`)."""
    caveats: list[str] = field(default_factory=list)

    def validate(self) -> BaselineComparisonResult:
        if self.freshness_state is FreshnessState.UNAVAILABLE:
            if self.latest_value is not None:
                raise ValueError(
                    "BaselineComparisonResult.latest_value must be None when "
                    "unavailable"
                )
        if self.comparison_state is ComparisonState.UNKNOWN:
            if self.baseline_mean is not None:
                raise ValueError(
                    "BaselineComparisonResult.baseline_mean must be None when "
                    "comparison_state is unknown"
                )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "baseline",
            "signal_name": self.signal_name,
            "metric_id": self.metric_id,
            "latest_value": self.latest_value,
            "baseline_mean": self.baseline_mean,
            "baseline_window": self.baseline_window,
            "comparison_state": self.comparison_state.value,
            "freshness_state": self.freshness_state.value,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class ChangeAroundDateResult:
    """"Did X change around this date?" — used by ``hrv_change_around_date``.

    Reports before/after means around a user-supplied anchor date. Never
    includes p-values, confidence intervals, or causal interpretation; the
    ``caveats`` must explicitly disclaim significance and causation.
    """

    signal_name: str
    metric_id: str
    anchor_date: date
    before_count: int
    after_count: int
    sufficient_data: bool
    before_mean: float | None = None
    after_mean: float | None = None
    delta: float | None = None
    caveats: list[str] = field(default_factory=list)

    def validate(self) -> ChangeAroundDateResult:
        if not self.sufficient_data and self.delta is not None:
            raise ValueError(
                "ChangeAroundDateResult.delta must be None when sufficient_data is False"
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "change",
            "signal_name": self.signal_name,
            "metric_id": self.metric_id,
            "anchor_date": _iso(self.anchor_date),
            "before_mean": self.before_mean,
            "after_mean": self.after_mean,
            "delta": self.delta,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "sufficient_data": self.sufficient_data,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class MissingInputReport:
    """Returned by Stage 3 when a tool cannot produce a grounded answer.

    ``message`` must not imply diagnosis or external reference data.
    """

    tool_name: str
    required_inputs: list[str]
    message: str
    missing_inputs: list[str] = field(default_factory=list)
    stale_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "missing_input",
            "tool_name": self.tool_name,
            "required_inputs": list(self.required_inputs),
            "missing_inputs": list(self.missing_inputs),
            "stale_inputs": list(self.stale_inputs),
            "message": self.message,
        }


@dataclass(frozen=True)
class MetricCatalogEntry:
    """One entry in the Stage 2 metric catalog.

    Reports declared metadata plus a computed validity status and latest usable
    observation. No raw row-counts or all-time extrema. Numeric fields are
    optional so an ``unavailable`` entry can serialize without fabricated data.

    ``validity_status`` is the honest freshness verdict for the latest
    available observation:

    * ``current``     — latest observation is within the validity window.
    * ``stale``       — present but older than the validity window allows.
    * ``unavailable`` — no usable observation exists.

    ``validity_window`` is the metric's declared window from ``hp.dim_metric``
    (ISO-8601 duration text), or None when no window is seeded.
    """

    metric_id: str
    validity_status: FreshnessState
    validity_window: str | None
    missing_data_policy: str | None
    unit: str
    latest_observation_at: datetime | None = None
    """Timestamp of the latest usable observation. MUST be None when
    ``validity_status`` is ``unavailable``."""
    latest_value: float | None = None
    """Latest numeric value. MUST be None when ``validity_status`` is
    ``unavailable``."""
    message: str | None = None
    """Optional human-readable context (e.g. why the metric is unavailable).
    Must not contain diagnosis or external reference data."""

    def validate(self) -> MetricCatalogEntry:
        if self.validity_status is FreshnessState.UNAVAILABLE:
            if self.latest_value is not None:
                raise ValueError(
                    "MetricCatalogEntry.latest_value must be None when unavailable"
                )
            if self.latest_observation_at is not None:
                raise ValueError(
                    "MetricCatalogEntry.latest_observation_at must be None when unavailable"
                )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "metric_catalog",
            "metric_id": self.metric_id,
            "validity_status": self.validity_status.value,
            "validity_window": self.validity_window,
            "missing_data_policy": self.missing_data_policy,
            "unit": self.unit,
            "latest_observation_at": _iso(self.latest_observation_at),
            "latest_value": self.latest_value,
            "message": self.message,
        }


@dataclass(frozen=True)
class MetricSummaryEntry:
    """Per-metric validity summary over a fixed 30-day window.

    Extends :class:`MetricCatalogEntry` with explicit coverage and imputation
    metadata for the recent window. No all-time extrema or raw row counts.

    ``sample_size``        — number of genuinely observed data points in the
                             30-day window.
    ``imputed_proportion`` — fraction of the window that relied on
                             carried-forward (LOCF) imputation. Always 0.0
                             for metrics with ``missing_data_policy: none``.
    ``gap_count``          — calendar days inside the window with no
                             observation and no carry-forward fill.
    ``window_days``        — fixed window length (always 30).

    Numeric coverage fields are None (not fabricated) when the metric is
    ``unavailable``.
    """

    metric_id: str
    validity_status: FreshnessState
    validity_window: str | None
    missing_data_policy: str | None
    unit: str
    window_days: int
    latest_observation_at: datetime | None = None
    """Timestamp of the latest usable observation in the window. None when unavailable."""
    latest_value: float | None = None
    """Latest numeric value in the window. None when unavailable."""
    sample_size: int | None = None
    """Number of genuinely observed data points in the window. None when unavailable."""
    imputed_proportion: float | None = None
    """Fraction of bucketed window slots that were carried-forward. 0.0 for no-imputation
    policies. None when unavailable."""
    gap_count: int | None = None
    """Calendar days in the window with no observation and no carry-forward. None when
    unavailable."""
    message: str | None = None
    """Optional human-readable context. Must not contain diagnosis or external reference."""

    def validate(self) -> MetricSummaryEntry:
        if self.validity_status is FreshnessState.UNAVAILABLE:
            if self.latest_value is not None:
                raise ValueError(
                    "MetricSummaryEntry.latest_value must be None when unavailable"
                )
            if self.latest_observation_at is not None:
                raise ValueError(
                    "MetricSummaryEntry.latest_observation_at must be None when unavailable"
                )
        if self.imputed_proportion is not None and not (0.0 <= self.imputed_proportion <= 1.0):
            raise ValueError(
                "MetricSummaryEntry.imputed_proportion must be in [0.0, 1.0]"
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "metric_summary",
            "metric_id": self.metric_id,
            "validity_status": self.validity_status.value,
            "validity_window": self.validity_window,
            "missing_data_policy": self.missing_data_policy,
            "unit": self.unit,
            "window_days": self.window_days,
            "latest_observation_at": _iso(self.latest_observation_at),
            "latest_value": self.latest_value,
            "sample_size": self.sample_size,
            "imputed_proportion": self.imputed_proportion,
            "gap_count": self.gap_count,
            "message": self.message,
        }


__all__ = [
    "FreshnessState",
    "TrendDirection",
    "ComparisonState",
    "StatusResult",
    "TrendPoint",
    "TrendResult",
    "BaselineComparisonResult",
    "ChangeAroundDateResult",
    "MissingInputReport",
    "MetricCatalogEntry",
    "MetricSummaryEntry",
]
