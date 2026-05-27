---
work_package_id: WP03
title: Architecture And Engine Boundary Alignment
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-27T12:27:28Z'
subtasks:
- T009
- T010
- T011
- T012
- T013
agent: "claude:opus:reviewer:reviewer"
shell_pid: "6305"
history:
- timestamp: '2026-05-27T12:27:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- docs/architecture/STAGES.md
- docs/architecture/UPDATE_STRATEGY.md
- src/premura/engine/CONTRACT.md
- tests/test_engine_contract.py
tags: []
---

# Work Package Prompt: WP03 - Architecture And Engine Boundary Alignment

## Objective

Align the shipped architecture and contributor surfaces with the new profile and
intake contract.

The repo currently has a strong story for observed measurements, intervals,
notes, and Stage 2 signal boundaries. This WP updates that story so future work
knows exactly where profile/intake semantics belong and how dependencies on them
must be declared.

## Owned Surface

- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- `src/premura/engine/CONTRACT.md`
- `tests/test_engine_contract.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP03 --agent <name>`

## Context

The new contract surface from WP01 is authoritative, but it is not sufficient on
its own. The core repo docs and the engine contributor contract must tell the
same story, or future agents will still read contradictory guidance.

This WP must keep one distinction very clear:

- profile/intake are new semantic domains,
- not new execution stages.

## Subtasks

### T009 - Update STAGES.md to name the new semantic domains

**Purpose**

Make the main architecture document acknowledge the new boundary without
rewriting the four-stage model.

**Required changes**

- Update `docs/architecture/STAGES.md` to explain where baseline profile context,
  nutrition intake, and supplement intake sit relative to the existing
  observation- and note-oriented model.
- Keep the four execution stages intact.
- Make clear that the new domains are semantic categories the stages may work
  with later, not new runtime layers.

### T010 - Tighten boundary examples and anti-patterns in STAGES.md

**Purpose**

Prevent future back-door modeling by making the overlap and anti-pattern cases
explicit in the main architecture narrative.

**Required changes**

- Add or revise examples covering:
  - declared vs measured height
  - meal calories vs wearable kcal
  - supplement dose vs body observation
- State clearly that profile and intake semantics must not be smuggled into
  `fact_measurement`, `fact_interval`, or generic note storage just because those
  paths already exist.

### T011 - Update UPDATE_STRATEGY.md for correction and supersession semantics

**Purpose**

Show how later profile/intake updates differ from rebuild-oriented changes to the
existing observation warehouse.

**Required changes**

- Update `docs/architecture/UPDATE_STRATEGY.md` to explain the intended update
  shape for profile assertions and intake corrections.
- Keep the existing rebuild/re-ingest story for observation history intact.
- Make clear that correction/supersession semantics are not the same thing as
  raw-history rebuild semantics.

### T012 - Update the engine contributor contract for explicit prerequisites

**Purpose**

Make future signal contributors declare profile/intake dependencies rather than
assuming opportunistic data presence.

**Required changes**

- Update `src/premura/engine/CONTRACT.md`.
- Add guidance that future signals must explicitly declare profile and intake
  prerequisites when they need them.
- Reject hidden fallbacks such as "use a measurement if it happens to be there"
  in place of a declared dependency.
- Keep the current non-diagnostic and evidence-boundary guidance intact.

### T013 - Extend engine contract tests

**Purpose**

Make the contributor-contract change reviewable and discoverable.

**Required changes**

- Extend `tests/test_engine_contract.py`.
- Assert that the engine-side contract now names explicit profile/intake
  prerequisite declarations and that the guidance is discoverable through the
  shipped contract surface.
- Keep the tests black-box with respect to internal implementation structure.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest tests/test_engine_contract.py -q
```

Manual spot-checks:

1. Read `docs/architecture/STAGES.md` and confirm the stage model is still four
   stages.
2. Read the new examples and confirm they distinguish semantic domains rather
   than inventing new runtime layers.

## Definition Of Done

- The main architecture docs explicitly name the new semantic boundary.
- The update-strategy doc explains correction/supersession semantics without
  collapsing them into rebuild flows.
- The engine contributor contract requires explicit profile/intake prerequisites.
- Contract tests lock that guidance in place.

## Risks And Watchouts

- The most likely mistake is to accidentally imply storage support or runtime
  behavior that is still future work.
- Another likely mistake is to describe the new domains as a fifth stage.
- Be careful not to weaken the current Stage 2 non-diagnostic boundary while
  adding dependency guidance.

## Reviewer Guidance

Focus review on consistency:

1. Does `STAGES.md` now tell the same story as the new contract surface?
2. Does `UPDATE_STRATEGY.md` preserve the existing rebuild story while making the
   new correction story explicit?
3. Does `engine/CONTRACT.md` turn hidden assumptions into declared
   prerequisites?

## Activity Log

- 2026-05-27T12:27:28Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T12:50:04Z – claude:opus:implementer:implementer – shell_pid=87779 – Started implementation via action command
- 2026-05-27T12:54:57Z – claude:opus:implementer:implementer – shell_pid=87779 – Ready for review
- 2026-05-27T12:55:32Z – claude:opus:reviewer:reviewer – shell_pid=6305 – Started review via action command
- 2026-05-27T12:58:44Z – claude:opus:reviewer:reviewer – shell_pid=6305 – Review passed: STAGES/UPDATE_STRATEGY/CONTRACT aligned with WP01 profile/intake contract; four-stage model and non-diagnostic boundary preserved; engine contract references real dependency-declaration shape; 23 engine-contract tests + 193 full suite green
