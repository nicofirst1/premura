---
work_package_id: WP01
title: Analytical Research Note
dependencies: []
requirement_refs:
- FR-011
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
agent: "claude:opus:reviewer:reviewer"
shell_pid: "13422"
history:
- 2026-05-29T15:18:42Z tasks generated
authoritative_surface: docs/history/research/
execution_mode: planning_artifact
owned_files:
- docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md
tags: []
---

# WP01: Analytical Research Note

## Objective

Create the durable Stage 3 analytical-depth research note that implementation work follows. This note turns the plan's decisions into a reviewable, project-history artifact.

## Branch Strategy

Planning/base branch: `master`. Final merge target: `master`. Implementation happens later in a Spec Kitty lane worktree computed from `lanes.json`; do not assume the project root checkout is the implementation workspace.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent <name>
```

## Context

Read these first:

- `kitty-specs/stage-3-analytical-tools-01KST48C/spec.md`
- `kitty-specs/stage-3-analytical-tools-01KST48C/plan.md`
- `kitty-specs/stage-3-analytical-tools-01KST48C/research.md`
- `docs/product/DOCTRINE.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/product/ROADMAP.md`
- `docs/adr/0007-evidence-admissibility-as-a-declared-contract.md`

## Detailed Guidance

### T001: Write the durable Stage 3 analytical-depth research note

Create `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md`.

The note should explain why this mission adds a deterministic analytical-tool contract before broader statistics, literature grounding, or reproducible traces. Use plain English. Treat the agent as the operational reader and the human as the beneficiary.

Required sections:

- Purpose
- Summary
- Decisions
- Alternatives rejected
- Consequences for implementation

### T002: Capture method decisions for `change_point` and smoothed average

Record the committed method shapes from `research.md`:

- `change_point`: one ordered series, candidate split points, minimum usable observations on both sides, largest absolute standardized level difference, no p-value.
- smoothed average: trailing rolling mean, declared window and minimum coverage, no long-gap filling, uncertainty explicitly unavailable if no natural interval exists.

Explain why more complex methods are deferred.

### T003: Capture analytical `QuestionType` and confound vocabulary decisions

Record the reviewed question types:

- `level_shift_detection`
- `smoothed_pattern`

Record the committed initial confound vocabulary:

- `high_imputation`
- `low_sample_size`
- `short_overlap_window`
- `parameter_at_limit`
- `vendor_estimate_input`
- `temporal_autocorrelation`
- `life_event_sensitive`
- `method_uncertainty_unavailable`

State that these are closed runtime vocabulary entries, not prose suggestions.

### T004: Cross-check research note against doctrine, roadmap, and plan

Verify the note does not:

- enumerate a full statistical surface
- introduce runtime network access
- imply diagnosis, causation, treatment, or population-norm comparison
- reopen Stage 2 result families

## Definition of Done

- `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md` exists.
- It resolves the decisions listed above without `[NEEDS CLARIFICATION]` markers.
- It cites or links the relevant doctrine/roadmap/ADR context.
- It uses plain English and avoids invented methodology jargon.

## Risks

- Leaving choices open will block later WPs or cause agents to invent incompatible contract shapes.

## Reviewer Guidance

Review for decision completeness and doctrine alignment, not for statistical sophistication.

## Activity Log

- 2026-05-29T15:24:13Z – claude:opus:planner:implementer – shell_pid=10144 – Started implementation via action command
- 2026-05-29T15:26:19Z – claude:opus:planner:implementer – shell_pid=10144 – Ready for review
- 2026-05-29T15:26:39Z – claude:opus:reviewer:reviewer – shell_pid=13422 – Started review via action command
- 2026-05-29T15:27:41Z – claude:opus:reviewer:reviewer – shell_pid=13422 – Review passed: durable Stage 3 analytical research note resolves all decisions (change_point & smoothed-average shapes, 2 closed QuestionTypes, 8 closed confound keys) with zero NEEDS CLARIFICATION, valid doctrine/roadmap/ADR links, and doctrine-aligned boundaries; only the research file changed.
