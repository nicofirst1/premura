# Feature Specification: Fresh Clone Bootstrap Agent

**Mission Type**: software-dev  
**Created**: 2026-06-01  
**Status**: Draft  
**Input**: User selected candidate 3, then clarified that the mission should also ship an install path that installs missing project dependencies locally in the Premura checkout/environment, akin to `pip install`.

## User Scenarios & Testing *(mandatory)*

### Primary User Story

A human has freshly cloned Premura and asks an agent inside the repo to install it. The agent follows a documented bootstrap path, installs missing project dependencies into the local Premura checkout/environment where possible, verifies the installation, installs or verifies required project agent skills, and reports whether a new agent session is needed before Premura can be operated.

### Acceptance Scenarios

1. **Given** a fresh Premura checkout with no project environment prepared, **When** an agent follows the bootstrap path, **Then** the local project environment is created or updated, required project dependencies are installed locally, and the agent receives a clear install-ready result or a bounded list of unmet prerequisites.
2. **Given** required project skills are missing or stale, **When** the bootstrap path reaches skill setup, **Then** it installs or verifies the skills through the repo-supported path and tells the user if the current agent session must be reloaded to see them.
3. **Given** a dependency cannot be installed safely inside the project checkout/environment, **When** bootstrap runs, **Then** it does not make an uncontrolled system-wide change and instead reports the prerequisite, why it cannot be handled locally, and the exact next action needed.
4. **Given** the bootstrap path completes successfully, **When** verification runs, **Then** it confirms enough of the local install for an agent to hand off to normal Premura operation without ingesting health data or answering health questions.

### Edge Cases

- The project environment already exists and is current; bootstrap should verify rather than reinstall unnecessarily.
- Dependencies are partially installed; bootstrap should converge to a clean local state or explain the blocker.
- Required system tools are absent and cannot be installed locally; bootstrap should stop with a clear prerequisite report rather than hiding the failure.
- Skill installation succeeds but the active agent session cannot see newly installed skills until reload; bootstrap should make that visible.
- The repo is dirty or has uncommitted user changes; bootstrap should avoid destructive cleanup and report what it did.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| FR-001 | Proposed | The bootstrap path MUST give an agent a single documented entry point for installing or verifying a freshly cloned Premura checkout. | A new agent can find the entry point from root guidance and complete the bootstrap workflow without reading planning-only artifacts. |
| FR-002 | Proposed | The bootstrap path MUST install missing project dependencies into the local Premura checkout/environment when the dependency is safely installable there. | On a clean checkout with supported local prerequisites, the workflow creates or updates the local project environment and reports the installed dependency groups. |
| FR-003 | Proposed | The bootstrap path MUST verify the installed project environment after dependency setup. | Verification reports pass/fail for command availability, ability to start the core project surfaces, and the existing Premura health check surface needed before normal operation. |
| FR-004 | Proposed | The bootstrap path MUST install or verify Premura-supported agent skills and setup artifacts through repo-supported commands or documented local paths. | Missing or stale supported skills are installed or reported with exact remediation steps, and successful runs state where the skills were installed. |
| FR-005 | Proposed | The bootstrap path MUST report when a fresh or reloaded agent session is needed for installed skills or environment changes to become visible. | A successful or partially successful run includes a reload-required field or plain-language equivalent whenever current-session visibility cannot be guaranteed. |
| FR-006 | Proposed | The bootstrap path MUST distinguish locally handled dependencies from prerequisites that require external user action. | Unsupported or system-level prerequisites are listed separately with a reason and exact next action; they are not presented as successful local installs. |
| FR-007 | Proposed | The bootstrap path MUST avoid runtime health-data operation. | The workflow does not ingest source artifacts, query private warehouse rows, run analytical tools, or answer health questions during bootstrap verification. |
| FR-008 | Proposed | The bootstrap path MUST produce a final handoff summary for the agent and human. | The summary states install status, remaining blockers, reload guidance, and the next safe command or doc for normal Premura operation. |

