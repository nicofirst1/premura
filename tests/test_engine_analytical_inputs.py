"""Tests for the Stage 3 analytical *input preparation* layer (WP03).

These exercise the engine-owned seam between the Stage 2 admissibility
evaluator and the future proof tools: usable evidence becomes an ordered,
overlap-annotated input series; missing / stale / inadmissible / insufficient /
out-of-bounds evidence is refused *before* any computation, with distinct
machine-readable reasons reused from the WP02 contract's ``RefusalOutcome``.

The evidence here is fixture-backed (hand-built ``EvidenceCandidate`` +
``MetricFamilyPolicy`` declarations and explicit ``PreparedPoint`` series); the
layer reads no warehouse, so nothing here touches SQL, DuckDB, MCP, or the
network. Everything is imported through the modules' public surfaces.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from premura.engine.analytical_contract import AnalyticalQuestionType, RefusalOutcome
from premura.engine.analytical_inputs import (
    ANALYTICAL_TO_POLICY_QUESTION,
    AnalyticalInputSeries,
    InputRefusalReason,
    PreparedPoint,
    points_for_computation,
    prepare_input_series,
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
# Fixture-backed evidence helpers
# ---------------------------------------------------------------------------


def _recent_trend_policy(
    *,
    admissibility: Admissibility = Admissibility.ADMISSIBLE,
    max_age: timedelta = timedelta(days=30),
    min_observations: int | None = None,
    default_rejection_reasons: tuple[RejectionReason, ...] = (),
) -> MetricFamilyPolicy:
    """A family policy that declares the analytical question types for the tests.

    The analytical questions are first-class :class:`QuestionType` values (research
    note D4), so this fixture registers the rule under the analytical question
    types the proof tools actually request — not under ``recent_trend``.
    """
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
        question_rules={
            QuestionType.RECENT_TREND: rule,
            QuestionType.LEVEL_SHIFT_DETECTION: rule,
            QuestionType.SMOOTHED_PATTERN: rule,
        },
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


def _points(
    n: int, *, end: datetime = REFERENCE, imputed_idx: tuple[int, ...] = ()
) -> list[PreparedPoint]:
    """``n`` daily points ending at ``end``, oldest-first, some optionally imputed."""
    out: list[PreparedPoint] = []
    for i in range(n):
        ts = end - timedelta(days=(n - 1 - i))
        out.append(PreparedPoint(ts=ts, value=60.0 + i, is_imputed=i in imputed_idx))
    return out


# ---------------------------------------------------------------------------
# T012: ordered series preparation for usable evidence
# ---------------------------------------------------------------------------


def test_prepares_ordered_series_for_usable_evidence() -> None:
    pts = _points(10)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=_recent_trend_policy(),
        points=pts,
        reference_time=REFERENCE,
    )

    assert series.is_usable
    assert series.refusal is None
    assert series.sample_size == 10
    # Points come back ordered by timestamp.
    timestamps = [p.ts for p in series.points]
    assert timestamps == sorted(timestamps)
    # Provenance from the evaluator is preserved on the source summary.
    assert series.source_summary["policy_id"] == "rolling_recent@1"
    assert series.source_summary["metric_family"] == FAMILY


def test_unordered_input_is_sorted_before_preparation() -> None:
    pts = _points(5)
    shuffled = [pts[2], pts[0], pts[4], pts[1], pts[3]]
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.SMOOTHED_PATTERN,
        candidate=_candidate(observed_at=REFERENCE, point_count=5),
        policies=_recent_trend_policy(),
        points=shuffled,
        reference_time=REFERENCE,
    )
    assert series.is_usable
    assert [p.ts for p in series.points] == [p.ts for p in pts]


def test_imputation_percentage_reflects_imputed_points() -> None:
    pts = _points(10, imputed_idx=(0, 1))  # 2 of 10 imputed
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.SMOOTHED_PATTERN,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=_recent_trend_policy(),
        points=pts,
        reference_time=REFERENCE,
    )
    assert series.is_usable
    assert series.is_imputed_pct == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# T012: overlap metadata for a single-series request
# ---------------------------------------------------------------------------


def test_single_series_overlap_equals_usable_window() -> None:
    pts = _points(7)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=7),
        policies=_recent_trend_policy(),
        points=pts,
        reference_time=REFERENCE,
    )
    assert series.is_usable
    # Overlap window equals the usable analysis window for a single series, but
    # the fields are explicit (present, not None) so multi-input tools inherit
    # the same contract.
    assert series.overlap_start == series.window_start
    assert series.overlap_end == series.window_end
    assert series.overlap_start is not None
    assert series.overlap_end is not None
    assert series.overlap_sample_size == series.sample_size == 7


# ---------------------------------------------------------------------------
# T012: every distinct pre-computation refusal reason, one case each
# ---------------------------------------------------------------------------


def _stale_series() -> AnalyticalInputSeries:
    # Observed 90 days ago, but the policy window is 30 days -> stale.
    stale_at = REFERENCE - timedelta(days=90)
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=stale_at, point_count=10),
        policies=_recent_trend_policy(max_age=timedelta(days=30)),
        points=_points(10, end=stale_at),
        reference_time=REFERENCE,
    )


def _insufficient_series() -> AnalyticalInputSeries:
    # Policy needs >= 8 observations; candidate has 3.
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=3),
        policies=_recent_trend_policy(min_observations=8),
        points=_points(3),
        reference_time=REFERENCE,
    )


def _unsupported_parameter_series() -> AnalyticalInputSeries:
    # Evidence is admissible, but the analytical parameter bound (min 12 points)
    # is not met -> unsupported_parameter, refused before computation.
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.SMOOTHED_PATTERN,
        candidate=_candidate(observed_at=REFERENCE, point_count=6),
        policies=_recent_trend_policy(),
        points=_points(6),
        reference_time=REFERENCE,
        min_observations=12,
    )


def _inadmissible_series() -> AnalyticalInputSeries:
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=_recent_trend_policy(
            admissibility=Admissibility.INADMISSIBLE,
            default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
        ),
        points=_points(10),
        reference_time=REFERENCE,
    )


def _missing_evidence_series() -> AnalyticalInputSeries:
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=0),
        policies=_recent_trend_policy(),
        points=[],
        reference_time=REFERENCE,
    )


def _unsupported_question_series() -> AnalyticalInputSeries:
    # The policy is declared for a different family, so the evaluator finds no
    # rule for the candidate's family -> unsupported_policy -> unsupported_question.
    other_policy = MetricFamilyPolicy(
        policy_id="other@1",
        version=1,
        metric_family="some_other_family",
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.RECENT_TREND: QuestionRule(admissibility=Admissibility.ADMISSIBLE)
        },
    )
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=other_policy,
        points=_points(10),
        reference_time=REFERENCE,
    )


@pytest.mark.parametrize(
    ("build_series", "expected_reason", "expected_parameter_name"),
    [
        (_stale_series, InputRefusalReason.STALE_FOR_QUESTION, None),
        (_insufficient_series, InputRefusalReason.INSUFFICIENT_DATA, None),
        (
            _unsupported_parameter_series,
            InputRefusalReason.UNSUPPORTED_PARAMETER,
            "min_observations",
        ),
        (_inadmissible_series, InputRefusalReason.INADMISSIBLE_FOR_QUESTION, None),
        (_missing_evidence_series, InputRefusalReason.EVIDENCE_MISSING, None),
        (_unsupported_question_series, InputRefusalReason.UNSUPPORTED_QUESTION, None),
    ],
)
def test_input_refused_before_computation_with_distinct_reason(
    build_series, expected_reason: InputRefusalReason, expected_parameter_name: str | None
) -> None:
    # Each distinct pre-computation refusal reason: refuses, carries the
    # machine-readable reason, and hands back no points to compute over.
    series = build_series()
    assert not series.is_usable
    assert series.refusal is not None
    assert series.refusal.reason == expected_reason.value
    assert series.points == ()
    if expected_parameter_name is not None:
        assert series.refusal.parameter_name == expected_parameter_name


def test_recent_trend_rule_does_not_serve_analytical_questions() -> None:
    # Behavioral lock for the DRIFT-1 fix: a SAME-family policy that declares
    # only a recent_trend rule must REFUSE an analytical question. This proves
    # the analytical questions are no longer collapsed onto recent_trend — if a
    # future edit re-pointed ANALYTICAL_TO_POLICY_QUESTION back at RECENT_TREND,
    # this admissible-looking evidence would wrongly become usable and the test
    # would fail. (Distinct from the different-family case above.)
    recent_trend_only = MetricFamilyPolicy(
        policy_id="recent_trend_only@1",
        version=1,
        metric_family=FAMILY,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.RECENT_TREND: QuestionRule(admissibility=Admissibility.ADMISSIBLE)
        },
        applies_to_metrics=(METRIC,),
    )
    for analytical in (
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        AnalyticalQuestionType.SMOOTHED_PATTERN,
    ):
        series = prepare_input_series(
            METRIC,
            analytical,
            candidate=_candidate(observed_at=REFERENCE, point_count=10),
            policies=recent_trend_only,
            points=_points(10),
            reference_time=REFERENCE,
        )
        assert not series.is_usable, analytical
        assert series.refusal is not None
        assert series.refusal.reason == InputRefusalReason.UNSUPPORTED_QUESTION.value


# ---------------------------------------------------------------------------
# T012: no computation for refused input (observable via public behavior)
# ---------------------------------------------------------------------------


def test_points_for_computation_returns_points_for_usable_series() -> None:
    pts = _points(10)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=_recent_trend_policy(),
        points=pts,
        reference_time=REFERENCE,
    )
    computation_points = points_for_computation(series)
    assert len(computation_points) == 10
    assert computation_points == series.points


def test_points_for_computation_refuses_to_hand_back_refused_input() -> None:
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=0),
        policies=_recent_trend_policy(),
        points=[],
        reference_time=REFERENCE,
    )
    # The seam structurally blocks computation over a refused input: a tool that
    # forgot to branch on the refusal still cannot get points.
    with pytest.raises(RuntimeError, match="must not be passed to computation"):
        points_for_computation(series)


# ---------------------------------------------------------------------------
# Contract-shape and wiring guarantees
# ---------------------------------------------------------------------------


def test_analytical_questions_map_to_their_own_first_class_question_type() -> None:
    # Research note D4: each analytical question is a first-class QuestionType
    # gated on its OWN rule, never collapsed onto a descriptive shape like
    # recent_trend. The map is closed (exactly the AnalyticalQuestionType set)
    # and is an identity-by-name onto the policy QuestionType vocabulary.
    assert set(ANALYTICAL_TO_POLICY_QUESTION) == set(AnalyticalQuestionType)
    assert all(isinstance(v, QuestionType) for v in ANALYTICAL_TO_POLICY_QUESTION.values())
    assert ANALYTICAL_TO_POLICY_QUESTION == {
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION: QuestionType.LEVEL_SHIFT_DETECTION,
        AnalyticalQuestionType.SMOOTHED_PATTERN: QuestionType.SMOOTHED_PATTERN,
        AnalyticalQuestionType.LAGGED_ASSOCIATION: QuestionType.LAGGED_ASSOCIATION,
        AnalyticalQuestionType.MOVING_WINDOW_PATTERN: QuestionType.MOVING_WINDOW_PATTERN,
        AnalyticalQuestionType.PAIRED_DIFFERENCE: QuestionType.PAIRED_DIFFERENCE,
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE: (
            QuestionType.CONDITION_PAIRED_DIFFERENCE
        ),
    }
    # No analytical question is routed onto a descriptive question shape.
    descriptive = {
        QuestionType.CURRENT_STATUS,
        QuestionType.RECENT_TREND,
        QuestionType.LONG_TERM_CONTROL,
        QuestionType.HISTORICAL_BASELINE,
    }
    assert not (set(ANALYTICAL_TO_POLICY_QUESTION.values()) & descriptive)
    # Each analytical question type shares the string value of its policy twin.
    for analytical, policy in ANALYTICAL_TO_POLICY_QUESTION.items():
        assert analytical.value == policy.value


def test_refused_series_rejects_carrying_points() -> None:
    refusal = RefusalOutcome(reason="evidence_missing", message="nope")
    with pytest.raises(ValueError, match="must not carry computation points"):
        AnalyticalInputSeries(
            metric_id=METRIC,
            question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
            points=(PreparedPoint(ts=REFERENCE, value=1.0),),
            refusal=refusal,
        )


def test_unordered_points_rejected_at_construction() -> None:
    later = REFERENCE
    earlier = REFERENCE - timedelta(days=1)
    with pytest.raises(ValueError, match="ordered by timestamp"):
        AnalyticalInputSeries(
            metric_id=METRIC,
            question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
            points=(PreparedPoint(ts=later, value=1.0), PreparedPoint(ts=earlier, value=2.0)),
            sample_size=2,
            overlap_sample_size=2,
            window_start=earlier,
            window_end=later,
            overlap_start=earlier,
            overlap_end=later,
        )


def test_usable_series_requires_window_and_overlap_metadata() -> None:
    # RISK-1 lock: a non-refusal series must carry full window/overlap metadata.
    # A direct dataclass construction with null timestamps cannot bypass the
    # input-series contract (the builder always populates these; this guards the
    # public type itself, which is the shape future multi-input tools inherit).
    pts = (
        PreparedPoint(ts=REFERENCE - timedelta(days=1), value=1.0),
        PreparedPoint(ts=REFERENCE, value=2.0),
    )
    with pytest.raises(ValueError, match="window/overlap metadata"):
        AnalyticalInputSeries(
            metric_id=METRIC,
            question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
            points=pts,
            sample_size=2,
            overlap_sample_size=2,
            # window_start / window_end / overlap_start / overlap_end left None
        )


def test_overlap_window_must_fall_within_usable_window() -> None:
    # The overlap window is the admissible overlap *inside* the usable window;
    # an overlap that starts before the window is an incoherent series.
    start = REFERENCE - timedelta(days=2)
    end = REFERENCE
    pts = (PreparedPoint(ts=start, value=1.0), PreparedPoint(ts=end, value=2.0))
    with pytest.raises(ValueError, match="overlap window must fall within"):
        AnalyticalInputSeries(
            metric_id=METRIC,
            question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
            points=pts,
            window_start=start,
            window_end=end,
            overlap_start=start - timedelta(days=1),
            overlap_end=end,
            sample_size=2,
            overlap_sample_size=2,
        )


def test_to_dict_is_json_safe_and_stable() -> None:
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=5),
        policies=_recent_trend_policy(),
        points=_points(5),
        reference_time=REFERENCE,
        freshness_status="current",
    )
    d1 = series.to_dict()
    d2 = series.to_dict()
    assert d1 == d2
    assert d1["freshness_status"] == "current"
    assert d1["refusal"] is None
    assert isinstance(d1["points"][0]["ts"], str)
