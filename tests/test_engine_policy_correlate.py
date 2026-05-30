"""Policy-layer tests for `correlate` lagged-association admissibility (WP01).

`correlate` is gated on its OWN first-class analytical question type, with its
own freshness/sufficiency declarations — never collapsed onto ``recent_trend``,
``level_shift_detection``, or ``smoothed_pattern`` (ADR-0008 / research note Q3).
These tests pin:

* a first-class policy ``QuestionType`` for lagged association;
* the closed analytical->policy question mapping wires correlate through the
  existing evaluator with no new mini-language;
* conservative, parameter-only default sufficiency that supports the later raw
  paired-sample floor of 20 (effective-sample floor of 12 is enforced in the
  tool, not the policy data);
* refusal reasons stay distinct from the single-series analytical questions.

Nothing here imports MCP, DuckDB, PubMed, or any network module.

Subtasks covered: T001 (policy-half failing contract) and T003 (mapping +
default sufficiency/freshness declarations).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from premura.engine.analytical_contract import AnalyticalQuestionType
from premura.engine.analytical_inputs import ANALYTICAL_TO_POLICY_QUESTION
from premura.engine.policies._defaults import BUILTIN_POLICIES
from premura.engine.policies._evaluator import evaluate_evidence
from premura.engine.policies._model import (
    EvidenceCandidate,
    EvidenceStatus,
    QuestionType,
    RejectionReason,
    SufficiencyRule,
)

# The locked raw paired-sample floor from the methodology research note (Q3).
RAW_PAIRED_FLOOR = 20


# ---------------------------------------------------------------------------
# T001 / T003: first-class policy question type for lagged association
# ---------------------------------------------------------------------------


def test_policy_question_type_has_lagged_association() -> None:
    """The policy layer mirrors the analytical question with its own closed
    ``QuestionType`` member, not a reused single-series shape."""
    assert QuestionType.LAGGED_ASSOCIATION.value == "lagged_association"
    assert QuestionType.LAGGED_ASSOCIATION is not QuestionType.RECENT_TREND
    assert QuestionType.LAGGED_ASSOCIATION is not QuestionType.LEVEL_SHIFT_DETECTION
    assert QuestionType.LAGGED_ASSOCIATION is not QuestionType.SMOOTHED_PATTERN


def test_analytical_to_policy_mapping_wires_lagged_association() -> None:
    """The closed analytical->policy map routes lagged association through the
    evaluator using the matching first-class policy question type — no ad-hoc
    string reaches the evaluator."""
    mapped = ANALYTICAL_TO_POLICY_QUESTION.get(AnalyticalQuestionType.LAGGED_ASSOCIATION)
    assert mapped is QuestionType.LAGGED_ASSOCIATION


# ---------------------------------------------------------------------------
# T003: default sufficiency/freshness declarations on recent-run families
# ---------------------------------------------------------------------------


def _families_with_recent_run() -> list:
    return [p for p in BUILTIN_POLICIES if QuestionType.RECENT_TREND in p.question_rules]


def test_recent_run_families_declare_lagged_association_rule() -> None:
    """Every family that supports recent-trend (the daily-series substrate
    correlate pairs over) also declares a lagged-association rule; families
    without a recent-run rule declare none, so an inadmissible substrate (A1C,
    profile, acute spot) never silently becomes a correlate input."""
    saw = False
    for policy in BUILTIN_POLICIES:
        rules = policy.question_rules
        if QuestionType.RECENT_TREND in rules:
            saw = True
            assert QuestionType.LAGGED_ASSOCIATION in rules, policy.metric_family
        else:
            assert QuestionType.LAGGED_ASSOCIATION not in rules, policy.metric_family
    assert saw


def test_lagged_association_rule_is_distinct_from_other_analytical_rules() -> None:
    """Lagged association is NOT the same rule object as recent-trend or the
    single-series analytical questions: it carries its own sufficiency so the
    paired-sample floor cannot be hidden behind a single-series threshold."""
    for policy in _families_with_recent_run():
        rules = policy.question_rules
        lagged = rules[QuestionType.LAGGED_ASSOCIATION]
        assert lagged is not rules[QuestionType.RECENT_TREND], policy.metric_family
        if QuestionType.LEVEL_SHIFT_DETECTION in rules:
            assert lagged is not rules[QuestionType.LEVEL_SHIFT_DETECTION]
        if QuestionType.SMOOTHED_PATTERN in rules:
            assert lagged is not rules[QuestionType.SMOOTHED_PATTERN]


def test_lagged_association_default_supports_raw_paired_floor() -> None:
    """The conservative default sufficiency declares a min-observations floor of
    at least the raw paired-sample floor (20). Declarative parameters only — no
    callables/expressions live in the rule."""
    for policy in _families_with_recent_run():
        rule = policy.question_rules[QuestionType.LAGGED_ASSOCIATION]
        assert rule.sufficiency is not None, policy.metric_family
        assert isinstance(rule.sufficiency, SufficiencyRule)
        assert rule.sufficiency.min_observations is not None
        assert rule.sufficiency.min_observations >= RAW_PAIRED_FLOOR, policy.metric_family


def test_lagged_association_refuses_below_raw_paired_floor() -> None:
    """A short overlap below the floor is refused with a distinct sparsity
    reason via the existing evaluator — refusal reasons remain distinct."""
    policy = _families_with_recent_run()[0]
    reference_time = datetime(2026, 1, 1, tzinfo=UTC)
    candidate = EvidenceCandidate(
        metric_id=policy.applies_to_metrics[0] if policy.applies_to_metrics else "probe",
        metric_family=policy.metric_family,
        value_kind="series",
        observed_at=reference_time - timedelta(days=1),
        point_count=RAW_PAIRED_FLOOR - 1,
        coverage_pct=100.0,
    )
    result = evaluate_evidence(
        QuestionType.LAGGED_ASSOCIATION,
        [candidate],
        policy,
        reference_time=reference_time,
    )
    assert not result.admissible_evidence
    reasons = {r for o in result.insufficient_evidence for r in o.rejection_reasons}
    assert RejectionReason.TOO_SPARSE in reasons


def test_lagged_association_admits_at_or_above_floor() -> None:
    """A recent overlap at the floor is admissible through the same evaluator."""
    policy = _families_with_recent_run()[0]
    reference_time = datetime(2026, 1, 1, tzinfo=UTC)
    candidate = EvidenceCandidate(
        metric_id=policy.applies_to_metrics[0] if policy.applies_to_metrics else "probe",
        metric_family=policy.metric_family,
        value_kind="series",
        observed_at=reference_time - timedelta(days=1),
        point_count=RAW_PAIRED_FLOOR,
        coverage_pct=100.0,
    )
    result = evaluate_evidence(
        QuestionType.LAGGED_ASSOCIATION,
        [candidate],
        policy,
        reference_time=reference_time,
    )
    assert result.admissible_evidence


def test_long_term_control_family_does_not_admit_lagged_association() -> None:
    """An integrate-over-months family (A1C-like) declares no lagged-association
    rule, so a correlate request over it is refused as unsupported — the wrong
    substrate cannot leak into a paired correlation."""
    a1c = next(p for p in BUILTIN_POLICIES if p.metric_family == "a1c_like_control")
    assert QuestionType.LAGGED_ASSOCIATION not in a1c.question_rules
    reference_time = datetime(2026, 1, 1, tzinfo=UTC)
    candidate = EvidenceCandidate(
        metric_id="hba1c",
        metric_family="a1c_like_control",
        value_kind="series",
        observed_at=reference_time,
        point_count=RAW_PAIRED_FLOOR,
    )
    result = evaluate_evidence(
        QuestionType.LAGGED_ASSOCIATION,
        [candidate],
        a1c,
        reference_time=reference_time,
    )
    assert not result.admissible_evidence
    assert result.refusal is not None
    assert RejectionReason.UNSUPPORTED_POLICY in result.refusal.rejection_reasons
