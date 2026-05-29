---
work_package_id: WP02
title: Deterministic Evidence Evaluator
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
agent: "claude:opus:implementer:implementer"
shell_pid: "6606"
history:
- timestamp: '2026-05-29T11:59:19Z'
  agent: gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/policies/
execution_mode: code_change
owned_files:
- src/premura/engine/policies/_evaluator.py
- tests/test_engine_policy_evaluator.py
tags: []
---

# Work Package Prompt: WP02 - Deterministic Evidence Evaluator

## Implement Command

```bash
spec-kitty agent action implement WP02 --agent <name>
```

## Objective

Implement the deterministic evaluator that takes a question type, evidence candidates, and family-level policy declarations, then returns admissible, rejected, insufficient, and refusal outcomes. This WP depends on WP01's model contract.

## Context

Key rule: declarations are parameters only. The evaluator owns all branching.

The evaluator must not:

- read DuckDB directly
- call PubMed or any network service
- use external clinical references
- produce diagnosis, treatment advice, p-values, confidence intervals, or causal claims

## Owned Files

- `src/premura/engine/policies/_evaluator.py`
- `tests/test_engine_policy_evaluator.py`

Do not edit files outside this list.

## Subtasks

### T006: Implement Evaluator Entrypoint

Create `evaluate_evidence(...)` in `_evaluator.py`.

Expected inputs:

- a `QuestionType`
- one or more `EvidenceCandidate` values
- metric-family policy declarations or a mapping from family to policy

Expected output:

- an `EvaluationResult` containing separated admissible, rejected, and insufficient outcomes

Guidance:

- Keep the signature simple and testable.
- Accept explicit candidate data rather than querying the warehouse.
- Preserve input order where practical so output is deterministic.

### T007: Implement Freshness, Provenance, And Question-Type Decisions

Evaluate each candidate against the relevant `QuestionRule`.

Required behavior:

- Missing required timestamp or effective date produces `missing_timestamp` or `missing_required_context`.
- `inadmissible` question rules produce `wrong_evidence_kind` or the rule's configured rejection reason.
- `strict_window` rejects candidates older than the window for the question.
- `valid_until_superseded` does not apply a hard age cutoff.
- Policy family mismatch or absent policy produces `unsupported_policy`.

Guidance:

- Keep rejection reasons distinct.
- Do not collapse outcomes into a quality score.
- Do not infer clinical meaning from metric names.

### T008: Implement Sufficiency And Refusal Aggregation

Use `SufficiencyRule` to decide whether evidence is too sparse.

Required behavior:

- Candidate point count below `min_observations` becomes `insufficient` with `too_sparse`.
- Coverage below `min_coverage_pct`, when declared, becomes `insufficient` with `too_sparse`.
- If no admissible evidence remains, the `EvaluationResult` includes a refusal outcome/message.

Refusal messages must be plain English and non-diagnostic.

### T009: Add Evaluator Tests

Create `tests/test_engine_policy_evaluator.py`.

Required tests:

- Stale current-status candidate is rejected with `stale_for_question`.
- Sparse trend candidate is insufficient with `too_sparse`.
- Candidate missing timestamp is not admissible.
- Long-term-control marker is inadmissible for current status but admissible for long-term control when declared that way.
- Admissible and rejected outcomes are returned in separate lists.
- No admissible evidence creates a refusal.

### T010: Add Determinism Tests

Add a test proving repeated evaluation with identical inputs produces equal results.

Guidance:

- Avoid implicit `datetime.now()` inside the evaluator.
- If age calculation is needed, pass a reference time explicitly.

## Implementation Notes

The evaluator is the only place that decides how declaration parameters become outcomes. This is the main guardrail against a future policy mini-language.

Suggested evaluator shape:

- `evaluate_evidence(question_type, candidates, policies, *, reference_time)` returns `EvaluationResult`.
- Candidate family lookup is deterministic and explicit.
- If no policy exists for a candidate's family, return an `unsupported_policy` rejection or insufficiency outcome.
- Process candidates in input order and preserve that order in each output bucket.
- Build plain-English messages from fixed templates and declaration caveats.

Freshness guidance:

- `strict_window`: reject when `reference_time - observed_at > max_age`.
- `preferred_window`: admit if inside preferred window; if outside, apply caveat or configured limited behavior rather than pretending it is current.
- `baseline_relative`: require caveat text and evaluate sufficiency more than recency unless the rule also provides a window.
- `caveat_only`: never use as a silent pass; attach caveats.
- `valid_until_superseded`: do not reject for age alone, but still require required context.

Sufficiency guidance:

- Treat missing `point_count` as insufficient when a minimum observation count is declared.
- Treat missing `coverage_pct` as insufficient when a minimum coverage is declared.
- Preserve `too_sparse` separately from `stale_for_question`.

Refusal guidance:

- Overall refusal happens only after every candidate has been evaluated.
- Refusal should summarize why nothing was usable without hiding individual outcome details.
- Refusal message must be descriptive, not medical advice.

## Edge Cases To Cover

- Mixed input where one candidate is admissible and one is stale.
- All candidates rejected.
- All candidates insufficient.
- Candidate with a policy but no rule for the requested question type.
- Candidate with no policy.
- Candidate with required timestamp missing.
- Candidate exactly at the strict freshness boundary.

## Reviewer Checklist

- The evaluator is pure over supplied arguments.
- The evaluator never reaches into DuckDB or `hp.*` tables.
- Every negative outcome has at least one closed rejection reason.
- The refusal outcome is derived from the absence of admissible evidence, not from a hand-coded special case.
- Caveats remain structured strings on outcomes; downstream callers do not need to parse a paragraph to find reasons.
- The evaluator does not introduce new question types, result families, or clinical labels.

## Common Failure Modes

- Treating `preferred_window` as a hard rejection even when the declaration says caveat-only behavior.
- Letting a missing timestamp pass because the candidate has a value.
- Returning one combined list of outcomes and expecting callers to separate them.
- Generating messages with advice-like phrasing such as "you should" or "see a doctor".
- Using `datetime.now()` internally and making tests time-dependent.

## Suggested Test Names

- `test_strict_window_rejects_stale_current_status_candidate`
- `test_sparse_trend_candidate_is_insufficient`
- `test_missing_timestamp_is_not_admissible`
- `test_long_term_marker_differs_by_question_type`
- `test_admissible_and_rejected_evidence_are_separated`
- `test_no_admissible_evidence_returns_refusal`
- `test_identical_inputs_produce_identical_results`

## Definition Of Done

- All evaluator tests pass.
- Evaluator does not import DuckDB, MCP, PubMed, or network libraries.
- Rejection reasons remain machine-readable.
- Refusal path is test-covered.

## Branch Strategy

Planning/base branch: `master`.
Final merge target: `master`.
Implementation worktrees are allocated later per computed lane from `lanes.json`; do not create worktrees manually.

## Reviewer Guidance

Focus review on whether branching lives in the evaluator and whether declarations remain parameters-only. Check that every negative outcome preserves a distinct reason.

## Activity Log

- 2026-05-29T12:22:20Z – claude:opus:implementer:implementer – shell_pid=6606 – Started implementation via action command
