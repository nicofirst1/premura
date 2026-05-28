# Implementation Plan: Stage 2 Input Resolution And BMI

**Branch**: `master` (planning base and merge target) | **Date**: 2026-05-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/stage-2-input-resolution-and-bmi-01KSPP73/spec.md`

## Summary

Implement the next Stage 2 foundation as a **domain-aware input-resolution seam**,
not as a universal prepared-series layer.

The mission ships four concrete things together:

1. **Observation resolver** for declared dependencies that read observation
   history with anchor-time-aware freshness behavior.
2. **Profile-as-of resolver** for declared dependencies that read the latest
   valid profile assertion as of an anchor time.
3. **BMI proof consumer** as the first cross-domain Stage 2 answer built on the
   new seam.
4. **Structural docs and registry pattern** so future domains can be added
   without rewriting dispatch logic and future maintainers can distinguish a new
   semantic domain from a new shape inside an existing one.

The scope is intentionally narrow. Nutrition and supplement domains remain valid
in the declaration contract, but their real resolvers wait until Premura ingests
real parser-produced rows for them. Stage 3 statistical tools remain out of
scope.

## Engineering Alignment

- **This mission is still Stage 2 only.** It does not add Stage 3 correlation,
  change-point, PubMed, or literature-grounding tools.
- **The abstraction unit is corrected.** The foundation is a declared,
  domain-aware input resolver, not a universal prepared-series object.
- **BMI is a proof consumer, not a polished user-facing analytical surface.** Its
  role is to validate cross-domain dispatch honestly using already-shipped data.
- **Only shipped domains with real data get real resolvers now.** Observation and
  profile context resolve concretely in this mission. Nutrition and supplement
  domains remain representable in declarations but return explicit unresolved or
  missing-input results until later parser missions land real rows.
- **Resolver dispatch should be open; answer families should stay closed.** The
  registry pattern should make domain resolvers pluggable in-tree, while
  `RESULT_FAMILIES` remains review-gated and unchanged in this mission.
- **Docs are part of the product boundary here.** The mission must update the
  architecture and engine guidance so future contributors do not recreate the
  rejected prepared-series framing.

## Technical Context

**Language/Version**: Python 3.11+ (`uv`-managed project).  
**Primary Dependencies**: existing Stage 2 engine modules under `src/premura/engine/`, DuckDB warehouse access, existing Stage 2 result envelopes, pytest, ruff, mypy.  
**Storage**: existing DuckDB warehouse with current observation tables and shipped profile-context tables from migration `004_profile_intake.sql`.  
**Testing**: pytest with black-box tests through public engine interfaces; acceptance-style fixtures for BMI success and refusal paths; regression coverage for unresolved-domain behavior.  
**Target Platform**: local-first Python toolchain on macOS; warehouse and artifacts remain portable.  
**Project Type**: single Python project (`src/premura`, `tests`, `docs`, `kitty-specs`).  
**Performance Goals**: first consumer (`BMI`) responds within existing non-ingest interactive expectations; no background network activity.  
**Constraints**: local-first; no PHI in tests/docs; no Stage 3 statistics in this mission; no speculative intake resolvers before real parser rows; do not open `RESULT_FAMILIES`; use Premura-native vocabulary rather than ML-platform terms in the public surface.  
**Scale/Scope**: one new Stage 2 resolver entrypoint, two concrete resolvers, one proof consumer, one resolver registry pattern, tests, and focused doc alignment.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial check: PASS**

- **Local-first / no network**: preserved. All planned behavior stays inside the
  local DuckDB + Stage 2 engine boundary.
- **Scientific grounding / no diagnostic overreach**: preserved. BMI is framed as
  a proof consumer with honest refusal behavior, not as a clinical interpreter.
- **PHI hygiene**: preserved. Planning artifacts require synthetic fixtures only.
- **Test-first / public-interface testing**: preserved. The plan expects public
  engine-interface tests rather than internal helper-driven assertions.
- **Smallest viable diff**: preserved. Only the two resolvers supported by
  already-shipped data are implemented now.

**Post-design re-check: PASS**

- Phase 1 keeps the mission inside the current charter and does not require a
  governance amendment.
- The design remains modular: dispatch is extensible, but the user-facing proof
  scope stays intentionally small.

## Project Structure

### Documentation (this feature)

```
kitty-specs/stage-2-input-resolution-and-bmi-01KSPP73/
├── plan.md                              # This file
├── research.md                          # Phase 0 output
├── data-model.md                        # Phase 1 output
├── quickstart.md                        # Phase 1 output
├── contracts/
│   ├── input-resolution-surface.yaml    # Declared dependency + resolution contract
│   ├── bmi-proof-consumer.yaml          # First consumer contract and refusal surface
│   └── resolver-registry-surface.yaml   # In-tree resolver registration shape
└── tasks.md                             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/premura/
└── engine/
    ├── __init__.py                      # Existing registry exports; planned resolver registry hook
    ├── CONTRACT.md                      # Update answer-family trigger guidance
    ├── _query.py                        # Reuse existing observation-window/policy helpers where possible
    ├── _results.py                      # Existing result envelopes; no family expansion planned here
    ├── _registry.py                     # Existing signal registry shape; mirror for resolvers as needed
    ├── views/
    │   ├── observation.py               # Planned observation resolver
    │   └── profile.py                   # Planned profile-as-of resolver
    └── [BMI consumer module]            # Planned proof consumer using the new seam

