---
work_package_id: WP06
title: MCP Analytical Exposure
dependencies:
- WP05
requirement_refs:
- FR-002
- FR-009
- FR-010
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
agent: "claude:opus:reviewer:reviewer"
shell_pid: "64832"
history:
- 2026-05-29T15:18:42Z tasks generated
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- tests/test_mcp_analytical_tools.py
tags: []
---

# WP06: MCP Analytical Exposure

## Objective

Expose `change_point` and `smoothed_average` on the default MCP surface with thin wrappers and complete final validation.

## Branch Strategy

Planning/base branch: `master`. Final merge target: `master`. This WP depends on WP05. Implementation worktrees are allocated per computed lane from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP06 --agent <name>
```

## Context

Read:

- `src/premura/mcp/server.py`
- `src/premura/mcp/entrypoint.py`
- `src/premura/engine/analytical.py`
- `kitty-specs/stage-3-analytical-tools-01KST48C/contracts/mcp-analytical-tools.md`
- `tests/test_mcp_signal_tools.py`
- `tests/test_mcp_server.py`

## Detailed Guidance

### T021: Add MCP server wrappers for `change_point` and `smoothed_average`

Add thin wrapper functions in `src/premura/mcp/server.py`.

Wrappers should:

- validate caller-facing parameter shape only
- open the warehouse through existing safe paths
- call the engine analytical public surface
- serialize the engine outcome

Wrappers must not:

- query raw fact tables directly
- implement statistical computation
- invent caveat or estimate values

### T022: Register analytical tools on the default MCP surface

Update `src/premura/mcp/entrypoint.py` to expose both proof tools on the default agent-safe surface.

Keep `query_warehouse` isolated to the operator surface.

### T023: Add MCP analytical-tool tests for success and refusal payloads

Create `tests/test_mcp_analytical_tools.py`.

Cover:

- default surface includes `change_point`
- default surface includes `smoothed_average`
- success payload contains `tool_name`, `status`, `message`, and `result`
- non-refusal result includes analytical envelope metadata
- refusal payload has distinct reason and no estimate
- wrappers delegate to engine behavior rather than raw SQL

### T024: Run final quality gates and document any unrelated pre-existing failures

Run:

```bash
ruff check .
ruff format --check .
mypy src
pytest -q
```

If unrelated pre-existing failures appear, document them in the WP result with a one-line rationale.

## Definition of Done

- Both analytical tools are available on the default MCP surface.
- MCP tests cover success and refusal payloads.
- Final quality gates are run and results are reported.

## Risks

- Accidentally putting statistical behavior in MCP wrappers would break the engine-owned boundary.

## Reviewer Guidance

Focus on boundary discipline: MCP should serialize and delegate, not compute.

## Activity Log

- 2026-05-29T15:59:39Z – claude:opus:implementer:implementer – shell_pid=52112 – Started implementation via action command
- 2026-05-29T16:15:52Z – claude:opus:implementer:implementer – shell_pid=52112 – Ready for review: change_point and smoothed_average exposed on default MCP surface via thin delegating wrappers; query_warehouse stays operator-only; full suite 466 passed
- 2026-05-29T16:16:29Z – claude:opus:reviewer:reviewer – shell_pid=64832 – Started review via action command
- 2026-05-29T16:21:23Z – claude:opus:reviewer:reviewer – shell_pid=64832 – Review passed: thin change_point+smoothed_average wrappers added (no SQL/compute, delegate to engine public surface), registered on default surface via _register_default_tools (both surfaces) while query_warehouse stays operator-only; 12-key end-to-end refusal chain verified; 466 passed; mission files clean on ruff/format/mypy; extra edits to test_mcp_server/signal_tools are minimal additive surface-snapshot updates only
