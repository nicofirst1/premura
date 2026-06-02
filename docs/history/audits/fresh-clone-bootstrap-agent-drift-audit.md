# Drift Audit: Fresh Clone Bootstrap Agent

**Date**: 2026-06-02  
**Auditor**: OpenCode `gpt-5.5`  
**Incident source**: `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/mission-review.md`  
**Mission**: `fresh-clone-bootstrap-agent-01KT1VFR`  
**Verdict under audit**: mission review failed the implementation for DRIFT-1 and DRIFT-2.

## Audit Method

This audit used the audit workflow from the agent audit skill, with one extension.

The normal method is: define the incident, select sources of truth, collect raw evidence, analyze the root cause chain, assess blast radius, and record recommendations. The user already supplied the incident and requested a saved Markdown result, so this audit skipped a blocking interview and recorded the assumptions instead.

Extension added for this audit: **snapshot integrity check**. The current worktree is not identical to the reviewed snapshot: `src/premura/bootstrap.py` is modified, and `mission-review.md` is currently untracked. Therefore, this audit treats `mission-review.md`, the mission artifacts, status events, and the mission merge metadata as the incident record. Current uncommitted code is out of scope except where explicitly noted.

## Audit Brief

**Incident**: A mission intended to let a bootstrap agent set up a fresh clone shipped docs and tests that did not satisfy the fresh-clone promise.  
**Primary drifts**: DRIFT-1, the documented first command depends on an already-installed `hpipe`; DRIFT-2, the bootstrap path did not verify every core readiness surface promised by `FR-003` at the reviewed snapshot.  
**Blast radius**: feature-scoped, with a systemic process risk for future setup missions.  
**Timeframe**: baseline commit `202e76178b43134ec0457f747522c94588d8224e` to mission merge commit `e2c53687cfc2af5016920e223c7945325305657e`, reviewed at `c13a1b7a095652fb6da6bbfaab55eb9176f577ef`.  
**Sources of truth**: `spec.md`, `plan.md`, task files, status events, shipped docs, test files, `pyproject.toml`, and `mission-review.md`.

## Executive Summary

The drift happened because a known bootstrap paradox was recorded as a risk but never converted into a hard work-package acceptance gate. The plan explicitly warned that `hpipe bootstrap` may be hard to run before dependencies are installed, but later tasks and reviews focused on making `hpipe bootstrap` exist after installation rather than proving a fresh clone has a runnable first command.

The second drift happened because the mission split readiness into several terms: local dependency setup, command availability, skill setup, optional upload readiness, and existing `doctor` behavior. During implementation and review, the safety boundary became the dominant check: bootstrap must not ingest, upload, analyze, or require private data. That was necessary, but it displaced the separate promise that bootstrap would verify the core project surfaces needed before normal operation.

The approvals were not careless in the narrow sense: each WP had tests and review evidence. The problem was that the evidence matched the narrower WP framing, not the full mission promise. This is a review-method failure: reviewers accepted local green checks without re-running the primary story from the spec as an end-to-end acceptance test.

## Key Evidence

1. The spec defines a true fresh-clone scenario. `spec.md:12` says the human has "freshly cloned Premura" and asks an agent inside the repo to install it. `spec.md:16` says the checkout has "no project environment prepared."

2. The spec requires one discoverable entry point. `spec.md:35` says the bootstrap path must give an agent "a single documented entry point" for a freshly cloned checkout. `spec.md:82` says the agent should complete setup "without inventing missing steps."

3. The plan knew the exact risk. `plan.md:111-112` says: "A bootstrap command may be hard to run before dependencies are installed," and says WPs should resolve "the minimal first command needed to make `hpipe` available."

4. The plan still chose `hpipe bootstrap` as the public command. `plan.md:9` names the planned command as `hpipe bootstrap`; `plan.md:79` repeats that as the explicit entry point.

5. WP02 weakened the key acceptance check. `tasks/WP02-cli-command-surface.md:151-162` asks for installed-console-script coverage, but `tasks/WP02-cli-command-surface.md:156-158` permits the test to skip if the installed binary is absent.

6. WP03 locked the risky command into docs. `tasks/WP03-documentation-and-handoff-routing.md:99` tells the README to point a fresh clone to `hpipe bootstrap`; `tasks/WP03-documentation-and-handoff-routing.md:112` tells CONTRIBUTING to do the same.

7. The shipped docs did what WP03 asked. `README.md:14-18` says a fresh clone runs one setup command first: `hpipe bootstrap`. `CONTRIBUTING.md:17-19` says the fresh-clone agent-friendly path is one command: `hpipe bootstrap`.

