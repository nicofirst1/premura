# Data Model: Stage 2 Evidence Admissibility Foundation

## Overview

This mission adds a Stage 2 policy declaration model and evaluator result model. The goal is to guide future agents when they add new evidence behavior, not to enumerate every possible health policy.

The models below are conceptual planning entities. Implementation should use frozen Python dataclasses and closed enums exposed through `premura.engine` where appropriate.

## Entity: QuestionType

Represents the kind of question the evidence is being evaluated for.

Fields:

- `value`: closed enum value.

Initial values:

- `current_status`
- `recent_trend`
- `long_term_control`
- `historical_baseline`

Validation rules:

- Unknown values are programming errors.
- Adding a value requires a future mission because it changes the Stage 2 authoring contract.

## Entity: MetricFamilyPolicy

Represents one family-level policy declaration.

Fields:

- `policy_id`: stable identifier.
- `version`: positive integer.
- `metric_family`: stable family identifier.
- `applies_to_metrics`: optional metric identifiers or family descriptors.
- `policy_shape`: closed enum describing reusable evidence-rule shape.
- `temporal_meaning`: closed enum describing what time means for this evidence.
- `question_rules`: mapping from `QuestionType` to `QuestionRule`.
- `required_provenance`: required evidence fields, such as timestamp or source identity.
- `standing_caveats`: caveats that always travel with this family.
- `rationale`: short plain-English explanation for future agents and reviewers.
- `source_notes`: optional notes pointing to research or docs used during authoring.
- `examples`: positive examples for expected admissibility behavior.

Validation rules:

- `policy_id`, `metric_family`, `policy_shape`, and `temporal_meaning` are required.
- At least one `question_rules` entry is required.
- Every `question_rules` key must be a known `QuestionType`.
- Caveats must be present for method-sensitive or baseline-relative shapes.
- Declarations cannot contain expressions, operators, conditions, or callable hooks.

## Entity: QuestionRule

Represents how one metric family behaves for one question type.

Fields:

- `admissibility`: closed enum: `admissible`, `inadmissible`, `limited`, or `requires_evidence_check`.
- `freshness`: optional `FreshnessRule`.
- `sufficiency`: optional `SufficiencyRule`.
- `required_context`: required context fields for this question type.
- `default_rejection_reasons`: closed enum list.
- `refusal_mode`: closed enum describing how to refuse when evidence fails.
- `caveats`: question-specific caveats.

Validation rules:

- `inadmissible` rules must name at least one rejection reason.
- `admissible` and `limited` rules must specify how freshness and sufficiency are handled, even when the answer is "not applicable".
- Rules cannot override evaluator branching with custom logic.

## Entity: FreshnessRule

Represents recency parameters for a question rule.

Fields:

- `mode`: closed enum such as `strict_window`, `preferred_window`, `baseline_relative`, `caveat_only`, or `valid_until_superseded`.
- `max_age`: optional duration.
- `preferred_age`: optional duration.

Validation rules:

- `strict_window` requires `max_age`.
- `valid_until_superseded` must not use `max_age`.
- `caveat_only` must include caveat text through the parent rule or policy.

## Entity: SufficiencyRule

Represents minimum evidence density or coverage.

Fields:

- `min_observations`: optional positive integer.
- `min_span`: optional duration.
- `min_coverage_pct`: optional percentage.
- `missing_data_behavior`: closed enum such as `reject`, `caveat`, or `ignore_if_not_required`.

Validation rules:

- Percentages must be between 0 and 100.
- Empty sufficiency rules are allowed only when the question rule explicitly states that evidence density is not applicable.

## Entity: EvidenceCandidate

Represents one warehouse value or series being evaluated.

Fields:

- `metric_id`
- `metric_family`
- `observed_at` or effective timestamp when applicable
- `source_id` or source descriptor when known
- `value_kind`
- `point_count`
- `coverage_pct`
- `context`

Validation rules:

- Candidates missing required provenance can be evaluated only into rejected or insufficient outcomes.
- No candidate should be silently coerced into another semantic domain.

## Entity: EvidenceOutcome

Represents the evaluator's decision for one candidate.

Fields:

- `status`: closed enum: `admissible`, `rejected`, or `insufficient`.
- `question_type`
- `metric_family`
- `policy_id`
- `rejection_reasons`: closed enum list.
- `caveats`: structured caveats.
- `provenance`: preserved candidate provenance.
- `message`: short plain-English explanation.

Validation rules:

- `rejected` and `insufficient` outcomes require at least one reason.
- `admissible` outcomes preserve provenance and caveats.
- Messages must not contain diagnosis, treatment advice, medication advice, emergency guidance, or population-norm claims.

## Entity: EvaluationResult

Represents the full policy evaluation result for one request.

Fields:

- `question_type`
- `admissible_evidence`: list of `EvidenceOutcome`.
- `rejected_evidence`: list of `EvidenceOutcome`.
- `insufficient_evidence`: list of `EvidenceOutcome`.
- `refusal`: optional refusal outcome when nothing admissible remains.

Validation rules:

- If no admissible evidence remains, `refusal` is required.
- Admissible and rejected evidence must stay separate.

## Relationships

- One `MetricFamilyPolicy` has many `QuestionRule` entries.
- One `QuestionRule` may contain one `FreshnessRule` and one `SufficiencyRule`.
- One `EvidenceCandidate` is evaluated against one `MetricFamilyPolicy` and one `QuestionType`.
- One evaluation produces one `EvaluationResult` containing zero or more `EvidenceOutcome` entries.

## State Transitions

Candidate evidence transitions through:

1. Candidate selected from warehouse-backed Stage 2 code.
2. Candidate matched to a metric family policy.
3. Candidate evaluated for the selected question type.
4. Candidate becomes `admissible`, `rejected`, or `insufficient`.
5. If no candidate is admissible, the overall result becomes a refusal.
