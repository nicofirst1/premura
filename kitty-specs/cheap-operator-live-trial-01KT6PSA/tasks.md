# Tasks: Cheap-operator live trial (parser path)

**Mission**: cheap-operator-live-trial-01KT6PSA · **Branch**: master → master
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Four work packages following the plan's build order. WP01 and WP02 are
independent foundations (parallel-safe). WP03 depends on both. WP04 closes the
deferred seam and depends on WP03.

```
WP01 (self-reconcile) ─┐
                       ├─► WP03 (operator + loop) ─► WP04 (seam wiring)
WP02 (scoreboard) ─────┘
```

## Subtask Index

| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | `SelfReconciliationResult` structure | WP01 | |
| T002 | `self_reconcile()` — raw-header vs declared∪loaded, manifest-blind | WP01 | |
| T003 | Unit test: raw-header rule, loophole, grader-equivalence on fixture | WP01 | [P] |
| T004 | `ScoreboardEntry` + `LiveTrialRunRecord` structures | WP02 | |
| T005 | `persist_run()` — kept log + verdict.json, synthetic-only guard | WP02 | |
| T006 | `append_scoreboard()` / `read_scoreboard()` — append-only JSONL | WP02 | |
| T007 | `current_floor()` + module `__main__` floor print | WP02 | |
| T008 | `.gitignore` `data/live_trials/` | WP02 | [P] |
| T009 | Unit test: append/read/order integrity, real-data no-persist, floor | WP02 | [P] |
| T010 | Ollama client (urllib): `_ollama`, `ollama_available`, model config | WP03 | |
| T011 | `OllamaOperator.operate` — retry loop with self-reconcile gate | WP03 | |
| T012 | `OllamaDriver` — fixed goal + canned respond | WP03 | |
| T013 | Grade attempt-1 + final; assemble + persist (synthetic only) | WP03 | |
| T014 | `run_live_trial_ollama()` entry + `__main__` | WP03 | |
| T015 | `pyproject.toml` — register + exclude `live_trial` marker | WP03 | [P] |
| T016 | Gated `live_trial` end-to-end test | WP03 | [P] |
| T017 | Wire `real_model_operator`/`real_model_driver` to delegate | WP04 | |
| T018 | Verify existing seam test + invariants (no regression) | WP04 | |
| T019 | Gated test: placeholders resolved, delegated end-to-end | WP04 | [P] |

---

## WP01 — Self-reconciliation gate

**Goal**: the manifest-blind honesty gate used inside the operator loop — the
answer-key-free twin of `grader.honest_about_gaps`, checking **every raw column
in the source file header**. **Priority**: foundation. **Dependencies**: none.
**Independent test**: `uv run pytest tests/test_self_reconcile.py` (default suite,
no model server). **Est. prompt**: ~260 lines. **Prompt**:
[tasks/WP01-self-reconciliation-gate.md](tasks/WP01-self-reconciliation-gate.md)

- [ ] T001 `SelfReconciliationResult` structure (WP01)
- [ ] T002 `self_reconcile()` — raw-header vs declared∪loaded, manifest-blind (WP01)
- [ ] T003 Unit test: raw-header rule, loophole, grader-equivalence on fixture (WP01)

Requirements: FR-003, C-005.

## WP02 — Kept run record + capability-floor scoreboard

**Goal**: durable local outputs — per-run kept session log + verdict, an
append-only scoreboard recording first-attempt vs final per model tier, and the
floor query. **Priority**: foundation. **Dependencies**: none. **Independent
test**: `uv run pytest tests/test_scoreboard.py`. **Est. prompt**: ~360 lines.
**Prompt**: [tasks/WP02-run-record-and-scoreboard.md](tasks/WP02-run-record-and-scoreboard.md)

- [ ] T004 `ScoreboardEntry` + `LiveTrialRunRecord` structures (WP02)
- [ ] T005 `persist_run()` — kept log + verdict.json, synthetic-only guard (WP02)
- [ ] T006 `append_scoreboard()` / `read_scoreboard()` — append-only JSONL (WP02)
- [ ] T007 `current_floor()` + module `__main__` floor print (WP02)
- [ ] T008 `.gitignore` `data/live_trials/` (WP02)
- [ ] T009 Unit test: append/read/order integrity, real-data no-persist, floor (WP02)

Requirements: FR-006, FR-007, FR-011, FR-012 (also NFR-002, NFR-005, C-001).

## WP03 — Cheap operator, driver, loop, grade both attempts

**Goal**: the deliverable run — a cheap local operator drives the parser-build
flow with a self-reconciliation retry loop; the independent slice-one grader
judges attempt-1 and final; results persist via WP02. **Priority**: core.
**Dependencies**: WP01, WP02. **Independent test**: `uv run pytest -m live_trial
tests/test_live_trial_ollama.py` (needs Ollama; skips otherwise). **Est. prompt**:
~430 lines. **Prompt**:
[tasks/WP03-cheap-operator-and-loop.md](tasks/WP03-cheap-operator-and-loop.md)

- [ ] T010 Ollama client (urllib): `_ollama`, `ollama_available`, model config (WP03)
- [ ] T011 `OllamaOperator.operate` — retry loop with self-reconcile gate (WP03)
- [ ] T012 `OllamaDriver` — fixed goal + canned respond (WP03)
- [ ] T013 Grade attempt-1 + final; assemble + persist (synthetic only) (WP03)
- [ ] T014 `run_live_trial_ollama()` entry + `__main__` (WP03)
- [ ] T015 `pyproject.toml` — register + exclude `live_trial` marker (WP03)
- [ ] T016 Gated `live_trial` end-to-end test (WP03)

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

## MVP

WP01 + WP02 + WP03 deliver a runnable, graded cheap-operator live trial with a
persisted floor. WP04 is the clean integration into the shared seam.
