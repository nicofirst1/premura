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
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "49168"
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

## Decision Matrix

Use WP01's recommendation exactly:

### If WP01 says `adopt`

Implement the additional target described in WP01. Keep it additive. Existing callers of `install_skills(target_root)` should still get the Claude-style install behavior.

If a function signature change is needed, prefer a backward-compatible optional parameter only if tests prove current CLI behavior still works. Do not add configuration files or new CLI flags unless WP01 explicitly justifies them.

### If WP01 says `defer`

Do not implement additional target support. Add only tests or validation needed to prove the new skill is installed through the existing path. The handoff should explain why the extra home is deferred.

### If WP01 says `reject`

Do not implement additional target support. Keep the skill content portable by standard format, but do not write files to unsupported homes. The handoff should explain what evidence led to rejection.

## Installer Behavior To Preserve

Existing behavior matters more than new target support. Preserve:

- discovering bundled skill directories by `SKILL.md`
- copying sibling resource files and directories
- idempotent second runs
- sha256 skip behavior where currently present
- CLI command `hpipe install-skills`
- writing the existing parser-generator skill as before

If changing `install_skills()` makes any existing install test fail, fix the regression rather than updating tests to weaker expectations.

## Public Test Examples

Tests should create a temporary target root, call `install_skills(tmp_path)`, and inspect output files. Avoid relying on private helper names.

Useful assertions:

- `tmp_path/.claude/skills/research-trace-audit/SKILL.md` exists
- `AUDIT_RUBRIC.md` and `fixtures/` are copied if the installer copies resources recursively
- second run returns no duplicate writes or preserves idempotent behavior
- adopted additional home contains the same skill content if WP01 said adopt

If the current installer does not copy non-`SKILL.md` sibling resources, stop and assess whether that is a blocker for this skill. The skill requires `AUDIT_RUBRIC.md` and fixtures to be bundled resources.

## Coordination With WP03

This WP depends on `SKILL.md` existing. If WP03 has not landed, do not fake an install target. The installer discovers directories by `SKILL.md`; without it, verification is meaningless.

Do not edit `SKILL.md` here. If installation reveals packaging requirements that require changing `SKILL.md`, coordinate with the owner of WP03 rather than silently crossing ownership.

## Definition of Done

- The new skill installs to `.claude/skills/research-trace-audit/SKILL.md`.
- Any additional installer target exactly follows WP01's adopt recommendation.
- Public-interface tests cover changed installer behavior.
- Deferred or rejected targets are explicitly noted in handoff.

## Reviewer Guidance

Reject if the WP implements a target WP01 did not recommend adopting, if tests inspect internals instead of output files, or if existing `.claude/skills/` behavior regresses.

## Activity Log

- 2026-05-31T16:55:54Z – claude:opus:python-implementer:implementer – shell_pid=42555 – Started implementation via action command
- 2026-05-31T17:03:06Z – claude:opus:python-implementer:implementer – shell_pid=42555 – Ready for review: verify-only per WP01 (OpenCode/multi-home installer rejected); existing single-home install_skills() bundles SKILL.md + AUDIT_RUBRIC.md + fixtures/*.json recursively with sha256 idempotency; regression test added; full suite 637 passed
- 2026-05-31T17:04:05Z – claude:opus:python-reviewer:reviewer – shell_pid=49168 – Started review via action command
- 2026-05-31T17:07:36Z – claude:opus:python-reviewer:reviewer – shell_pid=49168 – Review passed: verify-only impl honors WP01's REJECT of OpenCode/multi-home installer (research explicitly forbids test_install_skills_opencode_home.py). install_skills() unchanged (empty diff). New test_install_skills_research_trace_audit.py calls public install_skills(tmp_path), asserts SKILL.md+AUDIT_RUBRIC.md+fixtures/*.json materialize under .claude/skills/research-trace-audit/ and sha256 idempotency on 2nd run; assertions match installer reality (_iter_skill_files recurses subdirs, confirmed by reading both). Filename deviation (research-trace-audit vs owned multi-home) is justified+documented per WP01 reject. Scope clean (only new test file). 2 new tests pass; full suite 637 passed; ruff clean+format-clean; mypy import-untyped note is pre-existing pattern, not new drift.
- 2026-05-31T17:14:22Z – claude:opus:python-reviewer:reviewer – shell_pid=49168 – Done override: Mission merged to master (52ca5d8)
