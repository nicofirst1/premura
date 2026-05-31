---
work_package_id: WP05
title: Live Documentation Sync
dependencies:
- WP02
- WP03
- WP04
requirement_refs: []
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T017
- T018
- T019
- T020
history:
- timestamp: '2026-05-31T16:16:44Z'
  agent: openai:gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: planning_artifact
owned_files:
- docs/operations/STATUS.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
tags: []
---

# Work Package Prompt: WP05 - Live Documentation Sync

## Objective

Update live docs after the audit skill and installation decision land. The docs should say what shipped and keep all unrelated deferred work accurate.

This WP runs late. Do not start it before WP02, WP03, and WP04 are done.

## Branch Strategy

Planning artifacts were generated on `master`. Completed changes must merge back into `master`. During implementation, Spec Kitty allocates execution worktrees per computed lane from `lanes.json`; do not create your own worktree or branch manually.

Use this command for implementation after dependencies are done:

```bash
spec-kitty agent action implement WP05 --agent <name>
```

## Authoritative Context

Read these before editing:

- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `src/premura/skills/research-trace-audit/SKILL.md`
- `src/premura/skills/research-trace-audit/AUDIT_RUBRIC.md`
- WP04 handoff or tests for installation support

## Owned Files

You may modify only:

- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`

Do not edit skill source or mission planning artifacts in this WP.

## Detailed Guidance

### T017 - Update live status and roadmap docs

In `STATUS.md`, update the relevant Stage 3/session trace section to state that the Premura-specific research trace audit skill now ships, if WP02-WP04 actually made it true.

In `ROADMAP.md`, remove or revise wording that says the audit skill is still deferred. Preserve other deferred items.

Be precise: this is a Premura-specific agent skill over the session research trace, not a generic answer-audit product.

### T018 - Update phase-plan wording

In `FULL_APP_DEVELOPMENT_PLAN.md`, update Phase 3 wording so the audit skill status matches reality.

Keep the remaining deferred work accurate:

- `rolling_mean`
- `paired_t_test`
- PubMed/literature grounding
- intake parsers/resolvers, unless another mission changed them

Do not imply the audit skill changes trace storage, trace counts, or analytical tool math.

### T019 - Run doc consistency checks

Search the docs you touched for stale phrases such as:

- `audit skill deferred`
- `not shipped`
- `following mission`

Only change them when they refer to this audit skill. Do not rewrite historical mission specs or archived docs.

Cross-check code state:

- `src/premura/skills/research-trace-audit/SKILL.md` exists
- `AUDIT_RUBRIC.md` exists
- fixture files exist
- install support matches WP04's outcome

### T020 - Record final validation notes for reviewer handoff

In the WP handoff, summarize:

- which docs were updated
- which wording was intentionally left alone because it was historical or about other deferred work
- whether OpenCode-style or additional install support shipped, deferred, or rejected
- what checks were run

Do not add a separate status log unless existing workflow requires it.

## Validation

Run targeted content searches and any markdown formatting checks used by the repo. At minimum, inspect the changed doc diff for overclaims.

Suggested checks:

```bash
uv run ruff format --check src/premura/skills
```

If no Python files changed in this WP, note that full Python lint/test checks are not necessary for docs-only changes, unless required by reviewer.

## Definition of Done

- Live docs accurately say the audit skill shipped.
- Other deferred missions remain deferred in docs.
- Docs do not claim generic audit support.
- Docs do not claim trace semantics or analytical math changed.

## Reviewer Guidance

Reject if docs overclaim, if they mark contingent installer support as shipped incorrectly, or if they edit historical specs instead of live reference docs.
