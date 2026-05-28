# Tasks: Model Intake And Profile Context

**Mission**: `model-intake-and-profile-context-01KSMN80`
**Mission ID**: `01KSMN80WBKTQTX18MH7D72SFM`
**Generated**: `2026-05-27T12:27:28Z`
**Planning Branch**: `master`
**Merge Target**: `master`
**Feature Dir**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/model-intake-and-profile-context-01KSMN80`

## Branch Context

- Current branch at task generation: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- Branches match expected planning context: `true`
- Branch strategy: planning artifacts were generated on `master`; execution worktrees are allocated later per computed lane from `lanes.json`, and all completed work merges back into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt | Estimated Prompt Size |
|---|---|---|---|---|---|
| WP01 | Authoritative Profile And Intake Contract Surface | High | None | `tasks/WP01-authoritative-profile-and-intake-contract-surface.md` | ~300 lines |
| WP02 | Profile And Intake Contract Validation Harness | High | WP01 | `tasks/WP02-profile-and-intake-contract-validation-harness.md` | ~260 lines |
| WP03 | Architecture And Engine Boundary Alignment | High | WP01 | `tasks/WP03-architecture-and-engine-boundary-alignment.md` | ~300 lines |
| WP04 | Decision Record And Product Planning Alignment | Medium | WP01, WP03 | `tasks/WP04-decision-record-and-product-planning-alignment.md` | ~280 lines |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add a new authoritative architecture document that defines the three first-class domains, their meanings, and their boundaries against observation history and note history. | WP01 |  | [D] |
| T002 | Add a machine-readable entity contract file for profile, nutrition, supplement, and dependency entities with required fields and meanings. | WP01 | [D] |
| T003 | Add a machine-readable classification and overlap example file that makes one-home mapping and overlap cases explicit. | WP01 | [D] |
| T004 | Add a machine-readable invariant file that encodes the positive invariants and concrete violation examples the reviewers should enforce. | WP01 | [D] |
| T005 | Add a machine-readable dependency declaration contract file for future Stage 2 and Stage 3 consumers. | WP01 | [D] |
| T006 | Add black-box tests that load the shipped contract artifacts and verify they are internally complete, parseable, and mutually consistent. | WP02 |  | [D] |
| T007 | Add invariant-oriented tests for one-home classification, overlap distinctions, visible supersession paths, and the no-fabrication rule for partial knowledge. | WP02 |  | [D] |
| T008 | Add dependency-contract tests that reject implicit prerequisites and confirm the shipped contract stays domain-focused rather than drifting into transport/API placeholders. | WP02 |  | [D] |
| T009 | Update `docs/architecture/STAGES.md` so the four-stage model names baseline profile context and intake data as distinct semantic domains rather than forcing them into observations or notes. | WP03 |  | [D] |
| T010 | Update `docs/architecture/STAGES.md` boundary language and examples so profile assertions, intake records, and observations remain distinct and back-door modeling is explicitly rejected. | WP03 |  | [D] |
| T011 | Update `docs/architecture/UPDATE_STRATEGY.md` to explain how profile/intake corrections and supersessions differ from rebuild-oriented changes to observation history. | WP03 |  | [D] |
| T012 | Update `src/premura/engine/CONTRACT.md` so future signals must declare profile and intake prerequisites explicitly and may not rely on opportunistic measurement fallbacks. | WP03 |  | [D] |
| T013 | Extend `tests/test_engine_contract.py` to lock the new dependency-declaration guidance and its discoverability from the engine-side contract. | WP03 |  | [D] |
| T014 | Add a design decision note capturing the ports/adapters decision: storage stays flexible, semantics stay strict at the contract boundary. | WP04 |  | [D] |
| T015 | Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so future implementation work starts from the new contract baseline and not from the unresolved issue-`#6` framing alone. | WP04 | [D] |
| T016 | Update `docs/product/ROADMAP.md` to sequence follow-on work from the new domain contract, including the need for machine-checkable review gates. | WP04 | [D] |
| T017 | Update `docs/history/product/ROADMAP_BOOTSTRAP_PLAN.md` so the backlog language around issue `#6` reflects the broader profile-plus-intake contract now being defined. | WP04 | [D] |
| T018 | Update `docs/history/product/VISION.md` lightly so it acknowledges the new contract seam without overstating shipped user-facing capability. | WP04 | [D] |

## Work Packages

### WP01 - Authoritative Profile And Intake Contract Surface

