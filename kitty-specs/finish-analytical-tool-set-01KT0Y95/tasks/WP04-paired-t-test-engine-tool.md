---
work_package_id: WP04
title: Paired T-Test Engine Tool
dependencies:
- WP03
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-014
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
- T020
agent: "claude:opus:python-implementer:implementer"
shell_pid: "67616"
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/paired_t_test.py
- tests/test_engine_paired_t_test.py
tags: []
---

# Work Package Prompt: WP04 - Paired T-Test Engine Tool

## Implement Command

```bash
spec-kitty agent action implement WP04 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Implement `paired_t_test` as an engine-owned analytical tool over the simple
before/after paired input from WP03. The result should report paired difference,
uncertainty metadata, direction alignment, validity/confounds, or a first-class
refusal. It must not expose conventional significance theatre or cause claims.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/data-model.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/contracts/paired-t-test-contract.md`
- `src/premura/engine/paired_inputs.py` from WP03

## Owned Files

- `src/premura/engine/paired_t_test.py`
- `tests/test_engine_paired_t_test.py`

Do not edit MCP wrappers, trace files, live docs, or the before/after pairing
helper in this WP unless WP03 left an explicit defect that blocks the tool.

## Subtasks

### T016: Add failing paired-t-test acceptance tests for available paired-difference envelopes

Create `tests/test_engine_paired_t_test.py` with synthetic `BeforeAfterPairedInput`
fixtures from WP03.

Available-result tests should assert:

- `tool_name="paired_t_test"`.
- `status="available"`.
- Metric id and declared anchor/window parameters are preserved.
- Raw pair count is reported.
- Mean paired difference is computed as after minus before.
- Observed direction and expected direction are present.
- Direction-match metadata is present.
- Uncertainty metadata is present.
- The result has no diagnosis, treatment, causation, population-norm, or hidden
  search wording.

### T017: Add failing paired-t-test refusal tests for weak, malformed, and constant-difference inputs

Add refusal tests before implementing the estimate.

Required refusal cases:

- Paired input already carries a refusal.
- Pair count below the planned floor.
- Constant paired differences or zero variance where uncertainty cannot be
  honestly expressed.
- Missing required request metadata.
- Unsupported parameter if a caller tries to request p-value/significance,
  condition pairing, arbitrary pair maps, or anchor scans.

Refusals must carry no estimate.

### T018: Implement the deterministic `paired_t_test` tool registration and estimate payload

Add `src/premura/engine/paired_t_test.py` with a registered analytical tool.

Implementation guidance:

- Use the existing analytical contract and result envelope.
- Consume only the before/after paired input shape from WP03.
- Keep computations pure and deterministic. No clock, filesystem, warehouse,
  MCP, trace, network, or PubMed dependencies.
- Round stable numeric outputs in the same style as existing analytical tools.
- If the method name remains `paired_t_test`, ensure the user-facing payload
  still reads as paired-difference analysis rather than a declaration of
  statistical certainty.

### T019: Add paired-t-test uncertainty, direction, caveat, and confound metadata

Implement the metadata needed for agent narration without guessing.

Expected metadata:

- Pair count.
- Mean paired difference.
- Uncertainty metadata for the mean paired difference.
- Observed direction: `increase`, `decrease`, or `zero`.
- Expected direction copied from request.
- Direction-match boolean.
- Imputation percentage.
- Confound checklist.

Confounds should use the closed vocabulary only. Likely candidates include low
sample size, high imputation, short support window, parameter at limit, temporal
autocorrelation, vendor estimate input, and life-event sensitivity when rules
apply.

### T020: Add no-causation, no-diagnosis, and no-hidden-search assertions for paired_t_test

Add tests that inspect serialized output and built-in caveats/messages.

Forbidden output concepts:

- `significant` unless inside a test name or explicit forbidden-word assertion.
- `p-value` in user-facing payloads unless a later reviewed policy changes this.
- `cause`, `caused`, `effect`, `impact`, or `driver` in interpretive text.
- Diagnosis, treatment, dosing, emergency guidance, or population norms.

Also test that attempts to request broader condition pairing or anchor/window
scanning are refused by this tool path.

Definition of done:

- `paired_t_test` can be registered and called directly from engine tests.
- Available and refused outputs serialize deterministically.
- The implementation consumes WP03's paired input and does not create another
  pairing system.

## Test Strategy

Run:

```bash
uv run python -m pytest tests/test_engine_paired_t_test.py -q
```

If failures suggest paired input defects, run:

```bash
uv run python -m pytest tests/test_engine_before_after_pairs.py -q
```

## Risks

- Conventional t-test vocabulary can imply significance. Keep user-facing output
  descriptive and caveated.
- Re-implementing pairing inside this tool would bypass WP03's tested seam.

## Reviewer Guidance

Review whether the tool computes only over the provided paired input. Then review
the output language for overclaim risk.

## Activity Log

- 2026-06-01T07:51:04Z – claude:opus:python-implementer:implementer – shell_pid=67616 – Started implementation via action command
