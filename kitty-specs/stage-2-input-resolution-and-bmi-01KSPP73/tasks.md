# Tasks: Stage 2 Input Resolution And BMI

**Mission**: `stage-2-input-resolution-and-bmi-01KSPP73`
**Mission ID**: `01KSPP73Q501XP9QEKHBJ8JE95`
**Generated**: `2026-05-28T08:13:11Z`
**Planning Branch**: `master`
**Merge Target**: `master`
**Feature Dir**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/stage-2-input-resolution-and-bmi-01KSPP73`

## Branch Context

- Current branch at task generation: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- Branches match expected planning context: `true`
- Branch strategy: planning artifacts were generated on `master`; execution worktrees are allocated later per computed lane from `lanes.json`, and all completed work merges back into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt | Estimated Prompt Size |
|---|---|---|---|---|---|
| WP01 | Resolver Surface And Registry Foundation | High | None | `tasks/WP01-resolver-surface-and-registry-foundation.md` | ~320 lines |
| WP02 | Observation And Profile Resolvers | High | WP01 | `tasks/WP02-observation-and-profile-resolvers.md` | ~300 lines |
| WP03 | BMI Proof Consumer | High | WP01, WP02 | `tasks/WP03-bmi-proof-consumer.md` | ~280 lines |
| WP04 | Boundary And Planning Doc Alignment | Medium | WP01, WP02, WP03 | `tasks/WP04-boundary-and-planning-doc-alignment.md` | ~260 lines |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add failing public-interface tests that define the Stage 2 input-resolution surface and prove unsupported future domains fail explicitly rather than being coerced into another domain. | WP01 |  | [D] |
| T002 | Add the shared declared-input resolution entrypoint and supporting types so Stage 2 consumers can resolve dependencies by semantic domain and anchor time. | WP01 |  | [D] |
| T003 | Add a static built-in resolver registry pattern that mirrors the existing signal-registry shape without introducing dynamic discovery. | WP01 |  | [D] |
| T004 | Wire the public engine surface so the new resolution seam is reachable through existing public imports rather than private helper paths. | WP01 |  | [D] |
| T005 | Finish foundation coverage for registry dispatch, unsupported-domain behavior, and public-surface determinism. | WP01 |  | [D] |
| T006 | Add failing public-interface tests for observation-history resolution, including anchor-time freshness and honest missing/stale behavior. | WP02 |  | [D] |
| T007 | Implement the observation resolver by reusing existing `_query.py` policy and freshness helpers rather than re-querying ad hoc. | WP02 |  | [D] |
| T008 | Implement the profile-as-of resolver over shipped profile assertions with latest-valid-as-of semantics. | WP02 |  | [D] |
| T009 | Extend resolver coverage to prove there is no hidden fallback from measured height when a declared profile height is required. | WP02 |  | [D] |
| T010 | Add failing public-interface tests for BMI as the first cross-domain proof consumer. | WP03 |  |
| T011 | Implement BMI as a Stage 2 proof consumer that resolves declared height from profile context and weight from observation history. | WP03 |  |
| T012 | Ensure BMI returns explicit refusal or missing-input outcomes when declared profile height is absent, stale, or unsupported or when weight is stale or absent. | WP03 |  |
| T013 | Add end-to-end proof coverage that BMI uses the new resolver seam and that unresolved intake domains do not interfere with the BMI flow. | WP03 |  |
| T014 | Update `src/premura/engine/CONTRACT.md` so the Stage 2 boundary is framed as domain-aware input resolution and the trigger for extending answer families is explicit. | WP04 | [P] |
| T015 | Update `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md` with the domain-vs-shape rubric for future domain proposals. | WP04 | [P] |
| T016 | Update `docs/architecture/STAGES.md` and `docs/operations/STATUS.md` so the shipped Stage 2 foundation and BMI proof consumer are described accurately, including the still-unresolved intake domains. | WP04 | [P] |
| T017 | Update `docs/product/ROADMAP.md` and `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so future analytical planning starts from domain-aware input resolution instead of prepared-series language. | WP04 | [P] |

## Work Packages

### WP01 - Resolver Surface And Registry Foundation

