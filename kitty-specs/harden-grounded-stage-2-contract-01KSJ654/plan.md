# Implementation Plan: Harden Grounded Stage 2 Contract

**Branch**: `master` (planning base and merge target) | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/harden-grounded-stage-2-contract-01KSJ654/spec.md`

## Summary

Close four contract gaps left by `implement-grounded-stage-2-functions-01KSHZPC`,
without adding answers or analysis:

1. **Surface FR-008 fully.** The Stage 3 server already classifies unavailable
   answers into `missing_input` / `stale_input` / `insufficient_data`. Extend the
   serializer so that, when the answer is unavailable, it (a) uses the signal's
   registered `missing_input_hint` as the user-facing message, and (b) attaches a
   structured `MissingInputReport` (`required_inputs` / `missing_inputs` /
   `stale_inputs`) built from the signal's declared `inputs` and the result's
   freshness/availability. This consumes two already-shipped-but-dead surfaces
   (`missing_input_hint` and `MissingInputReport`).
2. **Loader honesty.** Replace `if REGISTRY: return` in
   `_ensure_builtin_signals_loaded()` with an explicit module-level
   `_BUILTINS_LOADED` flag so pre-registering a custom signal cannot suppress
   built-ins.
3. **Baseline honesty.** Make `BaselineComparisonResult.latest_value` and
   `baseline_mean` `float | None`, add a `validate()` that forbids a numeric value
   when `comparison_state` is `UNKNOWN` or `freshness_state` is `UNAVAILABLE`, and
   stop the `0.0` coercion in `comparative_signals.py`.
4. **Coverage.** Add a `weight_trend` end-to-end Stage 3 call test.

## Technical Context

**Language/Version**: Python 3.x (existing `premura` package, `uv`-managed)
**Primary Dependencies**: DuckDB warehouse, FastMCP (Stage 3), existing engine
registry/result envelopes. No new dependencies.
**Storage**: Existing `hp.*` DuckDB warehouse; no schema changes.
**Testing**: `uv run python -m pytest`; temp-DuckDB fixtures already used by
engine and MCP tests.
**Target Platform**: Local-first CLI/MCP server.
**Project Type**: Single project (`src/premura/...`).
**Performance Goals**: Unchanged; no new hot paths.
**Constraints**: Non-diagnostic; lazy-load boundary preserved; raw-tool contract
unchanged; profile-dependent work deferred to `#6`.
**Scale/Scope**: ~5 source files + their tests; surgical changes only.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No `.kittify/charter/charter.md` present — Charter Check **skipped** (governance
context loaded in `compact` mode; directives DIRECTIVE_010/024/028/030/033/034/036
apply via the software-dev-default template). No gate violations: the mission adds
no new architecture, keeps changes additive/behavior-preserving, and respects the
existing stage boundary.

## Project Structure

### Documentation (this feature)

```
kitty-specs/harden-grounded-stage-2-contract-01KSJ654/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (envelope/report shape changes)
├── quickstart.md        # Phase 1 output (validation commands)
├── contracts/           # Phase 1 output (Stage 3 unavailable-response contract)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/premura/engine/
├── _results.py            # FR-005: BaselineComparisonResult -> float|None + validate();
│                          #         (MissingInputReport already defined here)
├── __init__.py            # FR-004: explicit _BUILTINS_LOADED flag in loader
├── _registry.py           # (read-only) source of `inputs` + `missing_input_hint`
├── descriptive_signals.py # (read-only) authored hints
└── comparative_signals.py # FR-005: stop 0.0 coercion in sleep_deep_pct_baseline

src/premura/mcp/
└── server.py              # FR-001/002/003: serialize hint as message + attach
                           #                 structured MissingInputReport

tests/
├── test_engine_contract.py            # FR-004 loader regression test
├── test_engine_comparative_signals.py # FR-005 baseline no-fabrication test
└── test_mcp_signal_tools.py           # FR-001/002/003 actionable-guidance asserts;
                                       # FR-006 weight_trend Stage 3 call test
```

**Structure Decision**: Single-project layout; all edits land in the existing
`src/premura/engine`, `src/premura/mcp`, and `tests/` trees listed above. No new
modules or packages.

## Phase 0 — Research

No open unknowns: the post-merge review and the spec already fix the approach.
See [research.md](research.md) for the three small design decisions (where to
build the `MissingInputReport`, how to derive missing vs. stale inputs, and how
to keep the loader lazy while tracking load state).

## Phase 1 — Design & Contracts

- [data-model.md](data-model.md): the `BaselineComparisonResult` field-nullability
  change + `validate()` rule, and the `MissingInputReport` fields as they appear in
  a serialized Stage 3 response.
- [contracts/](contracts/): the Stage 3 unavailable-response contract — what an
  `missing_input` / `stale_input` / `insufficient_data` payload must contain.
- [quickstart.md](quickstart.md): the exact validation commands.

## Complexity Tracking

No Charter Check violations; table not applicable.
