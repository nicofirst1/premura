# Implementation Plan: Fresh Clone Bootstrap Agent

**Branch**: `master` | **Date**: 2026-06-01 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/spec.md`  
**Mission**: `fresh-clone-bootstrap-agent-01KT1VFR` (`01KT1VFR88AWTHYDGN7VBTX449`)

## Summary

Add an explicit agent-facing bootstrap CLI command, planned as `hpipe bootstrap`, that an agent can run from a fresh Premura checkout. The command installs or verifies local project dependencies where the repo can safely do so, verifies required project skills/setup, reports system-level blockers without uncontrolled global mutation, and gives reload guidance before normal Premura operation. It stays setup-only: no health-data ingest, no private warehouse queries, and no runtime operating-role orchestration.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing Typer/Rich CLI stack, existing project setup guidance, existing `skills.install_skills()` helper, existing `doctor` checks where reusable. No new runtime dependency is planned.  
**Storage**: No warehouse storage. The command may create/update local project environment artifacts and `.claude/skills/` files through existing supported mechanisms.  
**Testing**: pytest with Typer `CliRunner` and subprocess-style console-script checks where the behavior depends on installed entry points. Use test-first acceptance around observable CLI output and exit codes.  
**Target Platform**: Primary support remains macOS local checkout, matching the charter. The command should report unsupported or missing system prerequisites rather than attempting broad cross-platform setup.  
**Project Type**: Single Python project with a Typer CLI.  
**Performance Goals**: Success-path output fits within 200 terminal lines; successful bootstrap under 10 minutes on the supported local workstation when network dependency downloads are available.  
**Constraints**: Local-first and offline by default after dependency installation; no health-data ingest or analysis during bootstrap; no uncontrolled system-wide package management; root docs route to the command instead of duplicating long setup policy.  
**Scale/Scope**: One explicit bootstrap command plus the smallest supporting service/data shapes, tests, and docs needed for a fresh-clone agent handoff.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter Principle | Status | Notes |
|---|---|---|
| Agent-first, human-beneficiary posture | PASS | The feature exists so an agent can prepare a repo for the human without inventing setup steps. |
| Local-first and offline by default | PASS | Bootstrap may download/install project dependencies during setup, but normal operation remains local; runtime health-data paths are not invoked. |
| No PHI in logs, tests, or commits | PASS | Bootstrap tests use temporary checkouts and synthetic setup states only. |
| Test-first behavior | PASS | Plan calls for acceptance tests around the CLI before production code. |
| Public-interface testing | PASS | Verification happens through CLI output/exit codes and installed entry points, not private implementation calls. |
| Smallest viable diff | PASS | Add one CLI command and supporting helper rather than a new agent framework. |
| No live personal-data API scraping | PASS | Bootstrap does not ingest or fetch personal health data. |

## Project Structure

### Documentation (this feature)

```text
kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── bootstrap-cli-contract.md
└── tasks.md                  # Created later by /spec-kitty.tasks, not by this command
```

### Source Code (repository root)

```text
src/premura/
├── cli.py                    # Register hpipe bootstrap and format output
├── bootstrap.py              # Planned setup/check orchestration helpers
└── skills/__init__.py        # Existing skill materialization helper reused as-is if possible

tests/
├── test_bootstrap_cli.py      # New acceptance tests for hpipe bootstrap behavior
└── test_skeleton.py          # May extend console-script wiring coverage if needed

README.md                     # Route fresh-clone users/agents to hpipe bootstrap
CONTRIBUTING.md               # Keep contributor setup aligned with bootstrap path
docs/operations/STATUS.md     # Update shipped-state summary only after implementation ships
```

**Structure Decision**: Keep the bootstrap path inside the existing `hpipe` CLI. Add a small `premura.bootstrap` module only if needed to keep `src/premura/cli.py` from becoming a setup-state monolith. Do not create a runtime orchestrator, daemon, or separate agent package in this mission.

## Complexity Tracking

No charter violations are expected. The command touches setup behavior, CLI output, skill installation, and docs, but the scope stays inside one existing CLI surface.

## Phase 0 Research Summary

See [research.md](research.md). The relevant decisions are:

- Use `hpipe bootstrap` as the explicit agent-facing entry point.
- Treat local project dependency setup as a best-effort local project-environment action; report system-level prerequisites separately.
- Reuse `install-skills` behavior and make reload guidance explicit.
- Keep `doctor` as the operator health check and avoid making bootstrap depend on private health data or optional upload setup.

## Phase 1 Design Summary

See [data-model.md](data-model.md) and [contracts/bootstrap-cli-contract.md](contracts/bootstrap-cli-contract.md).

The planned behavior is a small setup report model:

- `BootstrapRun` captures one setup attempt.
- `BootstrapCheck` captures each dependency/skill/readiness check.
- `BootstrapAction` records local actions attempted by the command.
- `BootstrapSummary` gives the final agent handoff: ready, blocked, or partial, with reload guidance.

The CLI contract keeps output human-readable by default and may expose structured output only if implementation chooses to add a low-noise option. Regardless of presentation, the semantics are stable: local actions are separate from external prerequisites, bootstrap never ingests health data, and missing skill visibility produces reload guidance.

## Post-Design Charter Check

| Charter Principle | Status | Notes |
|---|---|---|
| Agent-first | PASS | The contract is written around an agent invoking a single command and reading a handoff summary. |
| Guide, do not enumerate | PASS | Checks are modelled as named setup categories and actions, not a brittle one-off transcript. |
| Local-first / no PHI | PASS | The command has an explicit setup-only boundary and no health-data path. |
| Test-first and public-interface tests | PASS | Contracts call for acceptance tests through CLI exit code/output and subprocess entry-point behavior. |
| Minimal blast radius | PASS | No new stage, no runtime orchestrator, no system-wide mutation by default. |

## Open Risks

| Risk | Mitigation |
|---|---|
| The command could accidentally duplicate `ops/bootstrap.sh` instead of clarifying it. | Reuse documented setup behavior where possible; make `hpipe bootstrap` the agent-facing local install/check wrapper, not a second unrelated setup universe. |
| A bootstrap command may be hard to run before dependencies are installed. | Plan WPs should resolve invocation mechanics explicitly, likely by documenting the minimal first command needed to make `hpipe` available, then using `hpipe bootstrap` for convergence and verification. |
| Skill visibility differs across agents. | Contract requires explicit reload guidance rather than pretending skill installation is visible in the current session. |
| Existing `doctor` currently fails optional upload prerequisites. | Bootstrap should distinguish required install readiness from optional upload readiness so fresh-clone setup does not fail just because optional Drive upload is absent. |

## Ready For Tasks

This plan is ready for `/spec-kitty.tasks`. Do not generate work packages until that command is invoked.
