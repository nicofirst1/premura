"""Tests for the deterministic Stage 2 evidence evaluator (WP02).

These tests treat the policy declarations as parameters and assert that the
evaluator (and only the evaluator) decides admissibility, freshness,
sufficiency, and refusal. They never patch ``datetime.now`` because the
evaluator must not call it: recency is judged against an explicit
``reference_time``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from premura.engine.policies._evaluator import evaluate_evidence
from premura.engine.policies._model import (
    Admissibility,
    EvidenceCandidate,
    EvidenceStatus,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    MissingDataBehavior,
    PolicyShape,
    QuestionRule,
    QuestionType,
    RefusalMode,
    RejectionReason,
    SufficiencyRule,
    TemporalMeaning,
)

REFERENCE_TIME = datetime(2026, 5, 29, 12, 0, 0)


# ---------------------------------------------------------------------------
# Policy fixtures (declarations are parameters only)
# ---------------------------------------------------------------------------


def _current_status_policy() -> MetricFamilyPolicy:
    """A point-in-time vital: strict 7-day window for current status."""
    return MetricFamilyPolicy(
        policy_id="vital.point_in_time.v1",
        version=1,
        metric_family="resting_heart_rate",
        policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(
                    mode=FreshnessMode.STRICT_WINDOW,
                    max_age=timedelta(days=7),
                ),
                required_context=("observed_at",),
            ),
        },
        required_provenance=("observed_at",),
    )


def _trend_policy() -> MetricFamilyPolicy:
    """A rolling-pattern family: recent_trend needs >= 5 observations."""
    return MetricFamilyPolicy(
        policy_id="vital.rolling.v1",
        version=1,
        metric_family="step_count",
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.RECENT_TREND: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                sufficiency=SufficiencyRule(
                    min_observations=5,
                    missing_data_behavior=MissingDataBehavior.REJECT,
                ),
                required_context=("observed_at",),
            ),
        },
        required_provenance=("observed_at",),
    )


def _coverage_policy() -> MetricFamilyPolicy:
    """A family that needs >= 80% time coverage for a trend."""
    return MetricFamilyPolicy(
        policy_id="vital.coverage.v1",
        version=1,
        metric_family="sleep_duration",
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.RECENT_TREND: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                sufficiency=SufficiencyRule(
                    min_coverage_pct=80.0,
                    missing_data_behavior=MissingDataBehavior.REJECT,
                ),
            ),
        },
    )


def _long_term_marker_policy() -> MetricFamilyPolicy:
    """A long-term-control marker: inadmissible for current status,
    admissible for long-term control."""
    return MetricFamilyPolicy(
        policy_id="lab.hba1c.v1",
        version=1,
        metric_family="hba1c",
        policy_shape=PolicyShape.INTEGRATED_LONG_TERM_CONTROL,
        temporal_meaning=TemporalMeaning.INTEGRATES_OVER_MONTHS,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.INADMISSIBLE,
                default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
            ),
            QuestionType.LONG_TERM_CONTROL: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(
                    mode=FreshnessMode.STRICT_WINDOW,
                    max_age=timedelta(days=120),
                ),
                required_context=("observed_at",),
            ),
        },
        required_provenance=("observed_at",),
    )


def _superseded_policy() -> MetricFamilyPolicy:
    """An effective-dated profile fact: valid until superseded (no age cutoff)."""
    return MetricFamilyPolicy(
        policy_id="profile.blood_type.v1",
        version=1,
        metric_family="blood_type",
        policy_shape=PolicyShape.ASSERTION_UNTIL_SUPERSEDED,
        temporal_meaning=TemporalMeaning.EFFECTIVE_DATED,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.VALID_UNTIL_SUPERSEDED),
                required_context=("observed_at",),
            ),
        },
        required_provenance=("observed_at",),
    )


# ---------------------------------------------------------------------------
# Required named tests
# ---------------------------------------------------------------------------


def test_strict_window_rejects_stale_current_status_candidate() -> None:
    policy = _current_status_policy()
    candidate = EvidenceCandidate(
        metric_id="rhr-1",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=30),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not result.admissible_evidence
    assert len(result.rejected_evidence) == 1
    rejected = result.rejected_evidence[0]
    assert rejected.rejection_reasons == (RejectionReason.STALE_FOR_QUESTION,)
    assert result.refusal is not None


def test_sparse_trend_candidate_is_insufficient() -> None:
    policy = _trend_policy()
    candidate = EvidenceCandidate(
        metric_id="steps-1",
        metric_family="step_count",
        value_kind="series",
        observed_at=REFERENCE_TIME,
        point_count=2,  # below min_observations=5
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not result.admissible_evidence
    assert len(result.insufficient_evidence) == 1
    insufficient = result.insufficient_evidence[0]
    assert insufficient.status is EvidenceStatus.INSUFFICIENT
    assert RejectionReason.TOO_SPARSE in insufficient.rejection_reasons
    assert result.refusal is not None


def test_insufficient_outcome_carries_policy_standing_caveats() -> None:
    policy = MetricFamilyPolicy(
        policy_id="method.sensitive.v1",
        version=1,
        metric_family="method_sensitive",
        policy_shape=PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
        temporal_meaning=TemporalMeaning.SLOW_TRAJECTORY,
        standing_caveats=("Method-sensitive evidence must be interpreted cautiously.",),
        question_rules={
            QuestionType.RECENT_TREND: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                sufficiency=SufficiencyRule(
                    min_observations=3,
                    missing_data_behavior=MissingDataBehavior.REJECT,
                ),
                required_context=("observed_at",),
            )
        },
    )
    candidate = EvidenceCandidate(
        metric_id="method-sensitive-1",
        metric_family="method_sensitive",
        value_kind="series",
        observed_at=REFERENCE_TIME,
        point_count=1,
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert result.insufficient_evidence
    assert result.insufficient_evidence[0].caveats == policy.standing_caveats


def test_rejected_outcome_carries_policy_standing_caveats() -> None:
    policy = MetricFamilyPolicy(
        policy_id="baseline.relative.v1",
        version=1,
        metric_family="baseline_relative",
        policy_shape=PolicyShape.BASELINE_RELATIVE,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        standing_caveats=("Only meaningful relative to your own baseline.",),
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(
                    mode=FreshnessMode.BASELINE_RELATIVE,
                    max_age=timedelta(days=2),
                ),
                required_context=("observed_at",),
            )
        },
    )
    candidate = EvidenceCandidate(
        metric_id="baseline-relative-1",
        metric_family="baseline_relative",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=5),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert result.rejected_evidence
    assert result.rejected_evidence[0].caveats == policy.standing_caveats


def test_missing_data_behavior_caveat_admits_with_caveat() -> None:
    policy = MetricFamilyPolicy(
        policy_id="caveat.density.v1",
        version=1,
        metric_family="caveat_density",
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.RECENT_TREND: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                sufficiency=SufficiencyRule(
                    min_observations=3,
                    missing_data_behavior=MissingDataBehavior.CAVEAT,
                ),
                required_context=("observed_at",),
            )
        },
    )
    candidate = EvidenceCandidate(
        metric_id="caveat-density-1",
        metric_family="caveat_density",
        value_kind="series",
        observed_at=REFERENCE_TIME,
        point_count=1,
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert result.admissible_evidence
    assert not result.insufficient_evidence
    assert any("density is below" in caveat for caveat in result.admissible_evidence[0].caveats)


def test_refusal_mode_suggest_different_question_adds_caveat() -> None:
    policy = MetricFamilyPolicy(
        policy_id="suggest.question.v1",
        version=1,
        metric_family="long_marker",
        policy_shape=PolicyShape.INTEGRATED_LONG_TERM_CONTROL,
        temporal_meaning=TemporalMeaning.INTEGRATES_OVER_MONTHS,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.INADMISSIBLE,
                default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
                refusal_mode=RefusalMode.SUGGEST_DIFFERENT_QUESTION,
            )
        },
    )
    candidate = EvidenceCandidate(
        metric_id="long-marker-1",
        metric_family="long_marker",
        value_kind="scalar",
        observed_at=REFERENCE_TIME,
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert result.rejected_evidence
    assert any(
        "different question type" in caveat for caveat in result.rejected_evidence[0].caveats
    )


def test_applies_to_metrics_rejects_undeclared_metric_id() -> None:
    policy = MetricFamilyPolicy(
        policy_id="scoped.family.v1",
        version=1,
        metric_family="scoped_family",
        policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        applies_to_metrics=("allowed_metric",),
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
            )
        },
    )
    candidate = EvidenceCandidate(
        metric_id="undeclared_metric",
        metric_family="scoped_family",
        value_kind="scalar",
        observed_at=REFERENCE_TIME,
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not result.admissible_evidence
    assert result.rejected_evidence
    assert RejectionReason.WRONG_EVIDENCE_KIND in result.rejected_evidence[0].rejection_reasons


def test_missing_timestamp_is_not_admissible() -> None:
    policy = _current_status_policy()
    candidate = EvidenceCandidate(
        metric_id="rhr-1",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=None,  # value present, timestamp missing
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not result.admissible_evidence
    assert len(result.rejected_evidence) == 1
    assert RejectionReason.MISSING_TIMESTAMP in result.rejected_evidence[0].rejection_reasons


def test_long_term_marker_differs_by_question_type() -> None:
    policy = _long_term_marker_policy()
    candidate = EvidenceCandidate(
        metric_id="hba1c-1",
        metric_family="hba1c",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=30),
    )

    # Inadmissible for current status.
    current = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not current.admissible_evidence
    assert len(current.rejected_evidence) == 1
    assert RejectionReason.WRONG_EVIDENCE_KIND in current.rejected_evidence[0].rejection_reasons

    # Admissible for long-term control.
    long_term = evaluate_evidence(
        QuestionType.LONG_TERM_CONTROL,
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert len(long_term.admissible_evidence) == 1
    assert not long_term.rejected_evidence
    assert long_term.refusal is None


def test_admissible_and_rejected_evidence_are_separated() -> None:
    policy = _current_status_policy()
    fresh = EvidenceCandidate(
        metric_id="rhr-fresh",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=1),
    )
    stale = EvidenceCandidate(
        metric_id="rhr-stale",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=60),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [fresh, stale],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert len(result.admissible_evidence) == 1
    assert len(result.rejected_evidence) == 1
    assert result.admissible_evidence[0].provenance["metric_id"] == "rhr-fresh"
    assert result.rejected_evidence[0].provenance["metric_id"] == "rhr-stale"
    # Admissible evidence remains -> no refusal.
    assert result.refusal is None


def test_no_admissible_evidence_returns_refusal() -> None:
    policy = _current_status_policy()
    stale = EvidenceCandidate(
        metric_id="rhr-stale",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=60),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [stale],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not result.admissible_evidence
    assert result.refusal is not None
    msg = result.refusal.message.lower()
    # Non-diagnostic, advice-free refusal message.
    for banned in ("you should", "see a doctor", "p-value", "confidence interval", "diagnos"):
        assert banned not in msg


def test_identical_inputs_produce_identical_results() -> None:
    policy = _current_status_policy()
    candidate = EvidenceCandidate(
        metric_id="rhr-1",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=2),
    )
    first = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [candidate], policy, reference_time=REFERENCE_TIME
    )
    second = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [candidate], policy, reference_time=REFERENCE_TIME
    )
    assert first == second
    assert first.to_dict() == second.to_dict()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_mixed_admissible_and_stale_preserves_order() -> None:
    policy = _current_status_policy()
    stale = EvidenceCandidate(
        metric_id="rhr-stale",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=60),
    )
    fresh_a = EvidenceCandidate(
        metric_id="rhr-fresh-a",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=1),
    )
    fresh_b = EvidenceCandidate(
        metric_id="rhr-fresh-b",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=2),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [fresh_a, stale, fresh_b],
        policy,
        reference_time=REFERENCE_TIME,
    )
    admissible_ids = [o.provenance["metric_id"] for o in result.admissible_evidence]
    assert admissible_ids == ["rhr-fresh-a", "rhr-fresh-b"]
    assert len(result.rejected_evidence) == 1


def test_all_candidates_rejected_returns_refusal() -> None:
    policy = _current_status_policy()
    candidates = [
        EvidenceCandidate(
            metric_id=f"rhr-{i}",
            metric_family="resting_heart_rate",
            value_kind="scalar",
            observed_at=REFERENCE_TIME - timedelta(days=40 + i),
        )
        for i in range(3)
    ]
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, candidates, policy, reference_time=REFERENCE_TIME
    )
    assert not result.admissible_evidence
    assert len(result.rejected_evidence) == 3
    assert result.refusal is not None


def test_all_candidates_insufficient_returns_refusal() -> None:
    policy = _trend_policy()
    candidates = [
        EvidenceCandidate(
            metric_id=f"steps-{i}",
            metric_family="step_count",
            value_kind="series",
            observed_at=REFERENCE_TIME,
            point_count=1,
        )
        for i in range(3)
    ]
    result = evaluate_evidence(
        QuestionType.RECENT_TREND, candidates, policy, reference_time=REFERENCE_TIME
    )
    assert not result.admissible_evidence
    assert len(result.insufficient_evidence) == 3
    assert result.refusal is not None


def test_policy_present_but_no_rule_for_question_is_unsupported() -> None:
    policy = _trend_policy()  # only declares RECENT_TREND
    candidate = EvidenceCandidate(
        metric_id="steps-1",
        metric_family="step_count",
        value_kind="series",
        observed_at=REFERENCE_TIME,
        point_count=10,
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,  # no rule for this
        [candidate],
        policy,
        reference_time=REFERENCE_TIME,
    )
    assert not result.admissible_evidence
    assert len(result.rejected_evidence) == 1
    assert RejectionReason.UNSUPPORTED_POLICY in result.rejected_evidence[0].rejection_reasons


def test_candidate_with_no_policy_is_unsupported() -> None:
    policy = _current_status_policy()
    orphan = EvidenceCandidate(
        metric_id="unknown-1",
        metric_family="mystery_metric",
        value_kind="scalar",
        observed_at=REFERENCE_TIME,
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [orphan], policy, reference_time=REFERENCE_TIME
    )
    assert not result.admissible_evidence
    assert RejectionReason.UNSUPPORTED_POLICY in result.rejected_evidence[0].rejection_reasons


def test_strict_window_boundary_is_admissible() -> None:
    policy = _current_status_policy()  # max_age = 7 days
    at_boundary = EvidenceCandidate(
        metric_id="rhr-boundary",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=7),  # age == max_age
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [at_boundary], policy, reference_time=REFERENCE_TIME
    )
    # age > max_age rejects; age == max_age is still admissible.
    assert len(result.admissible_evidence) == 1
    assert not result.rejected_evidence


def test_strict_window_just_past_boundary_is_rejected() -> None:
    policy = _current_status_policy()  # max_age = 7 days
    past_boundary = EvidenceCandidate(
        metric_id="rhr-past",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=7, seconds=1),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [past_boundary], policy, reference_time=REFERENCE_TIME
    )
    assert not result.admissible_evidence
    assert RejectionReason.STALE_FOR_QUESTION in result.rejected_evidence[0].rejection_reasons


def test_valid_until_superseded_admits_old_evidence() -> None:
    policy = _superseded_policy()
    old = EvidenceCandidate(
        metric_id="bt-1",
        metric_family="blood_type",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=3650),  # 10 years old
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [old], policy, reference_time=REFERENCE_TIME
    )
    # No hard age cutoff: still admissible despite being very old.
    assert len(result.admissible_evidence) == 1
    assert not result.rejected_evidence


def test_coverage_below_minimum_is_insufficient() -> None:
    policy = _coverage_policy()
    low_coverage = EvidenceCandidate(
        metric_id="sleep-1",
        metric_family="sleep_duration",
        value_kind="series",
        coverage_pct=40.0,  # below 80
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND, [low_coverage], policy, reference_time=REFERENCE_TIME
    )
    assert len(result.insufficient_evidence) == 1
    assert RejectionReason.TOO_SPARSE in result.insufficient_evidence[0].rejection_reasons


def test_missing_point_count_is_insufficient_when_minimum_declared() -> None:
    policy = _trend_policy()  # min_observations = 5
    no_count = EvidenceCandidate(
        metric_id="steps-1",
        metric_family="step_count",
        value_kind="series",
        observed_at=REFERENCE_TIME,
        point_count=None,  # missing while a minimum is declared
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND, [no_count], policy, reference_time=REFERENCE_TIME
    )
    assert len(result.insufficient_evidence) == 1
    assert RejectionReason.TOO_SPARSE in result.insufficient_evidence[0].rejection_reasons


def test_missing_coverage_pct_is_insufficient_when_minimum_declared() -> None:
    policy = _coverage_policy()  # min_coverage_pct = 80
    no_coverage = EvidenceCandidate(
        metric_id="sleep-1",
        metric_family="sleep_duration",
        value_kind="series",
        coverage_pct=None,
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND, [no_coverage], policy, reference_time=REFERENCE_TIME
    )
    assert len(result.insufficient_evidence) == 1
    assert RejectionReason.TOO_SPARSE in result.insufficient_evidence[0].rejection_reasons


def test_missing_required_context_field_is_rejected() -> None:
    policy = MetricFamilyPolicy(
        policy_id="lab.fasting.v1",
        version=1,
        metric_family="glucose",
        policy_shape=PolicyShape.SPARSE_LAB_ANALYTE_SPECIFIC,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(
                    mode=FreshnessMode.STRICT_WINDOW, max_age=timedelta(days=30)
                ),
                required_context=("fasting_state",),
            ),
        },
        required_provenance=("observed_at",),
    )
    candidate = EvidenceCandidate(
        metric_id="glucose-1",
        metric_family="glucose",
        value_kind="scalar",
        observed_at=REFERENCE_TIME,
        context={},  # fasting_state missing
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [candidate], policy, reference_time=REFERENCE_TIME
    )
    assert not result.admissible_evidence
    assert RejectionReason.MISSING_REQUIRED_CONTEXT in result.rejected_evidence[0].rejection_reasons


def test_provided_required_context_field_is_admissible() -> None:
    policy = MetricFamilyPolicy(
        policy_id="lab.fasting.v1",
        version=1,
        metric_family="glucose",
        policy_shape=PolicyShape.SPARSE_LAB_ANALYTE_SPECIFIC,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(
                    mode=FreshnessMode.STRICT_WINDOW, max_age=timedelta(days=30)
                ),
                required_context=("fasting_state",),
            ),
        },
        required_provenance=("observed_at",),
    )
    candidate = EvidenceCandidate(
        metric_id="glucose-1",
        metric_family="glucose",
        value_kind="scalar",
        observed_at=REFERENCE_TIME,
        context={"fasting_state": "fasting"},
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [candidate], policy, reference_time=REFERENCE_TIME
    )
    assert len(result.admissible_evidence) == 1


def test_standing_caveats_travel_with_admissible_outcome() -> None:
    policy = MetricFamilyPolicy(
        policy_id="lab.baseline.v1",
        version=1,
        metric_family="vo2max",
        policy_shape=PolicyShape.BASELINE_RELATIVE,
        temporal_meaning=TemporalMeaning.SLOW_TRAJECTORY,
        question_rules={
            QuestionType.HISTORICAL_BASELINE: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.BASELINE_RELATIVE),
            ),
        },
        standing_caveats=("Estimate is method-sensitive; compare like with like.",),
    )
    candidate = EvidenceCandidate(
        metric_id="vo2-1",
        metric_family="vo2max",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=200),
    )
    result = evaluate_evidence(
        QuestionType.HISTORICAL_BASELINE, [candidate], policy, reference_time=REFERENCE_TIME
    )
    assert len(result.admissible_evidence) == 1
    assert any("method-sensitive" in c for c in result.admissible_evidence[0].caveats)


def test_empty_candidates_returns_refusal() -> None:
    policy = _current_status_policy()
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [], policy, reference_time=REFERENCE_TIME
    )
    assert not result.admissible_evidence
    assert result.refusal is not None


def test_policies_accepted_as_mapping() -> None:
    policy = _current_status_policy()
    candidate = EvidenceCandidate(
        metric_id="rhr-1",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=1),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        {"resting_heart_rate": policy},
        reference_time=REFERENCE_TIME,
    )
    assert len(result.admissible_evidence) == 1


def test_policies_accepted_as_sequence() -> None:
    rhr = _current_status_policy()
    steps = _trend_policy()
    rhr_candidate = EvidenceCandidate(
        metric_id="rhr-1",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=1),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [rhr_candidate],
        [rhr, steps],
        reference_time=REFERENCE_TIME,
    )
    assert len(result.admissible_evidence) == 1


def test_outcome_messages_are_non_diagnostic() -> None:
    """No outcome message anywhere should contain advice or statistics."""
    rhr = _current_status_policy()
    long_term = _long_term_marker_policy()
    candidates = [
        EvidenceCandidate(
            metric_id="rhr-stale",
            metric_family="resting_heart_rate",
            value_kind="scalar",
            observed_at=REFERENCE_TIME - timedelta(days=60),
        ),
        EvidenceCandidate(
            metric_id="hba1c-1",
            metric_family="hba1c",
            value_kind="scalar",
            observed_at=REFERENCE_TIME,
        ),
    ]
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        candidates,
        [rhr, long_term],
        reference_time=REFERENCE_TIME,
    )
    all_outcomes = [
        *result.admissible_evidence,
        *result.rejected_evidence,
        *result.insufficient_evidence,
    ]
    if result.refusal is not None:
        all_outcomes.append(result.refusal)
    banned = ("you should", "see a doctor", "p-value", "p<", "confidence interval", "diagnos")
    for outcome in all_outcomes:
        lowered = outcome.message.lower()
        for phrase in banned:
            assert phrase not in lowered


@pytest.mark.parametrize("days_old", [0, 1, 6])
def test_fresh_current_status_is_admissible(days_old: int) -> None:
    policy = _current_status_policy()
    candidate = EvidenceCandidate(
        metric_id="rhr-1",
        metric_family="resting_heart_rate",
        value_kind="scalar",
        observed_at=REFERENCE_TIME - timedelta(days=days_old),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS, [candidate], policy, reference_time=REFERENCE_TIME
    )
    assert len(result.admissible_evidence) == 1
    assert result.refusal is None
