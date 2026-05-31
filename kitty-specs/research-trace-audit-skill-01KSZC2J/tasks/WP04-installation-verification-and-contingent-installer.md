---
work_package_id: WP04
title: Installation Verification and Contingent Installer
dependencies:
- WP01
- WP03
requirement_refs:
- FR-003
- FR-004
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T013
- T014
- T015
- T016
history:
- timestamp: '2026-05-31T16:16:44Z'
  agent: openai:gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/skills/
execution_mode: code_change
owned_files:
- src/premura/skills/__init__.py
- tests/test_install_skills_multi_home.py
tags: []
---

# Work Package Prompt: WP04 - Installation Verification and Contingent Installer

## Objective

Verify the new skill installs through the existing Claude-style path. Add another local install target only if WP01's research recommendation says `adopt`.

This WP is intentionally contingent. Do not implement OpenCode-style or other multi-home support merely because it sounds useful; follow the WP01 recommendation.

## Branch Strategy

Planning artifacts were generated on `master`. Completed changes must merge back into `master`. During implementation, Spec Kitty allocates execution worktrees per computed lane from `lanes.json`; do not create your own worktree or branch manually.

Use this command for implementation after WP01 and WP03 are done:

```bash
spec-kitty agent action implement WP04 --agent <name>
```

## Authoritative Context

Read these before editing:

- `kitty-specs/research-trace-audit-skill-01KSZC2J/research/wp0-skill-research.md`
- `src/premura/skills/__init__.py`
- `src/premura/cli.py`
- existing install-skills tests in `tests/test_skeleton.py`
- `src/premura/skills/research-trace-audit/SKILL.md`

## Owned Files

You may create or modify only:

- `src/premura/skills/__init__.py`
- `tests/test_install_skills_multi_home.py`

Do not edit existing `tests/test_skeleton.py`; add focused new tests if needed.

## Detailed Guidance

### T013 - Verify existing Claude-style install path discovers the new skill

The existing `install_skills(target_root)` walks bundled skill directories that contain `SKILL.md` and materializes them under `target_root/.claude/skills/`.

Add a public-interface test if needed to confirm the new `research-trace-audit` skill is discovered and copied by the existing function.

This verification may not require source changes if the current installer already works. If so, keep code unchanged and rely on the test or documented validation.

### T014 - If WP01 recommends adopt, extend installer support

Read the exact recommendation field in `wp0-skill-research.md`.

If it says `adopt`, implement the smallest additive installer change that supports the selected additional local home. Preserve idempotency and existing `.claude/skills/` behavior.

If it says `defer` or `reject`, do not change `install_skills()` for that target. In that case, this subtask is satisfied by explaining in the WP handoff that no code change was correct.

### T015 - Add public-interface tests for any installer extension

If code changes, test through the public `install_skills(target_root)` function and observable on-disk results. Do not test private helpers as the primary proof.

Tests should cover:

- existing `.claude/skills/research-trace-audit/SKILL.md` output
- any adopted additional home output
- idempotent second run, preserving existing sha256 skip behavior when practical
- no network access

If no extension is adopted, tests should still prove the new skill installs through the existing path.

### T016 - Document install verification outcomes

In the implementation handoff, state:

- which targets are supported
- which targets are deferred or rejected and why
- which command or test verifies each supported target

Do not write this into live product docs here; WP05 owns live docs.

## Validation

Run targeted tests for installer behavior. If Python changed, run formatting and lint checks for changed Python scope.

Recommended checks:

```bash
uv run pytest tests/test_install_skills_multi_home.py -q
uv run ruff check src/premura/skills tests/test_install_skills_multi_home.py
uv run ruff format --check src/premura/skills tests/test_install_skills_multi_home.py
```

If no new test file is needed, run the existing installer tests that prove the behavior.

## Definition of Done

- The new skill installs to `.claude/skills/research-trace-audit/SKILL.md`.
- Any additional installer target exactly follows WP01's adopt recommendation.
- Public-interface tests cover changed installer behavior.
- Deferred or rejected targets are explicitly noted in handoff.

## Reviewer Guidance

Reject if the WP implements a target WP01 did not recommend adopting, if tests inspect internals instead of output files, or if existing `.claude/skills/` behavior regresses.
