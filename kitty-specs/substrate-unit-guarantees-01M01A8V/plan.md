# Implementation Plan: Substrate Unit Guarantees

**Branch**: `substrate-unit-guarantees-01M01A8V` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md) **Input**: Feature specification from `/kitty-specs/substrate-unit-guarantees-01M01A8V/spec.md`

## Summary

Move measurement-unit correctness from per-parser convention into the load boundary: one shared table-driven unit module; `loader.load()` converts every measurement to its metric's canonical unit or refuses that row; refusals become queryable warehouse rows; parsers stop converting and merely report the unit as observed. Harden the bypass that caused the incident (source-kind vocabulary rail, read-only-by-default connections) and pave a cheaper sanctioned road (one parameterized MCP tool: metric lookup + manual single-row load with mandatory provenance). Clean legacy data (spelling-only backfill migration; reviewed one-shot labsheet delete + documented re-entry) and make every doc claim name its mechanical enforcement home. Every WP review runs a written six-question over-engineering pass (spec C-005).

## Technical Context

**Language/Version**: Python 3.11+ (uv-managed) **Primary Dependencies**: DuckDB, polars, PyYAML, FastMCP (existing; no new dependencies permitted without over-engineering-gate justification) **Storage**: DuckDB warehouse, schemas `hp`/`trace`; additive idempotent SQL migrations under `src/premura/store/migrations/` **Testing**: pytest; real temp-file DuckDB per test via `empty_warehouse` fixture (`tests/conftest.py:30`); parser tests use inline synthetic fixtures; e2e precedent `tests/intake/test_interval_unit_ingest.py` **Target Platform**: local machine (operator-owned), CLI + MCP server **Project Type**: single project (`src/premura/`) **Performance Goals**: N/A (small-batch ingest; no thresholds change) **Constraints**: no PHI in repo/tests (C-001); migrations replay-forever idempotent, destructive one-shots under `ops/` (C-002); at most one new MCP tool on the default surface (C-003) **Scale/Scope**: ~170-metric ontology, single-operator warehouse; 8 work packages

## Charter Check

