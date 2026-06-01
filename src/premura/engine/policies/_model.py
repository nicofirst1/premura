"""Stage 2 evidence-admissibility policy declaration model.

This module defines the *shape* future agents fill in when they teach Premura
how a metric family's evidence may be used — it is **not** an enumeration of
every clinical policy Premura will ever need. The vocabulary is intentionally
small and closed:

* Closed :class:`enum.StrEnum` vocabularies (consistent with
  ``premura.engine._results``) — no arbitrary string passthrough.
* Frozen dataclass *declarations* (``MetricFamilyPolicy`` and friends) that are
  parameters only: closed enum values, duration/count thresholds, required
  provenance fields, caveat strings, and examples. No callables, expressions,
  or conditionals live in a declaration; the evaluator (a later WP) owns all
  branching.
* Frozen dataclass *results* (``EvidenceOutcome``, ``EvaluationResult``) that
  keep admissible evidence separate from rejected/insufficient evidence and
  preserve provenance and machine-readable rejection reasons.

Validation is lightweight and construction-time (``__post_init__``): it catches
the declaration mistakes a future agent is most likely to make, with messages
specific enough to fix the declaration from the exception text. There is no
JSON Schema, Pydantic model, OPA, or policy-engine dependency here, and this
module reads nothing from the warehouse and makes no network calls.

This is an *internal* package surface for WP02/WP03. The top-level
``premura.engine`` public surface is owned by a later WP.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any, TypeVar

_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _require_enum(value: object, enum_type: type[_EnumT], field_name: str) -> _EnumT:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must be a {enum_type.__name__} value, got {value!r}")
    return value


def _require_timedelta_or_none(value: object, field_name: str) -> timedelta | None:
    if value is not None and not isinstance(value, timedelta):
        raise ValueError(f"{field_name} must be a timedelta or None, got {value!r}")
    return value


def _require_tuple_of_str(values: tuple[object, ...], field_name: str) -> tuple[str, ...]:
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} entries must be strings, got {value!r}")
        if not value.strip():
            raise ValueError(f"{field_name} must not contain empty strings")
    return values  # type: ignore[return-value]


def _require_tuple_of_enum(
    values: tuple[object, ...],
    enum_type: type[_EnumT],
    field_name: str,
) -> tuple[_EnumT, ...]:
    for value in values:
        _require_enum(value, enum_type, f"{field_name} entry")
    return values  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------
# These are closed by design. Adding a value changes the Stage 2/3 authoring
# contract and is a reviewed change (see evidence-policy-contract.md). The first
# four are the Stage 2 descriptive question shapes; the last two are the reviewed
# Stage 3 *analytical* question types added by the analytical-tools mission
# (research note D4) so analytical admissibility is declared as a first-class
# question type rather than smuggled onto a descriptive shape.


class QuestionType(StrEnum):
    """The kind of analytical question evidence is being evaluated for."""

    CURRENT_STATUS = "current_status"
    RECENT_TREND = "recent_trend"
    LONG_TERM_CONTROL = "long_term_control"
    HISTORICAL_BASELINE = "historical_baseline"
    # Stage 3 analytical question types (research note D4). A metric family opts
    # into analytical tools by declaring a QuestionRule for these, with its own
    # freshness/sufficiency — never by reusing a descriptive rule implicitly.
    LEVEL_SHIFT_DETECTION = "level_shift_detection"
    SMOOTHED_PATTERN = "smoothed_pattern"
    # Multi-input Stage 3 analytical question (correlate mission, ADR-0008): a
    # pre-registered, directional, integer-day lagged *association* between two
    # daily series. Its rule carries its OWN paired-sample sufficiency (a raw
    # paired floor); it is never collapsed onto recent_trend or a single-series
    # analytical question, which would hide that correlation-specific floor.
    LAGGED_ASSOCIATION = "lagged_association"
    # Stage 3 analytical questions added by the finish-analytical-tool-set
    # mission. Each is a first-class, closed, reviewed value with its OWN rule —
    # never an implicit reuse of a descriptive or other analytical shape.
    #
    #   MOVING_WINDOW_PATTERN: rolling_mean's declared trailing moving-window
    #   summary over one ordered series. Distinct from SMOOTHED_PATTERN because it
    #   emits a coverage-bearing *series* of window points, not a single smoothed
    #   level, so it carries its own per-point coverage sufficiency.
    #
    #   PAIRED_DIFFERENCE: paired_t_test's simple anchor-date before/after paired
    #   comparison over one operator's series. Distinct from LAGGED_ASSOCIATION
    #   because it carries a raw *pair* floor over matched observations, not a
    #   two-series association floor. "Simple anchor-date pairing" is the reviewed
    #   meaning here; broader condition/event pairing is a later reviewed value.
    MOVING_WINDOW_PATTERN = "moving_window_pattern"
    PAIRED_DIFFERENCE = "paired_difference"


class EvidenceStatus(StrEnum):
    """The evaluator's verdict for a single evidence candidate."""

    ADMISSIBLE = "admissible"
    REJECTED = "rejected"
    INSUFFICIENT = "insufficient"


