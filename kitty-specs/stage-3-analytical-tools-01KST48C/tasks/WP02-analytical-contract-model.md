---
work_package_id: WP02
title: Analytical Contract Model
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-005
- FR-006
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-stage-3-analytical-tools-01KST48C
base_commit: c1f880277e513db69f42cef9b30bd6f8b5faf44e
created_at: '2026-05-29T15:28:06.068646+00:00'
subtasks:
- T005
- T006
- T007
- T008
shell_pid: "15705"
agent: "claude:opus:implementer:implementer"
history:
- 2026-05-29T15:18:42Z tasks generated
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/analytical_contract.py
- tests/test_engine_analytical_contract.py
tags: []
---

# WP02: Analytical Contract Model

## Objective

Add the typed analytical contract model: tool descriptor, registry, result envelope, refusal outcome, confound vocabulary, and validation tests.

## Branch Strategy

Planning/base branch: `master`. Final merge target: `master`. This WP depends on WP01. Implementation worktrees are allocated per computed lane from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent <name>
```

## Context

Read:

- `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md`
- `kitty-specs/stage-3-analytical-tools-01KST48C/data-model.md`
- `kitty-specs/stage-3-analytical-tools-01KST48C/contracts/analytical-tool-contract.md`
- `src/premura/engine/_registry.py`
- `src/premura/engine/_results.py`

## Detailed Guidance

### T005: Add analytical registry and tool descriptor contract

Create `src/premura/engine/analytical_contract.py`.

Define a frozen dataclass for an analytical tool descriptor with at least:

- `name`
- `description`
- `input_shape`
- `parameters`
- `result_kind`
- `confound_keys`
- `revision`
- `fn` or callable slot if needed by the registry

Add a small registry and decorator/helper equivalent in spirit to the existing signal/resolver registries. The registry must allow a test-only trivial tool to register and dispatch without adding a per-tool branch.

### T006: Add analytical result/refusal/confound model types

Add typed result structures for:

- analytical result envelope
- refusal outcome
- confound checklist entries
- uncertainty payload or explicit unavailable marker

Keep these structures MCP-agnostic and warehouse-agnostic. Each successful outcome should serialize to JSON-safe primitives through `to_dict()` or an equivalent public method.

### T007: Add contract validation for unknown confound keys and malformed results

Validation must reject:

- unknown confound keys
- non-refusal results missing required metadata
- refusal results that include an estimate
- malformed tool descriptors

Committed confound keys are listed in WP01's research note and `research.md`.

### T008: Add contract tests through the new analytical contract module

Create `tests/test_engine_analytical_contract.py`.

Cover:

- trivial tool registration and dispatch
- serialization of a valid result envelope
- rejection of unknown confound key
- rejection of refusal with estimate
- deterministic repeated serialization for the same constructed result

## Definition of Done

- Contract model exists and is tested.
- No MCP or warehouse access is introduced in this module.
- Tests fail before implementation and pass after implementation.

## Risks

- Overexposing internal helpers now will freeze unnecessary API surface. Keep the public contract small.

## Reviewer Guidance

Verify that this WP defines a bounded extension point rather than a tool-specific implementation.

## Activity Log

- 2026-05-29T15:28:07Z – claude:opus:implementer:implementer – shell_pid=15705 – Assigned agent via action command
- 2026-05-29T15:33:09Z – claude:opus:implementer:implementer – shell_pid=15705 – Ready for review: analytical contract model (registry, descriptor, result/refusal envelope, closed confound + question vocabularies, validation); 17 tests pass; no MCP/warehouse imports
