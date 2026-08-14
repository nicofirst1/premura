# Tasks: Substrate Unit Guarantees

**Input**: spec.md (FR-001..FR-010, NFR-001..NFR-004, C-001..C-005), plan.md (IC-01..IC-07) **Prerequisites**: plan.md, research.md, data-model.md, contracts/

Details, owned files, and done-criteria live in each `tasks/WPNN-*.md` prompt; WP frontmatter is authoritative for ownership and dependencies. Every WP review records the six-question over-engineering pass (spec C-005) and runs `ruff format --check` in addition to the standard gates.

## WP01 — Shared units module + read-only connection default

Create `src/premura/units.py` (table-driven normalize/convert, byte-identical port of the two parser ladders) and flip `duck.connect` default to read-only. Phase 1 - Substrate.

- Dependencies: none
- Subtasks: T001, T002, T003

## WP02 — Load-boundary unit enforcement for measurements

`loader.load()` converts every measurement to canonical or refuses row-level; stored unit always `dim_metric.canonical_unit`. Phase 1 - Substrate.

- Dependencies: WP01
- Subtasks: T004, T005, T006

## WP03 — Parsers stop converting

Delete both parser-local conversion ladders; lab_pdf/bmt emit unit-as-observed; parsers shrink. Phase 2 - Simplification.

- Dependencies: WP02
- Subtasks: T007, T008, T009

## WP04 — Structured skip persistence (hp.ingest_skip)

Migration 009 + `_persist_skips`: refusals, parser skips, unmapped metrics become queryable rows. Phase 2 - Closed loops.

- Dependencies: WP02, WP03
- Subtasks: T010, T011, T012

## WP05 — Source-kind vocabulary rail + ingest_row MCP tool

Loader refuses unregistered source kinds pre-write; one parameterized MCP tool (metric lookup + manual load with mandatory provenance) routes through `loader.load()`. Phase 3 - Rail and road.

- Dependencies: WP02, WP04
- Subtasks: T013, T014, T015, T016

## WP06 — audit-integrity CLI verb + spelling-variant backfill migration

Detection queries (non-canonical units, out-of-vocabulary source kinds) + idempotent relabel of vetted spelling-only pairs. Phase 3 - Detection.

- Dependencies: WP01
- Subtasks: T017, T018, T019

## WP07 — Labsheet remediation: one-shot delete script + runtime procedure

`ops/delete_labsheet_rows.sql` (dry-run count first) + RUNTIME_AGENT.md paved-road procedure; execution post-merge on the operator machine. Phase 4 - Remediation.

- Dependencies: WP05
- Subtasks: T020, T021

## WP08 — Docs made true + doctrine substrate test + live-doc sync

Contract/docs claims name their enforcement home; DOCTRINE gains the substrate test; CHANGELOG + tool-count docstring synced. Phase 4 - Truth.

- Dependencies: WP03, WP05, WP06, WP07
- Subtasks: T022, T023, T024
