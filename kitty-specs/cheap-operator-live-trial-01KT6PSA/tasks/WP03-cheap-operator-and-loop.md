---
work_package_id: WP03
title: Cheap operator, driver, retry loop, grade both attempts
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- FR-008
- FR-009
- FR-010
- FR-014
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-06-03T12:45:00Z'
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
- T016
history:
- timestamp: '2026-06-03T12:45:00Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/live_trial_ollama.py
execution_mode: code_change
owned_files:
- src/premura/harness/live_trial_ollama.py
- tests/test_live_trial_ollama.py
- pyproject.toml
tags: []
---

# WP03 — Cheap operator, driver, retry loop, grade both attempts

## Objective

The deliverable run. A **cheap local operator** drives the parser-build flow:
it prompts a local model to author a parser into the sandbox, gates each attempt
with the WP01 self-reconciliation check (+ import/parse/validate), feeds failures
back up to a bounded cap, and the **independent slice-one grader** judges
**attempt-1 (un-nagged)** and **final** verdicts. Results persist via WP02 for
synthetic runs. The run reuses the slice-one machinery via
`run_live_trial_with_log` — it does **not** fork the sandbox/runner/store/grader.

> The uncommitted seed `src/premura/harness/live_trial_ollama.py` is
> non-authoritative inspiration only. Build to THIS spec/contracts; do not assume
> the seed is correct.

## Required reading

- `src/premura/harness/live_trial.py` — `Operator`/`Driver` protocols,
  `run_live_trial_with_log`, the sandbox/runner/store/grader call sequence, and
  the `_PARSER_DEST_RELPATH` / `_PARSER_MODULE` / `parser_attr` convention.
- `contracts/operator-driver.md`, `contracts/self-reconciliation.md`, `data-model.md`.
- `src/premura/harness/self_reconcile.py` (WP01) and
  `src/premura/harness/scoreboard.py` (WP02) — your dependencies.
- `src/premura/parsers/CONTRACT.md` + `src/premura/parsers/base.py` — the contract
  surface you give the model (NOT the reference parser).
- `pyproject.toml` `[tool.pytest.ini_options]` — the marker/addopts you extend.

## Subtasks

### T010 — Ollama client (stdlib urllib)

**Steps**:
1. In `src/premura/harness/live_trial_ollama.py`, add `_ollama(prompt, *, model,
   timeout=300) -> str` using `urllib.request` against
   `OLLAMA_URL` (default `http://localhost:11434/api/generate`), `stream=False`,
   low temperature.
2. `ollama_available() -> bool` (cheap ping; used by the gated test to skip).
3. `OllamaUnavailableError(RuntimeError)`; model + URL configurable via env
   (`OLLAMA_MODEL`, `OLLAMA_URL`), default to a locally available cheap coder
   model. No third-party HTTP client.

### T011 — `OllamaOperator.operate` with the retry loop

**Purpose**: the cheap operator authoring a parser, gated and retried.

**Steps**:
1. Implement the slice-one `Operator` protocol: `model_id: str`,
   `operate(self, sandbox, goal) -> None`. It edits ONLY the sandbox tree; it
   never opens the session log (NFR-004).
2. Loop, attempts `1..max_tries` (cap default 3, NFR-003):
   - Build the prompt from the parser-contract surface + a small sample of the
     source + the goal. On retries, append the prior failure. **Never** include
     `fixture_fields.yaml` or any ground-truth mapping (C-005).
   - Write the model output as the parser at the sandbox's
     `_PARSER_DEST_RELPATH`; normalize the class name to the runner-resolved
     `parser_attr`.
   - Gate the attempt: (a) import/parse/validate in a subprocess rooted at the
     sandbox `src`, and (b) `self_reconcile(source_path, batch)` from WP01.
   - On failure within the cap: feed back the parse error and/or the
     `unaccounted` columns; retry. On pass or cap-exhaustion: stop.
