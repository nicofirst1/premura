"""Tests for the Stage 3 *paired* analytical input preparation layer (WP02).

These exercise the two-series preparation seam ``correlate`` needs before any
coefficient can run (WP03): two already-admitted single-series
:class:`AnalyticalInputSeries` values plus a pre-registered hypothesis become an
ordered, overlap-narrowed :class:`PairedAnalyticalInput` — or a first-class
:class:`RefusalOutcome` with **no** pairs. Pairing is by same local calendar day
*after* applying the caller-declared integer-day lag; there is never a symmetric
tolerance window and never a lag scan (ADR-0008).

Everything is fixture-backed (hand-built ``PreparedPoint`` series via the WP02
single-series preparer); the layer reads no warehouse, so nothing here touches
SQL, DuckDB, MCP, or the network. The tests deliberately do **not** depend on the
eventual Spearman implementation — WP02 stops at a validated paired bundle.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from premura.engine.analytical_contract import AnalyticalQuestionType, RefusalOutcome
from premura.engine.analytical_inputs import (
    AnalyticalInputSeries,
    ExpectedDirection,
    InputRefusalReason,
    PairedAnalyticalInput,
    PairedInputRefusalReason,
    PairedObservation,
    PreparedPoint,
    PreRegisteredAssociationHypothesis,
    paired_points_for_computation,
    prepare_input_series,
    prepare_paired_input,
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

REFERENCE = datetime(2026, 5, 29, 0, 0, 0)
LEFT_METRIC = "resting_heart_rate"
RIGHT_METRIC = "hrv_overnight"
LEFT_FAMILY = "left_family"
RIGHT_FAMILY = "right_family"


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers (mirror the single-series test style)
# ---------------------------------------------------------------------------


def _policy(family: str, metric: str, *, min_observations: int = 1) -> MetricFamilyPolicy:
    """A family policy that admits the lagged-association question for ``metric``."""
    rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
        sufficiency=SufficiencyRule(
            min_observations=min_observations,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
    )
    return MetricFamilyPolicy(
        policy_id=f"{family}@1",
        version=1,
        metric_family=family,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={QuestionType.LAGGED_ASSOCIATION: rule},
        applies_to_metrics=(metric,),
    )


def _candidate(metric: str, family: str, *, point_count: int) -> EvidenceCandidate:
    return EvidenceCandidate(
        metric_id=metric,
        metric_family=family,
        value_kind="aggregate",
        observed_at=REFERENCE,
        source_id="fixture",
        point_count=point_count,
    )


def _daily_points(
    n: int,
    *,
    start: datetime = REFERENCE - timedelta(days=29),
    base: float = 50.0,
    imputed_idx: tuple[int, ...] = (),
) -> list[PreparedPoint]:
    """``n`` consecutive daily points starting at ``start`` (one per calendar day)."""
    out: list[PreparedPoint] = []
    for i in range(n):
        ts = start + timedelta(days=i)
        out.append(PreparedPoint(ts=ts, value=base + i, is_imputed=i in imputed_idx))
    return out


def _series(
    metric: str,
    family: str,
    points: list[PreparedPoint],
) -> AnalyticalInputSeries:
    """Prepare a usable single-series input through the WP02 preparer."""
    return prepare_input_series(
        metric,
        AnalyticalQuestionType.LAGGED_ASSOCIATION,
        candidate=_candidate(metric, family, point_count=len(points)),
        policies=_policy(family, metric),
        points=points,
        reference_time=REFERENCE,
    )


def _hypothesis(**overrides) -> PreRegisteredAssociationHypothesis:
    base = dict(
        left_metric_id=LEFT_METRIC,
        right_metric_id=RIGHT_METRIC,
        lag_days=0,
        expected_direction=ExpectedDirection.POSITIVE,
    )
    base.update(overrides)
    return PreRegisteredAssociationHypothesis(**base)


# ===========================================================================
# T006 / T008: same-day pairing after caller-declared lag
# ===========================================================================


def test_pairs_only_on_same_calendar_day_at_lag_zero() -> None:
    # Left and right share 25 overlapping days; right also has 5 extra trailing
    # days that have no left counterpart and must NOT pair.
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(30))

    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))

    assert paired.is_usable
    assert paired.refusal is None
    # Only the 25 shared calendar days pair.
    assert paired.overlap_sample_size == 25
    assert len(paired.pairs) == 25
    # Pairs are ordered by paired day.
    days = [p.paired_day for p in paired.pairs]
    assert days == sorted(days)
    # Overlap metadata narrowed to the actual paired days.
    assert paired.overlap_start == paired.pairs[0].paired_day
    assert paired.overlap_end == paired.pairs[-1].paired_day


def test_neighboring_days_do_not_pair_without_lag() -> None:
    # Left days D0..D24, right days shifted +1 calendar day (D1..D25). With lag 0
    # there is NO symmetric tolerance: a left day only pairs a right day on the
    # SAME calendar day, so the overlap is the 24-day intersection D1..D24.
    left = _series(
        LEFT_METRIC, LEFT_FAMILY, _daily_points(25, start=REFERENCE - timedelta(days=24))
    )
    right = _series(
        RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25, start=REFERENCE - timedelta(days=23))
    )

    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))

    assert paired.is_usable
    # Same-calendar-day intersection only: 24 shared days, never 25 via tolerance.
    assert paired.overlap_sample_size == 24


def test_lag_one_aligns_right_series_onto_left_day() -> None:
    # Right is the responding series. The hypothesis is "left at day D associates
    # with right at day D + lag". With lag 1, right's day D+1 aligns onto left's
    # day D. Construct right entirely one day later than left; with lag 1 they
    # should pair fully, whereas lag 0 (covered above) would not.
    left_pts = _daily_points(25, start=REFERENCE - timedelta(days=24), base=10.0)
    right_pts = _daily_points(25, start=REFERENCE - timedelta(days=23), base=100.0)
    left = _series(LEFT_METRIC, LEFT_FAMILY, left_pts)
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, right_pts)

    paired_lag0 = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    paired_lag1 = prepare_paired_input(left, right, _hypothesis(lag_days=1))

    # Lag 1 recovers the full 25-day pairing that lag 0 cannot.
    assert paired_lag1.is_usable
    assert paired_lag1.overlap_sample_size == 25
    assert paired_lag0.overlap_sample_size == 24
    # The paired day is keyed to the LEFT series day; right's value comes from
    # the day one later.
    first = paired_lag1.pairs[0]
    assert first.paired_day == left_pts[0].ts.date()
    assert first.left_value == left_pts[0].value
    assert first.right_value == right_pts[0].value  # right day D+1 carries this


# ===========================================================================
# T007: hypothesis + paired-input shape validation
# ===========================================================================


def test_hypothesis_requires_both_metric_ids() -> None:
    with pytest.raises(ValueError, match="metric"):
        PreRegisteredAssociationHypothesis(
            left_metric_id="",
            right_metric_id=RIGHT_METRIC,
            lag_days=0,
            expected_direction=ExpectedDirection.POSITIVE,
        ).validate()


def test_hypothesis_requires_expected_direction_value() -> None:
    with pytest.raises(ValueError, match="expected_direction"):
        PreRegisteredAssociationHypothesis(
            left_metric_id=LEFT_METRIC,
            right_metric_id=RIGHT_METRIC,
            lag_days=0,
            expected_direction="up",  # type: ignore[arg-type]
        ).validate()


def test_small_lag_is_free_without_justification() -> None:
    for lag in (-3, -1, 0, 1, 3):
        _hypothesis(lag_days=lag).validate()  # must not raise


def test_medium_lag_requires_justification() -> None:
    with pytest.raises(ValueError, match="justification"):
        _hypothesis(lag_days=7).validate()
    # With justification it is accepted.
    _hypothesis(lag_days=7, lag_justification="lactose -> gut symptoms next week").validate()


def test_large_lag_is_refused_even_with_justification() -> None:
    with pytest.raises(ValueError, match="lag"):
        _hypothesis(lag_days=15, lag_justification="anything").validate()


def test_paired_observation_requires_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        PairedObservation(
            paired_day=REFERENCE.date(),
            left_ts=REFERENCE,
            right_ts=REFERENCE,
            left_value=float("nan"),
            right_value=1.0,
        )


def test_paired_observation_imputed_when_either_side_imputed() -> None:
    obs = PairedObservation(
        paired_day=REFERENCE.date(),
        left_ts=REFERENCE,
        right_ts=REFERENCE,
        left_value=1.0,
        right_value=2.0,
        left_is_imputed=False,
        right_is_imputed=True,
    )
    assert obs.is_imputed is True


def test_refused_paired_input_carries_no_pairs_or_sample_size() -> None:
    refusal = RefusalOutcome(reason="no_paired_overlap", message="none")
    with pytest.raises(ValueError, match="no .*pairs|must not carry"):
        PairedAnalyticalInput(
            left_metric_id=LEFT_METRIC,
            right_metric_id=RIGHT_METRIC,
            question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
            pairs=(
                PairedObservation(
                    paired_day=REFERENCE.date(),
                    left_ts=REFERENCE,
                    right_ts=REFERENCE,
                    left_value=1.0,
                    right_value=2.0,
                ),
            ),
            refusal=refusal,
        )


# ===========================================================================
# T009: refusal behavior
# ===========================================================================


def test_missing_hypothesis_refuses() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    paired = prepare_paired_input(left, right, None)  # type: ignore[arg-type]
    assert not paired.is_usable
    assert paired.refusal is not None
    assert paired.refusal.reason == PairedInputRefusalReason.MISSING_HYPOTHESIS.value
    assert paired.pairs == ()
    assert paired.overlap_sample_size == 0


def test_invalid_lag_refuses_via_envelope_not_exception() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    # A >14 lag is an unsupported parameter: it must come back as a structured
    # refusal envelope, not an ad-hoc raised exception.
    paired = prepare_paired_input(
        left, right, _hypothesis(lag_days=20, lag_justification="x")
    )
    assert not paired.is_usable
    assert paired.refusal is not None
    assert paired.refusal.reason == PairedInputRefusalReason.INVALID_LAG.value
    assert paired.pairs == ()


def test_missing_lag_justification_refuses() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=8))
    assert not paired.is_usable
    assert paired.refusal is not None
    assert paired.refusal.reason == PairedInputRefusalReason.MISSING_LAG_JUSTIFICATION.value


def test_refused_left_input_propagates_as_paired_refusal() -> None:
    # The left series is itself refused (no evidence). The paired preparer must
    # delegate to that WP01-policy-derived refusal, not reimplement admissibility.
    left = prepare_input_series(
        LEFT_METRIC,
        AnalyticalQuestionType.LAGGED_ASSOCIATION,
        candidate=_candidate(LEFT_METRIC, LEFT_FAMILY, point_count=0),
        policies=_policy(LEFT_FAMILY, LEFT_METRIC),
        points=[],
        reference_time=REFERENCE,
    )
    assert left.refusal is not None  # precondition: WP01 policy refused it
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))

    paired = prepare_paired_input(left, right, _hypothesis())
    assert not paired.is_usable
    assert paired.refusal is not None
    # The refusal carries the underlying admissibility reason VERBATIM (delegated
    # to the WP01-policy-derived single-series refusal, not a parallel
    # reimplementation): an empty left series refuses with evidence_missing.
    assert paired.refusal.reason == left.refusal.reason
    assert paired.refusal.reason == InputRefusalReason.EVIDENCE_MISSING.value
    assert LEFT_METRIC in paired.refusal.missing_or_bad_inputs
    assert paired.pairs == ()


def test_inadmissible_right_input_propagates() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    bad_policy = MetricFamilyPolicy(
        policy_id="bad@1",
        version=1,
        metric_family=RIGHT_FAMILY,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.LAGGED_ASSOCIATION: QuestionRule(
                admissibility=Admissibility.INADMISSIBLE,
                default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
            )
        },
        applies_to_metrics=(RIGHT_METRIC,),
    )
    right = prepare_input_series(
        RIGHT_METRIC,
        AnalyticalQuestionType.LAGGED_ASSOCIATION,
        candidate=_candidate(RIGHT_METRIC, RIGHT_FAMILY, point_count=25),
        policies=bad_policy,
        points=_daily_points(25),
        reference_time=REFERENCE,
    )
    assert right.refusal is not None
    paired = prepare_paired_input(left, right, _hypothesis())
    assert not paired.is_usable
    assert paired.refusal is not None
    assert paired.refusal.reason == InputRefusalReason.INADMISSIBLE_FOR_QUESTION.value
    assert RIGHT_METRIC in paired.refusal.missing_or_bad_inputs


def test_no_overlap_after_lag_refuses() -> None:
    # Disjoint calendar days -> zero pairs after same-day matching.
    left = _series(
        LEFT_METRIC, LEFT_FAMILY, _daily_points(25, start=REFERENCE - timedelta(days=200))
    )
    right = _series(
        RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25, start=REFERENCE - timedelta(days=24))
    )
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    assert not paired.is_usable
    assert paired.refusal is not None
    assert paired.refusal.reason == PairedInputRefusalReason.NO_PAIRED_OVERLAP.value
    assert paired.pairs == ()


def test_weak_paired_support_below_floor_refuses() -> None:
    # Only 19 shared calendar days -> below the raw paired floor of 20.
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(19))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(19))
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    assert not paired.is_usable
    assert paired.refusal is not None
    assert paired.refusal.reason == PairedInputRefusalReason.WEAK_PAIRED_SUPPORT.value
    assert paired.pairs == ()


def test_each_refusal_reason_is_distinct() -> None:
    reasons = {
        PairedInputRefusalReason.MISSING_HYPOTHESIS.value,
        PairedInputRefusalReason.INVALID_LAG.value,
        PairedInputRefusalReason.MISSING_LAG_JUSTIFICATION.value,
        PairedInputRefusalReason.NO_PAIRED_OVERLAP.value,
        PairedInputRefusalReason.WEAK_PAIRED_SUPPORT.value,
    }
    assert len(reasons) == 5


def test_paired_points_for_computation_blocks_refused_input() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(19))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(19))
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    with pytest.raises(RuntimeError, match="must not be passed to computation"):
        paired_points_for_computation(paired)


def test_paired_points_for_computation_returns_pairs_for_usable_input() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    pairs = paired_points_for_computation(paired)
    assert pairs == paired.pairs
    assert len(pairs) == 25


# ===========================================================================
# T010: imputed-pair percentage + paired-source provenance
# ===========================================================================


def test_imputed_pair_percentage_counts_either_side_imputed() -> None:
    # Left imputes its first 5 of 25 points; right imputes none. The 5 paired
    # days where the left side is imputed count as imputed pairs -> 20%.
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25, imputed_idx=(0, 1, 2, 3, 4)))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    assert paired.is_usable
    assert paired.is_imputed_pct == pytest.approx(20.0)


def test_source_summary_carries_both_inputs_and_is_json_safe() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    paired = prepare_paired_input(
        left,
        right,
        _hypothesis(lag_days=2, common_cause_candidates=("seasonal_illness",)),
    )
    d = paired.to_dict()
    assert d["left_metric_id"] == LEFT_METRIC
    assert d["right_metric_id"] == RIGHT_METRIC
    # Enough to reproduce which metrics + lag produced the pair set.
    assert d["source_summary"]["lag_days"] == 2
    assert d["source_summary"]["left"]["metric_id"] == LEFT_METRIC
    assert d["source_summary"]["right"]["metric_id"] == RIGHT_METRIC
    # JSON-safe + stable.
    import json

    assert json.dumps(d, sort_keys=True) == json.dumps(paired.to_dict(), sort_keys=True)


def test_overlap_sample_size_equals_pair_count() -> None:
    left = _series(LEFT_METRIC, LEFT_FAMILY, _daily_points(25))
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, _daily_points(25))
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    assert paired.overlap_sample_size == len(paired.pairs)


def test_prepared_pairs_match_fixture_dates_exactly() -> None:
    # Deterministic alignment: with lag 0, the paired days are exactly the shared
    # calendar days, in order, with the right value taken from the same day.
    left_pts = _daily_points(20, start=REFERENCE - timedelta(days=19), base=1.0)
    right_pts = _daily_points(20, start=REFERENCE - timedelta(days=19), base=1000.0)
    left = _series(LEFT_METRIC, LEFT_FAMILY, left_pts)
    right = _series(RIGHT_METRIC, RIGHT_FAMILY, right_pts)
    paired = prepare_paired_input(left, right, _hypothesis(lag_days=0))
    assert [p.paired_day for p in paired.pairs] == [pt.ts.date() for pt in left_pts]
    assert [p.left_value for p in paired.pairs] == [pt.value for pt in left_pts]
    assert [p.right_value for p in paired.pairs] == [pt.value for pt in right_pts]
