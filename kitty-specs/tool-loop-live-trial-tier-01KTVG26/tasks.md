# Tasks: Tool-loop live-trial tier

**Mission**: `tool-loop-live-trial-tier-01KTVG26`
**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/tool-loop-tier.md](contracts/tool-loop-tier.md)
**Branch contract**: planning base `master`; merge target `master`.

> **Plan refinement recorded here (DIRECTIVE_010)**: plan.md sketched one new
> module; tasks split it into two — `src/premura/harness/tool_loop_contract.py`
> (chat client, tool registry, brief assembly: pure, deterministic, heavily
> unit-tested) and `src/premura/harness/live_trial_tool_loop.py` (operator,
> loop, outcomes, entry point: orchestration). Rationale: modularity quality
> gate + disjoint WP ownership. plan.md §Project Structure is amended in the
> same commit.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing tests: `tier` round-trip + legacy-line parse on scoreboard records | WP01 | [P] | [D] |
| T002 | Add `tier` field to `LiveTrialRunRecord` + `ScoreboardEntry` (default `"one_shot"`) | WP01 | | [D] |
| T003 | Group `current_floor` by `(operator_model, tier)`; tier column in CLI table | WP01 | | [D] |
| T004 | Back-compat verification: one-shot writer emits `tier="one_shot"`; legacy rows render | WP01 | | [D] |
| T005 | Failing fixture test: renamed-field-absorbing parser FAILS `self_reconcile` (SC-007) | WP02 | [P] |
| T006 | Sharpen renamed-field declared-gap line in the observation contract prompt | WP02 | |
| T007 | Sharpen the same line in the intake contract prompt; one-shot suites stay green | WP02 | |
| T008 | Failing tests: chat-client error mapping, tool-registry bounds, brief invariants | WP03 | [D] |
| T009 | Chat client `_ollama_chat` (stdlib, local-only guard, `num_ctx`) + `ToolCallsUnsupportedError` | WP03 | | [D] |
| T010 | `ToolRegistration` + registry + `read_context`/`write_parser`/`run_ingest` handlers | WP03 | | [D] |
| T011 | Brief assembler (single function; budget check fails loudly, never truncates) | WP03 | | [D] |
| T012 | Failing loop tests via injectable fake chat backend (happy path, gate feedback, cap) | WP04 | |
| T013 | `ToolLoopOperator`: agent loop, turn accounting, registry dispatch, gate integration | WP04 | |
| T014 | `run_live_trial_tool_loop`: first/final grading, `ToolLoopOutcome`, tier persistence | WP04 | |
| T015 | CLI `_main` (exit codes 0/2/3), `__all__`, module docstring boundaries | WP04 | |
| T016 | E2E edge fixtures: regression-across-turns, malformed call, manifest refusal, no-parser | WP05 | |
| T017 | E2E outcome edges: `model_unavailable`, `tool_calls_unsupported`, real-source no-persist | WP05 | |
| T018 | Gated `live_trial`-marked real-model test module | WP05 | |
| T019 | CHANGELOG entry for the tool-loop tier | WP06 | [P] |
| T020 | STATUS.md update (honest pre-merge tense) | WP06 | |
| T021 | ROADMAP reconciliation: tier work no longer "parked behind the gate" | WP06 | |

## Phase 1 — Foundational (parallel-safe)

### WP01 — Scoreboard tier axis

**Prompt**: [tasks/WP01-scoreboard-tier-axis.md](tasks/WP01-scoreboard-tier-axis.md)
**Goal**: back-compatible `tier` field on the run record and scoreboard line;
floor grouped by `(operator_model, tier)`. FR-007 data layer; SC-002.
**Priority**: P1 (unblocks WP04 persistence) · **Estimated prompt**: ~320 lines
**Independent test**: tier round-trips through JSONL; a pre-existing line
without `tier` parses as `one_shot`; floor table shows both tiers side by side.
**Dependencies**: none.

- [x] T001 Failing tests: tier round-trip + legacy-line parse (WP01)
- [x] T002 Add `tier` to `LiveTrialRunRecord` + `ScoreboardEntry` (WP01)
- [x] T003 `current_floor` groups by `(operator_model, tier)`; CLI tier column (WP01)
- [x] T004 Back-compat verification: one-shot writes `tier="one_shot"` untouched (WP01)

### WP02 — Renamed-field declared-gap rule (FR-009)

**Prompt**: [tasks/WP02-renamed-field-gap-rule.md](tasks/WP02-renamed-field-gap-rule.md)
**Goal**: prove the gate fails a consumed-but-undeclared renamed column
(SC-007, test-first) and state the rule explicitly in both drawer contract
prompts. Wording-only on the one-shot path (C-002).
**Priority**: P1 · **Estimated prompt**: ~280 lines
**Independent test**: the committed renamed-field fixture parser FAILS
`self_reconcile` with the consumed column listed unaccounted; all existing
one-shot suites green.
**Dependencies**: none.

- [ ] T005 Failing renamed-field gate fixture test (WP02)
- [ ] T006 Sharpen observation contract prompt line (WP02)
- [ ] T007 Sharpen intake contract prompt line; suites stay green (WP02)

### WP03 — Tool contract module (chat client, registry, brief)

**Prompt**: [tasks/WP03-tool-contract-module.md](tasks/WP03-tool-contract-module.md)
**Goal**: new `src/premura/harness/tool_loop_contract.py` — the deterministic
contract surface: chat client with local-only guard + `tool_calls_unsupported`
mapping, the bounded tool registry (manifest physically unreachable), and the
single-source brief assembler with explicit budget accounting.
FR-001/002/003/004, NFR-001/005; SC-006.
**Priority**: P1 (unblocks WP04) · **Estimated prompt**: ~460 lines
**Independent test**: registry refuses any non-allowlisted path; brief contains
every required API class name and no one-shot-only output directive; oversized
brief raises instead of truncating — all without a model server.
**Dependencies**: none.

