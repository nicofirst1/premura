---
work_package_id: WP04
title: Current Seam And Profile Dependency
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-24T13:02:16Z'
subtasks:
- T014
- T015
- T016
- T017
agent: "claude:opus:research-reviewer:reviewer"
shell_pid: "35512"
history:
- timestamp: '2026-05-24T13:02:16Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/
execution_mode: planning_artifact
owned_files:
- kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/04-engine-seam-and-profile-dependency.md
tags: []
---

# Work Package Prompt: WP04 - Current Seam And Profile Dependency

## Objective

Evaluate the current Stage 2 seam element by element and make the baseline-profile dependency explicit.

The output is `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/04-engine-seam-and-profile-dependency.md`.

## Why This WP Exists

Premura already has a small Stage 2 seam in code. This mission should not pretend the seam does not exist, but it also should not assume the seam is already the finished contributor contract. At the same time, useful early functions may depend on height, birth date, sex, or similar profile data that does not fit the ordinary measurement model cleanly. This WP forces both facts into the open.

This WP directly supports:

- `FR-006`
- `FR-007`

## Owned Surface

- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/04-engine-seam-and-profile-dependency.md`

Do not modify files outside this list.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP04 --agent <name>`

Do not start until WP01's baseline artifact is available.

## Required Inputs

- `research/01-repo-baseline.md`
- `src/premura/engine/__init__.py`
- `src/premura/engine/_registry.py`
- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- GitHub issue `#6`

## Subtasks

### T014 - Audit the current Stage 2 seam

**Purpose**

List the seam elements that already exist so the mission can explicitly evaluate them.

**Required work**

- Inventory the current seam elements already present in code and docs.
- Include items such as:
  - `SignalSpec`
  - registry model
  - compute entrypoints
  - domain listing
  - input-availability checks
  - revisions
  - `derived:` persistence pattern
- Keep the inventory focused on contract-level elements.

### T015 - Mark seam elements keep, change, or defer

**Purpose**

Turn the seam inventory into a usable disposition list for future work.

**Required work**

- For each seam element, assign one of:
  - keep
  - change
  - defer
- Add a brief rationale for each decision.
- Stay at the contract level rather than drifting into code design.

### T016 - Identify baseline-profile dependencies

**Purpose**

Show which useful engine functions require stable user context that is not just another measurement row.

**Required work**

- Identify the categories of baseline personal profile data likely to matter.
- Explain why those inputs do not fit cleanly into ordinary observed measurements.
- Tie the explanation back to plausible early function ideas where relevant.

### T017 - Connect the gap to issue `#6`

**Purpose**

Make the dependency actionable instead of leaving it as an aside.

**Required work**

- Reference issue `#6` explicitly.
- State what remains unresolved about the storage/update model for baseline profile data.
- Explain how later implementation work should treat this dependency until issue `#6` is addressed.

## Validation Strategy

This WP is complete when:

- `research/04-engine-seam-and-profile-dependency.md` exists.
- Every current seam element has a keep/change/defer disposition.
- The profile-data dependency is explicit and tied to issue `#6`.

## Definition Of Done

- Seam inventory written.
- Keep/change/defer decisions documented.
- Baseline-profile dependency analysis written.
- Issue `#6` linked as the follow-on design problem.

## Risks And Watchouts

- The seam analysis may become too implementation-specific.
- The profile-data dependency may get mentioned but not truly integrated into the output.

## Reviewer Guidance

- Check that the seam evaluation is specific enough to guide future work.
- Check that profile data is treated as a first-class dependency rather than hidden in assumptions.

## Activity Log

- 2026-05-24T13:24:50Z – claude:opus:research-implementer:implementer – shell_pid=18842 – Started implementation via action command
- 2026-05-24T13:28:06Z – claude:opus:research-implementer:implementer – shell_pid=18842 – Ready for review: seam inventory with keep/change/defer dispositions + baseline-profile dependency tied to issue #6
- 2026-05-24T13:28:27Z – claude:opus:research-reviewer:reviewer – shell_pid=35512 – Started review via action command
- 2026-05-24T13:29:55Z – claude:opus:research-reviewer:reviewer – shell_pid=35512 – Review passed: seam audit accurate vs _registry.py/__init__.py/lab_ratios.py; all 10 seam elements have keep/change/defer dispositions; profile-data analysis (sex/birth-date/age/height) verified against dim_metric.yaml; issue #6 contents match live gh issue.
