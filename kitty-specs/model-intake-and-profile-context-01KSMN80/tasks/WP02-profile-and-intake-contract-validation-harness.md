---
work_package_id: WP02
title: Profile And Intake Contract Validation Harness
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-27T12:27:28Z'
subtasks:
- T006
- T007
- T008
agent: "claude:opus:implementer:implementer"
shell_pid: "47453"
history:
- timestamp: '2026-05-27T12:27:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: tests/
execution_mode: code_change
owned_files:
- tests/test_profile_intake_contracts.py
tags: []
---

# Work Package Prompt: WP02 - Profile And Intake Contract Validation Harness

## Objective

Make the new profile/intake contract enforceable by agent reviewers.

The planning work explicitly chose machine-applicable gates because the expected
first-pass reviewers are agents. This WP turns the authoritative contract surface
from WP01 into something that can fail loudly when later changes drift.

## Owned Surface

- `tests/test_profile_intake_contracts.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP02 --agent <name>`

## Context

WP01 creates four machine-readable contract files plus an authoritative prose
document under `docs/architecture/`. This WP should read those shipped surfaces
as an external consumer would and enforce the load-bearing rules from planning.

The tests should validate semantics, not wording trivia.

## Subtasks

### T006 - Add black-box contract loading and consistency tests

**Purpose**

Prove that the authoritative contract artifacts exist, parse, and line up with
each other.

**Required changes**

- Add `tests/test_profile_intake_contracts.py`.
- Load the shipped YAML files from `docs/architecture/contracts/`.
- Assert that:
  - the expected files exist
  - each file parses successfully
  - the expected top-level sections are present
  - entities, examples, invariants, and dependency declarations refer to a
    shared vocabulary rather than unrelated names

**Testing stance**

- Treat the files as external artifacts.
- Avoid mocking the contract into existence.

### T007 - Add invariant-oriented semantic tests

**Purpose**

Turn the most important positive invariants into pass/fail checks.

**Required changes**

- Add tests that enforce:
  - every shipped example maps to exactly one canonical home
  - overlap examples keep profile, intake, observation, and note meanings distinct
  - the contract includes a visible supersession/correction path where planning
    says it must
  - partial knowledge is allowed without inventing values

**Design guidance**

- Focus on the semantic guarantees that matter for later review.
- Avoid asserting exact prose sentences unless the sentence itself is the
  contract.

### T008 - Add dependency-contract regression tests

**Purpose**

Prevent the contract from drifting into hidden prerequisites or fake API shapes.

**Required changes**

- Add tests that assert:
  - dependency declarations contain the required fields
  - examples cover profile, nutrition, and supplement use cases
  - the rules explicitly reject implicit opportunistic fallbacks
  - the contract remains domain-focused and does not sprout placeholder REST or
    GraphQL structures

**Constraints**

- The test should reject transport-contract leakage because planning explicitly
  said this mission does not define an API surface.

## Validation Strategy

Primary check for this WP:

```bash
uv run python -m pytest tests/test_profile_intake_contracts.py -q
```

Expected outcomes:

- The contract artifacts parse and stay aligned.
- The one-home mapping is enforceable.
- Hidden prerequisite and fake-API drift fail loudly.

## Definition Of Done

- A dedicated contract-validation test file exists.
- The test suite enforces the contract's load-bearing semantics rather than mere
  formatting.
- Later reviewers can rely on failing tests instead of arguing from intent.

## Risks And Watchouts

- The easiest mistake is writing snapshot tests that freeze wording instead of
  behavior.
- Another common mistake is to let the tests infer a storage shape from the
  contract even though the contract intentionally stays storage-agnostic.

## Reviewer Guidance

Ask whether the tests would actually catch the failure modes the planning phase
was worried about:

1. custom conventions sneaking in,
2. overlap cases being silently collapsed,
3. undeclared prerequisites being normalized after the fact.

If the answer is no, the harness is too weak.

## Activity Log

- 2026-05-27T12:27:28Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T12:42:06Z – claude:opus:implementer:implementer – shell_pid=47453 – Started implementation via action command
- 2026-05-27T12:47:02Z – claude:opus:implementer:implementer – shell_pid=47453 – Ready for review