### Non-Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| NFR-001 | Proposed | The successful bootstrap path SHOULD complete in under 10 minutes on the maintainer's supported local workstation when network access for dependency downloads is available. | A documented verification run records elapsed time below 10 minutes for a clean supported checkout. |
| NFR-002 | Proposed | The bootstrap verification output MUST fit in 200 terminal lines for the success path. | A success-path transcript is 200 lines or fewer while still naming installed groups, verification status, and reload guidance. |
| NFR-003 | Proposed | Bootstrap MUST be idempotent for an already prepared checkout. | Running the workflow twice in a row leaves the repo usable both times and the second run reports no unnecessary reinstall of already-current local dependencies. |
| NFR-004 | Proposed | Bootstrap MUST preserve local-first safety by default. | Verification confirms no health-data upload, no source-artifact ingest, and no remote health-data API access occurs during bootstrap. |
| NFR-005 | Proposed | Bootstrap failure reports MUST be actionable without hidden logs. | For each failed check, the user-facing output includes the failed item, observed state, and a concrete next action in no more than 5 lines per item. |

### Constraints

| ID | Status | Constraint | Acceptance Criteria |
|---|---|---|---|
| C-001 | Proposed | Bootstrap MUST stay separate from the runtime orchestrator and operating roles. | Documentation and behavior describe setup-only responsibilities and do not route ingest, analysis, or human-facing health tasks. |
| C-002 | Proposed | Bootstrap MUST prefer local project-environment installation over system-wide mutation. | Dependency installation targets the local checkout/environment where possible; any system-level prerequisite is reported for explicit user action. |
| C-003 | Proposed | Bootstrap MUST follow the agent-first doctrine without becoming a human-filled form or dashboard flow. | The primary flow is written for an agent operating in the repo, with human approval only where local setup cannot proceed safely. |
| C-004 | Proposed | Bootstrap MUST not copy, inspect, or commit private health artifacts. | Tests and verification use synthetic or non-health setup fixtures only, and no `data/` private payload is required. |
| C-005 | Proposed | Bootstrap MUST keep root docs as routers rather than duplicating full setup policy everywhere. | Root docs point to the bootstrap entry point and authoritative setup guidance without repeating long implementation details. |

## Key Entities *(include if feature involves data)*

- **Bootstrap run**: One agent-invoked setup attempt for a Premura checkout, including discovered prerequisites, local install actions, verification results, and reload guidance.
- **Local project environment**: The dependency environment tied to the Premura checkout and prepared through repo-supported setup guidance.
- **Bootstrap check**: A named verification item with a status, observed state, and next action when it fails.
- **Skill setup state**: Whether required Premura agent skills are installed, stale, visible to the current session, or require a reload.

## Assumptions

- The first supported install target is the local Premura checkout/environment, not a global machine bootstrap or package-manager takeover.
- Existing documented setup guidance in `README.md` and `CONTRIBUTING.md` is the starting point, but the mission may tighten or wrap it so a weaker agent can follow one path.
- System-level tools that cannot be installed safely inside the checkout are reported as prerequisites rather than silently installed globally.
- A successful bootstrap handoff means Premura is ready for normal operation; it does not mean any personal health-data source has been ingested.

## Success Criteria *(mandatory)*

| ID | Status | Criterion | Measurement |
|---|---|---|---|
| SC-001 | Proposed | A fresh-clone agent can complete setup without inventing missing steps. | In a clean supported checkout, a documented agent-run transcript reaches install-ready or bounded-prerequisite status using the bootstrap path. |
| SC-002 | Proposed | Local dependencies are installed or verified through one repeatable path. | A clean supported checkout reports all required project dependency checks passing after one bootstrap run. |
| SC-003 | Proposed | The bootstrap path gives clear reload guidance. | 100% of verification transcripts that install or update skills include either "reload required" or "reload not required" guidance. |
| SC-004 | Proposed | Bootstrap remains setup-only. | Acceptance review confirms zero bootstrap steps ingest health data, query private warehouse rows, or call analytical health tools. |
| SC-005 | Proposed | Failures are useful to a weaker agent. | In at least three simulated missing-prerequisite cases, the output names the blocker and exact next action without requiring hidden context. |

## Out of Scope

- Runtime orchestration of health-data tasks after install.
- End-to-end agent acceptance sandbox scoring across model tiers.
- Parser generation for a new health-data source.
- Teaching UI, health-direction interview flow, or health-answer narration.
- System-wide package management beyond reporting explicit prerequisites for user approval.
