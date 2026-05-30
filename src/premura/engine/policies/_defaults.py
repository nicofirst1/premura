"""Built-in Stage 2 evidence-admissibility *defaults* (WP03).

These are Premura's local **admissibility defaults**, not clinical authority.
They decide which personal-health evidence is honest to use for which question
shape — they are not diagnostic rules, treatment guidance, or population norms.
The evaluator (WP02) owns all branching; everything here is declarative
parameters only (closed enum values, durations, counts, required provenance,
and plain-English caveat/rationale strings).

The point of this module is the *abstraction level*, not breadth: it covers a
broad set of named metric **family groups** by mapping them onto a much smaller
set of reusable :class:`PolicyShape` builders. Many families share one shape
(e.g. CGM, activity, and sleep are all rolling-recent-pattern families; A1C-like
and lipid-like markers are both integrated long-term-control families). Adding a
new family should usually mean *calling an existing shape builder with new
parameters*, never writing a fresh bespoke clinical rule table.

Rationale and ``source_notes`` are informational only. They point at
``docs/history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md`` and general
source anchors for review; the evaluator never reads them at runtime and they
never become evidence.

No YAML, no functions/expressions/SQL/network references live in a declaration.
"""

from __future__ import annotations

from datetime import timedelta

from premura.engine.policies._model import (
    Admissibility,
    EvidenceStatus,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    MissingDataBehavior,
    PolicyExample,
    PolicyShape,
    QuestionRule,
    QuestionType,
    RefusalMode,
    RejectionReason,
    SufficiencyRule,
    TemporalMeaning,
)

# Shared source anchor. Informational only — never read at runtime.
_RESEARCH = "docs/history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md"

# Conservative default raw paired-sample floor for the lagged-association
# (correlate) question, from CORRELATE_METHODOLOGY_RESEARCH.md Q3: below 20
# paired observations a correlation point estimate carries essentially no
# information and the band spans nearly the whole range, so the default refuses.
# This is the *raw* paired floor declared at the policy layer; the stricter
# effective-sample floor (N_eff >= 12) is an autocorrelation-corrected check the
# correlate tool enforces at compute time, not a declarative density parameter.
_LAGGED_ASSOCIATION_MIN_PAIRED = 20


def _lagged_association_rule(*, caveats: tuple[str, ...]) -> QuestionRule:
    """The shared, conservative default rule for the lagged-association question.

    A distinct rule — never the recent-trend rule object — so the paired-sample
    floor cannot be hidden behind a single-series threshold. It reuses the
    recent-run admissibility/freshness posture (a delayed-association hypothesis
    is still about a recent daily window) but adds its own paired-sample
    sufficiency. Declarative parameters only: the evaluator owns all branching.
    """
    return QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
        sufficiency=SufficiencyRule(
            min_observations=_LAGGED_ASSOCIATION_MIN_PAIRED,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
        required_context=("observed_at",),
        caveats=(
            *caveats,
            "A lagged association describes whether two of your own series tend "
            "to move together at a declared day-offset; it is not evidence that "
            "one causes the other, and a third factor could drive both.",
        ),
    )


# ---------------------------------------------------------------------------
# Reusable policy-shape builders
# ---------------------------------------------------------------------------
# Each builder is ONE reusable shape. Families pass family-specific parameters
# (name, example metrics, window/density thresholds, caveats); they do not get a
# bespoke hand-written rule each. There are deliberately *fewer* builders than
# families that call them (see the registry tests). This is the guardrail
# against a one-off clinical rule per metric.


