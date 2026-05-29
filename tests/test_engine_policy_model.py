"""Model-level tests for the Stage 2 policy declaration contract (WP01).

These exercise construction-time validation only. There is no evaluator,
registry, or warehouse behavior in WP01, so nothing here touches SQL, the
network, or PubMed. Everything is imported through the package surface
``premura.engine.policies`` (not private module paths).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from premura.engine.policies import (
    Admissibility,
    EvaluationResult,
    EvidenceOutcome,
    EvidenceStatus,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    PolicyExample,
    PolicyShape,
    QuestionRule,
    QuestionType,
    RejectionReason,
    SufficiencyRule,
    TemporalMeaning,
)


def _admissible_rule() -> QuestionRule:
    return QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=timedelta(days=2)),
        sufficiency=SufficiencyRule(min_observations=1),
    )


def test_valid_metric_family_policy_constructs():
    policy = MetricFamilyPolicy(
        policy_id="acute_spot_vitals.v1",
        version=1,
        metric_family="acute_spot_vitals",
        policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        question_rules={
            QuestionType.CURRENT_STATUS: _admissible_rule(),
            QuestionType.LONG_TERM_CONTROL: QuestionRule(
                admissibility=Admissibility.INADMISSIBLE,
                default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
            ),
        },
        rationale="A spot vital answers 'what is X right now', not long-term control.",
        examples=(
            PolicyExample(
                question_type=QuestionType.CURRENT_STATUS,
                expected_status=EvidenceStatus.ADMISSIBLE,
                description="Fresh resting HR supports a current-status question.",
            ),
        ),
    )
    assert policy.policy_id == "acute_spot_vitals.v1"
    # The mapping is materialized as a dict and the same question types survive.
    assert set(policy.question_rules) == {
        QuestionType.CURRENT_STATUS,
        QuestionType.LONG_TERM_CONTROL,
    }


def test_strict_window_requires_max_age():
    with pytest.raises(ValueError, match="strict_window requires max_age"):
        FreshnessRule(mode=FreshnessMode.STRICT_WINDOW)


def test_valid_until_superseded_rejects_max_age():
    with pytest.raises(ValueError, match="valid_until_superseded must not use max_age"):
        FreshnessRule(mode=FreshnessMode.VALID_UNTIL_SUPERSEDED, max_age=timedelta(days=30))


def test_valid_until_superseded_without_max_age_constructs():
    # A profile fact is valid until superseded, with no timestamp-style max age.
    rule = FreshnessRule(mode=FreshnessMode.VALID_UNTIL_SUPERSEDED)
    assert rule.max_age is None


def test_inadmissible_question_rule_requires_rejection_reason():
    with pytest.raises(ValueError, match="inadmissible rule must name at least one"):
        QuestionRule(admissibility=Admissibility.INADMISSIBLE)


def test_rejected_outcome_requires_rejection_reason():
    with pytest.raises(ValueError, match="must name at least one rejection reason"):
        EvidenceOutcome(
            status=EvidenceStatus.REJECTED,
            question_type=QuestionType.CURRENT_STATUS,
            metric_family="acute_spot_vitals",
            policy_id="acute_spot_vitals.v1",
            message="rejected",
        )


def test_insufficient_outcome_requires_reason():
    # An insufficient outcome must name *why* it is insufficient, not just fail.
    with pytest.raises(ValueError, match="must name at least one rejection reason"):
        EvidenceOutcome(
            status=EvidenceStatus.INSUFFICIENT,
            question_type=QuestionType.RECENT_TREND,
            metric_family="acute_spot_vitals",
            policy_id="acute_spot_vitals.v1",
            message="not enough points",
        )


def test_evaluation_without_admissible_evidence_requires_refusal():
    rejected = EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=QuestionType.CURRENT_STATUS,
        metric_family="acute_spot_vitals",
        policy_id="acute_spot_vitals.v1",
        message="stale for a current-status question",
        rejection_reasons=(RejectionReason.STALE_FOR_QUESTION,),
    )
    with pytest.raises(ValueError, match="refusal outcome is required"):
        EvaluationResult(
            question_type=QuestionType.CURRENT_STATUS,
            rejected_evidence=(rejected,),
        )


def test_evaluation_with_refusal_constructs_and_serializes():
    refusal = EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=QuestionType.CURRENT_STATUS,
        metric_family="acute_spot_vitals",
        policy_id="acute_spot_vitals.v1",
        message="No admissible evidence for this question.",
        rejection_reasons=(RejectionReason.STALE_FOR_QUESTION,),
    )
    result = EvaluationResult(
        question_type=QuestionType.CURRENT_STATUS,
        rejected_evidence=(refusal,),
        refusal=refusal,
    )
    # The refusal is representable as plain data — no prose parsing needed.
    payload = result.to_dict()
    assert payload["refusal"]["rejection_reasons"] == ["stale_for_question"]
    assert payload["admissible_evidence"] == []


def test_method_sensitive_policy_requires_caveat():
    with pytest.raises(ValueError, match="must carry at least one\\s+standing caveat"):
        MetricFamilyPolicy(
            policy_id="body_composition.v1",
            version=1,
            metric_family="body_composition",
            policy_shape=PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
            temporal_meaning=TemporalMeaning.SLOW_TRAJECTORY,
            question_rules={QuestionType.HISTORICAL_BASELINE: _admissible_rule()},
        )


def test_baseline_relative_policy_requires_caveat():
    # Baseline-relative is the other caveat-required shape.
    with pytest.raises(ValueError, match="must carry at least one\\s+standing caveat"):
        MetricFamilyPolicy(
            policy_id="hrv.v1",
            version=1,
            metric_family="hrv_resting_recovery",
            policy_shape=PolicyShape.BASELINE_RELATIVE,
            temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
            question_rules={QuestionType.RECENT_TREND: _admissible_rule()},
        )


def test_method_sensitive_policy_with_caveat_constructs():
    policy = MetricFamilyPolicy(
        policy_id="body_composition.v1",
        version=1,
        metric_family="body_composition",
        policy_shape=PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
        temporal_meaning=TemporalMeaning.SLOW_TRAJECTORY,
        question_rules={QuestionType.HISTORICAL_BASELINE: _admissible_rule()},
        standing_caveats=("Method-sensitive; interpret trajectory, not a single reading.",),
    )
    assert policy.standing_caveats


def test_question_rules_keys_must_be_question_types():
    with pytest.raises(ValueError, match="must be a\\s+QuestionType"):
        MetricFamilyPolicy(
            policy_id="bad.v1",
            version=1,
            metric_family="bad",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={"current_status": _admissible_rule()},  # type: ignore[dict-item]
        )


def test_question_rule_rejects_callable_admissibility():
    with pytest.raises(ValueError, match="admissibility must be a Admissibility"):
        QuestionRule(admissibility=lambda candidate: Admissibility.ADMISSIBLE)  # type: ignore[arg-type]


def test_policy_rejects_callable_applies_to_metric():
    with pytest.raises(ValueError, match="applies_to_metrics entries must be strings"):
        MetricFamilyPolicy(
            policy_id="bad.v1",
            version=1,
            metric_family="bad",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={QuestionType.CURRENT_STATUS: _admissible_rule()},
            applies_to_metrics=(lambda: "bad",),  # type: ignore[arg-type]
        )


def test_policy_rejects_callable_required_provenance():
    with pytest.raises(ValueError, match="required_provenance entries must be strings"):
        MetricFamilyPolicy(
            policy_id="bad.v1",
            version=1,
            metric_family="bad",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={QuestionType.CURRENT_STATUS: _admissible_rule()},
            required_provenance=(lambda: "observed_at",),  # type: ignore[arg-type]
        )


def test_empty_policy_id_rejected():
    with pytest.raises(ValueError, match="policy_id must not be empty"):
        MetricFamilyPolicy(
            policy_id="  ",
            version=1,
            metric_family="acute_spot_vitals",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={QuestionType.CURRENT_STATUS: _admissible_rule()},
        )


def test_empty_metric_family_rejected():
    with pytest.raises(ValueError, match="metric_family must not be empty"):
        MetricFamilyPolicy(
            policy_id="x.v1",
            version=1,
            metric_family="",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={QuestionType.CURRENT_STATUS: _admissible_rule()},
        )


def test_at_least_one_question_rule_required():
    with pytest.raises(ValueError, match="at least one question_rules entry"):
        MetricFamilyPolicy(
            policy_id="x.v1",
            version=1,
            metric_family="acute_spot_vitals",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={},
        )


def test_version_must_be_positive():
    with pytest.raises(ValueError, match="version must be a positive integer"):
        MetricFamilyPolicy(
            policy_id="x.v0",
            version=0,
            metric_family="acute_spot_vitals",
            policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
            temporal_meaning=TemporalMeaning.POINT_IN_TIME,
            question_rules={QuestionType.CURRENT_STATUS: _admissible_rule()},
        )


def test_sufficiency_coverage_pct_bounds():
    with pytest.raises(ValueError, match="min_coverage_pct must be between 0 and 100"):
        SufficiencyRule(min_coverage_pct=150.0)


def test_policy_example_rejected_status_requires_reason():
    with pytest.raises(ValueError, match="must name its\\s+expected rejection reason"):
        PolicyExample(
            question_type=QuestionType.LONG_TERM_CONTROL,
            expected_status=EvidenceStatus.REJECTED,
            description="A spot vital cannot answer long-term control.",
        )
