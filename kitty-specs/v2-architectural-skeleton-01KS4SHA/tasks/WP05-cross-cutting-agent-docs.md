---
work_package_id: WP05
title: Cross-Cutting Agent Docs
dependencies: []
requirement_refs:
- FR-010
- FR-018
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
agent: "claude:opus-4-7:reviewer:reviewer"
shell_pid: "36293"
history:
- timestamp: '2026-05-21T09:53:12Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- AGENTS.md
- docs/UPDATE_STRATEGY.md
tags: []
---

# Work Package Prompt: WP05 - Cross-Cutting Agent Docs

## Objective

Add the repo-level guidance docs that make the skeleton usable by both human contributors and agent-driven workflows.

This WP is documentation-only at the repository surface, but it still affects real contributor behavior and therefore belongs in the implementation sequence rather than staying purely inside `kitty-specs/`.

## Owned Surface

- `AGENTS.md`
- `docs/UPDATE_STRATEGY.md`

Do not modify any `kitty-specs/` planning documents in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP05 --agent <name>`

## Subtasks

### T018 - Create `AGENTS.md`

**Purpose**

Provide the short top-level pointer document that agents can find without reading deep package docs first.

**Required content**

- State the standards-first rule as a repo-level expectation.
- Reference `src/premura/parsers/CONTRACT.md`.
- Reference `src/premura/skills/parser-generator/SKILL.md`.
- Keep the doc short and pointer-oriented rather than duplicating the full parser contract.

### T019 - Create `docs/UPDATE_STRATEGY.md`

**Purpose**

Explain the six warehouse-update shapes and which ones are handled now versus deferred.

**Required content**

- Cover the six update kinds named in the spec:
  - new ingest,
  - schema migration,
  - ontology seed refresh,
  - derived-signal invalidation,
  - full rebuild from raw,
  - parser updates.
- Mark the first three as handled by the current architecture or mission sequence.
- Mark the latter three as future-mission work.

**Context to include**

- why `revision` exists on `SignalSpec`,
- why a future rebuild path exists,
- why parser changes and ontology evolution are separate concerns.

### T020 - Align the docs with the finalized policy choices

**Purpose**

Ensure the new repo docs reflect the post-interview decisions rather than the older draft assumptions.

**Must be explicit about**

- Stage 4 package naming is `ui/`.
- Canonical vocabulary policy is defined now but legacy metric-id rewriting is deferred.
- The future vocabulary rewrite happens via full rebuild from raw, not in-place migration.
- Aliases are limited to clinically standard names and abbreviations.

## Validation Strategy

Primary checks:

```bash
test -f AGENTS.md
test -f docs/UPDATE_STRATEGY.md
```

Manual review expectations:

- `AGENTS.md` contains both required relative paths.
- `docs/UPDATE_STRATEGY.md` contains the key update-type terms.
- Neither doc reintroduces `learn/` or an in-place canonical-vocabulary migration story.

## Definition Of Done

- `AGENTS.md` exists and is pointer-focused.
- `docs/UPDATE_STRATEGY.md` exists with the six update kinds and handled/deferred split.
- Both docs reflect the final canonical-vocabulary and Stage 4 naming decisions.

## Risks And Watchouts

- These docs are easy to treat as soft guidance; they should be written as repository contracts.
- Do not let `AGENTS.md` balloon into a second copy of the parser contract.

## Reviewer Guidance

Read these docs from a newcomer perspective: could a contributor find the parser contract quickly, understand the standards-first rule, and understand why a future full rebuild exists? If not, tighten the wording.

## Activity Log

- 2026-05-21T11:33:02Z – claude:opus-4-7:implementer:implementer – shell_pid=62575 – Started implementation via action command
- 2026-05-21T11:39:12Z – claude:opus-4-7:implementer:implementer – shell_pid=62575 – Ready for review: AGENTS.md (standards-first rule + pointers to CONTRACT.md and parser-generator SKILL.md) and docs/UPDATE_STRATEGY.md (six update kinds; (a)/(b)/(c) handled, (d)/(e)/(f) deferred). All backticked paths verified to exist; 25/25 tests still pass.
- 2026-05-21T11:39:39Z – claude:opus-4-7:reviewer:reviewer – shell_pid=36293 – Started review via action command
- 2026-05-21T11:42:21Z – claude:opus-4-7:reviewer:reviewer – shell_pid=36293 – Review passed: AGENTS.md and docs/UPDATE_STRATEGY.md are tight, code-grounded, and reflect the final ui/-naming and deferred-canonical-rewrite policies; all backticked code paths resolve and 25/25 tests pass.
