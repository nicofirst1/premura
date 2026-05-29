---
work_package_id: WP04
title: Proof Analytical Tools
dependencies:
- WP03
requirement_refs:
- FR-007
- FR-008
- FR-010
- FR-012
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
history:
- 2026-05-29T15:18:42Z tasks generated
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_tools.py
- tests/test_engine_analytical_tools.py
tags: []
---

# WP04: Proof Analytical Tools

## Objective

Implement the two proof analytical tools behind the contract: `change_point` and smoothed average.

## Branch Strategy

Planning/base branch: `master`. Final merge target: `master`. This WP depends on WP03. Implementation worktrees are allocated per computed lane from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP04 --agent <name>
```

## Context

Read:

- `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md`
- `src/premura/engine/analytical_contract.py`
- `src/premura/engine/analytical_inputs.py`
- `kitty-specs/stage-3-analytical-tools-01KST48C/contracts/analytical-tool-contract.md`

## Detailed Guidance

### T013: Implement conservative `change_point` computation

Create `src/premura/engine/analytical_tools.py`.

Implement `change_point` as described in the research note:

- one admissible ordered series
- candidate split points with minimum usable observations on both sides
- before/after means for each candidate
- selected candidate by largest absolute standardized level difference
- no p-value and no causal label

Return a contract result envelope with the estimate and metadata.

### T014: Implement smoothed-average computation

Implement smoothed average as a trailing rolling mean:

- one admissible ordered series
- declared window and minimum coverage
- no long-gap filling
- preserve imputation visibility
- uncertainty explicitly unavailable if no natural interval exists

Return smoothed output with method revision, effective window, coverage, and metadata.

### T015: Add proof-tool tests for supported and refused inputs

Create `tests/test_engine_analytical_tools.py`.

Cover:

- representative level shift returns deterministic `change_point` estimate
- insufficient data refuses with no estimate
- smoothed average returns deterministic smoothed output
- out-of-bounds smoothing/window parameters refuse with no estimate
- repeated runs over identical inputs serialize identically

### T016: Verify proof tools do not claim causation, prediction, or significance

Tests should assert caveats/messages avoid:

- cause/caused/causal language
- diagnostic labels
- p-value or significance claims
- prediction claims for smoothed average

## Definition of Done

- Both proof tools exist behind the analytical contract.
- Supported and refused paths are tested.
- Outputs are deterministic and metadata-bearing.

## Risks

- It is easy for change-point language to imply the anchor event caused the change. Keep wording descriptive.

## Reviewer Guidance

Review estimates for honesty and refusal behavior, not for advanced statistical breadth.
