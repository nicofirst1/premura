---
work_package_id: WP02
title: Rolling Mean Engine Tool
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- FR-009
- FR-014
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "42142"
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/rolling_mean.py
- tests/test_engine_rolling_mean.py
tags: []
---

# Work Package Prompt: WP02 - Rolling Mean Engine Tool

## Implement Command

```bash
spec-kitty agent action implement WP02 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Implement `rolling_mean` as an engine-owned analytical tool. It should consume
one admitted ordered series, emit a moving-window series with per-point coverage,
and return the existing analytical envelope shape. This WP does not publish the
tool through the default loader or MCP; WP05 owns publication.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/data-model.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/contracts/rolling-mean-contract.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/research.md`

## Owned Files

- `src/premura/engine/rolling_mean.py`
- `tests/test_engine_rolling_mean.py`

Do not edit `src/premura/engine/analytical.py`, `src/premura/mcp/server.py`,
`src/premura/trace.py`, or live docs in this WP.

## Subtasks

### T006: Add failing rolling-mean acceptance tests for available envelopes

Create `tests/test_engine_rolling_mean.py` and start with synthetic
`AnalyticalInputSeries` fixtures.

Acceptance tests should prove an available result includes:

- `tool_name="rolling_mean"`.
- `status="available"`.
- Declared `window` and `min_coverage` parameters.
- Ordered summary points.
- Per-point coverage and imputation counts.
- Source input sample size and emitted point count.
- A closed-vocabulary confound checklist.

Test through the analytical tool function or direct registration import for this
WP. Do not require default publication; WP05 owns built-in loading.

### T007: Add failing rolling-mean refusal tests for invalid windows, weak coverage, and refused input

Add refusal fixtures before implementing happy-path logic.

Required refusal cases:

- Input series already carries a refusal.
- `window` is zero or negative.
- `window` exceeds the supported maximum.
- `min_coverage` is outside `[0.0, 1.0]`.
- No window reaches the required coverage.
- Caller asks for any auto-window-selection parameter if such a shape appears.

Every refusal must return no estimate and a machine-readable refusal reason.

### T008: Implement the deterministic `rolling_mean` tool registration and estimate payload

Add `src/premura/engine/rolling_mean.py` with a registered analytical tool.

Implementation guidance:

- Use the existing `analytical_tool` decorator and `AnalyticalResultEnvelope`.
- Obtain computation points only through the same public preparation seam used by
  existing tools.
- Use fixed rounding conventions already used in analytical tools so repeated
  serialization is byte-stable.
- Preserve point ordering by timestamp.
- Do not read DuckDB, MCP state, trace state, clock time, filesystem, or network.

Expected estimate shape should follow `data-model.md` and may be represented as
plain JSON-safe mapping inside the existing envelope.

### T009: Add rolling-mean caveats/confounds and forbidden-language assertions

Add tests and implementation for caveats/confounds.

At minimum consider:

- `low_sample_size` when emitted support is near the floor.
- `high_imputation` when imputation share is high.
- `short_overlap_window` or similar closed key when the admitted span is short.
- `parameter_at_limit` when the requested window or coverage sits at a bound.
- `method_uncertainty_unavailable` if the result does not carry a natural
  uncertainty interval.

Forbidden language assertions should reject built-in messages containing cause,
effect, significant, diagnosis, treatment, dosing, emergency, or population-norm
claims.

### T010: Keep rolling-mean runtime local, deterministic, and independent of MCP/trace

Add a focused import/runtime test that guards against accidental dependency creep.

The test should assert:

- Importing `premura.engine.rolling_mean` does not import MCP or trace modules.
- The module does not require network/PubMed/runtime HTTP dependencies.
- Two identical calls produce byte-equivalent `to_dict()` output.

Definition of done:

- `rolling_mean` can be registered and called directly from engine tests.
- No default public surface or MCP wrapper is required yet.
- Every available/refusal behavior in this WP is covered by synthetic fixtures.

## Test Strategy

Run:

```bash
uv run python -m pytest tests/test_engine_rolling_mean.py -q
```

If WP01 changed policy types, also run:

```bash
uv run python -m pytest tests/test_engine_policy_finish_tool_set.py -q
```

## Risks

- Accidentally duplicating `smoothed_average` without the rolling-series payload.
- Emitting too much prose instead of machine-readable point metadata.
- Creating MCP or trace coupling inside the engine.

## Reviewer Guidance

Review the result envelope shape and refusal behavior first. Then verify the tool
does not reach outside the engine and does not rely on default publication.

## Activity Log

- 2026-06-01T07:21:49Z – claude:opus:python-implementer:implementer – shell_pid=23594 – Started implementation via action command
- 2026-06-01T07:31:29Z – claude:opus:python-implementer:implementer – shell_pid=23594 – Ready for review: rolling_mean deterministic moving-window tool over one admitted ordered series (MOVING_WINDOW_PATTERN, WP01 vocabulary). Emits per-point coverage+imputation series in shared envelope; 8 refusal fixtures incl. FR-014 window-scan rejection; window>=2/365 max/0.5 coverage defaults; live-registered in shared REGISTRY + dispatch. 27 new tests green, full analytical regression passes, ruff/format/mypy clean.
- 2026-06-01T07:32:08Z – claude:opus:python-reviewer:reviewer – shell_pid=42142 – Started review via action command
- 2026-06-01T07:36:35Z – claude:opus:python-reviewer:reviewer – shell_pid=42142 – Review passed. rolling_mean is a bounded abstraction (declared trailing moving-window over any admitted ordered series via MOVING_WINDOW_PATTERN; no metric hardcoding), consumes WP01 vocabulary without redefining it. FR-002 envelope reports window/min_coverage/per-point coverage+imputation/emitted+blank counts/input span via the shared AnalyticalResultEnvelope (FR-008). 8 refusal fixtures spanning 3 distinct machine-readable reasons (unsupported_parameter, insufficient_data, insufficient_coverage), all no-estimate. Under-covered windows blank rather than fabricate; missingness stays visible. FR-014 scan-rejection: any extra positional/kwarg refused BEFORE computation. Determinism (NFR-001) byte-stable; no MCP/trace/network coupling (subprocess import probe). Forbidden causal/diagnostic/significance/prediction language absent; caveats <=320 chars. Gates: ruff/format/mypy clean on changed files; full suite 680 passed (no existing analytical/trace expectation broke, NFR-008 preserved). Only the two owned files touched. RULING on default-surface deferral to WP05: CORRECT, not a dead-code gap. WP02 owns ONLY rolling_mean.py + its test and is explicitly forbidden from editing analytical.py. FR-001 is intentionally split: WP02 makes the tool registerable+dispatchable-when-imported through the shared REGISTRY/dispatch (verified: import fires decorator, dispatch('rolling_mean',...) == direct call), while WP05 owns analytical.py and its task literally says 'Update analytical.py static built-in module/name lists' to publish it. list_analytical_tools() enumerates the static _BUILTIN_ANALYTICAL_MODULES/_NAMES, so the default surface returns only the 3 shipped tools until WP05 wires it — structural, not an oversight. Live registration consumer exists today (REGISTRY + dispatch + 27 passing tests), so this is not a module-with-zero-callers. SC-001's five-tool default discovery legitimately lands in WP05.
