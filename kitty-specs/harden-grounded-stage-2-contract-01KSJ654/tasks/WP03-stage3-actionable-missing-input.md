---
work_package_id: WP03
title: Stage 3 Actionable Missing-Input And Coverage
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-008
- NFR-002
- NFR-003
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
history: []
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- tests/test_mcp_signal_tools.py
tags: []
agent: "claude:opus:reviewer:reviewer"
shell_pid: "42157"
---

# Work Package Prompt: WP03 — Stage 3 Actionable Missing-Input And Coverage

## Objective

Deliver FR-008 for real. The engine already authors a `missing_input_hint` on
every signal and defines a `MissingInputReport` type — but the Stage 3 MCP layer
reads neither, so a user with no recorded data gets a generic "no value recorded"
message instead of actionable guidance like "Connect a wearable that records
resting heart rate." This WP wires the authored guidance and a structured
required/missing/stale-input report into the Stage 3 responses, strengthens the
tests to constrain that behavior, and closes the `weight_trend` coverage gap.

## Owned Surface

- `src/premura/mcp/server.py`
- `tests/test_mcp_signal_tools.py`

Do not modify files outside this list. The engine envelopes and registry are
owned by WP01/WP02; only READ them here.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Dependency: **WP02** (this WP consumes the honest baseline shape; the baseline
  unavailable test here asserts `None` numerics that WP02 introduces).
- Execution branch allocation: computed from `lanes.json` during implement.

## Background to read first

- `src/premura/mcp/server.py`: `_serialize_signal_result`, `_classify_result_status`
  (the four statuses: `available` / `missing_input` / `stale_input` /
  `insufficient_data`), and `_result_message`. These are the boundary you extend.
- `src/premura/engine/_registry.py` (`SignalSpec`): each signal carries `inputs`
  (list of metric ids) and `missing_input_hint` (the actionable text). Both are
  reachable from the server via the registry.
- `src/premura/engine/_results.py` (`MissingInputReport.to_dict()`): the
  structured shape you will emit (`required_inputs`, `missing_inputs`,
  `stale_inputs`, `message`, `family="missing_input"`).
- `src/premura/engine/descriptive_signals.py` / `comparative_signals.py`: the
  authored hint strings, so your tests can assert the real text.
- Mission `data-model.md` and `contracts/stage3-unavailable-response.md`: the
  exact response contract this WP must satisfy.

## Subtasks

### T006 — Build the structured missing-input report at the boundary

**Purpose**: Give callers machine-readable detail about what data an unavailable
answer needs.

**Required changes** (`src/premura/mcp/server.py`)

- When serializing a result whose status is `missing_input` or `stale_input`,
  construct a `MissingInputReport` (import from `premura.engine`) using:
  - `tool_name`: the tool name.
  - `required_inputs`: the signal's declared `inputs` from the registry
    (`REGISTRY[spec_name].inputs`).
  - `missing_inputs`: the required input(s) when the answer is `missing_input`
    (the value is absent / freshness unavailable).
  - `stale_inputs`: the required input(s) when the answer is `stale_input`.
  - `message`: the signal's `missing_input_hint`.
- All six approved signals are single-input today, so map the single declared
  input to `missing_inputs` (missing case) or `stale_inputs` (stale case)
  accordingly. Keep the logic simple and correct for the single-input case; do
  not invent per-input plumbing.

**Constraint**: do not change how the engine produces results; build the report
purely from data already available at the serialization boundary.

### T007 — Use the actionable hint as the user-facing message

**Required changes** (`src/premura/mcp/server.py`)

- For unavailable answers (`missing_input`, and where appropriate `stale_input`),
  set the response `message` to the signal's `missing_input_hint` (actionable),
  instead of the generic value-absent caveat.
- If a signal somehow lacks a hint, fall back to the current message (do not
  crash). Keep `available` and `insufficient_data` (fresh-but-sparse) messages as
  they are.

