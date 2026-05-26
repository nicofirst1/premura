---
work_package_id: WP04
title: Signal-Backed MCP Tools
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
- T021
agent: "claude:opus:reviewer:reviewer"
shell_pid: "71734"
history:
- timestamp: '2026-05-26T11:32:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- tests/test_mcp_signal_tools.py
tags: []
---

# Work Package Prompt: WP04 - Signal-Backed MCP Tools

## Objective

Expose the six new grounded Stage 2 answers through Stage 3 without disturbing the existing raw warehouse tools.

This WP is where the mission actually narrows the documented direct-read debt. The new Stage 3 tools should become the supported path for the six approved question shapes, while `query_warehouse`, `list_metrics`, and `metric_summary` remain available as exploratory utilities.

## Owned Surface

- `src/premura/mcp/server.py`
- `src/premura/mcp/entrypoint.py`
- `tests/test_mcp_signal_tools.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP04 --agent <name>`

## Subtasks

### T017 - Add six new signal-backed MCP server wrappers

**Purpose**

Expose the approved answers through stable Stage 3 tool functions that delegate to the engine rather than to raw SQL queries.

**Required changes**

- Extend `src/premura/mcp/server.py` with wrappers for:
  - `resting_hr_status`
  - `resting_hr_trend`
  - `steps_trend`
  - `weight_trend`
  - `sleep_deep_pct_baseline`
  - `hrv_change_around_date`
- Each wrapper should:
  - open the warehouse through the existing safe path
  - call the relevant Stage 2 signal
  - return a structured, JSON-safe response aligned with the planning contract

**Non-goals**

- Do not implement these answers in raw SQL here.
- Do not add any new statistics or PubMed behavior.

### T018 - Preserve the raw MCP tools unchanged

**Purpose**

Make sure the mission narrows direct-read debt without pretending the raw tools should disappear.

**Required behavior**

- Keep `query_warehouse`, `list_metrics`, and `metric_summary` intact in purpose and basic behavior.
- If refactoring is needed, it must be behavior-preserving for those existing tools.

**Specific review risk**

- Avoid opportunistic cleanup that changes the current raw-tool contract while adding the new signal-backed tools.

### T019 - Standardize Stage 3 failure and caveat serialization

**Purpose**

Give MCP callers a predictable way to understand freshness, missing-input, and insufficient-data states.

**Required behavior**

- Normalize how the new wrappers return:
  - successful results
  - missing-input states
  - stale-input states
  - insufficient-data states
- Keep the payloads plain and tool-friendly.
- Surface the user-facing message and the structured details together where appropriate.

### T020 - Publish all nine MCP tools through FastMCP

**Purpose**

Make the new tools actually reachable from the MCP entrypoint.

**Required changes**

- Update `src/premura/mcp/entrypoint.py`.
- Keep the current three raw tools published.
- Add the six new signal-backed tools with stable names and argument shapes.
- Ensure any tools needing parameters, such as lookback days or an anchor date, expose them clearly.

### T021 - Add MCP tool tests

**Purpose**

Lock the new Stage 3 surface through public tool calls.

**Required changes**

- Add `tests/test_mcp_signal_tools.py`.
- Cover at least:
  - tool registration includes all nine tools
  - one successful call for each result family
  - one missing or stale-input path
  - one insufficient-data path
  - preserved behavior of the existing raw tools
- Prefer public MCP entrypoint behavior where practical.

**Testing guidance**

- Reuse temporary DuckDB setup patterns from the current MCP tests.
- Keep assertions on structured tool responses.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest tests/test_mcp_signal_tools.py -q
uv run python -m pytest tests/test_mcp_server.py -q
```

Expected outcomes:

- The MCP entrypoint publishes nine tools total.
- The six new tools delegate to Stage 2-backed answers.
- The three raw tools remain available and behaviorally stable.

## Definition Of Done

- Stage 3 exposes six new signal-backed tools.
- Existing raw tools still work.
- Success, missing-input, stale-input, and insufficient-data states are serialized consistently.
- Focused MCP tool tests pass.

## Risks And Watchouts

- The highest risk is silently reintroducing raw-table logic inside the new wrappers.
- Another common failure mode is to collapse all non-success cases into a generic error rather than a structured unavailable reason.

## Reviewer Guidance

Review this WP as a boundary-enforcement change. The key question is whether the new Stage 3 tools genuinely route through Stage 2 and tell the truth about why an answer is or is not available.

## Activity Log

- 2026-05-26T12:20:03Z – claude:opus:implementer:implementer – shell_pid=38372 – Started implementation via action command
- 2026-05-26T12:26:26Z – claude:opus:implementer:implementer – shell_pid=38372 – Boundary note: WP04 publishes 9 tools. Two registry-membership assertions in tests/test_mcp_server.py (test_build_server_registers_expected_tools, test_stdio_mcp_server_exposes_tools) hardcode exactly the 3 raw tools as the complete registry, which WP04's stated goal invalidates. WP04 validation block mandates test_mcp_server.py and full suite stay green. Making the minimal behavior-preserving update: expand those two expected-tool lists from 3 to 9 names. Raw-tool per-tool behavior tests are untouched. File is outside the explicit owned-files set but the conflict is forced by the WP's own validation contract.
- 2026-05-26T12:29:27Z – claude:opus:implementer:implementer – shell_pid=38372 – Ready for review: six signal-backed MCP tools routing through engine, three raw tools preserved, structured unavailable-state serialization, nine tools published
- 2026-05-26T12:30:10Z – claude:opus:reviewer:reviewer – shell_pid=71734 – Started review via action command
- 2026-05-26T12:33:37Z – claude:opus:reviewer:reviewer – shell_pid=71734 – Review passed: BOUNDARY ENFORCEMENT verified — independent grep of signal-backed section (server.py line 180+) found ZERO raw SQL (no SELECT/INSERT/UPDATE/DELETE/FROM hp./fact_measurement/fact_interval/conn.execute/dim_metric); all six wrappers route through engine.compute() and comparative_signals.hrv_change_around_date(). Raw SQL confined to pre-existing list_metrics/metric_summary. _open_warehouse extraction is behavior-preserving (same read_only=True path + try/finally close) for query_warehouse; raw-tool contract unchanged. FOUR-STATE serialization structurally distinct via status field: available / missing_input (family==missing_input OR freshness==unavailable) / stale_input (freshness==stale) / insufficient_data (sufficient_data False, trend_direction==unknown, or comparison_state==unknown) — not collapsed into generic error. NINE tools confirmed published through FastMCP entrypoint (3 raw + 6 new). hrv_change_around_date passes user-supplied parsed anchor to explicit-anchor engine path (not midpoint default), verified by test asserting anchor_date passthrough. Tests cover registration=9, one success per family, missing/stale, insufficient-data x2, preserved raw tools, public entrypoint reachability. test_mcp_server.py out-of-scope edit is STRICTLY membership-list expansion 3->9 (new _EXPECTED_TOOLS constant); NO raw-tool behavior assertion weakened/removed — forced-by-design and acceptable. Validation: test_mcp_signal_tools+test_mcp_server 26 passed; full suite 131 passed.
