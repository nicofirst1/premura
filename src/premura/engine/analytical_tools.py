"""Stage 3 — the two proof analytical tools (WP04), behind the WP02 contract.

This module ships the *only* two tools the Stage 3 analytical mission needs to
prove the contract seam:

* :func:`change_point` — a single-level-shift detector over one ordered series
  (research note D2 / the ``level_shift_detection`` question), and
* :func:`smoothed_average` — a trailing rolling mean over one ordered series
  (research note D3 / the ``smoothed_pattern`` question).

Both are *registrations against the WP02 contract*, not new dispatcher
branches: importing this module runs the :func:`~premura.engine.analytical_contract.analytical_tool`
decorators, which add the tools to the shared ``REGISTRY``. WP05's public
surface can then discover and dispatch them through
:func:`~premura.engine.analytical_contract.dispatch` with no per-tool code.

Both tools consume the WP03 admissible-input layer rather than raw points: each
takes a prepared :class:`~premura.engine.analytical_inputs.AnalyticalInputSeries`
and obtains its computation points *only* through
:func:`~premura.engine.analytical_inputs.points_for_computation`. That helper
raises on a refused input, so a refused series short-circuits to a refusal
envelope **before** any arithmetic — the refusal path can never be bypassed.

Doctrine the implementations hold to (research note "Consequences"):

* **Descriptive honesty.** Results name a *when* and a *how much*, never a
  *why*. No causal language, no diagnostic labels, no prediction claims, and no
  p-value or significance claims appear in any estimate, caveat, or message.
* **Determinism.** Given the same prepared series, parameters, and revision, a
  tool returns a byte-identical envelope. No randomness, no clock reads.
* **Missingness stays visible.** The smoothed average never fills long gaps; it
  carries effective window, usable count, coverage, and imputation forward.
* **Refusal is first-class.** Out-of-bounds parameters and series too small for
  the method return a distinct :class:`~premura.engine.analytical_contract.RefusalOutcome`
  and no estimate.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from premura.engine.analytical_contract import (
    AnalyticalQuestionType,
    AnalyticalResultEnvelope,
    AnalyticalStatus,
    ConfoundEntry,
    ConfoundKey,
    RefusalOutcome,
    Uncertainty,
    analytical_tool,
)
from premura.engine.analytical_inputs import (
    AnalyticalInputSeries,
    points_for_computation,
)

__all__ = [
    "CHANGE_POINT_TOOL",
    "SMOOTHED_AVERAGE_TOOL",
    "DEFAULT_MIN_SIDE_OBSERVATIONS",
    "DEFAULT_SMOOTHING_WINDOW",
    "DEFAULT_MIN_COVERAGE",
    "MAX_SMOOTHING_WINDOW",
    "change_point",
    "smoothed_average",
]

# Tool names — the keys under which these register in the shared REGISTRY.
CHANGE_POINT_TOOL = "change_point"
SMOOTHED_AVERAGE_TOOL = "smoothed_average"

# ---------------------------------------------------------------------------
# change_point parameter bounds (research note D2)
# ---------------------------------------------------------------------------

DEFAULT_MIN_SIDE_OBSERVATIONS = 2
"""Minimum usable observations a candidate split must leave on *both* sides.

