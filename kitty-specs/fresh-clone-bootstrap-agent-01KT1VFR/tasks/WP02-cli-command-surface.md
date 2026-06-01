---
work_package_id: WP02
title: CLI Command Surface
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-005
- FR-007
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
agent: "claude:opus:implementer:implementer"
shell_pid: "86250"
history:
- timestamp: '2026-06-01T15:11:47Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/cli.py
execution_mode: code_change
owned_files:
- src/premura/cli.py
- tests/test_bootstrap_cli.py
tags: []
---

# Work Package Prompt: WP02 - CLI Command Surface

## Implement Command

```bash
spec-kitty agent action implement WP02 --agent <name> --mission fresh-clone-bootstrap-agent-01KT1VFR
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Expose WP01's bootstrap service as `hpipe bootstrap`. The command should be easy for an agent to discover and should print a concise handoff that distinguishes ready, partial, and blocked states. It must map readiness to exit codes and preserve the setup-only boundary.

## Authoritative Inputs

- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/contracts/bootstrap-cli-contract.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/data-model.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/quickstart.md`
- WP01 public surface in `src/premura/bootstrap.py`
- Existing CLI style in `src/premura/cli.py`
- Existing console-script tests in `tests/test_skeleton.py` for style only
- `.kittify/charter/charter.md`

## Owned Files

- `src/premura/cli.py`
- `tests/test_bootstrap_cli.py`

Do not edit `src/premura/bootstrap.py`; WP01 owns service behavior. Do not edit root docs; WP03 owns documentation.

## Implementation Notes

The CLI should be a thin presentation layer over WP01's service. The key review question is whether a weaker agent can run one command and know what happened. Do not optimize for a pretty table at the expense of branchable status. If Rich tables make tests brittle, keep the output simple and stable.

Recommended command behavior:

- `hpipe bootstrap` runs install-and-verify by default.
- It prints an overall result near the top and a final next step near the bottom.
- It separates required blockers from optional warnings.
- It always prints reload guidance.
- It exits non-zero when required blockers remain.

Avoid adding flags unless implementation discovers a concrete need. A structured-output flag is optional, not required by this WP. If you add one, keep the default human/agent-readable output concise.

## Required Subtasks

### T007: Add acceptance-first CLI tests

Purpose: Lock the observable command behavior before implementation.

Guidance:
- Create `tests/test_bootstrap_cli.py` first.
- Use Typer `CliRunner` for command registration and formatting tests.
- Monkeypatch the WP01 service at its public boundary so CLI tests focus on CLI behavior rather than local dependency installation.
- Cover:
  - `bootstrap` appears in registered commands.
  - ready summary exits 0 and includes local actions plus reload guidance.
  - partial summary exits 0 only when remaining items are warnings/visibility guidance, not required blockers.
  - blocked summary exits non-zero and prints blocker plus next action.
  - success output is concise enough to satisfy the 200-line NFR.

Validation:
- Tests fail before command registration.
- Tests assert exact high-value phrases without overfitting the whole Rich layout.

### T008: Register `hpipe bootstrap`

Purpose: Add the explicit command the user requested.

Guidance:
- Add a Typer command named `bootstrap` to `src/premura/cli.py`.
- Keep the function thin: call WP01's bootstrap service and format its report.
- Do not put local dependency orchestration directly in the CLI function.
- Include a help string that makes clear this is fresh-clone/setup readiness, not ingest or analysis.

Validation:
- `CliRunner` help output or registered command inspection includes `bootstrap`.

### T009: Format bootstrap reports for terminal handoff

Purpose: Make output useful to weaker agents and humans.

Guidance:
- Print an overall status.
- Print local actions changed/no-change.
- Print blockers separately from optional warnings.
- Print reload guidance on every run.
- Print one safe next step.
- Keep ordinary success output below 200 terminal lines.
- Avoid private paths unless they are setup paths the user needs to see; never print secrets or health-data excerpts.

Validation:
- Tests assert blockers and warnings are distinguishable.
- Tests assert reload guidance appears for ready, partial, and blocked examples.

### T010: Map summary status to exit codes

Purpose: Let agents branch reliably on success/failure.

