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
]