- Prompt: `tasks/WP01-authoritative-profile-and-intake-contract-surface.md`
- Goal: ship the authoritative repo-level contract surface that later implementations and agent reviewers will treat as the stable semantic source of truth.
- Priority: High
- Independent validation: the authoritative contract doc and the machine-readable contract files exist, parse cleanly, and agree on the core entities, examples, invariants, and dependency declaration shape.
- Dependencies: None.
- Owned files: `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`, `docs/architecture/contracts/profile_and_intake_entities.yaml`, `docs/architecture/contracts/profile_and_intake_examples.yaml`, `docs/architecture/contracts/profile_and_intake_invariants.yaml`, `docs/architecture/contracts/profile_and_intake_dependencies.yaml`
- Estimated prompt size: ~300 lines

Included subtasks:
- [x] T001 Add a new authoritative architecture document that defines the three first-class domains, their meanings, and their boundaries against observation history and note history. (WP01)
- [x] T002 Add a machine-readable entity contract file for profile, nutrition, supplement, and dependency entities with required fields and meanings. (WP01)
- [x] T003 Add a machine-readable classification and overlap example file that makes one-home mapping and overlap cases explicit. (WP01)
- [x] T004 Add a machine-readable invariant file that encodes the positive invariants and concrete violation examples the reviewers should enforce. (WP01)
- [x] T005 Add a machine-readable dependency declaration contract file for future Stage 2 and Stage 3 consumers. (WP01)

Implementation sketch:
1. Translate the planning artifacts in `data-model.md` and `contracts/` into a repo-level authoritative surface under `docs/architecture/`.
2. Keep the prose doc and the YAML contract files tightly aligned: the prose explains the meaning, the YAML makes it reviewable and machine-consumable.
3. Make the one-home mapping, overlap cases, positive invariants, and dependency declaration shape explicit enough that later tests can fail on drift.
4. Preserve storage agnosticism: define meanings and requirements, not tables or migrations.

Parallel opportunities:
- T002, T003, T004, and T005 are parallel-safe once the prose document outline from T001 is fixed, because they live in separate YAML files with distinct concerns.

Risks:
- The doc could accidentally drift into storage prescription, which would violate the planning decision.
- The YAML could become a second, inconsistent contract if it is not kept tightly aligned with the prose surface.
- Overlap examples could be too sparse, leaving agent reviewers room to improvise.

Reviewer focus:
- Confirm the contract is semantic, not storage-prescriptive.
- Confirm each named example has one canonical home.
- Confirm the invariants are positive, load-bearing rules rather than an open-ended list of taste-based warnings.

### WP02 - Profile And Intake Contract Validation Harness

- Prompt: `tasks/WP02-profile-and-intake-contract-validation-harness.md`
- Goal: make the new contract machine-reviewable so agent reviewers can reject drift without debating prose intent.
- Priority: High
- Independent validation: a dedicated contract test suite loads the authoritative artifacts and fails when entity coverage, overlap examples, invariants, or dependency declarations drift out of sync.
- Dependencies: WP01.
- Owned files: `tests/test_profile_intake_contracts.py`
- Estimated prompt size: ~260 lines

Included subtasks:
- [x] T006 Add black-box tests that load the shipped contract artifacts and verify they are internally complete, parseable, and mutually consistent. (WP02)
- [x] T007 Add invariant-oriented tests for one-home classification, overlap distinctions, visible supersession paths, and the no-fabrication rule for partial knowledge. (WP02)
- [x] T008 Add dependency-contract tests that reject implicit prerequisites and confirm the shipped contract stays domain-focused rather than drifting into transport/API placeholders. (WP02)

Implementation sketch:
1. Load the authoritative prose/YAML contract artifacts through file reads rather than internal helper mocks.
2. Assert the basic completeness and alignment first: all expected artifacts exist, parse, and cover the entities/invariants promised in planning.
3. Add focused tests for the hardest drift cases: dual classification, overlap collapse, hidden supersession, and undeclared prerequisites.
4. Keep the tests black-box with respect to implementation structure: they validate the shipped contract artifacts as external surfaces.

Parallel opportunities:
- None inside this WP; the tests should evolve as one coherent harness once WP01 is complete.

Risks:
- Tests could devolve into brittle wording snapshots instead of validating the load-bearing semantics.
- Tests could accidentally encode a storage shape even though the contract intentionally does not.
- A too-weak harness would give false confidence and leave agent review subjective.

Reviewer focus:
- Confirm the tests enforce semantics, not incidental phrasing.
- Confirm the failing modes correspond to the positive invariants and not just formatting preferences.
- Confirm the contract remains domain-focused and transport-agnostic.

### WP03 - Architecture And Engine Boundary Alignment

- Prompt: `tasks/WP03-architecture-and-engine-boundary-alignment.md`
- Goal: align the shipped architecture docs and engine contributor contract so future implementations know where profile/intake work belongs and how to declare dependencies on it.
- Priority: High
- Independent validation: the stage-boundary docs and engine contributor contract all tell the same story about the new domains, correction behavior, and explicit dependency declarations.
- Dependencies: WP01.
- Owned files: `docs/architecture/STAGES.md`, `docs/architecture/UPDATE_STRATEGY.md`, `src/premura/engine/CONTRACT.md`, `tests/test_engine_contract.py`
- Estimated prompt size: ~300 lines