Governing doctrine: `docs/shared/DOCTRINE.md` (agent-first; design a level above — guide, don't enumerate). This mission additionally binds spec C-005: every WP review and the mission review record a written pass/fail on the six-question over-engineering checklist (existence, abstraction budget, shrink check, one-rule-one-chokepoint, process test, reuse ladder). Mechanism untraceable to an FR fails review even with green tests. The mission itself adds the "substrate test" to DOCTRINE.md (FR-010).

Gate status: PASS — the design consolidates two enumerated per-parser ladders into one registry-shaped module and deletes more parser code than it adds elsewhere (spec NFR-001/SC-006).

## Project Structure

### Documentation (this mission)

```
kitty-specs/substrate-unit-guarantees-01M01A8V/
├── plan.md              # This file
├── research.md          # Phase 0: incident investigation digest
├── data-model.md        # Phase 1: hp.ingest_skip + entity notes
├── quickstart.md        # Phase 1: verification walkthrough
├── contracts/
│   ├── load-boundary.md # unit convert-or-refuse + vocabulary rail
│   └── ingest-row-tool.md # paved-road MCP tool contract
└── tasks/               # Phase 2 (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/premura/
├── units.py                          # NEW (IC-01): shared normalize/convert tables
├── store/
│   ├── loader.py                     # IC-02/03/05: boundary enforcement, _persist_skips, vocabulary rail
│   ├── duck.py                       # IC-05: read_only default flip
│   ├── manual_load.py                # NEW (IC-05): thin single-row batch builder
│   └── migrations/
│       ├── 009_ingest_skip.sql       # NEW (IC-03)
│       └── 010_unit_spelling_backfill.sql  # NEW (IC-06)
├── parsers/
│   ├── lab_pdf.py                    # IC-04: conversion logic deleted
│   └── bmt.py                        # IC-04: conversion logic deleted
├── mcp/
│   ├── server.py                     # IC-05: ingest_row delegation
│   └── entrypoint.py                 # IC-05: tool registration + docstring counts
└── cli.py                            # IC-06: audit-integrity verb

ops/delete_labsheet_rows.sql          # NEW (IC-06): one-shot, hand-run

tests/
├── test_units.py                     # NEW
├── intake/test_measurement_unit_ingest.py  # NEW (mirrors test_interval_unit_ingest.py)
├── intake/test_ingest_skip_migration.py    # NEW
├── intake/test_unit_spelling_migration.py  # NEW
├── mcp/test_ingest_row_tool.py       # NEW
└── test_cli_audit_integrity.py       # NEW
```

**Structure Decision**: single project, existing layout; two new modules (`units.py`, `store/manual_load.py`), two migrations, one ops one-shot. No new packages, no new dependencies.

## Complexity Tracking

No charter violations. New-artifact budget and its FR traceability: `units.py` (FR-001), `hp.ingest_skip` (FR-003), `manual_load.py` + `ingest_row` tool (FR-006), `audit-integrity` verb (FR-007), two migrations (FR-003/FR-008), one ops script (FR-009). Anything beyond this list fails the C-005 gate.

## Implementation Concern Map

> Implementation concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Shared unit module

- **Purpose**: one home for unit spelling normalization and value conversion; refusal when no rule exists.
- **Relevant requirements**: FR-001
- **Affected surfaces**: `src/premura/units.py` (new), `tests/test_units.py`
- **Sequencing/depends-on**: none
- **Risks**: the port must be byte-identical in behavior to `lab_pdf.py:374-446` + `bmt.py:75-109` (parametrized tests over the old tables catch regressions mechanically). Tables stay module dicts — no YAML formula DSL (target unit and conversion rule are different facts with different homes).

### IC-02 — Load-boundary enforcement

- **Purpose**: every `fact_measurement` row converted to canonical or refused row-level at `loader.load()`; stored unit label always `dim_metric.canonical_unit` (extends the existing interval pattern, `loader.py:164-187`).
- **Relevant requirements**: FR-002
- **Affected surfaces**: `store/loader.py` (`_persist_plan`, `LoadStats.rows_skipped_unit`), `tests/intake/test_measurement_unit_ingest.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: measurements carry values in source units — the boundary must convert values, never merely relabel (relabeling IS the incident bug). `DedupePlanner` stays untouched; the unit pass is a post-dedupe step in `_persist_plan` (dedupe and unit-validity are orthogonal).

### IC-03 — Structured skip persistence

- **Purpose**: refusals, parser skips, and unmapped metrics become queryable warehouse rows (`hp.ingest_skip`), closing the computed-then-dropped loop.
- **Relevant requirements**: FR-003, NFR-002
- **Affected surfaces**: `store/migrations/009_ingest_skip.sql`, `store/loader.py` (`_persist_skips`), migration + ingest tests
- **Sequencing/depends-on**: IC-02
- **Risks**: `dup_priority` row-level detail comes from a SQL NOT EXISTS filter, not a Python list — count-only is acceptable there (stretch goal only; don't restructure dedupe for it).

### IC-04 — Parser simplification

- **Purpose**: parsers emit unit-as-observed; both local conversion ladders deleted; the loader is the only unit decision-maker.
- **Relevant requirements**: FR-004, NFR-001
- **Affected surfaces**: `parsers/lab_pdf.py`, `parsers/bmt.py`, their tests
- **Sequencing/depends-on**: IC-02 (load-bearing order: the loader must enforce before parsers stop converting, or unconverted values land raw in between)
- **Risks**: BMT wide-format has no per-row unit string — its config-declared unit stays a parser-level assumption, documented as the one scope exception. Old parser conversion assertions move to the loader e2e tests, not deleted.

### IC-05 — Bypass hardening + paved road

- **Purpose**: source-kind vocabulary rail in `validate_batch_against_warehouse`; `duck.connect` read-only by default (defense-in-depth); one parameterized MCP tool `ingest_row(op="load"|"suggest_metric")` on the default surface routing through `loader.load()`.
- **Relevant requirements**: FR-005, FR-006, NFR-003
- **Affected surfaces**: `store/loader.py`, `store/duck.py`, `store/manual_load.py` (new), `mcp/server.py`, `mcp/entrypoint.py`, `tests/mcp/*`
- **Sequencing/depends-on**: IC-02, IC-03
- **Risks**: the vocabulary check is THE rail (would have made the incident raise); the read-only default is hygiene, not the fix — don't overstate it. Reuse `registered_source_kinds()` (`parsers/registry.py:53`); define `MANUAL_LOAD_SOURCE_KIND` exactly once. Tool inventory test (`_DEFAULT_TOOLS`) must be updated deliberately.

### IC-06 — Detection + legacy cleanup

- **Purpose**: `premura audit-integrity` verb (non-canonical units, out-of-vocabulary source kinds); spelling-variant backfill migration with a hand-vetted allowlist; one-shot labsheet delete script + dry-run count.
- **Relevant requirements**: FR-007, FR-008, FR-009, NFR-004
- **Affected surfaces**: `cli.py`, `store/migrations/010_unit_spelling_backfill.sql`, `ops/delete_labsheet_rows.sql`, tests
- **Sequencing/depends-on**: IC-01 (spelling vocabulary); IC-03 optional (audit may summarize skips)
- **Risks**: the backfill allowlist is authored once by running the detection query against the real warehouse and classifying pairs by hand — magnitude-wrong rows must stay visibly wrong until deleted (the allowlist must not over-fire; test proves it). The delete is NOT a migration (C-002).

### IC-07 — Docs truth + doctrine

- **Purpose**: every guarantee claim names its enforcement home; runtime guide names the paved road and forbids direct warehouse writes; DOCTRINE gains the substrate test with this incident as worked example; live docs (STATUS/ROADMAP, tool counts, CHANGELOG) synced.
- **Relevant requirements**: FR-010
- **Affected surfaces**: `src/premura/parsers/CONTRACT.md`, `PARSER_CONTRIBUTING.md`, `docs/building/STAGES.md`, `docs/shared/SPEC.md`, `src/premura/store/UPDATE_STRATEGY.md`, `docs/operating/RUNTIME_AGENT.md`, `docs/shared/DOCTRINE.md`, `docs/shared/STATUS.md`/`ROADMAP.md`, `mcp/entrypoint.py` docstring
- **Sequencing/depends-on**: IC-02, IC-04, IC-05, IC-06 (docs trail the code they describe)
- **Risks**: known drift pattern — a pre-merge sync WP cannot describe its own merge; plan a post-merge live-doc reconciliation pass at mission review.