def _assertion_until_superseded(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Stable, effective-dated profile facts.

    Valid until a newer assertion supersedes them — *not* "fresh until stale".
    Old age alone is not a rejection; missing an effective date is.
    """
    effective_dated = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.VALID_UNTIL_SUPERSEDED),
        required_context=("observed_at",),
        refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
    )
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.ASSERTION_UNTIL_SUPERSEDED,
        temporal_meaning=TemporalMeaning.EFFECTIVE_DATED,
        applies_to_metrics=applies_to_metrics,
        required_provenance=("source_id",),
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.HISTORICAL_BASELINE: effective_dated,
            # An effective-dated fact is reasonable context for "now" too; it is
            # not a measurement that expires.
            QuestionType.CURRENT_STATUS: effective_dated,
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.HISTORICAL_BASELINE,
                expected_status=EvidenceStatus.ADMISSIBLE,
                description=(
                    "An old but un-superseded profile fact is still usable as "
                    "baseline context; it is not rejected for age alone."
                ),
            ),
        ),
    )


def _point_in_time_acute(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    current_max_age: timedelta,
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Acute spot measures — point-in-time state that goes stale quickly.

    Admissible for current status only inside a strict recency window; usable as
    a "what was true then" historical point with a caveat once outside it.
    """
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.POINT_IN_TIME_ACUTE,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        applies_to_metrics=applies_to_metrics,
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=current_max_age),
                required_context=("observed_at",),
            ),
            QuestionType.HISTORICAL_BASELINE: QuestionRule(
                admissibility=Admissibility.LIMITED,
                freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
                required_context=("observed_at",),
                refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
                caveats=(
                    "A single spot reading describes one moment; treat it as a "
                    "historical point, not a stable level.",
                ),
            ),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.CURRENT_STATUS,
                expected_status=EvidenceStatus.REJECTED,
                description=(
                    "A spot measure older than the current-status window is "
                    "rejected as stale for a present-tense question."
                ),
                expected_rejection_reasons=(RejectionReason.STALE_FOR_QUESTION,),
            ),
        ),
    )


def _serial_average_short_run(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    current_max_age: timedelta,
    min_readings: int,
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Short-run serial averages (e.g. home blood pressure).

    A single reading is noisy; the honest unit is several readings over a short
    run. Current status needs both recency and enough readings.
    """
    serial_caveat = (
        "Read this as a short-run average of several readings, not as one isolated value.",
    )
    # A recent run of readings is the honest unit for trend and for the Stage 3
    # analytical tools (level-shift / smoothed pattern), so the analytical
    # questions reuse the recent-run admissibility rule. The tools layer adds its
    # own method-level sufficiency (e.g. observations on both sides of a split).
    recent_run_rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.PREFERRED_WINDOW, preferred_age=current_max_age),
        sufficiency=SufficiencyRule(
            min_observations=min_readings,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
        required_context=("observed_at",),
        caveats=serial_caveat,
    )
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.SERIAL_AVERAGE_SHORT_RUN,
        temporal_meaning=TemporalMeaning.SHORT_RUN_AVERAGE,
        applies_to_metrics=applies_to_metrics,
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=current_max_age),
                sufficiency=SufficiencyRule(
                    min_observations=min_readings,
                    missing_data_behavior=MissingDataBehavior.REJECT,
                ),
                required_context=("observed_at",),
                caveats=serial_caveat,
            ),
            QuestionType.RECENT_TREND: recent_run_rule,
            QuestionType.LEVEL_SHIFT_DETECTION: recent_run_rule,
            QuestionType.SMOOTHED_PATTERN: recent_run_rule,
            QuestionType.LAGGED_ASSOCIATION: _lagged_association_rule(caveats=serial_caveat),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.CURRENT_STATUS,
                expected_status=EvidenceStatus.INSUFFICIENT,
                description=(
                    "A single reading is insufficient for a current-status "
                    "answer; this family needs several readings."
                ),
                expected_rejection_reasons=(RejectionReason.TOO_SPARSE,),
            ),
        ),
    )


def _rolling_recent_pattern(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    current_max_age: timedelta,
    min_coverage_pct: float,
    rationale: str,
    source_notes: tuple[str, ...],
    extra_caveats: tuple[str, ...] = (),
) -> MetricFamilyPolicy:
    """Dense, high-frequency recent patterns (CGM, activity, sleep).

    Meaning comes from a recent window with enough coverage; a single day or a
    thin window can mislead, so current status requires coverage density.
    """
    coverage_caveat = (
        "This reflects a recent pattern over a window; gaps or non-wear can "
        "skew it, so read it as a pattern, not a single fact.",
        *extra_caveats,
    )
    # The recent windowed pattern is also the admissible substrate for the
    # Stage 3 analytical tools (level-shift / smoothed pattern); they reuse the
    # recent-trend rule and add their own method-level sufficiency on top.
    recent_pattern_rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.PREFERRED_WINDOW, preferred_age=current_max_age),
        sufficiency=SufficiencyRule(
            min_coverage_pct=min_coverage_pct,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
        required_context=("observed_at",),
        caveats=coverage_caveat,
    )
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        applies_to_metrics=applies_to_metrics,
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=current_max_age),
                sufficiency=SufficiencyRule(
                    min_coverage_pct=min_coverage_pct,
                    missing_data_behavior=MissingDataBehavior.REJECT,
                ),
                required_context=("observed_at",),
                caveats=coverage_caveat,
            ),
            QuestionType.RECENT_TREND: recent_pattern_rule,
            QuestionType.LEVEL_SHIFT_DETECTION: recent_pattern_rule,
            QuestionType.SMOOTHED_PATTERN: recent_pattern_rule,
            QuestionType.LAGGED_ASSOCIATION: _lagged_association_rule(caveats=coverage_caveat),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.CURRENT_STATUS,
                expected_status=EvidenceStatus.INSUFFICIENT,
                description=(
                    "Thin coverage over the recent window is insufficient: "
                    "non-wear must not be read as a real pattern."
                ),
                expected_rejection_reasons=(RejectionReason.TOO_SPARSE,),
            ),
        ),
    )


def _integrated_long_term_control(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    long_term_max_age: timedelta,
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Markers that integrate control over weeks/months (A1C-like, lipid-like).

    Honest for long-term control and historical baseline; explicitly *not*
    honest evidence for "what is happening right now", which it would misstate.
    """
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.INTEGRATED_LONG_TERM_CONTROL,
        temporal_meaning=TemporalMeaning.INTEGRATES_OVER_MONTHS,
        applies_to_metrics=applies_to_metrics,
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.INADMISSIBLE,
                default_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
                refusal_mode=RefusalMode.SUGGEST_DIFFERENT_QUESTION,
            ),
            QuestionType.LONG_TERM_CONTROL: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(
                    mode=FreshnessMode.PREFERRED_WINDOW, preferred_age=long_term_max_age
                ),
                required_context=("observed_at",),
            ),
            QuestionType.HISTORICAL_BASELINE: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
                required_context=("observed_at",),
                refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
            ),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.CURRENT_STATUS,
                expected_status=EvidenceStatus.REJECTED,
                description=(
                    "A long-horizon control marker is the wrong kind of "
                    "evidence for a present-tense question."
                ),
                expected_rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
            ),
            PolicyExample(
                question_type=QuestionType.LONG_TERM_CONTROL,
                expected_status=EvidenceStatus.ADMISSIBLE,
                description=(
                    "The same marker is admissible for a long-term-control "
                    "question, which is what it actually measures."
                ),
            ),
        ),
    )


