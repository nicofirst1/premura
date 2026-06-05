# Tasks: Intake Parser Acceptance Scenario

**Mission**: intake-parser-acceptance-scenario-01KTBT72
**Branch**: master (planning base) → merges into master
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

7 work packages, 30 subtasks. Each WP is independently implementable and green on its
own. Tests are first-class here (this mission *is* a test harness).

## Subtask Index (reference table — not a tracking surface)

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Capture golden observation verdict (pre-refactor baseline) | WP01 |  | [D] |
| T002 | Define `Scenario` + `DrawerGradingStrategy` protocol + registry primitives | WP01 |  | [D] |
| T003 | Implement the observation `DrawerGradingStrategy` (wraps today's logic) | WP01 |  | [D] |
| T004 | Refactor `grade()` to compute rules via the strategy (no per-drawer branch) | WP01 |  | [D] |
| T005 | Golden-verdict regression test (observation byte-identical) | WP01 |  | [D] |
| T006 | Implement `check_intake_runtime_contract` over the IntakeBatch surface | WP02 | [D] |
| T007 | Return a `ContractCheckResult`-shaped result (sorted violations) | WP02 | [D] |
| T008 | Test intake runtime clauses + clause names/count match contract | WP02 | [D] |
| T030 | Runner witnesses intake parse/validate/persist (stage-tagged error) | WP02 |  | [D] |
| T009 | Author `alien_intake.csv` (meals+supplements, epoch-µs, foreign cols) | WP03 | [D] |
| T010 | Author `alien_intake_manifest.yaml` (grader-only ground truth) | WP03 | [D] |
| T011 | Implement `reference_intake_parser.py` (+ `MAPPED_SOURCE_COLUMNS`) | WP03 | [D] |
| T012 | Intake boundary-truth reader (intake tables) | WP04 |  | [D] |
| T013 | Intake gap reconciler (manifest vs loaded∪declared) | WP04 |  | [D] |
| T014 | Assemble the intake `DrawerGradingStrategy` | WP04 |  | [D] |
| T015 | `scenario_registry.py` — observation + intake → `all_scenarios()` | WP04 |  | [D] |
| T016 | Layer-1 happy-path e2e: reference parser → full three-rule pass | WP04 |  | [D] |
| T017 | e2e: mis-filed intake row → `loaded` fails | WP05 | [D] |
| T018 | e2e: unmappable field → declared gap (not silent drop) | WP05 | [D] |
| T019 | e2e: renamed-but-consumed column → accounted | WP05 | [D] |
| T020 | e2e: intake-only vs both drawer targets | WP05 | [D] |
| T021 | structural: no per-source branch + ≥2 scenarios over one path | WP05 | [D] |
| T022 | Widen captured provenance to carry the intake surface (transport) | WP06 |  | [D] |
| T023 | `live_trial` run path drives a `Scenario`; pass strategy to `grade()` | WP06 |  | [D] |
| T024 | Failure path persists a completed failing record on import/parse failure | WP06 |  | [D] |
| T025 | Type-widen `self_reconcile` (`IngestBatch \| IntakeBatch`) | WP06 |  | [D] |
| T026 | `StubBrokenParserOperator` + deterministic failure-path test | WP06 |  | [D] |
| T027 | Generalize `_PROBE_TEMPLATE` off its observation-only gate | WP07 |  | [D] |
| T028 | Layer-2 entry selects the intake scenario; records run/model ids | WP07 |  | [D] |
| T029 | `live_trial`-marked intake test (prints score, never asserts pass) | WP07 |  | [D] |

## Dependency graph

```
WP01 ─┬─> WP04 ──> WP05
WP02 ─┤
WP03 ─┘
WP01 ─> WP06
WP03, WP04, WP06 ─> WP07
```

Parallel start: **WP01, WP02, WP03** (no dependencies).

---

## WP01 — Scenario abstraction + drawer-parametric grader (foundation)

**Goal**: Lift the harness's hardcoded observation source into a `Scenario` + injected
`DrawerGradingStrategy`, generalize `grade()` so the three rules are strategy-computed
with no per-drawer branch, and prove the observation verdict is unchanged byte-for-byte.
**Priority**: P0 (foundation; everything depends on the abstraction).
**Independent test**: the golden observation verdict reproduces exactly after the refactor.
**Prompt**: [tasks/WP01-scenario-abstraction-and-grader.md](tasks/WP01-scenario-abstraction-and-grader.md) · ~320 lines

- [x] T001 Capture golden observation verdict (pre-refactor baseline) (WP01)
- [x] T002 Define `Scenario` + `DrawerGradingStrategy` protocol + registry primitives (WP01)
- [x] T003 Implement the observation `DrawerGradingStrategy` (wraps today's logic) (WP01)
- [x] T004 Refactor `grade()` to compute rules via the strategy (no per-drawer branch) (WP01)
- [x] T005 Golden-verdict regression test (observation byte-identical) (WP01)

**Dependencies**: none. **Risks**: regressing observation grading (mitigated by T001→T005).

## WP02 — Intake runtime_valid checker

**Goal**: A bounded `check_intake_runtime_contract` over the real IntakeBatch surface —
not the full parser-review contract, and not a fake canonical-metric mirror.
**Priority**: P0 (intake grading needs it).
**Independent test**: each clause's pass/fail; clause names/count match the contract.
**Prompt**: [tasks/WP02-intake-runtime-contract.md](tasks/WP02-intake-runtime-contract.md) · ~200 lines

- [x] T006 Implement `check_intake_runtime_contract` over the IntakeBatch surface (WP02)
- [x] T007 Return a `ContractCheckResult`-shaped result (sorted violations) (WP02)
- [x] T008 Test intake runtime clauses + clause names/count match contract (WP02)
- [x] T030 Runner witnesses intake parse/validate/persist; emits stage-tagged error (WP02)

**Dependencies**: none. **Risks**: drifting toward the full review contract (guarded by T008). Owns the producer (runner) + consumer (checker) of the runtime-evidence seam so it is internal to one WP.

## WP03 — Alien source + manifest + reference intake parser (fixtures)

**Goal**: The synthetic, deliberately-alien meals+supplements source, its grader-only
ground-truth manifest, and a known-good reference intake parser (layer-1 operator).
**Priority**: P0 (the thing being read).
**Independent test**: the reference parser parses the alien source and `validate()`s.
**Prompt**: [tasks/WP03-alien-source-and-reference-parser.md](tasks/WP03-alien-source-and-reference-parser.md) · ~240 lines

- [x] T009 Author `alien_intake.csv` (meals+supplements, epoch-µs, foreign cols) (WP03)
- [x] T010 Author `alien_intake_manifest.yaml` (grader-only ground truth) (WP03)
- [x] T011 Implement `reference_intake_parser.py` (+ `MAPPED_SOURCE_COLUMNS`) (WP03)

**Dependencies**: none. **Risks**: manifest leaking onto an operator path (C-005) — keep it grader-only.

## WP04 — Intake drawer strategy + scenario registry + happy-path e2e (first intake slice)

**Goal**: The intake `DrawerGradingStrategy` (intake-table boundary truth + the WP02
checker + gap reconcile), the scenario registry exposing both scenarios, and the
layer-1 full-pass end-to-end run.
**Priority**: P1 (first user-visible intake value).
**Independent test**: reference parser over the alien source → full three-rule pass.
**Prompt**: [tasks/WP04-intake-strategy-and-grading-e2e.md](tasks/WP04-intake-strategy-and-grading-e2e.md) · ~360 lines

- [x] T012 Intake boundary-truth reader (intake tables) (WP04)
- [x] T013 Intake gap reconciler (manifest vs loaded∪declared) (WP04)
- [x] T014 Assemble the intake `DrawerGradingStrategy` (WP04)
- [x] T015 `scenario_registry.py` — observation + intake → `all_scenarios()` (WP04)
- [x] T016 Layer-1 happy-path e2e: reference parser → full three-rule pass (WP04)

**Dependencies**: WP01, WP02, WP03. **Risks**: a per-drawer branch creeping into the shared path (the structural guard lands later in the edge-case suite).

## WP05 — Intake drawer + edge-case end-to-end suite

**Goal**: End-to-end fixtures for the **four deterministic** spec-named intake edge cases this
WP owns (mis-filed row, unmappable field, renamed-but-consumed, intake-only vs both) + the
structural no-fork / ≥2-scenarios proof. The fifth edge case ("malformed parser") is owned by
WP06 (deterministic) and WP07 (live), not here.
**Priority**: P1.
**Independent test**: the five e2e/structural tests pass deterministically, offline.
**Prompt**: [tasks/WP05-intake-edge-cases-and-no-fork.md](tasks/WP05-intake-edge-cases-and-no-fork.md) · ~340 lines

- [x] T017 e2e: mis-filed intake row → `loaded` fails (WP05)
- [x] T018 e2e: unmappable field → declared gap (not silent drop) (WP05)
- [x] T019 e2e: renamed-but-consumed column → accounted (WP05)
- [x] T020 e2e: intake-only vs both drawer targets (WP05)
- [x] T021 structural: no per-source branch + ≥2 scenarios over one path (WP05)

**Dependencies**: WP04. **Risks**: edge cases asserted at component level (D7) — every one here is full sandbox→grade.

## WP06 — Captured provenance + self_reconcile widening + deterministic failure path

**Goal**: Widen captured provenance to carry the intake surface, make the run path drive
a `Scenario`, guarantee a completed failing record on parser import/parse failure, and
type-widen `self_reconcile`.
**Priority**: P1.
**Independent test**: a stub broken-parser operator yields a completed, persisted, failing record.
**Prompt**: [tasks/WP06-provenance-failure-path.md](tasks/WP06-provenance-failure-path.md) · ~320 lines

- [x] T022 Widen captured provenance to carry the intake surface (transport) (WP06)
- [x] T023 `live_trial` run path drives a `Scenario`; pass strategy to `grade()` (WP06)
- [x] T024 Failure path persists a completed failing record on import/parse failure (WP06)
- [x] T025 Type-widen `self_reconcile` (`IngestBatch | IntakeBatch`) (WP06)
- [x] T026 `StubBrokenParserOperator` + deterministic failure-path test (WP06)

**Dependencies**: WP01. **Risks**: the failure path crashing before a record exists (the RCA this guards).

## WP07 — Layer-2 live-trial intake (opt-in)

**Goal**: Generalize the in-sandbox probe off its observation-only gate, let the layer-2
entry select the intake scenario, and add the `live_trial`-marked intake test.
**Priority**: P2 (opt-in; never blocks CI).
**Independent test**: with local Ollama, the intake scenario runs end-to-end and prints a verdict.
**Prompt**: [tasks/WP07-live-trial-intake.md](tasks/WP07-live-trial-intake.md) · ~260 lines

- [x] T027 Generalize `_PROBE_TEMPLATE` off its observation-only gate (WP07)
- [x] T028 Layer-2 entry selects the intake scenario; records run/model ids (WP07)
- [x] T029 `live_trial`-marked intake test (prints score, never asserts pass) (WP07)

**Dependencies**: WP03, WP04, WP06. **Risks**: a non-local backend leaking data (guarded by the inherited `OLLAMA_URL` check).

## MVP

**WP01** is the foundation (abstraction + observation-preserving grader). The first
*intake* value is **WP04** (intake graded end-to-end). WP07 is opt-in and can land last.
