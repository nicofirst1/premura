# Tasks: Session Log Substrate (Slice One)

**Mission**: session-log-substrate-01KT45S1
**Planning/base branch**: `master` · **Final merge target**: `master`
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Data model**: [data-model.md](data-model.md) · **Contracts**: [contracts/](contracts/)

8 work packages, 32 subtasks. Tests are required (charter: test-first,
DIRECTIVE_034/036). Front-loadable (no deps): **WP01, WP02, WP04, WP08**.

## Subtask Index

| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | session-log `schema.sql` (3 tables, own file) | WP01 | | [D] |
| T002 | `connect()` + idempotent `init_schema()` | WP01 | | [D] |
| T003 | `open_session` / `record_step` / `finish_session` writers | WP01 | | [D] |
| T004 | `record_ingest_provenance` writer (two-origin + contract_pass) | WP01 | | [D] |
| T005 | `config.session_log_path` property | WP01 | | [D] |
| T006 | store tests (row capture, single-writer, vocab) | WP01 | | [D] |
| T007 | `ContractCheckResult` + `check_runtime_contract` clauses 1–2 | WP02 | [D] |
| T008 | `check_runtime_contract` clauses 3–4 | WP02 | [D] |
| T009 | contract-check tests (each clause pass/fail) | WP02 | [D] |
| T010 | `sandbox.py` build temp copy from tracked tree + temp paths | WP03 | | [D] |
| T011 | sandbox teardown + `install_parser` helper | WP03 | | [D] |
| T012 | `ingest_runner.py` subprocess → JSON outcome envelope | WP03 | | [D] |
| T013 | sandbox/runner tests (tracked-only, envelope valid, teardown) | WP03 | | [D] |
| T014 | synthetic CSV + `fixture_fields.yaml` manifest | WP04 | [D] |
| T015 | `good_fitbit_hr` reference parser (PASS) | WP04 | [D] |
| T016 | `dishonest_fitbit_hr` reference parser (silent drop) | WP04 | [D] |
| T017 | fixtures tests (manifest ↔ CSV; parser behaviors) | WP04 | [D] |
| T018 | `grade()` verdict struct + `loaded` rule | WP05 | |
| T019 | `runtime_valid` rule (calls contract_check on captured evidence) | WP05 | |
| T020 | `honest_about_gaps` reconciliation vs fixture manifest | WP05 | |
| T021 | grader tests (PASS / FAIL+silent_drops / no-trust) | WP05 | |
| T022 | `repeatable_check.py` orchestrator + scripted log steps | WP06 | |
| T023 | wire good-path + dishonest-path | WP06 | |
| T024 | end-to-end tests (full PASS + FAIL) | WP06 | |
| T025 | determinism + offline tests (NFR-001/002) | WP06 | |
| T026 | live-trial `Driver`/`Operator` protocols + `run_live_trial` | WP07 | |
| T027 | fake-operator seam test | WP07 | |
| T028 | NFR-005 test: live trial not in any default gate | WP07 | |
| T029 | edit `operating-agent-roles.md` review-before-use sentence | WP08 | [D] |
| T030 | edit ADR 0010 line + DOCTRINE.md clarifying line | WP08 | [D] |
| T031 | live-doc sync (STATUS / ROADMAP) | WP08 | [D] |
| T032 | SC-007 assertion test (no review-before-use sentence remains) | WP08 | [D] |

---

## Phase 1 — Foundation (no dependencies; parallelizable)

### WP01 — Session-log store (own file, schema, writers, config path)

**Goal**: The session log's own local DuckDB file with idempotent schema and the
sole-writer API. **Priority**: P0 (everything depends on it).
**Independent test**: write a session + steps + provenance to a `tmp_path` file,
query the file back, assert exact rows; assert single-writer.
**Prompt**: [tasks/WP01-session-log-store.md](tasks/WP01-session-log-store.md) (~360 lines)
**Dependencies**: none. **Requirements**: FR-001, FR-002, FR-003, FR-010, FR-011, FR-012, FR-013, FR-021, FR-031, FR-032, FR-070, FR-080; NFR-003, NFR-008.

