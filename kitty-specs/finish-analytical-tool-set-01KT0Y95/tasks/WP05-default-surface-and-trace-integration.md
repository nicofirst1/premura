---
work_package_id: WP05
title: Default Surface And Trace Integration
dependencies:
- WP02
- WP04
requirement_refs:
- FR-010
- FR-011
- FR-012
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During implementation this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical.py
- src/premura/engine/__init__.py
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- src/premura/trace.py
- tests/test_engine_finished_tool_set_public_surface.py
- tests/test_mcp_finished_tool_set.py
- tests/test_trace_finished_tool_set.py
tags: []
---

# Work Package Prompt: WP05 - Default Surface And Trace Integration

## Implement Command

```bash
spec-kitty agent action implement WP05 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Publish `rolling_mean` and simple anchor-date `paired_t_test` through the public
engine facade, default MCP surface, and session research trace identity registry.
This WP wires surfaces only; it must not change either tool's method logic.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/plan.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/contracts/rolling-mean-contract.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/contracts/paired-t-test-contract.md`
- Tool modules from WP02 and WP04

## Owned Files

- `src/premura/engine/analytical.py`
- `src/premura/engine/__init__.py`
- `src/premura/mcp/server.py`
- `src/premura/mcp/entrypoint.py`
- `src/premura/trace.py`
- `tests/test_engine_finished_tool_set_public_surface.py`
- `tests/test_mcp_finished_tool_set.py`
- `tests/test_trace_finished_tool_set.py`

Do not edit tool method modules in this WP except to fix an integration defect
that cannot be solved through publication/wrapper code.

## Subtasks

### T021: Publish both tools through the analytical built-in loader and public engine surface

Add failing tests in `tests/test_engine_finished_tool_set_public_surface.py`.

Tests should assert:

- `list_analytical_tools()` includes five built-ins: `change_point`,
  `smoothed_average`, `correlate`, `rolling_mean`, and `paired_t_test`.
- The loader uses the static in-tree module list, not filesystem scanning.
- Public exports include any request/input types agents or MCP wrappers need.
- Existing tools remain discoverable and unchanged.

Implementation guidance:

- Update `src/premura/engine/analytical.py` static built-in module/name lists.
- Update `src/premura/engine/__init__.py` exports only for public names required
  by MCP wrappers or tool authors.
- Do not add a plugin loader.

### T022: Add thin default MCP wrappers for `rolling_mean` and simple `paired_t_test`

Add failing tests in `tests/test_mcp_finished_tool_set.py`.

Wrapper behavior:

- Validate caller-facing shape only.
- Read evidence through existing engine-owned query/preparation path.
- For `rolling_mean`, prepare one admitted series and dispatch the engine tool.
- For `paired_t_test`, prepare one admitted series, build simple before/after
  paired input, then dispatch the engine tool.
- Serialize engine envelopes unchanged.

Do not compute rolling means, pair differences, caveats, confounds, or
uncertainty in MCP code.

### T023: Add trace normalized hypothesis identities for both new tools

Add tests in `tests/test_trace_finished_tool_set.py` for identity normalization.

Expected identity fields:

- `rolling_mean`: metric id, window, minimum coverage.
- `paired_t_test`: metric id, anchor date, before days, after days, expected
  direction.

Tests should prove:

- Omitted defaults and explicit defaults collapse where defaults are supported.
- Different windows or anchors are different hypotheses.
- Identity registration happens through the trace registry seam, not a disclosure
  counting branch.

### T024: Add MCP and trace tests for publication, recording, exact retries, refusals, and surfaced marks

Add end-to-end tests through public MCP/trace surfaces.

Scenarios:

- A traced `rolling_mean` call records exactly one analytical call.
- A traced `paired_t_test` call records exactly one analytical call.
- Exact retries collapse in unique hypothesis count.
- Refused calls count toward examined hypotheses and refusal breakdown.
- Surfaced marks can target calls from both tools.
- Non-analytical calls still do not count.

### T025: Verify traced and untraced engine envelopes remain byte-equivalent aside from trace metadata

Add regression tests mirroring the existing trace purity tests.

For each new tool:

- Call without `session_id` and capture serialized engine envelope.
- Call with `session_id` and remove wrapper-level trace metadata.
- Assert the remaining payload is byte-equivalent.

This protects the rule that trace recording happens around dispatch, not inside
the engine.

Definition of done:

- Default MCP surface exposes the two new tools.
- Operator surface inherits them as part of the default set if that is the
  existing pattern.
- Trace disclosure handles both tools by normalized identity.

## Test Strategy

Run:

```bash
uv run python -m pytest tests/test_engine_finished_tool_set_public_surface.py -q
uv run python -m pytest tests/test_mcp_finished_tool_set.py -q
uv run python -m pytest tests/test_trace_finished_tool_set.py -q
```

Also run existing trace/MCP tests if focused tests pass:

```bash
uv run python -m pytest tests/test_mcp_trace_recording.py tests/test_mcp_analytical_tools.py tests/test_trace_store.py -q
```

## Risks

- MCP wrappers can accidentally duplicate engine logic. Keep them thin.
- Trace identity drift can make disclosure counts misleading. Pin defaults in
  tests if duplicated literals are necessary to keep trace engine-import-free.

## Reviewer Guidance

Review this WP by following one call path per tool: MCP wrapper -> engine prepare
-> engine dispatch -> serialized envelope -> trace recording. Any computation in
MCP or trace is a red flag.
