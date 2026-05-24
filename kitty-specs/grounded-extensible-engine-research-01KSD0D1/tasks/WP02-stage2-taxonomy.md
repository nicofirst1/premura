---
work_package_id: WP02
title: Stage 2 Taxonomy
dependencies:
- WP01
requirement_refs:
- FR-002
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-24T13:02:16Z'
subtasks:
- T005
- T006
- T007
- T008
agent: "claude:opus:research-implementer:implementer"
shell_pid: "60085"
history:
- timestamp: '2026-05-24T13:02:16Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/
execution_mode: planning_artifact
owned_files:
- kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/02-stage2-taxonomy.md
tags: []
---

# Work Package Prompt: WP02 - Stage 2 Taxonomy

## Objective

Define the shared Stage 2 language for this mission: which health directions Premura should reason about first, which recurring user-question shapes matter, and which engine function families belong in Stage 2.

The output is `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/02-stage2-taxonomy.md`.

## Why This WP Exists

Without a shared taxonomy, later work will mix together user goals, engine responsibilities, Stage 3 tools, and Stage 4 teaching behavior. This WP keeps those concerns separate and turns the broad vision into a practical first-wave map.

This WP directly supports:

- `FR-002`
- downstream grounding and quick-win ranking work

## Owned Surface

- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/02-stage2-taxonomy.md`

Do not modify files outside this list.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP02 --agent <name>`

Do not begin this WP until WP01's baseline artifact is available in the assigned lane.

## Inputs You Should Reuse

- `research/01-repo-baseline.md` from WP01
- `docs/product/VISION.md`
- `docs/architecture/STAGES.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/operations/STATUS.md`

Use the normalized vocabulary from WP01 rather than inventing new terms.

## Subtasks

### T005 - Normalize first-wave health directions

**Purpose**

Turn the repo's broad health-direction ideas into a practical first-wave set for Stage 2 research.

**Required work**

- Start from the directions already named in repo docs.
- Choose a practical first-wave set, not a full medical taxonomy.
- Explain briefly why each chosen direction belongs in the first-wave set.

**Good outcome**

- A shortlist a maintainer can actually use when talking about Stage 2 scope.

### T006 - Enumerate recurring user-question shapes

**Purpose**

Make clear what kinds of questions Stage 2 is helping answer before talking about individual functions.

**Required work**

- For each chosen direction, list the recurring question shapes Stage 2 should answer first.
- Examples may include:
  - current status
  - trend over time
  - comparison to a baseline
  - change after an event or intervention
  - compound interpretation from multiple signals
- Keep the list focused on patterns, not one-off function ideas.

### T007 - Map question shapes to Stage 2 function families

**Purpose**

Turn user-question shapes into engine-level function families while protecting stage boundaries.

**Required work**

- Map each question shape to one or more function families.
- Explicitly note what belongs in Stage 2 versus what should remain in Stage 3 or Stage 4.
- Keep deterministic engine logic separate from:
  - Stage 3 statistics tooling
  - Stage 4 teaching and presentation

**Watchouts**

- Do not let the taxonomy become a tool menu.
- Do not let UI teaching patterns masquerade as engine functions.

### T008 - Draft the taxonomy artifact

**Purpose**

Package the direction, question-shape, and function-family work into one artifact later WPs can reference.

**Required work**

- Write `research/02-stage2-taxonomy.md`.
- Include:
  - chosen first-wave directions
  - recurring question shapes
  - function-family mapping
  - short examples for each layer
- Cite the repo sources that justify the first-wave scope.

## Validation Strategy

This WP is complete when:

- `research/02-stage2-taxonomy.md` exists.
- It clearly separates directions, question shapes, and function families.
- It explicitly distinguishes Stage 2 from Stage 3 and Stage 4 responsibilities.

## Definition Of Done

- First-wave directions normalized.
- Recurring question shapes listed.
- Function-family mapping documented.
- The artifact is concise and reusable by WP03 and WP05.

## Risks And Watchouts

- A taxonomy that is too broad will not guide real prioritization.
- A taxonomy that mixes stages will make the later contract and quick-win ranking incoherent.

## Reviewer Guidance

- Check that the direction set is practical rather than encyclopedic.
- Check that the function families clearly belong to Stage 2.
- Check that examples stay consistent with the vocabulary chosen in WP01.

## Activity Log

- 2026-05-24T13:15:20Z – claude:opus:research-implementer:implementer – shell_pid=60085 – Started implementation via action command
