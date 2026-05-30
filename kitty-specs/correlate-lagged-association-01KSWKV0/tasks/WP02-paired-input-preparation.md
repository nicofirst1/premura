---
work_package_id: WP02
title: Paired Input Preparation
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-006
- FR-009
- FR-012
- FR-013
- FR-016
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
history:
- 2026-05-30T14:27:30Z tasks generated for correlate lagged association mission
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_inputs.py
- tests/test_engine_correlate_inputs.py
tags: []
---

# WP02: Paired Input Preparation

## Objective

Create the two-series preparation seam for `correlate`. This WP aligns two usable
analytical input series by one caller-declared lag, narrows overlap metadata to
actual paired days, and refuses before statistical computation when the pair is
not honest to analyze.

## Branch Strategy

Planning/base branch is `master`. Final merge target is `master`. Do not create a
manual worktree. Spec Kitty will allocate execution worktrees per computed lane
from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent <name>
```

## Context

Depends on WP01. Do not begin until lagged-association vocabulary and policy
mapping exist.

The single-series `AnalyticalInputSeries` already carries explicit overlap
metadata. This WP should not break that shape. Add a paired preparation seam in
`src/premura/engine/analytical_inputs.py` or a minimal adjacent construct in that
file's public surface. The output must be inspectable and refuse before any
coefficient can run.

## Subtasks

### T006: Add failing paired-preparation tests for same-day pairing after caller-declared lag

Purpose: make the lag contract executable.

Guidance:

- Add `tests/test_engine_correlate_inputs.py`.
- Build synthetic `PreparedPoint` series with clear dates and values.
- Cover lag 0 and lag 1.
- Assert pairing occurs only on same local calendar day after lag is applied.
- Assert no symmetric tolerance exists. Points on neighboring days should not
  pair unless the declared lag makes them same-day aligned.
- Assert output pairs are ordered by paired day.

Validation:

- Tests fail before paired preparation exists.
- Tests should not depend on the eventual Spearman implementation.

### T007: Define paired hypothesis/input data shapes and validation in the analytical input layer

Purpose: give the engine a typed preparation contract.

Guidance:

- Add a hypothesis shape carrying metric pair, `lag_days`, expected direction,
  optional lag justification, and optional common-cause candidates.
- Add a paired observation shape carrying paired day, source timestamps, values,
  and imputation flags.
- Add a paired input shape carrying pairs, overlap metadata, imputation
  percentage, source summary, freshness/admissibility summary, and refusal.
- Keep refused paired inputs structurally no-computation: no pairs and no sample
  size.
- Enforce lag rules here: `abs(lag_days) <= 3` free, `4..14` requires
  justification, `>14` refused.

Validation:

- Direct construction or preparation with missing metric IDs, missing expected
  direction, unsupported lag, or missing justification fails/refuses clearly.

### T008: Implement paired input preparation over two usable series with narrowed overlap metadata

Purpose: produce the actual paired computation input.

Guidance:

- Accept two `AnalyticalInputSeries` values plus the hypothesis.
- If either series is refused, return a paired refusal before reading points for
  computation.
- Apply the declared lag to one side consistently and document which side moves.
- Pair by local calendar day after lag alignment.
- Compute `overlap_start`, `overlap_end`, and `overlap_sample_size` from the
  actual paired days.
- Preserve source/provenance summaries for both inputs.
- Do not read the warehouse and do not call the policy evaluator here unless the
  existing preparation pattern requires it.

Validation:

- Prepared paired output matches fixture dates exactly.
- The existing single-series preparation tests continue to pass.

### T009: Implement paired-preparation refusal behavior for invalid lag, missing hypothesis, inadmissible input, no overlap, and weak paired support

Purpose: prevent the method layer from guessing about bad inputs.

Guidance:

- Return structured refusals for missing/malformed hypothesis.
- Return structured refusals for invalid lag or missing large-lag justification.
- Return structured refusals when either input series is refused.
- Return structured refusals when zero pairs remain after lag.
- Enforce the raw paired sample floor below 20 as a preparation refusal.
- Leave effective-sample-size refusal to WP03 unless this WP can compute it
  without duplicating method logic.

Validation:

- Each refusal carries a distinct machine-readable reason and no pairs.
- No statistical method needs to inspect malformed input.

### T010: Add imputed-pair percentage and paired-source provenance to the paired input output

Purpose: carry enough validity metadata into the result envelope.

Guidance:

- Compute imputed-pair share as percentage of pairs where either side is imputed.
- Preserve left/right source summaries and policy IDs where available.
- Include enough identifiers to reproduce which metrics and lag produced the
  pair set.
- Keep caveat/confound emission out of this WP unless the input layer already has
  established metadata-only behavior.

Validation:

- A fixture with imputed pairs reports the expected percentage.
- Source summary remains JSON-safe.

## Definition Of Done

- Paired input preparation exists and is tested independently of `correlate`.
- Lag is directional and caller-specified, not tolerance-based.
- Overlap metadata is narrowed to actual paired days.
- Refused paired inputs cannot be passed to computation with pairs attached.
- No single-series contract regression.

## Risks And Review Notes

- Reviewers should inspect date alignment carefully. This is the crux of the
  mission.
- Avoid duplicating statistical logic here; preparation is about admissible pairs,
  not association estimates.
- Confirm the old `overlap_*` semantics still work for single-series tools.