### T008 — Attach the structured block; keep statuses distinct

**Required changes** (`src/premura/mcp/server.py`)

- Add the serialized `MissingInputReport.to_dict()` to the response under a
  stable key (e.g. `missing_input`) for `missing_input` and `stale_input`
  statuses only.
- Leave the existing keys (`tool_name`, `status`, `message`, `result`) intact.
- Do NOT add the block to `available` or to pure `insufficient_data` (fresh input,
  too sparse) responses — the input is present there.
- Preserve the four structurally-distinct statuses (FR-003). The three raw tools
  (`query_warehouse`, `list_metrics`, `metric_summary`) are out of scope and
  unchanged.

### T009 — Strengthen the missing/stale tests

**Required changes** (`tests/test_mcp_signal_tools.py`)

- Upgrade the missing-input test(s) so they assert:
  - `status == "missing_input"`,
  - the `message` CONTAINS the signal's specific actionable hint substring (e.g.
    the resting-HR hint text), not merely `assert payload["message"]`,
  - the response carries `missing_input.required_inputs` and `missing_inputs`
    naming the input (e.g. `resting_hr`).
- Add/upgrade a stale-input test asserting `status == "stale_input"` and
  `missing_input.stale_inputs` names the input.
- Add a baseline unavailable/unknown test (consumes WP02) asserting the serialized
  `result` numeric fields are `null`, not `0.0`.
- Keep existing assertions for the `available` cases.

### T010 — `weight_trend` end-to-end Stage 3 test

**Required changes** (`tests/test_mcp_signal_tools.py`)

- Add an end-to-end test that calls the `weight_trend` tool through the Stage 3
  surface (`server.weight_trend(...)`, matching the pattern used for the other
  five signals) with a seeded warehouse, and asserts a sensible structured
  response (e.g. `status == "available"` and `result.family == "trend"` for a
  populated series). This satisfies the "all six approved questions covered
  end-to-end" promise (FR-006 / the original NFR-002).

## Validation

```bash
uv run python -m pytest tests/test_mcp_signal_tools.py -q
uv run python -m pytest tests/test_mcp_server.py -q     # raw tools unaffected
uv run python -m pytest tests/ -q                       # full suite green
```

## Definition of Done

- An unavailable approved answer returns the signal's actionable hint as
  `message` AND a structured `missing_input` block with required/missing/stale
  fields.
- The four statuses remain distinct; raw tools unchanged.
- Tests constrain the actionable guidance and structured fields (not "some
  message"); a baseline unavailable case asserts `null` (not `0.0`).
- `weight_trend` has an end-to-end Stage 3 call test; full suite is green.

## Risks & Watchouts

- The single-input mapping is correct today but write it so it doesn't silently
  break if a signal declared multiple inputs (map all declared inputs, don't
  hard-code one).
- Don't attach the structured block where the input is actually present
  (`available`, fresh-but-sparse `insufficient_data`) — that would misreport.
- Ensure the baseline test depends on WP02 being merged in the lane (it will be,
  since WP03 depends on WP02).

## Reviewer Guidance

Trace FR-008 end to end: confirm `missing_input_hint` is now READ (not just
defined) and reaches the user-facing `message`, and that `MissingInputReport` is
actually CONSTRUCTED and serialized — grep that both have a live consumer now.
Verify the tests would fail against the old "generic message only" behavior.
Confirm the six approved questions each have a Stage 3 call test.

## Activity Log

- 2026-05-26T13:24:07Z – claude:opus:implementer:implementer – shell_pid=23126 – Started implementation via action command
- 2026-05-26T13:28:43Z – claude:opus:implementer:implementer – shell_pid=23126 – Ready for review: FR-008 delivered — actionable hint as message + structured MissingInputReport for missing/stale; baseline null test; weight_trend e2e test
- 2026-05-26T13:29:17Z – claude:opus:reviewer:reviewer – shell_pid=42157 – Started review via action command