- [x] T001 session-log `schema.sql` (log_session, log_step, log_ingest_provenance), own file (WP01)
- [x] T002 `connect()` + idempotent `init_schema()` (WP01)
- [x] T003 `open_session` / `record_step` / `finish_session` writers (WP01)
- [x] T004 `record_ingest_provenance` writer — two-origin fields + grader-only `contract_pass` (WP01)
- [x] T005 `config.session_log_path` property (additive) (WP01)
- [x] T006 store tests: row capture, single-writer, status/run_kind vocab (WP01)

### WP02 — Runtime contract checker

**Goal**: The minimal runtime-valid checker (none exists today), a pure function
over captured evidence. **Priority**: P0. **Independent test**: feed crafted
declared/emitted sets + an `empty_warehouse` and assert each clause.
**Prompt**: [tasks/WP02-runtime-contract-checker.md](tasks/WP02-runtime-contract-checker.md) (~250 lines)
**Dependencies**: none. **Requirements**: FR-050.

- [x] T007 `ContractCheckResult` + `check_runtime_contract` clauses `no_derived_emitted`, `declared_equals_emitted` (WP02)
- [x] T008 clauses `declared_exist_in_dim_metric`, `produced_batch_without_raising` (WP02)
- [x] T009 contract-check tests: each clause pass + fail (WP02)

### WP04 — Synthetic fixtures + reference parsers

**Goal**: Committed synthetic Fitbit-HR fixture + ground-truth manifest + good and
dishonest reference parsers. **Priority**: P0. **Independent test**: manifest
matches CSV header; good parser declares unmapped; dishonest parser drops a field.
**Prompt**: [tasks/WP04-fixtures-and-reference-parsers.md](tasks/WP04-fixtures-and-reference-parsers.md) (~320 lines)
**Dependencies**: none. **Requirements**: FR-040; supports NFR-007/SC-002.

- [x] T014 synthetic CSV + `fixture_fields.yaml` (complete source-field set, distinct metric per mappable field) (WP04)
- [x] T015 `good_fitbit_hr` parser — maps HR, declares the rest unmapped, loads (WP04)
- [x] T016 `dishonest_fitbit_hr` parser — silently drops one fixture field (WP04)
- [x] T017 fixtures tests: manifest ↔ CSV header; each reference parser behaves as labeled (WP04)

### WP08 — Doctrine docs update (FR-130) + live-doc sync

**Goal**: Land the build-and-use-now parser rule across the three docs and sync
live status docs. **Priority**: P1 (independent; lands the settled doctrine).
**Independent test**: a test asserts no review-before-use sentence remains and the
build-and-use rule is present (SC-007).
**Prompt**: [tasks/WP08-doctrine-docs-and-sync.md](tasks/WP08-doctrine-docs-and-sync.md) (~280 lines)
**Dependencies**: none. **Requirements**: FR-130; SC-007.

- [x] T029 replace `operating-agent-roles.md` §Dev-time-boundary review-before-use sentence (WP08)
- [x] T030 adjust ADR 0010 "separate from codebase extension" line + add DOCTRINE.md clarifying line (WP08)
- [x] T031 live-doc sync: STATUS (and ROADMAP if it tracks this mission) (WP08)
- [x] T032 SC-007 assertion test (WP08)

---

## Phase 2 — Sandbox + Grader (depend on foundation)

### WP03 — Sandbox + ingest runner

**Goal**: A throwaway full temp copy of the tracked tree with temp warehouse/log
paths, and an in-sandbox subprocess runner that emits the JSON outcome envelope.
**Priority**: P0. **Independent test**: sandbox built from `git ls-files` only;
runner emits a schema-valid envelope; teardown removes everything.
**Prompt**: [tasks/WP03-sandbox-and-ingest-runner.md](tasks/WP03-sandbox-and-ingest-runner.md) (~400 lines)
**Dependencies**: WP01. **Requirements**: FR-020, FR-021; NFR-004.

- [x] T010 `sandbox.py` — build temp copy from tracked tree; point warehouse + session-log paths at temp (WP03)
- [x] T011 teardown + `install_parser(sandbox, parser_src)` helper (WP03)
- [x] T012 `ingest_runner.py` — subprocess entry: parse→validate→load→emit envelope (no log write) (WP03)
- [x] T013 sandbox/runner tests: tracked-only copy, envelope valid, teardown, no-export (WP03)

