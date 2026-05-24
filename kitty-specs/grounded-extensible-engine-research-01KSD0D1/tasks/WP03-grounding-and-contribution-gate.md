---
work_package_id: WP03
title: Grounding And Contribution Gate
dependencies:
- WP01
- WP02
requirement_refs:
- FR-003
- FR-004
- FR-005
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-24T13:02:16Z'
subtasks:
- T009
- T010
- T011
- T012
- T013
agent: "claude:opus:research-implementer:implementer"
shell_pid: "88351"
history:
- timestamp: '2026-05-24T13:02:16Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/
execution_mode: planning_artifact
owned_files:
- kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/03-grounding-and-contribution-gate.md
tags: []
---

# Work Package Prompt: WP03 - Grounding And Contribution Gate

## Objective

Define the scientific grounding rubric, the contributor-facing submission contract, and the reviewer gate for future Stage 2 engine functions.

The output is `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/03-grounding-and-contribution-gate.md`.

## Why This WP Exists

The mission's central promise is not only to explain which Stage 2 ideas seem useful, but also to explain how contributors and coding agents should add new engine functions without weakening trust. That means this WP must turn abstract safety language into a usable decision rule and a compact review gate.

This WP directly supports:

- `FR-003`
- `FR-004`
- `FR-005`
- `NFR-003`

## Owned Surface

- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/03-grounding-and-contribution-gate.md`

Do not modify files outside this list.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP03 --agent <name>`

Do not start until WP01 and WP02 are available in the lane assigned to this WP.

## Inputs You Must Reuse

- `research/01-repo-baseline.md`
- `research/02-stage2-taxonomy.md`
- `src/premura/parsers/CONTRACT.md`
- `src/premura/engine/__init__.py`
- `src/premura/engine/_registry.py`
- Any explicit outside evidence you need for the grounding rubric

## Subtasks

### T009 - Compare the parser contract with the current engine seam

**Purpose**

Use the parser contribution model as a comparison point without blindly copying it.

**Required work**

- Identify what the parser contract gets right that Stage 2 should borrow.
- Identify what is different about Stage 2 and therefore should not be copied literally.
- Summarize the differences in practical contributor terms, not just architecture terms.

**Watchouts**

- Do not imply that Stage 2 needs the exact same plugin mechanism as parsers.
- Keep the comparison focused on contribution contract shape and review discipline.

### T010 - Draft the scientific grounding rubric

**Purpose**

Define what makes a proposed engine function acceptable, defer-worthy, or reject-worthy.

**Required work**

- Write explicit accept, defer, and reject criteria.
- Make clear what counts as sufficient evidence for a function to belong in Premura.
- Include expectations for caveat handling and uncertainty disclosure.
- Make the rubric specific enough to evaluate a real candidate later.

**Good outcome**

- A reviewer can point to the rubric and justify why a function belongs, needs more evidence, or should be rejected.

### T011 - Draft the contributor submission contract

**Purpose**

Tell future contributors exactly what they must provide when proposing a new engine function.

**Required work**

- Define the minimum submission package.
- Include at least:
  - intended user question
  - required inputs
  - output shape
  - rationale
  - evidence basis
  - caveats / uncertainty handling
  - notes for review
- Keep it compact and concrete.

### T012 - Compress the reviewer gate

**Purpose**

Turn the contract into a review surface that is usable in normal work rather than a long essay.

**Required work**

- Express the reviewer gate as 10 or fewer pass/fail checks.
- Keep the checks objective where possible.
- Ensure the gate covers scientific grounding, boundary compliance, and review readiness.

**Constraint**

- Do not exceed 10 checks.

### T013 - Add worked examples

**Purpose**

Prove that the rubric and gate are usable, not merely aspirational.

**Required work**

- Add at least three worked examples:
  - one accept case
  - one defer case
  - one reject case
- Use examples that are plausible for Premura.
- Explain why each case lands where it does under the rubric.

## Validation Strategy

This WP is complete when:

- `research/03-grounding-and-contribution-gate.md` exists.
- It contains a grounding rubric, contributor contract, reviewer gate, and worked examples.
- The reviewer gate contains 10 or fewer checks.

## Definition Of Done

- Parser-vs-engine contract comparison documented.
- Accept/defer/reject rubric written.
- Contributor contract written.
- Reviewer gate compressed and usable.
- Worked examples included.

## Risks And Watchouts

- The biggest risk is vague prose that sounds wise but does not guide a decision.
- The second biggest risk is writing an overbuilt governance framework that future contributors will ignore.

## Reviewer Guidance

- Check whether a contributor could follow the contract without extra meetings.
- Check whether the worked examples genuinely exercise the rubric.
- Check whether the gate is short enough for routine review.

## Activity Log

- 2026-05-24T13:20:00Z – claude:opus:research-implementer:implementer – shell_pid=88351 – Started implementation via action command
