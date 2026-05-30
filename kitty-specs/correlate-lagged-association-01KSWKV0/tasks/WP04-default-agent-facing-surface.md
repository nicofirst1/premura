---
work_package_id: WP04
title: Default Agent-Facing Surface
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-017
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
agent: "claude:opus:implementer:implementer"
shell_pid: "92809"
history:
- 2026-05-30T14:27:30Z tasks generated for correlate lagged association mission
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- tests/test_mcp_correlate.py
tags: []
---

# WP04: Default Agent-Facing Surface

## Objective

Expose `correlate` through the default agent-facing MCP surface as a thin wrapper.
All preparation, computation, refusals, and caveats stay in the engine. The MCP
layer publishes and serializes; it does not become a statistics layer.

## Branch Strategy

Planning/base branch is `master`. Final merge target is `master`. Do not create a
manual worktree. Spec Kitty will allocate execution worktrees per computed lane
from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP04 --agent <name>
```

## Context

Depends on WP03. Follow the patterns used by existing analytical proof tools on
the default MCP surface. If those wrappers read from the warehouse before calling
engine preparation, keep that logic bounded to input retrieval and delegate all
analytical behavior to the engine.

## Subtasks

### T017: Add failing default-surface tests for the agent-facing `correlate` wrapper

Purpose: define the agent-facing contract before implementation.

Guidance:

- Add `tests/test_mcp_correlate.py` or follow the existing MCP test location if
  the repo has a more specific convention.
- Assert `correlate` appears on the default surface.
- Assert an available fixture returns the serialized analytical envelope from the
  engine.
- Assert a refusal fixture returns a serialized refusal and no estimate.
- Use synthetic data only.

Validation:

- Tests fail before the wrapper is published.

### T018: Implement the thin MCP wrapper that delegates all behavior to the engine analytical path

Purpose: publish the tool without duplicating engine logic.

Guidance:

- Update `src/premura/mcp/server.py` only within existing wrapper patterns.
- The wrapper should accept the agent-facing fields needed for a pre-registered
  hypothesis.
- It may gather/read the two input series if existing analytical wrappers do so,
  but it must delegate admissibility, pairing, computation, and result-envelope
  construction to the engine.
- Do not calculate Spearman, effective sample size, caveats, or confounds in MCP.
- Do not call PubMed or any network service.

Validation:

- Wrapper implementation remains small and declarative.
- Engine tests remain the source of truth for statistical behavior.

### T019: Validate wrapper serialization for available and refused outcomes

Purpose: ensure agents see the exact engine envelope.

Guidance:

- Test that available output includes estimate, uncertainty, validity, imputation,
  sample counts, effective sample size, overlap, lag, and confounds.
- Test that refusal output includes refusal reason/message and no estimate.
- Test that common-cause metadata is preserved when supplied.
- Test opposite-direction metadata is preserved.

Validation:

- Serialized wrapper payloads should be JSON-safe and byte-stable for identical
  fixtures.

### T020: Verify the MCP layer performs no statistical computation, no raw fact-table analysis, and no network/PubMed work

Purpose: preserve the Stage 3 boundary.

Guidance:

- Add static or behavioral tests appropriate to existing patterns.
- Confirm no Spearman/effective-sample/confound computation appears in MCP.
- Confirm no PubMed, HTTP, or network imports are introduced.
- Confirm the wrapper does not create an alternate direct raw fact-table analysis
  path that bypasses engine preparation.

Validation:

- Tests should fail if future changes move computation into MCP.

## Definition Of Done

- `correlate` is available on the default agent-facing surface.
- MCP delegates all analytical behavior to the engine.
- Available and refused outputs serialize correctly.
- No MCP-level statistics, network, PubMed, or causation/significance behavior.

## Risks And Review Notes

- Reviewers should reject any wrapper that computes statistics itself.
- Reviewers should check that user-facing parameter names still force a
  pre-registered hypothesis rather than inviting exploratory lag scans.
- Any warehouse reads must remain consistent with existing analytical wrappers.

## Activity Log

- 2026-05-30T15:20:16Z – claude:opus:implementer:implementer – shell_pid=92809 – Started implementation via action command
