# Implementation Plan: Model Intake And Profile Context

**Branch**: `master` (planning base and merge target) | **Date**: 2026-05-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/model-intake-and-profile-context-01KSMN80/spec.md`

## Summary

Define a strict, agent-reviewable contract for three new Premura domains while
leaving storage adapters open:

1. baseline profile context,
2. nutrition intake,
3. supplement intake.

The implementation plan does **not** choose a warehouse table layout. Instead it
locks down the semantics that later implementations must preserve, so agents can
change storage without changing what the data means. The key planning decision is
therefore a ports/adapters split:

- **Strict port / contract**: canonical entities, required fields, dependency
  declarations, positive invariants, and review gates.
- **Flexible adapter / storage**: whichever concrete persistence shape later
  missions choose, as long as it satisfies the contract and its checks.

Because first-pass review is expected to be agent-driven, the load-bearing
guardrails must be machine-applicable where possible. This plan therefore leads
with positive invariants and checkable contract artifacts, then uses forbidden
shortcuts only as examples of what invariant violations look like.

## Engineering Alignment

- **Storage remains open.** This mission does not prescribe a DuckDB schema,
  migration, or repository layout for profile/intake persistence.
- **Meaning is not open.** The contract must define what each entity means, what
  it is not, and how it relates to existing observation history.
- **Invariants before examples.** Implementation review should test a small set
  of positive invariants first; forbidden shortcuts are illustrative teeth, not
  the primary contract.
- **Agent-review first.** Contract artifacts and tests should let an agent
  reviewer reject a PR for a broken invariant without debating prose intent.
- **No hidden back-doors.** Future work must not smuggle profile context or
  intake semantics into `hp.fact_measurement`, `hp.fact_interval`, or free-form
  notes just because those paths already exist.

## Technical Context

**Language/Version**: Python 3.x project (`uv`-managed) with documentation and contract artifacts in Markdown/YAML.  
**Primary Dependencies**: Existing Premura docs and contracts, pytest, existing Stage 2/Stage 3 contract docs. No new runtime dependency required for this planning output.  
**Storage**: Deliberately storage-agnostic at this mission stage; future implementations may choose concrete DuckDB shapes later if they honor the contract.  
**Testing**: Agent-reviewable contract checks via pytest over contract artifacts and any public-facing contract surfaces added later.  
**Target Platform**: Local-first Python toolchain on macOS, with portable docs/artifacts for the repo.  
**Project Type**: Single project (`src/premura/...`, `docs/...`, `tests/...`).  
**Performance Goals**: No new runtime hot path in this mission; unchanged platform targets from the charter and `docs/product/SPEC.md`.  
**Constraints**: Local-first; no PHI in docs/tests; no live API access; no hidden semantics; storage-flexible but contract-strict; machine-reviewable invariants required because agents perform review.  
**Scale/Scope**: Planning artifacts now; later implementation is expected to touch a small set of docs/contracts/tests and possibly add a narrow contract-validation surface.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial check: PASS**

- **Local-first / no network**: preserved. This mission is boundary modeling and
  contract design only.
- **PHI hygiene**: preserved. Planned artifacts are abstract entities,
  invariants, and examples only; no real operator data belongs in these files.
- **Scientific grounding / no overconfident health claims**: preserved. The
  mission defines data contracts, not interpretations or diagnoses.
- **Docs synchronized with workflow changes**: satisfied. The implementation path
  explicitly expects doc and contract alignment together.
- **Testing and quality gates**: compatible. Because agents review first-pass PRs,
  the plan requires machine-checkable contract tests rather than prose-only
  guidance, which is aligned with DIRECTIVE_030/034/036.

**Post-design re-check: PASS**

- The Phase 1 design keeps storage open but makes the semantic contract explicit
  and reviewable through versioned artifacts.
- No charter amendment is needed; no risk boundary is crossed.

## Project Structure

### Documentation (this feature)

```
kitty-specs/model-intake-and-profile-context-01KSMN80/
├── plan.md                     # This file
├── research.md                 # Phase 0 output
├── data-model.md               # Phase 1 output
├── quickstart.md               # Phase 1 output
├── contracts/
│   ├── domain-entities.yaml    # Canonical entity shapes + required fields
│   ├── semantic-invariants.yaml# Positive invariants + detection intent
│   └── dependency-contract.yaml# How future functions declare prerequisites
└── tasks.md                    # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
docs/architecture/
├── STAGES.md                   # Boundary wording: observations vs profile/intake domains
└── UPDATE_STRATEGY.md          # How corrections / supersessions differ from rebuild flows

docs/product/
└── FULL_APP_DEVELOPMENT_PLAN.md# Follow-on sequencing after the domain decision

src/premura/engine/
└── CONTRACT.md                 # Future function dependency declarations must reference the new contract

tests/
└── test_profile_intake_contracts.py
                               # Planned black-box validation of contract artifacts / invariants
```

**Structure Decision**: Keep the mission centered on `kitty-specs/model-intake-and-profile-context-01KSMN80/` for the planning artifacts, then implement the approved contract by aligning the existing docs and adding one narrow contract-validation test surface under `tests/`. No storage module or migration path is selected in this mission's first implementation.

## Phase 0 — Research

There are no unresolved planning questions left, but the rationale behind the
chosen direction is important enough to record. See [research.md](research.md)
for the five planning decisions that shape the implementation:

1. keep storage agnostic while making semantics strict,
2. make the strictness boundary the contract surface rather than table shape,
3. lead review with positive invariants and treat forbidden shortcuts as examples,
4. make the guardrails machine-applicable because agents are expected to review PRs,
5. use domain contracts rather than transport/API contracts for this mission.

## Phase 1 — Design & Contracts

- [data-model.md](data-model.md): conceptual entities, required fields,
  relationships, correction/supersession rules, and overlap handling with the
  current observation history.
- [contracts/domain-entities.yaml](contracts/domain-entities.yaml): the minimum
  stable contract surface each implementation must satisfy, independent of
  storage layout.
- [contracts/semantic-invariants.yaml](contracts/semantic-invariants.yaml): the
  positive invariants that implementation and review must enforce.
- [contracts/dependency-contract.yaml](contracts/dependency-contract.yaml): how
  future Stage 2 / Stage 3 work declares profile and intake prerequisites.
- [quickstart.md](quickstart.md): the concrete validation path for the later
  implementation mission.

## Review Gates For Later Implementation

Any follow-on implementation derived from this plan should fail review if any of
the following are missing:

1. A checked-in contract surface derived from the Phase 1 artifacts.
2. At least one machine-applicable validation path for each load-bearing
   invariant.
3. An explicit distinction between profile assertions, intake events/items, and
   observed measurements.
4. An explicit dependency declaration path for future profile- or
   intake-dependent functions.
5. Docs updated in the same change if the shipped boundary wording changes.

## Complexity Tracking

No Charter Check violations; table not applicable.
