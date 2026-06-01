# Implementation Plan: Finish Analytical Tool Set

**Branch**: `master` | **Date**: 2026-06-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`

**Mission**: `finish-analytical-tool-set-01KT0Y95`
**Mission ID**: `01KT0Y95X8XKZCQH3G1Y8QVPDJ`
**Branch contract**: current branch at plan start `master`; planning/base branch `master`; final merge target `master`; `branch_matches_target=true`.

## Summary

Complete Premura's first bounded analytical tool set by adding `rolling_mean` and
`paired_t_test` to the existing engine-owned analytical registry, default MCP
surface, and session research trace accounting. `rolling_mean` is a declared
moving-window summary over one admitted ordered series. `paired_t_test` is scoped
to the simple version confirmed during planning: a before/after paired comparison
around one caller-declared anchor date. Broader caller-supplied condition labels
or arbitrary pair maps are deferred.

The work should land as a vertical sequence: first settle the analytical question
types and admissibility mapping, then implement `rolling_mean`, then implement
the simple paired-input shape and `paired_t_test`, then expose both through the
default agent surface and session trace identity registry, then update docs and
validation.

## Engineering Alignment

- `rolling_mean` is a distinct roadmap tool from the shipped
  `smoothed_average`; it returns a moving-window series with explicit coverage,
  not a replacement or rename.
- `paired_t_test` supports only before/after pairing around a declared anchor
  date in this mission.
- Condition-label, event-label, or user-supplied arbitrary pair matching is out
  of scope and should be named as future extension capacity only.
- Both tools are deterministic, local-first, non-diagnostic, and non-causal.
- MCP wrappers stay thin and delegate to `premura.engine` for preparation,
  computation, caveats, and refusals.
- Session research trace support is additive: traced and untraced engine
  envelopes remain byte-equivalent except for wrapper-level trace metadata.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing Premura engine/MCP stack only; no new runtime statistics, network, PubMed, or literature dependency planned.  
**Storage**: No new warehouse health-data tables. Existing `trace.*` tables record analytical-call provenance for the new tools.  
**Testing**: pytest through public engine, MCP, and trace surfaces. Test-first work packages are required; changed scope must pass ruff, ruff format, mypy, and pytest before review handoff.  
**Target Platform**: Local-first Premura runtime on macOS primary platform; outputs remain JSON-safe analytical payloads.  
**Project Type**: Single Python package with engine and MCP surfaces.  
**Performance Goals**: Non-ingest agent-facing calls remain under the charter's 2 second soft target on representative synthetic daily-series fixtures; analytical tool listing remains under 1 second.  
**Constraints**: Deterministic stateless engine; no network; no PubMed runtime calls; no hidden search over windows/dates/conditions; no causal, diagnostic, treatment, dosing, emergency, or population-norm claims.  
**Scale/Scope**: Two new analytical tools, two reviewed analytical question-type additions if needed, simple before/after paired-input preparation, trace identity declarations, default MCP exposure, tests, and docs.

## Planning Questions Answered

| Question | Decision |
|---|---|
| Should both deferred tools be included? | Yes. The mission includes both `rolling_mean` and `paired_t_test`. |
| How broad should `paired_t_test` be? | Simple before/after pairing around one declared anchor date only. |
| Should condition-label or arbitrary-pair pairing be supported now? | No. Defer as a future extension after the simple paired comparison is proven. |

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Phase 0 Gate**: PASS.

- **Agent-first / human-first**: PASS. The tools are default-surface analytical capabilities an operating agent calls to help the human understand their own data.
- **Design a level above**: PASS. The plan defines declared windows and declared anchor-date pairing rules rather than enumerating metrics, dates, or conditions.
- **Local-first / offline**: PASS. Runtime analysis uses local warehouse-derived evidence and existing engine inputs only.
- **Health-claim safety**: PASS. Outputs are descriptive/comparative only; no diagnosis, treatment, causation, or population ranking is allowed.
- **Test-first**: PASS. Work packages must start from failing public-behavior tests and use short red/green/refactor loops.
- **Public-interface tests**: PASS. Tests should assert through engine facade, MCP wrappers, and trace public surfaces rather than patching internal collaborators.
- **Quality gates**: PASS. Changed scope must satisfy ruff, ruff format, mypy, and pytest before handoff; unrelated pre-existing failures must be named.

**Post-Phase 1 Gate**: PASS.

- The design keeps the analytical engine stateless and offline.
- The data model extends the existing analytical envelope and trace identity seam rather than inventing a separate result channel.
- The contract forbids hidden alternative scanning and keeps broader condition pairing deferred.
- No charter amendment or complexity exemption is required.

## Project Structure

### Documentation (this feature)

```text
kitty-specs/finish-analytical-tool-set-01KT0Y95/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── rolling-mean-contract.md
│   └── paired-t-test-contract.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
src/premura/engine/
├── analytical_contract.py      # closed analytical question/confound vocabulary and tool spec
├── analytical_inputs.py        # single-series preparation and before/after paired preparation
├── analytical_tools.py         # built-in analytical methods and registration
├── analytical.py               # built-in analytical tool loading and dispatch facade
├── policies/                   # evidence-admissibility question rules and defaults
└── __init__.py                 # public engine exports

