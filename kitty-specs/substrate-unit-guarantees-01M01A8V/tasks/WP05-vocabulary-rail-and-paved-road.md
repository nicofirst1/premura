---
work_package_id: WP05
title: Source-kind vocabulary rail + ingest_row MCP tool
dependencies:
- WP02
- WP04
requirement_refs:
- FR-005
- FR-006
- NFR-003
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this mission were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 3 - Rail and road
history:
- timestamp: '2026-08-15T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
create_intent:
- src/premura/store/manual_load.py
- tests/mcp/test_ingest_row_tool.py
- tests/intake/test_measurement_unit_ingest.py
execution_mode: code_change
owned_files:
- src/premura/store/loader.py
- src/premura/store/manual_load.py
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- tests/mcp/test_ingest_row_tool.py
- tests/mcp/test_mcp_server.py
- tests/intake/test_measurement_unit_ingest.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 – Vocabulary rail + paved road

## Objective

Close the incident's hole and pave the road: `loader.load()` refuses unregistered source kinds before any write, and one parameterized MCP tool on the default surface gives agents metric lookup + manual single-row load with mandatory provenance.

## Read first

`kitty-specs/substrate-unit-guarantees-01M01A8V/contracts/ingest-row-tool.md` (authoritative tool contract) and `contracts/load-boundary.md`; `parsers/registry.py:39-55` (`registered_source_kinds`); the collapsed-parameterized convention: `condition_episode` in `mcp/entrypoint.py:926-993` + its `mcp/server.py` delegation; tool inventory test `tests/mcp/test_mcp_server.py` (`_DEFAULT_TOOLS`).

## Subtasks

- **T013**: define `MANUAL_LOAD_SOURCE_KIND` once (store layer); `validate_batch_against_warehouse` raises `ValueError` when `batch.source_kind` ∉ `registered_source_kinds()` ∪ {manual kind} — before any write.
- **T014**: `store/manual_load.py`: thin builder — one `Measurement` + `SourceDescriptor` → single-row `IngestBatch(source_kind=MANUAL_LOAD_SOURCE_KIND)` → `loader.load()`. No unit logic, no validation duplication (the boundary owns both).
- **T015**: `ingest_row(op="load"|"suggest_metric", ...)` tool on the DEFAULT surface per the contract doc: `suggest_metric` delegates to `parsers.lookup.suggest_metric`; `load` requires `source_ref` (refuse pre-loader if missing) and returns `status='loaded'|'refused'` with reason. Update entrypoint docstring/tool-count prose and `_DEFAULT_TOOLS` deliberately.
- **T016**: tests — **the bypass regression test: `loader.load()` with `source_kind='labsheet'` (any unregistered string) raises and writes zero rows — this is the test that would have caught the incident**; MCP e2e: valid load lands in `fact_measurement` under the manual kind; unconvertible unit → `status='refused'` + `hp.ingest_skip` row; missing `source_ref` → refused before the loader; `suggest_metric` op returns what `parsers.lookup.suggest_metric` returns; combined-hardening smoke: bare `duck.connect(path)` write attempt fails.

## Done criteria

All new + existing MCP/intake tests green; full suite + lint/type gates clean.

## Constraints

+1 tool max on the default surface (C-003). The tool delegates — zero conversion/validation logic in MCP layers (C-005). Provenance is never fabricated. No PHI.
