---
work_package_id: WP03
title: Comparative Stage 2 Signals
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
- T012
- T013
- T014
- T015
- T016
agent: "claude:opus:reviewer:reviewer"
shell_pid: "21773"
history:
- timestamp: '2026-05-26T11:32:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/comparative_signals.py
- tests/test_engine_comparative_signals.py
tags: []
---

# Work Package Prompt: WP03 - Comparative Stage 2 Signals

## Objective

Implement the two more caveat-heavy Stage 2 answers:

- `sleep_deep_pct_baseline`
- `hrv_change_around_date`

These are still grounded Stage 2 functions, but they sit closer to the boundary with interpretation and statistics. The implementation must be strict about what they do and do not claim.

## Owned Surface

- `src/premura/engine/comparative_signals.py`
- `tests/test_engine_comparative_signals.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP03 --agent <name>`

## Subtasks

### T012 - Implement own-baseline comparison primitives

**Purpose**

Provide the deterministic building blocks for answers that compare the user's latest value to their own recent normal.

**Required behavior**

- Implement comparison helpers inside `comparative_signals.py` for own-baseline windows.
- Keep the logic strictly user-relative.
- Make it easy to detect and report when there is not enough trustworthy data for a baseline.

**Constraints**

- No population or clinical reference ranges.
- No profile-dependent behavior.

### T013 - Implement `sleep_deep_pct_baseline`

**Purpose**

Answer: "Was last night's deep-sleep percentage below my own recent normal?"

**Required behavior**

- Register `sleep_deep_pct_baseline`.
- Use `sleep_deep_pct` as the primary metric.
- Compare the latest usable value against the user's own recent baseline.
- Return a baseline-family result with:
  - latest value
  - baseline mean
  - comparison state (`below`, `within`, `above`, or `unknown`)
  - freshness state
  - caveats

**Caveat requirements**

- Explicitly frame this as a device-estimate-based own-baseline comparison.
- Do not imply a medical threshold.

### T014 - Implement before/after comparison primitives

**Purpose**

Support deterministic comparisons around a user-supplied date without drifting into statistical tooling.

**Required behavior**

- Implement helper logic for:
  - selecting pre-window and post-window observations around an anchor date
  - computing simple means and counts
  - deciding whether the data is sufficient to answer at all
- Keep the helper output compatible with the shared change-family result shape.

### T015 - Implement `hrv_change_around_date`

**Purpose**

Answer: "Did my overnight HRV shift after a date I name?"

**Required behavior**

- Register `hrv_change_around_date`.
- Use `hrv_rmssd_overnight`.
- Return a change-family result with:
  - anchor date
  - before mean
  - after mean
  - delta
  - before/after counts
  - sufficiency flag
  - caveats

**Hard boundary**

- No p-values.
- No confidence intervals.
- No causal or significance language.

### T016 - Add comparative-signal tests

**Purpose**

Prove the comparative functions tell the truth about sufficiency and caveats.

**Required changes**

- Add `tests/test_engine_comparative_signals.py`.
- Cover at least:
  - successful own-baseline comparison
  - insufficient data for own-baseline comparison
  - successful before/after HRV comparison
  - insufficient HRV windows around the anchor date
  - caveat presence for both functions
- Assert through public engine interfaces.

**Testing stance**

- Keep assertions on the returned result shape and its caveats.
- Do not introspect internal helper functions directly.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest tests/test_engine_comparative_signals.py -q
uv run python -m pytest tests/test_engine.py -q
```

Expected outcomes:

- Both comparative signals are registered and callable.
- Own-baseline behavior stays user-relative.
- Before/after behavior refuses to over-claim when data is weak.

## Definition Of Done

- The two comparative signals are implemented and registered.
- Baseline and before/after helpers stay deterministic and local.
- Focused comparative tests pass.

## Risks And Watchouts

- It is very easy to accidentally make `sleep_deep_pct_baseline` sound like a clinical rule.
- `hrv_change_around_date` must not become a disguised statistics tool.

## Reviewer Guidance

Review the language of the outputs as carefully as the calculations. The main success criterion is honest, bounded comparison behavior with explicit caveats.

## Activity Log

- 2026-05-26T12:10:57Z – claude:opus:implementer:implementer – shell_pid=1280 – Started implementation via action command
- 2026-05-26T12:16:30Z – claude:opus:implementer:implementer – shell_pid=1280 – Ready for review: two comparative signals (own-baseline + before/after) with sufficiency honesty and bounded caveats; wired into builtin loader
- 2026-05-26T12:17:08Z – claude:opus:reviewer:reviewer – shell_pid=21773 – Started review via action command
