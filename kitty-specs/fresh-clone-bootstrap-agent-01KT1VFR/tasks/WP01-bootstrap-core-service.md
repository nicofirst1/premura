---
work_package_id: WP01
title: Bootstrap Core Service
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-fresh-clone-bootstrap-agent-01KT1VFR
base_commit: b4c8b8b7fc23c8a4437c9367606d734755aa7c9f
created_at: '2026-06-01T15:19:02.439570+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
shell_pid: "84039"
agent: "claude:opus:reviewer:reviewer"
history:
- timestamp: '2026-06-01T15:11:47Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/bootstrap.py
execution_mode: code_change
owned_files:
- src/premura/bootstrap.py
- tests/test_bootstrap_core.py
tags: []
---

# Work Package Prompt: WP01 - Bootstrap Core Service

## Implement Command

```bash
spec-kitty agent action implement WP01 --agent <name> --mission fresh-clone-bootstrap-agent-01KT1VFR
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Build the bootstrap service layer that powers the later `hpipe bootstrap` CLI command. This WP owns the internal report model, setup-state classification, safe local action orchestration, skill setup integration, and setup-only safety boundaries. It must not register the CLI command; WP02 owns `src/premura/cli.py`.

## Authoritative Inputs

- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/spec.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/plan.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/data-model.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/contracts/bootstrap-cli-contract.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/research.md`
- `.kittify/charter/charter.md`
- Existing helper: `src/premura/skills/__init__.py`

## Owned Files

- `src/premura/bootstrap.py`
- `tests/test_bootstrap_core.py`

Do not edit `src/premura/cli.py`; WP02 owns command registration and terminal formatting. Do not edit README/CONTRIBUTING/status docs; WP03 owns docs.

## Implementation Notes

The core service is the contract between setup mechanics and the CLI. Keep it boring and data-shaped: callers should get a report they can format, test, and reason about. Avoid burying decisions in printed strings. The CLI can decide how to render, but it should not need to reclassify blockers or infer reload guidance.

Recommended public shape:

- A single orchestration function such as `run_bootstrap(project_root: Path, ...) -> BootstrapRun`.
- A command-runner argument or protocol for local install actions, so tests do not invoke real setup commands.
- A skill installer argument or wrapper defaulting to `skills.install_skills`, so tests can simulate written vs unchanged skills.
- Small status constants or enums. If you use strings, keep them centralized and covered by tests.

Keep the implementation local and inspectable. Do not add background jobs, daemon behavior, a hidden cache, or a persistent setup database. The report returned from a run is enough for this mission.

## Required Subtasks

### T001: Add acceptance-first bootstrap core tests

Purpose: Define the service behavior before implementation.

Guidance:
- Create `tests/test_bootstrap_core.py` first.
- Drive the public surface of `premura.bootstrap`, not private helper functions.
- Use temporary project roots and fake command runners; do not run real dependency installation in unit tests.
- Cover at least these cases:
  - Fresh supported checkout with local actions allowed returns a ready or fixed summary.
  - Already prepared checkout returns no-change/idempotent action results.
  - Missing external/system prerequisite returns a blocked check with `local_action_allowed=False` and a next action.
  - Optional upload capability is a warning, not a required blocker.
  - Skill setup reports installed/unchanged state plus reload guidance.
  - No path invokes health-data operations.

Validation:
- Tests fail before `premura.bootstrap` exists.
- Assertions are on report objects or documented public functions/classes.

### T002: Create the bootstrap report model

Purpose: Give the CLI a stable setup-state object to format.

Guidance:
- Add `src/premura/bootstrap.py`.
- Define small typed records for the entities from `data-model.md`: `BootstrapRun`, `BootstrapCheck`, `BootstrapAction`, `SkillSetupState`, and `BootstrapSummary` or equivalent names.
- Keep closed status vocabularies small and explicit: ready/partial/blocked for summary; pass/fixed/blocked/warning/skipped for checks; changed/no_change/failed/not_attempted for actions.
- Include enough fields for the CLI to print blockers, warnings, local actions, reload guidance, and next step without recomputing status.
- Prefer simple dataclasses or typed structures; avoid a new dependency.

Validation:
- Tests can instantiate or obtain reports with stable fields.
- The report model distinguishes blockers from optional warnings.

### T003: Implement prerequisite classification

Purpose: Decide what bootstrap can fix locally and what must be reported.

Guidance:
- Add a public service function such as `run_bootstrap(...)` or a small `Bootstrapper` object.
- Classify setup areas into the categories from `data-model.md`: project environment, command availability, skill setup, optional capability, external prerequisite.
- Required install readiness should not depend on private health data, `data/inbox/`, `data/raw/`, or an existing warehouse.
- System-level prerequisites that cannot be handled safely in the project environment must become blocked checks with exact next actions.
- Optional upload capability must not block local install readiness.

Validation:
- A test proves an absent optional upload capability does not make the summary blocked.
- A test proves a required external prerequisite produces a blocker.

### T004: Implement local project dependency action orchestration

Purpose: Let bootstrap install or verify local project dependencies without uncontrolled global mutation.

