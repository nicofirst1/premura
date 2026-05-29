# Implementation Plan: Stage 2 Evidence Admissibility Foundation

**Branch**: `master` | **Date**: 2026-05-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/spec.md`

## Summary

Build a Stage 2 evidence-admissibility foundation that helps future AI agents add safe, reviewable signal policies without forcing Premura to pre-enumerate every future metric, domain, and health question.

The implementation will use a local, deterministic, declarative frozen-dataclass registry. Policy declarations live in code as frozen dataclass instances backed by closed enums, not YAML files and not a policy mini-language. PubMed MCP and other literature tools may support agent-side policy review during planning, but Stage 2 runtime remains local and warehouse-only.

## Engineering Alignment

- The mission implements a contract-first, declarative evidence-admissibility layer for Stage 2.
- The goal is agent guidance: future agents should author bounded policy declarations instead of freehand logic.
- The mission does not create Stage 3 MCP tools and does not call PubMed at runtime.
- PubMed MCP belongs to agent-side research/review before a policy is encoded, not to the deterministic evaluator.
- Policies are keyed by metric family with per-question-type modifiers, avoiding a full `(family, question_type)` matrix of duplicated declarations.
- Declarations are parameters only: enums, thresholds, windows, required fields, caveats, refusal modes, and examples.
- Declarations must not contain expressions, conditions, operators, or arbitrary executable logic.
- The evaluator owns all branching.
- Validation should be lightweight: construct frozen dataclasses, validate required fields and enum consistency, and fail early on invalid declarations.
- Existing Stage 2 signals should not be broadly refactored. A small proof integration is acceptable only if needed to prove the contract.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing Premura Stage 2 engine modules; no new third-party policy engine  
**Storage**: Existing local DuckDB warehouse remains the source of evidence; no schema migration is planned for this mission  
**Testing**: pytest, test-first; behavior verified through public `premura.engine` interfaces and observable outcomes  
**Target Platform**: Local-first Premura Python toolchain on macOS, with DuckDB artifacts remaining portable  
**Project Type**: Single Python package  
**Performance Goals**: Policy evaluation should be negligible relative to warehouse reads; no network calls in Stage 2 runtime  
**Constraints**: Stage 2 only; local warehouse evidence only; no diagnosis, treatment advice, population norms, or statistical significance claims  
**Scale/Scope**: Initial policy contract plus representative policy declarations covering at least 10 metric families or family groups through a smaller set of reusable evidence-rule shapes

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Check

- **Agent-first / design altitude**: PASS. The plan defines a bounded declaration contract future agents fill in, rather than hardcoding an exhaustive metric/question table.
- **Local-first runtime**: PASS. Stage 2 runtime remains local and offline; PubMed MCP is explicitly outside runtime.
- **No overclaiming health confidence**: PASS. The evaluator produces admissible/rejected/insufficient outcomes and refusal reasons, not diagnosis or treatment advice.
- **Test-first**: PASS. Work packages must add failing tests for invalid declarations, refusal outcomes, and representative admissibility behavior before implementation.
- **Public-interface testing**: PASS. Tests should exercise public `premura.engine` exports or documented contributor-facing surfaces, not private implementation details.
- **Minimal change radius**: PASS. Existing signals are not broadly refactored; at most one proof integration is allowed.

### Post-Design Check

- **Agent-first / design altitude**: PASS. The data model centers on policy declarations and examples as a bounded authoring shape.
- **Local-first runtime**: PASS. Generated contracts specify no runtime network dependency.
- **No clinical authority claim**: PASS. Rationale/caveats document Premura's admissibility defaults, not universal medicine.
- **Quality gates**: PASS. Plan requires pytest, ruff, and mypy for changed scope before handoff.

## Project Structure

### Documentation (this feature)

```text
kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evidence-policy-contract.md
├── checklists/
│   └── requirements.md
└── tasks/
    └── README.md
```

### Source Code (repository root)

```text
src/premura/engine/
├── __init__.py
├── _registry.py
├── _results.py
├── _query.py
├── _resolution.py
└── policies.py              # planned Stage 2 policy declaration/evaluator surface

tests/
├── test_engine_policies.py  # planned public behavior tests for declarations/evaluator
└── test_*.py                # existing Stage 2 signal tests may receive one narrow proof integration if needed
```

**Structure Decision**: Keep the foundation inside `src/premura/engine/` because it is Stage 2 behavior. Add a narrow `policies.py` module rather than a new package unless implementation pressure proves the module too large. Keep documentation and contracts inside `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/` until implementation promotes stable contributor guidance into `src/premura/engine/CONTRACT.md` or a sibling contract file.

## Complexity Tracking

No charter violations identified.

## Phase 0 Research Summary

Phase 0 is complete. The remaining design questions were resolved through in-session research and reviewer feedback:

- Use a contract-first, declarative policy layer, not an exhaustive metric policy table.
- Use frozen dataclass declarations in Python, not YAML, because no human domain reviewer will directly review policy files.
- PubMed MCP supports agent review and authoring outside runtime; Stage 2 does not call PubMed.
- Key policies by family-level declaration with per-question modifiers to avoid duplication.
- Keep declarations parameters-only; no YAML DSL, no expressions, no arbitrary code.

See [research.md](research.md) for decisions and alternatives.

## Phase 1 Design Summary

The design defines a small authoring contract future agents can use:

- Closed enums for question type, admissibility outcome, rejection reason, temporal meaning, and policy shape.
- Frozen dataclasses for policy declarations, per-question behavior, evidence candidates, evidence outcomes, and evaluator results.
- Representative built-in policy declarations that cover at least 10 metric families through shared evidence-rule shapes.
- Negative/refusal fixtures that prove stale, sparse, missing timestamp, wrong question type, and no-admissible-evidence paths.

See [data-model.md](data-model.md), [contracts/evidence-policy-contract.md](contracts/evidence-policy-contract.md), and [quickstart.md](quickstart.md).

## Gate Status

- No unresolved planning clarifications.
- No bulk-edit mode applies.
- No charter conflict identified.
- Ready for `/spec-kitty.tasks` after user review.