- [x] T008 Failing tests: client error mapping, registry bounds, brief invariants (WP03)
- [x] T009 Chat client + `ToolCallsUnsupportedError` + `num_ctx` pinning (WP03)
- [x] T010 `ToolRegistration` + registry + three bounded handlers (WP03)
- [x] T011 Brief assembler with loud budget check (WP03)

## Phase 2 — The loop

### WP04 — ToolLoopOperator and tier entry point

**Prompt**: [tasks/WP04-tool-loop-operator.md](tasks/WP04-tool-loop-operator.md)
**Goal**: new `src/premura/harness/live_trial_tool_loop.py` — the agent loop
(`ToolLoopOperator` implementing the existing `Operator` protocol),
`run_live_trial_tool_loop` with first/final verdicts, `ToolLoopOutcome`,
tier-tagged persistence, CLI. FR-005/006/007/008, NFR-002/004/006; SC-001/005.
**Priority**: P1 (the mission's core) · **Estimated prompt**: ~480 lines
**Independent test**: with a scripted fake chat backend, a full trial runs
end-to-end over the synthetic fixture: tools dispatched, gate feedback loops,
cap respected, two verdicts recorded, scoreboard line `tier="tool_loop"`.
**Dependencies**: WP01, WP03.

- [ ] T012 Failing loop tests via injectable fake chat backend (WP04)
- [ ] T013 `ToolLoopOperator` loop + turn accounting + gate integration (WP04)
- [ ] T014 `run_live_trial_tool_loop` + `ToolLoopOutcome` + tier persistence (WP04)
- [ ] T015 CLI `_main` exit codes + module surface (WP04)

## Phase 3 — Whole-story acceptance

### WP05 — Spec edge-case fixtures and gated real-model test

**Prompt**: [tasks/WP05-edge-fixtures-and-gated-test.md](tasks/WP05-edge-fixtures-and-gated-test.md)
**Goal**: one end-to-end fixture per spec-enumerated edge case (charter drift
dimension D7) through the public entry point, plus the `live_trial`-gated
real-model test. NFR-003/006; SC-003/004/005.
**Priority**: P2 · **Estimated prompt**: ~420 lines
**Independent test**: every spec edge case drives `run_live_trial_tool_loop`
end-to-end in the default suite (no model server); the real-model module is
skipped by default and runnable locally.
**Dependencies**: WP04.

- [ ] T016 E2E edge fixtures: regression, malformed call, manifest refusal, no-parser (WP05)
- [ ] T017 E2E outcome edges: unavailable, unsupported, real-source no-persist (WP05)
- [ ] T018 Gated `live_trial` real-model test module (WP05)

### WP06 — Live-doc sync (pre-merge tense)

**Prompt**: [tasks/WP06-live-doc-sync.md](tasks/WP06-live-doc-sync.md)
**Goal**: CHANGELOG entry, STATUS.md and ROADMAP.md reconciliation in honest
pre-merge tense ("on the lane / not yet merged" — charter D6: this WP cannot
describe its own merge; the orchestrator's post-merge close-out flips tense).
**Priority**: P2 · **Estimated prompt**: ~240 lines
**Independent test**: the three live docs name the tool-loop tier with correct
pre-merge status and no stale "parked behind the intake gate" language.
**Dependencies**: WP04 (describes what exists).

- [ ] T019 CHANGELOG entry (WP06)
- [ ] T020 STATUS.md update, pre-merge tense (WP06)
- [ ] T021 ROADMAP reconciliation (WP06)

## Parallelization

- **Wave 1 (3 lanes in parallel)**: WP01, WP02, WP03 — fully disjoint files.
- **Wave 2**: WP04 (needs WP01 + WP03 merged into its base).
- **Wave 3 (2 lanes)**: WP05 and WP06 (both depend only on WP04).

## Dependency summary

| WP | Depends on |
|----|-----------|
| WP01 | — |
| WP02 | — |
| WP03 | — |
| WP04 | WP01, WP03 |
| WP05 | WP04 |
| WP06 | WP04 |

## Measurable NFR / SC ownership (charter fidelity gate)

| Ref | Owner WP | Evidence artifact |
|-----|----------|-------------------|
| NFR-001 | WP03 | local-only URL tests in `tests/test_tool_loop_contract.py` |
| NFR-002 | WP04 (+WP05 e2e) | real-source no-persist tests |
| NFR-003 | WP05 | gated module + default-suite collection assertion |
| NFR-004 | WP04 | import-reuse (no copied layers); one-shot suites untouched |
| NFR-005 | WP03 | registry-rule tests (new tool = registration) |
| NFR-006 | WP04 (+WP05 e2e) | outcome-invariant tests |
| SC-001 | WP04 | e2e fake-backend trial test |
| SC-002 | WP01 | two-tier floor rendering test |
| SC-003 | WP05 | real-source zero-artifact test |
| SC-004 | WP05 | default-collection assertion |
| SC-005 | WP04/WP05 | no-parser-ever FAIL-record tests |
| SC-006 | WP03 | brief-contains-API-surface test |
| SC-007 | WP02 | renamed-field gate fixture test |

## MVP scope

WP01 + WP03 + WP04 deliver a runnable, scored tool-loop trial (the mission's
core). WP02 is independent hardening; WP05/WP06 complete whole-story
acceptance and doc honesty.
