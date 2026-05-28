---
work_package_id: WP01
title: Resolver Surface And Registry Foundation
dependencies: []
requirement_refs:
- FR-001
- FR-006
- FR-007
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-stage-2-input-resolution-and-bmi-01KSPP73
base_commit: 06f17df200337f8492558ab697ba7f1a65294509
created_at: '2026-05-28T08:22:16.358543+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
agent: "claude:opus-4.7:python-implementer:implementer"
shell_pid: "84126"
history:
- timestamp: '2026-05-28T08:13:11Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/__init__.py
- src/premura/engine/_registry.py
- src/premura/engine/_resolution.py
- src/premura/engine/views/__init__.py
- tests/test_engine_input_resolution_surface.py
tags: []
---

# Work Package Prompt: WP01 - Resolver Surface And Registry Foundation

## Objective

Establish the Stage 2 input-resolution seam as a real, public, deterministic
engine boundary before any concrete resolver or consumer lands.

This WP is the structural correction for the mission. It must make Premura's
next analytical foundation look like:

- declared dependency
- anchor-time-aware resolution
- explicit supported vs unresolved domains
- static in-tree resolver registration

and **not** like a universal prepared-series abstraction.

## Owned Surface

- `src/premura/engine/__init__.py`
- `src/premura/engine/_registry.py`
- `src/premura/engine/_resolution.py`
- `src/premura/engine/views/__init__.py`
- `tests/test_engine_input_resolution_surface.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: none
- Implementation command: `spec-kitty agent action implement WP01 --agent <name>`

## Context

The mission spec and plan lock one central design decision:

- the Stage 2 foundation is a **domain-aware input-resolution seam**
- not a universal prepared-series layer

This WP therefore owns the public surface and registry shape that every later WP
builds on.

The repo already has useful ingredients:

- public engine imports through `premura.engine`
- a signal registry pattern
- dependency-declaration language in the profile/intake contract and engine
  contract

This WP must connect those pieces into a real resolution entrypoint without
overdesigning future domains.

## Subtasks

### T001 - Add failing public-surface tests for the new seam

**Purpose**

Define the contract through public behavior before implementation begins.

**Required changes**

- Add `tests/test_engine_input_resolution_surface.py`.
- Drive tests through public engine imports only.
- Cover at least:
  - a declared dependency can be passed to the new resolution seam
  - unsupported-but-declared domains fail explicitly
  - the public access path is deterministic and inspectable

**Testing guidance**

- Do not import private helpers to drive behavior.
- Keep fixtures synthetic and PHI-free.

### T002 - Add the shared resolution entrypoint and types

**Purpose**

Create one Stage 2 seam for resolving declared dependencies as of an anchor
time.

**Required changes**

- Add `src/premura/engine/_resolution.py`.
- Define the shared resolution entrypoint and the supporting types it needs.
- Keep the contract explicit about:
  - declared dependency input
  - anchor time
  - explicit usable vs missing vs stale vs unresolved outcomes

**Constraints**

- Do not promise one universal resolved payload shape.
- Keep the contract about the resolution protocol, not an all-data supertype.

### T003 - Add the static in-tree resolver registry pattern

**Purpose**

Make domain dispatch extensible in-tree now, while keeping it explicit and
reviewable.

**Required changes**

- Add static built-in resolver registration mirroring the existing signal
  registry shape.
- Use explicit in-tree module registration.
- Keep this static: no filesystem scanning, no out-of-tree discovery, no entry
  points.

**Constraints**

- Resolver dispatch should become open.
- Answer-family growth remains out of scope here.

### T004 - Wire the public engine surface

**Purpose**

Make the new seam consumable through public engine imports so later WPs and
tests do not need private internals.

**Required changes**

- Update `src/premura/engine/__init__.py` and/or related registry exports as
  needed.
- Ensure the new seam is reachable through the same style of public surface the
  rest of the engine already uses.

**Constraints**

- Keep imports lazy where existing engine behavior expects laziness.
- Avoid broad eager loading or a new plugin loader.

### T005 - Finish foundation coverage for unsupported future domains

**Purpose**

Lock the honest failure path before the concrete resolvers land.

**Required changes**

- Extend the tests to prove declared `nutrition_intake` and
  `supplement_intake` dependencies fail explicitly, not by coercion into another
  domain.
- Prove registry dispatch and unresolved-domain behavior are both observable from
  the public seam.

**Testing guidance**

- Make the failure explicit and inspectable.
- Do not overcommit to future domain behavior beyond “declared but not yet
  resolvable”.

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q tests/test_engine_input_resolution_surface.py
```

Expected outcomes:

- the new seam is visible through public engine imports
- resolver dispatch is registry-driven
- unresolved future domains fail honestly

## Definition Of Done

- A shared resolution entrypoint exists.
- A static in-tree resolver registry exists.
- The seam is reachable through public engine imports.
- Unsupported future domains fail explicitly rather than being silently coerced.
- Public-surface tests lock the behavior.

## Risks And Watchouts

- The biggest risk is recreating the prepared-series abstraction under a new name.
- Another risk is making the seam private-first and forcing later WPs to bypass
  it.
- Avoid dynamic discovery or speculative plugin machinery in this WP.

## Reviewer Guidance

Review this WP as the structural boundary correction for the mission.

Ask:

1. Is the seam really “declared dependency + resolution” rather than “data made
   series-shaped”? 
2. Can future domains stay declared without being falsely treated as supported?
3. Is the public engine surface the real entrypoint?

## Activity Log

- 2026-05-28T08:13:11Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-28T08:22:17Z – claude:opus-4.7:python-implementer:implementer – shell_pid=84126 – Assigned agent via action command
- 2026-05-28T08:32:37Z – claude:opus-4.7:python-implementer:implementer – shell_pid=84126 – Ready for review: resolver surface + registry + public re-exports + black-box tests; resolvers populated in WP02
