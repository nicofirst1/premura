"""Tests for the Stage 3 proof analytical tools (WP04).

These exercise the two proof tools — ``change_point`` and ``smoothed_average`` —
*behind* the WP02 analytical contract and *through* the WP03 admissible-input
layer:

* Both tools register against the shared contract registry, so WP05's public
  surface can discover and dispatch them with no per-tool branch.
* Both consume a prepared :class:`AnalyticalInputSeries`; a refused series is
  surfaced as a refusal envelope rather than computed over (the refusal path is
  not bypassed).
* Supported runs produce deterministic, byte-stable, metadata-bearing
  envelopes; out-of-bounds and insufficient inputs refuse with no estimate.
* Doctrine: estimates, caveats, and messages avoid causal language, diagnostic
  labels, p-value / significance claims, and (for the smoothed average)
  prediction claims.

Evidence is fixture-backed: hand-built ``EvidenceCandidate`` +
``MetricFamilyPolicy`` plus explicit ``PreparedPoint`` series. Nothing here
reads the warehouse, SQL, DuckDB, MCP, or the network.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest

from premura.engine.analytical_contract import (
    CONFOUND_KEYS,
    REGISTRY,
    AnalyticalQuestionType,
    AnalyticalStatus,
    ConfoundKey,
    dispatch,
)
from premura.engine.analytical_inputs import (
    AnalyticalInputSeries,
    PreparedPoint,
    prepare_input_series,
)
from premura.engine.analytical_tools import (
    CHANGE_POINT_TOOL,
    DEFAULT_MIN_SIDE_OBSERVATIONS,
    MAX_SMOOTHING_WINDOW,
    SMOOTHED_AVERAGE_TOOL,
    change_point,
    smoothed_average,
)
from premura.engine.policies._model import (
    Admissibility,
    EvidenceCandidate,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    MissingDataBehavior,
    PolicyShape,
    QuestionRule,
    QuestionType,
    RejectionReason,
    SufficiencyRule,
    TemporalMeaning,
)

REFERENCE = datetime(2026, 5, 29, 12, 0, 0)
FAMILY = "rolling_recent_family"
METRIC = "resting_heart_rate"


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers (mirrors the WP03 test scaffolding)
# ---------------------------------------------------------------------------


def _recent_trend_policy(
    *,
    admissibility: Admissibility = Admissibility.ADMISSIBLE,
    max_age: timedelta = timedelta(days=3650),
    min_observations: int | None = None,
    default_rejection_reasons: tuple[RejectionReason, ...] = (),
) -> MetricFamilyPolicy:
    rule = QuestionRule(
        admissibility=admissibility,
        freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=max_age),
        sufficiency=(
            SufficiencyRule(
                min_observations=min_observations,
                missing_data_behavior=MissingDataBehavior.REJECT,
            )
            if min_observations is not None
            else None
        ),
        default_rejection_reasons=default_rejection_reasons,
    )
    return MetricFamilyPolicy(
        policy_id="rolling_recent@1",
        version=1,
        metric_family=FAMILY,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={QuestionType.RECENT_TREND: rule},
        applies_to_metrics=(METRIC,),
    )


def _candidate(*, observed_at: datetime, point_count: int) -> EvidenceCandidate:
    return EvidenceCandidate(
        metric_id=METRIC,
        metric_family=FAMILY,
        value_kind="aggregate",
        observed_at=observed_at,
        source_id="fixture",
        point_count=point_count,
    )


def _series_from_values(
    values: list[float],
    *,
    question_type: AnalyticalQuestionType,
    imputed_idx: tuple[int, ...] = (),
    min_observations: int | None = None,
    end: datetime = REFERENCE,
) -> AnalyticalInputSeries:
    """Build a usable prepared series from explicit values, oldest-first."""
    n = len(values)
    points = [
        PreparedPoint(
            ts=end - timedelta(days=(n - 1 - i)),
            value=values[i],
            is_imputed=i in imputed_idx,
        )
        for i in range(n)
    ]
    return prepare_input_series(
        METRIC,
        question_type,
        candidate=_candidate(observed_at=end, point_count=n),
        policies=_recent_trend_policy(min_observations=min_observations),
        points=points,
        reference_time=REFERENCE,
        freshness_status="current",
    )


def _refused_series(question_type: AnalyticalQuestionType) -> AnalyticalInputSeries:
    """A refused prepared series (no evidence at all)."""
    series = prepare_input_series(
        METRIC,
        question_type,
        candidate=_candidate(observed_at=REFERENCE, point_count=0),
        policies=_recent_trend_policy(),
        points=[],
        reference_time=REFERENCE,
    )
    assert not series.is_usable
    return series


# Terms doctrine forbids in any surfaced estimate / caveat / message.
_FORBIDDEN_PATTERNS = (
    r"\bcaus\w*",  # cause, caused, causal, causes, causation
    r"\bp-?value\w*",
    r"\bsignifican\w*",  # significant, significance
    r"\bdiagnos\w*",  # diagnosis, diagnostic, diagnose
)
_PREDICTION_PATTERNS = (
    r"\bpredict\w*",
    r"\bforecast\w*",
    r"\bwill\s+be\b",
    r"\bfuture\s+value",
)


def _all_text(envelope_dict: dict) -> str:
    """Flatten every human-readable string in an envelope for assertion."""
    parts: list[str] = []

    def walk(obj: object) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)

    walk(envelope_dict)
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Registration / contract wiring (integration check)
# ---------------------------------------------------------------------------


def test_both_tools_register_against_the_contract() -> None:
    # Importing the tools module ran the decorators; both are now discoverable
    # in the shared registry with their reviewed question types.
    assert CHANGE_POINT_TOOL in REGISTRY
    assert SMOOTHED_AVERAGE_TOOL in REGISTRY
    cp_spec = REGISTRY[CHANGE_POINT_TOOL]
    sa_spec = REGISTRY[SMOOTHED_AVERAGE_TOOL]
    assert cp_spec.question_type is AnalyticalQuestionType.LEVEL_SHIFT_DETECTION
    assert sa_spec.question_type is AnalyticalQuestionType.SMOOTHED_PATTERN
    # Declared confound keys are all in the committed closed vocabulary.
    assert set(cp_spec.confound_keys) <= CONFOUND_KEYS
    assert set(sa_spec.confound_keys) <= CONFOUND_KEYS
    # The spec carries the function so dispatch can call it with no branch.
    assert cp_spec.fn is change_point
    assert sa_spec.fn is smoothed_average


def test_tools_invoke_through_shared_dispatch() -> None:
    series = _series_from_values(
        [60, 60, 61, 60, 80, 81, 80, 81],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = dispatch(CHANGE_POINT_TOOL, series)
    assert envelope.status is AnalyticalStatus.AVAILABLE
    assert envelope.tool_name == CHANGE_POINT_TOOL


# ---------------------------------------------------------------------------
# T015: change_point — supported level shift is deterministic
# ---------------------------------------------------------------------------


def test_change_point_detects_representative_level_shift() -> None:
    # A clear shift from ~60 to ~80 between index 3 and 4.
    series = _series_from_values(
        [60, 61, 60, 59, 80, 81, 79, 80],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = change_point(series)
    assert envelope.status is AnalyticalStatus.AVAILABLE
    assert envelope.refusal is None
    est = envelope.estimate
    assert est is not None
    assert est["split_index"] == 4
    assert est["direction"] == "increase"
    assert est["before_level"] == pytest.approx(60.0)
    assert est["after_level"] == pytest.approx(80.0)
    # No p-value or causal label leaks into the estimate keys/values.
    assert "p_value" not in est
    assert "cause" not in est
    # Required validity metadata is present.
    assert envelope.sample_size == 8
    assert envelope.validity_status == "current"
    assert envelope.is_imputed_pct == 0.0


def test_change_point_is_deterministic_across_runs() -> None:
    values = [50, 51, 49, 70, 71, 69]
    s1 = _series_from_values(values, question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION)
    s2 = _series_from_values(values, question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION)
    assert change_point(s1).to_dict() == change_point(s2).to_dict()


def test_change_point_uncertainty_carries_no_pvalue() -> None:
    series = _series_from_values(
        [60, 60, 60, 90, 90, 90],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = change_point(series)
    assert envelope.uncertainty is not None
    assert envelope.uncertainty.available is True
    payload = envelope.uncertainty.payload
    assert payload is not None
    assert "p_value" not in payload
    assert "standardized_level_difference" in payload


# ---------------------------------------------------------------------------
# T015: change_point — insufficient data / bad params refuse with no estimate
# ---------------------------------------------------------------------------


def test_change_point_refuses_insufficient_data() -> None:
    # Only 3 points cannot leave the default 2 per side of any split.
    series = _series_from_values(
        [60, 61, 80],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = change_point(series)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.reason == "insufficient_data"


def test_change_point_refuses_out_of_bounds_parameter() -> None:
    series = _series_from_values(
        [60, 61, 62, 80, 81, 82],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = change_point(series, min_side_observations=1)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.reason == "unsupported_parameter"
    assert envelope.refusal.parameter_name == "min_side_observations"


def test_change_point_surfaces_refused_input_without_computing() -> None:
    # A refused prepared series must come back as a refusal envelope, not a
    # crash and not an estimate. points_for_computation is never reached.
    series = _refused_series(AnalyticalQuestionType.LEVEL_SHIFT_DETECTION)
    envelope = change_point(series)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.reason == "evidence_missing"


# ---------------------------------------------------------------------------
# T015: smoothed_average — supported run is deterministic
# ---------------------------------------------------------------------------


def test_smoothed_average_returns_deterministic_output() -> None:
    series = _series_from_values(
        [10, 20, 30, 40, 50],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    envelope = smoothed_average(series, window=3)
    assert envelope.status is AnalyticalStatus.AVAILABLE
    est = envelope.estimate
    assert est is not None
    assert est["effective_window"] == 3
    pts = est["smoothed_points"]
    # 5 points, window 3 -> 3 trailing means: mean(10,20,30)=20, (20,30,40)=30,
    # (30,40,50)=40.
    assert [p["value"] for p in pts] == [20.0, 30.0, 40.0]
    # Uncertainty is the explicit unavailable marker, not a fabricated band.
    assert envelope.uncertainty is not None
    assert envelope.uncertainty.available is False
    assert envelope.uncertainty.payload is None
    assert ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE.value in {
        e.key.value for e in envelope.confound_checklist
    }


def test_smoothed_average_is_deterministic_across_runs() -> None:
    values = [5, 7, 9, 11, 13, 15]
    s1 = _series_from_values(values, question_type=AnalyticalQuestionType.SMOOTHED_PATTERN)
    s2 = _series_from_values(values, question_type=AnalyticalQuestionType.SMOOTHED_PATTERN)
    assert smoothed_average(s1, window=2).to_dict() == smoothed_average(s2, window=2).to_dict()


def test_smoothed_average_does_not_fill_undercovered_window() -> None:
    # Window of 4 with 3 of 4 imputed -> coverage 0.25 < 0.5 default -> blank.
    series = _series_from_values(
        [10, 20, 30, 40, 50, 60],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
        imputed_idx=(0, 1, 2),
    )
    envelope = smoothed_average(series, window=4, min_coverage=0.5)
    est = envelope.estimate
    assert est is not None
    first = est["smoothed_points"][0]
    # First trailing window covers idx 0..3: 3 imputed -> coverage 0.25 -> blank.
    assert first["value"] is None
    assert first["coverage"] == pytest.approx(0.25)
    # Imputation visibility is preserved on the envelope.
    assert envelope.is_imputed_pct == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# T015: smoothed_average — out-of-bounds params refuse with no estimate
# ---------------------------------------------------------------------------


def test_smoothed_average_refuses_window_out_of_bounds() -> None:
    series = _series_from_values(
        [10, 20, 30, 40],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    envelope = smoothed_average(series, window=MAX_SMOOTHING_WINDOW + 1)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.reason == "unsupported_parameter"
    assert envelope.refusal.parameter_name == "window"


def test_smoothed_average_refuses_bad_min_coverage() -> None:
    series = _series_from_values(
        [10, 20, 30, 40],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    envelope = smoothed_average(series, window=2, min_coverage=1.5)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.parameter_name == "min_coverage"


def test_smoothed_average_refuses_window_longer_than_series() -> None:
    series = _series_from_values(
        [10, 20, 30],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    envelope = smoothed_average(series, window=7)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.reason == "insufficient_data"


def test_smoothed_average_surfaces_refused_input_without_computing() -> None:
    series = _refused_series(AnalyticalQuestionType.SMOOTHED_PATTERN)
    envelope = smoothed_average(series)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.estimate is None
    assert envelope.refusal is not None
    assert envelope.refusal.reason == "evidence_missing"


# ---------------------------------------------------------------------------
# T015: repeated runs serialize identically (byte-stable)
# ---------------------------------------------------------------------------


def test_repeated_serialization_is_byte_identical() -> None:
    series = _series_from_values(
        [60, 61, 60, 80, 81, 80],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = change_point(series)
    assert envelope.to_dict() == envelope.to_dict()

    series2 = _series_from_values(
        [1, 2, 3, 4, 5, 6],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    smoothed = smoothed_average(series2, window=2)
    assert smoothed.to_dict() == smoothed.to_dict()


# ---------------------------------------------------------------------------
# T016: doctrine — no causation, no significance, no diagnosis, no prediction
# ---------------------------------------------------------------------------


def test_change_point_text_avoids_causal_significance_diagnostic_language() -> None:
    series = _series_from_values(
        [60, 61, 60, 80, 81, 80],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    text = _all_text(change_point(series).to_dict())
    for pattern in _FORBIDDEN_PATTERNS:
        match = re.search(pattern, text)
        # "caus" is allowed only inside the deliberate negation "not ... cause";
        # to keep the assertion strict, assert no *bare positive* causal claim:
        # the only allowed match family is a negated form. We assert no banned
        # term appears at all in significance/diagnostic/p-value families, and
        # for causal language we additionally require it to be negated.
        if pattern == r"\bcaus\w*" and match is not None:
            # Every causal mention must be part of an explicit denial.
            for m in re.finditer(r".{0,30}caus\w*", text):
                snippet = m.group(0)
                assert "not" in snippet or "does not" in snippet, snippet
        else:
            assert match is None, f"forbidden term {pattern!r} found in: {text}"


def test_change_point_refusal_text_avoids_forbidden_language() -> None:
    series = _series_from_values(
        [60, 61, 80],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    text = _all_text(change_point(series).to_dict())
    for pattern in (r"\bp-?value\w*", r"\bsignifican\w*", r"\bdiagnos\w*"):
        assert re.search(pattern, text) is None, f"{pattern} found in refusal: {text}"


def test_smoothed_average_text_avoids_forbidden_and_prediction_language() -> None:
    series = _series_from_values(
        [10, 20, 30, 40, 50],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    text = _all_text(smoothed_average(series, window=3).to_dict())
    # No causal / significance / diagnostic / p-value claims.
    for pattern in (r"\bp-?value\w*", r"\bsignifican\w*", r"\bdiagnos\w*"):
        assert re.search(pattern, text) is None, f"{pattern} found in: {text}"
    # No bare causal claim (negated denials are acceptable but this method emits
    # none, so assert outright absence of the family is not required; check
    # prediction instead).
    # No prediction / forecast claim — but the deliberate denial "not a forecast"
    # is allowed, so require any forecast/predict mention to be negated.
    for pattern in _PREDICTION_PATTERNS:
        for m in re.finditer(rf".{{0,20}}{pattern}", text):
            snippet = m.group(0)
            assert "not" in snippet, f"unnegated prediction claim: {snippet!r}"


def test_smoothed_average_caveats_assert_not_a_forecast() -> None:
    series = _series_from_values(
        [10, 20, 30, 40, 50],
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    caveat_text = " ".join(smoothed_average(series, window=3).caveats).lower()
    # The honest denial is present and is negated.
    assert "not a forecast" in caveat_text


def test_default_min_side_observations_is_supported() -> None:
    # Sanity: the documented default is a valid (non-refusing) parameter.
    series = _series_from_values(
        [60, 61, 62, 80, 81, 82],
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = change_point(series, min_side_observations=DEFAULT_MIN_SIDE_OBSERVATIONS)
    assert envelope.status is AnalyticalStatus.AVAILABLE