def _baseline_relative(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    current_max_age: timedelta,
    standing_caveats: tuple[str, ...],
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Baseline-relative recent physiology (HRV, resting HR, recovery).

    Only meaningful relative to the operator's own baseline and context; weakly
    standardized, so it must always carry caveats (enforced by the model for
    this shape) and is read as deviation-from-baseline, never an absolute norm.
    """
    current_rule = QuestionRule(
        admissibility=Admissibility.LIMITED,
        freshness=FreshnessRule(mode=FreshnessMode.BASELINE_RELATIVE, max_age=current_max_age),
        required_context=("observed_at",),
        refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
    )
    relative_rule = QuestionRule(
        admissibility=Admissibility.LIMITED,
        freshness=FreshnessRule(mode=FreshnessMode.BASELINE_RELATIVE, max_age=current_max_age),
        required_context=("observed_at",),
        refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
    )
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.BASELINE_RELATIVE,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        applies_to_metrics=applies_to_metrics,
        standing_caveats=standing_caveats,
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.CURRENT_STATUS: current_rule,
            QuestionType.RECENT_TREND: relative_rule,
            # Baseline-relative recent physiology is the admissible substrate for
            # the Stage 3 analytical tools too; they reuse the deviation-from-
            # baseline rule (with its standing caveats) and add method-level
            # sufficiency on top.
            QuestionType.LEVEL_SHIFT_DETECTION: relative_rule,
            QuestionType.SMOOTHED_PATTERN: relative_rule,
            # Standing caveats (baseline-relative weakness) attach via the
            # evaluator; the rule adds the paired-sample floor and the
            # association-not-causation caveat.
            QuestionType.LAGGED_ASSOCIATION: _lagged_association_rule(caveats=()),
            QuestionType.HISTORICAL_BASELINE: QuestionRule(
                admissibility=Admissibility.LIMITED,
                freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
                required_context=("observed_at",),
                refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
            ),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.RECENT_TREND,
                expected_status=EvidenceStatus.ADMISSIBLE,
                description=(
                    "Recent baseline-relative physiology is admissible for a "
                    "deviation-from-baseline trend question, always with its "
                    "standing caveats attached."
                ),
            ),
        ),
    )


def _slow_trajectory_method_sensitive(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    current_max_age: timedelta,
    standing_caveats: tuple[str, ...],
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Slow-moving, method-sensitive trajectories (weight, body composition).

    Day-to-day noise and measurement method can mislead, so this shape always
    carries caveats (enforced by the model) and treats the slow trajectory, not
    a single reading, as the real signal.
    """
    trajectory_rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.PREFERRED_WINDOW, preferred_age=current_max_age),
        required_context=("observed_at",),
        refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
    )
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
        temporal_meaning=TemporalMeaning.SLOW_TRAJECTORY,
        applies_to_metrics=applies_to_metrics,
        standing_caveats=standing_caveats,
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.CURRENT_STATUS: QuestionRule(
                admissibility=Admissibility.LIMITED,
                freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=current_max_age),
                required_context=("observed_at",),
                refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
                caveats=(
                    "A single reading can reflect day-to-day noise; the slow "
                    "trajectory is the more honest signal.",
                ),
            ),
            QuestionType.RECENT_TREND: trajectory_rule,
            # The slow trajectory is the admissible substrate for the Stage 3
            # analytical tools too; they reuse the trend rule (with its
            # method-sensitivity caveats) and add method-level sufficiency.
            QuestionType.LEVEL_SHIFT_DETECTION: trajectory_rule,
            QuestionType.SMOOTHED_PATTERN: trajectory_rule,
            # Method-sensitivity standing caveats attach via the evaluator; the
            # rule adds the paired-sample floor and association-not-causation
            # caveat.
            QuestionType.LAGGED_ASSOCIATION: _lagged_association_rule(caveats=()),
            QuestionType.HISTORICAL_BASELINE: QuestionRule(
                admissibility=Admissibility.ADMISSIBLE,
                freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
                required_context=("observed_at",),
                refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
            ),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.RECENT_TREND,
                expected_status=EvidenceStatus.ADMISSIBLE,
                description=(
                    "Admissible for a slow-trajectory trend question, always "
                    "carrying its method-sensitivity caveats."
                ),
            ),
        ),
    )


