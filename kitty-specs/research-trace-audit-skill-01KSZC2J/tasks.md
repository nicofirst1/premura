# Tasks: Research Trace Audit Skill

**Mission**: `research-trace-audit-skill-01KSZC2J`  
**Mission ID**: `01KSZC2J8N2EE41AV1DT5R9HBY`  
**Branch Contract**: Planning/base branch `master`; completed changes merge into `master`.  
**Generated**: 2026-05-31T16:16:44Z

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Research general agent skill authoring standards and current external guidance. | WP01 | No | [D] |
| T002 | Research local skill discovery and installation patterns for Claude-style and OpenCode-style homes. | WP01 | No | [D] |
| T003 | Evaluate write-once packaging or installer approaches and give adopt/defer/reject recommendation. | WP01 | No | [D] |
| T004 | Translate findings into Premura-specific skill-authoring and installation rules. | WP01 | No | [D] |
| T005 | Author five synthetic audit fixtures with expected verdicts before rubric prose. | WP02 | No |
| T006 | Write `AUDIT_RUBRIC.md` as a bounded criteria registry, not a banned-phrase list. | WP02 | No |
| T007 | Cross-check rubric criteria against the audit-consumer contract and fixture expectations. | WP02 | No |
| T008 | Verify fixture hygiene: synthetic only, no PHI, no redefined trace counts. | WP02 | No |
| T009 | Author `SKILL.md` frontmatter for discoverability and correct invocation. | WP03 | No |
| T010 | Write the skill workflow for required inputs, review sequence, and audit output. | WP03 | No |
| T011 | Link the skill to `AUDIT_RUBRIC.md`, fixtures, and authoritative Premura contracts. | WP03 | No |
| T012 | Validate first-time-reader clarity and offline runtime behavior. | WP03 | No |
| T013 | Verify existing Claude-style install path discovers the new skill. | WP04 | No |
| T014 | If WP01 recommends adopt, extend installer support for the selected additional local home. | WP04 | No |
| T015 | Add public-interface tests for any installer extension. | WP04 | No |
| T016 | Document install verification outcomes for supported, deferred, or rejected homes. | WP04 | No |
| T017 | Update live status and roadmap docs to mark the audit skill shipped after implementation. | WP05 | No |
| T018 | Update phase-plan wording so remaining deferred work stays accurate. | WP05 | No |
| T019 | Run doc consistency checks against code and mission artifacts. | WP05 | No |
| T020 | Record final validation notes for reviewer handoff. | WP05 | No |

## Work Package Overview

| WP | Title | Subtasks | Dependencies | Prompt |
|---|---|---:|---|---|
| WP01 | WP0 Skill Research Gate | 4 | None | `tasks/WP01-wp0-skill-research-gate.md` |
| WP02 | Fixtures and Bounded Rubric | 4 | WP01 | `tasks/WP02-fixtures-and-bounded-rubric.md` |
| WP03 | Agent Skill Instructions | 4 | WP01, WP02 | `tasks/WP03-agent-skill-instructions.md` |
| WP04 | Installation Verification and Contingent Installer | 4 | WP01, WP03 | `tasks/WP04-installation-verification-and-contingent-installer.md` |
| WP05 | Live Documentation Sync | 4 | WP02, WP03, WP04 | `tasks/WP05-live-documentation-sync.md` |

## WP01 - WP0 Skill Research Gate

**Goal**: Produce the mission's required WP0 research deliverable before implementation locks rubric or install choices.  
**Priority**: Highest. This gates all later WPs.  
**Independent Test**: Reviewer can read `research/wp0-skill-research.md` and find external-source-backed skill-authoring guidance, install-path findings, write-once packaging recommendation, and Premura-specific rules in <= 1,500 words excluding citations.

**Included subtasks**:

- [x] T001 Research general agent skill authoring standards and current external guidance. (WP01)
- [x] T002 Research local skill discovery and installation patterns for Claude-style and OpenCode-style homes. (WP01)
- [x] T003 Evaluate write-once packaging or installer approaches and give adopt/defer/reject recommendation. (WP01)
- [x] T004 Translate findings into Premura-specific skill-authoring and installation rules. (WP01)

**Implementation sketch**:

1. Start from `research.md` and the plan's anchor source notes, but do not treat them as final.
2. Use current external sources to confirm skill format, frontmatter, resource bundling, progressive disclosure, and install homes.
3. Write one concise research deliverable under `research/` with citations, recommendation, and Premura-specific consequences.
4. Explicitly state whether OpenCode-style installer support is adopt, defer, or reject for this mission.

**Parallel opportunities**: None. The recommendation controls downstream scope.

**Dependencies**: None.

**Risks**:

- Treating planning assumptions as research findings.
- Overcommitting to multi-home installer work without verifying local scan paths.
- Writing a broad literature review instead of a decision-ready recommendation.

**Estimated prompt size**: ~230 lines.

## WP02 - Fixtures and Bounded Rubric

**Goal**: Create synthetic audit fixtures and the bounded rubric that interprets Premura's audit-consumer contract without hardcoding a brittle banned-phrase checklist.  
**Priority**: High. This is the core audit behavior.  
**Independent Test**: Two reviewer agents can apply the rubric to the five fixtures and agree on at least 4 of 5 top-level verdicts.

**Included subtasks**:

