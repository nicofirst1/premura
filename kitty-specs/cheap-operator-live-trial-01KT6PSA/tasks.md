# Tasks: Cheap-operator live trial (parser path)

**Mission**: cheap-operator-live-trial-01KT6PSA · **Branch**: master → master
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Four work packages following the plan's build order. WP01 and WP02 are
independent foundations (parallel-safe). WP03 depends on both. WP04 closes the
deferred seam and depends on WP03.

```
WP01 (self-reconcile) ─┐                              ┌─► WP04 (seam wiring)
                       ├─► WP03 (operator + loop) ────┤
WP02 (scoreboard) ─────┘                              └─► WP05 (edge-case fixtures)
```

## Subtask Index

| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | `SelfReconciliationResult` structure | WP01 | | [D] |
| T002 | `self_reconcile()` — raw-header vs declared∪loaded, manifest-blind | WP01 | | [D] |
| T003 | Unit test: raw-header rule, loophole, grader-equivalence on fixture | WP01 | [D] |
| T004 | `ScoreboardEntry` + `LiveTrialRunRecord` structures | WP02 | | [D] |
| T005 | `persist_run()` — kept log + verdict.json, synthetic-only guard | WP02 | | [D] |
| T006 | `append_scoreboard()` / `read_scoreboard()` — append-only JSONL | WP02 | | [D] |
| T007 | `current_floor()` + module `__main__` floor print | WP02 | | [D] |
| T008 | `.gitignore` `data/live_trials/` | WP02 | [D] |
| T009 | Unit test: append/read/order integrity, real-data no-persist, floor | WP02 | [D] |
| T010 | Ollama client (urllib): `_ollama`, `ollama_available`, model config | WP03 | | [D] |
| T011 | `OllamaOperator.operate` — retry loop with self-reconcile gate | WP03 | | [D] |
| T012 | `OllamaDriver` — fixed goal + canned respond | WP03 | | [D] |
| T013 | Grade attempt-1 + final; assemble + persist (synthetic only) | WP03 | | [D] |
| T014 | `run_live_trial_ollama()` entry + `__main__` | WP03 | | [D] |
| T015 | `pyproject.toml` — register + exclude `live_trial` marker | WP03 | [D] |
| T016 | Gated `live_trial` end-to-end test | WP03 | [D] |
| T017 | Wire `real_model_operator`/`real_model_driver` to delegate | WP04 | |
| T018 | Verify existing seam test + invariants (no regression) | WP04 | |
| T019 | Gated test: placeholders resolved, delegated end-to-end | WP04 | [P] |
| T020 | E2E fixture: real-data no-persist | WP05 | [P] |
| T021 | E2E fixture: operator never succeeds within the cap | WP05 | [P] |
| T022 | E2E fixture: model server unavailable outcome | WP05 | [P] |

---

## WP01 — Self-reconciliation gate

**Goal**: the manifest-blind honesty gate used inside the operator loop — the
answer-key-free twin of `grader.honest_about_gaps`, checking **every raw column
in the source file header**. **Priority**: foundation. **Dependencies**: none.
**Independent test**: `uv run pytest tests/test_self_reconcile.py` (default suite,
no model server). **Est. prompt**: ~260 lines. **Prompt**:
[tasks/WP01-self-reconciliation-gate.md](tasks/WP01-self-reconciliation-gate.md)

- [x] T001 `SelfReconciliationResult` structure (WP01)
- [x] T002 `self_reconcile()` — raw-header vs declared∪loaded, manifest-blind (WP01)
- [x] T003 Unit test: raw-header rule, loophole, grader-equivalence on fixture (WP01)

Requirements: FR-003, C-005.

## WP02 — Kept run record + capability-floor scoreboard

**Goal**: durable local outputs — per-run kept session log + verdict, an
append-only scoreboard recording first-attempt vs final per model tier, and the
floor query. **Priority**: foundation. **Dependencies**: none. **Independent
test**: `uv run pytest tests/test_scoreboard.py`. **Est. prompt**: ~360 lines.
**Prompt**: [tasks/WP02-run-record-and-scoreboard.md](tasks/WP02-run-record-and-scoreboard.md)

