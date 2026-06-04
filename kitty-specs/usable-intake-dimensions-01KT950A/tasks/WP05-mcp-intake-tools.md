---
work_package_id: WP05
title: Default-surface MCP tool exposure
dependencies:
- WP04
requirement_refs:
- FR-006
- NFR-001
- NFR-002
planning_base_branch: master
merge_target_branch: master
branch_strategy: Plan/base branch master; final merge target master. Execution worktree allocated per computed lane from lanes.json.
subtasks:
- T023
- T024
- T025
- T026
history:
- 2026-06-04T11:52:07Z created by /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- tests/test_mcp_intake_tools.py
tags: []
---

# WP05 — Default-surface MCP tool exposure

## Objective

Expose both intake signals as **thin** tools on the **default** MCP surface so an
agent can actually use them, following the existing signal-tool pattern. Satisfies
**FR-006** and the surface half of **SC-001/SC-002**.

## Context

- Existing wrappers live in `src/premura/mcp/server.py` (e.g. `resting_hr_status`
  at `:360` delegates via `_run_signal(tool_name, warehouse_path=...)`); the
  missing-input report is built by `_build_missing_input_report(...)` and the
  standard envelope is `{tool_name, status, message, result, missing_input?}`
  (see `server.py:854-879`).
- The intake signals are **parameterized** (matcher/key + window), unlike the
  zero-arg `resting_hr_status`. Follow the **parameterized** tool precedent
  (`correlate` and the other analytical tools already pass caller params through).
  Thread the caller's matcher/key + window from the tool signature into the signal
  call; do **not** re-derive intake semantics from raw tables (the wrapper is
  thin).
- Default-surface registration happens in `src/premura/mcp/entrypoint.py` (the
  live tool registry). Both new tools go on the **default** surface alongside the
  existing signal-backed tools.

## Subtasks

### T023 — `supplement_intake_adherence` tool wrapper (`mcp/server.py`)
- Thin wrapper delegating to the WP04 signal; passes through `matcher` +
  `window_days`; returns the standard envelope; preserves the structured
  `missing_input` report for missing/stale.

### T024 — `nutrition_intake_trend` tool wrapper (`mcp/server.py`)
- Thin wrapper delegating to the WP04 signal; passes through the nutrient/energy
  `key` + `window_days`; standard envelope.

### T025 — Register on the default surface (`mcp/entrypoint.py`)
- Add both tools to the default registry. Assert the tool count increases by two
  and both are **published** on the default surface (FR-006).

### T026 — Tool tests (`tests/test_mcp_intake_tools.py`)
- One successful call per tool (data present → `available` with result).
- `missing_input` / `stale_input` / `insufficient_data` tool-path tests, asserting
  **structurally distinct** states (not generic string errors).
- Assert no diagnosis/recommendation/causal language in the tool payloads (NFR-001
  at the surface).

## Branch Strategy

Plan/base branch **master**; final merge target **master**. Worktree per lane in
`lanes.json`. Implement with: `spec-kitty agent action implement WP05 --agent <name>`
(after WP04 is approved).

## Test Strategy (test-first)

Write `tests/test_mcp_intake_tools.py` first (publication + one happy call + three
refusal states per tool), then implement the wrappers and registration. Assert via
tool payloads only.

## Definition of Done

- [ ] Both tools published on the default surface; tool count +2 (FR-006).
- [ ] Each tool returns the standard envelope; missing/stale/insufficient are structurally distinct.
- [ ] Wrappers are thin — no intake semantics re-derived from raw tables.
- [ ] No diagnosis/recommendation language at the surface (NFR-001); no network (NFR-002).
- [ ] ruff + ruff format + mypy + pytest green.

## Risks

- **Wrapper re-derives semantics.** Mitigation: assert the wrapper only calls the
  signal and shapes the envelope; reviewer checks for any SQL/compute in the
  wrapper.
- **Operator surface drift.** Confirm the tools land on the **default** surface
  (not only the operator surface), since "usable by an agent" is the goal.

## Reviewer Guidance

- Confirm parameter pass-through matches the WP04 signal signatures.
- Confirm both tools are on the default registry and the count assertion is exact.
