---
work_package_id: WP01
title: Contract And Policy Vocabulary
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-014
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-correlate-lagged-association-01KSWKV0
base_commit: 7aa67e4a3049feb101fae8b1be5e4062c57e7fbf
created_at: '2026-05-30T14:33:02.044685+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
shell_pid: "56900"
agent: "claude:opus:reviewer:reviewer"
history:
- 2026-05-30T14:27:30Z tasks generated for correlate lagged association mission
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_contract.py
- src/premura/engine/policies/**
- tests/test_engine_correlate_contract.py
- tests/test_engine_policy_correlate.py
tags: []
---

# WP01: Contract And Policy Vocabulary

## Objective

Make `correlate` reviewable before it exists as a method. Add the closed runtime
vocabulary and policy declarations that allow later WPs to prepare and compute a
lagged association without free-form strings or hidden sufficiency rules.

## Branch Strategy

Planning/base branch is `master`. Final merge target is `master`. Do not create a
manual worktree. Spec Kitty will allocate execution worktrees per computed lane
from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent <name>
```

## Context

Authoritative inputs:

- `kitty-specs/correlate-lagged-association-01KSWKV0/spec.md`
- `kitty-specs/correlate-lagged-association-01KSWKV0/plan.md`
- `kitty-specs/correlate-lagged-association-01KSWKV0/research.md`
- `kitty-specs/correlate-lagged-association-01KSWKV0/contracts/correlate-contract.md`
- `docs/adr/0008-correlate-pre-registered-lagged-association.md`

This WP must keep Premura's closed-vocabulary contract intact. `correlate` needs
a new analytical question type because the existing single-series question types
do not express two-series lagged association. It also needs one new confound key,
`common_cause_plausible`, resolved by the research note.

## Subtasks

### T001: Add failing contract tests for lagged-association vocabulary and `common_cause_plausible`

Purpose: pin the public contract before implementation.

Guidance:

- Add tests in `tests/test_engine_correlate_contract.py` and/or
  `tests/test_engine_policy_correlate.py`.
- Assert that the analytical question vocabulary contains a reviewed value for
  lagged association.
- Assert that the confound vocabulary contains `common_cause_plausible`.
- Assert the confound validator rejects unreviewed strings.
- Assert analytical tool descriptors can declare `paired_ordered_daily_series` as
  an input shape without requiring a dispatcher branch.
- Keep tests observable through public engine imports where possible.

Validation:

- The tests should fail before production changes.
- They should not import MCP, DuckDB, PubMed, or network modules.

### T002: Extend the closed analytical question and confound vocabularies for correlate

Purpose: add the smallest reviewed vocabulary required for `correlate`.

Guidance:

- Update `src/premura/engine/analytical_contract.py`.
- Add a lagged-association member to `AnalyticalQuestionType`.
- Add `COMMON_CAUSE_PLAUSIBLE = "common_cause_plausible"` to `ConfoundKey`.
- Update enum docstrings so agents understand these are closed runtime values,
  not prose labels.
- Do not add a catalog of possible common causes.
- Do not loosen `validate_confound_keys`.

Validation:

- Existing analytical contract tests still pass.
- New tests from T001 pass for vocabulary additions.

### T003: Add evidence-policy question mapping and default sufficiency/freshness declarations for lagged association

Purpose: make admissibility explicit before paired computation.

Guidance:

- Update the relevant files under `src/premura/engine/policies/`.
- Add the matching closed policy question type if the policy layer mirrors
  analytical questions.
- Add defaults for relevant metric families using declarative parameters only.
- The declaration should be conservative and reviewable. It should support the
  later hard floors: raw paired sample size 20 and effective sample size 12.
- Do not add expressions, callables, SQL, or network behavior to policy data.
- Do not collapse lagged association onto `recent_trend`, `level_shift_detection`,
  or `smoothed_pattern`.

Validation:

- Policy model/default/evaluator tests cover the new question value.
- Refusal reasons remain distinct.

### T004: Add contract validation tests for paired input shape metadata and forbidden confound keys

Purpose: protect the extension seam before the paired-input implementation.

Guidance:

- Tests should verify an analytical tool descriptor can declare the paired input
  shape and the new confound key.
- Tests should verify duplicate or unknown confound keys are still rejected.
- Tests should verify no per-tool branch is required in analytical dispatch for
  a descriptor to exist.
- Keep this focused on contract behavior, not the eventual correlation method.

Validation:

- Test failures should point to contract validation, not statistical behavior.

### T005: Verify no runtime network or PubMed dependency is introduced by the contract changes

Purpose: preserve the local-first engine boundary.

Guidance:

- Add or extend smoke tests that import the policy/analytical contract surface in
  a clean process and verify no PubMed, MCP, HTTP, or network-adjacent modules are
  loaded.
- If an existing no-network public-surface test already covers this, extend it
  only within this WP's owned test files or add a new correlate-specific test.
- Do not modify unrelated public-surface tests unless ownership is adjusted in a
  later task revision.

Validation:

- Importing `premura.engine` or the relevant analytical contract does not require
  MCP, PubMed, HTTP clients, DuckDB, or network access.

## Definition Of Done

- Lagged association exists as reviewed closed vocabulary.
- `common_cause_plausible` exists and is validated like other confound keys.
- Policy declarations are parameter-only and covered by tests.
- No runtime network/PubMed dependency is introduced.
- Changed-scope tests for this WP pass or unrelated pre-existing failures are
  named in the handoff.

## Risks And Review Notes

- Watch for over-broad globs or static loaders. The bounded registry pattern must
  remain explicit and reviewable.
- Watch for any attempt to enumerate common causes. The rule is caller-supplied
  candidate, not a built-in catalog.
- Reviewers should confirm new vocabulary is closed and tested, not ad-hoc
  strings in the tool body.

## Activity Log

- 2026-05-30T14:33:03Z – claude:opus:implementer:implementer – shell_pid=45555 – Assigned agent via action command
- 2026-05-30T14:42:07Z – claude:opus:implementer:implementer – shell_pid=45555 – Ready for review: closed lagged_association AnalyticalQuestionType + policy QuestionType, common_cause_plausible ConfoundKey, analytical->policy mapping wired, distinct paired-sample-floor sufficiency (min 20) on all recent-run families; 490 passed
- 2026-05-30T14:42:53Z – claude:opus:reviewer:reviewer – shell_pid=56900 – Started review via action command
- 2026-05-30T14:44:13Z – claude:opus:reviewer:reviewer – shell_pid=56900 – Review passed: lagged_association + common_cause_plausible added as closed-enum members (AnalyticalQuestionType/ConfoundKey + policy QuestionType); validate_confound_keys enforces the new key via CONFOUND_KEYS membership; distinct first-class _lagged_association_rule with parameter-only SufficiencyRule(min_observations=20) per research Q3, no mini-language/callables; ANALYTICAL_TO_POLICY_QUESTION mapping consumed live at analytical_inputs.py:409; one rule-shaped confound flag (no enumerated catalog); contract import no-network subprocess test passes; 56 tests green. Scope warning on analytical_inputs.py + 2 test files is the known shared-lane false alarm — edits are the direct consequence of the vocabulary extension.