### WP05 — Deterministic grader

**Goal**: The three-rule grader that recomputes every rule from ground truth and
never trusts self-report; deterministic verdict. **Priority**: P0.
**Independent test**: good parser → PASS, dishonest → FAIL with `silent_drops`,
verdict excludes ids/timestamps.
**Prompt**: [tasks/WP05-deterministic-grader.md](tasks/WP05-deterministic-grader.md) (~420 lines)
**Dependencies**: WP01, WP02, WP04. **Requirements**: FR-060, FR-061, FR-062, FR-063, FR-064, FR-065; NFR-006.

- [ ] T018 verdict structure + `loaded` rule (warehouse rows vs logged) (WP05)
- [ ] T019 `runtime_valid` rule — call `check_runtime_contract` on captured evidence (WP05)
- [ ] T020 `honest_about_gaps` — reconcile fixture manifest vs warehouse + claims (WP05)
- [ ] T021 grader tests: PASS / FAIL+silent_drops / no-self-report-trust (WP05)

---

## Phase 3 — Integration (the end-to-end loop)

### WP06 — Repeatable check (end-to-end wiring, CI-able)

**Goal**: Wire foundation + sandbox + grader into the always-on deterministic
check driven by the fake scripted agent (good + dishonest paths), with named
`tool_call` log steps. **Priority**: P0 (the MVP that proves the machinery).
**Independent test**: full PASS path + full FAIL path; byte-identical verdict on
re-run; runs from a clean clone offline.
**Prompt**: [tasks/WP06-repeatable-check.md](tasks/WP06-repeatable-check.md) (~420 lines)
**Dependencies**: WP01, WP02, WP03, WP04, WP05. **Requirements**: FR-004, FR-030; NFR-001, NFR-002; SC-001..SC-006.

- [ ] T022 `repeatable_check.py` orchestrator: build sandbox, install parser, run runner, harness writes log (scripted steps), grade (WP06)
- [ ] T023 wire good-path (PASS) and dishonest-path (FAIL) (WP06)
- [ ] T024 end-to-end tests: full PASS + full FAIL (WP06)
- [ ] T025 determinism (byte-identical verdict) + offline/clean-clone tests (WP06)

### WP07 — Live-trial seam (scaffold; model deferred)

**Goal**: The `Driver`/`Operator` protocol seam + Fitbit-pointing config + a
`run_live_trial` reusing the harness with a fake operator; real model wiring is a
named follow-up. **Priority**: P2 (never blocks). **Independent test**: fake
operator drives the seam to a verdict; a test asserts the live trial is referenced
by no default gate.
**Prompt**: [tasks/WP07-live-trial-seam.md](tasks/WP07-live-trial-seam.md) (~260 lines)
**Dependencies**: WP03, WP05. **Requirements**: FR-030, FR-031; NFR-005; SC-005.

- [ ] T026 `Driver`/`Operator` protocols + `LiveTrialConfig` + `run_live_trial` (WP07)
- [ ] T027 fake-operator seam test (drives to a verdict) (WP07)
- [ ] T028 NFR-005 test: live trial not wired into any default pytest/CI gate (WP07)

---

## Dependency graph

```
WP01 ─┬─► WP03 ─┬──────────────► WP06
      ├─► WP05 ─┤                 ▲
WP02 ─┘   ▲     └─► WP07          │
WP04 ─────┴───────────────────────┘
WP08 (independent)
```

## MVP scope

**WP06** is the value-proving milestone (the working repeatable check), but it
requires the WP01–WP05 foundation. Smallest first-runnable slice: **WP01 → WP02 →
WP04 → WP05 → WP03 → WP06**. WP07 and WP08 are independent and can land any time.

## Parallelization

- **Wave 1 (no deps):** WP01, WP02, WP04, WP08 — four agents in parallel.
- **Wave 2:** WP03 (after WP01), WP05 (after WP01/02/04).
- **Wave 3:** WP06 (after WP03/05), WP07 (after WP03/05).
