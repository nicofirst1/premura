# Tasks: Implement Profile And Intake Storage

**Mission**: `implement-profile-and-intake-storage-01KSMWV1`
**Mission ID**: `01KSMWV1HHYTTKJF053AVXSK9K`
**Generated**: `2026-05-27T14:35:44Z`
**Planning Branch**: `master`
**Merge Target**: `master`
**Feature Dir**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-profile-and-intake-storage-01KSMWV1`

## Branch Context

- Current branch at task generation: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- Branches match expected planning context: `true`
- Branch strategy: planning artifacts were generated on `master`; execution worktrees are allocated later per computed lane from `lanes.json`, and all completed work merges back into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt | Estimated Prompt Size |
|---|---|---|---|---|---|
| WP01 | Warehouse Profile And Intake Schema | High | None | `tasks/WP01-warehouse-profile-and-intake-schema.md` | ~260 lines |
| WP02 | Persistence Layer And Parser Intake Seam | High | WP01 | `tasks/WP02-persistence-layer-and-parser-intake-seam.md` | ~330 lines |
| WP03 | Agent-Mediated Profile Capture Surface | High | WP02 | `tasks/WP03-agent-mediated-profile-capture-surface.md` | ~300 lines |
| WP04 | Documentation And Shipped-State Alignment | Medium | WP02, WP03 | `tasks/WP04-documentation-and-shipped-state-alignment.md` | ~260 lines |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add a new DuckDB migration that creates separate profile-capture, profile-assertion, nutrition-intake, and supplement-intake tables with the provenance and supersession columns planned for this mission. | WP01 |  | [D] |
| T002 | Encode one-home separation directly in the migration shape by giving nutrition and supplement records their own event/item/quantity or dose tables rather than reusing observation or note tables. | WP01 |  | [D] |
| T003 | Add migration-level verification that warehouse initialization applies the new schema cleanly and leaves the existing observation tables intact. | WP01 |  | [D] |
| T004 | Add runtime profile-field support loading so the bounded allowlist from planning becomes an enforceable application surface rather than documentation only. | WP02 |  | [D] |
| T005 | Add `src/premura/store/profile_intake.py` with the concrete persistence service for bounded profile capture and parser-ready intake persistence. | WP02 |  | [D] |
| T006 | Extend `src/premura/parsers/base.py` with normalized nutrition/supplement persistence types that future parsers can emit outside the current `IngestBatch` observation path. | WP02 | [D] |
| T007 | Update `src/premura/parsers/CONTRACT.md` so parser contributors know when to emit normalized intake records instead of `IngestBatch` measurements or notes. | WP02 | [D] |
| T008 | Add persistence and parser-contract tests for profile supersession, bounded field rejection, partial intake records, and one-home separation. | WP02 |  | [D] |
| T009 | Add MCP helpers in `src/premura/mcp/server.py` for listing supported profile fields and recording bounded profile assertions through the new persistence service. | WP03 |  |
| T010 | Register the new profile-capture tools on the default agent-safe MCP surface in `src/premura/mcp/entrypoint.py`. | WP03 |  |
| T011 | Add thin CLI fallback commands in `src/premura/cli.py` that mirror the MCP schema and record operations for testing and expert fallback use. | WP03 |  |
| T012 | Add black-box tests that drive the supported profile schema and record flows through MCP/CLI surfaces and verify unsupported fields such as `age` are rejected explicitly. | WP03 |  |
| T013 | Update doctrine-facing docs so the agent-mediated profile path and parser/plugin intake path are explicit enough that future planning does not regress back to a human-form or one-off-importer assumption. | WP04 | [P] |
| T014 | Update architecture and status docs so they describe the newly shipped concrete storage and profile capture path without claiming built-in nutrition/supplement importers exist. | WP04 | [P] |
| T015 | Update product planning docs so they treat future nutrition/supplement work as parser/plugin source adaptation over a shipped storage seam rather than as another boundary-definition exercise. | WP04 | [P] |
| T016 | Add a concrete storage design decision note that records why this mission chose separate domain tables plus agent-mediated profile capture instead of a generic context blob or measurement-table reuse. | WP04 | [P] |

## Work Packages

### WP01 - Warehouse Profile And Intake Schema

- Prompt: `tasks/WP01-warehouse-profile-and-intake-schema.md`
- Goal: make the one-home rule concrete in DuckDB by adding the separate warehouse tables this mission needs before any runtime write surface is exposed.
- Priority: High
- Independent validation: `duck.initialize(...)` applies the new migration successfully, the expected profile/nutrition/supplement tables exist, and the pre-existing observation tables remain intact.
- Dependencies: None.
- Owned files: `src/premura/store/migrations/004_profile_intake.sql`, `tests/test_profile_intake_migration.py`
- Estimated prompt size: ~260 lines

Included subtasks:
- [x] T001 Add a new DuckDB migration that creates separate profile-capture, profile-assertion, nutrition-intake, and supplement-intake tables with the provenance and supersession columns planned for this mission. (WP01)
- [x] T002 Encode one-home separation directly in the migration shape by giving nutrition and supplement records their own event/item/quantity or dose tables rather than reusing observation or note tables. (WP01)
- [x] T003 Add migration-level verification that warehouse initialization applies the new schema cleanly and leaves the existing observation tables intact. (WP01)

Implementation sketch:
1. Design the `004_profile_intake.sql` schema directly from `data-model.md`, not from convenience with existing fact tables.
2. Keep profile capture history explicit through session and assertion tables, including supersession columns.
3. Add dedicated nutrition and supplement event/item/value tables with provenance and dedupe columns so later parser work has a real landing zone.
4. Add a focused migration test that checks for the new tables/sequences and also confirms `hp.fact_measurement`, `hp.fact_interval`, and `hp.fact_clinical_note` still exist untouched.

Parallel opportunities:
- None inside this WP. The migration and its verification should evolve together as one coherent storage foundation.

Risks:
- Accidentally recreating observation-like tables that still invite profile/intake drift.
- Missing supersession or provenance columns that later profile capture will need.
- A migration test that proves only existence, not separation from older storage paths.

Reviewer focus:
- Confirm the storage shape makes the one-home rule easier to enforce rather than easier to bypass.
- Confirm profile history is append/supersede oriented, not overwrite-in-place.
- Confirm the migration leaves older observation storage untouched.

### WP02 - Persistence Layer And Parser Intake Seam

- Prompt: `tasks/WP02-persistence-layer-and-parser-intake-seam.md`
- Goal: build the concrete runtime persistence service and parser-facing normalized intake seam on top of the new warehouse tables.
- Priority: High
- Independent validation: synthetic profile, nutrition, and supplement records can be persisted through the new service, unsupported profile fields are rejected, and parser-facing normalized types map cleanly into the new tables.
- Dependencies: WP01.
- Owned files: `src/premura/profile_fields.py`, `src/premura/store/profile_intake.py`, `src/premura/parsers/base.py`, `src/premura/parsers/CONTRACT.md`, `tests/test_profile_intake_persistence.py`, `tests/test_profile_intake_parser_contract.py`
- Estimated prompt size: ~330 lines

Included subtasks:
- [x] T004 Add runtime profile-field support loading so the bounded allowlist from planning becomes an enforceable application surface rather than documentation only. (WP02)
- [x] T005 Add `src/premura/store/profile_intake.py` with the concrete persistence service for bounded profile capture and parser-ready intake persistence. (WP02)
- [x] T006 Extend `src/premura/parsers/base.py` with normalized nutrition/supplement persistence types that future parsers can emit outside the current `IngestBatch` observation path. (WP02)
- [x] T007 Update `src/premura/parsers/CONTRACT.md` so parser contributors know when to emit normalized intake records instead of `IngestBatch` measurements or notes. (WP02)
- [x] T008 Add persistence and parser-contract tests for profile supersession, bounded field rejection, partial intake records, and one-home separation. (WP02)

Implementation sketch:
1. Add a small runtime module that turns the planned profile field allowlist into application-readable metadata.
2. Implement the persistence service with two clear entry points: one for bounded profile capture, one for normalized intake persistence.
3. Extend the parser seam with normalized intake record types that are intentionally separate from `Measurement`, `Interval`, and `ClinicalNote`.
4. Update the parser contract docs so future parser work knows when to stay in the old `IngestBatch` path and when to use the new intake persistence seam.
5. Add focused tests that prove profile supersession, partial intake persistence, and one-home behavior all work through public write/read surfaces.

Parallel opportunities:
- T006 and T007 can overlap after the target persistence shapes are clear from T005, because they touch separate parser-facing files.

Risks:
- Letting the new persistence service become an unbounded key/value writer rather than a bounded domain service.
- Making parser-facing types so loose that later source adapters still need to redesign storage.
- Reintroducing observation-history shortcuts from inside the store layer.

Reviewer focus:
- Confirm unsupported profile keys fail explicitly.
- Confirm nutrition and supplement persistence are concrete enough for later parser work but do not ship source-specific logic.
- Confirm tests exercise the service behavior rather than private helper internals.

### WP03 - Agent-Mediated Profile Capture Surface

- Prompt: `tasks/WP03-agent-mediated-profile-capture-surface.md`
- Goal: expose the bounded profile capture flow through the agent-safe MCP surface, with a thin CLI fallback for testing and expert fallback use.
- Priority: High
- Independent validation: the default MCP surface can list supported profile fields and record a bounded capture session; the CLI mirrors those operations; unsupported fields such as `age` are rejected explicitly.
- Dependencies: WP02.
- Owned files: `src/premura/mcp/server.py`, `src/premura/mcp/entrypoint.py`, `src/premura/cli.py`, `tests/test_profile_capture_tools.py`
- Estimated prompt size: ~300 lines

Included subtasks:
- [ ] T009 Add MCP helpers in `src/premura/mcp/server.py` for listing supported profile fields and recording bounded profile assertions through the new persistence service. (WP03)
- [ ] T010 Register the new profile-capture tools on the default agent-safe MCP surface in `src/premura/mcp/entrypoint.py`. (WP03)
- [ ] T011 Add thin CLI fallback commands in `src/premura/cli.py` that mirror the MCP schema and record operations for testing and expert fallback use. (WP03)
- [ ] T012 Add black-box tests that drive the supported profile schema and record flows through MCP/CLI surfaces and verify unsupported fields such as `age` are rejected explicitly. (WP03)

Implementation sketch:
1. Add runtime-facing server helpers that delegate to the persistence layer rather than reimplementing validation in the MCP layer.
2. Register those helpers on the default agent-safe MCP surface so profile capture follows the same product path as other agent-facing operations.
3. Add CLI wrappers that mirror the tool behavior closely enough for tests and expert fallback use.
4. Add black-box tests that use the public surfaces to validate happy path, provenance visibility, and unsupported-field rejection.

Parallel opportunities:
- T010 and T011 can overlap once the server helpers from T009 are stable, because they wire the same behavior into separate entry surfaces.

Risks:
- Exposing these tools only on the operator surface instead of the default agent-safe one.
- Duplicating validation between MCP and CLI instead of letting the persistence layer stay authoritative.
- Adding an unbounded record API that breaks the mission's bounded profile-capture rule.

Reviewer focus:
- Confirm the primary runtime path is agent-mediated MCP, not CLI-first.
- Confirm the CLI remains a thin mirror rather than a second independent implementation.
- Confirm unsupported fields fail with explicit, inspectable outcomes.

### WP04 - Documentation And Shipped-State Alignment

- Prompt: `tasks/WP04-documentation-and-shipped-state-alignment.md`
- Goal: align doctrine, architecture, status, and roadmap docs with the actually shipped implementation so future planning does not regress back into the earlier ambiguity.
- Priority: Medium
- Independent validation: the updated docs consistently describe agent-mediated profile capture as the shipped path, parser/plugin intake support as the follow-on path, and the concrete storage decision as already taken by this mission.
- Dependencies: WP02, WP03.
- Owned files: `docs/product/DOCTRINE.md`, `CONTEXT.md`, `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`, `docs/architecture/STAGES.md`, `docs/operations/STATUS.md`, `docs/product/ROADMAP.md`, `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, `docs/adr/0006-profile-intake-storage-and-capture.md`
- Estimated prompt size: ~260 lines

