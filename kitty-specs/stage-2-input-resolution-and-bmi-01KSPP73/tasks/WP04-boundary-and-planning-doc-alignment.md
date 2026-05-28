---
work_package_id: WP04
title: Boundary And Planning Doc Alignment
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-009
- FR-010
- FR-011
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-28T08:13:11Z'
subtasks:
- T014
- T015
- T016
- T017
agent: ''
history:
- timestamp: '2026-05-28T08:13:11Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- src/premura/engine/CONTRACT.md
- docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md
- docs/architecture/STAGES.md
- docs/operations/STATUS.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
tags: []
---

# Work Package Prompt: WP04 - Boundary And Planning Doc Alignment

## Objective

Align the code-adjacent contracts, architecture docs, shipped-state docs, and
planning docs with the corrected Stage 2 boundary this mission ships.

The repo should come out of this WP with one consistent story:

- the next Stage 2 foundation is domain-aware input resolution
- BMI is the first proof consumer
- observation and profile resolvers ship now
- nutrition and supplement domains remain declared but unresolved until real rows
  exist
- answer families remain closed unless a later mission deliberately opens them

## Owned Surface

- `src/premura/engine/CONTRACT.md`
- `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`
- `docs/architecture/STAGES.md`
- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: `WP01`, `WP02`, `WP03`
- Implementation command: `spec-kitty agent action implement WP04 --agent <name>`

## Context

This WP exists because the repo already had drift around this topic:

- “prepared series” language started to overfit to current observation metrics
- future domains were easy to talk about but not yet concretely resolvable
- Stage 2 and Stage 3 boundaries risked blurring again

The docs now need to make the corrected story unmistakable.

## Subtasks

### T014 - Update the engine contract

**Purpose**

Make the code-adjacent Stage 2 contributor contract reflect the new seam.

**Required changes**

- Update `src/premura/engine/CONTRACT.md`.
- Make clear that the next foundation is domain-aware input resolution.
- Add the trigger for when answer families should be extended later.

**Constraints**

- Keep the answer-family set closed in this mission.

### T015 - Add the domain-vs-shape rubric

**Purpose**

Give future contributors a review rule for deciding when a genuinely new domain
exists.

**Required changes**

- Update `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`.
- Add the agreed domain-vs-shape rubric.
- Keep the emphasis on meaning, not merely temporal shape.

### T016 - Update architecture and shipped-state docs

**Purpose**

Describe what now ships and what still does not.

**Required changes**

- Update `docs/architecture/STAGES.md`.
- Update `docs/operations/STATUS.md`.
- Describe:
  - the shipped input-resolution seam
  - observation + profile resolvers now
  - BMI as proof consumer
  - nutrition/supplement domains declared but unresolved

### T017 - Realign planning docs

**Purpose**

Make future analytical planning start from the corrected Stage 2 foundation.

**Required changes**

- Update `docs/product/ROADMAP.md`.
- Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`.
- Remove or replace lingering prepared-series framing.
- Keep Stage 3 statistical tooling explicitly later in the sequence.

## Validation Strategy

Primary checks for this WP:

- maintainer review of the six owned files for consistency
- confirm the same boundary is stated in engine contract, architecture docs,
  shipped-state docs, and planning docs

Expected outcomes:

- one consistent Stage 2 boundary story across doc layers
- no stale prepared-series framing
- no overclaim about intake resolver support

## Definition Of Done

- The engine contract reflects domain-aware input resolution.
- The semantic contract includes the domain-vs-shape rubric.
- Architecture and status docs describe the shipped seam accurately.
- Planning docs start future analytical work from the corrected Stage 2 basis.

## Risks And Watchouts

- Overstating unsupported intake-domain behavior as if it were fully shipped.
- Leaving one stale prepared-series phrasing behind in a key doc.
- Implying that answer-family growth is now open-ended.

## Reviewer Guidance

Review this WP for consistency and honesty, not prose polish alone.

Ask:

1. Do all six files tell the same boundary story? 
2. Is BMI clearly framed as proof scope? 
3. Are future intake domains represented without being overstated as supported?

## Activity Log

- 2026-05-28T08:13:11Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
