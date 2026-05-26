# Implementation Plan: Implement Grounded Stage 2 Functions

**Branch**: `master` | **Date**: 2026-05-26 | **Spec**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/spec.md`
**Input**: Feature specification from `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/spec.md`
**Mission ID**: `01KSHZPCHTFN326808SW6FRVFE` (mid8: `01KSHZPC`)
**Mission type**: `software-dev`

## Summary

Implement one combined mission that turns the approved Stage 2 research outcome into shipped behavior. The mission will add six grounded Stage 2 answers, expose them through new Stage 3 MCP tools, keep the current raw Stage 3 tools in place, and tighten the engine seam so future non-profile-dependent Stage 2 additions are easier for contributors and agents to implement and submit as PRs.

This is a boundary-correction mission, not a full Stage 3 rewrite. The current direct-read debt in Stage 3 remains acceptable outside the six approved question shapes. Profile-dependent work remains deferred to issue `#6`.

## Planning Interrogation Record

### Confirmed answers

1. The mission lands on `master`.
2. This is one combined `software-dev` mission, not two sequential missions.
3. The mission updates Stage 3 now, not just Stage 2.
4. Stage 3 should keep the existing raw tools and also gain explicit signal-backed tools for the six approved answers.
5. The mission should strengthen the Stage 2 engine seam in code, not just in docs, so future agent-authored extensions are easier to add and review.

### Engineering alignment

- Keep existing Stage 3 raw tools stable: `query_warehouse`, `list_metrics`, `metric_summary`.
- Add six new Stage 3 MCP tools backed by Stage 2 for the approved question shapes.
- Keep the Stage 2 registry core, but make the engine seam more contributor-ready through additive metadata, standard result envelopes, and engine-side contract documentation.
- Do not solve profile-precondition support or expand statistical tooling in this mission.

## Technical Context

**Language/Version**: Python `>=3.11` (`pyproject.toml`)  
**Primary Dependencies**: DuckDB, MCP Python SDK, Typer, Rich, Pydantic, Polars, Structlog, PyYAML  
**Storage**: Local DuckDB warehouse (`hp.fact_measurement`, `hp.fact_interval`, `hp.dim_metric`, `hp.dim_source`)  
**Testing**: `pytest` with test-first delivery, public-interface assertions, fixture-backed warehouse tests, MCP server tests, `ruff`, and `mypy`  
**Target Platform**: macOS primary; warehouse and encrypted artifacts stay portable to Linux and Windows  
**Project Type**: Local-first Python CLI plus MCP server package  
**Performance Goals**: Non-ingest CLI verbs under 2 s by charter; approved question flows under 5 s for at least 95% of representative local runs by spec  
**Constraints**: Local-first, no background network calls, no PHI in logs/tests/commits, no profile-dependent function support, no Stage 3 statistics expansion, no silent raw-read fallback for the six new flows  
**Scale/Scope**: 6 new Stage 2 answers, 6 new MCP tools, additive seam hardening, no warehouse schema change required for this mission

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Phase 0 gate

| Gate | Result | Notes |
|---|---|---|
| Scientific grounding required for health-facing claims | PASS | The six approved functions come from the research mission's ACCEPT shortlist and retain explicit caveats. |
| Local-first / offline by default | PASS | New Stage 2 answers and Stage 3 tools remain local and deterministic; no new network path is introduced. |
| Test-first delivery | PASS | Plan requires failing tests first for each signal family and for MCP tool exposure. |
| Public-interface testing | PASS | Engine validation stays on public helpers and MCP tool calls, not internal patching. |
| Quality gates (`ruff`, `mypy`, `pytest -q`) | PASS | Included in validation plan and quickstart. |
| Documentation stays synchronized | PASS | Spec and research both require doc alignment in this mission. |
| No risk-boundary breach | PASS | No live API scraping, no hosted dependency, no profile-data back-door, no silent sharing. |

