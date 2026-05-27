---
work_package_id: WP04
title: Documentation And Shipped-State Alignment
dependencies:
- WP02
- WP03
requirement_refs:
- FR-001
- FR-009
- FR-010
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-27T14:35:44Z'
subtasks:
- T013
- T014
- T015
- T016
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "51813"
history:
- timestamp: '2026-05-27T14:35:44Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/product/DOCTRINE.md
- CONTEXT.md
- docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md
- docs/architecture/STAGES.md
- docs/operations/STATUS.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- docs/adr/0006-profile-intake-storage-and-capture.md
tags: []
---

# Work Package Prompt: WP04 - Documentation And Shipped-State Alignment

## Objective

Align doctrine, architecture, shipped-status, and roadmap docs with the actual
implementation this mission adds.

This WP exists because the project already experienced drift: the doctrine said
"agent-first," but planning still slipped into human-form/manual-entry thinking.
After WP02 and WP03 land, the docs should make the shipped story unmistakable:

- profile capture is agent-mediated,
- nutrition/supplement storage exists,
- nutrition/supplement source adaptation is still parser/plugin follow-on work.

## Owned Surface

- `docs/product/DOCTRINE.md`
- `CONTEXT.md`
- `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`
- `docs/architecture/STAGES.md`
- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/adr/0006-profile-intake-storage-and-capture.md`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: `WP02`, `WP03`
- Implementation command: `spec-kitty agent action implement WP04 --agent <name>`

## Context

The repo now needs to express two different truths at once:

- storage and profile capture are now real,
- nutrition/supplement source adaptation is still future parser/plugin work.

The docs must not fall back into any of these wrong stories:

- humans fill out forms by default
- built-in MyFitnessPal or supplement import already exists
- the boundary question is still unresolved

## Subtasks

### T013 - Tighten doctrine and maintainer context wording

**Purpose**

Make the default operator and capture assumptions explicit enough to prevent the
same planning mistake from happening again.

**Required changes**

- Update `docs/product/DOCTRINE.md`.
- Update `CONTEXT.md`.
- Make clear that:
  - the agent is the default operational client
  - stable profile facts are captured through agent-mediated bounded interview
  - nutrition/supplement source support follows the parser/plugin path by
    default

### T014 - Update architecture and shipped-status docs

**Purpose**

Reflect the concrete storage and runtime behavior that now ships.

**Required changes**

- Update `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md` to point to the fact
  that concrete storage now exists while keeping the semantic contract intact.
- Update `docs/architecture/STAGES.md` to name the shipped agent-mediated profile
  capture path accurately.
- Update `docs/operations/STATUS.md` to describe what now works end-to-end.

**Constraints**

- Do not imply nutrition/supplement source importers now ship if they do not.

### T015 - Update product planning docs for the new baseline

**Purpose**

Make future mission sequencing inherit the shipped storage seam instead of
re-opening the same boundary question.

**Required changes**

- Update `docs/product/ROADMAP.md`.
- Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`.
- Reframe future work as:
  - parser/plugin source adaptation for nutrition/supplements
  - future profile-aware signals such as BMI/age-adjusted interpretation

### T016 - Add the concrete storage design decision note

**Purpose**

Record the specific implementation choice this mission made and why it won.

**Required changes**

- Add `docs/adr/0006-profile-intake-storage-and-capture.md`.
- Keep it short and decision-focused.
- Record that this mission chose:
  - separate concrete domain tables
  - agent-mediated bounded profile capture
  - parser/plugin follow-on work for nutrition/supplement source adaptation
- Name the rejected alternatives, including:
  - generic context blob / JSON bucket
  - measurement-table reuse
  - form-first or one-off importer-first assumptions

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q
```

Expected outcomes:

- The shipped docs consistently describe the new runtime/storage baseline.
- No doc claims nutrition/supplement importers already exist if they do not.
- The design decision note clearly records the winning implementation choice.

## Definition Of Done

- Doctrine/context wording is explicit enough to avoid future planning drift.
- Architecture/status docs match the implemented runtime/storage behavior.
- Product planning docs start from the new storage seam.
- A concrete storage/capture design decision note exists.

## Risks And Watchouts

- The main risk is overclaiming shipped capability for nutrition/supplement
  ingestion.
- Another risk is updating only one doc layer and leaving contradictory guidance
  elsewhere.
- The decision note should stay short; do not turn it into a second plan.

## Reviewer Guidance

Review this WP as a documentation-faithfulness change.

Ask:

1. Would a future planner still be likely to assume human-first forms?
2. Would a future contributor incorrectly believe built-in nutrition import now
   exists?
3. Do the docs consistently treat the storage question as resolved by this
   mission?

## Activity Log

- 2026-05-27T14:35:44Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T15:23:30Z – claude:opus:python-implementer:implementer – shell_pid=15618 – Started implementation via action command
- 2026-05-27T15:35:03Z – claude:opus:python-implementer:implementer – shell_pid=15618 – Ready for review: aligned doctrine/CONTEXT, profile-intake contract, STAGES, STATUS, ROADMAP, FULL_APP_DEVELOPMENT_PLAN, and added ADR 0006; all factual claims cross-checked against code; 260/260 pytest pass
- 2026-05-27T15:35:45Z – claude:opus:python-reviewer:reviewer – shell_pid=51813 – Started review via action command
- 2026-05-27T15:38:59Z – claude:opus:python-reviewer:reviewer – shell_pid=51813 – Review passed: docs-only commit b5ba05b touches exactly the 8 owned files. All factual claims cross-checked against code and match: 8 hp.* tables in 004_profile_intake.sql; allowlist birth_date/sex/standing_height_cm + age-rejected in profile_fields.py; MCP profile_context_supported_fields/record on default surface + CLI profile-fields/profile-record; provenance agent_profile_capture; tool counts default 8->10 and operator 9->11 verified; standing_height reconciled to standing_height_cm with honest bridge line, no dangling refs; nutrition/supplement scoped as parser/plugin follow-on, BMI/age out-of-scope. pytest 260/260 pass.
