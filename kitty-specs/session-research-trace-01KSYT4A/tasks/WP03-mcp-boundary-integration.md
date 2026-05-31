---
work_package_id: WP03
title: MCP Boundary Integration
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-009
- FR-010
- FR-011
- FR-012
- FR-015
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
- T019
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "18747"
history:
- timestamp: '2026-05-31T10:54:25Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/entrypoint.py
- tests/test_mcp_trace_tools.py
- tests/test_mcp_trace_recording.py
tags: []
---

# Work Package Prompt: WP03 – MCP Boundary Integration

## Implement Command

```bash
spec-kitty agent action implement WP03 --agent <name> --mission session-research-trace-01KSYT4A
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Expose the trace service through the MCP boundary and mechanically record analytical calls. The MCP layer is where the system observes tool use; the analytical engine must remain pure and produce the same envelopes with or without tracing.

## Dependencies

Depends on WP02 because this WP calls the `premura.trace` service API.

## Authoritative Inputs

- `kitty-specs/session-research-trace-01KSYT4A/spec.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/mcp-trace-tools.md`
- `kitty-specs/session-research-trace-01KSYT4A/quickstart.md`
- `src/premura/mcp/entrypoint.py`

## Owned Files

- `src/premura/mcp/entrypoint.py`
- `tests/test_mcp_trace_tools.py`
- `tests/test_mcp_trace_recording.py`

Do not modify migration files, `src/premura/trace.py`, live docs, or analytical engine code in this WP unless a discovered blocker requires renegotiating ownership.

## Subtasks

### T013: Add MCP trace tools for opening sessions, marking surfaced calls, and reading disclosure

Add tools to the shared default registration path in `src/premura/mcp/entrypoint.py`.

Expected tools:

- `research_trace_open(client_label: str | None = None)`.
- `research_trace_mark_surfaced(session_id, call_id, role, rationale)`.
- `research_trace_disclosure(session_id, format="json", include_calls=True)`.

These names are planned names. If implementation needs a slight name change, update contracts in WP04 and keep the semantics identical.

Default surface behavior:

- Trace tools belong on the default agent-safe surface because the trace is the supported agent workflow.
- Operator surface should inherit them because it adds `query_warehouse` on top of the full default set.

### T014: Wire analytical wrappers to record calls before/after dispatch when a `session_id` is supplied

Extend only the analytical MCP wrappers:

- `change_point`.
- `smoothed_average`.
- `correlate`.

Do not record:

- `list_metrics`.
- `metric_summary`.
- The six signal-backed Stage 2 tools unless the spec is amended later.
- Trace read/export tools.

Recording flow:

1. Validate enough input to know the request is an analytical question.
2. Ask `premura.trace` to start/record the call with normalized identity metadata.
3. Dispatch to the existing warehouse server/engine path.
4. Finish the trace record with available/refused/error status and result reference.

### T015: Preserve existing analytical behavior when no trace session is supplied

Tracing must be opt-in by explicit session association.

Tests should prove:

- Existing analytical MCP calls still work without `session_id`.
- Existing response shape remains compatible for untraced calls.
- No trace row is written when no session is supplied.

Avoid making `session_id` mandatory for analytical tools.

### T016: Return stable recorded-call references without changing engine result envelopes

The engine result envelope must stay byte-identical with tracing on vs off.

The MCP response may include trace metadata at the wrapper layer if needed, for example:

- Top-level wrapper metadata beside the engine envelope.
- A `trace` object containing `session_id`, `call_id`, and `result_id`.

Do not inject trace ids into the engine's serialized envelope object. The purity regression in T018 must catch that.

### T017: Add MCP tests for trace tools, analytical recording, refusals, retries, and non-analytical exclusions

Add `tests/test_mcp_trace_tools.py` and/or `tests/test_mcp_trace_recording.py`.

Required scenarios:

- `research_trace_open` returns required session fields.
- Mark surfaced succeeds for a call in the same session.
- Disclosure for unknown session returns explicit not-found.
- A successful analytical call is recorded.
- A refused analytical call is recorded and counted.
- Exact retry increases raw calls but not unique hypothesis count.
- `list_metrics`/`metric_summary` do not count as analytical calls.

Exercise through the MCP entrypoint/tool surface as much as existing tests allow.

### T018: Add engine-purity regression tests proving traced and untraced envelopes are byte-identical

Add a regression that compares the engine envelope content from an analytical tool with and without trace recording.

The exact approach can follow existing MCP analytical tests:

- Build a fixture warehouse.
- Invoke an analytical tool without `session_id`.
- Open a trace session.
- Invoke the same analytical tool with `session_id`.
- Compare the engine envelope portion after excluding MCP wrapper trace metadata.

This test exists to enforce NFR-001. If it fails, do not solve it by weakening the assertion; fix the boundary so trace metadata stays outside the engine envelope.

### T019: Verify operator surface inherits trace behavior without exposing new raw-health semantics

Add tests covering operator surface registration:

- Operator surface includes default trace tools plus `query_warehouse`.
- Operator surface still differs from default by exactly the raw SQL escape hatch if existing tests expect that pattern, adjusted for the new trace tools.
- Trace disclosure does not use `query_warehouse` or expose raw health rows.

This guards the stage boundary: trace is agent-safe provenance; `query_warehouse` remains lower-guarantee operator-only.

## Test Strategy

Run focused MCP trace tests:

```bash
uv run pytest tests/test_mcp_trace_tools.py tests/test_mcp_trace_recording.py -q
```

Run existing MCP tests because tool counts and surfaces will change:

```bash
uv run pytest tests/test_mcp_server.py tests/test_mcp_signal_tools.py tests/test_mcp_analytical_tools.py tests/test_mcp_correlate.py tests/test_mcp_trace_tools.py tests/test_mcp_trace_recording.py -q
```

## Definition Of Done

- Default MCP surface exposes trace session, mark, and disclosure tools.
- Analytical wrappers record calls only when explicitly associated with a session.
- Existing untraced analytical calls remain valid.
- Refusals, retries, and non-analytical exclusions are tested through the MCP boundary.
- Engine envelope purity is proven by regression tests.

## Reviewer Guidance

Reviewers should inspect boundary placement. MCP may orchestrate trace recording; it must not compute statistics, inspect raw `hp.*` rows directly for analysis, or mutate engine result envelopes.

## Activity Log

- 2026-05-31T11:30:56Z – claude:opus:python-implementer:implementer – shell_pid=8220 – Started implementation via action command
- 2026-05-31T11:44:00Z – claude:opus:python-implementer:implementer – shell_pid=8220 – Ready for review: MCP trace tools (open/mark/disclosure) on default surface + opt-in analytical recording on change_point/smoothed_average/correlate + engine-purity regression, all green
- 2026-05-31T11:44:38Z – claude:opus:python-reviewer:reviewer – shell_pid=18747 – Started review via action command
