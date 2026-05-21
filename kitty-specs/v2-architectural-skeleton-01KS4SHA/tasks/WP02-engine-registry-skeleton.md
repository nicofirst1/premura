---
work_package_id: WP02
title: Engine Registry Skeleton
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
agent: "claude:opus-4-7:reviewer:reviewer"
shell_pid: "34228"
history:
- timestamp: '2026-05-21T09:53:12Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/**
tags: []
---

# Work Package Prompt: WP02 - Engine Registry Skeleton

## Objective

Create the Stage 2 engine skeleton: the public registry contract and the five stub API functions, with no actual signal implementations.

This WP is small but architecturally load-bearing. Future engine work should be able to drop real signal functions onto this surface without file moves or contract rewrites.

## Owned Surface

- `src/premura/engine/_registry.py`
- `src/premura/engine/__init__.py`

Do not modify any files outside `src/premura/engine/` in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP02 --agent <name>`

## Subtasks

### T005 - Create `engine/_registry.py`

**Purpose**

Define the open-boundary registry data model that future signal functions register into.

**Required changes**

- Create `src/premura/engine/_registry.py`.
- Add the frozen `SignalSpec` dataclass with exactly these fields:
  - `name`
  - `domain`
  - `inputs`
  - `output`
  - `priority`
  - `auto_safe`
  - `revision`
  - `fn`
- Add module-level `REGISTRY: dict[str, SignalSpec] = {}`.
- Add `signal(...)` decorator factory that registers the decorated function in `REGISTRY` and returns the function unchanged.

**Contract details**

- Defaults must match the spec exactly.
- `revision` default is string `"1"`.
- `fn` is set by the decorator.
- The decorator should overwrite duplicate names rather than layering extra structures; collision prevention is review-time, not runtime, in this mission.

### T006 - Create `engine/__init__.py`

**Purpose**

Publish the Stage 2 import surface and stub API contract.

**Required changes**

- Add a module docstring that explicitly references:
  - `Stage 2`
  - `Signal engine`
  - `on-demand`
  - `auto-run`
  - the open registry boundary / possible proprietary derivations
- Re-export `signal`, `SignalSpec`, and `REGISTRY` from `_registry.py`.
- Add these five functions, all raising `NotImplementedError` with a message referencing `STAGES.md`:
  - `compute(spec_name, conn)`
  - `list_by_domain(domain)`
  - `list_auto_safe()`
  - `check_inputs_available(inputs, conn, within=None)`
  - `list_unavailable(domain, conn)`

**Keep it minimal**

- No real DuckDB reads.
- No signal discovery from the filesystem.
- No helper modules beyond `_registry.py`.

### T007 - Preserve the open-boundary import behavior

**Purpose**

Ensure the engine can be imported in isolation and remains empty until future implementation modules opt into registration.

**Required outcomes**

- Importing `premura.engine` must not import any non-existent or future signal modules.
- `REGISTRY` must be empty immediately after import.
- The module graph must stay small enough that `hpipe doctor` overhead remains negligible.

**Non-goals**

- Do not add reference signal implementations.
- Do not wire `auto_safe` into ingest.
- Do not introduce an engine package tree beyond the two files in this WP.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -c "from premura.engine import signal, SignalSpec, REGISTRY; assert REGISTRY == {}; print('open boundary OK')"
```

And after implementation, expect these behaviors:

- Decorating a test function with `@signal(...)` populates `REGISTRY[name]`.
- Calling any stub raises `NotImplementedError`.
- Importing the module does not attempt to load anything beyond `_registry.py`.

## Definition Of Done

- `src/premura/engine/_registry.py` exists with the exact registry/dataclass/decorator surface.
- `src/premura/engine/__init__.py` exists with the required docstring, re-exports, and five stubs.
- `REGISTRY` is empty at import time.

## Risks And Watchouts

- Small type/default mismatches here will ripple into every future engine mission.
- The easiest mistake is to over-engineer the registry or introduce premature helper modules.

## Reviewer Guidance

Review against the spec line-by-line. This WP should be intentionally boring: exact fields, exact stubs, exact docstring intent, no extra architecture.

## Activity Log

- 2026-05-21T11:05:27Z – claude:opus-4-7:implementer:implementer – shell_pid=54117 – Started implementation via action command
- 2026-05-21T11:10:02Z – claude:opus-4-7:implementer:implementer – shell_pid=54117 – Ready for review: engine registry _registry.py and Stage 2 stub API in __init__.py; REGISTRY empty at import, decorator round-trips, 5 stubs raise NotImplementedError, ruff/pytest clean (25 tests still pass)
- 2026-05-21T11:10:32Z – claude:opus-4-7:reviewer:reviewer – shell_pid=34228 – Started review via action command
