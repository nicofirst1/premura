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
    PairedAnalyticalInput,
    PairedObservation,
    PreRegisteredAssociationHypothesis,
    paired_points_for_computation,
    points_for_computation,
)

__all__ = [
    "CHANGE_POINT_TOOL",
    "SMOOTHED_AVERAGE_TOOL",
    "CORRELATE_TOOL",
    "DEFAULT_MIN_SIDE_OBSERVATIONS",
    "DEFAULT_SMOOTHING_WINDOW",
    "DEFAULT_MIN_COVERAGE",
    "MAX_SMOOTHING_WINDOW",
    "MIN_RAW_PAIRED_SAMPLE",
    "MIN_EFFECTIVE_SAMPLE",
    "MARGINAL_RAW_PAIRED_SAMPLE",
    "MARGINAL_EFFECTIVE_SAMPLE",
    "SHORT_OVERLAP_DAYS",
    "HIGH_IMPUTATION_PCT",
    "change_point",
    "smoothed_average",
    "correlate",
]

# Tool names — the keys under which these register in the shared REGISTRY.
CHANGE_POINT_TOOL = "change_point"
SMOOTHED_AVERAGE_TOOL = "smoothed_average"
CORRELATE_TOOL = "correlate"

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


# ---------------------------------------------------------------------------
# WP03 — correlate (pre-registered, deterministic lagged ASSOCIATION)
# ---------------------------------------------------------------------------
#
# The third built-in analytical tool, and the first over a *paired* input. It
# reports an ASSOCIATION only: Spearman's rho plus an honest association band
# widened for autocorrelation. It NEVER computes or returns a p-value, the word
# "significant"/"significance", causal vocabulary, a diagnosis, or a lag scan —
# per ADR-0008 this is not a display rule, the forbidden quantity is never
# computed at all. The method is deterministic, stateless, and offline (no clock,
# no network, pure stdlib `math`; scipy/numpy are deliberately not used).

# --- Hard floors (research note + data-model; locked by WP01/WP02/WP03) ---
MIN_RAW_PAIRED_SAMPLE = 20
"""Raw paired sample floor. Below 20 paired days the estimate is too unstable to
show a non-expert. WP02 already enforces this when preparing the paired input;
the duplicated constant here lets a directly-built paired input be re-checked."""

MIN_EFFECTIVE_SAMPLE = 12
"""Effective-sample floor. Even with >= 20 raw pairs, heavily autocorrelated
series carry too little independent information; ``N_eff < 12`` is a *refusal*,
not a caveat (research note "Refuse below 20 raw pairs or effective sample 12").
12 also keeps the Fisher-z domain (``N_eff - 3 > 0``) comfortably valid."""

# --- Marginal-support caveat thresholds (research note) ---
MARGINAL_RAW_PAIRED_SAMPLE = 50
"""Raw pairs in ``20..49`` get a ``low_sample_size`` caveat (marginal band)."""

MARGINAL_EFFECTIVE_SAMPLE = 30
"""Effective sample in ``12..29`` also gets ``low_sample_size`` (visible caution
even when the hard floor is met)."""

SHORT_OVERLAP_DAYS = 28
"""Paired calendar overlap under 28 days emits ``short_overlap_window``."""

HIGH_IMPUTATION_PCT = 20.0
"""Imputed-pair share at or above 20% emits ``high_imputation``."""

# --- Effective-sample autocorrelation truncation (locked) ---
_NEFF_MAX_LAG = 7
"""Upper cap on the autocorrelation lag sum. The truncation is
``1..min(7, floor(raw_paired_sample_size / 4))`` so output stays byte-deterministic
(research note "Use effective sample size for the association band")."""

_NEFF_FLOOR_FOR_BAND = 4.0
"""Lowest ``N_eff`` the band math will use. ``N_eff - 3`` must stay positive for
Fisher's z; a hard floor here keeps the band defined even in the refusal path."""

_IMPUTED_PAIR_WEIGHT = 0.5
"""LOCF-imputed pairs (either side imputed) count at half weight toward effective
support, so manufactured agreement cannot inflate independent information
(research note "Count imputed pairs at half weight")."""

_CORRELATE_METHOD_REVISION = "1"

# Parameter names the caller may legitimately pass. ANY other keyword (a
# p-value/significance/lag-scan/tolerance request) is refused BEFORE computation.
_CORRELATE_SUPPORTED_KWARGS: frozenset[str] = frozenset()


