---
work_package_id: WP07
title: Live-trial seam (scaffold; model deferred)
dependencies:
- WP03
- WP05
requirement_refs:
- FR-030
- FR-031
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
agent: "claude:opus:python-implementer:implementer"
shell_pid: "81412"
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/live_trial.py
execution_mode: code_change
owned_files:
- src/premura/harness/live_trial.py
- tests/test_live_trial_seam.py
tags: []
---

# WP07 — Live-trial seam (scaffold; model deferred)

## Objective

Lay down the **live-trial seam** so the real (cheap-model) operator can be wired in
later without reshaping anything: the `Driver` / `Operator` protocols, a
`LiveTrialConfig` pointing at the local Fitbit dump, and a `run_live_trial` that
reuses the **same** sandbox + log + grader machinery as the repeatable check but
with an `Operator` editing the sandbox instead of a scripted install. The actual
cheap-model invocation is a **named follow-up** (D4) — this WP ships the seam and
proves it with a **fake operator**. The live trial must be wired into **no** CI
gate (NFR-005); real Fitbit data stays local and uncommitted (C-003).

Read first: `contracts/live-trial-seam.md`, `research.md` (D4), WP03 + WP05
prompts.

## Context / grounding

- Identical machinery to WP06; only the "agent" differs (an `Operator` that edits
  the sandbox tree vs. a scripted install). To avoid owning WP06's file, this
  module calls the lower layers (sandbox, runner, store, grader) directly.
- `operator_model` / `driver_model` are captured on the session (FR-031) for the
  later capability-tier sweep.
- SC-005 is refined here: the seam is exercised by a fake operator; model-driven
  execution against the real dump is the follow-up — this is explicit, not a
  silent waiver (DIRECTIVE_010).

## Subtasks

### T026 — protocols + config + `run_live_trial`

**Steps** — `src/premura/harness/live_trial.py`:
- `Operator(Protocol)`: `model_id: str`; `operate(sandbox, goal) -> None` — edits
  the sandbox tree to make the dropped data ingestable (writes a parser). A
  provided `ReferenceParserOperator` test double installs a committed reference
  parser (an outside-boundary substitute).
- `Driver(Protocol)`: `model_id: str`; `goal() -> str`; `respond(question) -> str`.
- `LiveTrialConfig`: `source_dir: Path` (default `~/Downloads/MyFitbitData`),
  `category: str = "heart_rate"`, `run_kind: str = "live_trial"`.
- `run_live_trial(config, *, driver, operator) -> Verdict`: build sandbox → record
  session with `operator_model=operator.model_id`,
  `driver_model=driver.model_id`, `run_kind="live_trial"` → `operator.operate(...)`
  → run the WP03 runner → harness writes the log → WP05 grade → teardown → return
  verdict.
- A clearly-named `NotImplementedError`-raising placeholder (or a documented
  `# follow-up`) for the real cheap-model `Operator`/`Driver` — do **not** invoke
  any model in this slice.

### T027 — fake-operator seam test

**Steps** — `tests/test_live_trial_seam.py` (test-first):
- `test_seam_drives_to_verdict_with_fake_operator`: use `ReferenceParserOperator`
  installing `good_fitbit_hr` against the synthetic fixture (not the real dump);
  assert `run_live_trial` returns a `passed True` verdict and the session records
  `run_kind=="live_trial"` with the fake `operator_model`/`driver_model`.

### T028 — NFR-005 test: not in any default gate

**Steps**:
- `test_live_trial_not_in_default_gate`: assert no default-collected test module
  imports/invokes `run_live_trial` against the real `source_dir`, and that the
  live trial path is not referenced by any CI/pytest default marker. Practically:
  the only test that touches `run_live_trial` is this seam test (synthetic input),
  and any real-dump exercise is guarded by `@pytest.mark.regression` (skipped when
  files absent) — assert that guard exists if a real-dump test stub is included.

## Definition of Done

- [ ] `Driver`/`Operator` protocols + `LiveTrialConfig` + `run_live_trial` exist
      and reuse the shared machinery; no model is invoked (deferred placeholder).
- [ ] `operator_model`/`driver_model`/`run_kind=live_trial` captured (FR-031).
- [ ] Fake-operator seam test passes against the **synthetic** fixture.
- [ ] NFR-005 test proves the live trial is in no default gate; real dump access
      is regression-marked/local-only.
- [ ] `ruff` (check+format), `mypy src/premura/harness/live_trial.py`, `pytest -q
      tests/test_live_trial_seam.py` green.

## Risks / reviewer guidance

- **R5 (plan)**: the deferral must read as a **named follow-up**, not a waiver —
  reviewer confirms the placeholder is explicit and SC-005's refinement is
  documented here.
- Nothing under `source_dir` is ever copied into the repo or a commit (C-003).
- Reviewer: confirm `run_live_trial` does not duplicate WP06's orchestrator file
  (ownership) — it calls the lower layers directly.

## Implementation command

```bash
spec-kitty agent action implement WP07 --agent <name>
```

## Activity Log

- 2026-06-02T14:14:07Z – claude:opus:python-implementer:implementer – shell_pid=81412 – Started implementation via action command
- 2026-06-02T14:20:54Z – claude:opus:python-implementer:implementer – shell_pid=81412 – Ready for review