- Prompt: `tasks/WP01-resolver-surface-and-registry-foundation.md`
- Goal: establish the Stage 2 input-resolution seam, its public entrypoint, and the static in-tree resolver registry pattern before any concrete resolver or consumer lands.
- Priority: High
- Independent validation: public engine tests can resolve declared dependencies through the new seam, unsupported future domains fail explicitly, and resolver dispatch is driven by the new registry rather than a growing hardcoded branch chain.
- Dependencies: None.
- Owned files: `src/premura/engine/__init__.py`, `src/premura/engine/_registry.py`, `src/premura/engine/_resolution.py`, `src/premura/engine/views/__init__.py`, `tests/test_engine_input_resolution_surface.py`
- Estimated prompt size: ~320 lines

Included subtasks:
- [x] T001 Add failing public-interface tests that define the Stage 2 input-resolution surface and prove unsupported future domains fail explicitly rather than being coerced into another domain. (WP01)
- [x] T002 Add the shared declared-input resolution entrypoint and supporting types so Stage 2 consumers can resolve dependencies by semantic domain and anchor time. (WP01)
- [x] T003 Add a static built-in resolver registry pattern that mirrors the existing signal-registry shape without introducing dynamic discovery. (WP01)
- [x] T004 Wire the public engine surface so the new resolution seam is reachable through existing public imports rather than private helper paths. (WP01)
- [x] T005 Finish foundation coverage for registry dispatch, unsupported-domain behavior, and public-surface determinism. (WP01)

Implementation sketch:
1. Start by writing failing public-interface tests that define what it means to resolve a declared dependency at an anchor time.
2. Add one shared Stage 2 resolution module that introduces the seam without committing to a single universal payload shape.
3. Mirror the static signal-registry pattern for resolvers so supported domains register in one place.
4. Expose the new seam through the public engine surface so later WPs can consume it without importing private internals.
5. Finish with tests that lock unsupported-domain behavior and deterministic public access.

Parallel opportunities:
- None inside this WP. The public seam, registry pattern, and surface tests should evolve together as one foundation.

Risks:
- Recreating the rejected “prepared series” abstraction under a different name.
- Building a resolver surface that is only reachable through private helpers.
- Hardcoding future-domain behavior in a way that makes later resolver addition expensive.

Reviewer focus:
- Confirm the abstraction is “declared dependency + resolver”, not “everything is a series”.
- Confirm unsupported `nutrition_intake` and `supplement_intake` declarations fail explicitly.
- Confirm the public engine surface is the test boundary.

### WP02 - Observation And Profile Resolvers

- Prompt: `tasks/WP02-observation-and-profile-resolvers.md`
- Goal: implement the two concrete resolvers backed by already-shipped data: observation history and profile-as-of.
- Priority: High
- Independent validation: observation and profile dependencies resolve correctly at a chosen anchor time, respect freshness and as-of semantics, and never fall back across domains.
- Dependencies: WP01.
- Owned files: `src/premura/engine/views/observation.py`, `src/premura/engine/views/profile.py`, `src/premura/engine/_query.py`, `tests/test_engine_resolvers.py`
- Estimated prompt size: ~300 lines

Included subtasks:
- [x] T006 Add failing public-interface tests for observation-history resolution, including anchor-time freshness and honest missing/stale behavior. (WP02)
- [x] T007 Implement the observation resolver by reusing existing `_query.py` policy and freshness helpers rather than re-querying ad hoc. (WP02)
- [x] T008 Implement the profile-as-of resolver over shipped profile assertions with latest-valid-as-of semantics. (WP02)
- [x] T009 Extend resolver coverage to prove there is no hidden fallback from measured height when a declared profile height is required. (WP02)

Implementation sketch:
1. Write failing tests for both resolver families through the public seam.
2. Implement observation resolution first, leaning on existing freshness and policy helpers where they already fit.
3. Implement profile-as-of resolution next, using the shipped profile assertion storage semantics.
4. Finish with negative-path tests that prove declared profile prerequisites cannot be satisfied by opportunistic observation reads.

Parallel opportunities:
- T007 and T008 can overlap once the surface from WP01 is stable, because they live in separate resolver modules.

Risks:
- Re-implementing freshness logic instead of reusing the Stage 2 helpers already in the repo.
- Treating profile resolution as “latest row wins” rather than “latest valid as of anchor”.
- Allowing measured height to satisfy declared-height requests.

Reviewer focus:
- Confirm the observation resolver respects existing metric policy rather than inventing new rules.
- Confirm the profile resolver resolves by meaning and time, not convenience.
- Confirm the tests prove the no-hidden-fallback rule.

### WP03 - BMI Proof Consumer

