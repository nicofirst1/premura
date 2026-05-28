---
work_package_id: WP02
title: Observation And Profile Resolvers
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-28T08:13:11Z'
subtasks:
- T006
- T007
- T008
- T009
agent: ''
history:
- timestamp: '2026-05-28T08:13:11Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/views/
execution_mode: code_change
owned_files:
- src/premura/engine/views/observation.py
- src/premura/engine/views/profile.py
- src/premura/engine/_query.py
- tests/test_engine_resolvers.py
tags: []
---

# Work Package Prompt: WP02 - Observation And Profile Resolvers

## Objective

Implement the two concrete resolvers backed by already-shipped data:

- observation-history resolution
- profile-as-of resolution

This WP should prove that the new seam can resolve real dependencies honestly at
an anchor time without collapsing domain meaning.

## Owned Surface

- `src/premura/engine/views/observation.py`
- `src/premura/engine/views/profile.py`
- `src/premura/engine/_query.py`
- `tests/test_engine_resolvers.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: `WP01`
- Implementation command: `spec-kitty agent action implement WP02 --agent <name>`

## Context

WP01 defines the seam and unresolved-domain behavior.

This WP must implement the only two concrete resolvers the mission has enough
real data to justify now:

1. `observation_history`
2. `profile_context`

The repo already contains reusable observation-side logic in `_query.py`. Reuse
that where it fits instead of creating a second interpretation of validity and
freshness.

The profile resolver must honor the meaning contract:

- resolve declared profile context
- as of an anchor time
- never substitute an observation just because it exists

## Subtasks

### T006 - Add failing public-interface tests for concrete resolver behavior

**Purpose**

Define what successful observation and profile resolution look like before the
resolver modules are written.

**Required changes**

- Add `tests/test_engine_resolvers.py`.
- Cover at least:
  - observation resolution with usable input
  - observation resolution with stale input
  - profile resolution with a valid declared value as of anchor time
  - profile resolution with no matching declared value

**Testing guidance**

- Drive behavior through the public seam from WP01.
- Use synthetic fixtures and temporary DuckDB state.

### T007 - Implement the observation resolver

**Purpose**

Resolve declared observation dependencies honestly using the metric policy and
freshness logic Premura already has.

**Required changes**

- Add `src/premura/engine/views/observation.py`.
- Reuse `_query.py` policy and freshness helpers where appropriate.
- Return explicit usable, stale, and missing outcomes.

**Constraints**

- Do not fork metric-policy behavior into a second code path.
- Keep the resolver domain-specific and deterministic.

### T008 - Implement the profile-as-of resolver

**Purpose**

Resolve declared profile dependencies from the shipped profile assertion storage
as of a chosen anchor time.

**Required changes**

- Add `src/premura/engine/views/profile.py`.
- Resolve the latest valid profile assertion as of the anchor time.
- Preserve explicit absence behavior.

**Constraints**

- Resolve by meaning and as-of semantics, not by “latest row wins”.
- Do not reach into observation history to satisfy profile requirements.

### T009 - Prove there is no hidden fallback

**Purpose**

Lock the hardest failure mode: opportunistically satisfying a declared profile
dependency from a convenient observation row.

**Required changes**

- Extend `tests/test_engine_resolvers.py` to cover a case where a measured height
  exists but declared height does not.
- Prove that the resolver still refuses rather than silently reclassifying the
  dependency.

**Testing guidance**

- Make the failure explicit and easy for reviewers to understand.

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q tests/test_engine_resolvers.py
```

Expected outcomes:

- observation dependencies resolve with real freshness behavior
- profile dependencies resolve as-of anchor time
- hidden cross-domain fallbacks are rejected

## Definition Of Done

- Observation and profile resolver modules exist.
- Both are reachable through the WP01 surface.
- Tests prove usable, stale, missing, and no-hidden-fallback behavior.

## Risks And Watchouts

- Duplicating observation freshness logic instead of reusing `_query.py`.
- Treating profile resolution as a storage-shape lookup instead of a meaning-
  and-time lookup.
- Writing tests that accidentally bless fallback behavior.

## Reviewer Guidance

Review this WP as the first real semantic-domain resolution implementation.

Ask:

1. Does the observation resolver respect existing Stage 2 policy? 
2. Does the profile resolver resolve declared data as of the anchor time? 
3. Is the no-hidden-fallback rule actually proven by tests?

## Activity Log

- 2026-05-28T08:13:11Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