### Post-Phase 1 re-check

No new charter conflict is introduced by the Phase 1 design artifacts in this plan. The design keeps Stage 3 tool additions local-first, keeps profile-data support deferred, and preserves test-first plus documentation-sync requirements.

## Project Structure

### Documentation (this feature)

```
/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── mcp-signal-tools.yaml
├── spec.md
└── tasks/                    # remains empty until /spec-kitty.tasks
```

### Source Code (repository root)

```
/Users/nbrandizzi/repos/personal/premura/src/premura/
├── engine/
│   ├── __init__.py
│   ├── _registry.py
│   ├── lab_ratios.py
│   └── ...new signal modules and shared helpers...
├── mcp/
│   ├── __init__.py
│   ├── server.py
│   └── entrypoint.py
├── parsers/
├── store/
├── ui/
├── cli.py
└── dim_metric.yaml

/Users/nbrandizzi/repos/personal/premura/tests/
├── test_engine.py
├── test_mcp_server.py
├── test_store.py
└── ...existing regression suites...
```

**Structure Decision**: Keep the existing single Python package layout. Add new Stage 2 signal modules and shared engine helpers under `/Users/nbrandizzi/repos/personal/premura/src/premura/engine/`, extend the existing MCP server surface under `/Users/nbrandizzi/repos/personal/premura/src/premura/mcp/`, and add the engine-side contributor contract under `/Users/nbrandizzi/repos/personal/premura/src/premura/engine/`. No new top-level package or service is needed.

## Complexity Tracking

No charter violation requires justification. The plan stays within the repo's existing package layout and stage boundaries.

## Current Baseline

### Stage 2 today

- `/Users/nbrandizzi/repos/personal/premura/src/premura/engine/__init__.py` already exposes `compute`, `list_by_domain`, `list_auto_safe`, `check_inputs_available`, and `list_unavailable`.
- The only built-in Stage 2 functions today are the three lab ratios in `/Users/nbrandizzi/repos/personal/premura/src/premura/engine/lab_ratios.py`.
- `SignalSpec` in `/Users/nbrandizzi/repos/personal/premura/src/premura/engine/_registry.py` carries core registry fields only.
- `check_inputs_available` already respects per-metric `validity_window` from `/Users/nbrandizzi/repos/personal/premura/src/premura/dim_metric.yaml`.

### Stage 3 today

- `/Users/nbrandizzi/repos/personal/premura/src/premura/mcp/server.py` currently exposes only raw warehouse helpers: `query_warehouse`, `list_metrics`, and `metric_summary`.
- `/Users/nbrandizzi/repos/personal/premura/src/premura/mcp/entrypoint.py` publishes those three tools over FastMCP.
- There are no existing Stage 3 tools for the six approved question shapes, so this mission must add them rather than only rewire hidden internals.

### Metric and freshness baseline

- `resting_hr`: `validity_window: P1D`, `missing_data_policy: last_observation_carried_forward`
- `weight`: `validity_window: P1W`, `missing_data_policy: last_observation_carried_forward`
- `steps`: `validity_window: P1D`, `missing_data_policy: none`
- `sleep_rating`: `validity_window: P1D`, `missing_data_policy: none`
- `sleep_deep_pct`: `validity_window: P1D`, `missing_data_policy: none`
- `hrv_rmssd_overnight`: `validity_window: P1D`, `missing_data_policy: none`

These existing ontology rows are enough to support the six approved functions without adding new canonical metrics in this mission.

## Phase 0: Outline & Research

Phase 0 resolves implementation-shape questions that remained after specification but did not require further user interrogation.

### Research goals

1. Decide how Stage 3 should expose the six new grounded answers without breaking the current raw-tool surface.
2. Decide the smallest code-level seam hardening that makes future Stage 2 additions contributor-friendly without taking on the unsolved profile-data problem.
3. Decide the common result shapes the six functions should share so Stage 3 can expose them consistently.
4. Confirm test strategy, fixture shape, and validation order for engine and MCP changes.

