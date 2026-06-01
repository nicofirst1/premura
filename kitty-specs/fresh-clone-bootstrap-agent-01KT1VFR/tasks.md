# Tasks: Fresh Clone Bootstrap Agent

**Input**: Design documents from `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/`  
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/bootstrap-cli-contract.md`, `quickstart.md`  
**Branch Contract**: Planning/base branch `master`; final merge target `master`.

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add acceptance-first bootstrap core tests for report states and idempotent local actions. | WP01 |  | [D] |
| T002 | Create the bootstrap report model for runs, checks, actions, skill state, and summary. | WP01 |  | [D] |
| T003 | Implement prerequisite classification for local project environment, external blockers, and optional capabilities. | WP01 |  | [D] |
| T004 | Implement local project dependency action orchestration with injectable command runner boundaries. | WP01 |  | [D] |
| T005 | Implement skill setup integration through the existing skill materialization helper. | WP01 |  | [D] |
| T006 | Implement final summary calculation and setup-only safety guards in the core service. | WP01 |  | [D] |
| T007 | Add acceptance-first CLI tests for `hpipe bootstrap` command registration and output. | WP02 |  | [D] |
| T008 | Register `hpipe bootstrap` on the existing Typer app. | WP02 |  | [D] |
| T009 | Format bootstrap reports as concise terminal output with blockers, warnings, local actions, and reload guidance. | WP02 |  | [D] |
| T010 | Map bootstrap summary status to exit codes. | WP02 |  | [D] |
| T011 | Add installed-console-script coverage for `hpipe bootstrap` invocation. | WP02 |  | [D] |
| T012 | Verify command safety through CLI-level tests that no health-data operation is invoked. | WP02 |  | [D] |
| T013 | Update the root README fresh-clone path to route agents and humans to `hpipe bootstrap`. | WP03 | [P] |
| T014 | Update contributor setup guidance so development setup and bootstrap behavior stay aligned. | WP03 | [P] |
| T015 | Update shipped-state/operations docs after the command exists. | WP03 | [P] |
| T016 | Add documentation checks or lightweight assertions for the new bootstrap command references. | WP03 |  |
| T017 | Record final validation evidence and scope boundaries in the mission quickstart/docs. | WP03 |  |

## Work Package Overview

| WP | Title | Priority | Dependencies | Subtasks | Prompt |
|---|---|---|---|---:|---|
| WP01 | Bootstrap Core Service | P1 | None | 6 | `tasks/WP01-bootstrap-core-service.md` |
| WP02 | CLI Command Surface | P1 | WP01 | 6 | `tasks/WP02-cli-command-surface.md` |
| WP03 | Documentation and Handoff Routing | P2 | WP02 | 5 | `tasks/WP03-documentation-and-handoff-routing.md` |

## WP01 - Bootstrap Core Service

**Goal**: Build the reusable bootstrap service/report layer that can classify setup state, perform safe local actions, install/verify bundled skills, and produce a final handoff summary without touching health data.  
**Priority**: P1  
**Independent Test**: Core tests can drive `premura.bootstrap` with fake command runners and temporary project roots, without invoking the CLI.  
**Dependencies**: None.  
**Estimated Prompt Size**: ~360 lines.

### Included Subtasks

- [x] T001 Add acceptance-first bootstrap core tests for report states and idempotent local actions. (WP01)
- [x] T002 Create the bootstrap report model for runs, checks, actions, skill state, and summary. (WP01)
- [x] T003 Implement prerequisite classification for local project environment, external blockers, and optional capabilities. (WP01)
- [x] T004 Implement local project dependency action orchestration with injectable command runner boundaries. (WP01)
- [x] T005 Implement skill setup integration through the existing skill materialization helper. (WP01)
- [x] T006 Implement final summary calculation and setup-only safety guards in the core service. (WP01)

### Implementation Sketch

1. Start with `tests/test_bootstrap_core.py` and write failing tests for the success, blocked, partial, and idempotent states from `data-model.md`.
2. Add `src/premura/bootstrap.py` with small typed records and a service entry point that accepts a project root plus injectable local-action runners.
3. Keep ordinary setup failures as report data, not unhandled exceptions.
4. Reuse `skills.install_skills()` for skill materialization and convert its result into reload guidance.
5. Ensure no core path calls ingest, run-monthly, upload, MCP analytical tools, or warehouse writes.

### Parallel Opportunities

WP01 is foundational. WP02 consumes the service surface produced here. While WP01 runs, WP03 can draft docs only if it does not claim shipped behavior prematurely, but final docs wait for the CLI behavior.

### Risks

- The service may become a second `ops/bootstrap.sh`. Keep it a small agent-facing report/convergence layer.
- Local dependency setup may be hard to test if it shells out directly. Use injectable command runner boundaries.
- Do not make optional upload readiness a required bootstrap blocker.

## WP02 - CLI Command Surface

**Goal**: Expose the core bootstrap service as `hpipe bootstrap`, with concise agent-readable output, correct exit codes, installed console-script coverage, and CLI-level setup-only safety tests.  
**Priority**: P1  
**Independent Test**: CLI tests drive the Typer app and installed console script, asserting output and exit codes.  
**Dependencies**: Depends on WP01.  
**Estimated Prompt Size**: ~380 lines.

### Included Subtasks

- [x] T007 Add acceptance-first CLI tests for `hpipe bootstrap` command registration and output. (WP02)
- [x] T008 Register `hpipe bootstrap` on the existing Typer app. (WP02)
- [x] T009 Format bootstrap reports as concise terminal output with blockers, warnings, local actions, and reload guidance. (WP02)
- [x] T010 Map bootstrap summary status to exit codes. (WP02)
- [x] T011 Add installed-console-script coverage for `hpipe bootstrap` invocation. (WP02)
- [x] T012 Verify command safety through CLI-level tests that no health-data operation is invoked. (WP02)

### Implementation Sketch

1. Add failing CLI tests before touching `src/premura/cli.py`.
2. Register the command under the existing Typer app and delegate to `premura.bootstrap` rather than embedding setup logic in the CLI function.
3. Format output so a weaker agent can distinguish ready, partial, and blocked states without hidden logs.
4. Treat blocked required prerequisites as non-zero and ready/partial-with-only-optional-warnings as zero only if normal operation is safe.
5. Add installed-entry-point coverage similar to existing `install-skills` tests.

### Parallel Opportunities

WP02 depends on WP01 for the service contract. Documentation wording in WP03 can proceed after WP02's command name and output semantics are stable.

### Risks

- CLI tests that patch internals too heavily can miss real entry-point failures. Include subprocess coverage where entry-point wiring matters.
- Output can become too verbose. Keep the success path under the 200-line NFR.
- Do not accidentally make bootstrap run private health-data operations during verification.

## WP03 - Documentation and Handoff Routing

**Goal**: Make the fresh-clone path discoverable from root/contributor/operations docs and record validation evidence without duplicating long setup policy everywhere.  
**Priority**: P2  
**Independent Test**: Documentation checks can assert key command references and boundary language.  
**Dependencies**: Depends on WP02.  
**Estimated Prompt Size**: ~300 lines.

### Included Subtasks

- [ ] T013 Update the root README fresh-clone path to route agents and humans to `hpipe bootstrap`. (WP03)
- [ ] T014 Update contributor setup guidance so development setup and bootstrap behavior stay aligned. (WP03)
- [ ] T015 Update shipped-state/operations docs after the command exists. (WP03)
- [ ] T016 Add documentation checks or lightweight assertions for the new bootstrap command references. (WP03)
- [ ] T017 Record final validation evidence and scope boundaries in the mission quickstart/docs. (WP03)

### Implementation Sketch

1. Update root docs as routers: name `hpipe bootstrap`, state when to use it, and point deeper rather than duplicating the implementation contract.
2. Keep contributor setup aligned with the new path while preserving existing development validation commands.
3. Update operations/status docs only once WP02 has made the command real.
4. Add small docs assertions where existing tests already protect command/doc wiring, or create a narrow test if no suitable place exists.
5. Update mission quickstart with actual validation commands/evidence from implementation.

### Parallel Opportunities

README and CONTRIBUTING edits are parallel-safe with code WPs in file ownership terms, but final wording should wait for WP02's actual command behavior.

### Risks

- Root docs can become repetitive. Keep them as routers.
- Documentation must not imply bootstrap ingests data or answers health questions.
- Do not claim install success before the code and tests support it.
