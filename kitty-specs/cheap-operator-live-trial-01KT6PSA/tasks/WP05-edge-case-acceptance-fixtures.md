---
work_package_id: WP05
title: End-to-end acceptance fixtures for the spec-named edge cases (D7)
dependencies:
- WP03
requirement_refs:
- FR-002
- FR-012
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-06-03T12:45:00Z'
subtasks:
- T020
- T021
- T022
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "2464"
history:
- timestamp: '2026-06-03T12:45:00Z'
  actor: tasks
  action: created
authoritative_surface: tests/test_live_trial_edge_cases.py
execution_mode: code_change
owned_files:
- tests/test_live_trial_edge_cases.py
tags: []
---

# WP05 — End-to-end acceptance fixtures for the spec-named edge cases

## Objective

Give **each spec-named edge case an owning end-to-end fixture** that runs the real
`run_live_trial_ollama()` path. This closes a **D7-style coverage gap**: today
these edge cases are covered only by WP02 unit tests or WP03 prose, not by an
end-to-end acceptance run — exactly the drift the audit method
(`docs/building/agents/implement-review-drift-audit.md`) and the prior RCA
(`docs/history/audits/2026-06-02-session-log-substrate-live-doc-drift-rca.md`,
drift dim D7) say lives *between* WPs.

Crucially, all three fixtures run in the **default suite, with no model server**,
by injecting a deterministic fake operator into `run_live_trial_ollama()` (the
injection seam added in WP03 T014). A skipped/absent test is not ownership.

## Spec edge cases owned here

- **Real-data no-persist** — spec.md:77-78 / FR-012.
- **Operator never succeeds within the cap** — spec.md:75-76 / FR-002.
- **Model server unavailable** — spec.md:72-74 (the outcome itself, not a skip).

## Required reading

- `kitty-specs/cheap-operator-live-trial-01KT6PSA/spec.md` "Edge cases" (lines
  ~70-78) and the requirements it names.
- `src/premura/harness/live_trial_ollama.py` (WP03) — `run_live_trial_ollama`'s
  injectable `operator` param, the `LiveTrialOutcome` / `model_unavailable`
  sentinel, and the `is_synthetic` source classifier.
- `src/premura/harness/scoreboard.py` (WP02) — `read_scoreboard` and the runs dir,
  to assert nothing was written.
- `src/premura/harness/live_trial.py` — the `ReferenceParserOperator` test double
  (a deterministic fake that installs a known-good parser) you can reuse as the
  "succeeds" fake.

## Subtasks

### T020 — Real-data no-persist (end-to-end)

**Purpose**: prove an end-to-end real-data invocation leaves **no kept log and no
scoreboard line** (FR-012/NFR-002) — not just that `persist_run` declines in
isolation.

**Steps**: in `tests/test_live_trial_edge_cases.py` (default-collected; use
`tmp_path` for the runs dir + scoreboard, and monkeypatch the module `DATA_DIR` /
pass overrides so nothing touches the real `data/`):
1. Build a deterministic **succeeding** fake operator (reuse
   `ReferenceParserOperator` with the committed good parser, or a local fake that
   installs it) so no model server is needed.
2. Call `run_live_trial_ollama(operator=<fake>, source=<a temp NON-fixture CSV>)`
   — a source that classifies as **non-synthetic**.
3. Assert: the run completed with a verdict, AND the runs dir contains **zero**
   run directories, AND `read_scoreboard()` returns **zero** entries (no line
   appended). No file was created under the temp data dir.

### T021 — Operator never succeeds within the cap (end-to-end)

**Purpose**: prove cap exhaustion yields a recorded FAIL, not a crash (FR-002).

**Steps**:
1. Build a fake operator that **always fails** (e.g. writes a parser that raises,
   or never reconciles) so every attempt fails.
2. Call `run_live_trial_ollama(operator=<always-fail fake>, source=<synthetic
   fixture>, max_tries=2)`.
3. Assert: the call returns normally (no exception), `attempts_used == max_tries`,
   and the final verdict is a well-formed three-rule verdict with `passed=False`.
   (For a synthetic source this run DOES persist — assert exactly one scoreboard
   line with `final_pass=False`.)

### T022 — Model server unavailable (the outcome itself)

**Purpose**: prove the unavailable path produces the defined outcome without
raising into the suite (NFR-001) — owning the outcome, not skipping it.

**Steps**:
1. Force unavailability deterministically: monkeypatch
   `live_trial_ollama.ollama_available` to return `False` (and/or `_ollama` to
   raise `OllamaUnavailableError`).
2. Call `run_live_trial_ollama()` with the **default** operator (so it hits the
   unavailable path).
3. Assert: the call **returns the `model_unavailable` outcome** (or raises
   `OllamaUnavailableError` caught by the test) — it does NOT hang and does NOT
   raise an unexpected error; nothing was persisted (no run dir, no scoreboard
   line).

## Definition of Done

- `tests/test_live_trial_edge_cases.py` exists with T020/T021/T022, all
  **default-collected** (no `live_trial` marker, no model server), all passing.
- Each spec-named edge case (real-data no-persist, cap exhaustion, model
  unavailable) has exactly one owning end-to-end fixture here.
- `ruff`/`mypy` clean; `uv run pytest tests/test_live_trial_edge_cases.py` green.

## Risks & reviewer guidance

- **This is the D7 gate**: reviewer should confirm each edge case is exercised
  through `run_live_trial_ollama()` end-to-end (not via `persist_run` alone) and
  that the tests run in the **default** suite (grep: no `@pytest.mark.live_trial`,
  no `ollama_available()` skip in this file).
- **No real PHI**: the "real-data" case uses a temp synthetic CSV that merely
  *classifies* as non-synthetic — never an actual dump (C-001).
- Confirms the WP03 injection seam + `is_synthetic` classifier are real (if a test
  cannot inject a fake or force unavailability, WP03 is under-built — reject back).

## Branch strategy

Planning happened on `master`; this WP merges back into `master`. Depends on WP03.
Execution worktrees are allocated per computed lane from `lanes.json`.

Implement command: `spec-kitty agent action implement WP05 --agent <name>`

## Activity Log

- 2026-06-03T14:33:23Z – claude:opus:python-implementer:implementer – shell_pid=93782 – Started implementation via action command
- 2026-06-03T14:42:12Z – claude:opus:python-implementer:implementer – shell_pid=93782 – Ready for review: 3 default-suite e2e edge-case fixtures via injected fake operator; frozen guard green
- 2026-06-03T14:42:56Z – claude:opus:python-reviewer:reviewer – shell_pid=2464 – Started review via action command
- 2026-06-03T14:49:31Z – claude:opus:python-reviewer:reviewer – shell_pid=2464 – Review passed: 3 spec-named edge cases each owned by a genuine end-to-end run_live_trial_ollama drive in the DEFAULT suite (no marker, no server) via injected fake operator; T020 no-persist is real (wrapper delegates to the REAL persist_run whose is_synthetic guard makes the decision, source asserted non-synthetic); T021 cap exhaustion returns FAIL with attempts_used==max_tries + 1 scoreboard line + 1 run dir; T022 returns model_unavailable sentinel, nothing persisted; frozen seam guard untouched + green; only owned file committed; ruff clean; full suite 923 passed / 7 deselected.
- 2026-06-03T14:55:24Z – claude:opus:python-reviewer:reviewer – shell_pid=2464 – Done override: Mission merged to master (commit 07cb23c)
