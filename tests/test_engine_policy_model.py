"""Model-level tests for the Stage 2 policy declaration contract (WP01).

These exercise construction-time validation only. There is no evaluator,
registry, or warehouse behavior in WP01, so nothing here touches SQL, the
network, or PubMed. Everything is imported through the package surface
``premura.engine.policies`` (not private module paths).

The validation-guard tests are parametrized by the dataclass whose constructor
raises. Every case still hits a *distinct* guard branch, pinned by its own
``match`` on the raised message, so collapsing them does not merge code paths.
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


def _acute_policy(**overrides: object) -> MetricFamilyPolicy:
    """A valid POINT_IN_TIME_ACUTE policy with per-field overrides.

    Field-guard tests pass a single malformed override; the surviving fields
    stay valid so the error under test is the only one that can fire.
    """
    kwargs: dict[str, object] = {
        "policy_id": "acute.v1",
        "version": 1,
        "metric_family": "acute_spot_vitals",
        "policy_shape": PolicyShape.POINT_IN_TIME_ACUTE,
        "temporal_meaning": TemporalMeaning.POINT_IN_TIME,
        "question_rules": {QuestionType.CURRENT_STATUS: _admissible_rule()},
    }
    kwargs.update(overrides)
    return MetricFamilyPolicy(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Behavioral construction (success paths + serialization)
# ---------------------------------------------------------------------------


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


def test_valid_until_superseded_without_max_age_constructs():
    # A profile fact is valid until superseded, with no timestamp-style max age.
    rule = FreshnessRule(mode=FreshnessMode.VALID_UNTIL_SUPERSEDED)
    assert rule.max_age is None


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


# ---------------------------------------------------------------------------
# FreshnessRule construction guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        pytest.param(
            {"mode": FreshnessMode.STRICT_WINDOW},
            "strict_window requires max_age",
            id="strict_window_requires_max_age",
        ),
        pytest.param(
            {"mode": FreshnessMode.VALID_UNTIL_SUPERSEDED, "max_age": timedelta(days=30)},
            "valid_until_superseded must not use max_age",
            id="valid_until_superseded_rejects_max_age",
        ),
    ],
)
def test_freshness_rule_construction_guards(kwargs: dict[str, object], match: str):
    with pytest.raises(ValueError, match=match):
        FreshnessRule(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# EvidenceOutcome construction guards (each non-admissible status names a reason)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "question_type", "match"),
    [
        pytest.param(
            EvidenceStatus.REJECTED,
            QuestionType.CURRENT_STATUS,
            "must name at least one rejection reason",
            id="rejected_requires_reason",
        ),
        pytest.param(
            EvidenceStatus.INSUFFICIENT,
            QuestionType.RECENT_TREND,
            "must name at least one rejection reason",
            id="insufficient_requires_reason",
        ),
    ],
)
def test_evidence_outcome_requires_reason(
    status: EvidenceStatus, question_type: QuestionType, match: str
):
    with pytest.raises(ValueError, match=match):
        EvidenceOutcome(
            status=status,
            question_type=question_type,
            metric_family="acute_spot_vitals",
            policy_id="acute_spot_vitals.v1",
            message="no reason given",
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


# ---------------------------------------------------------------------------
# MetricFamilyPolicy caveat-required shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("policy_shape", "temporal_meaning", "question_type"),
    [
        pytest.param(
            PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
            TemporalMeaning.SLOW_TRAJECTORY,
            QuestionType.HISTORICAL_BASELINE,
            id="method_sensitive",
        ),
        pytest.param(
            PolicyShape.BASELINE_RELATIVE,
            TemporalMeaning.ROLLING_RECENT_PATTERN,
            QuestionType.RECENT_TREND,
            id="baseline_relative",
        ),
    ],
)
def test_caveat_required_shape_needs_caveat(
    policy_shape: PolicyShape,
    temporal_meaning: TemporalMeaning,
    question_type: QuestionType,
):
    with pytest.raises(ValueError, match="must carry at least one\\s+standing caveat"):
        MetricFamilyPolicy(
            policy_id="caveat.v1",
            version=1,
            metric_family="caveat_family",
            policy_shape=policy_shape,
            temporal_meaning=temporal_meaning,
            question_rules={question_type: _admissible_rule()},
        )


# ---------------------------------------------------------------------------
# MetricFamilyPolicy field guards (one malformed field over a valid base)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("override", "match"),
    [
        pytest.param(
            {"question_rules": {"current_status": _admissible_rule()}},
            "must be a\\s+QuestionType",
            id="rule_key_must_be_question_type",
        ),
        pytest.param(
            {"applies_to_metrics": (lambda: "bad",)},
            "applies_to_metrics entries must be strings",
            id="applies_to_metrics_must_be_strings",
        ),
        pytest.param(
            {"required_provenance": (lambda: "observed_at",)},
            "required_provenance entries must be strings",
            id="required_provenance_must_be_strings",
        ),
        pytest.param(
            {"policy_id": "  "},
            "policy_id must not be empty",
            id="empty_policy_id",
        ),
        pytest.param(
            {"metric_family": ""},
            "metric_family must not be empty",
            id="empty_metric_family",
        ),
        pytest.param(
            {"question_rules": {}},
            "at least one question_rules entry",
            id="at_least_one_rule",
        ),
        pytest.param(
            {"version": 0},
            "version must be a positive integer",
            id="version_must_be_positive",
        ),
    ],
)
def test_metric_family_policy_field_guards(override: dict[str, object], match: str):
    with pytest.raises(ValueError, match=match):
        _acute_policy(**override)


# ---------------------------------------------------------------------------
# Remaining single-shape guards (QuestionRule / SufficiencyRule / PolicyExample)
# ---------------------------------------------------------------------------


def test_inadmissible_question_rule_requires_rejection_reason():
    with pytest.raises(ValueError, match="inadmissible rule must name at least one"):
        QuestionRule(admissibility=Admissibility.INADMISSIBLE)


def test_question_rule_rejects_callable_admissibility():
    with pytest.raises(ValueError, match="admissibility must be a Admissibility"):
        QuestionRule(admissibility=lambda candidate: Admissibility.ADMISSIBLE)  # type: ignore[arg-type]


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