def _sparse_lab_analyte_specific(
    *,
    policy_id: str,
    metric_family: str,
    applies_to_metrics: tuple[str, ...],
    min_observations: int,
    rationale: str,
    source_notes: tuple[str, ...],
) -> MetricFamilyPolicy:
    """Sparse lab panels whose meaning varies by analyte and collection context.

    Collection-time observations: honest for "what was true then" and for slow
    personal-baseline comparison, but trend questions need enough repeats, so
    sparse evidence is refused where density is required.
    """
    analyte_caveat = (
        "Interpretation depends on the specific analyte and the collection "
        "context; read this as analyte-specific, not a general status.",
    )
    # Sparse labs need enough repeats before a trend or analytical tool runs; the
    # same density-checked rule gates recent-trend and the Stage 3 analytical
    # tools (which add their own method-level minimums on top).
    repeats_required_rule = QuestionRule(
        admissibility=Admissibility.REQUIRES_EVIDENCE_CHECK,
        freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
        sufficiency=SufficiencyRule(
            min_observations=min_observations,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
        required_context=("observed_at",),
        refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
        caveats=analyte_caveat,
    )
    return MetricFamilyPolicy(
        policy_id=policy_id,
        version=1,
        metric_family=metric_family,
        policy_shape=PolicyShape.SPARSE_LAB_ANALYTE_SPECIFIC,
        temporal_meaning=TemporalMeaning.POINT_IN_TIME,
        applies_to_metrics=applies_to_metrics,
        required_provenance=("source_id",),
        rationale=rationale,
        source_notes=source_notes,
        question_rules={
            QuestionType.HISTORICAL_BASELINE: QuestionRule(
                admissibility=Admissibility.LIMITED,
                freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
                required_context=("observed_at",),
                refusal_mode=RefusalMode.OFFER_WITH_CAVEATS,
                caveats=analyte_caveat,
            ),
            QuestionType.RECENT_TREND: repeats_required_rule,
            QuestionType.LEVEL_SHIFT_DETECTION: repeats_required_rule,
            QuestionType.SMOOTHED_PATTERN: repeats_required_rule,
            QuestionType.LAGGED_ASSOCIATION: _lagged_association_rule(caveats=analyte_caveat),
        },
        examples=(
            PolicyExample(
                question_type=QuestionType.RECENT_TREND,
                expected_status=EvidenceStatus.INSUFFICIENT,
                description=(
                    "A lone sparse lab value is insufficient for a trend "
                    "question; reference-change thinking needs repeats."
                ),
                expected_rejection_reasons=(RejectionReason.TOO_SPARSE,),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Built-in family declarations (>=10 family groups across the 8 shapes above)
# ---------------------------------------------------------------------------
# Many families intentionally reuse the same shape. The number of distinct
# PolicyShape values used here is strictly less than the number of families.

BUILTIN_POLICIES: tuple[MetricFamilyPolicy, ...] = (
    # 1. Stable profile facts -> assertion_until_superseded
    _assertion_until_superseded(
        policy_id="builtin.stable_profile_facts.v1",
        metric_family="stable_profile_facts",
        applies_to_metrics=("date_of_birth", "biological_sex", "blood_type"),
        rationale=(
            "Profile facts are effective-dated context, valid until superseded "
            "by a newer assertion; age alone does not make them stale."
        ),
        source_notes=(f"{_RESEARCH} (metric-family table: 'Stable profile facts').",),
    ),
    # 2. Acute spot measures -> point_in_time_acute
    _point_in_time_acute(
        policy_id="builtin.acute_spot_measures.v1",
        metric_family="acute_spot_measures",
        applies_to_metrics=("body_temperature", "spo2_spot", "heart_rate_spot"),
        current_max_age=timedelta(hours=12),
        rationale=(
            "Spot vitals describe a single moment and go stale quickly; usable "
            "for current status only inside a short recency window."
        ),
        source_notes=(f"{_RESEARCH} (metric-family table: 'Acute spot measures').",),
    ),
    # 3. Home blood pressure -> serial_average_short_run
    _serial_average_short_run(
        policy_id="builtin.home_blood_pressure.v1",
        metric_family="home_blood_pressure",
        applies_to_metrics=("systolic_bp", "diastolic_bp"),
        current_max_age=timedelta(days=7),
        min_readings=3,
        rationale=(
            "Home blood pressure is honest as a short-run average of several "
            "readings; a single isolated reading is noisy."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'Home blood pressure'; "
            "ACC/AHA blood-pressure source anchor, used here only as a Premura "
            "admissibility default, not a clinical threshold).",
        ),
    ),
    # 4. CGM -> rolling_recent_pattern
    _rolling_recent_pattern(
        policy_id="builtin.cgm.v1",
        metric_family="cgm",
        applies_to_metrics=("glucose_cgm",),
        current_max_age=timedelta(days=1),
        min_coverage_pct=70.0,
        rationale=(
            "CGM is a high-frequency recent pattern; it needs enough recent "
            "wear coverage before it can describe current status or trend."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'CGM'; ATTD consensus source "
            "anchor on CGM interpretation, used as a Premura admissibility "
            "default only).",
        ),
    ),
    # 5. A1C-like long-term control -> integrated_long_term_control
    _integrated_long_term_control(
        policy_id="builtin.a1c_like_control.v1",
        metric_family="a1c_like_control",
        applies_to_metrics=("hba1c",),
        long_term_max_age=timedelta(days=120),
        rationale=(
            "An A1C-like marker integrates control over months; honest for "
            "long-term control, not for what is happening right now."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'A1C'; NIDDK source anchor, "
            "used as a Premura admissibility default only).",
        ),
    ),
    # 6. Lipids -> integrated_long_term_control (SAME shape as A1C)
    _integrated_long_term_control(
        policy_id="builtin.lipid_like_control.v1",
        metric_family="lipid_like_control",
        applies_to_metrics=("ldl_cholesterol", "hdl_cholesterol", "triglycerides"),
        long_term_max_age=timedelta(days=365),
        rationale=(
            "Lipids respond slowly and are a chronic-control/therapy-response "
            "marker; weak as a same-week signal, honest over weeks to months."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'Lipids'; ACC/AHA lipid source "
            "anchor, used as a Premura admissibility default only).",
        ),
    ),
    # 7. Sparse lab panels -> sparse_lab_analyte_specific
    _sparse_lab_analyte_specific(
        policy_id="builtin.sparse_lab_panels.v1",
        metric_family="sparse_lab_panels",
        applies_to_metrics=("vitamin_d", "ferritin", "tsh"),
        min_observations=2,
        rationale=(
            "Sparse lab panels are collection-time observations whose meaning "
            "varies by analyte; a single value cannot anchor a trend."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'Sparse lab panels'; "
            "lab-medicine biological-variation / reference-change source "
            "anchor).",
        ),
    ),
    # 8. Weight -> slow_trajectory_method_sensitive
    _slow_trajectory_method_sensitive(
        policy_id="builtin.weight.v1",
        metric_family="weight",
        applies_to_metrics=("body_weight",),
        current_max_age=timedelta(days=3),
        standing_caveats=(
            "Day-to-day weight is noisy (hydration, timing); the slow "
            "trajectory is the more honest signal.",
        ),
        rationale=(
            "Weight is current body mass plus a slow trajectory; day-to-day "
            "noise can mislead, so the trajectory carries the meaning."
        ),
        source_notes=(f"{_RESEARCH} (metric-family table: 'Weight').",),
    ),
    # 9. Body composition -> slow_trajectory_method_sensitive (SAME shape as weight)
    _slow_trajectory_method_sensitive(
        policy_id="builtin.body_composition.v1",
        metric_family="body_composition",
        applies_to_metrics=("body_fat_pct", "lean_mass"),
        current_max_age=timedelta(days=14),
        standing_caveats=(
            "Body-composition estimates are method-sensitive (e.g. impedance "
            "varies with hydration and device); compare like method with like.",
        ),
        rationale=(
            "Body composition is a slow-moving, method-sensitive phenotype; "
            "weak for short-horizon claims, honest as a longer trajectory."
        ),
        source_notes=(f"{_RESEARCH} (metric-family table: 'Body composition').",),
    ),
    # 10. Activity -> rolling_recent_pattern (SAME shape as CGM)
    _rolling_recent_pattern(
        policy_id="builtin.activity.v1",
        metric_family="activity",
        applies_to_metrics=("steps", "active_minutes", "exercise_minutes"),
        current_max_age=timedelta(days=7),
        min_coverage_pct=50.0,
        rationale=(
            "Activity is a recent behavior load read over a window (often a "
            "week); a single day can mislead."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'Activity metrics'; WHO "
            "physical-activity weekly-framing source anchor, used as a Premura "
            "admissibility default only).",
        ),
    ),
    # 11. Sleep -> rolling_recent_pattern (SAME shape as CGM/activity)
    _rolling_recent_pattern(
        policy_id="builtin.sleep.v1",
        metric_family="sleep",
        applies_to_metrics=("sleep_duration", "sleep_efficiency", "sleep_stages"),
        current_max_age=timedelta(days=3),
        min_coverage_pct=50.0,
        rationale=(
            "Sleep is a multi-night recent pattern; a single night can mislead "
            "and wearable scoring is not hard truth."
        ),
        source_notes=(f"{_RESEARCH} (metric-family table: 'Sleep metrics').",),
        extra_caveats=("Wearable sleep staging is an estimate, not a clinical sleep study.",),
    ),
    # 12. HRV / resting HR / recovery -> baseline_relative
    _baseline_relative(
        policy_id="builtin.hrv_resting_recovery.v1",
        metric_family="hrv_resting_recovery",
        applies_to_metrics=("hrv", "resting_hr", "recovery_score"),
        current_max_age=timedelta(days=2),
        standing_caveats=(
            "These are only meaningful relative to your own baseline and are "
            "weakly standardized; read as deviation-from-baseline, not an "
            "absolute level.",
        ),
        rationale=(
            "HRV/resting-HR/recovery are baseline-relative recent physiology; "
            "context-sensitive and weakly standardized across people."
        ),
        source_notes=(
            f"{_RESEARCH} (metric-family table: 'HRV / resting HR / recovery'; "
            "wearable-validity / digital-phenotyping source anchors).",
        ),
    ),
)


def builtin_policies() -> tuple[MetricFamilyPolicy, ...]:
    """Return the built-in family policies in deterministic declaration order.

    A function (not just the module constant) so callers have a stable,
    intention-revealing entrypoint; the underlying tuple is already immutable.
    """
    return BUILTIN_POLICIES


__all__ = ["BUILTIN_POLICIES", "builtin_policies"]
