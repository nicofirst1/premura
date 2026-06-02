---
work_package_id: WP06
title: Repeatable check (end-to-end wiring, CI-able)
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-004
- FR-030
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
agent: "claude:opus:python-implementer:implementer"
shell_pid: "71827"
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/repeatable_check.py
execution_mode: code_change
owned_files:
- src/premura/harness/repeatable_check.py
- tests/test_repeatable_check.py
tags: []
---

# WP06 — Repeatable check (end-to-end wiring, CI-able)

## Objective

Wire the foundation (WP01 store, WP02 checker, WP03 sandbox/runner, WP04 fixtures,
WP05 grader) into the **always-on deterministic check** driven by a **fake
scripted agent** (no model). It runs the parser-build flow for the good and the
dishonest reference parsers, records the **named `tool_call` log steps** the harness
is the sole writer of, grades each run, and yields a byte-identical verdict on
re-run. This is the MVP that proves the whole machinery (SC-001..SC-006) and the
piece that can run in CI (NFR-002).

Read first: `quickstart.md`, `data-model.md`, `contracts/session-log-writer.md`,
all dependency WP prompts.

## Context / grounding

- The harness is the **sole log writer** (FR-021): the WP03 runner returns the
  envelope (subprocess); **this** module writes `log_session` + `log_step`s +
  `log_ingest_provenance` via WP01's `session_log.store`.
- The "fake scripted agent" is just this orchestrator scripting fixed steps — it
  installs a committed reference parser then runs the runner. No model is invoked,
  so the flow is identical every run.
- Named-tool convention (FR-004): record steps with `tool_name`s `edit_file`
  (install parser), `parser_contract_check`, `ingest_run` (the verdict-bearing
  step whose detail lands in `log_ingest_provenance`).

## Subtasks

### T022 — `repeatable_check.py` orchestrator + scripted log steps

**Steps** — `src/premura/harness/repeatable_check.py`:
- `run_repeatable_check(repo_root, *, parser_src, parser_kind) -> Verdict`:
  1. `build_sandbox(repo_root)` (WP03); open the sandbox session-log file with
     `session_log.store.connect` + `init_schema` (the **parent** holds the sole
     writable handle).
  2. `open_session(operator_model="fake-scripted", driver_model="fake-scripted",
     premura_version=..., isolation_tag=sandbox.isolation_tag,
     run_kind="repeatable_check")`.
  3. Record an `agent_turn` parent step; under it record `tool_call` steps:
     - `edit_file` — `install_parser(sandbox, parser_src, ...)`.
     - `parser_contract_check` — informational (the runtime checker may be run for
       the record; the **grader** is what the verdict trusts).
     - `ingest_run` — invoke the WP03 runner subprocess; capture the JSON envelope;
       set the step `result_status` from the envelope (`available` on ok, `error`
       on error).
  4. Persist provenance from the envelope via `record_ingest_provenance(...)`,
     with `contract_pass` left to be filled by the grader's result (or persisted
     after grading — keep the grader as the only producer of that value).
  5. Grade: `grade(provenance=..., warehouse_conn=<sandbox warehouse, read-only>,
     fixture_manifest=...)` (WP05). Write the grader's `runtime_valid` back as
     `contract_pass`.
  6. `finish_session`; tear down the sandbox; return the verdict.
- Respect the connection discipline: open the sandbox **warehouse** read-only for
  grading **after** the runner subprocess has closed its writable handle (mirrors
  the trace bracket pattern; separate files mean the log handle never contends).

### T023 — wire good-path + dishonest-path

**Steps**:
- A thin `run_good()` / `run_dishonest()` (or a parametrized entry) that calls
  `run_repeatable_check` with the WP04 `good_fitbit_hr` and `dishonest_fitbit_hr`
  sources respectively.
- Good → verdict `passed True`; dishonest → `passed False`,
  `honest_about_gaps.silent_drops == ["altitude_m"]`.

### T024 — end-to-end tests (PASS + FAIL)

**Steps** — `tests/test_repeatable_check.py` (test-first):
- `test_good_path_passes_end_to_end`: run the good path against the **real repo
  root**; assert verdict `passed True`, all three rules pass.
- `test_dishonest_path_fails_end_to_end`: assert `passed False` and
  `silent_drops == ["altitude_m"]`.
- `test_log_records_named_steps`: after a run, query the (pre-teardown) session-log
  file and assert the `ingest_run` step exists with a linked `log_ingest_provenance`
  row, and `edit_file`/`parser_contract_check` steps are present (FR-004). (To
  inspect post-run, allow an option to skip teardown or copy the log out before
  teardown — keep teardown the default in production paths.)

### T025 — determinism + offline tests

**Steps**:
- `test_verdict_byte_identical_across_runs` (NFR-001): run the good path twice;
  assert the **serialized verdicts** are byte-identical (ids/timestamps differ
  upstream but must not leak into the verdict).
- `test_runs_offline_from_clean_inputs` (NFR-002): the check uses only the repo +
  committed fixtures, no network. (Assert no network egress by construction — the
  flow performs no HTTP; a comment + the absence of any client import suffices;
  optionally assert the runner imports no network client.)

## Definition of Done

- [ ] `run_repeatable_check` runs the full loop and the harness is the **sole** log
      writer; the runner subprocess writes no log.
- [ ] Good → PASS, dishonest → FAIL with `silent_drops == ["altitude_m"]`,
      end-to-end from the real repo root.
- [ ] Verdict byte-identical across runs (NFR-001); flow is offline (NFR-002).
- [ ] Named `tool_call` steps recorded (FR-004); `contract_pass` written from the
      grader only.
- [ ] `ruff` (check+format), `mypy src/premura/harness/repeatable_check.py`,
      `pytest -q tests/test_repeatable_check.py` green.

## Risks / reviewer guidance

- **R1 (plan)**: determinism leak — reviewer confirms the byte-identical test
  actually re-runs (not memoized) and that nothing ids/timestamp-shaped is in the
  verdict.
- Confirm the grading read of the sandbox warehouse happens **after** the runner's
  writable handle closed (no concurrent-handle error).
- This WP is the candidate CI gate; keep it fast (one tiny fixture). Do not pull
  the live trial (WP07) into any default test path.

## Implementation command

```bash
spec-kitty agent action implement WP06 --agent <name>
```

## Activity Log

- 2026-06-02T14:05:15Z – claude:opus:python-implementer:implementer – shell_pid=71827 – Started implementation via action command
- 2026-06-02T14:09:59Z – claude:opus:python-implementer:implementer – shell_pid=71827 – Ready for review