A split with fewer points than this on either side is not a candidate; below
the smallest usable value the request is refused as ``unsupported_parameter``."""

_MIN_ALLOWED_SIDE_OBSERVATIONS = 2
"""The smallest ``min_side_observations`` the method supports. Two points per
side is the minimum needed to speak of a before/after level at all; one point
gives no spread to standardize against."""


# ---------------------------------------------------------------------------
# smoothed_average parameter bounds (research note D3)
# ---------------------------------------------------------------------------

DEFAULT_SMOOTHING_WINDOW = 7
"""Default trailing window length (in observations)."""

MAX_SMOOTHING_WINDOW = 365
"""Upper bound on the trailing window. A window larger than this, or larger than
the series, is out of bounds and refused rather than silently truncated."""

DEFAULT_MIN_COVERAGE = 0.5
"""Default minimum fraction of a trailing window that must be non-imputed for an
output point to be emitted. Below this fraction the point is left blank so
missingness stays visible — the method never fills long gaps."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _refusal_envelope(
    tool_name: str,
    series: AnalyticalInputSeries,
    refusal: RefusalOutcome,
) -> AnalyticalResultEnvelope:
    """Build a validated refusal envelope carrying no estimate."""
    return AnalyticalResultEnvelope(
        tool_name=tool_name,
        status=AnalyticalStatus.REFUSED,
        inputs=(series.metric_id,),
        refusal=refusal.validate(),
    ).validate()


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _population_std(values: Sequence[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _round(value: float, places: int = 6) -> float:
    """Stable rounding so repeated serialization is byte-identical."""
    return round(value, places)


# ---------------------------------------------------------------------------
# T013 — change_point (single-level-shift detector)
# ---------------------------------------------------------------------------


@analytical_tool(
    name=CHANGE_POINT_TOOL,
    description=(
        "Single-level-shift detector over one admissible ordered series. Reports "
        "the split with the largest absolute standardized level difference between "
        "its before-mean and after-mean. Descriptive only: it names when the level "
        "changed and by how much, never why, and carries no p-value."
    ),
    input_shape="single_ordered_series",
    parameters=("min_side_observations",),
    result_kind="change_point_estimate",
    confound_keys=(
        ConfoundKey.LOW_SAMPLE_SIZE.value,
        ConfoundKey.HIGH_IMPUTATION.value,
        ConfoundKey.PARAMETER_AT_LIMIT.value,
        ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ConfoundKey.TEMPORAL_AUTOCORRELATION.value,
        ConfoundKey.LIFE_EVENT_SENSITIVE.value,
    ),
    question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    revision="1",
)
def change_point(
    series: AnalyticalInputSeries,
    *,
    min_side_observations: int = DEFAULT_MIN_SIDE_OBSERVATIONS,
) -> AnalyticalResultEnvelope:
    """Detect a single level shift in one admissible ordered series (research D2).

    The tool consumes a prepared :class:`AnalyticalInputSeries`. It obtains its
    points only through :func:`points_for_computation`, so a refused series can
    never reach computation. When the series is refused, the same refusal is
    surfaced as the result envelope.

    It scans every split that leaves at least ``min_side_observations`` usable
    points on both sides, computes the before-mean and after-mean for each, and
    selects the split with the **largest absolute standardized level
    difference** (the absolute mean gap divided by the pooled spread). The
    estimate reports the split time, the before/after levels, the signed
    difference, the direction of the shift, the sample counts on each side, and
    the method revision. It carries **no p-value and no causal label**.

    Refuses (no estimate) when ``min_side_observations`` is below the supported
    minimum, or when the usable window is too small to leave that many points on
    both sides of any split.
    """
    # Refused input short-circuits here: points_for_computation raises on a
    # refused series, so we surface the refusal as the result envelope rather
    # than computing over points we should not have.
    if series.refusal is not None:
        return _refusal_envelope(CHANGE_POINT_TOOL, series, series.refusal)

    points = points_for_computation(series)
    n = len(points)

    # Parameter-bound refusal (out-of-bounds parameter -> no estimate).
    if min_side_observations < _MIN_ALLOWED_SIDE_OBSERVATIONS:
        return _refusal_envelope(
            CHANGE_POINT_TOOL,
            series,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    f"change_point needs at least {_MIN_ALLOWED_SIDE_OBSERVATIONS} "
                    f"observations on each side of a split; "
                    f"min_side_observations={min_side_observations} is below that bound."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="min_side_observations",
            ),
        )

    # A split at index k uses points[:k] as "before" and points[k:] as "after".
    # Valid k runs from min_side_observations to n - min_side_observations so
    # both sides keep at least the required number of observations.
    first_split = min_side_observations
    last_split = n - min_side_observations
    if first_split > last_split:
        return _refusal_envelope(
            CHANGE_POINT_TOOL,
            series,
            RefusalOutcome(
                reason="insufficient_data",
                message=(
                    f"change_point needs at least {2 * min_side_observations} usable "
                    f"observations to leave {min_side_observations} on each side of a "
                    f"split, but only {n} are available for metric "
                    f"'{series.metric_id}'."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="min_side_observations",
            ),
        )

    values = [p.value for p in points]

    best_k: int | None = None
    best_score = -1.0
    best_before_mean = 0.0
    best_after_mean = 0.0
    best_pooled_std = 0.0

    for k in range(first_split, last_split + 1):
        before = values[:k]
        after = values[k:]
        before_mean = _mean(before)
        after_mean = _mean(after)
        # Pooled spread across both sides; population std keeps the estimate
        # deterministic and avoids a degrees-of-freedom policy choice. This is a
        # standardized *level difference*, not a test statistic — no p-value.
        pooled = before + after
        pooled_std = _population_std(pooled, _mean(pooled))
        gap = abs(after_mean - before_mean)
        # When the pooled spread is zero (a perfectly flat series) the raw gap is
        # the score; this only happens when gap is also zero, so all splits tie.
        score = gap / pooled_std if pooled_std > 0.0 else gap
        # Strict ">" keeps the earliest split on ties -> deterministic selection.
        if score > best_score:
            best_score = score
            best_k = k
            best_before_mean = before_mean
            best_after_mean = after_mean
            best_pooled_std = pooled_std

    assert best_k is not None  # guaranteed: first_split <= last_split

    before_count = best_k
    after_count = n - best_k
    split_point = points[best_k]
    signed_diff = best_after_mean - best_before_mean
    if signed_diff > 0:
        direction = "increase"
    elif signed_diff < 0:
        direction = "decrease"
    else:
        direction = "flat"

    estimate = {
        "split_time": split_point.ts.isoformat(),
        "split_index": best_k,
        "before_level": _round(best_before_mean),
        "after_level": _round(best_after_mean),
        "level_difference": _round(signed_diff),
        "direction": direction,
        "before_sample_size": before_count,
        "after_sample_size": after_count,
        "method_revision": "1",
    }

    # Uncertainty DESCRIBES the support around the selected split. It is the
    # standardized level difference and the per-side spread — deliberately NOT a
    # p-value or any significance claim.
    uncertainty = Uncertainty(
        available=True,
        payload={
            "standardized_level_difference": _round(best_score),
            "pooled_spread": _round(best_pooled_std),
        },
    )

    confounds: list[ConfoundEntry] = []
    if min(before_count, after_count) <= min_side_observations:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.LOW_SAMPLE_SIZE,
                detail=(
                    "The selected split leaves close to the minimum usable "
                    "observations on one side."
                ),
            )
        )
    if series.is_imputed_pct >= 50.0:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.HIGH_IMPUTATION,
                detail="More than half of the usable series was carried-forward.",
            )
        )
    # A level shift in self-tracked data is easily moved by ordinary life events;
    # flag it so the agent does not narrate the change as evidence of a cause.
    confounds.append(
        ConfoundEntry(
            key=ConfoundKey.LIFE_EVENT_SENSITIVE,
            detail=(
                "A change in level can follow ordinary life events; it is not "
                "evidence that any event produced the change."
            ),
        )
    )

    caveats = (
        "Describes when the series level changed and by how much, based on the "
        "operator's own history. It does not establish what produced the change.",
        "The split is the largest standardized level difference among valid "
        "candidates; it is a descriptive ranking, not a hypothesis test.",
    )

    return AnalyticalResultEnvelope(
        tool_name=CHANGE_POINT_TOOL,
        status=AnalyticalStatus.AVAILABLE,
        inputs=(series.metric_id,),
        parameters={"min_side_observations": min_side_observations},
        estimate=estimate,
        uncertainty=uncertainty,
        validity_status=series.freshness_status or "admissible",
        is_imputed_pct=_round(series.is_imputed_pct),
        sample_size=n,
        confound_checklist=tuple(confounds),
        caveats=caveats,
    ).validate()