class RejectionReason(StrEnum):
    """Machine-readable reasons evidence is rejected or insufficient.

    These stay distinct (per CR-005): a generic quality score is not enough.
    """

    STALE_FOR_QUESTION = "stale_for_question"
    TOO_SPARSE = "too_sparse"
    MISSING_TIMESTAMP = "missing_timestamp"
    MISSING_REQUIRED_CONTEXT = "missing_required_context"
    WRONG_EVIDENCE_KIND = "wrong_evidence_kind"
    UNSUPPORTED_POLICY = "unsupported_policy"


class FreshnessMode(StrEnum):
    """How recency is judged for a question rule."""

    STRICT_WINDOW = "strict_window"
    PREFERRED_WINDOW = "preferred_window"
    BASELINE_RELATIVE = "baseline_relative"
    CAVEAT_ONLY = "caveat_only"
    VALID_UNTIL_SUPERSEDED = "valid_until_superseded"


class Admissibility(StrEnum):
    """How a family behaves for a given question type."""

    ADMISSIBLE = "admissible"
    INADMISSIBLE = "inadmissible"
    LIMITED = "limited"
    REQUIRES_EVIDENCE_CHECK = "requires_evidence_check"


class TemporalMeaning(StrEnum):
    """What "time" means for a family's evidence — separate from freshness.

    e.g. an A1C-like marker *integrates over months*, a spot vital is
    *point-in-time*, and a stable profile fact is *effective-dated* (valid
    until a newer assertion supersedes it).
    """

    POINT_IN_TIME = "point_in_time"
    SHORT_RUN_AVERAGE = "short_run_average"
    ROLLING_RECENT_PATTERN = "rolling_recent_pattern"
    INTEGRATES_OVER_MONTHS = "integrates_over_months"
    SLOW_TRAJECTORY = "slow_trajectory"
    EFFECTIVE_DATED = "effective_dated"


class PolicyShape(StrEnum):
    """Reusable evidence-rule shape a family is assigned to.

    A small set of shared shapes (not one bespoke rule per metric) that many
    families map onto. Names are implementation-facing; user-facing prose stays
    plain English. ``SLOW_TRAJECTORY_METHOD_SENSITIVE`` and ``BASELINE_RELATIVE``
    are "caveat-required" shapes (see :data:`CAVEAT_REQUIRED_SHAPES`).
    """

    ASSERTION_UNTIL_SUPERSEDED = "assertion_until_superseded"
    POINT_IN_TIME_ACUTE = "point_in_time_acute"
    SERIAL_AVERAGE_SHORT_RUN = "serial_average_short_run"
    ROLLING_RECENT_PATTERN = "rolling_recent_pattern"
    INTEGRATED_LONG_TERM_CONTROL = "integrated_long_term_control"
    BASELINE_RELATIVE = "baseline_relative"
    SLOW_TRAJECTORY_METHOD_SENSITIVE = "slow_trajectory_method_sensitive"
    SPARSE_LAB_ANALYTE_SPECIFIC = "sparse_lab_analyte_specific"


class MissingDataBehavior(StrEnum):
    """What a sufficiency rule does when evidence density is below threshold."""

    REJECT = "reject"
    CAVEAT = "caveat"
    IGNORE_IF_NOT_REQUIRED = "ignore_if_not_required"


class RefusalMode(StrEnum):
    """How the evaluator refuses when evidence fails a question rule."""

    REFUSE_WITH_REASON = "refuse_with_reason"
    OFFER_WITH_CAVEATS = "offer_with_caveats"
    SUGGEST_DIFFERENT_QUESTION = "suggest_different_question"


# Policy shapes whose results must always carry standing caveats because the
# underlying evidence is method-sensitive or only meaningful relative to a
# baseline. Used by :class:`MetricFamilyPolicy` validation.
CAVEAT_REQUIRED_SHAPES: frozenset[PolicyShape] = frozenset(
    {
        PolicyShape.BASELINE_RELATIVE,
        PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
    }
)


