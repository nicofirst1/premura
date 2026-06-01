---
work_package_id: WP01
title: Contract And Policy Vocabulary
dependencies: []
requirement_refs:
- FR-008
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-finish-analytical-tool-set-01KT0Y95
base_commit: 7a858a4a46d53a854c23fed0f11a63da633683e4
created_at: '2026-06-01T07:04:30.201627+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
shell_pid: "18591"
agent: "claude:opus:python-reviewer:reviewer"
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_contract.py
- src/premura/engine/policies/_model.py
- src/premura/engine/policies/_defaults.py
- tests/test_engine_analytical_contract_finish_tool_set.py
- tests/test_engine_policy_finish_tool_set.py
tags: []
---

# Work Package Prompt: WP01 - Contract And Policy Vocabulary

## Implement Command

```bash
spec-kitty agent action implement WP01 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Create the reviewed vocabulary and admissibility policy foundation for
`rolling_mean` and the simple anchor-date `paired_t_test`. This WP must not
implement either analytical method, expose MCP tools, or add trace recording. It
only prepares the closed vocabulary and policy gate that later WPs use.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/plan.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/research.md`
- `src/premura/engine/CONTRACT.md`
- `.kittify/charter/charter.md`

## Owned Files

- `src/premura/engine/analytical_contract.py`
- `src/premura/engine/policies/_model.py`
- `src/premura/engine/policies/_defaults.py`
- `tests/test_engine_analytical_contract_finish_tool_set.py`
- `tests/test_engine_policy_finish_tool_set.py`

Do not edit analytical tool implementation files, MCP wrappers, trace files, or
live docs in this WP.

## Subtasks

### T001: Add reviewed analytical question vocabulary for moving-window and paired-comparison shapes

Start with a failing test in `tests/test_engine_analytical_contract_finish_tool_set.py`.

The test should prove that the analytical question vocabulary can represent the
two roadmap tools without using ad hoc strings:

- `rolling_mean` must have a reviewed question shape. Reuse the existing
  smoothed-pattern value only if the test names why it honestly covers a
  moving-window series result; otherwise add a narrow moving-window value.
- `paired_t_test` must have a reviewed paired-comparison question type. Do not
  collapse it onto lagged association, level-shift detection, or recent trend.

Implementation guidance:

- Keep vocabulary additions narrow and descriptive.
- Update enum docstrings to explain what each shape means and why it is not a
  generic catch-all.
- Do not add broad values such as `comparison` unless constrained enough that a
  reviewer can tell exactly what behavior it permits.

### T002: Add evidence-admissibility policy defaults for the new analytical question shapes

Add failing tests in `tests/test_engine_policy_finish_tool_set.py` that build the
builtin policy registry and verify the new question types have policy rules.

The tests should assert:

- Each new question type is accepted only through the closed policy vocabulary.
- The default rules include measurable sufficiency/freshness gates.
- The rules are family-based, not metric-specific enumerations.
- No policy rule imports MCP, trace, PubMed, or network modules.

Implementation guidance:

- Update `src/premura/engine/policies/_model.py` only for closed enum additions
  and any shape metadata required by existing policy machinery.
- Update `src/premura/engine/policies/_defaults.py` with conservative defaults
  aligned to existing analytical policies.
- Do not decide method-specific math here; later tool WPs own method-level
  refusals such as exact pair-count floors.

### T003: Add contract tests for vocabulary closure and forbidden ad hoc labels

Extend the contract tests so invalid question types and confound keys are still
rejected at registration time.

Assertions should cover:

- A descriptor for `rolling_mean` or `paired_t_test` cannot register with an
  arbitrary string question type.
- Closed confound vocabulary enforcement remains active.
- Duplicate confound keys still fail validation.
- The registry still works by descriptor registration, not by dispatcher branch.

Implementation guidance:

- Prefer tests against `AnalyticalToolSpec.validate()` and the public analytical
  contract types.
- Do not import the future tool modules; they do not exist yet.

### T004: Add policy tests proving the new question shapes are admissibility-gated independently

Add tests proving the new question shapes map to policy rules independently of
existing analytical shapes.

The tests should make these regressions hard:

- `paired_t_test` cannot silently reuse `lagged_association` rules.
- `rolling_mean` cannot silently reuse a descriptive trend policy if a reviewed
  moving-window question type was added.