# ---------------------------------------------------------------------------
# T014 — smoothed_average (trailing rolling mean)
# ---------------------------------------------------------------------------


@analytical_tool(
    name=SMOOTHED_AVERAGE_TOOL,
    description=(
        "Trailing rolling mean over one admissible ordered series. Each output "
        "point averages only the declared trailing window of prior observations, "
        "and is left blank when the window's non-imputed coverage falls below the "
        "declared minimum, so missing data stays visible. Descriptive only: it "
        "summarizes a recent pattern, it does not predict future values."
    ),
    input_shape="single_ordered_series",
    parameters=("window", "min_coverage"),
    result_kind="smoothed_series",
    confound_keys=(
        ConfoundKey.HIGH_IMPUTATION.value,
        ConfoundKey.LOW_SAMPLE_SIZE.value,
        ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ConfoundKey.PARAMETER_AT_LIMIT.value,
        ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE.value,
    ),
    question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    revision="1",
)
def smoothed_average(
    series: AnalyticalInputSeries,
    *,
    window: int = DEFAULT_SMOOTHING_WINDOW,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> AnalyticalResultEnvelope:
    """Compute a trailing rolling mean over one admissible series (research D3).

    The tool consumes a prepared :class:`AnalyticalInputSeries` and obtains its
    points only through :func:`points_for_computation`, so a refused series can
    never reach computation. When the series is refused, the refusal is surfaced
    as the result envelope.

    Each output point is the mean of the trailing ``window`` observations ending
    at that point (a *trailing*, never centered, mean — it never uses
    observations from after the point it summarizes). A trailing window whose
    non-imputed fraction is below ``min_coverage`` produces a blank value
    (``None``) rather than a filled guess, so long gaps stay visible. The method
    has **no natural confidence interval**, so the result's uncertainty is the
    explicit :meth:`Uncertainty.unavailable` marker, paired with the
    ``method_uncertainty_unavailable`` confound key — never a fabricated band.

    Refuses (no estimate) when ``window`` or ``min_coverage`` is out of bounds,
    or when the series is shorter than one full window.
    """
    if series.refusal is not None:
        return _refusal_envelope(SMOOTHED_AVERAGE_TOOL, series, series.refusal)

    points = points_for_computation(series)
    n = len(points)

    # Out-of-bounds parameter refusals -> no estimate.
    if window < 1 or window > MAX_SMOOTHING_WINDOW:
        return _refusal_envelope(
            SMOOTHED_AVERAGE_TOOL,
            series,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    f"smoothed_average window must be between 1 and "
                    f"{MAX_SMOOTHING_WINDOW}; window={window} is out of bounds."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="window",
            ),
        )
    if not (0.0 < min_coverage <= 1.0):
        return _refusal_envelope(
            SMOOTHED_AVERAGE_TOOL,
            series,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    f"smoothed_average min_coverage must be in (0.0, 1.0]; "
                    f"min_coverage={min_coverage} is out of bounds."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="min_coverage",
            ),
        )
    if n < window:
        return _refusal_envelope(
            SMOOTHED_AVERAGE_TOOL,
            series,
            RefusalOutcome(
                reason="insufficient_data",
                message=(
                    f"smoothed_average needs at least one full window of {window} "
                    f"observations, but only {n} are available for metric "
                    f"'{series.metric_id}'."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="window",
            ),
        )

    values = [p.value for p in points]
    imputed_flags = [p.is_imputed for p in points]

    smoothed: list[dict[str, object]] = []
    emitted = 0
    for i in range(window - 1, n):
        window_slice = values[i - window + 1 : i + 1]
        window_imputed = imputed_flags[i - window + 1 : i + 1]
        non_imputed = sum(1 for flag in window_imputed if not flag)
        coverage = non_imputed / window
        # No long-gap filling: an under-covered window emits a blank value.
        if coverage < min_coverage:
            smoothed.append(
                {
                    "ts": points[i].ts.isoformat(),
                    "value": None,
                    "coverage": _round(coverage),
                    "usable_count": non_imputed,
                    "effective_window": window,
                }
            )
            continue
        emitted += 1
        smoothed.append(
            {
                "ts": points[i].ts.isoformat(),
                "value": _round(_mean(window_slice)),
                "coverage": _round(coverage),
                "usable_count": non_imputed,
                "effective_window": window,
            }
        )

    estimate = {
        "smoothed_points": smoothed,
        "effective_window": window,
        "min_coverage": _round(min_coverage),
        "emitted_points": emitted,
        "blank_points": len(smoothed) - emitted,
        "method_revision": "1",
    }

    # The trailing mean has no natural uncertainty interval (research note D3):
    # be explicit rather than fabricate a band.
    uncertainty = Uncertainty.unavailable()

    confounds: list[ConfoundEntry] = [
        ConfoundEntry(
            key=ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE,
            detail="A trailing rolling mean has no natural uncertainty interval.",
        )
    ]
    if series.is_imputed_pct >= 50.0:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.HIGH_IMPUTATION,
                detail="More than half of the usable series was carried-forward.",
            )
        )
    if window == MAX_SMOOTHING_WINDOW:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.PARAMETER_AT_LIMIT,
                detail="The requested window sits at the largest allowed value.",
            )
        )

    caveats = (
        "Summarizes the recent pattern of the operator's own series using a "
        "trailing average; under-covered windows are left blank so missing data "
        "stays visible.",
        "This is a description of past observations, not a forecast of future values.",
    )

    return AnalyticalResultEnvelope(
        tool_name=SMOOTHED_AVERAGE_TOOL,
        status=AnalyticalStatus.AVAILABLE,
        inputs=(series.metric_id,),
        parameters={"window": window, "min_coverage": _round(min_coverage)},
        estimate=estimate,
        uncertainty=uncertainty,
        validity_status=series.freshness_status or "admissible",
        is_imputed_pct=_round(series.is_imputed_pct),
        sample_size=n,
        confound_checklist=tuple(confounds),
        caveats=caveats,
    ).validate()
