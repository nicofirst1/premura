# Implementation Plan: Correlate Lagged Association

**Branch**: `master` | **Date**: 2026-05-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/correlate-lagged-association-01KSWKV0/spec.md`

**Mission**: `correlate-lagged-association-01KSWKV0`
**Mission ID**: `01KSWKV0W5C8DP8WCRMWD0G92Y`
**Branch contract**: current branch at plan start `master`; planning/base branch `master`; final merge target `master`; `branch_matches_target=true`.

## Summary

Add `correlate` as the first multi-input Stage 3 analytical tool. The tool will
compare two admissible daily health series over same-local-calendar-day pairs
after one caller-specified whole-day lag, require a pre-registered hypothesis,
and return an association-only result envelope with Spearman's rho, an
autocorrelation-adjusted association band, raw and effective sample counts,
overlap metadata, and closed-vocabulary confounds. It will refuse before
computation when the hypothesis, lag, evidence, paired overlap, rank variation,
or effective sample size cannot support an honest result.

The work should land as a small vertical sequence: first extend the closed
contract and admissibility vocabulary, then add paired input preparation, then
add the deterministic correlation method/envelope, then expose it through the
default agent-facing surface and update docs/tests.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing Premura engine/MCP stack only; no new runtime statistics, network, or literature dependency planned.  
**Storage**: No new warehouse table. The tool consumes caller-provided prepared analytical series and returns serialized analytical envelopes.  
**Testing**: pytest through public engine/MCP-facing surfaces, with test-first work packages and fixture series for success/refusal paths. Ruff, ruff format, and mypy for changed scope before review handoff.  
**Target Platform**: Local-first Premura runtime on macOS primary platform; outputs remain plain JSON-safe payloads.  
**Project Type**: Single Python package with engine and MCP surfaces.  
**Performance Goals**: Non-ingest agent-facing calls remain comfortably under the charter's 2 second soft target on representative daily-series fixtures.  
**Constraints**: Deterministic, stateless engine; no network; no PubMed runtime calls; no p-values; no significance labels; no causal/diagnostic/treatment claims; no automatic lag or metric-pair scan.  
**Scale/Scope**: Exactly one new analytical tool, one paired-input preparation seam, one reviewed analytical question type, one reviewed confound key, and the docs/tests needed to make the extension reviewable.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pre-Phase 0 Gate**: PASS.

- **Agent-first / human-first**: PASS. `correlate` is an agent-callable analytical tool that helps the operator ask grounded questions about their own data.
- **Design a level above**: PASS. The plan defines a paired-input and hypothesis contract rather than enumerating metric pairs or common causes.
- **Local-first / offline**: PASS. Runtime analysis has no network or literature calls.
- **Health-claim safety**: PASS. Output is association-only, non-diagnostic, non-causal, and excludes p-values/significance.
- **Test-first**: PASS. Work packages must start with failing observable tests for the behavior they add.
- **Public-interface tests**: PASS. Tests should assert through public engine/MCP surfaces and serialized outcomes, not by patching internals.
- **Quality gates**: PASS. Changed scope must satisfy ruff, ruff format, mypy, and pytest before handoff; unrelated pre-existing failures must be named.

**Post-Phase 1 Gate**: PASS.

- The data model keeps the engine stateless and no-PHI; no persisted ledger is introduced.
- Contracts preserve the existing registry/dispatch pattern and avoid per-tool branching.
- Quickstart validation remains local and test-first.
- No charter amendment is required.

## Project Structure

### Documentation (this feature)

```
kitty-specs/correlate-lagged-association-01KSWKV0/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── correlate-contract.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)
```
src/premura/engine/
├── analytical_contract.py      # closed analytical question/confound vocabulary, tool spec, result envelope
├── analytical_inputs.py        # single-series preparation; add paired preparation seam here or adjacent
├── analytical_tools.py         # built-in analytical methods and registration
├── policies/                   # evidence-admissibility question rules and defaults
└── __init__.py                 # public engine exports

src/premura/mcp/
└── server.py                   # default agent-facing wrapper delegates to engine

tests/
├── test_engine_analytical_inputs.py
├── test_engine_analytical_tools.py
├── test_engine_analytical_public_surface.py
├── test_engine_policy_defaults.py
├── test_engine_policy_evaluator.py
└── MCP/server public-surface tests where existing patterns place them

docs/
├── adr/0008-correlate-pre-registered-lagged-association.md
├── history/research/CORRELATE_METHODOLOGY_RESEARCH.md
├── operations/STATUS.md
└── product/ROADMAP.md
```

**Structure Decision**: Keep this as a single-package engine/MCP change. The
engine owns input preparation, method computation, vocabulary validation, and
envelope construction. The MCP wrapper is a thin publication layer. Docs stay in
the existing product/operations/history locations only when behavior changes.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0: Research Decisions

See [research.md](research.md). All implementation-open choices from the
pre-mission research note are resolved for planning:

- Spearman only in v1.
- Same-day pairing after one caller-specified integer lag.
- No lag scan, p-values, significance, or causal wording.
- `N_eff` uses rank-transformed autocorrelation terms through
  `1..min(7, floor(raw_paired_sample_size / 4))`.
- Raw paired sample floor is 20; effective sample floor is 12.
- `low_sample_size` applies below 50 raw pairs or below 30 effective sample size.
- Imputed pairs count half for effective sample support; 20% imputed-pair share
  triggers `high_imputation`.
- `common_cause_plausible` is emitted only when a caller-supplied candidate is
  present in the pre-registered hypothesis.
- Future block bootstrap is not implemented, but the contract reserves a
  deterministic seed and fixed block-length rule.

## Phase 1: Design Artifacts

- [data-model.md](data-model.md): paired input, hypothesis, result, refusal, and
  confound entities.
- [contracts/correlate-contract.md](contracts/correlate-contract.md): engine and
  agent-facing contract for the tool.
- [quickstart.md](quickstart.md): local validation flow and acceptance checks.

## Implementation Sequencing

The next `/spec-kitty.tasks` pass should produce work packages in this order:

1. Contract and policy vocabulary: add lagged-association question type,
   `common_cause_plausible`, registration metadata, admissibility mapping, and
   tests that reject unsupported vocabulary or forbidden language.
2. Paired input preparation: align two usable series by declared lag, narrow
   overlap metadata, compute raw paired counts and imputation share, and refuse
   before computation for invalid pairs.
3. Correlation method and envelope: compute Spearman, effective sample size,
   association band, direction alignment, confounds, caveats, and all refusal
   paths.
4. Default surface integration: expose `correlate` through the existing
   agent-facing path, delegating all behavior to the engine.
5. Docs and review gates: update contracts/status/roadmap as needed and verify
   public-surface, no-network, no-significance, no-causation, ruff, mypy, and
   pytest gates.