Guidance:
- Use an injectable command runner boundary for local setup commands so tests can simulate success/failure.
- Represent each attempted local action as a `BootstrapAction`.
- Ordinary command failure should produce a failed action and blocked summary, not an uncaught exception with a traceback.
- Keep the exact command choice close to existing repo setup guidance. If implementation chooses to call the existing local dependency setup command, record that in the action detail.
- Do not call package managers that mutate the system globally unless the action is explicitly classified as external and reported rather than run.

Validation:
- Tests simulate a successful local dependency action and a failed one.
- Failure output has a next action and does not hide behind a traceback.

### T005: Implement skill setup integration

Purpose: Reuse the existing bundled skill materialization path.

Guidance:
- Call or wrap `skills.install_skills(project_root)` rather than creating a second installer.
- Convert the returned list of written paths into `SkillSetupState`.
- Include the destination path and whether files changed.
- Always produce reload guidance. If skill files changed, prefer `reload required` or `reload recommended`; if unchanged, `reload not required` is acceptable unless implementation cannot know visibility.

Validation:
- Tests monkeypatch or fake `skills.install_skills` and assert installed/unchanged states.
- Tests assert reload guidance is present on every run.

### T006: Implement summary calculation and setup-only safety guards

Purpose: Ensure the service produces an honest final handoff and never crosses into runtime health operation.

Guidance:
- Compute summary status from checks/actions: blocked if required blockers remain, partial for optional warnings or visibility caveats, ready when required checks pass/fix.
- The next step should be a safe setup/operation handoff, not an automatic ingest or analysis action.
- Add constants or tests that guard against invoking health-data commands from this service.
- Do not import or call parser ingest, warehouse query, MCP analytical dispatch, upload, or run-monthly functions.

Validation:
- Tests cover ready, partial, and blocked summaries.
- Tests assert the core service does not call forbidden health-data operation hooks.

## Test Strategy

Use tests to pin the behavior at the service boundary before implementation:

- `test_bootstrap_ready_when_local_actions_succeed`: fake local dependency action succeeds, skills are installed or unchanged, required checks pass, summary is ready or fixed.
- `test_bootstrap_idempotent_when_everything_current`: fake command runner reports no change and skill installer writes nothing; summary remains ready and actions are no-change.
- `test_bootstrap_blocks_external_prerequisite_without_mutating_system`: a required system-level prerequisite is absent; the report includes a blocker with a next action and no local action is attempted.
- `test_optional_upload_is_warning_not_blocker`: optional upload/rclone-like capability is absent; summary is not blocked solely for that reason.
- `test_reload_guidance_is_always_present`: every summary has explicit reload guidance.
- `test_core_service_does_not_touch_health_data_operations`: forbidden hooks are unavailable or monkeypatched to fail, and the service still produces a setup report.

Prefer observable report fields over implementation details. If a helper is private, tests should not import it.

## Validation Commands

Run the focused tests first:

```bash
uv run python -m pytest -q tests/test_bootstrap_core.py --tb=short
```

Then run changed-scope static checks before handoff:

```bash
uv run ruff check src/premura/bootstrap.py tests/test_bootstrap_core.py
uv run ruff format --check src/premura/bootstrap.py tests/test_bootstrap_core.py
uv run mypy src/premura/bootstrap.py
```

If `mypy` needs a broader package context, run the smallest broader command that includes the new module and call that out in the WP activity log.

## Risk Checklist

- The service must not create or initialize a health warehouse as part of setup readiness.
- The service must not require real `data/` contents.
- The service must not treat optional upload setup as required install readiness.
- The service must not rely on a currently active Claude/OpenCode session seeing newly copied skill files; it must report reload guidance honestly.
- The service must make failed local commands understandable to a weaker agent without requiring hidden logs.

## Definition of Done

- `src/premura/bootstrap.py` exists with a documented public service/report surface.
- `tests/test_bootstrap_core.py` covers success, blocked, idempotent, skill, optional-warning, and setup-only safety behavior.
- Core tests pass with `uv run python -m pytest -q tests/test_bootstrap_core.py --tb=short`.
- No CLI command is registered in this WP.

## Reviewer Guidance

- Reject if the service shells out directly in tests instead of using an injectable boundary.
- Reject if missing optional upload capability blocks bootstrap readiness.
- Reject if the service imports or calls health-data operation paths.
- Verify ordinary setup failures are report data, not uncaught tracebacks.

## Activity Log

- 2026-06-01T15:19:03Z – claude:opus:implementer:implementer – shell_pid=78065 – Assigned agent via action command
- 2026-06-01T15:24:39Z – claude:opus:implementer:implementer – shell_pid=78065 – Ready for review
- 2026-06-01T15:25:05Z – claude:opus:reviewer:reviewer – shell_pid=84039 – Started review via action command
- 2026-06-01T15:26:22Z – claude:opus:reviewer:reviewer – shell_pid=84039 – Review passed: injectable command_runner/skill_installer/tool_probe boundaries (no real shell-outs); optional rclone is warning not blocker; only imports premura.skills (no ingest/warehouse/MCP/upload/run-monthly); failed command -> failed action + blocked summary, no traceback; all 5 data-model entities with closed vocabularies; reload_guidance on every run; readiness independent of data/inbox|raw|warehouse; cli.py untouched; pytest 10 passed, ruff check/format clean, mypy clean.
