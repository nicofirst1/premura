---
work_package_id: WP01
title: Built-in Loader Honesty
dependencies: []
requirement_refs:
- FR-004
- NFR-001
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-harden-grounded-stage-2-contract-01KSJ654
base_commit: dbd7aa862c6182fe0f050d524dd8835872693d5c
created_at: '2026-05-26T13:13:52.859373+00:00'
subtasks:
- T001
- T002
shell_pid: '35810'
history: []
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/__init__.py
- tests/test_engine_contract.py
tags: []
---

# Work Package Prompt: WP01 — Built-in Loader Honesty

## Objective

Remove the built-in signal loader footgun found by the post-merge review:
`_ensure_builtin_signals_loaded()` currently returns early when `REGISTRY` is
non-empty, so registering any custom signal before built-ins load silently
suppresses ALL built-in signals (lab ratios + the six grounded answers). Track
load state explicitly instead.

This is a tiny, behavior-preserving change plus a regression test.

## Owned Surface

- `src/premura/engine/__init__.py`
- `tests/test_engine_contract.py`

Do not modify files outside this list.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed from `lanes.json` during implement.

## Subtasks

### T001 — Explicit `_BUILTINS_LOADED` sentinel

**Purpose**: Decouple "have built-ins loaded?" from "is the registry
non-empty?".

**Required changes**

- In `src/premura/engine/__init__.py`, add a module-level
  `_BUILTINS_LOADED: bool = False`.
- Rewrite `_ensure_builtin_signals_loaded()` so it returns early only when
  `_BUILTINS_LOADED` is `True`; otherwise it imports each module in
  `_BUILTIN_SIGNAL_MODULES`, calls `register_builtin_signals()`, and then sets
  `_BUILTINS_LOADED = True` (use `global`).
- The set/flag must be set AFTER the imports succeed so a failed import does not
  leave the flag wrongly true. (Keep current import-error behavior — do not add
  new swallowing.)

**Constraints**

- Preserve the lazy guarantee: importing `premura.engine` must not call the
  loader or import any signal module eagerly.
- Do not add filesystem scanning. Keep the static `_BUILTIN_SIGNAL_MODULES`
  tuple as the source of truth.
- Idempotent: calling the loader twice must not double-register or error.

### T002 — Loader regression test

**Purpose**: Lock the fix so a future change can't reintroduce the suppression.

**Required changes**

- In `tests/test_engine_contract.py`, add a test that:
  1. Ensures a clean state (built-ins not yet loaded for the assertion — follow
     the existing lazy-state test pattern in this file; reset
     `premura.engine._BUILTINS_LOADED` / clear `REGISTRY` as that pattern does).
  2. Registers a custom signal directly into `REGISTRY` BEFORE calling the
     loader (simulating a contributor's custom pre-registration).
  3. Calls `_ensure_builtin_signals_loaded()`.
  4. Asserts the built-ins are now present — e.g. both a lab-ratio name
     (`ast_alt_ratio`) and a grounded name (`resting_hr_status`) are in
     `REGISTRY` — AND the custom signal is still present.
- Add/keep a check that `import premura.engine` alone does not populate
  `REGISTRY` (laziness preserved) if not already covered.

**Testing stance**

- Use public imports and observable `REGISTRY` membership; do not assert on
  private import mechanics beyond the flag reset the existing tests already use.
- Be careful with test isolation: this test mutates global `REGISTRY` and the
  load flag. Restore state in a fixture/teardown so other tests are unaffected
  (mirror how the existing lazy-load test cleans up).

## Validation

```bash
uv run python -m pytest tests/test_engine_contract.py -q
uv run python -m pytest tests/ -q -k engine     # no regression
uv run python -c "import sys, premura.engine as e; print('lazy:', len(e.REGISTRY)==0 and 'premura.engine.descriptive_signals' not in sys.modules)"
```

## Definition of Done

- `_ensure_builtin_signals_loaded()` uses an explicit load flag, not registry
  truthiness.
- A custom signal registered before the first load no longer suppresses
  built-ins.
- Lazy import behavior is unchanged; full engine tests pass.

## Risks & Watchouts

- Test pollution: the regression test mutates global state — ensure teardown
  restores `REGISTRY` and the flag, or later tests will see a dirty registry.
- Do not set the flag before imports complete.

## Reviewer Guidance

Confirm the early-return now keys off the explicit flag, the flag is set only
after successful import, the lazy guarantee still holds, and the regression test
actually fails against the old `if REGISTRY: return` logic (mentally or by
checking it exercises the pre-registration path).