# ---------------------------------------------------------------------------
# Declaration dataclasses (authored by agents)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreshnessRule:
    """Recency parameters for one question rule.

    ``max_age`` / ``preferred_age`` are durations, never parsed strings — the
    declaration layer accepts ``timedelta | None`` directly.
    """

    mode: FreshnessMode
    max_age: timedelta | None = None
    preferred_age: timedelta | None = None

    def __post_init__(self) -> None:
        _require_enum(self.mode, FreshnessMode, "FreshnessRule.mode")
        _require_timedelta_or_none(self.max_age, "FreshnessRule.max_age")
        _require_timedelta_or_none(self.preferred_age, "FreshnessRule.preferred_age")
        if self.mode is FreshnessMode.STRICT_WINDOW and self.max_age is None:
            raise ValueError("FreshnessRule: strict_window requires max_age (a timedelta)")
        if self.mode is FreshnessMode.VALID_UNTIL_SUPERSEDED and self.max_age is not None:
            raise ValueError(
                "FreshnessRule: valid_until_superseded must not use max_age; "
                "effective-dated evidence is valid until a newer assertion "
                "supersedes it, not until a timestamp window expires"
            )
        for name, value in (("max_age", self.max_age), ("preferred_age", self.preferred_age)):
            if value is not None and value <= timedelta(0):
                raise ValueError(f"FreshnessRule: {name} must be a positive duration")


@dataclass(frozen=True)
class SufficiencyRule:
    """Minimum evidence density or coverage for one question rule."""

    min_observations: int | None = None
    min_span: timedelta | None = None
    min_coverage_pct: float | None = None
    missing_data_behavior: MissingDataBehavior = MissingDataBehavior.IGNORE_IF_NOT_REQUIRED

    def __post_init__(self) -> None:
        _require_enum(
            self.missing_data_behavior,
            MissingDataBehavior,
            "SufficiencyRule.missing_data_behavior",
        )
        _require_timedelta_or_none(self.min_span, "SufficiencyRule.min_span")
        if self.min_observations is not None and self.min_observations <= 0:
            raise ValueError("SufficiencyRule: min_observations must be positive")
        if self.min_span is not None and self.min_span <= timedelta(0):
            raise ValueError("SufficiencyRule: min_span must be a positive duration")
        if self.min_coverage_pct is not None and not (0.0 <= self.min_coverage_pct <= 100.0):
            raise ValueError("SufficiencyRule: min_coverage_pct must be between 0 and 100")


@dataclass(frozen=True)
class QuestionRule:
    """How one metric family behaves for one question type.

    Repeated immutable fields are tuples so the declaration stays hashable and
    cannot be mutated after construction.
    """

    admissibility: Admissibility
    freshness: FreshnessRule | None = None
    sufficiency: SufficiencyRule | None = None
    required_context: tuple[str, ...] = ()
    default_rejection_reasons: tuple[RejectionReason, ...] = ()
    refusal_mode: RefusalMode = RefusalMode.REFUSE_WITH_REASON
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.admissibility, Admissibility, "QuestionRule.admissibility")
        if self.freshness is not None and not isinstance(self.freshness, FreshnessRule):
            raise ValueError("QuestionRule.freshness must be a FreshnessRule or None")
        if self.sufficiency is not None and not isinstance(self.sufficiency, SufficiencyRule):
            raise ValueError("QuestionRule.sufficiency must be a SufficiencyRule or None")
        _require_tuple_of_str(self.required_context, "QuestionRule.required_context")
        _require_tuple_of_enum(
            self.default_rejection_reasons,
            RejectionReason,
            "QuestionRule.default_rejection_reasons",
        )
        _require_enum(self.refusal_mode, RefusalMode, "QuestionRule.refusal_mode")
        _require_tuple_of_str(self.caveats, "QuestionRule.caveats")
        if self.admissibility is Admissibility.INADMISSIBLE and not self.default_rejection_reasons:
            raise ValueError(
                "QuestionRule: an inadmissible rule must name at least one "
                "default rejection reason so the evaluator can explain the "
                "refusal"
            )


@dataclass(frozen=True)
class PolicyExample:
    """A positive/negative example proving expected admissibility behavior.

    Examples are part of the contract (CR-006). They are descriptive data a
    future test can execute against, not executable predicates.
    """

    question_type: QuestionType
    expected_status: EvidenceStatus
    description: str
    expected_rejection_reasons: tuple[RejectionReason, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.question_type, QuestionType, "PolicyExample.question_type")
        _require_enum(self.expected_status, EvidenceStatus, "PolicyExample.expected_status")
        _require_tuple_of_enum(
            self.expected_rejection_reasons,
            RejectionReason,
            "PolicyExample.expected_rejection_reasons",
        )
        if not self.description.strip():
            raise ValueError("PolicyExample: description must not be empty")
        if (
            self.expected_status in (EvidenceStatus.REJECTED, EvidenceStatus.INSUFFICIENT)
            and not self.expected_rejection_reasons
        ):
            raise ValueError(
                "PolicyExample: a rejected/insufficient example must name its "
                "expected rejection reason(s)"
            )