3. Expose telemetry for grading/recording: `tries_used`, per-attempt
   `AttemptRecord`s, and the parser produced at **attempt 1** (so it can be graded
   un-nagged in T013).

### T012 — `OllamaDriver`

**Steps**: implement the `Driver` protocol — `model_id`, `goal()` returns the
fixed heart-rate goal, `respond()` returns a canned answer. Records a driver
`model_id`; does NOT call a frontier model (FR-008, DIRECTIVE_036 substitute).

### T013 — Grade attempt-1 and final; assemble + persist

**Purpose**: FR-014 — the un-nagged vs final distinction; FR-004 — grader is the
authority.

**Steps**:
1. Run the flow via `run_live_trial_with_log` (reuse, don't fork). The final
   verdict is the grader's, recorded as the authority.
2. Additionally grade **attempt 1** with the same unchanged grader (ingest the
   attempt-1 parser through the runner + grade), independently of any feedback.
3. Assemble a `LiveTrialRunRecord` (WP02) with `operator_model`, `driver_model`,
   `attempts_used`, `first_attempt_verdict`, `final_verdict`.
4. For a **synthetic** run only, `persist_run(...)` + `append_scoreboard(...)`
   (WP02). A real-data run records nothing (delegated to WP02's guard).

### T014 — Run entry + `__main__`

**Steps**:
1. `run_live_trial_ollama(*, model=DEFAULT_MODEL, source=<synthetic fixture>,
   max_tries=3, repo_root=<repo>) -> (LiveTrialRunRecord, list[AttemptRecord])`.
   Default source is the committed synthetic fixture (no private data, C-001).
2. `__main__`: run, print attempts used, the **first-attempt** and **final**
   three-rule verdicts, and the kept run path; on no server print a clear message
   and exit non-zero WITHOUT raising into any default test (NFR-001).

### T015 — `pyproject.toml` marker

**Steps**: register a `live_trial` marker and exclude it from default collection:
`addopts = ["-m", "not regression and not live_trial"]`, and add the marker line
to `markers`. (If the working tree already has this, make it match exactly.)

### T016 — Gated end-to-end test

**Steps**: in `tests/test_live_trial_ollama.py`, marked `@pytest.mark.live_trial`:
1. `if not ollama_available(): pytest.skip(...)`.
2. Run `run_live_trial_ollama()` over the synthetic fixture.
3. Assert: a well-formed three-rule verdict object (`{loaded, runtime_valid,
   honest_about_gaps}`), `operator_model`/`driver_model` recorded, `1 <=
   attempts_used <= cap`, and that **both** first-attempt and final verdicts are
   present. Do NOT assert PASS (the cheap model is non-deterministic). Tear down /
   clean any kept artifacts the test created.

## Definition of Done

- `run_live_trial_ollama()` runs end-to-end via the unchanged slice-one machinery;
  the loop uses the WP01 gate; attempt-1 and final are graded and recorded via WP02.
- `pyproject.toml` excludes `live_trial` from default collection;
  `uv run pytest -q` stays green with no model server.
- `uv run pytest -m live_trial tests/test_live_trial_ollama.py` runs end-to-end
  when Ollama is up. `ruff`/`mypy` clean.

## Risks & reviewer guidance

- **C-005**: confirm no prompt path includes the manifest/ground truth.
- **Reuse (NFR-006)**: confirm grading/running goes through
  `run_live_trial_with_log` and the existing grader, not a re-implementation.
- **FR-014**: confirm attempt-1 is graded *before* any feedback shaped it.
- **NFR-004**: the operator must not touch the session-log store.

## Branch strategy

Planning happened on `master`; this WP merges back into `master`. Depends on WP01
+ WP02 — branch from the dependency-aware base the implement command selects.
Execution worktrees are allocated per computed lane from `lanes.json`.

Implement command: `spec-kitty agent action implement WP03 --agent <name>`
