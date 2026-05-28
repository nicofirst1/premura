---
work_package_id: WP03
title: BMI Proof Consumer
dependencies:
- WP01
- WP02
requirement_refs:
- FR-004
- FR-005
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-28T08:13:11Z'
subtasks:
- T010
- T011
- T012
- T013
agent: "claude:opus-4.7:python-reviewer:reviewer"
shell_pid: "25829"
history:
- timestamp: '2026-05-28T08:13:11Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/descriptive_signals.py
- tests/test_bmi_signal.py
tags: []
---

# Work Package Prompt: WP03 - BMI Proof Consumer

## Objective

Use BMI as the first cross-domain Stage 2 proof consumer for the new input-
resolution seam.

This WP should not turn BMI into a broad polished analytical feature. Its job is
to prove one thing cleanly:

- a Stage 2 consumer can declare dependencies across profile context and
  observation history
- resolve them honestly
- and refuse explicitly when prerequisites are missing or stale

## Owned Surface

- `src/premura/engine/descriptive_signals.py`
- `tests/test_bmi_signal.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: `WP01`, `WP02`
- Implementation command: `spec-kitty agent action implement WP03 --agent <name>`

## Context

The spec and plan explicitly chose BMI over other candidate first consumers
because BMI is:

- buildable now from shipped data
- cross-domain today
- small enough to stay in proof scope

This WP must therefore treat BMI as a **load-bearing validation slice**, not as a
general body-composition product surface.

## Subtasks

### T010 - Add failing BMI proof tests

**Purpose**

Define the proof slice through public engine behavior before implementation.

**Required changes**

- Add `tests/test_bmi_signal.py`.
- Cover at least:
  - success with declared height + usable weight
  - refusal with missing declared height
  - refusal with stale or missing weight

**Testing guidance**

- Drive behavior through public engine interfaces, not private resolver calls.
- Keep the test names clear that BMI is proof scope.

### T011 - Implement BMI as a Stage 2 consumer

**Purpose**

Add the first cross-domain consumer to the existing Stage 2 answer surface.

**Required changes**

- Implement BMI in `src/premura/engine/descriptive_signals.py`.
- Resolve declared height from `profile_context`.
- Resolve weight from `observation_history`.
- Use the new input-resolution seam instead of direct ad hoc queries.

**Constraints**

- Do not create a new answer family.
- Do not turn BMI into a diagnosis or interpretation layer.

### T012 - Make refusal behavior explicit

**Purpose**

Ensure the proof consumer demonstrates Premura's honesty rules as clearly as its
happy path.

**Required changes**

- Return explicit missing/stale outcomes when declared height or usable weight is
  unavailable.
- Make clear that measured height cannot satisfy the declared-height dependency.

**Constraints**

- No hidden fallback from observation height to declared profile height.
- No silent use of stale weight as if it were current.

### T013 - Add end-to-end proof coverage around the seam

**Purpose**

Prove BMI is actually using the new seam and not bypassing it.

**Required changes**

- Extend `tests/test_bmi_signal.py` to make the cross-domain path explicit.
- Include one case showing unresolved intake-domain declarations remain outside
  the BMI flow and do not change its behavior.

**Testing guidance**

- Keep this targeted: the point is not to test nutrition resolution, only to
  prove unresolved future domains do not leak into the current proof consumer.

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q tests/test_bmi_signal.py
```

Expected outcomes:

- BMI succeeds only with both cross-domain prerequisites present and usable
- BMI refusal states are explicit and deterministic
- the proof consumer visibly depends on the new seam

## Definition Of Done

- BMI exists as a Stage 2 proof consumer.
- BMI resolves declared height and weight through the new seam.
- Missing and stale prerequisite behavior is explicit.
- Tests prove both the happy path and the proof value of the consumer.

## Risks And Watchouts

- The biggest risk is letting BMI reach around the resolver seam “just for one
  simple calculation”.
- Another risk is letting proof scope drift into a broader interpretation surface.
- Avoid conflating “proof consumer” with “throwaway code”; this should be real,
  maintainable Stage 2 behavior.

## Reviewer Guidance

Review this WP as the first true cross-domain consumer.

Ask:

1. Does BMI genuinely use both domains? 
2. Is the refusal behavior as important and well-tested as the success path? 
3. Does the implementation stay inside proof scope?

## Activity Log

- 2026-05-28T08:13:11Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-28T09:19:14Z – claude:opus-4.7:python-implementer:implementer – shell_pid=76148 – Started implementation via action command
- 2026-05-28T09:32:50Z – claude:opus-4.7:python-implementer:implementer – shell_pid=76148 – Ready: BMI registered, dispatches through compute(), uses resolver seam exclusively, refusal paths explicit
- 2026-05-28T09:33:27Z – claude:opus-4.7:python-reviewer:reviewer – shell_pid=25829 – Started review via action command
