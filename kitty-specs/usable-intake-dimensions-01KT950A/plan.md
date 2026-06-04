# Implementation Plan: Usable Intake Dimensions

**Branch**: `master` (base + merge target) | **Date**: 2026-06-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/usable-intake-dimensions-01KT950A/spec.md`

**Branch contract**: Current branch at plan start `master`; planning/base branch
`master`; final merge target `master`; `branch_matches_target = true`.

## Summary

Turn `nutrition_intake` and `supplement_intake` from declarable-but-unresolved
domains into **usable Stage 2 inputs and Stage 3 tools** without inventing a new
intake abstraction layer. The mission has five coupled deliverables:

1. extend the parser contract/protocol so runtime parsers can emit intake as a
   first-class supported output rather than only observation `IngestBatch`;
2. ship concrete Stage 2 intake resolvers for both domains through the existing
   `@resolver(domain=...)` seam, preserving explicit no-fallback behavior;
3. ship one descriptive, bounded-window, intake-backed signal per domain and
   expose both on the default MCP surface;
4. anchor the path with a minimal synthetic reference intake parser + fixture
   proving `parse -> IntakeBatch -> persist_intake_batch` end-to-end; and
5. write down the generalized rule for adding the next intake dimension, plus a
   recommendation on whether and when a dedicated intake-dimension contract
   becomes worthwhile.

The design stays grounded in shipped seams rather than introducing a new one:
`src/premura/parsers/base.py` already defines `IntakeBatch` and the normalized
intake inputs; `src/premura/store/profile_intake.py` persists them; the Stage 2
input-resolution seam in `src/premura/engine/_resolution.py` already declares
both intake domains; and Stage 3 already exposes signal-backed tools through
`src/premura/mcp/server.py` and `src/premura/mcp/entrypoint.py`. The main
architectural gap to close is that the parser **contract prose** now describes
two seams while the **actual parser protocol and invocation path** still assume
`parse(path) -> IngestBatch` only.

## Technical Context

**Language/Version**: Python 3.11+.
**Primary Dependencies**: Existing Premura stack only: DuckDB, pytest, ruff,
mypy, typer/rich MCP surface, existing engine/parser/store modules. No new
runtime dependency is needed.
**Storage**: Existing local DuckDB warehouse tables for intake under
`hp.nutrition_intake_*`, `hp.nutrition_quantity`, `hp.supplement_intake_*`, and
`hp.supplement_dose`; no new external storage.
**Testing**: pytest, test-first, public-interface focused. Anchor against parser
contract tests, intake persistence tests, resolver surface tests, and MCP signal
tool tests.
**Target Platform**: Local-first Premura toolchain on macOS; platform-portable
warehouse behavior retained.
**Project Type**: Single Python project; Stage 2 + Stage 3 extension plus parser
contract/runtime path work.
**Performance Goals**: New signal-backed tools remain aligned with the charter's
soft local command budget; no network calls introduced; resolver/signal work
stays query-bounded over one user-selected window.
**Constraints**: descriptive only; no diagnosis/causation/significance; no
silent cross-domain fallback; no intake-as-observation coercion; synthetic
fixtures only; local calendar day basis must be explicit and fixture-locked when
`local_tz` is present.
**Scale/Scope**: One parser protocol adjustment, two resolvers, two descriptive
signals, two MCP tool wrappers, one synthetic reference parser/fixture, and the
companion docs/contracts/recommendation artifacts.

## Planning Answers

- The mission **does** extend the parser contract/protocol in this slice so
  runtime intake parsers are a first-class supported path, not just skill prose.
- Both intake-backed signals accept a caller-supplied **bounded window**, with
  sane repo defaults.
- Both signals stay **generic**: caller-declared keys/matchers within their
  domain, not a tiny hardcoded nutrient/supplement list.
- The mission remains descriptive and level-above: no intake-specific fixed list
  becomes product policy.

## Charter Check

*GATE: must pass before Phase 0. Re-check after Phase 1 design.*

| Gate (charter) | Status | How this plan satisfies it |
| --- | --- | --- |
| **Test-first, no horizontal slicing** (DIRECTIVE_034) | PASS | Each slice starts from failing public-interface tests: parser protocol/contract, intake resolver behavior, intake signals, and MCP tool exposure. |
| **Black-box via public interfaces** (DIRECTIVE_036) | PASS | Tests assert parser outputs, persisted warehouse rows, `resolve_dependency(...)` outcomes, signal envelopes, and MCP tool payloads; they do not drive business logic by patching inside-boundary internals. |
| **Quality gates: ruff + mypy + pytest green** | PASS | Quickstart enumerates the expected commands; public protocol changes and new Stage 2/3 surfaces remain typed. |
| **Modularity / smallest diff** (DIRECTIVE_024) | PASS | The plan extends shipped seams (`parsers/base.py`, `engine/views/`, `descriptive_signals.py`, `mcp/server.py`) rather than adding a new intake framework. |
| **PHI hygiene; no PHI in logs/tests/commits** | PASS | Reference parser and fixtures are synthetic only; no real nutrition/supplement export enters the repo. |
| **Local-first / offline by default** | PASS | No new network access; new runtime behavior is local parser execution, warehouse persistence, and local MCP answers only. |
| **Design altitude — guide, don't enumerate** | PASS | The deliverable is the rule for adding intake dimensions and generic domain inputs, not a closed nutrient/supplement allowlist. |
| **Fidelity gates** | PASS (planned) | The plan assigns measurable NFR/SC ownership, requires positive-path fixtures for "when available" clauses, and locks temporal basis with a local-midnight divergence fixture. |

No charter amendment is required.

## Project Structure

### Documentation (this feature)

```text
kitty-specs/usable-intake-dimensions-01KT950A/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── intake-parser-runtime-contract.md
│   ├── intake-resolution-and-signals-contract.md
│   └── intake-tool-surface-contract.md
└── tasks.md              # Created later by /spec-kitty.tasks, not by this command
```

### Source Code (repository root)

```text
src/premura/
├── parsers/
│   ├── base.py                    # parser protocol + intake-aware parse/output shape
│   ├── CONTRACT.md                # authoritative parser contract
│   └── ... existing parsers
├── store/
│   ├── loader.py                  # observation path remains separate
│   └── profile_intake.py          # persist_intake_batch already exists
├── engine/
│   ├── __init__.py
│   ├── _resolution.py             # semantic-domain seam; domains already declared
│   ├── _registry.py               # resolver + signal registries
│   ├── descriptive_signals.py     # existing descriptive signal family patterns
│   └── views/
│       ├── __init__.py
│       ├── observation.py
│       ├── profile.py
│       ├── nutrition_intake.py    # NEW
│       └── supplement_intake.py   # NEW
├── mcp/
│   ├── server.py                  # tool-facing wrappers around signals
│   └── entrypoint.py              # default MCP tool registration
└── cli.py                         # parser invocation path; affected by parser protocol change