Included subtasks:
- [x] T009 Update `docs/architecture/STAGES.md` so the four-stage model names baseline profile context and intake data as distinct semantic domains rather than forcing them into observations or notes. (WP03)
- [x] T010 Update `docs/architecture/STAGES.md` boundary language and examples so profile assertions, intake records, and observations remain distinct and back-door modeling is explicitly rejected. (WP03)
- [x] T011 Update `docs/architecture/UPDATE_STRATEGY.md` to explain how profile/intake corrections and supersessions differ from rebuild-oriented changes to observation history. (WP03)
- [x] T012 Update `src/premura/engine/CONTRACT.md` so future signals must declare profile and intake prerequisites explicitly and may not rely on opportunistic measurement fallbacks. (WP03)
- [x] T013 Extend `tests/test_engine_contract.py` to lock the new dependency-declaration guidance and its discoverability from the engine-side contract. (WP03)

Implementation sketch:
1. Update `STAGES.md` first so the repo’s primary architecture story explicitly names the new contract seam.
2. Tighten the boundary examples and anti-pattern language there before touching update semantics.
3. Update `UPDATE_STRATEGY.md` so correction/supersession semantics for profile and intake do not get conflated with rebuild flows for observations.
4. Update the engine contributor contract to require explicit dependency declarations and forbid hidden fallbacks.
5. Add contract tests that keep that guidance discoverable and reviewable.

Parallel opportunities:
- T011 and T012 can overlap after the main boundary wording in `STAGES.md` is settled, because they apply that decision to separate surfaces.

Risks:
- `STAGES.md` could accidentally imply that profile/intake are new execution stages rather than new semantic domains.
- `UPDATE_STRATEGY.md` could muddle correction semantics with destructive rebuild semantics.
- The engine contract could imply implementation support that this mission still does not ship.

Reviewer focus:
- Confirm the four-stage execution model stays intact.
- Confirm the repo now explicitly forbids back-dooring profile/intake semantics into measurement history.
- Confirm the engine contract requires declarations, not assumptions.

### WP04 - Decision Record And Product Planning Alignment

- Prompt: `tasks/WP04-decision-record-and-product-planning-alignment.md`
- Goal: capture the architectural decision and realign the product-planning docs so later missions start from the new contract baseline.
- Priority: Medium
- Independent validation: the design decision note and product-planning docs consistently describe the ports/adapters choice, the invariant-first review strategy, and the follow-on work now unlocked or still deferred.
- Dependencies: WP01, WP03.
- Owned files: `docs/adr/0005-profile-and-intake-contract.md`, `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, `docs/product/ROADMAP.md`, `docs/history/product/ROADMAP_BOOTSTRAP_PLAN.md`, `docs/history/product/VISION.md`
- Estimated prompt size: ~280 lines

Included subtasks:
- [x] T014 Add a design decision note capturing the ports/adapters decision: storage stays flexible, semantics stay strict at the contract boundary. (WP04)
- [x] T015 Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so future implementation work starts from the new contract baseline and not from the unresolved issue-`#6` framing alone. (WP04)
- [x] T016 Update `docs/product/ROADMAP.md` to sequence follow-on work from the new domain contract, including the need for machine-checkable review gates. (WP04)
- [x] T017 Update `docs/history/product/ROADMAP_BOOTSTRAP_PLAN.md` so the backlog language around issue `#6` reflects the broader profile-plus-intake contract now being defined. (WP04)
- [x] T018 Update `docs/history/product/VISION.md` lightly so it acknowledges the new contract seam without overstating shipped user-facing capability. (WP04)

Implementation sketch:
1. Record the architectural decision first in a design decision note so the follow-on docs can point to one clear decision.
2. Update the detailed planning document next, since it is the main source for future mission sequencing.
3. Update roadmap-facing docs after that so backlog framing and near-term work order inherit the new contract baseline.
4. Keep the vision change light and non-diagnostic; it should acknowledge the seam, not claim a user-facing feature shipped.

Parallel opportunities:
- T015, T016, T017, and T018 are parallel-safe once the design decision note from T014 is in place, because they touch separate docs with different audiences.

Risks:
- The docs could overclaim that user-facing profile/intake functionality now exists when the mission only defines the contract.
- The issue-`#6` framing could become inconsistent across planning docs if one file still describes the old narrower gap.
- The design decision note could repeat the whole spec instead of recording the specific winning choice and why it won.

Reviewer focus:
- Confirm the decision note records the contract-vs-storage split clearly.
- Confirm the product docs now start from the resolved boundary question, not the old ambiguity.
- Confirm no doc overstates shipped runtime behavior.
