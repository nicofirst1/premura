---
work_package_id: WP03
title: Simple Before After Pairing Input
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-014
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/paired_inputs.py
- tests/test_engine_before_after_pairs.py
tags: []
---

# Work Package Prompt: WP03 - Simple Before/After Pairing Input

## Implement Command

```bash
spec-kitty agent action implement WP03 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Add the narrow engine-owned input preparation shape for anchor-date before/after
pairing. This WP produces paired inputs and refusals only. It must not implement
the paired statistical estimate and must not expose any MCP or trace behavior.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/data-model.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/contracts/paired-t-test-contract.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/research.md`

## Owned Files

- `src/premura/engine/paired_inputs.py`
- `tests/test_engine_before_after_pairs.py`

Do not edit `src/premura/engine/paired_t_test.py`, MCP wrappers, trace files, or
live docs in this WP.

## Subtasks

### T011: Add failing before/after paired-input tests for anchor-date pairing

Create `tests/test_engine_before_after_pairs.py` with synthetic
`AnalyticalInputSeries` fixtures.

Happy-path tests should prove:

- The caller supplies `metric_id`, `anchor_date`, `before_days`, `after_days`, and
  `expected_direction`.
- The preparer builds before/after pairs around the anchor date using one fixed
  deterministic rule.
- Pair records include before/after timestamps, values, imputation flags, and
  `difference = after - before`.
- Pair order is deterministic.
- Before/after span metadata and raw pair count are populated.

### T012: Add failing before/after paired-input refusal tests for malformed requests and weak pairs

Add refusal tests before implementing broad behavior.

Required refusal cases:

- Input series already carries a refusal.
- Missing or malformed anchor date.
- `before_days` or `after_days` is zero, negative, or beyond supported bounds.
- Missing expected direction or unknown expected direction.
- No values before the anchor.
- No values after the anchor.
- Too few valid pairs.

Each refusal returns no computation-ready pairs and a `RefusalOutcome`.

### T013: Implement simple before/after request, pair, and paired-input shapes

Add immutable dataclasses or equivalent frozen shapes in
`src/premura/engine/paired_inputs.py`.

Expected shapes:

- `BeforeAfterPairedRequest`.
- `BeforeAfterPair`.
- `BeforeAfterPairedInput`.
- A closed expected-direction vocabulary such as `increase` / `decrease` if not
  already provided by WP01.

Validation guidance:

- Validate ordinary malformed requests as refusals where the public preparer can
  reasonably do so.
- Use exceptions only for programming errors in direct shape construction.
- Keep fields JSON-safe or easily serializable by later envelopes.

### T014: Implement deterministic anchor-date pairing semantics with visible imputation metadata

Implement a public helper such as `prepare_before_after_paired_input`.

Pairing guidance:

- The anchor is a local calendar date. Use existing local-time helper patterns if
  needed.
- Use one fixed documented rule for matching before and after observations, such
  as nearest-to-anchor outward or same ordinal day within windows. The exact rule
  must be in tests and docstrings.
- Preserve upstream `is_imputed` flags from `PreparedPoint`.
- Compute `is_imputed_pct` over pairs where either side is imputed.
- Never invent values to complete a pair.

### T015: Guard against condition-label pairing, arbitrary pair maps, and anchor/window scanning

Add tests and code paths that make out-of-scope shapes explicit.

Guardrails:

- No `condition_label` parameter.
- No arbitrary pair ids.
- No list of candidate anchors.
- No list of windows.
- No option to choose the best split.

If an agent asks for those shapes later, the correct behavior is to refuse or to
require a future mission with a separate contract.

Definition of done:

- The paired input helper can be used by WP04 without touching MCP/trace.
- All supported and refused pairing shapes are covered by synthetic fixtures.

## Test Strategy

Run:

```bash
uv run python -m pytest tests/test_engine_before_after_pairs.py -q
```

## Risks

- Pairing can quietly become a search algorithm. Keep every pairing decision
  declared and deterministic.
- If the pair construction rule is not tested, later implementers may change the
  paired estimate without realizing the input changed.

## Reviewer Guidance

Review the refusal surface and pair construction rule before reviewing field
names. If condition pairing sneaks in, reject as scope creep.
