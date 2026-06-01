"""Stage 3 — the ``paired_t_test`` analytical tool (WP04), behind the WP02 contract.

``paired_t_test`` reports a **simple declared before/after paired-difference**
comparison over matched observations from **one** operator's series, split by one
caller-declared anchor date. It is a *bounded abstraction* — the rule "compare
metric M across declared anchor date D, expecting an increase/decrease" applied
to any admitted series — not a metric-specific or condition-specific tool. The
metric, the anchor date, the before/after windows, and the expected direction are
all caller-declared **before** the result exists (the anti-p-hacking discipline
FR-005 calls out); the tool never scans anchor dates or windows to pick the
strongest-looking split (FR-014 / C-004).

It is a **registration against the WP02 contract**, not a new dispatcher branch:
importing this module runs the
:func:`~premura.engine.analytical_contract.analytical_tool` decorator, which adds
the tool to the shared ``REGISTRY``. WP05's default public surface appends this
module to its static built-in list and can then discover/dispatch it through
:func:`~premura.engine.analytical_contract.dispatch` with no per-tool code. This
WP does **not** publish the tool through the default loader, MCP, or the trace
recorder.

It **consumes the WP03 seam** and never re-derives matched pairs: it takes a
prepared :class:`~premura.engine.paired_inputs.BeforeAfterPairedInput` and reads
its pairs only through
:func:`~premura.engine.paired_inputs.before_after_pairs_for_computation`, so a
refused paired input can never reach the arithmetic. Every upstream refusal
(inadmissible/stale series, missing direction, out-of-bounds window, no valid
pairs, too few pairs, scan request) is surfaced verbatim as a ``paired_t_test``
refusal envelope with a machine-readable reason and **no** estimate.

Honesty boundary (plan C-003 / FR-007): the tool keeps the familiar name
``paired_t_test`` for caller familiarity, but it is **not** a hypothesis test and
it must **never** emit a p-value, a "significant"/"significance" verdict, or any
hypothesis-test-pass language. It reports the *mean paired difference and its
dispersion* (the standard deviation of the differences, the standard error of the
mean difference, and a descriptive difference interval) — never a probability of
the null, never a significance call. It makes no causal, diagnostic, treatment,
dosing, emergency, or population-norm claim. A *constant* set of paired
differences (zero variance) has no honest uncertainty band, so the tool refuses
rather than fabricate a zero-width interval.

Doctrine the implementation holds to (matching the proof tools and
``rolling_mean``):

* **Descriptive honesty.** Results name a before/after *difference* and its
  *spread*, never a *why*, a *significance*, or a *forecast*. Direction agreement
  with the declared expectation is reported as plain metadata, never as a causal
  or significance verdict.
* **Determinism.** Given the same prepared paired input, the tool returns a
  byte-identical envelope. No randomness, clock, network, MCP, or trace access.
* **Missingness stays visible.** The upstream imputation percentage and pair
  count travel with the result; a high-imputation pair set carries the
  ``high_imputation`` confound.
* **Refusal is first-class.** Every weak, malformed, scanning, or
  constant-difference input returns a distinct machine-readable
  :class:`~premura.engine.analytical_contract.RefusalOutcome` and no estimate.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite, sqrt

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
from premura.engine.paired_inputs import (
    BeforeAfterDirection,
    BeforeAfterPairedInput,
    before_after_pairs_for_computation,
)

__all__ = [
    "PAIRED_T_TEST_TOOL",
    "paired_t_test",
]

# Tool name — the key under which this registers in the shared REGISTRY. It is a
# familiar label only; the tool emits a paired-difference estimate, never a
# significance verdict (see the module docstring honesty boundary).
PAIRED_T_TEST_TOOL = "paired_t_test"

_METHOD_REVISION = "1"

# ---------------------------------------------------------------------------
# Confound thresholds (mirror the proof-tool / rolling_mean convention).
# ---------------------------------------------------------------------------

# Imputed share (of the paired set) at or above which the result carries the
# ``high_imputation`` confound.
_HIGH_IMPUTATION_PCT = 50.0

# Pair count at or below which the result carries ``low_sample_size``: a paired
# set at (or barely above) the raw pair floor rests on little support.
_LOW_SAMPLE_FLOOR = 8

# Standard-normal multiplier for the descriptive difference interval. This is a
# plain ~95% dispersion band around the mean difference for agent narration; it
# is deliberately NOT a hypothesis-test threshold and never yields a p-value.
_INTERVAL_Z = 1.959964


def _round(value: float, places: int = 6) -> float:
    """Stable rounding so repeated serialization is byte-identical."""
    return round(value, places)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sample_std(values: Sequence[float], mean: float) -> float:
    """Sample standard deviation (n-1 denominator). Requires len(values) >= 2."""
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return sqrt(var)


def _refusal_envelope(
    paired: BeforeAfterPairedInput,
    refusal: RefusalOutcome,
) -> AnalyticalResultEnvelope:
    """Build a validated refusal envelope carrying no estimate."""
    return AnalyticalResultEnvelope(
        tool_name=PAIRED_T_TEST_TOOL,
        status=AnalyticalStatus.REFUSED,
        inputs=(paired.metric_id,),
        refusal=refusal.validate(),
    ).validate()


@analytical_tool(
    name=PAIRED_T_TEST_TOOL,
    description=(
        "Simple declared before/after paired-difference comparison over matched "
        "observations from one operator's admissible series, split by one "
        "caller-declared anchor date. Reports the pair count, the mean paired "
        "difference (after minus before), and that difference's dispersion "
        "(standard deviation, standard error, and a descriptive difference "
        "interval), plus whether the observed direction matches the declared "
        "expectation. The caller declares the metric, anchor date, before/after "
        "windows, and expected direction before computation; the tool never scans "
        "anchors or windows to pick the strongest split. It is descriptive only: "
        "it does not emit a p-value or a significance verdict, and it makes no "
        "causal, diagnostic, treatment, or population-norm claim."
    ),
    input_shape="before_after_paired_input",
    parameters=("anchor_date", "before_days", "after_days", "expected_direction"),
    result_kind="paired_difference_estimate",
    confound_keys=(
        ConfoundKey.LOW_SAMPLE_SIZE.value,
        ConfoundKey.HIGH_IMPUTATION.value,
        ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ConfoundKey.PARAMETER_AT_LIMIT.value,
        ConfoundKey.VENDOR_ESTIMATE_INPUT.value,
        ConfoundKey.TEMPORAL_AUTOCORRELATION.value,
        ConfoundKey.LIFE_EVENT_SENSITIVE.value,
    ),
    question_type=AnalyticalQuestionType.PAIRED_DIFFERENCE,
    revision=_METHOD_REVISION,
)
def paired_t_test(
    paired: BeforeAfterPairedInput,
    *args: object,
    **kwargs: object,
) -> AnalyticalResultEnvelope:
    """Compute a simple before/after paired-difference estimate, or refuse.

    The tool consumes a prepared
    :class:`~premura.engine.paired_inputs.BeforeAfterPairedInput` (the WP03 seam)
    and obtains its matched pairs only through
    :func:`~premura.engine.paired_inputs.before_after_pairs_for_computation`, so a
    refused paired input can never reach computation. When the paired input is
    refused, the same refusal is surfaced as the result envelope with no estimate.

    The estimate is the mean of ``after - before`` across the matched pairs,
    reported with the **dispersion** of those differences — the sample standard
    deviation, the standard error of the mean (``std / sqrt(n)``), and a
    descriptive ~95% difference interval (``mean +/- z * std_error``). This is
    **not** a hypothesis test: it never produces a p-value or a
    "significant"/"significance" verdict, and the difference interval is a plain
    dispersion band for narration, not a test threshold.

    The observed direction (``increase`` / ``decrease`` / ``zero``) is compared
    against the caller's declared ``expected_direction`` and reported as plain
    agreement metadata — never as a causal or significance claim.

    The supported surface is exactly ``(paired)``. Any extra positional or keyword
    argument is a request to scan/select an anchor or window (or some other
    unsupported behaviour) and is refused **before** computation (FR-014 / C-004).

    Refuses (no estimate) when: the paired input is already refused
    (inadmissible/stale series, missing direction, out-of-bounds window, no valid
    pairs, too few pairs, or a scan request — all propagated verbatim from the
    seam); the matched paired differences are constant (zero variance), so the
    mean difference has no honest uncertainty band; or the caller passes any
    unsupported argument.
    """
    # --- Forbidden-request gate: refuse BEFORE any computation. ---------------
    # The supported surface is exactly (paired). Any extra positional or keyword
    # argument is an attempt to scan/select an anchor or window or otherwise widen
    # the tool past its one declared hypothesis (FR-014 / C-004).
    if args or kwargs:
        offending = [f"positional[{i}]" for i in range(len(args))] + sorted(kwargs)
        return _refusal_envelope(
            paired,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    "paired_t_test compares one declared anchor-date split only and "
                    "accepts no extra parameters. It will not scan anchor dates or "
                    "windows, select the best split, pair by condition label, or "
                    "return a significance verdict. "
                    f"Unsupported argument(s): {offending}."
                ),
                missing_or_bad_inputs=(paired.metric_id,),
                parameter_name=offending[0] if offending else None,
            ),
        )

    # --- Refused paired input short-circuits, surfacing the seam's reason. -----
    # before_after_pairs_for_computation raises on a refused input, so a refused
    # input can never reach the arithmetic even if this branch were missed.
    if paired.refusal is not None:
        return _refusal_envelope(paired, paired.refusal)

    pairs = before_after_pairs_for_computation(paired)
    differences = [p.difference for p in pairs]
    n = len(differences)

    # The seam already enforces the raw pair floor; a usable input therefore has
    # at least BEFORE_AFTER_MIN_PAIRS (>= 2) pairs. Guard defensively anyway so a
    # single pair (no n-1 variance) cannot reach the std computation.
    if n < 2:
        return _refusal_envelope(
            paired,
            RefusalOutcome(
                reason="insufficient_data",
                message=(
                    f"paired_t_test needs at least two matched pairs to express the "
                    f"spread of the paired difference; only {n} is available for "
                    f"metric '{paired.metric_id}'."
                ),
                missing_or_bad_inputs=(paired.metric_id,),
                parameter_name="raw_pair_count",
            ),
        )

    mean_difference = _mean(differences)
    std_difference = _sample_std(differences, mean_difference)

    # --- Constant-difference refusal: no honest uncertainty band. -------------
    # When every matched pair has the same difference the spread is zero, so the
    # mean difference carries no expressible uncertainty. Refuse rather than emit
    # a fabricated zero-width interval (FR-007 / data-model PairedTTestEstimate).
    if std_difference == 0.0 or not isfinite(std_difference):
        return _refusal_envelope(
            paired,
            RefusalOutcome(
                reason="constant_difference",
                message=(
                    f"All {n} matched paired differences for metric "
                    f"'{paired.metric_id}' are identical, so the mean paired "
                    "difference has no expressible spread. The tool refuses rather "
                    "than report a fabricated zero-width uncertainty band."
                ),
                missing_or_bad_inputs=(paired.metric_id,),
                parameter_name="std_difference",
            ),
        )

    std_error = std_difference / sqrt(n)
    interval_low = mean_difference - _INTERVAL_Z * std_error
    interval_high = mean_difference + _INTERVAL_Z * std_error

    # --- Observed direction vs. the declared expectation (metadata only). ------
    if mean_difference > 0:
        observed_direction = "increase"
    elif mean_difference < 0:
        observed_direction = "decrease"
    else:  # pragma: no cover - a non-constant set can still average to exactly 0
        observed_direction = "zero"
    expected = paired.request.expected_direction
    expected_value = expected.value if isinstance(expected, BeforeAfterDirection) else str(expected)
    direction_matches = (
        observed_direction == BeforeAfterDirection.INCREASE.value
        and expected is BeforeAfterDirection.INCREASE
    ) or (
        observed_direction == BeforeAfterDirection.DECREASE.value
        and expected is BeforeAfterDirection.DECREASE
    )

    estimate: dict[str, object] = {
        "mean_difference": _round(mean_difference),
        "observed_direction": observed_direction,
        "expected_direction": expected_value,
        "direction_matches_hypothesis": direction_matches,
        "raw_pair_count": n,
        "before_window_start": (
            paired.before_window_start.isoformat() if paired.before_window_start else None
        ),
        "before_window_end": (
            paired.before_window_end.isoformat() if paired.before_window_end else None
        ),
        "after_window_start": (
            paired.after_window_start.isoformat() if paired.after_window_start else None
        ),
        "after_window_end": (
            paired.after_window_end.isoformat() if paired.after_window_end else None
        ),
        "method_revision": _METHOD_REVISION,
    }

    # Uncertainty for the mean paired difference: dispersion only (sample std, the
    # standard error of the mean, and a descriptive difference interval). NEVER a
    # p-value, a test statistic, or a significance call.
    uncertainty = Uncertainty(
        available=True,
        payload={
            "std_difference": _round(std_difference),
            "std_error": _round(std_error),
            "difference_interval_low": _round(interval_low),
            "difference_interval_high": _round(interval_high),
            "interval_kind": "descriptive_dispersion_band",
        },
    )

    # --- Closed-vocabulary confound checklist. --------------------------------
    confounds: list[ConfoundEntry] = [
        # Before/after observations on near-adjacent days are temporally
        # autocorrelated; flag it as a standing limit of this method so apparent
        # change is not over-read.
        ConfoundEntry(
            key=ConfoundKey.TEMPORAL_AUTOCORRELATION,
            detail=(
                "Before/after observations sit close in time, so successive "
                "values are correlated and the spread may understate true noise."
            ),
        ),
    ]
    if n <= _LOW_SAMPLE_FLOOR:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.LOW_SAMPLE_SIZE,
                detail=(
                    "The matched pair count sits at or near the minimum for a "
                    "paired comparison, so the difference rests on little support."
                ),
            )
        )
    if paired.is_imputed_pct >= _HIGH_IMPUTATION_PCT:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.HIGH_IMPUTATION,
                detail="Half or more of the matched pairs carry a filled-in value.",
            )
        )

    caveats = (
        "Describes the average before/after change in the operator's own metric "
        "around one declared anchor date, with the spread of that change; the "
        "anchor only splits the windows and is not shown to be the reason for it.",
        "This reports a difference and its spread, not a verdict — a matching "
        "direction is agreement with the declared expectation, nothing more.",
    )

    return AnalyticalResultEnvelope(
        tool_name=PAIRED_T_TEST_TOOL,
        status=AnalyticalStatus.AVAILABLE,
        inputs=(paired.metric_id,),
        parameters=paired.request.to_dict(),
        estimate=estimate,
        uncertainty=uncertainty,
        validity_status=paired.freshness_status or "admissible",
        is_imputed_pct=_round(paired.is_imputed_pct),
        sample_size=n,
        confound_checklist=tuple(confounds),
        caveats=caveats,
    ).validate()
