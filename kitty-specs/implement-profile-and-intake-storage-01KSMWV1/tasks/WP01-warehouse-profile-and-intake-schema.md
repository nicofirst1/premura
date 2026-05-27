---
work_package_id: WP01
title: Warehouse Profile And Intake Schema
dependencies: []
requirement_refs:
- FR-001
- FR-007
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-profile-and-intake-storage-01KSMWV1
base_commit: 5cddbc88f021046f2737584ce2fecbab9073d6c4
created_at: '2026-05-27T14:45:00.335496+00:00'
subtasks:
- T001
- T002
- T003
shell_pid: "61340"
agent: "claude:opus:python-reviewer:reviewer"
history:
- timestamp: '2026-05-27T14:35:44Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/store/
execution_mode: code_change
owned_files:
- src/premura/store/migrations/004_profile_intake.sql
- tests/test_profile_intake_migration.py
tags: []
---

# Work Package Prompt: WP01 - Warehouse Profile And Intake Schema

## Objective

Make the one-home rule real in DuckDB before any runtime write surface is added.

This WP is the storage foundation for the whole mission. If the warehouse shape
is vague or too generic here, later code will drift back toward
`hp.fact_measurement`, `hp.fact_interval`, or note storage as shortcuts.

The key requirement is simple:

- separate profile, nutrition, and supplement storage from observation history,
- preserve provenance and supersession semantics from day one.

## Owned Surface

- `src/premura/store/migrations/004_profile_intake.sql`
- `tests/test_profile_intake_migration.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP01 --agent <name>`

## Context

The planning artifacts define the storage shape at a conceptual level:

- `spec.md` requires separate persistent homes for profile context, nutrition
  intake, and supplement intake, with no back-door reuse of observation history.
- `plan.md` chooses concrete storage in this mission and points to
  `src/premura/store/migrations/004_profile_intake.sql` as the storage entry
  point.
- `data-model.md` names the planned entities and their relationships:
  `ProfileCaptureSession`, `ProfileContextAssertion`, `NutritionIntakeEvent`,
  `NutritionIntakeItem`, `NutritionQuantity`, `SupplementIntakeEvent`,
  `SupplementItem`, and `SupplementDose`.

This WP turns those planning artifacts into real warehouse tables.

## Subtasks

### T001 - Add the concrete profile/intake migration

**Purpose**

Create the real warehouse tables for the new domains.

**Required changes**

- Add `src/premura/store/migrations/004_profile_intake.sql`.
- Create the tables needed for:
  - profile capture sessions
  - profile context assertions
  - nutrition events/items/quantities
  - supplement events/items/doses
- Include the provenance, timestamps, and supersession fields from
  `data-model.md`.

**Design guidance**

- Use explicit table names under `hp.` rather than a generic JSON bucket.
- Make supersession/history possible for profile assertions.
- Preserve raw payload columns where the model calls for them.

### T002 - Encode one-home separation in the schema itself

**Purpose**

Prevent later code from using observation or note storage as the easy path.

**Required changes**

- Make nutrition and supplement storage distinct from each other and from
  `hp.fact_measurement`, `hp.fact_interval`, and `hp.fact_clinical_note`.
- Include the dedupe/provenance columns needed for future parser-driven writes.
- Add indexes or uniqueness constraints where later persistence will rely on
  them, especially for dedupe keys and parent-child joins.

**Constraints**

- Do not modify the older observation tables in this migration.
- Do not add convenience columns that collapse nutrition and supplement meaning.

### T003 - Add migration-level verification

**Purpose**

Prove the new migration applies cleanly and does not damage the existing
warehouse boot path.

**Required changes**

- Add `tests/test_profile_intake_migration.py`.
- Initialize a fresh warehouse through the public initialization path.
- Assert that:
  - the new profile/nutrition/supplement tables exist
  - the existing fact tables still exist
  - the new migration can run idempotently through the normal migration loader

**Testing guidance**

- Keep the test black-box with respect to migration execution: use the normal
  warehouse initialization path rather than calling private SQL fragments.

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q tests/test_profile_intake_migration.py
```

Expected outcomes:

- The warehouse initializes successfully with the new migration.
- All expected new tables are present.
- Existing observation tables remain present and unchanged in role.

## Definition Of Done

- `004_profile_intake.sql` exists and creates the planned domain tables.
- The schema makes one-home separation concrete rather than optional.
- A migration test proves the warehouse initializes cleanly with the new schema.

## Risks And Watchouts

- The biggest failure mode is slipping back into a pseudo-observation schema.
- The second biggest failure mode is under-specifying keys/relationships so later
  persistence code has to rewrite the migration.
- Avoid putting business validation that belongs in Python into the migration if
  it will make later writes brittle.

## Reviewer Guidance

Review this WP as a storage-shape decision.

Ask:

1. Does the schema make the one-home rule easier to obey?
2. Is profile history append/supersede capable rather than overwrite-based?
3. Are nutrition and supplement records clearly distinct in storage?

## Activity Log

- 2026-05-27T14:35:44Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T14:45:01Z – claude:opus:python-implementer:implementer – shell_pid=91499 – Assigned agent via action command
- 2026-05-27T14:51:44Z – claude:opus:python-implementer:implementer – shell_pid=91499 – Ready for review: migration 004 adds explicit profile/nutrition/supplement tables with supersession + dedupe + FK semantics; migration test green via public init path; full suite (205) passes
- 2026-05-27T14:52:13Z – claude:opus:python-reviewer:reviewer – shell_pid=61340 – Started review via action command
- 2026-05-27T14:55:32Z – claude:opus:python-reviewer:reviewer – shell_pid=61340 – Review passed: migration 004_profile_intake.sql creates all 8 data-model tables (profile_capture_session, profile_context_assertion, nutrition_intake_event/item/quantity, supplement_intake_event/item/dose) under hp. with provenance, UNIQUE dedupe_key, FK parent-child chains, CHECK constraints, and append/supersede semantics (supersedes_assertion_id + effective window). No JSON catch-all; older observation/note migrations (001/003) untouched. Verified live wiring: run_migrations globs all *.sql in premura.store.migrations and 004 sits there, so initialize() discovers it automatically (not dead code); tests use the public duck.initialize path. Independently ran: 12/12 WP tests pass, full suite 205 passed. test_store.py out-of-scope edit is minimal and correct (adds exactly the 8 new table names to the alphabetical expected-tables list, no other assertions altered, no regressions hidden). Note: 9 repo-level ruff errors exist but are pre-existing in test_mcp_signal_tools.py/test_sleep_as_android.py (confirmed on base branch), untouched by WP01; WP01-owned files + test_store.py are ruff-clean.
