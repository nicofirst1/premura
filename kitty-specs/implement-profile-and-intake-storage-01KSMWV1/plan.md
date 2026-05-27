# Implementation Plan: Implement Profile And Intake Storage

**Branch**: `master` (planning base and merge target) | **Date**: 2026-05-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/implement-profile-and-intake-storage-01KSMWV1/spec.md`

## Summary

Implement the first concrete storage layer for Premura's three profile/intake
domains:

1. profile context,
2. nutrition intake,
3. supplement intake.

The design follows the clarified agent-first product stance:

- **Profile context** gets a real agent-mediated capture path. The human answers
  a bounded set of profile questions, and the agent writes those answers through
  deterministic tools.
- **Nutrition and supplement intake** get their concrete warehouse home and
  parser-ready persistence seam, but this mission does **not** ship built-in
  vendor importers or human-first manual-entry forms for those domains.

The key implementation split is therefore:

- **Agent write path now**: bounded profile capture over MCP tools, with CLI as a
  thin fallback / testing surface.
- **Parser landing zone now**: concrete storage and persistence types for
  nutrition and supplement records.
- **Source adaptation later**: future parser missions turn vendor artifacts into
  those normalized persistence inputs.

## Engineering Alignment

- **The current issue is now explicit.** The doctrine and maintainer context now
  say plainly that Premura's default operator is the agent, not a human form
  filler or a human CLI user.
- **Profile capture is the only shipped write flow in this mission.** It is
  bounded, agent-mediated, and deterministic.
- **Nutrition and supplement support stay on the plug-in / parser path.** This
  mission gives those domains real tables and persistence shapes, but not a
  built-in MyFitnessPal importer or a one-off CSV importer.
- **Concrete storage is in scope.** Unlike the previous contract mission, this
  mission does choose a real warehouse layout and persistence service.
- **One-home rule remains load-bearing.** The new tables exist specifically so
  later work cannot smuggle profile or intake semantics into
  `hp.fact_measurement`, `hp.fact_interval`, or `hp.fact_clinical_note`.

## Technical Context

**Language/Version**: Python 3.11+ (`uv`-managed project).  
**Primary Dependencies**: existing `typer` CLI, existing `mcp` server surface, DuckDB warehouse, existing parser seam in `src/premura/parsers/base.py`, pytest.  
**Storage**: DuckDB with a new warehouse migration for profile/intake domain tables plus a new store module for profile/intake persistence.  
**Testing**: pytest; black-box tests through MCP tools and CLI for profile capture, plus persistence tests for normalized nutrition/supplement records.  
**Target Platform**: local-first Python toolchain on macOS; warehouse remains portable.  
**Project Type**: single Python project (`src/premura`, `tests`, `docs`).  
**Performance Goals**: bounded profile capture write/read round-trip under existing non-ingest interactive expectations; no new network-dependent path.  
**Constraints**: local-first; no PHI in tests or docs; no live API access; no human-facing forms as the default path; parser/plugin path preserved for vendor-shaped nutrition/supplement artifacts; bounded profile field allowlist only.  
**Scale/Scope**: one new migration, one new persistence module, one bounded agent-facing write surface, parser-ready nutrition/supplement entities, and a focused set of tests/docs.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial check: PASS**

- **Agent-first operational stance**: preserved. The plan uses MCP tools as the
  primary write surface and treats CLI as fallback / testing support.
- **Local-first / no network**: preserved. All writes stay local to DuckDB.
- **PHI hygiene**: preserved. Planning artifacts use synthetic examples only.
- **Scientific grounding / no overconfident health claims**: preserved. This
  mission stores inputs; it does not add interpretation behavior.
- **Testing and quality gates**: compatible with the charter. New behavior is
  planned around pytest and public-interface testing.

**Post-design re-check: PASS**

- Phase 1 keeps the doctrine's agent-first stance explicit in both tool surface
  and storage design.
- No charter amendment is needed; the work stays inside the current policy.

## Project Structure

### Documentation (this feature)

```
kitty-specs/implement-profile-and-intake-storage-01KSMWV1/
├── plan.md                              # This file
├── research.md                          # Phase 0 output
├── data-model.md                        # Phase 1 output
├── quickstart.md                        # Phase 1 output
├── contracts/
│   ├── profile-capture-tools.yaml       # Agent-facing bounded write/read surface
│   ├── profile-field-allowlist.yaml     # Supported profile keys for this mission
│   └── intake-persistence-schema.yaml   # Parser-ready nutrition/supplement shapes
└── tasks.md                             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/premura/
├── cli.py                               # Existing CLI; add bounded profile commands
├── mcp/
│   ├── entrypoint.py                    # Existing MCP registration surface
│   └── server.py                        # Existing MCP helpers; add profile write/read helpers
├── parsers/
│   └── base.py                          # Extend normalized parser seam for intake records
└── store/
    ├── loader.py                        # Existing ingest loader; intake persistence may reuse parts
    ├── profile_intake.py                # Planned new persistence service
    └── migrations/
        └── 004_profile_intake.sql       # Planned new warehouse tables

tests/
├── test_profile_capture_tools.py        # Planned MCP/CLI black-box tests
└── test_profile_intake_persistence.py   # Planned persistence and one-home tests
```

**Structure Decision**: Add one new store module and one new migration for the
profile/intake domains. Keep the primary agent-facing path inside the existing
MCP surface and add a thin CLI wrapper in `src/premura/cli.py` for fallback and
testing. Extend the parser seam in `src/premura/parsers/base.py` so future
nutrition/supplement parsers can emit normalized intake-domain records without
having to redesign storage.

## Phase 0 — Research

See [research.md](research.md) for the five decisions that lock the corrected
scope:

1. treat doctrine ambiguity as a real issue and make the agent-first stance
   explicit,
2. make MCP the primary write surface for profile capture,
3. keep CLI as a thin fallback / testing wrapper,
4. keep nutrition/supplement source support on the plug-in / parser path,
5. use concrete domain tables plus a parser-ready persistence seam rather than a
   generic context blob or measurement-table reuse.

## Phase 1 — Design & Contracts

- [data-model.md](data-model.md): concrete entities, fields, relationships, and
  correction rules for profile context, nutrition intake, and supplement intake.
- [contracts/profile-capture-tools.yaml](contracts/profile-capture-tools.yaml):
  the bounded agent-facing write/read surface for stable profile facts.
- [contracts/profile-field-allowlist.yaml](contracts/profile-field-allowlist.yaml):
  the supported profile keys and validation rules for this mission.
- [contracts/intake-persistence-schema.yaml](contracts/intake-persistence-schema.yaml):
  normalized nutrition/supplement record shapes that future parsers should emit.
- [quickstart.md](quickstart.md): the validation path for the later
  implementation mission.

## Review Gates For Later Implementation

Any follow-on implementation derived from this plan should fail review if any of
the following are missing:

1. A concrete DuckDB migration that creates separate profile, nutrition, and
   supplement domain tables.
2. A bounded profile field allowlist and deterministic agent-facing write
   surface.
3. Black-box tests that drive profile capture through MCP and/or CLI rather than
   direct helper calls.
4. A parser-ready persistence seam for nutrition and supplement records that
   does not reuse `hp.fact_measurement` or notes as shortcuts.
5. Docs updated in the same change if implementation wording drifts from the
   clarified agent-first doctrine.

## Complexity Tracking

No Charter Check violations; table not applicable.