### Phase 0 output

- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/research.md`

## Phase 1: Design & Contracts

Phase 1 translates the confirmed scope and Phase 0 decisions into implementation-ready design artifacts.

### Workstreams

1. **Engine result model**
   - Define the logical result shapes for status, trend, own-baseline, and change-around-date answers.
   - Keep them deterministic and friendly to MCP serialization.

2. **Engine seam hardening**
   - Preserve current `SignalSpec` core fields.
   - Add the minimum contributor-facing metadata needed for reviewable future extensions.
   - Add an engine-side contract doc that mirrors the approved grounding and caveat standards.

3. **Stage 2 built-in signals**
   - Implement four descriptive functions first: `resting_hr_status`, `resting_hr_trend`, `steps_trend`, `weight_trend`.
   - Implement the two caveat-heavier functions second: `sleep_deep_pct_baseline`, `hrv_change_around_date`.

4. **Stage 3 MCP contracts**
   - Keep `query_warehouse`, `list_metrics`, and `metric_summary` unchanged.
   - Add six new Stage 3 tools with structured responses mapped directly to the Stage 2 result shapes.
   - Preserve explicit missing-input and freshness signaling.

5. **Docs and contributor alignment**
   - Update the named project docs once implementation lands.
   - Add the engine-side contributor path and the issue `#6` follow-on note.

### Phase 1 outputs

- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/data-model.md`
- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/contracts/mcp-signal-tools.yaml`
- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/quickstart.md`

## Work Package Shaping Notes For /spec-kitty.tasks

The likely work-package split should follow risk and dependence, not file ownership:

1. Engine seam and common result helpers
2. Descriptive signals plus tests
3. Baseline and change-around-date signals plus tests
4. MCP tool exposure and tool-level tests
5. Documentation and contributor-contract alignment

WP generation is intentionally deferred to `/spec-kitty.tasks`.

## Risks And Mitigations

| Risk | Why it matters | Mitigation in this plan |
|---|---|---|
| Signal result shapes drift across the six functions | Stage 3 tools become inconsistent and harder for future agents to extend safely. | Phase 0 fixes common result envelopes before implementation work is broken into WPs. |
| Stage 3 keeps using direct warehouse reads for the new flows | The mission would fail its main boundary-correction goal. | MCP contracts in Phase 1 are explicitly signal-backed; raw tools stay only as parallel utilities. |
| Seam hardening grows into a plugin-system redesign | Scope would balloon and delay the six approved answers. | The plan keeps the existing registry and chooses additive metadata plus contract docs. |
| Profile-data work sneaks in through contributor-readiness changes | The mission would cross the explicit issue `#6` boundary. | The plan limits seam hardening to non-profile-dependent functions and records profile preconditions as deferred. |
| Health claims become stronger than the research approved | Trust and charter compliance would be broken. | Every function keeps explicit freshness, gap, and caveat behavior; Stage 3 adds no significance or diagnostic language. |

## Validation Plan

### Before coding

- Add failing tests for the new engine result families and the new MCP tools.
- Reuse temporary DuckDB fixtures and public engine/MCP interfaces.

### During implementation

- Prefer targeted loops: `tests/test_engine.py` and `tests/test_mcp_server.py` first.
- Add fixture-backed cases for stale data, missing inputs, sparse data, and successful answers.

### Before review handoff

- `uv run ruff check`
- `uv run mypy src/premura`
- `uv run python -m pytest -q`

Pre-existing failures outside scope, if any, must be called out explicitly.

## Planning Stop Point

This planning step ends after the Phase 0 and Phase 1 artifacts are written:

- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/plan.md`
- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/research.md`
- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/data-model.md`
- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/contracts/mcp-signal-tools.yaml`
- `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC/quickstart.md`

No task generation happens in this command.