tests/
├── [engine resolver tests]              # Planned public-interface resolution tests
└── [BMI consumer tests]                 # Planned success/refusal coverage for the proof consumer

docs/
├── architecture/
│   ├── STAGES.md                        # Boundary wording update
│   └── PROFILE_AND_INTAKE_CONTRACT.md   # Domain-vs-shape rubric
├── product/
│   ├── ROADMAP.md                       # Stage 2 foundation wording
│   └── FULL_APP_DEVELOPMENT_PLAN.md     # Phase framing alignment
└── history/                             # No new archive moves expected in this mission
```

**Structure Decision**: keep the new seam inside the existing engine package.
Resolvers live as dedicated Stage 2 modules, registered through a static in-tree
registry pattern mirroring the signal registry. The first proof consumer should
call the resolver entrypoint through public engine interfaces rather than
reaching directly into profile or observation storage.

## Phase 0 — Research

See [research.md](research.md) for the planning decisions that lock the corrected
scope:

1. preserve the Stage 2 / Stage 3 split while correcting the abstraction unit,
2. ship only the two resolvers backed by already-shipped data,
3. keep nutrition and supplement domains in the declaration contract but return
   explicit unresolved or missing-input outcomes until real rows exist,
4. use BMI as the singular first cross-domain consumer,
5. mirror the static signal-registry pattern for resolvers now,
6. record the domain-vs-shape rubric and answer-family extension trigger in docs
   as part of this mission.

## Phase 1 — Design & Contracts

- [data-model.md](data-model.md): the declared-dependency, resolved-input,
  resolver-registry, and BMI proof-consumer entities plus their relationships.
- [contracts/input-resolution-surface.yaml](contracts/input-resolution-surface.yaml):
  the Stage 2 declared-input and resolution contract, including unsupported but
  declared future domains.
- [contracts/bmi-proof-consumer.yaml](contracts/bmi-proof-consumer.yaml): the
  first cross-domain consumer contract and its honest refusal behavior.
- [contracts/resolver-registry-surface.yaml](contracts/resolver-registry-surface.yaml):
  the in-tree resolver registration pattern for supported domains.
- [quickstart.md](quickstart.md): the validation path for later implementation,
  focused on the proof consumer and refusal cases.

## Review Gates For Later Implementation

Any follow-on implementation derived from this plan should fail review if any of
the following are missing:

1. A declared-input resolver entrypoint that dispatches by semantic domain
   rather than assuming all inputs are observation-series data.
2. A concrete observation resolver and a concrete profile-as-of resolver.
3. A BMI proof consumer that exercises both domains and refuses honestly when a
   declared prerequisite is absent or stale.
4. Explicit unresolved or missing-input behavior for nutrition and supplement
   domains rather than silent coercion into another domain.
5. A resolver registration pattern that avoids a growing hardcoded dispatch
   chain.
6. Docs updated in the same change so future contributors can distinguish a new
   semantic domain from a new shape and can tell when extending answer families
   is the correct move.

## Complexity Tracking

No Charter Check violations; table not applicable.
