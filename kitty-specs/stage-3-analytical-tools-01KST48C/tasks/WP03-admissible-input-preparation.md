---
work_package_id: WP03
title: Admissible Input Preparation
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-004
- FR-011
planning_base_branch: master
merge_target_branch: master
branch_strategy: 'Current branch at workflow start: master. Planning/base branch for this feature: master. Completed changes must merge into master.'
subtasks:
- T009
- T010
- T011
- T012
history:
- 2026-05-29T15:18:42Z tasks generated
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_inputs.py
- tests/test_engine_analytical_inputs.py
tags: []
---

# WP03: Admissible Input Preparation

## Objective

Add the engine-owned input preparation layer that turns warehouse evidence into analytical input series only after admissibility checks pass.

## Branch Strategy

Planning/base branch: `master`. Final merge target: `master`. This WP depends on WP02. Implementation worktrees are allocated per computed lane from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP03 --agent <name>
```

## Context

Read:

- `src/premura/engine/policies/_model.py`
- `src/premura/engine/policies/_evaluator.py`
- `src/premura/engine/_query.py`
- `src/premura/engine/analytical_contract.py`
- `kitty-specs/stage-3-analytical-tools-01KST48C/data-model.md`

## Detailed Guidance

### T009: Add admissible input-series model and overlap metadata handling

Create `src/premura/engine/analytical_inputs.py`.

Define the prepared input-series shape from `data-model.md`:

- metric id
- ordered points
- usable analysis window
- overlap start/end
- overlap sample size
- sample size
- imputation percentage
- freshness/admissibility status
- source summary
- optional refusal outcome

For single-series tools, overlap window equals usable analysis window. Keep the field explicit so future multi-input tools inherit the same contract.

### T010: Add input-preparation refusal behavior before computation

Prepared inputs must refuse before computation when evidence is missing, stale, inadmissible, insufficient, or parameter bounds make the request unsupported.

Refusal outcomes must carry distinct machine-readable reasons and no estimate.

### T011: Add analytical question-type policy wiring for prepared inputs

Wire the reviewed analytical question types into admissibility preparation:

- `level_shift_detection`
- `smoothed_pattern`

Use the existing policy evaluator pattern. Do not pass ad-hoc strings through the evaluator.

### T012: Add input-preparation tests with fixture-backed evidence

Create `tests/test_engine_analytical_inputs.py`.

Cover:

- ordered series preparation for usable evidence
- overlap metadata for a single-series request
- stale input refusal
- insufficient data refusal
- rejected/inadmissible input refusal
- no computation called for refused input, where observable through public behavior

## Definition of Done

- Prepared input layer exists and is tested.
- Analytical question types are closed/reviewed, not free-form.
- Refusals happen before statistical methods run.

## Risks

- This layer can accidentally become a new generic query planner. Keep it bounded to the analytical input contract.

## Reviewer Guidance

Check that no proof method bypasses this layer later.