tests/
├── test_profile_intake_parser_contract.py
├── test_profile_intake_persistence.py
├── test_engine_input_resolution_surface.py
├── test_engine_resolvers.py
├── test_mcp_signal_tools.py
├── test_mcp_server.py
├── test_bmi_signal.py             # proof-consumer pattern for cross-domain signals
├── test_intake_resolvers.py       # NEW
├── test_intake_signals.py         # NEW
├── test_mcp_intake_tools.py       # NEW
└── fixtures/intake/               # NEW synthetic intake source fixtures + reference parser
```

**Structure Decision**: Keep every change on the existing Stage 2/Stage 3 seams.
Resolvers live as new modules under `src/premura/engine/views/`, signal logic
lives with the other descriptive signals, and MCP exposure follows the existing
signal-wrapper pattern. The parser path is corrected at the source contract and
protocol level instead of layering a second intake-only parser mechanism beside
the existing one.

## Phase 0: Research Plan

Research resolves the main architecture forks before implementation tasks are
generated:

1. What is the smallest viable parser output/runtime-path change that replaces
   today's observation-only `parse(path) -> IngestBatch` assumption while
   preserving the one-home split between observations and intake?
2. Which current invocation points (`cli.py`, harness, parser-facing docs) must
   be updated so runtime intake parser authoring is genuinely supported, not just
   typed in one protocol file?
3. What is the minimal generic key/matcher contract for the two new signals so
   they stay level-above and do not hardcode a nutrient/supplement list?
4. Which warehouse rows and payload shapes should each intake resolver surface so
   Stage 2 signals can stay declarative and avoid direct raw-table coupling?
5. How should day/window/freshness semantics be defined so computation and
   reported metadata both use the same local-day basis when `local_tz` is
   present?

Research output is recorded in [research.md](research.md).

## Phase 1: Design Outputs

- [data-model.md](data-model.md): parser-result, resolver payloads, signal
  inputs/results, and reference parser/fixture entities.
- [contracts/intake-parser-runtime-contract.md](contracts/intake-parser-runtime-contract.md): parser protocol and runtime intake load path.
- [contracts/intake-resolution-and-signals-contract.md](contracts/intake-resolution-and-signals-contract.md): resolver payloads, signal inputs, refusal states, temporal basis.
- [contracts/intake-tool-surface-contract.md](contracts/intake-tool-surface-contract.md): default MCP tool exposure and payload contract.
- [quickstart.md](quickstart.md): reviewer-facing validation path and example
  end-to-end flows.

## NFR / Success-Criteria Ownership (fidelity gate)

Every measurable requirement must be owned by a WP with a committed evidence
artifact. Provisional map for `/spec-kitty.tasks`:

| Requirement | Evidence artifact | Likely WP |
| --- | --- | --- |
| NFR-001 descriptive-only, non-diagnostic | signal/tool tests asserting no diagnosis/causation/significance language or fields | intake-signal WP |
| NFR-002 local-first / no export/network | changed-scope static check + no-network path in tests | parser/runtime + MCP WP |
| NFR-003 no silent fallback | resolver/signal regression where same-named observation rows do not satisfy intake dependencies | intake-resolver WP |
| NFR-004 deterministic offline coverage | full deterministic pytest scope for parser, resolver, signal, MCP surfaces | all code WPs |
| NFR-005 structural generalization | test asserting shared resolver seam has no intake-domain branch in common path | intake-resolver WP |
| NFR-006 temporal basis explicit + locked | local-midnight divergence fixture asserting compute and report basis match | intake-signal WP |
| SC-001 supplement adherence answer | signal + MCP positive-path test | supplement-signal WP |
| SC-002 nutrition trend answer | signal + MCP positive-path test | nutrition-signal WP |
| SC-003 no-intake honest refusal | missing/stale/empty-domain tests across both signals | intake-signal WP |
| SC-004 runtime intake parser build-and-use rule is implementable | parser contract/runtime-path + invocation + skill/contract tests | parser-contract/runtime WP |
| SC-005 add-next-dimension rule holds without shared seam change | doc + structural tests over two shipped domains | documentation/generalization WP |
| SC-006 recommendation note present with trigger condition | recommendation artifact in docs/spec outputs | documentation/generalization WP |

## Phasing Sketch (WP breakdown happens at /spec-kitty.tasks)

1. **Parser runtime surface**: extend parser protocol/contract and runtime
   invocation points so intake output is a first-class supported path.
2. **Reference intake parser + fixture**: synthetic nutrition/supplement source,
   parser proof, and parse->persist end-to-end tests.
3. **Intake resolvers**: `nutrition_intake` and `supplement_intake` concrete
   resolver modules through the existing registry seam.
4. **Intake signals**: one descriptive signal per domain, bounded caller window,
   positive-path + refusal-path + temporal-basis fixtures.
5. **MCP exposure**: default tool wrappers + registration + payload tests.
6. **Generalization docs and recommendation**: parser-generator skill update,
   add-a-dimension rule, and dedicated-contract recommendation note.

## Risks (must resolve to a task / non-goal / acceptance check before WP approval)

- **R1 — Parser protocol drift across runtime entrypoints.** Updating only
  `parsers/base.py` would leave CLI/harness/docs observation-only. Mitigation:
  one WP owns the whole runtime parser path and its tests.
- **R2 — Missingness-only tests mask unimplemented positive path.** This is the
  D5 drift shape. Mitigation: each signal/tool ships a distinct positive-path
  fixture for data-present behavior, separate from missing/stale tests.
- **R3 — UTC-date reporting diverges from local-day compute basis.** This is the
  D4 drift shape. Mitigation: at least one fixture crosses local midnight and
  asserts reported day/window metadata uses the same local-day basis as the
  computation.
- **R4 — Generic keying silently collapses into a hardcoded list.** Mitigation:
  contracts and tests assert caller-declared keys/matchers rather than seeded
  nutrient/supplement enums.
- **R5 — Resolver payloads become overfit to one signal.** Mitigation: keep
  resolver payloads domain-level and generic enough for the next intake consumer,
  with signal-specific interpretation living in `descriptive_signals.py`.

## Post-Design Charter Re-check

Re-evaluated after Phase 1 design: still PASS. The design keeps intake on its
own home, extends existing seams rather than adding a new abstraction layer,
uses positive-path and divergence fixtures to satisfy the charter's fidelity
gates, and leaves every measurable NFR/SC with a concrete evidence path for
task decomposition.

## Complexity Tracking

No charter violations or complexity exceptions are currently justified.