- [ ] T005 Author five synthetic audit fixtures with expected verdicts before rubric prose. (WP02)
- [ ] T006 Write `AUDIT_RUBRIC.md` as a bounded criteria registry, not a banned-phrase list. (WP02)
- [ ] T007 Cross-check rubric criteria against the audit-consumer contract and fixture expectations. (WP02)
- [ ] T008 Verify fixture hygiene: synthetic only, no PHI, no redefined trace counts. (WP02)

**Implementation sketch**:

1. Read the session trace audit-consumer contract before writing fixture shapes.
2. Create the required five fixture JSON files with expected verdicts and reason categories first.
3. Write `AUDIT_RUBRIC.md` to satisfy the fixtures and the rubric-criterion contract.
4. Verify each non-pass expected verdict has concrete evidence references available from structured disclosure fields or answer spans.

**Parallel opportunities**: Low. Fixtures and rubric should be authored together to avoid drift.

**Dependencies**: Depends on WP01.

**Risks**:

- Encoding a closed list of forbidden tokens instead of category questions.
- Accidentally changing trace semantics by inventing counts.
- Using real health data in fixtures.

**Estimated prompt size**: ~280 lines.

## WP03 - Agent Skill Instructions

**Goal**: Write the agent-facing `SKILL.md` that activates correctly, names required inputs clearly, and guides an audit from trace disclosure plus final answer to an actionable result.  
**Priority**: High. This makes the rubric usable as a skill.  
**Independent Test**: A first-time reader can identify required inputs in under 2 minutes and follow the workflow without reading source code.

**Included subtasks**:

- [ ] T009 Author `SKILL.md` frontmatter for discoverability and correct invocation. (WP03)
- [ ] T010 Write the skill workflow for required inputs, review sequence, and audit output. (WP03)
- [ ] T011 Link the skill to `AUDIT_RUBRIC.md`, fixtures, and authoritative Premura contracts. (WP03)
- [ ] T012 Validate first-time-reader clarity and offline runtime behavior. (WP03)

**Implementation sketch**:

1. Use WP01 findings for skill format and WP02 artifacts for audit behavior.
2. Keep discovery frontmatter concise and activation instructions practical.
3. Make required inputs explicit: structured Session Disclosure and final answer text.
4. Tell agents exactly when to return pass, needs revision, or blocked, while deferring criteria detail to `AUDIT_RUBRIC.md`.

**Parallel opportunities**: Starts after WP02; no useful parallel split inside this WP.

**Dependencies**: Depends on WP01 and WP02.

**Risks**:

- Duplicating the rubric in `SKILL.md` and creating two sources of truth.
- Hiding required inputs in prose that is hard to scan.
- Letting packaging guidance leak into audit logic.

**Estimated prompt size**: ~250 lines.

## WP04 - Installation Verification and Contingent Installer

**Goal**: Verify the new skill installs through the existing Claude-style path and implement any additional local skill-home support only if WP01 recommends adopt.  
**Priority**: Medium. It makes the skill locally usable without expanding scope prematurely.  
**Independent Test**: Reviewer can verify at least one supported local installation path and can see whether extra homes were adopted, deferred, or rejected.

**Included subtasks**:

- [ ] T013 Verify existing Claude-style install path discovers the new skill. (WP04)
- [ ] T014 If WP01 recommends adopt, extend installer support for the selected additional local home. (WP04)
- [ ] T015 Add public-interface tests for any installer extension. (WP04)
- [ ] T016 Document install verification outcomes for supported, deferred, or rejected homes. (WP04)

**Implementation sketch**:

1. Run the existing installer path against a temp project and verify `research-trace-audit/SKILL.md` is materialized.
2. Read WP01's recommendation before changing code.
3. If recommendation is adopt, add the smallest installer extension and public-interface tests.
4. If recommendation is defer or reject, do not change installer code; document the decision and verification path.

**Parallel opportunities**: Can proceed after WP03 and WP01; independent of WP05.

**Dependencies**: Depends on WP01 and WP03.

**Risks**:

- Implementing OpenCode support after a defer/reject recommendation.
- Testing installer internals instead of public observable behavior.
- Creating overlapping or non-idempotent install writes.

**Estimated prompt size**: ~270 lines.

## WP05 - Live Documentation Sync

**Goal**: Update live product/status docs after the skill and installer decisions land, without overclaiming generic audit support or changing deferred work incorrectly.  
**Priority**: Medium. This is the bookkeeping that prevents stale roadmap/status truth.  
**Independent Test**: Docs accurately state that the Premura audit skill is shipped, while PubMed, intake, and remaining analytical tools stay deferred unless changed by other missions.

**Included subtasks**:

- [ ] T017 Update live status and roadmap docs to mark the audit skill shipped after implementation. (WP05)
- [ ] T018 Update phase-plan wording so remaining deferred work stays accurate. (WP05)
- [ ] T019 Run doc consistency checks against code and mission artifacts. (WP05)
- [ ] T020 Record final validation notes for reviewer handoff. (WP05)

**Implementation sketch**:

1. Wait until WP02-WP04 have landed so docs describe actual behavior.
2. Update `STATUS.md`, `ROADMAP.md`, and the phase plan with precise wording.
3. Preserve the distinction between Premura-specific audit skill and generic answer audit tooling.
4. Confirm no doc implies PubMed, intake resolvers, `rolling_mean`, or `paired_t_test` shipped.

**Parallel opportunities**: None. This should run late.

**Dependencies**: Depends on WP02, WP03, and WP04.

**Risks**:

- Marking contingent installer support as shipped when WP01 rejected or deferred it.
- Accidentally claiming the audit skill changes trace counts.
- Stale roadmap language around other deferred missions.

**Estimated prompt size**: ~220 lines.
