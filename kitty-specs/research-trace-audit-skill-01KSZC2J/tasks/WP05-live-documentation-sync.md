---
work_package_id: WP05
title: Live Documentation Sync
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-012
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
agent: "claude:opus:docs-reviewer:reviewer"
shell_pid: "56254"
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

## Documentation Wording Guidance

Use restrained, exact language. Prefer:

- "Premura now ships a research trace audit skill that consumes the audit-consumer contract."
- "The skill reviews final answers for search-effort disclosure, hidden refusals or unavailable surfaced marks, and overclaims."
- "The skill does not change trace counts or analytical tool math."

Avoid:

- "Premura audits all agent answers."
- "The audit skill guarantees correctness."
- "The audit skill detects significance problems" if that wording implies significance exists.
- "The trace now judges answers" because the trace remains measurement, not interpretation.

## Files And Likely Edits

`STATUS.md` should move the audit skill from deferred to shipped in the section that already describes session research trace and multiplicity disclosure.

`ROADMAP.md` should remove the audit skill from the immediate deferred list, while leaving other deferred work alone.

`FULL_APP_DEVELOPMENT_PLAN.md` should update Phase 3 status and exit-criteria wording. It may still mention that deterministic stats and PubMed remain future work.

Do not update archived history docs unless they are actively wrong about current state and are not meant to be historical.

## Consistency Checklist

Before handoff, answer these checks in your notes:

- Does any live doc still say the audit skill is deferred?
- Does any live doc imply a generic audit product shipped?
- Does any live doc imply trace counts changed?
- Does any live doc imply PubMed, `rolling_mean`, `paired_t_test`, or intake resolvers shipped?
- Does install-target wording match WP04's actual outcome?

If any answer is unclear, fix the docs or explicitly note why the wording is historical and left unchanged.

## Review Scope

This WP is documentation-only. It should not fix code, add fixtures, or adjust skill content. If you notice a code bug while syncing docs, record it in handoff and stop rather than expanding this WP.

## Definition of Done

- Live docs accurately say the audit skill shipped.
- Other deferred missions remain deferred in docs.
- Docs do not claim generic audit support.
- Docs do not claim trace semantics or analytical math changed.

## Reviewer Guidance

Reject if docs overclaim, if they mark contingent installer support as shipped incorrectly, or if they edit historical specs instead of live reference docs.

## Activity Log

- 2026-05-31T17:08:05Z – claude:opus:docs-implementer:implementer – shell_pid=51416 – Started implementation via action command
- 2026-05-31T17:10:57Z – claude:opus:docs-implementer:implementer – shell_pid=51416 – Ready for review: live docs synced to shipped audit skill
- 2026-05-31T17:11:28Z – claude:opus:docs-reviewer:reviewer – shell_pid=56254 – Started review via action command