8. `hpipe` is a package console script, not a guaranteed shell command in an unprepared clone. `pyproject.toml:40-43` declares `hpipe`, `premura-mcp`, and `premura-mcp-operator` under `[project.scripts]`.

9. The installed-console-script test did not prove fresh-clone availability. `tests/test_bootstrap_cli.py:472-488` locates the installed `hpipe` next to `sys.executable` and skips if it is absent.

10. The docs guard checked for command presence, not first-command executability. `tests/test_bootstrap_docs.py:25-31` only asserts that README contains `hpipe bootstrap` and `quick start`; `tests/test_bootstrap_docs.py:33-39` only asserts that CONTRIBUTING contains `hpipe bootstrap` plus dev check names.

11. The mission review recorded the same conclusion. `mission-review.md:17-37` classifies DRIFT-1 as HIGH because the documented fresh-clone entry point depends on `hpipe` already existing.

12. `FR-003` promised broader readiness. `spec.md:37` requires verification to report pass/fail for "command availability, ability to start the core project surfaces, and the existing Premura health check surface needed before normal operation."

13. WP01 listed categories that included command availability but its concrete tests narrowed the check set. `tasks/WP01-bootstrap-core-service.md:132-136` names project environment, command availability, skill setup, optional capability, and external prerequisite. `tasks/WP01-bootstrap-core-service.md:189-194` then lists tests for dependency action, idempotency, missing external prerequisite, optional upload, reload guidance, and no health-data operations.

14. WP02 explicitly warned not to call `hpipe doctor` blindly. `tasks/WP02-cli-command-surface.md:218` says not to call `hpipe doctor` blindly if optional upload checks would make a fresh install look failed.

15. The mission review found that readiness verification was narrower than `FR-003`. `mission-review.md:39-55` says the implementation checked dependency sync, skills, and optional `rclone`, but not `hpipe doctor`, `premura-mcp`, `premura-mcp-operator`, or equivalent core surface startup at the reviewed snapshot.

16. WP approvals cited the narrower evidence. `status.events.jsonl:8` approved WP01 with evidence about fakes, optional `rclone`, reload guidance, no health-data directories, and tests. `status.events.jsonl:13` approved WP02 with evidence about CLI presentation, blockers, exit codes, setup-only tripwire, console-script coverage, and green tests. `status.events.jsonl:18` approved WP03 with evidence that docs route fresh clone to `hpipe bootstrap` as setup-only.

17. No review-cycle files were available for deeper review reconstruction. `mission-review.md:110-115` says no review-cycle files were present under the mission `tasks/` directory.

## Root Cause Chain

Known risk in `plan.md` -> work packages translated the risk into command/docs coverage instead of a fresh-clone first-command acceptance gate -> tests and reviews proved `hpipe bootstrap` after installation or when an installed binary exists -> docs told a truly fresh clone to run a command that may not exist yet -> the primary fresh-clone promise failed.

For DRIFT-2:

Broad `FR-003` readiness language -> task-level focus shifted toward safe setup, dependency sync, skill setup, and avoiding optional upload false failures -> concrete tests did not require startup/import verification for all core project surfaces -> WP approvals accepted the narrower readiness evidence -> the reviewed implementation partially satisfied readiness but not the full `FR-003` promise.

## How The Drifts Could Happen

### 1. The risk was visible but not owned

The plan did not miss the bootstrap paradox. It named it directly in `plan.md:111-112`. The failure was that no later artifact made one WP responsible for proving the true first command from an unprepared checkout. Once that risk became a note rather than a required test, it could be bypassed by otherwise reasonable work.

### 2. "Single documented entry point" and "first runnable command" were treated as the same thing

The spec wanted a new agent to find one path. The plan chose `hpipe bootstrap`. The docs then correctly routed users to that command. But the mission needed two separate guarantees: a canonical command after the environment exists, and a minimal invocation that works before the console script exists. Those were collapsed into one phrase: `hpipe bootstrap`.

### 3. The test suite tested the installed state

The installed-console-script test was useful, but it explicitly skips when the binary is missing. That makes sense for ordinary packaging coverage, but it is the wrong shape for a fresh-clone acceptance test. The failure condition for DRIFT-1 is exactly "the binary is missing."

### 4. Documentation tests froze the drift

The docs tests guarded that `hpipe bootstrap` stayed in README and CONTRIBUTING. That prevented accidental deletion, but it also made the incorrect first command look deliberately protected. A docs guard should have checked the fresh-clone precondition too, such as requiring the documented first command to be runnable without an already-installed console script or explicitly documenting the `uv run`/bootstrap-shell pre-step.