src/premura/
├── mcp/server.py               # default agent-facing wrappers delegate to engine
└── trace.py                    # hypothesis identity declarations for trace counting

tests/
├── test_engine_analytical_inputs.py
├── test_engine_analytical_tools.py
├── test_engine_analytical_public_surface.py
├── test_mcp_analytical_tools.py
├── test_mcp_trace_recording.py
├── test_trace_store.py
├── test_engine_policy_defaults.py
└── test_engine_policy_evaluator.py

docs/
├── operations/STATUS.md
├── architecture/STAGES.md
├── product/ROADMAP.md
└── product/FULL_APP_DEVELOPMENT_PLAN.md
```

**Structure Decision**: Keep this as a single-package engine/MCP/trace change.
The engine owns analytical preparation, computation, vocabulary validation, and
envelope construction. MCP wrappers are publication/serialization layers only.
The trace service receives identity declarations for the two new tools without
moving analytical state into the engine.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0: Research Decisions

See [research.md](research.md). Planning resolves the remaining design choices:

- Keep `rolling_mean` separate from `smoothed_average` by using it as the
  reviewable moving-window series output with per-point coverage metadata.
- Use conservative fixed defaults for `rolling_mean`: a 7-observation default
  window, a 365-observation maximum, and a 0.5 minimum coverage default unless
  plan-time implementation research finds an existing project constant that must
  be reused.
- Scope `paired_t_test` to anchor-date before/after pairs only.
- Require an explicit anchor date, before window, after window, and expected
  direction for `paired_t_test`; no condition-label pairing in this mission.
- Use a conservative paired-sample floor and report paired-difference uncertainty;
  p-value/significance wording remains forbidden unless a later explicit review
  changes the analytical honesty policy.
- Add trace normalized identities for `rolling_mean` and anchor-date
  `paired_t_test` so exact retries collapse and different windows/anchors remain
  distinct hypotheses.

## Phase 1: Design Artifacts

- [data-model.md](data-model.md): rolling-window result, before/after paired
  input, paired estimate, refusal, confound, and trace identity entities.
- [contracts/rolling-mean-contract.md](contracts/rolling-mean-contract.md):
  engine and agent-facing contract for `rolling_mean`.
- [contracts/paired-t-test-contract.md](contracts/paired-t-test-contract.md):
  engine and agent-facing contract for simple anchor-date `paired_t_test`.
- [quickstart.md](quickstart.md): local validation flow and acceptance checks.

## Implementation Sequencing Guidance

The next `/spec-kitty.tasks` pass should produce work packages in this order:

1. Contract and policy vocabulary: add reviewed analytical question types,
   admissibility-policy mapping, built-in catalog expectations, and tests that
   reject unsupported vocabulary or forbidden language.
2. `rolling_mean`: add failing tests for available/refused envelopes, then the
   deterministic moving-window method, confounds, and public discovery.
3. Simple paired preparation: add anchor-date before/after paired input shape,
   validation, refusal behavior, and public tests.
4. `paired_t_test`: add deterministic paired-difference estimate, uncertainty,
   caveats/confounds, refusal behavior, and no-causation/no-significance tests.
5. Default surface and trace integration: add thin wrappers, optional session
   recording, hypothesis identities, and disclosure tests for both tools.
6. Docs and validation: sync live docs/contracts and run ruff, format check,
   mypy for changed scope, and focused pytest before review handoff.
