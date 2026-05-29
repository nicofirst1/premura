---
work_package_id: WP05
title: Public Engine Analytical Surface
dependencies:
- WP04
requirement_refs:
- FR-001
- FR-005
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
history:
- 2026-05-29T15:18:42Z tasks generated
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical.py
- src/premura/engine/__init__.py
- tests/test_engine_analytical_public_surface.py
tags: []
---

# WP05: Public Engine Analytical Surface

## Objective

Expose the analytical contract and proof tools through a stable public engine surface while preserving static loading and no dispatch ladder behavior.

## Branch Strategy

Planning/base branch: `master`. Final merge target: `master`. This WP depends on WP04. Implementation worktrees are allocated per computed lane from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP05 --agent <name>
```

## Context

Read:

- `src/premura/engine/__init__.py`
- `src/premura/engine/analytical_contract.py`
- `src/premura/engine/analytical_inputs.py`
- `src/premura/engine/analytical_tools.py`
- existing public-surface tests under `tests/test_engine_*`

## Detailed Guidance

### T017: Add engine public analytical dispatch/load surface

Create `src/premura/engine/analytical.py` as the public analytical facade.

It should provide narrowly scoped helpers for:

- loading/registering built-in analytical tools statically
- listing registered analytical tools if needed by MCP/tests
- invoking a tool by name through the shared analytical dispatch path

Avoid filesystem scanning, plugin entry points, and per-tool dispatch branches.

### T018: Re-export stable analytical symbols from `premura.engine`

Update `src/premura/engine/__init__.py` with only the symbols implementation and MCP callers need.

Do not re-export private helpers or every internal dataclass by default.

### T019: Add public-surface tests for registration, dispatch, determinism, and serialization

Create `tests/test_engine_analytical_public_surface.py`.

Cover:

- built-in tools are available after analytical built-in loading
- tool invocation returns serialized envelopes
- repeated invocation over same fixture is deterministic
- unknown tool names refuse or raise a clear public error

### T020: Preserve static built-in loading and no dispatch ladder behavior

Tests or review notes should make clear that adding future tools means registering against the analytical contract and adding a static built-in module entry if needed, not editing a branch ladder.

## Definition of Done

- Public engine analytical surface exists.
- Stable symbols are intentionally exported.
- No broad plugin loader or filesystem scanner is introduced.

## Risks

- Public API creep. Keep the facade minimal.

## Reviewer Guidance

Confirm public imports and invocation behavior are what MCP will depend on.
