"""Stage 3 — the ``condition_paired_t_test`` analytical tool (m8 WP2).

``condition_paired_t_test`` reports a **declared condition-label paired
difference** over matched off/on periods from **one** operator's series. It is the
condition-label sibling of :mod:`~premura.engine.paired_t_test` (the simple
anchor-date tool): the engine CONTRACT's deferred-extension rule required
condition-label pairing to ship as a new pairing contract with new trace-identity
fields and new refusal rules, and this is that reviewed addition. The anchor-date
tool is **not** modified.

The caller declares one operator-chosen condition *label* (any non-empty string,
never an enum), a set of non-overlapping on-condition episodes, before/after
window sizes, and an expected direction — all **before** the result exists. The
seam (:func:`~premura.engine.condition_inputs.prepare_condition_label_paired_input`)
turns each usable episode into one off/on pair (off = mean of usable off-window
observations outside every declared episode; on = mean of usable on-window
observations truncated at ``after_days`` and the episode end); this tool computes
the **mean of the per-episode differences** (on − off) and its descriptive
dispersion band. The paired unit is the **episode**.

It is a **registration against the analytical contract**, not a new dispatcher
branch: importing this module runs the
:func:`~premura.engine.analytical_contract.analytical_tool` decorator. It
**consumes the condition seam** and never re-derives pairs: it reads them only
through
:func:`~premura.engine.condition_inputs.condition_episode_pairs_for_computation`,
so a refused paired input can never reach the arithmetic.

Honesty boundary (matching the whole analytical family): the tool keeps the
familiar ``paired_t_test`` shape of name but is **not** a hypothesis test — it
emits **no p-value, no significance verdict**, names **no cause**, and makes no
diagnostic, treatment, dosing, emergency, or population-norm claim. A constant set
of per-episode differences (zero variance) has no honest uncertainty band, so the
tool refuses rather than fabricate a zero-width interval. The label is
operator-declared, not a verified condition, and only splits the windows.

This module imports nothing from MCP and nothing from the warehouse/DuckDB layer;
it makes no network calls, holds no clock, and is fully deterministic.
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
from premura.engine.condition_inputs import (
    ConditionLabelPairedInput,
    condition_episode_pairs_for_computation,
)
from premura.engine.paired_inputs import BeforeAfterDirection

__all__ = [
    "CONDITION_PAIRED_T_TEST_TOOL",
    "condition_paired_t_test",
]

# Tool name — the key under which this registers in the shared REGISTRY.
CONDITION_PAIRED_T_TEST_TOOL = "condition_paired_t_test"

_METHOD_REVISION = "1"

# Usable-episode count at or below which the result carries ``low_sample_size``: a
# per-episode set at (or barely above) the minimum-episode floor rests on little
# support.
_LOW_SAMPLE_FLOOR = 4

# Imputed share (of the per-episode set) at or above which the result carries the
# ``high_imputation`` confound.
_HIGH_IMPUTATION_PCT = 50.0

# Standard-normal multiplier for the descriptive difference interval. A plain ~95%
# dispersion band for agent narration — deliberately NOT a hypothesis-test
# threshold and never a p-value.
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
    paired: ConditionLabelPairedInput,
    refusal: RefusalOutcome,
) -> AnalyticalResultEnvelope:
    """Build a validated refusal envelope carrying no estimate."""
    return AnalyticalResultEnvelope(
        tool_name=CONDITION_PAIRED_T_TEST_TOOL,
        status=AnalyticalStatus.REFUSED,
        inputs=(paired.metric_id,),
        refusal=refusal.validate(),
    ).validate()


@analytical_tool(
    name=CONDITION_PAIRED_T_TEST_TOOL,
    description=(
        "Declared condition-label paired-difference comparison over matched off/on "
        "periods from one operator's admissible series. The caller declares one "
        "operator-chosen condition label, a set of non-overlapping on-condition "
        "episodes, before/after windows, and the expected direction before "
        "computation. Each usable episode contributes one off/on pair (off = mean "
        "of usable off-window observations outside every declared episode; on = "
        "mean of usable on-window observations); the tool reports the mean of the "
        "per-episode differences (on minus off), its dispersion (a descriptive "
        "difference interval), the echoed label, declared/used episode counts, and "
        "per-episode exclusions, plus whether the observed direction matches the "
        "declared expectation. It never scans labels, episode sets, or windows. It "
        "is descriptive only: it emits no p-value or significance verdict and makes "
        "no causal, diagnostic, treatment, or population-norm claim — the label is "
        "operator-declared, not a verified condition, and only splits the windows."
    ),
    input_shape="condition_label_paired_input",
    parameters=("condition_label", "episodes", "before_days", "after_days", "expected_direction"),
    result_kind="condition_paired_difference_estimate",
    confound_keys=(
        ConfoundKey.LOW_SAMPLE_SIZE.value,
        ConfoundKey.HIGH_IMPUTATION.value,
        ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ConfoundKey.PARAMETER_AT_LIMIT.value,
        ConfoundKey.VENDOR_ESTIMATE_INPUT.value,
        ConfoundKey.TEMPORAL_AUTOCORRELATION.value,
        ConfoundKey.LIFE_EVENT_SENSITIVE.value,
    ),
    question_type=AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE,
    revision=_METHOD_REVISION,
)
def condition_paired_t_test(
    paired: ConditionLabelPairedInput,
    *args: object,
    **kwargs: object,
) -> AnalyticalResultEnvelope:
    """Compute a condition-label per-episode paired-difference estimate, or refuse.

    The tool consumes a prepared
    :class:`~premura.engine.condition_inputs.ConditionLabelPairedInput` (the m8
    seam) and obtains its per-episode pairs only through
    :func:`~premura.engine.condition_inputs.condition_episode_pairs_for_computation`,
    so a refused paired input can never reach computation. When the paired input is
    refused, the same refusal is surfaced as the result envelope with no estimate.

    The estimate is the mean of ``on - off`` across the usable episodes, reported
    with the **dispersion** of those per-episode differences — the sample standard
    deviation, the standard error of the mean, and a descriptive ~95% difference
    interval. This is **not** a hypothesis test: it never produces a p-value or a
    significance verdict, and the difference interval is a plain dispersion band.

    The observed direction (``increase`` / ``decrease`` / ``zero``) is compared
    against the caller's declared ``expected_direction`` and reported as plain
    agreement metadata — never as a causal or significance claim.

    The supported surface is exactly ``(paired)``. Any extra positional or keyword
    argument is a request to scan/select a label, episode set, or window (or some
    other unsupported behaviour) and is refused **before** computation.

    Refuses (no estimate) when: the paired input is already refused (inadmissible/
    stale series, too few declared/usable episodes, overlapping episodes, missing
    direction, out-of-bounds window, scan request — all propagated verbatim from
    the seam); the per-episode differences are constant (zero variance), so the
    mean difference has no honest uncertainty band; or the caller passes any
    unsupported argument.
    """
    # --- Forbidden-request gate: refuse BEFORE any computation. ---------------
    if args or kwargs:
        offending = [f"positional[{i}]" for i in range(len(args))] + sorted(kwargs)
        return _refusal_envelope(
            paired,
            RefusalOutcome(
                reason="unsupported_parameter",
                message=(
                    "condition_paired_t_test compares one declared label and episode set "
                    "only and accepts no extra parameters. It will not scan labels, "
                    "episode sets, or windows, select the best episodes, or launder a "
                    f"verdict the data cannot support. Unsupported argument(s): {offending}."
                ),
                missing_or_bad_inputs=(paired.metric_id,),
                parameter_name=offending[0] if offending else None,
            ),
        )

    # --- Refused paired input short-circuits, surfacing the seam's reason. -----
    if paired.refusal is not None:
        return _refusal_envelope(paired, paired.refusal)

    pairs = condition_episode_pairs_for_computation(paired)
    differences = [p.difference for p in pairs]
    n = len(differences)

    # The seam already enforces the minimum-episode floor; a usable input therefore
    # has at least CONDITION_MIN_EPISODES (>= 2) pairs. Guard defensively anyway.
    if n < 2:
        return _refusal_envelope(
            paired,
            RefusalOutcome(
                reason="insufficient_data",
                message=(
                    "condition_paired_t_test needs at least two usable episodes to express "
                    f"the spread of the per-episode difference; only {n} is available for "
                    f"metric '{paired.metric_id}'."
                ),
                missing_or_bad_inputs=(paired.metric_id,),
                parameter_name="episode_count_used",
            ),
        )

    mean_difference = _mean(differences)
    std_difference = _sample_std(differences, mean_difference)

    # --- Constant-difference refusal: no honest uncertainty band. -------------
    if std_difference == 0.0 or not isfinite(std_difference):
        return _refusal_envelope(
            paired,
            RefusalOutcome(
                reason="constant_difference",
                message=(
                    f"All {n} usable per-episode differences for metric "
                    f"'{paired.metric_id}' are identical, so the mean per-episode "
                    "difference has no expressible spread. The tool refuses rather than "
                    "report a fabricated zero-width uncertainty band."
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
        "condition_label": paired.condition_label,
        "episode_count_declared": paired.episode_count_declared,
        "episode_count_used": paired.episode_count_used,
        "per_episode_exclusions": paired.excluded_episodes_as_dicts(),
        "before_days": paired.request.before_days,
        "after_days": paired.request.after_days,
        "method_revision": _METHOD_REVISION,
    }

    # Uncertainty for the mean per-episode difference: dispersion only.
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
        # Observations near each episode boundary are temporally autocorrelated;
        # flag it as a standing limit of this method.
        ConfoundEntry(
            key=ConfoundKey.TEMPORAL_AUTOCORRELATION,
            detail=(
                "Off and on observations sit close in time around each episode, so "
                "successive values are correlated and the spread may understate noise."
            ),
        ),
        # A condition-label split is inherently sensitive to ordinary life events
        # (travel, illness, other changes) coinciding with the declared periods.
        ConfoundEntry(
            key=ConfoundKey.LIFE_EVENT_SENSITIVE,
            detail=(
                "The declared on-label periods may coincide with other life changes, "
                "so an off-vs-on difference is not evidence the label is the reason."
            ),
        ),
    ]
    if n <= _LOW_SAMPLE_FLOOR:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.LOW_SAMPLE_SIZE,
                detail=(
                    "The usable episode count sits at or near the minimum for a "
                    "condition-label comparison, so the difference rests on little support."
                ),
            )
        )
    if paired.is_imputed_pct >= _HIGH_IMPUTATION_PCT:
        confounds.append(
            ConfoundEntry(
                key=ConfoundKey.HIGH_IMPUTATION,
                detail="Half or more of the usable episodes carry a filled-in value.",
            )
        )

    caveats = (
        "Describes the average on-vs-off difference across the operator's own "
        "declared labeled periods; the label is operator-declared, not a verified "
        "condition, and only splits the windows — it is not shown to be the reason.",
        "This reports a difference and its spread, not a verdict — a matching "
        "direction is agreement with the declared expectation, nothing more.",
    )

    return AnalyticalResultEnvelope(
        tool_name=CONDITION_PAIRED_T_TEST_TOOL,
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