@dataclass(frozen=True)
class MetricFamilyPolicy:
    """One family-level policy declaration.

    Describes a metric family (CR-001): which question types it can honestly
    support, what time means for its evidence, what provenance is required, and
    what caveats always travel with it. It must not become a one-off branch per
    metric; the evaluator owns branching.
    """

    policy_id: str
    version: int
    metric_family: str
    policy_shape: PolicyShape
    temporal_meaning: TemporalMeaning
    question_rules: Mapping[QuestionType, QuestionRule]
    applies_to_metrics: tuple[str, ...] = ()
    required_provenance: tuple[str, ...] = ()
    standing_caveats: tuple[str, ...] = ()
    rationale: str = ""
    source_notes: tuple[str, ...] = ()
    examples: tuple[PolicyExample, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.policy_shape, PolicyShape, "MetricFamilyPolicy.policy_shape")
        _require_enum(self.temporal_meaning, TemporalMeaning, "MetricFamilyPolicy.temporal_meaning")
        _require_tuple_of_str(self.applies_to_metrics, "MetricFamilyPolicy.applies_to_metrics")
        _require_tuple_of_str(self.required_provenance, "MetricFamilyPolicy.required_provenance")
        _require_tuple_of_str(self.standing_caveats, "MetricFamilyPolicy.standing_caveats")
        _require_tuple_of_str(self.source_notes, "MetricFamilyPolicy.source_notes")
        for example in self.examples:
            if not isinstance(example, PolicyExample):
                raise ValueError(
                    "MetricFamilyPolicy.examples entries must be PolicyExample values, "
                    f"got {example!r}"
                )
        if not self.policy_id.strip():
            raise ValueError("MetricFamilyPolicy: policy_id must not be empty")
        if not self.metric_family.strip():
            raise ValueError("MetricFamilyPolicy: metric_family must not be empty")
        if self.version <= 0:
            raise ValueError("MetricFamilyPolicy: version must be a positive integer")
        if not self.question_rules:
            raise ValueError("MetricFamilyPolicy: at least one question_rules entry is required")
        for key in self.question_rules:
            if not isinstance(key, QuestionType):
                raise ValueError(
                    "MetricFamilyPolicy: every question_rules key must be a "
                    f"QuestionType, got {key!r}"
                )
        if self.policy_shape in CAVEAT_REQUIRED_SHAPES and not self.standing_caveats:
            raise ValueError(
                f"MetricFamilyPolicy: policy_shape {self.policy_shape.value!r} is "
                "method-sensitive/baseline-relative and must carry at least one "
                "standing caveat"
            )
        # Freeze the mapping so the declaration cannot be mutated after build.
        object.__setattr__(self, "question_rules", dict(self.question_rules))


# ---------------------------------------------------------------------------
# Evaluation dataclasses (produced by the evaluator in a later WP)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceCandidate:
    """One warehouse value or series being considered for use.

    This is an input to the (later-WP) evaluator. It carries no warehouse-read
    behavior itself — it is the data the evaluator inspects.
    """

    metric_id: str
    metric_family: str
    value_kind: str
    observed_at: Any | None = None
    source_id: str | None = None
    point_count: int | None = None
    coverage_pct: float | None = None
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.observed_at is not None and not hasattr(self.observed_at, "__sub__"):
            raise ValueError("EvidenceCandidate.observed_at must be datetime-like or None")
        if self.source_id is not None and not isinstance(self.source_id, str):
            raise ValueError("EvidenceCandidate.source_id must be a string or None")
        if not isinstance(self.context, Mapping):
            raise ValueError("EvidenceCandidate.context must be a mapping")
        if not self.metric_id.strip():
            raise ValueError("EvidenceCandidate: metric_id must not be empty")
        if not self.metric_family.strip():
            raise ValueError("EvidenceCandidate: metric_family must not be empty")
        if self.point_count is not None and self.point_count < 0:
            raise ValueError("EvidenceCandidate: point_count must not be negative")
        if self.coverage_pct is not None and not (0.0 <= self.coverage_pct <= 100.0):
            raise ValueError("EvidenceCandidate: coverage_pct must be between 0 and 100")
        object.__setattr__(self, "context", dict(self.context))


