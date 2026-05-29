---
work_package_id: WP01
title: Policy Declaration Contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master.
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- timestamp: '2026-05-29T11:59:19Z'
  agent: gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/policies/
execution_mode: code_change
owned_files:
- src/premura/engine/policies/__init__.py
- src/premura/engine/policies/_model.py
- tests/test_engine_policy_model.py
tags: []
---

# Work Package Prompt: WP01 - Policy Declaration Contract

## Implement Command

```bash
spec-kitty agent action implement WP01 --agent <name>
```

## Objective

Create the Stage 2 policy declaration model: closed enums plus frozen dataclasses that future agents will use to declare evidence-admissibility behavior. This WP is model-only. Do not implement evaluator branching, built-in defaults, or public top-level `premura.engine` exports here.

## Context

Authoritative inputs:

- `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/spec.md`
- `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/plan.md`
- `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/data-model.md`
- `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/contracts/evidence-policy-contract.md`

Core design decisions:

- Frozen Python dataclasses, not YAML.
- Closed vocabularies, not open-ended strings.
- Declarations are parameters only.
- Validation is lightweight and construction-time.
- No PubMed, network, SQL, or evaluator behavior in this WP.

## Owned Files

- `src/premura/engine/policies/__init__.py`
- `src/premura/engine/policies/_model.py`
- `tests/test_engine_policy_model.py`

Do not edit files outside this list.

## Subtasks

### T001: Define Closed Policy Enums

Add closed enum types in `src/premura/engine/policies/_model.py`.

Required initial vocabularies:

- `QuestionType`: `current_status`, `recent_trend`, `long_term_control`, `historical_baseline`
- `EvidenceStatus`: `admissible`, `rejected`, `insufficient`
- `RejectionReason`: `stale_for_question`, `too_sparse`, `missing_timestamp`, `missing_required_context`, `wrong_evidence_kind`, `unsupported_policy`
- `FreshnessMode`: `strict_window`, `preferred_window`, `baseline_relative`, `caveat_only`, `valid_until_superseded`
- `Admissibility`: `admissible`, `inadmissible`, `limited`, `requires_evidence_check`
- Add compact enums for `TemporalMeaning` and `PolicyShape` using the planning docs as the source of names.

Guidance:

- Prefer `StrEnum`, consistent with `_results.py`.
- Do not allow arbitrary string passthrough.
- Keep names stable and plain.

### T002: Add Frozen Dataclasses

Add frozen dataclasses for the conceptual entities in `data-model.md`.

Required classes:

- `FreshnessRule`
- `SufficiencyRule`
- `QuestionRule`
- `PolicyExample`
- `MetricFamilyPolicy`
- `EvidenceCandidate`
- `EvidenceOutcome`
- `EvaluationResult`

Guidance:

- Keep fields close to `data-model.md`.
- Use standard Python types and `datetime.timedelta` for durations.
- Include `to_dict()` only where needed for observable result tests. Do not overbuild serialization.
- Do not make these classes responsible for warehouse reads.

### T003: Implement Lightweight Validation

Use `__post_init__` validation or helper validation functions.

Required validation examples:

- `strict_window` requires `max_age`.
- `valid_until_superseded` must not use `max_age`.
- `inadmissible` rules require at least one rejection reason.
- `rejected` and `insufficient` outcomes require at least one reason.
- `EvaluationResult` requires a refusal outcome when there are no admissible outcomes.
- Method-sensitive or baseline-relative policy shapes must include standing caveats.

Do not add a JSON Schema, Pydantic model, OPA, or any policy-engine dependency.

### T004: Expose Internal Package Surface

Create `src/premura/engine/policies/__init__.py` to re-export only the model types needed by WP02/WP03.

Important:

- This is not the top-level `premura.engine` public surface yet.
- WP04 owns top-level exports.
- Keep imports lazy and lightweight.

### T005: Add Model-Level Tests

Create `tests/test_engine_policy_model.py`.

Required tests:

- Valid minimal policy declaration constructs successfully.
- Invalid strict-window freshness without `max_age` fails.
- `valid_until_superseded` with `max_age` fails.
- Inadmissible question rule without rejection reasons fails.
- Rejected outcome without rejection reason fails.
- Evaluation result with no admissible evidence and no refusal fails.
- Caveat-required policy shapes fail when caveats are missing.

Test through imports from `premura.engine.policies`, not private module paths unless necessary for package-internal validation.

## Implementation Notes

Keep the model vocabulary intentionally small. This WP defines the shape future agents fill in; it does not define every clinical policy Premura will ever need.

Suggested modeling details:

- Use `@dataclass(frozen=True)` for every declaration/result class.
- Use tuples for repeated immutable fields where practical, especially caveats, examples, and rejection reasons.
- Accept `timedelta | None` for duration fields rather than parsing strings in this layer.
- Keep messages as plain strings but validate that required message/caveat fields are not empty when needed.
- Make validation errors specific enough that a future agent can fix the declaration from the exception message.

Validation should prevent common agent mistakes:

- Empty `policy_id` or `metric_family`.
- `QuestionRule(admissibility=INADMISSIBLE)` with no rejection reason.
- `EvidenceOutcome(status=REJECTED)` with no rejection reason.
- `EvaluationResult(admissible_evidence=(), refusal=None)` when rejected or insufficient evidence exists.
- A freshness rule that combines mutually exclusive semantics.

Do not add behavior that belongs to later WPs:

- No policy registry.
- No candidate evaluation.
- No built-in metric-family declarations.
- No top-level `premura.engine` exports.
- No warehouse reads.

## Edge Cases To Cover

- A policy can intentionally mark a question type as inadmissible.
- A profile fact can use valid-until-superseded freshness without a timestamp-style max age.
- A method-sensitive policy shape must carry caveats.
- An insufficient outcome must name why it is insufficient, not just that it failed.
- A refusal outcome should be representable as data without requiring downstream prose parsing.

## Suggested Test Names

- `test_valid_metric_family_policy_constructs`
- `test_strict_window_requires_max_age`
- `test_valid_until_superseded_rejects_max_age`
- `test_inadmissible_question_rule_requires_rejection_reason`
- `test_rejected_outcome_requires_rejection_reason`
- `test_evaluation_without_admissible_evidence_requires_refusal`
- `test_method_sensitive_policy_requires_caveat`

## Definition Of Done

- All owned tests pass.
- No third-party dependencies added.
- No top-level `premura.engine` exports changed.
- No evaluator logic implemented.
- New model code is type-annotated and frozen where appropriate.

## Branch Strategy

Planning/base branch: `master`.
Final merge target: `master`.
Implementation worktrees are allocated later per computed lane from `lanes.json`; do not create worktrees manually.

## Reviewer Guidance

Review that the model is bounded but not over-enumerated. The safe action for future agents should be to fill these dataclasses, not invent policy logic.
