"""Internal Stage 2 policy package surface.

Re-exports only the policy *model* types (closed vocabularies + frozen
declaration/result dataclasses) that WP02/WP03 build on. This is **not** the
top-level ``premura.engine`` public surface — that is owned by a later WP. No
registry, built-in declarations, or evaluator behavior live here yet.
"""

from __future__ import annotations

from premura.engine.policies._model import (
    CAVEAT_REQUIRED_SHAPES,
    Admissibility,
    EvaluationResult,
    EvidenceCandidate,
    EvidenceOutcome,
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

__all__ = [
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
    "FreshnessRule",
    "SufficiencyRule",
    "QuestionRule",
    "PolicyExample",
    "MetricFamilyPolicy",
    "EvidenceCandidate",
    "EvidenceOutcome",
    "EvaluationResult",
]
