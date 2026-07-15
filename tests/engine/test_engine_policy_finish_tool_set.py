"""Policy-vocabulary tests for the finished analytical tool set (WP01).

These prove the admissibility *foundation* the two remaining roadmap tools
(`rolling_mean` and `paired_t_test`) gate on:

* the new first-class policy question types `MOVING_WINDOW_PATTERN` and
  `PAIRED_DIFFERENCE` exist in the closed policy vocabulary;
* the built-in defaults declare measurable freshness/sufficiency rules for them
  on the recent-run families, family-based rather than metric-specific;
* `paired_difference` carries its OWN paired-sample floor — it never silently
  reuses the lagged-association rule or a descriptive trend rule;
* a family that declares no rule for a new question type still produces the
  established `UNSUPPORTED_POLICY` refusal, not a Python exception.

No analytical-method math is decided here (that is WP02/WP04). Tests drive the
shipped evaluator/registry public surface, not private collaborators.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from premura.engine.policies._defaults import (
    BUILTIN_POLICIES,
    builtin_policies,
)
from premura.engine.policies._evaluator import evaluate_evidence
from premura.engine.policies._model import (
    EvidenceCandidate,
    EvidenceStatus,
    QuestionType,
    RejectionReason,
    SufficiencyRule,
)
from premura.engine.policies._registry import build_builtin_registry

NOW = datetime(2026, 5, 29, 12, 0, 0)

# The two reviewed analytical question types this mission adds.
_NEW_ANALYTICAL = (QuestionType.MOVING_WINDOW_PATTERN, QuestionType.PAIRED_DIFFERENCE)


# ---------------------------------------------------------------------------
# T002: closed vocabulary + measurable default gates
# ---------------------------------------------------------------------------


def test_new_question_types_carry_the_committed_wire_values() -> None:
    """The two new shapes serialize to their committed wire strings.

    Member *existence* is already exercised by every test below that keys
    ``question_rules`` on these members; what is pinned *only* here is the
    serialized ``.value`` (the wire format), which nothing else asserts.
    """
    assert QuestionType.MOVING_WINDOW_PATTERN.value == "moving_window_pattern"
    assert QuestionType.PAIRED_DIFFERENCE.value == "paired_difference"


def test_recent_run_families_declare_the_new_analytical_rules() -> None:
    """Every family with a recent-run substrate gates the new analytical shapes.

    Mirrors the existing DRIFT-1 guard for level-shift/smoothed-pattern: a family
    that can honestly support recent trend also declares the moving-window and
    paired-difference questions; a family with no recent-run rule declares
    neither (so a long-term-control/profile/acute substrate is never silently
    opened to analytical tools).
    """
    saw_recent_run = False
    for policy in BUILTIN_POLICIES:
        rules = policy.question_rules
        if QuestionType.RECENT_TREND in rules:
            saw_recent_run = True
            for q in _NEW_ANALYTICAL:
                assert q in rules, f"{policy.metric_family} missing {q.value}"
        else:
            for q in _NEW_ANALYTICAL:
                assert q not in rules, (
                    f"{policy.metric_family} declares {q.value} without a recent-run rule"
                )
    assert saw_recent_run


def test_new_analytical_rules_carry_measurable_sufficiency_or_freshness() -> None:
    """The default rules are not empty passthroughs: each carries a real gate."""
    for policy in BUILTIN_POLICIES:
        for q in _NEW_ANALYTICAL:
            rule = policy.question_rules.get(q)
            if rule is None:
                continue
            has_freshness = rule.freshness is not None
            has_sufficiency = rule.sufficiency is not None and (
                rule.sufficiency.min_observations is not None
                or rule.sufficiency.min_span is not None
                or rule.sufficiency.min_coverage_pct is not None
            )
            assert has_freshness or has_sufficiency, (
                f"{policy.metric_family}:{q.value} declares no measurable gate"
            )


def test_paired_difference_rule_is_family_based_not_metric_specific() -> None:
    """The paired-difference default is keyed on the family shape, not a metric.

    The same paired-sample floor must be reused across families rather than
    hand-tuned per metric id, so the rule's sufficiency is shape-derived.
    """
    floors: set[int] = set()
    for policy in BUILTIN_POLICIES:
        rule = policy.question_rules.get(QuestionType.PAIRED_DIFFERENCE)
        if rule is None or rule.sufficiency is None:
            continue
        if rule.sufficiency.min_observations is not None:
            floors.add(rule.sufficiency.min_observations)
    # A single shared paired floor across families (not a per-metric grid).
    assert len(floors) == 1, f"paired floor should be one shared value, saw {floors}"


# ---------------------------------------------------------------------------
# T004: the new shapes are gated independently of existing shapes
# ---------------------------------------------------------------------------


def test_paired_difference_does_not_reuse_lagged_association_rule() -> None:
    """`paired_difference` must not silently reuse the `lagged_association` rule.

    They share neither rule object nor sufficiency floor by accident: paired
    before/after and lagged two-series association are different sufficiency
    questions.
    """
    for policy in BUILTIN_POLICIES:
        paired = policy.question_rules.get(QuestionType.PAIRED_DIFFERENCE)
        lagged = policy.question_rules.get(QuestionType.LAGGED_ASSOCIATION)
        if paired is None or lagged is None:
            continue
        assert paired is not lagged, (
            f"{policy.metric_family} collapsed paired_difference onto lagged_association"
        )


def test_moving_window_pattern_reuses_the_recent_run_admissible_substrate() -> None:
    """`moving_window_pattern` gates on the family's recent-run substrate.

    Like the other single-series analytical questions (level-shift, smoothed
    pattern), the moving-window question reuses the family's recent-run rule as
    its *admissibility* substrate — that is the documented convention, and the
    rolling-mean tool (WP02) adds its own per-point coverage sufficiency on top.
    So on a recent-run family moving-window shares that substrate rule object
    rather than getting a bespoke per-metric rule (the guide-don't-enumerate
    guardrail). Its independence from the smoothed shape lives at the contract
    enum and tool layers, not in a divergent policy substrate.
    """
    saw = False
    for policy in BUILTIN_POLICIES:
        moving = policy.question_rules.get(QuestionType.MOVING_WINDOW_PATTERN)
        if moving is None:
            continue
        saw = True
        # The single-series analytical questions all share one substrate rule
        # object for the family; moving-window is one of them.
        level_shift = policy.question_rules.get(QuestionType.LEVEL_SHIFT_DETECTION)
        assert moving is level_shift, (
            f"{policy.metric_family} moving_window_pattern diverged from the "
            "recent-run analytical substrate"
        )
    assert saw


def _candidate(metric_family: str, **kwargs: object) -> EvidenceCandidate:
    default_metric_ids = {
        "activity": "steps",
        "sleep": "sleep_duration",
        "hrv_resting_recovery": "resting_hr",
        "cgm": "glucose_cgm",
    }
    defaults: dict[str, object] = {
        "metric_id": kwargs.pop(
            "metric_id", default_metric_ids.get(metric_family, f"{metric_family}_metric")
        ),
        "metric_family": metric_family,
        "value_kind": kwargs.pop("value_kind", "scalar"),
    }
    defaults.update(kwargs)
    return EvidenceCandidate(**defaults)  # type: ignore[arg-type]


def test_moving_window_pattern_admissible_on_a_recent_run_family() -> None:
    """A dense recent-pattern family admits a moving-window question with coverage."""
    registry = build_builtin_registry()
    candidate = _candidate(
        "activity",
        observed_at=NOW - timedelta(days=1),
        coverage_pct=95.0,
        point_count=30,
    )
    result = evaluate_evidence(
        QuestionType.MOVING_WINDOW_PATTERN,
        [candidate],
        registry.policies(),
        reference_time=NOW,
    )
    assert result.admissible_evidence
    assert result.admissible_evidence[0].status is EvidenceStatus.ADMISSIBLE


def test_paired_difference_refuses_when_family_has_no_rule() -> None:
    """An analytical question on a non-recent-run family refuses, never raises.

    A long-term-control family (e.g. A1C-like) declares no paired-difference rule,
    so the evaluator returns the established UNSUPPORTED_POLICY refusal path
    instead of throwing — proving the new vocabulary is gated, not crash-prone.
    """
    registry = build_builtin_registry()
    candidate = _candidate(
        "a1c_like_control",
        metric_id="hba1c",
        observed_at=NOW - timedelta(days=30),
    )
    result = evaluate_evidence(
        QuestionType.PAIRED_DIFFERENCE,
        [candidate],
        registry.policies(),
        reference_time=NOW,
    )
    assert not result.admissible_evidence
    assert result.refusal is not None
    assert RejectionReason.UNSUPPORTED_POLICY in result.rejected_evidence[0].rejection_reasons


def test_paired_difference_floor_is_a_positive_observation_count() -> None:
    """The shared paired floor is a positive, measurable observation count."""
    seen = False
    for policy in builtin_policies():
        rule = policy.question_rules.get(QuestionType.PAIRED_DIFFERENCE)
        if rule is None:
            continue
        seen = True
        assert isinstance(rule.sufficiency, SufficiencyRule)
        assert rule.sufficiency.min_observations is not None
        assert rule.sufficiency.min_observations > 0
    assert seen
