"""m8 WP1 — the condition-paired-difference contract vocabulary (FR-1).

Shipping condition-label pairing requires a new reviewed analytical question
type, a matching policy-layer question type, the closed analytical->policy map
staying total, and a ``QuestionRule`` declared for exactly the metric families
that already allow ``PAIRED_DIFFERENCE`` today (same admissibility posture, no
new family judgments invented). These tests pin that vocabulary.
"""

from __future__ import annotations

from premura.engine.analytical_contract import (
    ANALYTICAL_QUESTION_TYPES,
    AnalyticalQuestionType,
)
from premura.engine.analytical_inputs import ANALYTICAL_TO_POLICY_QUESTION
from premura.engine.policies._defaults import BUILTIN_POLICIES
from premura.engine.policies._model import QuestionType


def test_condition_paired_difference_is_a_new_analytical_question_type() -> None:
    assert AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE.value == "condition_paired_difference"
    assert "condition_paired_difference" in ANALYTICAL_QUESTION_TYPES


def test_condition_paired_difference_has_a_policy_twin() -> None:
    assert QuestionType.CONDITION_PAIRED_DIFFERENCE.value == "condition_paired_difference"


def test_analytical_to_policy_map_stays_total_and_routes_condition_pairing() -> None:
    # The closed map must stay total over the AnalyticalQuestionType enum.
    assert set(ANALYTICAL_TO_POLICY_QUESTION) == set(AnalyticalQuestionType)
    assert (
        ANALYTICAL_TO_POLICY_QUESTION[AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE]
        is QuestionType.CONDITION_PAIRED_DIFFERENCE
    )
    # Identity-by-name onto the policy vocabulary, like every other analytical question.
    for analytical, policy in ANALYTICAL_TO_POLICY_QUESTION.items():
        assert analytical.value == policy.value


def test_condition_rule_declared_for_exactly_the_paired_difference_families() -> None:
    # Same admissibility posture as PAIRED_DIFFERENCE: a family that allows the
    # anchor-date paired difference today also allows condition pairing, and one
    # that does not, does not. No new family judgments are invented tonight.
    saw_any = False
    for policy in BUILTIN_POLICIES:
        rules = policy.question_rules
        has_paired = QuestionType.PAIRED_DIFFERENCE in rules
        has_condition = QuestionType.CONDITION_PAIRED_DIFFERENCE in rules
        assert has_paired == has_condition, policy.metric_family
        if has_paired:
            saw_any = True
    assert saw_any  # guard against the loop asserting nothing
