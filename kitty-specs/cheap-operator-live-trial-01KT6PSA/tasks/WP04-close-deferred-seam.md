---
work_package_id: WP04
title: Close the deferred live-trial seam (resolve D4/R5 placeholders)
dependencies:
- WP03
requirement_refs:
- FR-013
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-06-03T12:45:00Z'
subtasks:
- T017
- T018
- T019
agent: "claude:opus:python-implementer:implementer"
shell_pid: "76986"
history:
- timestamp: '2026-06-03T12:45:00Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/live_trial.py
execution_mode: code_change
owned_files:
- src/premura/harness/live_trial.py
- tests/test_real_model_seam.py
tags: []
---

# WP04 — Close the deferred live-trial seam

## Objective

Resolve the substrate's named follow-up (D4 / R5): make
`live_trial.real_model_operator` and `live_trial.real_model_driver` **delegate to
the WP03 Ollama operator/driver** instead of raising `NotImplementedError`
(FR-013). Touch **nothing else** in `live_trial.py` — the rest of the slice-one
seam stays byte-for-byte behaviourally unchanged (NFR-006), and the harness stays
the sole log writer (NFR-004).

## Why it matters

This closes the loop opened by slice one in a way that keeps the codebase honest:
the deferred placeholders become real rather than lingering as stubs, and the
shared seam gains the real cheap operator without forking. Because it edits
shared slice-one code, it is isolated into its own focused, reviewable WP.

## Required reading

- `src/premura/harness/live_trial.py` — specifically `real_model_operator` /
  `real_model_driver` (the `NotImplementedError` placeholders and the
  `_DEFERRED_MSG`) and the `Operator`/`Driver` protocols they must satisfy.
- `src/premura/harness/live_trial_ollama.py` (WP03) — `OllamaOperator` /
  `OllamaDriver` you delegate to.
- `tests/test_live_trial_seam.py` — the EXISTING seam test that must keep passing
  (do not modify it; it is owned by slice one).

## Subtasks

### T017 — Delegate the placeholders

**Steps**:
1. Replace the bodies of `real_model_operator(...)` and `real_model_driver(...)`
   so they construct and return the WP03 `OllamaOperator` / `OllamaDriver`
   (forwarding model/source/cap kwargs as appropriate).
2. Remove the `NotImplementedError` raise for these two functions. Keep the
   `_DEFERRED_MSG` only if still referenced elsewhere; otherwise delete it
   cleanly. Avoid a hard import cycle — import the Ollama module lazily inside the
   functions if needed.
3. Do not alter any other function, protocol, or the existing
   `ReferenceParserOperator` / `ScriptedDriver` doubles.

### T018 — No-regression verification

**Steps**:
1. Run `uv run pytest tests/test_live_trial_seam.py` — it must stay green
   (the scripted/repeatable path is unchanged).
2. Confirm the invariants by inspection: the harness is still the only session-log
   writer (the delegated operator edits only the sandbox tree, NFR-004); no
   slice-one machinery was copied or forked (NFR-006); nothing new is wired into a
   default CI gate (NFR-001 / C-004).

### T019 — Gated delegated test

**Steps**: in a NEW `tests/test_real_model_seam.py`, marked
`@pytest.mark.live_trial`:
1. Assert `real_model_operator()` returns an object satisfying the `Operator`
   protocol (has `model_id` + `operate`) and does **not** raise
   `NotImplementedError`; same for `real_model_driver()`. (These assertions can
   run without a server if construction does no network — otherwise guard with
   `ollama_available()`.)
2. If Ollama is available, drive one end-to-end live trial **through the delegated
   path** over the synthetic fixture and assert a well-formed three-rule verdict.
   Skip cleanly otherwise.

## Definition of Done

- `real_model_operator` / `real_model_driver` no longer raise; they return working
  WP03 operator/driver instances.
- `tests/test_live_trial_seam.py` still passes (no regression).
- `tests/test_real_model_seam.py` (gated) asserts the placeholders are resolved and
  the delegated path runs end-to-end when a server is present.
- Default suite stays green with no server; `ruff`/`mypy` clean.

## Risks & reviewer guidance

- **Smallest, most sensitive change**: it edits shared slice-one code. Reviewer:
  confirm the diff to `live_trial.py` is limited to the two placeholder bodies
  (plus any now-dead `_DEFERRED_MSG` cleanup) and that `test_live_trial_seam.py`
  is untouched and green.
- Watch for import cycles between `live_trial.py` and `live_trial_ollama.py`
  (the latter imports the former); delegate via a lazy import.

## Branch strategy

Planning happened on `master`; this WP merges back into `master`. Depends on WP03.
Execution worktrees are allocated per computed lane from `lanes.json`.

Implement command: `spec-kitty agent action implement WP04 --agent <name>`

## Activity Log

- 2026-06-03T14:15:35Z – claude:opus:python-implementer:implementer – shell_pid=76986 – Started implementation via action command
- 2026-06-03T14:24:32Z – claude:opus:python-implementer:implementer – shell_pid=76986 – Ready for review: real_model_operator/driver delegate to live_trial_ollama; seam green; gated delegated test added