- Prompt: `tasks/WP03-bmi-proof-consumer.md`
- Goal: prove the new seam with one buildable cross-domain Stage 2 consumer, keeping it clearly in proof scope rather than broad analytical-product scope.
- Priority: High
- Independent validation: BMI succeeds only when declared profile height and usable weight both resolve honestly, and refuses explicitly otherwise.
- Dependencies: WP01, WP02.
- Owned files: `src/premura/engine/descriptive_signals.py`, `tests/test_bmi_signal.py`
- Estimated prompt size: ~280 lines

Included subtasks:
- [ ] T010 Add failing public-interface tests for BMI as the first cross-domain proof consumer. (WP03)
- [ ] T011 Implement BMI as a Stage 2 proof consumer that resolves declared height from profile context and weight from observation history. (WP03)
- [ ] T012 Ensure BMI returns explicit refusal or missing-input outcomes when declared profile height is absent, stale, or unsupported or when weight is stale or absent. (WP03)
- [ ] T013 Add end-to-end proof coverage that BMI uses the new resolver seam and that unresolved intake domains do not interfere with the BMI flow. (WP03)

Implementation sketch:
1. Start with failing tests that define BMI success and refusal through public Stage 2 interfaces.
2. Add BMI in the existing Stage 2 answer family surface without opening a new family.
3. Resolve inputs through the new seam rather than by direct ad hoc queries.
4. Finish with coverage that proves BMI is a cross-domain proof consumer and not a hidden observation-only shortcut.

Parallel opportunities:
- None inside this WP. The proof consumer and its success/refusal semantics should be implemented as one coherent slice.

Risks:
- Letting BMI drift into a polished user-facing interpretation instead of a proof consumer.
- Quietly reading measured height when declared height is absent.
- Reaching around the resolver seam “just for this one signal”.

Reviewer focus:
- Confirm BMI genuinely crosses domains.
- Confirm refusal behavior is explicit and inspectable.
- Confirm the implementation proves the resolver pattern rather than bypassing it.

### WP04 - Boundary And Planning Doc Alignment

- Prompt: `tasks/WP04-boundary-and-planning-doc-alignment.md`
- Goal: align engine, architecture, status, and planning docs with the corrected Stage 2 foundation so future work does not regress back to prepared-series or domain-collapsing language.
- Priority: Medium
- Independent validation: the updated docs consistently describe domain-aware input resolution as the next Stage 2 foundation, record the domain-vs-shape rubric, record the answer-family extension trigger, and describe BMI as a proof consumer with unresolved intake domains still deferred.
- Dependencies: WP01, WP02, WP03.
- Owned files: `src/premura/engine/CONTRACT.md`, `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`, `docs/architecture/STAGES.md`, `docs/operations/STATUS.md`, `docs/product/ROADMAP.md`, `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- Estimated prompt size: ~260 lines

Included subtasks:
- [ ] T014 Update `src/premura/engine/CONTRACT.md` so the Stage 2 boundary is framed as domain-aware input resolution and the trigger for extending answer families is explicit. (WP04)
- [ ] T015 Update `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md` with the domain-vs-shape rubric for future domain proposals. (WP04)
- [ ] T016 Update `docs/architecture/STAGES.md` and `docs/operations/STATUS.md` so the shipped Stage 2 foundation and BMI proof consumer are described accurately, including the still-unresolved intake domains. (WP04)
- [ ] T017 Update `docs/product/ROADMAP.md` and `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so future analytical planning starts from domain-aware input resolution instead of prepared-series language. (WP04)

Implementation sketch:
1. Update the engine contract first so future contributors see the corrected boundary in the most code-adjacent guidance.
2. Add the domain-vs-shape rubric to the semantic contract next.
3. Update architecture and shipped-state docs after the implementation details are stable.
4. Realign product planning docs last so future missions inherit the corrected Stage 2 framing.

Parallel opportunities:
- T014, T015, T016, and T017 can overlap once WP01-WP03 make the shipped behavior clear, because they target distinct docs with different audiences.

Risks:
- Keeping stale prepared-series phrasing in one doc layer while fixing it in another.
- Overstating nutrition/supplement resolution before those resolvers exist.
- Opening answer-family growth by implication rather than keeping it review-gated.

Reviewer focus:
- Confirm the docs now separate “supported declaration target” from “concrete resolver shipped”.
- Confirm BMI is documented as proof scope, not as a large analytical surface.
- Confirm the growth rules for new domains and new answer families are explicit.