- Unsupported policy shapes still produce the established refusal path rather
  than a Python exception in normal missing-policy cases.

Implementation guidance:

- Keep tests public-boundary oriented: build/evaluate policies through the
  existing policy API where possible.
- Avoid patching private collaborators just to force branches.

### T005: Document the contract/policy decisions in code comments without widening scope

Update docstrings or nearby comments only where they help a future tool author.

The comments should state:

- The new vocabulary is reviewed and closed.
- `paired_t_test` means simple paired comparison in this mission, not arbitrary
  condition pairing.
- Any later broader pairing mode must add its own contract/rules rather than
  smuggling behavior into this shape.

Definition of done:

- Contract and policy tests pass.
- No analytical method implementation is added.
- No MCP/trace/default publication code is touched.

## Test Strategy

Run focused tests:

```bash
uv run python -m pytest tests/test_engine_analytical_contract_finish_tool_set.py tests/test_engine_policy_finish_tool_set.py -q
```

Run existing nearby policy tests if time permits:

```bash
uv run python -m pytest tests/test_engine_policy_defaults.py tests/test_engine_policy_evaluator.py -q
```

## Risks

- Over-broad question types will make future tool review weak. Prefer narrow
  names and docstrings.
- Adding a question type without a default policy will make later input
  preparation fail late. Keep the vocabulary and policy defaults together.

## Reviewer Guidance

Review that this WP creates only the foundation. If it includes tool math, MCP
wrappers, trace identity registration, or docs/status sync, reject as scope creep.

## Activity Log

- 2026-06-01T07:04:31Z – claude:opus:python-implementer:implementer – shell_pid=98304 – Assigned agent via action command
- 2026-06-01T07:16:26Z – claude:opus:python-implementer:implementer – shell_pid=98304 – Ready for review: Added reviewed closed analytical question types MOVING_WINDOW_PATTERN (rolling_mean) and PAIRED_DIFFERENCE (paired_t_test) to the contract enum + policy QuestionType; declared family-based admissibility defaults (moving-window reuses the recent-run substrate; paired-difference gets its own shared pair-floor rule, distinct from lagged-association); extended the live ANALYTICAL_TO_POLICY_QUESTION map and tests. No tool math/MCP/trace. Necessary out-of-scope edits: analytical_inputs.py map + two existing closed-set tests (no WP owns analytical_inputs.py). Full suite 653 passed; ruff/format/mypy(src) clean.
- 2026-06-01T07:16:59Z – claude:opus:python-reviewer:reviewer – shell_pid=18591 – Started review via action command
- 2026-06-01T07:21:10Z – claude:opus:python-reviewer:reviewer – shell_pid=18591 – Review passed: MOVING_WINDOW_PATTERN (rolling_mean) and PAIRED_DIFFERENCE (paired_t_test) added as distinct reviewed closed-vocabulary values in both AnalyticalQuestionType and policies.QuestionType, neither collapsed onto smoothed_pattern/lagged_association; vocabulary closure stays enforced (tests prove rejection of ad hoc question types, unknown/duplicate confound keys); admissibility defaults gate both new shapes family-based across all recent-run families with measurable freshness/sufficiency, paired_difference gets its own shared pair floor (8) via _paired_difference_rule distinct from lagged-association; paired_difference scoped to simple anchor-date pairing with broader modes documented-not-implemented; no causal/significance/diagnostic language introduced (anti-causal caveats only); no tool math/MCP/trace. Integration confirmed: enum->ANALYTICAL_QUESTION_TYPES frozenset, policy question_rules read by evaluator, and ANALYTICAL_TO_POLICY_QUESTION map all consume the new members (no dead vocabulary). Gates: ruff check + format clean, mypy clean on 4 changed src files, full suite 653 passed. Scope judgment: the analytical_inputs.py ANALYTICAL_TO_POLICY_QUESTION edit and the two existing closed-set test updates are the MINIMUM necessary integration (no WP owns analytical_inputs.py; omitting the two map entries would strand the new tools at input prep and break the existing closed-set assertions) — justified, not creep; the incidental ruff-format reflows in analytical_inputs.py stem from the base file being format-dirty and are formatter-driven, harmless.
- 2026-06-01T09:14:50Z – claude:opus:python-reviewer:reviewer – shell_pid=18591 – Done override: Mission squash-merged to master (984cc48)
