---
work_package_id: WP02
title: Persistence Layer And Parser Intake Seam
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-006
- FR-007
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-27T14:35:44Z'
subtasks:
- T004
- T005
- T006
- T007
- T008
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "32098"
history:
- timestamp: '2026-05-27T14:35:44Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/store/
execution_mode: code_change
owned_files:
- src/premura/profile_fields.py
- src/premura/store/profile_intake.py
- src/premura/parsers/base.py
- src/premura/parsers/CONTRACT.md
- tests/test_profile_intake_persistence.py
- tests/test_profile_intake_parser_contract.py
tags: []
---

# Work Package Prompt: WP02 - Persistence Layer And Parser Intake Seam

## Objective

Build the runtime persistence service and parser-facing normalized intake seam on
top of the new warehouse schema.

This WP is where the planning model becomes a reusable application boundary:

- bounded profile capture can be written safely,
- future nutrition/supplement parsers get a stable persistence target,
- later missions no longer need to reopen storage design.

## Owned Surface

- `src/premura/profile_fields.py`
- `src/premura/store/profile_intake.py`
- `src/premura/parsers/base.py`
- `src/premura/parsers/CONTRACT.md`
- `tests/test_profile_intake_persistence.py`
- `tests/test_profile_intake_parser_contract.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: `WP01`
- Implementation command: `spec-kitty agent action implement WP02 --agent <name>`

## Context

The planning artifacts choose two write paths:

1. `record_profile_context(...)` for bounded agent-mediated profile capture
2. `persist_intake_batch(...)` for normalized nutrition/supplement records from
   future parsers

The repo already has:

- an observation-oriented parser seam in `src/premura/parsers/base.py`
- a warehouse loader for observation batches in `src/premura/store/loader.py`

This WP must add a new intake-ready seam without forcing nutrition and
supplement records through the old observation path.

## Subtasks

### T004 - Add runtime profile-field support loading

**Purpose**

Turn the planned allowlist into a real runtime surface that code can enforce.

**Required changes**

- Add `src/premura/profile_fields.py`.
- Load or encode the bounded profile keys supported by this mission.
- Make the runtime surface explicit enough to answer:
  - which keys are supported
  - what typed value each key expects
  - which aliases must be rejected (for example `age`)

**Constraints**

- Keep this bounded to stable baseline profile facts.
- Do not create an open-ended profile key registry.

### T005 - Add the concrete persistence service

**Purpose**

Provide the store-layer API that writes profile assertions and normalized intake
records into the new tables.

**Required changes**

- Add `src/premura/store/profile_intake.py`.
- Implement the planned write paths:
  - `record_profile_context(...)`
  - `persist_intake_batch(...)`
- Include readback helpers if needed for tests or runtime inspection.
- Preserve provenance and effective-time semantics.

**Design guidance**

- Keep validation at the store boundary: unsupported profile fields should fail
  here, not later in the tool layer.
- Make profile supersession explicit rather than overwriting old assertions.

### T006 - Extend the parser seam for normalized intake records

**Purpose**

Give future parser/plugin missions concrete Python types to emit for nutrition
and supplement persistence.

**Required changes**

- Extend `src/premura/parsers/base.py` with normalized intake types that match
  the planning contract.
- Keep these types distinct from `Measurement`, `Interval`, and `ClinicalNote`.
- Include the validation needed to keep one-home separation intact.

**Constraints**

- Do not try to fold intake types back into `IngestBatch` observation rows.
- Keep the types source-agnostic and vendor-neutral.

### T007 - Update the parser contributor contract

**Purpose**

Tell future parser contributors how to use the new seam correctly.

**Required changes**

- Update `src/premura/parsers/CONTRACT.md`.
- Explain when a parser should:
  - emit `IngestBatch` observation rows
  - emit normalized intake persistence inputs
- Make clear that nutrition and supplement records do not belong in
  `Measurement`, `Interval`, or note storage just because those paths already
  exist.

### T008 - Add persistence and parser-contract tests

**Purpose**

Lock the new persistence seam and its one-home behavior with executable checks.

**Required changes**

- Add `tests/test_profile_intake_persistence.py`.
- Add `tests/test_profile_intake_parser_contract.py`.
- Cover at least:
  - bounded field acceptance for `birth_date`, `sex`, `standing_height_cm`
  - rejection of unsupported fields such as `age`
  - profile supersession history
  - partial nutrition quantities
  - supplement item/dose variants
  - parser-facing normalized type validation

**Testing guidance**

- Favor public store/persistence entry points over private helpers.
- Keep fixture data synthetic and PHI-free.

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q tests/test_profile_intake_persistence.py tests/test_profile_intake_parser_contract.py
```

Expected outcomes:

- Supported profile fields persist correctly.
- Unsupported fields fail explicitly.
- Nutrition and supplement records can persist through normalized inputs.
- Parser-facing types describe a real seam rather than a vague placeholder.

## Definition Of Done

- A runtime profile-field allowlist exists and is enforceable.
- The new store persistence service exists and supports both planned write paths.
- The parser seam includes normalized intake types for later parser/plugin work.
- Tests cover one-home separation, supersession, and bounded profile capture.

## Risks And Watchouts

- The biggest risk is turning `record_profile_context(...)` into an unrestricted
  attribute writer.
- Another risk is making intake types so underspecified that later parser work
  still has to redesign the seam.
- Avoid spreading validation rules across too many layers; the store boundary
  should stay authoritative.

## Reviewer Guidance

Review this WP as a boundary-implementation change.

Ask:

1. Does the store service enforce the bounded profile surface?
2. Could a future parser persist nutrition/supplement data without reopening the
   storage model?
3. Do the tests prove one-home behavior rather than just happy-path inserts?

## Activity Log

- 2026-05-27T14:35:44Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T14:56:14Z – claude:opus:python-implementer:implementer – shell_pid=84537 – Started implementation via action command
- 2026-05-27T15:05:09Z – claude:opus:python-implementer:implementer – shell_pid=84537 – Ready for review: persistence service (record_profile_context append/supersede + persist_intake_batch idempotent via dedupe_key) and normalized parser intake seam (IntakeBatch, distinct from IngestBatch). 42 new tests, full suite 247 passed, ruff clean on owned files.
- 2026-05-27T15:05:42Z – claude:opus:python-reviewer:reviewer – shell_pid=32098 – Started review via action command
- 2026-05-27T15:09:56Z – claude:opus:python-reviewer:reviewer – shell_pid=32098 – Review passed: bounded profile allowlist (birth_date/sex/standing_height_cm; age rejected as derived at store boundary), record_profile_context append/supersede never overwrites and validates before BEGIN, persist_intake_batch idempotent via dedupe_key UNIQUE (constraint-backed, proven by backstop test), IntakeBatch genuinely distinct from IngestBatch with structural one-home separation. 42 WP02 tests + 247 full suite pass; ruff clean on all 6 owned files; commit 8c65626 touched only its 6 owned files; cross-module seam wired (profile_intake imports parsers/base + profile_fields). Boundary-WP dead-code caveat accepted: production parser callers land in WP03/WP04 per criteria.
- 2026-05-27T16:35:35Z – claude:opus:python-reviewer:reviewer – shell_pid=32098 – Done override: Feature merged to master (commit 177d9ce); merge gate passed all-approved + risk + dependency checks
