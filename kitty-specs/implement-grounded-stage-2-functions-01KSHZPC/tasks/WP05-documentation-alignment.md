---
work_package_id: WP05
title: Documentation Alignment
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- FR-006
- FR-007
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
- T026
agent: "claude:opus:implementer:implementer"
shell_pid: "89784"
history:
- timestamp: '2026-05-26T11:32:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/architecture/STAGES.md
- docs/operations/STATUS.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- docs/product/VISION.md
tags: []
---

# Work Package Prompt: WP05 - Documentation Alignment

## Objective

Update the project docs so they describe the newly shipped Stage 2 and Stage 3 baseline accurately.

This WP should leave the repo with a coherent story: the six approved grounded answers now exist, Stage 3 has a signal-backed path for those question shapes, the remaining direct-read debt is narrower but still real outside those flows, and profile-dependent work remains blocked on issue `#6`.

## Owned Surface

- `docs/architecture/STAGES.md`
- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/product/VISION.md`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP05 --agent <name>`

## Subtasks

### T022 - Update `STAGES.md`

**Purpose**

Make the architecture source of truth reflect the new shipped path for the approved question shapes.

**Required changes**

- Update the Stage 2 and Stage 3 sections to reflect the six grounded answers now available.
- Narrow the wording around direct-read debt so it is clear that:
  - the debt still exists in general
  - it is now reduced for the six approved question shapes
- Keep the stage-boundary language strict and plain.

### T023 - Update `STATUS.md`

**Purpose**

Refresh the live shipped snapshot.

**Required changes**

- Add the new Stage 2 capabilities to the shipped state summary.
- Note the six signal-backed Stage 3 tools alongside the preserved raw tools.
- Keep the doc factual and current, not aspirational.

### T024 - Update `ROADMAP.md`

**Purpose**

Make future work start from the new baseline rather than from the old stubbed Stage 2/3 picture.

**Required changes**

- Remove or rewrite roadmap language that still treats these six flows as hypothetical.
- Keep future Stage 3 statistics tooling and broader analytical work clearly separate from what this mission ships.
- Keep profile-dependent work deferred.

### T025 - Update `FULL_APP_DEVELOPMENT_PLAN.md`

**Purpose**

Ensure phase-level planning acknowledges that Stage 2 and part of Stage 3 are now real, not only stubs.

**Required changes**

- Update the current starting point and phase descriptions where they still describe Stage 2/3 as entirely missing.
- Keep future-phase language aligned with the newly shipped descriptive and comparative answers.

### T026 - Update `VISION.md`

**Purpose**

Add a light acknowledgment that the first grounded question flows now exist, without turning the vision doc into a status log.

**Required changes**

- Keep the update small and trajectory-oriented.
- Preserve the privacy, non-diagnostic, and teaching-first stance.
- Do not oversell the current UI surface.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest -q
```

Manual validation expectations:

- `STAGES.md` no longer implies the six new flows are absent.
- `STATUS.md` reads like a live snapshot of the implemented mission.
- `ROADMAP.md` and `FULL_APP_DEVELOPMENT_PLAN.md` start future work from the new baseline.
- `VISION.md` remains long-term and non-diagnostic.

## Definition Of Done

- All five docs are updated and internally consistent.
- The docs explicitly keep issue `#6` deferred.
- The wording stays plain-English and aligned with the repo's mental-model guidance.

## Risks And Watchouts

- The most likely mistake is overstating how much of the Stage 3 direct-read debt is gone.
- Another is turning the vision doc into a changelog instead of a trajectory doc.

## Reviewer Guidance

Review these docs against the shipped code, not against the ideal future architecture. The goal is honest synchronization: what changed, what did not, and what remains deferred.

## Activity Log

- 2026-05-26T12:34:10Z – claude:opus:implementer:implementer – shell_pid=89784 – Started implementation via action command
- 2026-05-26T12:40:16Z – claude:opus:implementer:implementer – shell_pid=89784 – Ready for review: five docs synced to shipped Stage 2/3 baseline; direct-read debt narrowed not eliminated; #6 still deferred