Guidance:
- Exit 0 for ready.
- Exit non-zero for blocked required prerequisites.
- For partial, follow the contract: if normal operation is safe and only optional warnings remain, exit 0; if required readiness is absent, exit non-zero.
- Keep this mapping visible in tests.

Validation:
- Tests cover ready, partial-warning, and blocked cases.

### T011: Add installed-console-script coverage

Purpose: Catch the class of packaging/entry-point failure that app registration tests miss.

Guidance:
- Add subprocess-style coverage in `tests/test_bootstrap_cli.py` if practical, or use the same pattern as existing console-script tests.
- Invoke the installed `hpipe` binary where available.
- If the binary is not installed in the test environment, skip with a clear message rather than fail unrelated environments.
- Use a temporary project root and monkeypatch/environment controls where possible to avoid real dependency installation.

Validation:
- Installed `hpipe bootstrap` can be invoked and returns controlled output in the test setup.

### T012: Verify setup-only safety at the CLI layer

Purpose: Make the boundary visible to reviewers.

Guidance:
- Add CLI-level tests proving the command delegates only to bootstrap setup behavior.
- Monkeypatch forbidden CLI operation functions (`ingest`, `run_monthly`, upload path, MCP analytical calls if reachable) to fail if called, then run bootstrap.
- The command should not require real `data/inbox`, private `data/raw`, or a real warehouse.

Validation:
- Tests fail if bootstrap invokes a health-data operation path.
- Tests pass with an empty temporary project root.

## Test Strategy

Start with `tests/test_bootstrap_cli.py` and drive the command through `CliRunner`:

- `test_cli_registers_bootstrap_command`: inspect `cli.app.registered_commands` or help output.
- `test_cli_ready_summary_prints_actions_and_reload_guidance`: fake a ready `BootstrapRun` and assert exit 0 plus high-value output phrases.
- `test_cli_blocked_summary_exits_nonzero`: fake a blocked summary and assert non-zero exit plus blocker and next action.
- `test_cli_partial_optional_warning_can_exit_zero`: fake a partial summary with optional-only warnings and assert the output calls it out without treating it as a required blocker.
- `test_cli_output_stays_concise`: count output lines for success path and keep below the NFR threshold.
- `test_cli_does_not_invoke_health_operations`: monkeypatch forbidden CLI functions to raise if called.

For installed-console-script coverage, follow the existing pattern in `tests/test_skeleton.py`: locate `Path(sys.executable).parent / "hpipe"`, skip if absent, and invoke the command in a temp root with the bootstrap service faked or controlled enough to avoid real dependency installation.

## Validation Commands

Run focused CLI tests first:

```bash
uv run python -m pytest -q tests/test_bootstrap_cli.py --tb=short
```

If you extend entry-point coverage in a way that touches existing skeleton checks, also run:

```bash
uv run python -m pytest -q tests/test_skeleton.py --tb=short
```

Run changed-scope static checks:

```bash
uv run ruff check src/premura/cli.py tests/test_bootstrap_cli.py
uv run ruff format --check src/premura/cli.py tests/test_bootstrap_cli.py
uv run mypy src/premura/cli.py
```

## Risk Checklist

- Do not catch all exceptions and report false success.
- Do not hide required blockers among optional warnings.
- Do not print long subprocess logs on the success path.
- Do not make command output depend on private health-data files existing.
- Do not call `hpipe doctor` blindly if its optional-upload checks would make a fresh install look failed.

## Definition of Done

- `hpipe bootstrap` is registered and visible from the CLI.
- CLI tests cover ready, partial, blocked, concise output, reload guidance, and setup-only safety.
- Installed-console-script coverage exists or is intentionally skipped only when the binary is unavailable.
- Changed-scope validation includes `uv run python -m pytest -q tests/test_bootstrap_cli.py --tb=short`.

## Reviewer Guidance

- Reject if `src/premura/cli.py` grows a second copy of setup orchestration instead of delegating to `premura.bootstrap`.
- Reject if blocked prerequisites exit 0.
- Reject if output buries required blockers among optional warnings.
- Reject if command verification ingests data, touches private warehouse rows, or attempts upload.

## Activity Log

- 2026-06-01T15:26:56Z – claude:opus:implementer:implementer – shell_pid=86250 – Started implementation via action command
- 2026-06-01T15:31:17Z – claude:opus:implementer:implementer – shell_pid=86250 – Ready for review
