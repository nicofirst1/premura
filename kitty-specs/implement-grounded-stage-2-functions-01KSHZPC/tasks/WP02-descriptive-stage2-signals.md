---
work_package_id: WP02
title: Descriptive Stage 2 Signals
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-004
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
agent: "claude:opus:implementer:implementer"
shell_pid: "30909"
history:
- timestamp: '2026-05-26T11:32:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/_query.py
- src/premura/engine/descriptive_signals.py
- tests/test_engine_descriptive_signals.py
tags: []
---

# Work Package Prompt: WP02 - Descriptive Stage 2 Signals

## Objective

Implement the four descriptive first-wave Stage 2 answers:

- `resting_hr_status`
- `resting_hr_trend`
- `steps_trend`
- `weight_trend`

These are the lowest-risk, highest-value functions from the research mission. They should close the most obvious direct-read debt by returning grounded, freshness-aware answers instead of raw-table snapshots.

## Owned Surface

- `src/premura/engine/_query.py`
- `src/premura/engine/descriptive_signals.py`
- `tests/test_engine_descriptive_signals.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP02 --agent <name>`

## Subtasks

### T006 - Add shared Stage 2 query helpers

**Purpose**

Avoid duplicating warehouse-query logic across four descriptive functions.

**Required changes**

- Add `src/premura/engine/_query.py`.
- Implement shared helpers for:
  - latest usable value lookup with freshness handling
  - extracting ordered windows for trend calculations
  - distinguishing observed from carried-forward or missing points where the metric policy allows it
- Keep all helpers local to Stage 2 and compatible with DuckDB connections already used by the engine.

**Design guidance**

- Respect each metric's existing `validity_window` and `missing_data_policy` from `hp.dim_metric`.
- Use the current warehouse schema directly; do not add schema changes.
- Keep helper names plain and easy to test.

### T007 - Implement `resting_hr_status`

**Purpose**

Answer the plain question: "What is my resting HR right now, and can I trust it?"

**Required behavior**

- Register `resting_hr_status` as a built-in Stage 2 signal.
- Use `resting_hr`.
- Return a status-family result with:
  - latest usable value
  - timestamp
  - freshness verdict
  - caveats when the value is stale or unavailable
- Refuse to present stale data as current.

**Non-goals**

- No trend language.
- No reference-range or training interpretation.
- No significance or diagnosis.

### T008 - Implement `resting_hr_trend`

**Purpose**

Answer the plain question: "Is my resting HR going up, down, or flat over recent weeks?"

**Required behavior**

- Register `resting_hr_trend`.
- Produce a trend-family result with:
  - ordered points
  - plain trend direction
  - visibility into carried-forward points if they exist
  - explicit freshness for the latest relevant point
- Keep the output descriptive only.

**Caveat handling**

- Make gaps and carried-forward behavior visible.
- Do not turn a sparse series into a confident trend claim.

### T009 - Implement `steps_trend`

**Purpose**

Answer the plain question: "Are my daily steps trending up or down?"

**Required behavior**

- Register `steps_trend`.
- Use `steps`, which currently has `missing_data_policy: none`.
- Return a trend-family result with zero imputed points.
- Make missing days visible as gaps rather than inventing continuity.

**Specific risk to avoid**

- Do not accidentally reuse carried-forward logic from `resting_hr` or `weight`.

### T010 - Implement `weight_trend`

**Purpose**

Answer the plain question: "Is my weight rising, falling, or flat over the last month?"

**Required behavior**

- Register `weight_trend`.
- Use `weight`, which currently allows carried-forward behavior within its freshness window.
- Return a trend-family result with visible carried-forward points and explicit caveats.
- Do not present a stale weight as current when it falls outside its allowed window.

**Non-goals**

- No BMI or body-composition interpretation.
- No profile-dependent behavior.

### T011 - Add descriptive-signal tests

**Purpose**

Lock the descriptive signal behavior through public engine interfaces.

**Required changes**

- Add `tests/test_engine_descriptive_signals.py`.
- Cover at least these paths:
  - `resting_hr_status`: current value, stale value, no value
  - `resting_hr_trend`: clear trend, sparse trend, insufficient data
  - `steps_trend`: missing-day gaps stay gaps
  - `weight_trend`: carried-forward points are flagged and stale values are not misreported
- Drive behavior through public engine helpers and `engine.compute(...)`.

**Testing guidance**

- Use temporary DuckDB fixtures like the existing engine tests.
- Keep assertions on externally visible outputs, not internal helper behavior.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest tests/test_engine_descriptive_signals.py -q
uv run python -m pytest tests/test_engine.py -q
```

Expected outcomes:

- All four descriptive signals are registered and callable.
- Status and trend responses include explicit trust-state information.
- `steps_trend` shows gaps without imputation.

## Definition Of Done

- The four descriptive signals are implemented and registered.
- Shared query helpers exist and are reused.
- Freshness, gaps, and carried-forward behavior are explicit in outputs.
- Focused descriptive-signal tests pass.

## Risks And Watchouts

- Trend code often hides stale-input bugs by reusing the latest point without checking freshness.
- `steps_trend` is especially likely to inherit an imputation assumption it must not have.

## Reviewer Guidance

Review these functions as user-answering tools, not as analytics. The main review question is whether they tell the truth about freshness and sparsity, not whether they are mathematically fancy.

## Activity Log

- 2026-05-26T11:54:33Z – claude:opus:implementer:implementer – shell_pid=30909 – Started implementation via action command