### 5. Setup-only safety crowded out readiness verification

The mission correctly emphasized that bootstrap must not touch health data, ingest, upload, or answer health questions. Many tests and review notes focused on that boundary. The problem is that setup-only safety is not the same as operation readiness. `FR-003` required command availability and core surface startup checks, not just absence of unsafe runtime behavior.

### 6. Optional `doctor` behavior created a justified avoidance path

The plan warned that existing `doctor` could fail optional upload prerequisites. WP02 then warned not to call `hpipe doctor` blindly. That was valid, but it needed a replacement readiness definition. Without one, avoiding `doctor` also avoided part of the promised health-check/readiness surface.

### 7. WP reviews validated each slice, not the original primary story

The event log shows each WP was reviewed and approved with relevant evidence. The missing step was a final mission-level acceptance run that restated the primary story from `spec.md:12-19` and checked whether the merged behavior satisfied it. The later mission review did that, which is why it caught the drift.

## Blast Radius

The direct blast radius is feature-scoped: it affects the fresh clone bootstrap mission and the setup docs/routes it touched.

There is a systemic process risk for future missions that have a similar shape: a high-level promise, a known risk in the plan, and work packages that each prove a narrower slice. The failure mode is not specific to bootstrap. Any mission can drift if a risk remains advisory and no WP owns an acceptance check for the original user story.

No evidence in this audit shows private health-data exposure, runtime warehouse mutation, or security compromise. The setup-only boundary appears to have been actively guarded.

## Severity

**HIGH** for DRIFT-1: the main fresh-clone path can fail at the first command, so the central mission promise is blocked.

**MEDIUM** for DRIFT-2: readiness was narrower than promised, but the failure is less immediate than the missing first command and is partly entangled with legitimate avoidance of optional `doctor` blockers.

Overall audit severity: **HIGH**, because the primary user story was not satisfied.

## Methodology Gaps Found

1. A known risk can survive from plan to implementation without a named owner.

2. Work-package reviews can pass by checking task-local evidence while missing the mission-level promise.

3. Docs tests can protect an incorrect instruction if they assert phrase presence rather than preconditions.

4. Installed-entry-point tests can look like fresh-clone tests while explicitly skipping the missing-binary condition.

5. Review artifacts were not rich enough to reconstruct the full reviewer reasoning beyond status event summaries.

## Recommendations

### Process Changes

1. Turn every `plan.md` open risk into either a WP-owned task, an explicit non-goal, or a mission-level acceptance check.

2. Add a final mission-review checklist item: rerun the primary user story from `spec.md` in plain English before approving the mission.

3. For setup/bootstrap missions, require a "first runnable command" test separate from installed console-script coverage.

4. Require docs tests to protect preconditions when docs make a first-step claim. For example, a fresh-clone command must either be runnable before install or name the pre-step that makes it runnable.

5. Keep review-cycle notes as files under the mission directory when possible, not only compressed status-event summaries.

### Fix Direction

1. For DRIFT-1, choose and document the true first command for a clean clone. It could be `uv run hpipe bootstrap`, a shell bootstrap wrapper, or another minimal repo-supported pre-step, but the docs and tests must agree.

2. Add an acceptance test that starts from a checkout state where the `hpipe` console script is not already installed and proves the documented first command reaches a bounded ready/blocked result.

3. For DRIFT-2, define the exact setup-time core surfaces that count as readiness without requiring private health data or optional upload configuration.

4. Add tests that fail if readiness omits those surfaces, while keeping optional upload checks as warnings rather than required blockers.

## Open Questions

1. Should the canonical first command be `uv run hpipe bootstrap`, `bash ops/bootstrap.sh` followed by `hpipe bootstrap`, or a new repo-local wrapper? The audit identifies the need; it does not choose the product answer.

2. Which core surfaces should count as setup readiness: importability of console-script targets, `hpipe doctor`, MCP entrypoints, or a smaller named subset? The spec says the category, but the implementation needs a bounded list or rule.

3. Was the missing first-command acceptance check a one-off oversight, or does spec-kitty need a formal "open risks must be closed" gate before WP approval? This audit found enough evidence to recommend the gate, but not enough history to measure frequency.

## Current-State Note

The current worktree has modifications to `src/premura/bootstrap.py`, and the current file contains code that appears to address at least part of core-surface verification. This audit intentionally does not judge those uncommitted changes. It audits how the drift described in `mission-review.md` could happen at the reviewed mission snapshot.
