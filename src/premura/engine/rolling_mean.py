"""Stage 3 — the ``rolling_mean`` analytical tool (WP02), behind the WP02 contract.

``rolling_mean`` reports a **declared moving-window summary** over one admitted
ordered series: a trailing window of caller-declared length is slid across the
series, and each emitted point summarises only the observations inside its own
trailing window, carrying that window's coverage and imputation count. It is a
*bounded abstraction* — the rule "summarise metric M with a W-observation
trailing window" applied to any admitted ordered series — not a metric-specific
tool. The metric, the window, and the coverage floor are all caller-declared
before computation; the tool never scans windows to pick the strongest-looking
one (FR-014 / C-004).

It is a **registration against the WP02 contract**, not a new dispatcher branch:
importing this module runs the
:func:`~premura.engine.analytical_contract.analytical_tool` decorator, which adds
the tool to the shared ``REGISTRY``. WP05's default public surface appends this
module to its static built-in list and can then discover/dispatch it through
:func:`~premura.engine.analytical_contract.dispatch` with no per-tool code. This
WP does **not** publish the tool through the default loader or MCP.

Distinct from ``smoothed_average``: that tool answers "what is the current
smoothed level" with one trailing average and the same per-point shape, but its
reviewed question type is ``smoothed_pattern``. ``rolling_mean`` answers "how has
the level *moved* over time" under the reviewed ``moving_window_pattern``
question type (WP01 vocabulary), whose admissibility policy declares its own
moving-window coverage sufficiency. The two are deliberately separate reviewed
question types, not a shared one.

Doctrine the implementation holds to (matching the proof tools):

* **Descriptive honesty.** Results name a moving *level over time*, never a
  *why*, a *forecast*, or a *significance*. No causal, diagnostic, treatment,
  population-norm, prediction, or p-value language appears in any estimate,
  caveat, or message.
* **Determinism.** Given the same prepared series, parameters, and revision, the
  tool returns a byte-identical envelope. No randomness, clock, network, MCP, or
  trace access.
* **Missingness stays visible.** An under-covered trailing window emits a blank
  value rather than a fabricated fill; long gaps surface through per-point
  coverage and imputation counts.
* **Refusal is first-class.** Refused/inadmissible inputs, out-of-bounds
  parameters, a window longer than the span, a coverage floor no window reaches,
  and any window-scan request return a distinct machine-readable
  :class:`~premura.engine.analytical_contract.RefusalOutcome` and no estimate.
"""

from __future__ import annotations

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
    "ROLLING_MEAN_TOOL",
    "DEFAULT_WINDOW",
    "DEFAULT_MAX_WINDOW",
    "DEFAULT_MIN_COVERAGE",
    "MIN_SUPPORTED_WINDOW",
    "rolling_mean",
]

# Tool name — the key under which this registers in the shared REGISTRY.
ROLLING_MEAN_TOOL = "rolling_mean"

_METHOD_REVISION = "1"

# ---------------------------------------------------------------------------
# Parameter bounds (plan defaults; aligned with the shipped smoothed_average
# bounds so the analytical catalog stays internally consistent).
# ---------------------------------------------------------------------------

DEFAULT_WINDOW = 7
"""Default trailing window length (in observations) when the caller declares none."""

DEFAULT_MAX_WINDOW = 365
"""Upper bound on the trailing window. A window larger than this — or larger than
the available admitted span — is out of bounds and refused rather than silently
truncated."""

MIN_SUPPORTED_WINDOW = 2
"""Smallest window that is a *moving-window summary* at all. A window of one is a
passthrough of the raw series (no averaging), so it is refused as unsupported
rather than answered as a degenerate rolling mean."""

DEFAULT_MIN_COVERAGE = 0.5
"""Default minimum fraction of a trailing window that must be non-imputed for an
output point to be emitted. Below this fraction the point is left blank so
missingness stays visible — the method never fills long gaps."""

# Imputed share (of the source series) at or above which the result carries the
# ``high_imputation`` confound. Mirrors the proof-tool threshold convention.
_HIGH_IMPUTATION_PCT = 50.0

# Emitted-support count at or below which the result carries ``low_sample_size``:
# only a handful of usable trailing windows is near the method floor.
_LOW_SUPPORT_FLOOR = 1


