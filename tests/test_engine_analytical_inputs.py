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
    ANALYTICAL_TO_DESCRIPTIVE_QUESTION,
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
    """A minimal single-question (recent_trend) family policy for the tests."""
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
# T012: stale input refusal
# ---------------------------------------------------------------------------


def test_stale_evidence_is_refused_before_computation() -> None:
    # Observed 90 days ago, but the policy window is 30 days -> stale.
    stale_at = REFERENCE - timedelta(days=90)
    pts = _points(10, end=stale_at)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=stale_at, point_count=10),
        policies=_recent_trend_policy(max_age=timedelta(days=30)),
        points=pts,
        reference_time=REFERENCE,
    )
    assert not series.is_usable
    assert series.refusal is not None
    assert series.refusal.reason == InputRefusalReason.STALE_FOR_QUESTION.value
    assert series.points == ()
    assert series.sample_size == 0


# ---------------------------------------------------------------------------
# T012: insufficient data refusal
# ---------------------------------------------------------------------------


def test_insufficient_evidence_is_refused() -> None:
    # Policy needs >= 8 observations; candidate has 3.
    pts = _points(3)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=3),
        policies=_recent_trend_policy(min_observations=8),
        points=pts,
        reference_time=REFERENCE,
    )
    assert not series.is_usable
    assert series.refusal is not None
    assert series.refusal.reason == InputRefusalReason.INSUFFICIENT_DATA.value
    assert series.points == ()


def test_parameter_bound_refused_before_computation() -> None:
    # Evidence is admissible, but the analytical parameter bound (min 12 points)
    # is not met -> unsupported_parameter, refused before computation.
    pts = _points(6)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.SMOOTHED_PATTERN,
        candidate=_candidate(observed_at=REFERENCE, point_count=6),
        policies=_recent_trend_policy(),
        points=pts,
        reference_time=REFERENCE,
        min_observations=12,
    )
    assert not series.is_usable
    assert series.refusal is not None
    assert series.refusal.reason == InputRefusalReason.UNSUPPORTED_PARAMETER.value
    assert series.refusal.parameter_name == "min_observations"
    assert series.points == ()


# ---------------------------------------------------------------------------
# T012: rejected / inadmissible input refusal
# ---------------------------------------------------------------------------


def test_inadmissible_family_is_refused() -> None:
    pts = _points(10)
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=_recent_trend_policy(
            admissibility=Admissibility.INADMISSIBLE,
            default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
        ),
        points=pts,
        reference_time=REFERENCE,
    )
    assert not series.is_usable
    assert series.refusal is not None
    assert series.refusal.reason == InputRefusalReason.INADMISSIBLE_FOR_QUESTION.value
    assert series.points == ()


def test_missing_evidence_is_refused() -> None:
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=0),
        policies=_recent_trend_policy(),
        points=[],
        reference_time=REFERENCE,
    )
    assert not series.is_usable
    assert series.refusal is not None
    assert series.refusal.reason == InputRefusalReason.EVIDENCE_MISSING.value
    assert series.points == ()


def test_unsupported_question_when_no_policy_for_family() -> None:
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
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=10),
        policies=other_policy,
        points=_points(10),
        reference_time=REFERENCE,
    )
    assert not series.is_usable
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


def test_question_types_are_closed_and_wired_to_descriptive() -> None:
    # Every reviewed analytical question type maps to a descriptive
    # admissibility question; nothing else is accepted.
    assert set(ANALYTICAL_TO_DESCRIPTIVE_QUESTION) == set(AnalyticalQuestionType)
    assert all(isinstance(v, QuestionType) for v in ANALYTICAL_TO_DESCRIPTIVE_QUESTION.values())


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