Included subtasks:
- [ ] T013 Update doctrine-facing docs so the agent-mediated profile path and parser/plugin intake path are explicit enough that future planning does not regress back to a human-form or one-off-importer assumption. (WP04)
- [ ] T014 Update architecture and status docs so they describe the newly shipped concrete storage and profile capture path without claiming built-in nutrition/supplement importers exist. (WP04)
- [ ] T015 Update product planning docs so they treat future nutrition/supplement work as parser/plugin source adaptation over a shipped storage seam rather than as another boundary-definition exercise. (WP04)
- [ ] T016 Add a concrete storage design decision note that records why this mission chose separate domain tables plus agent-mediated profile capture instead of a generic context blob or measurement-table reuse. (WP04)

Implementation sketch:
1. Start by updating doctrine and context wording so the agent-first capture assumption is unmistakable.
2. Update architecture and status docs next so the shipped behavior is clear to future contributors.
3. Realign product planning docs so future parser/plugin missions inherit the new baseline instead of re-opening the same question.
4. Capture the concrete storage/capture choice in a design decision note so later missions have a stable citation.

Parallel opportunities:
- T013, T014, T015, and T016 can overlap once WP02/WP03 are complete enough to know the shipped surface precisely, because they target different docs with different audiences.

Risks:
- Overstating nutrition/supplement source support before any parser mission ships.
- Updating only one doc layer and leaving contradictory guidance elsewhere.
- Turning the design decision note into a full implementation narrative instead of a short record of the winning choice.

Reviewer focus:
- Confirm the docs now make the default operator unmistakably the agent.
- Confirm the shipped/runtime claims are narrow and accurate.
- Confirm the design decision note records the concrete storage choice and why it beat the rejected alternatives.