def _round(value: float, places: int = 6) -> float:
    """Stable rounding so repeated serialization is byte-identical."""
    return round(value, places)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _refusal_envelope(
    series: AnalyticalInputSeries,
    refusal: RefusalOutcome,
) -> AnalyticalResultEnvelope:
    """Build a validated refusal envelope carrying no estimate."""
    return AnalyticalResultEnvelope(
        tool_name=ROLLING_MEAN_TOOL,
        status=AnalyticalStatus.REFUSED,
        inputs=(series.metric_id,),
        refusal=refusal.validate(),
    ).validate()


@analytical_tool(
    name=ROLLING_MEAN_TOOL,
    description=(
        "Declared moving-window summary over one admissible ordered series. A "
        "trailing window of the caller-declared length is slid across the series; "
        "each emitted point averages only the observations inside its own trailing "
        "window and carries that window's coverage and imputation count, and is "
        "left blank when non-imputed coverage falls below the declared minimum so "
        "missing data stays visible. The caller declares the metric and the window "
        "before computation; the tool never scans windows to pick the strongest. "
        "Descriptive only: it summarizes how a level moved over time, it does not "
        "predict future values."
    ),
    input_shape="single_ordered_series",
    parameters=("window", "min_coverage"),
    result_kind="rolling_mean_estimate",
    confound_keys=(
        ConfoundKey.HIGH_IMPUTATION.value,
        ConfoundKey.LOW_SAMPLE_SIZE.value,
        ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ConfoundKey.PARAMETER_AT_LIMIT.value,
        ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE.value,
    ),
    question_type=AnalyticalQuestionType.MOVING_WINDOW_PATTERN,
    revision=_METHOD_REVISION,
)
def rolling_mean(
    series: AnalyticalInputSeries,
    *args: object,
    window: int = DEFAULT_WINDOW,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    **kwargs: object,
) -> AnalyticalResultEnvelope:
    """Compute a declared moving-window summary over one admissible series.

    The tool consumes a prepared :class:`AnalyticalInputSeries` and obtains its
    points only through :func:`points_for_computation`, so a refused series can
    never reach computation. When the series is refused, the same refusal is
    surfaced as the result envelope.

    Each emitted point is the mean of the trailing ``window`` observations ending
    at that point (a *trailing*, never centered, mean — it never uses
    observations from after the point it summarizes). A trailing window whose
    non-imputed fraction is below ``min_coverage`` produces a blank value
    (``None``) rather than a filled guess, so long gaps stay visible. The method
    has **no natural confidence interval**, so the result's uncertainty is the
    explicit :meth:`Uncertainty.unavailable` marker, paired with the
    ``method_uncertainty_unavailable`` confound key — never a fabricated band.

    The supported surface is exactly ``(series, window=..., min_coverage=...)``.
    Any extra positional or keyword argument is a request to scan/select a window
    (or some other unsupported behaviour) and is refused **before** computation
    (FR-014 / C-004): the caller must submit one declared window, not a request to
    find the best one.

    Refuses (no estimate) when: the input series is refused/inadmissible; ``window``
    is below the supported minimum, zero, negative, or beyond the supported
    maximum; ``window`` is longer than the admitted span; ``min_coverage`` is
    outside ``[0.0, 1.0]``; no trailing window reaches the required coverage; or
    the caller passes any unsupported argument.
    """
    # --- Forbidden-request gate: refuse BEFORE any computation. ---------------
    # The supported surface is exactly (series, window, min_coverage). Any extra
    # positional or keyword argument is an attempt to scan/select a window or
    # otherwise widen the tool past its one declared hypothesis (FR-014 / C-004).
    if args or kwargs:
        offending = [f"positional[{i}]" for i in range(len(args))] + sorted(kwargs)
        return _refusal_envelope(
            series,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    "rolling_mean summarises one declared window only and accepts no "
                    "extra parameters. It will not scan windows or select the "
                    f"strongest-looking one. Unsupported argument(s): {offending}."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name=offending[0] if offending else None,
            ),
        )

    # --- Refused input short-circuits to a refusal. ---------------------------
    # points_for_computation raises on a refused series, so a refused input can
    # never reach the arithmetic even if this branch were missed.
    if series.refusal is not None:
        return _refusal_envelope(series, series.refusal)

    points = points_for_computation(series)
    n = len(points)

    # --- Out-of-bounds window refusals -> no estimate. ------------------------
    if window < MIN_SUPPORTED_WINDOW or window > DEFAULT_MAX_WINDOW:
        return _refusal_envelope(
            series,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    f"rolling_mean window must be between {MIN_SUPPORTED_WINDOW} and "
                    f"{DEFAULT_MAX_WINDOW}; window={window} is out of bounds (a window "
                    "of one is a passthrough, not a moving-window summary)."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="window",
            ),
        )
    if not (0.0 <= min_coverage <= 1.0):
        return _refusal_envelope(
            series,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    f"rolling_mean min_coverage must be in [0.0, 1.0]; "
                    f"min_coverage={min_coverage} is out of bounds."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="min_coverage",
            ),
        )
    if n < window:
        return _refusal_envelope(
            series,
            RefusalOutcome(
                reason="insufficient_data",
                message=(
                    f"rolling_mean needs at least one full window of {window} "
                    f"observations, but only {n} are available for metric "
                    f"'{series.metric_id}'."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="window",
            ),
        )

    values = [p.value for p in points]
    imputed_flags = [p.is_imputed for p in points]

    # --- Slide the trailing window across the series. -------------------------
    emitted_points: list[dict[str, object]] = []
    emitted_count = 0
    for i in range(window - 1, n):
        window_values = values[i - window + 1 : i + 1]
        window_imputed = imputed_flags[i - window + 1 : i + 1]
        imputed_in_window = sum(1 for flag in window_imputed if flag)
        observation_count = window - imputed_in_window
        coverage = observation_count / window
        # No long-gap filling: an under-covered window emits a blank value.
        if coverage < min_coverage:
            emitted_points.append(
                {
                    "ts": points[i].ts.isoformat(),
                    "value": None,
                    "window_observation_count": observation_count,
                    "window_expected_count": window,
                    "coverage": _round(coverage),
                    "imputed_observation_count": imputed_in_window,
                }
            )
            continue
        emitted_count += 1
        emitted_points.append(
            {
                "ts": points[i].ts.isoformat(),
                "value": _round(_mean(window_values)),
                "window_observation_count": observation_count,
                "window_expected_count": window,
                "coverage": _round(coverage),
                "imputed_observation_count": imputed_in_window,
            }
        )

    # --- Coverage refusal: no usable summary point at all -> no estimate. -----
    # The data model requires an available result to carry at least one emitted
    # point; when every trailing window is below the coverage floor we refuse
    # rather than hand back a points list of only blanks.
    if emitted_count == 0:
        return _refusal_envelope(
            series,
            RefusalOutcome(
                reason="insufficient_coverage",
                message=(
                    f"no trailing window of {window} observations reaches the required "
                    f"non-imputed coverage of {_round(min_coverage)} for metric "
                    f"'{series.metric_id}', so no moving-window point can be emitted."
                ),
                missing_or_bad_inputs=(series.metric_id,),
                parameter_name="min_coverage",
            ),
        )

    estimate: dict[str, object] = {
        "points": emitted_points,
        "window": window,
        "min_coverage": _round(min_coverage),
        "emitted_point_count": emitted_count,
        "blank_point_count": len(emitted_points) - emitted_count,
        "input_sample_size": n,
        "method_revision": _METHOD_REVISION,
    }

    # The moving-window mean has no natural uncertainty interval: be explicit
    # rather than fabricate a band.
    uncertainty = Uncertainty.unavailable()

    # --- Closed-vocabulary confound checklist. --------------------------------
    confounds: list[ConfoundEntry] = [
        ConfoundEntry(
            key=ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE,
            detail="A trailing moving-window mean has no natural uncertainty interval.",
        )
    ]
    if emitted_count <= _LOW_SUPPORT_FLOOR:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.LOW_SAMPLE_SIZE,
                detail=(
                    "Only a handful of trailing windows reached the coverage floor, "
                    "so the moving-window summary rests on little usable support."
                ),
            )
        )
    if series.is_imputed_pct >= _HIGH_IMPUTATION_PCT:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.HIGH_IMPUTATION,
                detail="More than half of the usable series was carried-forward.",
            )
        )
    if window == DEFAULT_MAX_WINDOW:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.PARAMETER_AT_LIMIT,
                detail="The requested window sits at the largest allowed value.",
            )
        )

    caveats = (
        "Summarizes how the operator's own series moved over time using a trailing "
        "window; under-covered windows are left blank so missing data stays visible.",
        "This is a description of past observations, not a projection of later values.",
    )

    return AnalyticalResultEnvelope(
        tool_name=ROLLING_MEAN_TOOL,
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
