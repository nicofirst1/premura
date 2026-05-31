---
work_package_id: WP03
title: Correlate Engine Method
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-005
- FR-007
- FR-008
- FR-010
- FR-011
- FR-014
- FR-015
- FR-016
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
agent: "claude:opus:reviewer:reviewer"
shell_pid: "87896"
history:
- 2026-05-30T14:27:30Z tasks generated for correlate lagged association mission
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_tools.py
- src/premura/engine/__init__.py
- tests/test_engine_correlate_tool.py
tags: []
---

# WP03: Correlate Engine Method

## Objective

Implement the deterministic engine-owned `correlate` tool over the paired input
from WP02. The result must report association only: Spearman's rho, association
band, effective sample size, direction alignment, validity, confounds, or a
structured refusal with no estimate.

## Branch Strategy

Planning/base branch is `master`. Final merge target is `master`. Do not create a
manual worktree. Spec Kitty will allocate execution worktrees per computed lane
from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP03 --agent <name>
```

## Context

Depends on WP01 and WP02. The method must consume paired prepared input, not raw
warehouse rows. Keep all statistical behavior in `src/premura/engine/`, not MCP.

The method choices are fixed:

- Spearman rho only.
- No p-values.
- No significance labels.
- No lag scan.
- No causal language.
- Effective sample size uses rank-transformed autocorrelation terms through
  `1..min(7, floor(raw_paired_sample_size / 4))`.
- Raw paired sample floor is 20.
- Effective sample floor is 12.

## Subtasks

### T011: Add failing engine tool tests for available correlate output and core refusal classes

Purpose: define observable behavior before method code.

Guidance:

- Add `tests/test_engine_correlate_tool.py`.
- Cover one available association with lag 1 and expected negative direction.
- Assert the serialized envelope includes tool name, inputs, parameters,
  Spearman rho, association band, raw/effective sample counts, overlap metadata,
  imputation percentage, validity status, and confound checklist.
- Add refusal tests for below-20 raw pairs, below-12 effective sample size,
  constant series, malformed hypothesis, and refused paired input.
- Tests should assert no estimate is present for refusals.

Validation:

- Tests fail before implementation.
- Tests use synthetic daily fixtures only.

### T012: Implement deterministic Spearman rho and rank handling for paired observations

Purpose: compute the v1 association estimate.

Guidance:

- Implement rank transformation with deterministic tie handling.
- Compute signed Spearman rho over paired values.
- Refuse constant or rank-deficient series rather than returning NaN or a fake
  zero.
- Keep helper functions private unless the engine public contract requires them.
- Avoid introducing numpy/scipy or a new runtime dependency unless explicitly
  justified; a small deterministic implementation is likely sufficient.

Validation:

- Known monotonic positive and negative fixtures produce expected signs.
- Tied-value fixtures are deterministic.

### T013: Implement effective sample size and association-band calculation with deterministic truncation

Purpose: make uncertainty honest for autocorrelated personal series.

Guidance:

- Compute sample autocorrelation over rank-transformed paired series.
- Use lags `1..min(7, floor(raw_paired_sample_size / 4))`.
- Treat undefined/noisy autocorrelation terms as zero where needed to preserve
  deterministic output.
- Apply half weight to pairs where either side is imputed when calculating
  effective support.
- Refuse if effective sample size is below 12.
- Produce an association band bounded inside `[-1.0, 1.0]`.
- Do not name the band a confidence interval in payload or caveats.

Validation:

- A highly autocorrelated fixture has lower effective sample size and wider band
  than a less autocorrelated fixture.
- A below-floor effective sample fixture refuses with no estimate.

### T014: Implement correlate result envelope, direction alignment, confounds, caveats, and refusal outcomes

Purpose: make the result safe for agent narration.

Guidance:

- Use the existing `AnalyticalOutcome` / envelope conventions.
- Include observed direction, expected direction, and whether they match.
- Emit `low_sample_size` for raw pairs 20-49 or effective sample size 12-29.
- Emit `short_overlap_window` for paired calendar overlap under 28 days.
- Emit `high_imputation` when imputed-pair share is at least 20%.
- Emit `temporal_autocorrelation` when effective sample size is less than half
  raw paired sample size.
- Emit `common_cause_plausible` only when candidate common causes were supplied
  before computation.
- Carry life-event caveats from source/policy metadata where available.
- Keep caveats short and non-causal.

Validation:

- Confound fixtures trigger exactly the expected keys.
- Caveats stay under 280 characters.

### T015: Register `correlate` as a built-in analytical tool and export the public engine surface

Purpose: make the tool available through the existing analytical registry.

Guidance:

- Register the tool in `src/premura/engine/analytical_tools.py` using the existing
  decorator pattern.
- Use input shape `paired_ordered_daily_series` and result kind
  `correlate_association_estimate`.
- Declare only supported parameters.
- Export the tool through `src/premura/engine/__init__.py` if current project
  conventions require built-in analytical tool exports there.
- Do not add a per-tool branch to analytical dispatch.

Validation:

- Dispatch can invoke `correlate` by name.
- Existing proof tools still register and dispatch.

### T016: Add forbidden-output tests for p-values, significance, causal language, diagnosis, and lag scanning

Purpose: lock the health-honesty boundary.

Guidance:

- Assert serialized available/refused outcomes contain no p-value fields.
- Assert no significance flag or significance wording appears.
- Assert caveats and messages avoid `cause`, `effect`, `impact`, `driver`,
  diagnosis, treatment, dosing, emergency, and population-norm claims.
- Add tests that attempts to request p-values, significance, tolerance pairing,
  or lag scanning are refused before computation.

Validation:

- These tests must be direct enough that future regressions fail loudly.

## Definition Of Done

- `correlate` computes deterministic Spearman association over paired inputs.
- All hard floors and caveat thresholds are implemented.
- Available outcomes are complete analytical envelopes.
- Refusals carry no estimate.
- No p-values, significance labels, causal language, or lag scan behavior exists.

## Risks And Review Notes

- Reviewers should inspect every serialized key for statistical-theater leakage.
- Tie handling and autocorrelation truncation should be deterministic and simple.
- Do not bury preparation failures inside the method; invalid pair inputs should
  already be refused by WP02.

## Activity Log

- 2026-05-30T14:57:49Z – claude:opus:implementer:implementer – shell_pid=73259 – Started implementation via action command
- 2026-05-30T15:13:34Z – claude:opus:implementer:implementer – shell_pid=73259 – Ready for review: deterministic Spearman lagged-association correlate tool (midrank ties, N_eff autocorrelation+imputation band via Fisher z, raw<20 / N_eff<12 refusals, confound checklist, forbidden-output guards). Registered + reachable via dispatch + exported. 84/84 mission tests, 541/541 full suite pass.
- 2026-05-30T15:14:11Z – claude:opus:reviewer:reviewer – shell_pid=87896 – Started review via action command
- 2026-05-30T15:19:41Z – claude:opus:reviewer:reviewer – shell_pid=87896 – Review passed. Spearman independently verified: [1,2,3,4,5]/[2,1,4,3,5]=0.8, perfect monotone +/-1.0, ties case 0.9545454545 matches scipy spearmanr (proper midrank tie correction), constant series returns None -> refused (no fake zero). N_eff widening verified: rank-based N_eff=N/(1+2*sum rho_xx*rho_yy) over lags 1..min(7,floor(N/4)); on N=40 iid N_eff=37.4 vs autocorrelated walk N_eff=6.0, band width 0.255 vs 0.834 -> rank-switch did NOT skip autocorrelation widening; imputed pairs half-weighted, inflation floored at 1.0, N_eff floored to 4.0 keeping Fisher z valid. Band is Fisher z SE=1/sqrt(N_eff-3) back-transformed clamped [-1,1], never called confidence interval, never thresholded. Refusals exact: raw<20 (insufficient_data), N_eff<12 (insufficient_effective_sample), constant (insufficient_rank_variation), hypothesis mismatch (missing_hypothesis), refused paired input propagated. FORBIDDEN OUTPUT verified by reading code: no p-value/significance computed anywhere; any extra positional/kwarg refused BEFORE computation via _CORRELATE_SUPPORTED_KWARGS=frozenset() gate; banned causal vocab appears only in negated meta-docstrings/refusal-explanations, never in estimate/caveat/confound prose; T016 tests substantive (word-boundary regex over engine prose, full-blob substring check for confidence interval/p-value/significance, recursive key walker, 4 smuggle-request refusal tests). Registry now 3 built-ins, correlate reachable via dispatch with paired_ordered_daily_series shape; facade (list/invoke/load) exported, tool functions intentionally not top-level (matches change_point/smoothed_average convention). analytical.py diff is the single necessary registration line. stdlib math only, no scipy/numpy/clock/network/state. Multiplicity/ledger correctly absent. N_eff envelope judgment: ACCEPT - shared AnalyticalResultEnvelope (other WP, not editable) lacks effective_sample_size top-level; N_eff surfaced in estimate + uncertainty.payload, byte-stable, no info loss. 84/84 mission tests, 541/541 full suite green.
- 2026-05-31T08:22:59Z – claude:opus:reviewer:reviewer – shell_pid=87896 – Done override: Mission #11 merged to master (a7fe925); post-merge done-transition repair