def _refusal_envelope_paired(
    refusal: RefusalOutcome,
    *,
    left_metric_id: str,
    right_metric_id: str,
) -> AnalyticalResultEnvelope:
    """Build a validated correlate refusal envelope carrying no estimate."""
    return AnalyticalResultEnvelope(
        tool_name=CORRELATE_TOOL,
        status=AnalyticalStatus.REFUSED,
        inputs=(left_metric_id, right_metric_id),
        refusal=refusal.validate(),
    ).validate()


def _midranks(values: Sequence[float]) -> list[float]:
    """Rank ``values`` ascending with deterministic midrank tie handling.

    Tied values share the average (fractional) of the ranks they span, so the
    rank transform is order-invariant within a tie block and fully deterministic.
    Ranks are 1-based. Example: ``[1, 1, 2]`` -> ``[1.5, 1.5, 3.0]``.
    """
    n = len(values)
    # Sort indices by value; ties broken by original index keeps it deterministic.
    order = sorted(range(n), key=lambda i: (values[i], i))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        # Extend the tie block while the *value* is equal.
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        # Positions i..j (0-based) -> 1-based ranks (i+1)..(j+1); midrank is mean.
        midrank = ((i + 1) + (j + 1)) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = midrank
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation of two equal-length sequences, or ``None`` if either
    side has zero variance (a constant series has no defined correlation)."""
    n = len(xs)
    if n < 2:
        return None
    mx = _mean(xs)
    my = _mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _sample_autocorrelation(values: Sequence[float], lag: int) -> float:
    """Sample autocorrelation of ``values`` at ``lag`` over the rank series.

    Uses the standard biased estimator (divide by the full ``n``), which keeps
    the term bounded and the output deterministic. A non-finite or undefined term
    (e.g. zero variance) is treated as ``0.0`` so the effective-sample sum stays
    deterministic (research note "Treat undefined/noisy autocorrelation terms as
    zero where needed")."""
    n = len(values)
    if lag <= 0 or lag >= n:
        return 0.0
    mean = _mean(values)
    denom = sum((v - mean) ** 2 for v in values)
    if denom <= 0.0:
        return 0.0
    num = sum((values[t] - mean) * (values[t + lag] - mean) for t in range(n - lag))
    rho = num / denom
    if not math.isfinite(rho):
        return 0.0
    return rho


def _effective_sample_size(
    left_ranks: Sequence[float],
    right_ranks: Sequence[float],
    *,
    imputed_flags: Sequence[bool],
    raw_n: int,
) -> float:
    """Effective sample size adjusted for autocorrelation AND imputation.

    Switching to ranks does NOT remove temporal autocorrelation, so the band must
    be widened regardless. Compute

        N_eff = N_weighted / (1 + 2 * sum_k rho_xx(k) * rho_yy(k))

    over the rank-transformed series, with the deterministic lag truncation
    ``k = 1..min(7, floor(raw_n / 4))``. ``N_weighted`` discounts LOCF-imputed
    pairs to half weight so manufactured agreement cannot inflate support. The
    inflation factor is floored at 1.0 (autocorrelation only ever *reduces*
    independent information), and the result is floored at ``_NEFF_FLOOR_FOR_BAND``
    so the Fisher-z band stays defined even on the refusal path.
    """
    weighted_n = sum(
        _IMPUTED_PAIR_WEIGHT if flag else 1.0 for flag in imputed_flags
    )
    max_lag = min(_NEFF_MAX_LAG, raw_n // 4)
    autocov_sum = 0.0
    for lag in range(1, max_lag + 1):
        rho_xx = _sample_autocorrelation(left_ranks, lag)
        rho_yy = _sample_autocorrelation(right_ranks, lag)
        autocov_sum += rho_xx * rho_yy
    inflation = 1.0 + 2.0 * autocov_sum
    # Autocorrelation can only cost independent information; never let a negative
    # autocovariance sum manufacture MORE effective samples than weighted pairs.
    if inflation < 1.0:
        inflation = 1.0
    n_eff = weighted_n / inflation
    if n_eff > weighted_n:
        n_eff = weighted_n
    return max(n_eff, _NEFF_FLOOR_FOR_BAND)


def _association_band(rho: float, n_eff: float) -> tuple[float, float]:
    """An honest association range around ``rho`` via Fisher's z on ``N_eff``.

    NOT a confidence interval and NOT a significance threshold: it is a plausible
    RANGE given the limited *independent* information ``N_eff`` represents. The
    standard error in z-space is ``1 / sqrt(N_eff - 3)`` (a ~1 SE band, not a 95%
    coverage claim); we back-transform to r-space and clamp to ``[-1, 1]``. The
    band widens automatically as ``N_eff`` falls.
    """
    # Clamp rho off the exact unit boundary so atanh stays finite.
    r = max(min(rho, 0.999999), -0.999999)
    z = math.atanh(r)
    denom = max(n_eff - 3.0, 1.0)  # _NEFF_FLOOR_FOR_BAND keeps this >= 1.
    se = 1.0 / math.sqrt(denom)
    lower = math.tanh(z - se)
    upper = math.tanh(z + se)
    return (max(lower, -1.0), min(upper, 1.0))


def _direction_of(rho: float) -> str:
    if rho > 0.0:
        return "positive"
    if rho < 0.0:
        return "negative"
    return "zero"


@analytical_tool(
    name=CORRELATE_TOOL,
    description=(
        "Pre-registered, directional, integer-day lagged ASSOCIATION between two "
        "admissible daily series. Reports Spearman's rho with an honest "
        "association band widened for autocorrelation, the effective sample size, "
        "and whether the observed direction matches the caller's pre-registered "
        "expectation. Association only: it never computes or returns a p-value, a "
        "significance label, causal language, a diagnosis, or a best-fit lag scan."
    ),
    input_shape="paired_ordered_daily_series",
    parameters=("hypothesis",),
    result_kind="correlate_association_estimate",
    confound_keys=(
        ConfoundKey.LOW_SAMPLE_SIZE.value,
        ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ConfoundKey.HIGH_IMPUTATION.value,
        ConfoundKey.TEMPORAL_AUTOCORRELATION.value,
        ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value,
        ConfoundKey.LIFE_EVENT_SENSITIVE.value,
    ),
    question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
    revision=_CORRELATE_METHOD_REVISION,
)
def correlate(
    paired: PairedAnalyticalInput,
    hypothesis: PreRegisteredAssociationHypothesis,
    *args: object,
    **kwargs: object,
) -> AnalyticalResultEnvelope:
    """Report a pre-registered lagged ASSOCIATION over a prepared paired input.

    Consumes a WP02 :class:`PairedAnalyticalInput` (two already-admitted series
    aligned by same local calendar day after one declared integer-day lag) plus
    the pre-registered :class:`PreRegisteredAssociationHypothesis`, and returns an
    available association estimate or a first-class refusal carrying NO estimate.

    Method (all deterministic, offline, stdlib-only):

    * **Spearman's rho** — rank both paired sides with midrank tie handling, then
      Pearson-correlate the ranks. The only shipped coefficient (ADR-0008).
    * **Effective sample size** — ``N_eff = N_weighted / (1 + 2 * sum_k
      rho_xx(k) * rho_yy(k))`` over the rank series, lags
      ``1..min(7, floor(raw_n / 4))``, imputed pairs at half weight. Switching to
      ranks does NOT fix autocorrelation, so the band is widened regardless.
    * **Association band** — Fisher's z on ``N_eff`` (``SE = 1/sqrt(N_eff - 3)``),
      back-transformed and clamped to ``[-1, 1]``. A plausible RANGE, never a
      confidence interval and never a threshold.

    Refuses (no estimate) when: the paired input was already refused; the
    hypothesis does not describe the same metric pair / lag as the input; the raw
    paired sample is below 20; the effective sample is below 12; either rank
    series is constant; or the caller passes ANY unsupported keyword (a p-value,
    significance, tolerance-pairing, or lag-scan request is refused *before*
    computation — the forbidden quantity is never computed).
    """
    left_metric_id = paired.left_metric_id
    right_metric_id = paired.right_metric_id

    # --- Forbidden-request gate: refuse BEFORE any computation. ---------------
    # The supported surface is exactly (paired, hypothesis). Any extra positional
    # or keyword argument is an attempt to request a p-value, significance,
    # tolerance pairing, a lag scan, or best-fit selection — none of which this
    # tool will ever compute (ADR-0008).
    if args or set(kwargs) - _CORRELATE_SUPPORTED_KWARGS:
        offending = sorted(set(kwargs) - _CORRELATE_SUPPORTED_KWARGS)
        if args:
            offending = [f"positional[{i}]" for i in range(len(args))] + offending
        return _refusal_envelope_paired(
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    "correlate reports an association only and accepts no extra "
                    "parameters. It will not select a best lag, pair by a tolerance "
                    "window, or produce a probability/threshold statistic. "
                    f"Unsupported argument(s): {offending}."
                ),
                missing_or_bad_inputs=(left_metric_id, right_metric_id),
                parameter_name=offending[0] if offending else None,
            ),
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )

    # --- Refused paired input short-circuits to a refusal. --------------------
    # paired_points_for_computation raises on a refused input, so a refused paired
    # bundle can never reach the coefficient step even if this branch were missed.
    if paired.refusal is not None:
        return _refusal_envelope_paired(
            paired.refusal,
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )

    # --- Hypothesis must describe the same pair/lag as the prepared input. ----
    try:
        hypothesis.validate()
    except ValueError as exc:
        return _refusal_envelope_paired(
            RefusalOutcome(
                reason="missing_hypothesis",
                message=f"the pre-registered hypothesis is malformed: {exc}",
                missing_or_bad_inputs=(left_metric_id, right_metric_id),
            ),
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )
    if (
        hypothesis.left_metric_id != left_metric_id
        or hypothesis.right_metric_id != right_metric_id
    ):
        return _refusal_envelope_paired(
            RefusalOutcome(
                reason="missing_hypothesis",
                message=(
                    "the pre-registered hypothesis names a different metric pair "
                    f"({hypothesis.left_metric_id!r}/{hypothesis.right_metric_id!r}) "
                    f"than the prepared paired input "
                    f"({left_metric_id!r}/{right_metric_id!r})."
                ),
                missing_or_bad_inputs=(left_metric_id, right_metric_id),
            ),
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )

    pairs: tuple[PairedObservation, ...] = paired_points_for_computation(paired)
    raw_n = len(pairs)

    # --- Raw paired floor (WP02 enforces it; re-check a directly-built input). -
    if raw_n < MIN_RAW_PAIRED_SAMPLE:
        return _refusal_envelope_paired(
            RefusalOutcome(
                reason="insufficient_data",
                message=(
                    f"correlate needs at least {MIN_RAW_PAIRED_SAMPLE} paired days, "
                    f"but only {raw_n} are available for "
                    f"'{left_metric_id}'/'{right_metric_id}'."
                ),
                missing_or_bad_inputs=(left_metric_id, right_metric_id),
            ),
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )

    left_values = [p.left_value for p in pairs]
    right_values = [p.right_value for p in pairs]
    imputed_flags = [p.is_imputed for p in pairs]

    left_ranks = _midranks(left_values)
    right_ranks = _midranks(right_values)

    # --- Spearman's rho = Pearson over midranks. Refuse rank-deficient series. -
    rho = _pearson(left_ranks, right_ranks)
    if rho is None:
        return _refusal_envelope_paired(
            RefusalOutcome(
                reason="insufficient_rank_variation",
                message=(
                    "one of the paired series is constant or has too little rank "
                    "variation to form an association; correlate refuses rather "
                    "than returning a fabricated zero."
                ),
                missing_or_bad_inputs=(left_metric_id, right_metric_id),
            ),
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )

    n_eff = _effective_sample_size(
        left_ranks,
        right_ranks,
        imputed_flags=imputed_flags,
        raw_n=raw_n,
    )

    # --- Effective-sample floor: refuse with no estimate below 12. ------------
    if n_eff < MIN_EFFECTIVE_SAMPLE:
        return _refusal_envelope_paired(
            RefusalOutcome(
                reason="insufficient_effective_sample",
                message=(
                    "the paired series carry too little independent information: "
                    f"the effective sample size is {_round(n_eff, 2)} (floor "
                    f"{MIN_EFFECTIVE_SAMPLE}). correlate refuses rather than report "
                    "a band that would look more informative than the data support."
                ),
                missing_or_bad_inputs=(left_metric_id, right_metric_id),
            ),
            left_metric_id=left_metric_id,
            right_metric_id=right_metric_id,
        )

    band_lower, band_upper = _association_band(rho, n_eff)

    observed_direction = _direction_of(rho)
    expected_direction = hypothesis.expected_direction.value
    direction_matches = observed_direction == expected_direction

    estimate = {
        "coefficient": _round(rho),
        "coefficient_method": "spearman_rho",
        "observed_direction": observed_direction,
        "expected_direction": expected_direction,
        "direction_matches_hypothesis": direction_matches,
        "raw_paired_sample_size": raw_n,
        "effective_sample_size": _round(n_eff, 2),
        "association_band": {
            "lower": _round(band_lower),
            "upper": _round(band_upper),
        },
        "lag_days": hypothesis.lag_days,
        "method_revision": _CORRELATE_METHOD_REVISION,
    }

    # Uncertainty DESCRIBES the association band and how it was widened. It is a
    # plausible range given limited independent information — never a p-value,
    # never a significance claim, and deliberately not named a confidence interval.
    uncertainty = Uncertainty(
        available=True,
        payload={
            "association_band_lower": _round(band_lower),
            "association_band_upper": _round(band_upper),
            "effective_sample_size": _round(n_eff, 2),
            "band_basis": "rank_fisher_transform_on_effective_sample",
        },
    )

    # --- Closed-vocabulary confound checklist (data-model trigger policy). ----
    confounds: list[ConfoundEntry] = []

    overlap_days = 0
    if paired.overlap_start is not None and paired.overlap_end is not None:
        overlap_days = (paired.overlap_end - paired.overlap_start).days + 1

    if (
        MIN_RAW_PAIRED_SAMPLE <= raw_n < MARGINAL_RAW_PAIRED_SAMPLE
        or MIN_EFFECTIVE_SAMPLE <= n_eff < MARGINAL_EFFECTIVE_SAMPLE
    ):
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.LOW_SAMPLE_SIZE,
                detail=(
                    "Paired support is near the minimum, so the association band is "
                    "wide and the estimate should be read as tentative."
                ),
            )
        )
    if overlap_days and overlap_days < SHORT_OVERLAP_DAYS:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.SHORT_OVERLAP_WINDOW,
                detail=(
                    f"The paired days span only {overlap_days} calendar days, a short "
                    "window relative to what a stable association needs."
                ),
            )
        )
    if paired.is_imputed_pct >= HIGH_IMPUTATION_PCT:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.HIGH_IMPUTATION,
                detail=(
                    "A large share of paired days carry a carried-forward value on "
                    "at least one side; those pairs were down-weighted in support."
                ),
            )
        )
    # Switching to ranks does not remove autocorrelation; flag it when the
    # effective sample falls well below the raw paired count.
    if n_eff < raw_n / 2.0:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.TEMPORAL_AUTOCORRELATION,
                detail=(
                    "Nearby days move together, so the paired series carry much less "
                    "independent information than the raw paired-day count implies; "
                    "the association band is widened to reflect that."
                ),
            )
        )
    # The defining correlation confound, emitted ONLY when the caller pre-declared
    # a candidate before computation (open-ended, never an enumerated catalog).
    if hypothesis.common_cause_candidates:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.COMMON_CAUSE_PLAUSIBLE,
                detail=(
                    "The caller flagged a shared upstream factor that could move both "
                    "series, so this association may reflect that shared factor rather "
                    "than a direct link between the two metrics."
                ),
            )
        )
    # Carry a life-event caveat when source/policy metadata marks the metric
    # family as easily shifted by ordinary life events.
    if _paired_life_event_sensitive(paired):
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.LIFE_EVENT_SENSITIVE,
                detail=(
                    "These metrics shift with ordinary life events (travel, illness, "
                    "schedule change), which can move both series together."
                ),
            )
        )

    caveats = (
        "This is an association between the operator's own two series at the "
        "declared lag, read from their history. It is not evidence that one metric "
        "produces the other.",
        "The association band is a plausible range given how much independent "
        "information the paired days carry; it is not a probability statement.",
    )

    return AnalyticalResultEnvelope(
        tool_name=CORRELATE_TOOL,
        status=AnalyticalStatus.AVAILABLE,
        inputs=(left_metric_id, right_metric_id),
        parameters={
            "lag_days": hypothesis.lag_days,
            "expected_direction": expected_direction,
            "coefficient_method": "spearman_rho",
            "method_revision": _CORRELATE_METHOD_REVISION,
            "overlap_start": (
                paired.overlap_start.isoformat() if paired.overlap_start else None
            ),
            "overlap_end": (
                paired.overlap_end.isoformat() if paired.overlap_end else None
            ),
        },
        estimate=estimate,
        uncertainty=uncertainty,
        validity_status=paired.freshness_status or "admissible",
        is_imputed_pct=_round(paired.is_imputed_pct),
        sample_size=raw_n,
        confound_checklist=tuple(confounds),
        caveats=caveats,
    ).validate()


def _paired_life_event_sensitive(paired: PairedAnalyticalInput) -> bool:
    """True when either side's provenance flags life-event sensitivity.

    Reads the WP02 paired ``source_summary`` provenance blocks rather than
    enumerating metric families here (guide, don't enumerate): a per-series
    summary may carry a ``life_event_sensitive`` flag set by the metric-family
    policy upstream. Absent the flag, the confound is not emitted.
    """
    summary = paired.source_summary or {}
    for key in ("left", "right"):
        block = summary.get(key)
        if isinstance(block, dict) and block.get("life_event_sensitive"):
            return True
    # A top-level flag (some preparers summarise it once) is also honoured.
    return bool(summary.get("life_event_sensitive"))
