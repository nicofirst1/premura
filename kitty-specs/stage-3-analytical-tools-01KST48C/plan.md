# Implementation Plan: Stage 3 Analytical Tools
*Path: kitty-specs/stage-3-analytical-tools-01KST48C/plan.md*

**Branch**: `master` | **Date**: 2026-05-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/stage-3-analytical-tools-01KST48C/spec.md`

## Summary

Build the first deterministic Stage 3 analytical-tool layer for Premura. The
plan starts with an analytical-depth research note, then lands a narrow contract
and proof surface: `change_point` plus smoothed average. The implementation must
preserve the existing agent-safe boundary: default MCP tools delegate to engine
code, analytical runtime stays local-first, and every non-refusal result carries
uncertainty, validity, imputation, sample-size, and closed-vocabulary confound
metadata.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing Premura runtime stack: DuckDB, pytest, ruff,
mypy, FastMCP-facing wrappers, and current `premura.engine` package surfaces. No
new runtime network or statistics service dependency is planned.  
**Storage**: Existing local DuckDB warehouse remains the evidence source; this
mission adds transient analytical envelopes, not new persisted health tables.  
**Testing**: Test-first with pytest. New behavior is covered through public
engine/MCP surfaces and fixture-backed warehouse inputs. Quality gate: relevant
pytest subset, `pytest -q`, ruff, and mypy for changed scope before review
handoff.  
**Target Platform**: Local-first macOS primary platform, with warehouse/tool
artifacts remaining portable where existing Premura constraints require it.  
**Project Type**: Single Python package plus MCP surface.  
**Performance Goals**: Analytical tool calls over representative local fixture
data should complete within the existing non-ingest interaction target of under
2 seconds.  
**Constraints**: No runtime network calls; no raw fact-table access in default
MCP analytical wrappers; no Stage 2 result-family expansion; no diagnosis,
treatment, dosing, emergency, causation, or population-norm claims.  
**Scale/Scope**: One contract, two proof tools (`change_point`, smoothed
average), default MCP exposure, and tests. Broad statistical coverage and
literature grounding stay out of this mission.

## Engineering Alignment

- Phase 0 research is part of this plan and must complete before code work.
- The research note resolves the conservative change-point method, smoothed
  average shape, analytical `QuestionType` strategy, and confound vocabulary.
  It chooses reviewed analytical question types: `level_shift_detection` and
  `smoothed_pattern`.
- Implementation sequence is research first, analytical contract/data shapes
  second, proof tools third, MCP exposure and validation last.
- This is not a bulk-edit mission. No `occurrence_map.yaml` is required.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter Area | Gate | Status | Notes |
|---|---|---|---|
| Agent-first design altitude | Define bounded abstractions instead of enumerating the whole statistical surface. | Pass | The plan centers on an analytical tool contract and registry, with two proof tools only. |
| Local-first and offline | Runtime must not make network calls. | Pass | PubMed and literature grounding are explicitly out of scope. |
| Scientific humility | Health outputs must not overstate diagnostic confidence. | Pass | Result envelopes require validity/confound metadata and refusals for unsupported data. |
| Testing standards | New health-data behavior needs fixture-backed tests, test-first workflow, and public-surface assertions. | Pass | Plan requires pytest fixtures through public engine/MCP surfaces. |
| Quality gates | ruff, mypy for changed scope, and `pytest -q` before handoff. | Pass | Included in Technical Context and quickstart. |
| Branch strategy | Planning happens on `master`; implementation later uses Spec Kitty worktrees. | Pass | setup-plan returned `branch_matches_target=true`. |
| PHI hygiene | No real private health artifacts in tests, logs, docs, or commits. | Pass | Plan uses synthetic/fixture data only. |

## Project Structure

### Documentation (this feature)

```
kitty-specs/stage-3-analytical-tools-01KST48C/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── analytical-tool-contract.md
│   └── mcp-analytical-tools.md
├── checklists/
│   └── requirements.md
└── tasks/
    └── README.md
```

### Source Code (repository root)

```
src/premura/engine/
├── __init__.py
├── _registry.py
├── _results.py
├── _query.py
├── policies/
│   ├── _model.py
│   ├── _evaluator.py
│   ├── _defaults.py
│   └── _registry.py
└── analytical.py                  # planned analytical contract/proof tools module

src/premura/mcp/
├── server.py                      # planned serialized analytical wrappers
└── entrypoint.py                  # planned default-surface tool registration

tests/
├── test_engine_analytical_contract.py
├── test_engine_analytical_tools.py
└── test_mcp_analytical_tools.py
```

**Structure Decision**: Keep the analytical runtime inside `src/premura/engine/`
because Stage 3 MCP wrappers must delegate to engine-owned preparation and
evaluation. Use `src/premura/mcp/server.py` and `src/premura/mcp/entrypoint.py`
only for serialization and explicit default-surface registration. Tests assert
through public engine and MCP surfaces rather than internal implementation paths.

## Complexity Tracking

No charter violations are introduced. The additional analytical engine module is
justified by the need to keep Stage 3 wrappers thin while avoiding expansion of
Stage 2 result families.

## Phase 0: Research

Output: [research.md](research.md)

Research resolves the decisions the spec intentionally left to the planning
phase:

- conservative `change_point` method
- smoothed-average method shape
- analytical evidence-policy `QuestionType` strategy: add reviewed values
  `level_shift_detection` and `smoothed_pattern`
- closed confound vocabulary
- runtime dependency posture

## Phase 1: Design & Contracts

Outputs:

- [data-model.md](data-model.md)
- [contracts/analytical-tool-contract.md](contracts/analytical-tool-contract.md)
- [contracts/mcp-analytical-tools.md](contracts/mcp-analytical-tools.md)
- [quickstart.md](quickstart.md)

Design decisions:

- Model analytical outcomes separately from Stage 2 signal result families.
- Use a closed vocabulary for analytical validity status, refusal reasons, and
  confound keys.
- Extend the closed evidence-policy question vocabulary with reviewed analytical
  values instead of mapping analytical tools onto descriptive question types.
- Treat the smoothed average proof tool as a conservative pattern summary, not a
  significance or prediction tool.
- Preserve explicit MCP wrapper registration.

## Post-Design Charter Check

| Charter Area | Status | Notes |
|---|---|---|
| Agent-first design altitude | Pass | Contracts define how future tools register rather than listing all tools. |
| Local-first and offline | Pass | Contracts explicitly prohibit runtime network access. |
| Scientific humility | Pass | Contracts require refusals and caveats instead of overconfident estimates. |
| Testing standards | Pass | Quickstart and contracts require public-surface, fixture-backed tests. |
| Quality gates | Pass | Verification commands are listed in quickstart. |

## Planned Work Package Shape

This plan stops before task generation. The likely later work-package sequence is:

- WP01: write the Stage 3 analytical-depth research note.
- WP02: add analytical contract/data shapes and public engine surface.
- WP03: implement `change_point` and smoothed average behind the contract.
- WP04: expose proof tools through MCP wrappers and complete validation gates.

`/spec-kitty.tasks` owns the final work-package breakdown.