- [x] T004 `ScoreboardEntry` + `LiveTrialRunRecord` structures (WP02)
- [x] T005 `persist_run()` — kept log + verdict.json, synthetic-only guard (WP02)
- [x] T006 `append_scoreboard()` / `read_scoreboard()` — append-only JSONL (WP02)
- [x] T007 `current_floor()` + module `__main__` floor print (WP02)
- [x] T008 `.gitignore` `data/live_trials/` (WP02)
- [x] T009 Unit test: append/read/order integrity, real-data no-persist, floor (WP02)

Requirements: FR-006, FR-007, FR-011, FR-012 (also NFR-002, NFR-005, C-001).

## WP03 — Cheap operator, driver, loop, grade both attempts

**Goal**: the deliverable run — a cheap local operator drives the parser-build
flow with a self-reconciliation retry loop; the independent slice-one grader
judges attempt-1 and final; results persist via WP02. **Priority**: core.
**Dependencies**: WP01, WP02. **Independent test**: `uv run pytest -m live_trial
tests/test_live_trial_ollama.py` (needs Ollama; skips otherwise). **Est. prompt**:
~430 lines. **Prompt**:
[tasks/WP03-cheap-operator-and-loop.md](tasks/WP03-cheap-operator-and-loop.md)

- [x] T010 Ollama client (urllib): `_ollama`, `ollama_available`, model config (WP03)
- [x] T011 `OllamaOperator.operate` — retry loop with self-reconcile gate (WP03)
- [x] T012 `OllamaDriver` — fixed goal + canned respond (WP03)
- [x] T013 Grade attempt-1 + final; assemble + persist (synthetic only) (WP03)
- [x] T014 `run_live_trial_ollama()` entry + `__main__` (WP03)
- [x] T015 `pyproject.toml` — register + exclude `live_trial` marker (WP03)
- [x] T016 Gated `live_trial` end-to-end test (WP03)

Requirements: FR-001, FR-002, FR-004, FR-005, FR-008, FR-009, FR-010, FR-014
(also NFR-003, C-003, C-005).

## WP04 — Close the deferred live-trial seam

**Goal**: resolve the substrate's deferred D4/R5 placeholders so
`live_trial.real_model_operator` / `real_model_driver` delegate to the new module
instead of raising — without altering the rest of the slice-one seam.
**Priority**: integration. **Dependencies**: WP03. **Independent test**: existing
`tests/test_live_trial_seam.py` still green + new gated delegated test. **Est.
prompt**: ~200 lines. **Prompt**:
[tasks/WP04-close-deferred-seam.md](tasks/WP04-close-deferred-seam.md)

- [ ] T017 Wire `real_model_operator`/`real_model_driver` to delegate (WP04)
- [ ] T018 Verify existing seam test + invariants (no regression) (WP04)
- [ ] T019 Gated test: placeholders resolved, delegated end-to-end (WP04)

Requirements: FR-013 (also NFR-001, NFR-004, NFR-006, C-004).

## WP05 — End-to-end acceptance fixtures for the spec-named edge cases

**Goal**: an owning end-to-end fixture for each spec-named edge case (real-data
no-persist, cap exhaustion, model unavailable), all running in the **default
suite** via an injected fake operator (no model server). Closes the D7 coverage
gap that lives between WP02's unit test and WP03's happy path. **Priority**:
acceptance. **Dependencies**: WP03. **Independent test**: `uv run pytest
tests/test_live_trial_edge_cases.py`. **Est. prompt**: ~190 lines. **Prompt**:
[tasks/WP05-edge-case-acceptance-fixtures.md](tasks/WP05-edge-case-acceptance-fixtures.md)

- [ ] T020 E2E fixture: real-data no-persist (WP05)
- [ ] T021 E2E fixture: operator never succeeds within the cap (WP05)
- [ ] T022 E2E fixture: model server unavailable outcome (WP05)

Requirements: FR-002, FR-012 (edge-case ownership; also NFR-001, NFR-002).

## MVP

WP01 + WP02 + WP03 deliver a runnable, graded cheap-operator live trial with a
persisted floor. WP04 is the clean integration into the shared seam; WP05 proves
the spec-named edge cases end-to-end (the D7 acceptance gate).
