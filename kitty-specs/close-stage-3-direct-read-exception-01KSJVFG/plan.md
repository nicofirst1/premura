# Implementation Plan: Close the Stage 3 Direct-Read Exception
*Path: `kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/plan.md`*


**Branch**: `master` | **Date**: 2026-05-27 | **Spec**: `kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/spec.md`
**Input**: Feature specification from `kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `src/specify_cli/missions/software-dev/command-templates/plan.md` for the execution workflow.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

Close the last Stage 3 direct-read exception by moving `list_metrics` and `metric_summary` behind new validity-gated Stage 2 engine helpers, while splitting `query_warehouse` into a separate operator entrypoint. The default `premura-mcp` surface becomes fully doctrine-compliant and agent-safe; a new operator entrypoint keeps raw SQL available for expert use and for explicitly user-approved advanced agent exploration. The operator entrypoint shares the same server core but registers one extra low-guarantee tool and is intentionally allowed to diverge later.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `mcp` Python SDK / FastMCP surface, DuckDB >=1.1, Polars, Typer, Pydantic settings  
**Storage**: Local DuckDB warehouse (`data/duck/health.duckdb`) in read-only mode for Stage 3  
**Testing**: `pytest -q`, with MCP server tests, signal-tool tests, engine lazy-load contract tests, and full regression suite where practical  
**Target Platform**: macOS primary, but warehouse and encrypted artifacts remain cross-platform portable  
**Project Type**: Single Python project with `src/premura/` package and `tests/`  
**Performance Goals**: Preserve charter soft targets: non-ingest CLI verbs under 2 s; no noticeable regression in MCP startup or tool invocation latency  
**Constraints**: Reuse existing freshness vocabulary and Stage 2 primitives; preserve engine lazy-load behavior; keep outputs non-diagnostic; explicit user approval required before any agent switches to the operator entrypoint  
**Scale/Scope**: Focused cross-package refactor spanning `src/premura/engine/`, `src/premura/mcp/`, targeted tests, and the relevant docs / ADR only

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **DIRECTIVE_010 / 024**: Keep the change faithful to the spec and tightly scoped to engine catalog helpers, MCP entrypoints, tests, and docs. No unrelated refactors.
- **DIRECTIVE_030 / 034 / 036**: Add failing tests first for default-vs-operator entrypoint registration and for validity-gated catalog / summary behavior. Assert through public interfaces only.
- **Quality gates**: `ruff`, `mypy` on changed scope, and `pytest -q` must be green before review handoff.
- **Risk boundaries**: Default agent surface must remain fully validity-gated. Operator/raw mode may exist only behind an explicit separate entrypoint and requires explicit user approval before an agent uses it. No live API access, no PHI leakage, no diagnostic overreach.
- **Status**: PASS for Phase 0 research. No charter conflict remains after the planning clarifications.

## Project Structure

### Documentation (this feature)

```
kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── default-agent-surface.yaml
│   └── operator-entrypoint.yaml
└── tasks.md             # Created later by /spec-kitty.tasks
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
src/
└── premura/
    ├── cli.py
    ├── config.py
    ├── engine/
    │   ├── __init__.py
    │   ├── _query.py
    │   ├── _registry.py
    │   ├── _results.py
    │   ├── descriptive_signals.py
    │   ├── comparative_signals.py
    │   └── lab_ratios.py
    └── mcp/
        ├── __init__.py
        ├── entrypoint.py
        └── server.py

tests/
├── test_engine.py
├── test_engine_contract.py
├── test_mcp_server.py
├── test_mcp_signal_tools.py
└── test_skeleton.py

docs/
├── architecture/STAGES.md
└── adr/
```

**Structure Decision**: Use the existing single-project Python layout. Add new Stage 2 catalog/summary helpers under `src/premura/engine/`, extend `src/premura/mcp/server.py` to consume them, and split entrypoint registration in `src/premura/mcp/entrypoint.py` so `premura-mcp` stays agent-safe while a new operator entrypoint can register `query_warehouse`.

## Complexity Tracking

No justified charter violations are planned.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