@dataclass(frozen=True)
class EvidenceOutcome:
    """The evaluator's decision for one candidate.

    Keeps a machine-readable status plus distinct rejection reasons and
    preserved provenance, so downstream surfaces never have to parse prose.
    """

    status: EvidenceStatus
    question_type: QuestionType
    metric_family: str
    policy_id: str
    message: str
    rejection_reasons: tuple[RejectionReason, ...] = ()
    caveats: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_enum(self.status, EvidenceStatus, "EvidenceOutcome.status")
        _require_enum(self.question_type, QuestionType, "EvidenceOutcome.question_type")
        _require_tuple_of_enum(
            self.rejection_reasons,
            RejectionReason,
            "EvidenceOutcome.rejection_reasons",
        )
        _require_tuple_of_str(self.caveats, "EvidenceOutcome.caveats")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("EvidenceOutcome.provenance must be a mapping")
        if not self.message.strip():
            raise ValueError("EvidenceOutcome: message must not be empty")
        if (
            self.status in (EvidenceStatus.REJECTED, EvidenceStatus.INSUFFICIENT)
            and not self.rejection_reasons
        ):
            raise ValueError(
                f"EvidenceOutcome: a {self.status.value} outcome must name at "
                "least one rejection reason (a generic 'failed' is not enough)"
            )
        object.__setattr__(self, "provenance", dict(self.provenance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "question_type": self.question_type.value,
            "metric_family": self.metric_family,
            "policy_id": self.policy_id,
            "message": self.message,
            "rejection_reasons": [r.value for r in self.rejection_reasons],
            "caveats": list(self.caveats),
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class EvaluationResult:
    """The full policy evaluation result for one request.

    Admissible evidence stays separate from rejected and insufficient evidence.
    A refusal outcome (representable as data, not prose) is required whenever no
    admissible evidence remains.
    """

    question_type: QuestionType
    admissible_evidence: tuple[EvidenceOutcome, ...] = ()
    rejected_evidence: tuple[EvidenceOutcome, ...] = ()
    insufficient_evidence: tuple[EvidenceOutcome, ...] = ()
    refusal: EvidenceOutcome | None = None

    def __post_init__(self) -> None:
        _require_enum(self.question_type, QuestionType, "EvaluationResult.question_type")
        for field_name, outcomes in (
            ("admissible_evidence", self.admissible_evidence),
            ("rejected_evidence", self.rejected_evidence),
            ("insufficient_evidence", self.insufficient_evidence),
        ):
            for outcome in outcomes:
                if not isinstance(outcome, EvidenceOutcome):
                    raise ValueError(
                        f"EvaluationResult.{field_name} entries must be EvidenceOutcome values, "
                        f"got {outcome!r}"
                    )
        if self.refusal is not None and not isinstance(self.refusal, EvidenceOutcome):
            raise ValueError("EvaluationResult.refusal must be an EvidenceOutcome or None")
        if not self.admissible_evidence and self.refusal is None:
            raise ValueError(
                "EvaluationResult: a refusal outcome is required when no "
                "admissible evidence remains"
            )
        for outcome in self.admissible_evidence:
            if outcome.status is not EvidenceStatus.ADMISSIBLE:
                raise ValueError(
                    "EvaluationResult: admissible_evidence may only contain admissible outcomes"
                )
        for outcome in self.rejected_evidence:
            if outcome.status is not EvidenceStatus.REJECTED:
                raise ValueError(
                    "EvaluationResult: rejected_evidence may only contain rejected outcomes"
                )
        for outcome in self.insufficient_evidence:
            if outcome.status is not EvidenceStatus.INSUFFICIENT:
                raise ValueError(
                    "EvaluationResult: insufficient_evidence may only contain insufficient outcomes"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type.value,
            "admissible_evidence": [o.to_dict() for o in self.admissible_evidence],
            "rejected_evidence": [o.to_dict() for o in self.rejected_evidence],
            "insufficient_evidence": [o.to_dict() for o in self.insufficient_evidence],
            "refusal": self.refusal.to_dict() if self.refusal is not None else None,
        }


__all__ = [
    # Closed vocabularies
    "QuestionType",
    "EvidenceStatus",
    "RejectionReason",
    "FreshnessMode",
    "Admissibility",
    "TemporalMeaning",
    "PolicyShape",
    "MissingDataBehavior",
    "RefusalMode",
    "CAVEAT_REQUIRED_SHAPES",
    # Declarations
    "FreshnessRule",
    "SufficiencyRule",
    "QuestionRule",
    "PolicyExample",
    "MetricFamilyPolicy",
    # Evaluation
    "EvidenceCandidate",
    "EvidenceOutcome",
    "EvaluationResult",
]
