---
work_package_id: WP03
title: Agent-Mediated Profile Capture Surface
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-27T14:35:44Z'
subtasks:
- T009
- T010
- T011
- T012
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "227"
history:
- timestamp: '2026-05-27T14:35:44Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- src/premura/cli.py
- tests/test_profile_capture_tools.py
tags: []
---

# Work Package Prompt: WP03 - Agent-Mediated Profile Capture Surface

## Objective

Expose the bounded profile capture workflow through Premura's actual runtime
surface: the default agent-safe MCP interface, with CLI as a fallback/testing
mirror.

This WP is where the corrected doctrine becomes visible in code. The agent should
be able to:

- discover the supported profile fields,
- write a bounded capture session,
- get explicit rejection for unsupported fields.

## Owned Surface

- `src/premura/mcp/server.py`
- `src/premura/mcp/entrypoint.py`
- `src/premura/cli.py`
- `tests/test_profile_capture_tools.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Dependencies: `WP02`
- Implementation command: `spec-kitty agent action implement WP03 --agent <name>`

## Context

The repo already treats the MCP surface as the default analytical interface.
This mission extends that stance to stable profile capture.

The planning contract defines two tool-level operations:

- `profile_context_supported_fields`
- `profile_context_record`

The CLI wrappers exist only so tests and expert fallback use can hit the same
behavior without a separate implementation path.

## Subtasks

### T009 - Add MCP server helpers for bounded profile capture

**Purpose**

Publish the new profile capture operations through the runtime helper layer.

**Required changes**

- Update `src/premura/mcp/server.py`.
- Add helpers that:
  - return the supported profile schema/allowlist
  - record a bounded profile capture session
- Delegate validation and persistence to the store layer rather than duplicating
  it in MCP code.

### T010 - Register the tools on the default agent-safe MCP surface

**Purpose**

Make the default agent-facing server the primary runtime path for profile
capture.

**Required changes**

- Update `src/premura/mcp/entrypoint.py`.
- Register the new profile tools on the default surface, not only on an
  operator-only surface.
- Keep them consistent with the naming and style of the existing MCP tools.

### T011 - Add thin CLI fallback commands

**Purpose**

Provide a narrow expert/testing entry path that mirrors MCP behavior.

**Required changes**

- Update `src/premura/cli.py`.
- Add commands that mirror:
  - listing the supported profile schema
  - recording profile assertions
- Keep the CLI wrappers thin: they should call into the same runtime behavior as
  MCP, not fork the logic.

### T012 - Add black-box capture-surface tests

**Purpose**

Verify the public surfaces behave the way the mission requires.

**Required changes**

- Add `tests/test_profile_capture_tools.py`.
- Drive the runtime through public MCP/CLI-facing behavior.
- Cover at least:
  - listing supported fields
  - recording `birth_date`, `sex`, `standing_height_cm`
  - explicit rejection of `age`
  - inspectable response structure for stored vs rejected assertions

**Testing guidance**

- Keep the tests black-box: assert on returned data and stored row effects, not
  private helper internals.

## Validation Strategy

Primary checks for this WP:

```bash
pytest -q tests/test_profile_capture_tools.py
```

Expected outcomes:

- The default agent-safe MCP surface exposes the new profile operations.
- The CLI mirrors the same bounded behavior.
- Unsupported fields fail explicitly.

## Definition Of Done

- Agent-safe MCP tools exist for profile schema discovery and record write.
- CLI fallback wrappers exist and mirror the MCP behavior.
- Public-surface tests cover happy path and unsupported-field rejection.

## Risks And Watchouts

- The main risk is accidentally making CLI the primary implementation path.
- Another risk is duplicating validation in multiple layers, which would drift.
- Avoid returning vague success responses that hide rejected assertions.

## Reviewer Guidance

Review this WP as a runtime-surface change.

Ask:

1. Is the default runtime path clearly MCP-first?
2. Does the CLI stay thin and derivative?
3. Are unsupported fields rejected visibly rather than ignored?

## Activity Log

- 2026-05-27T14:35:44Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T15:10:29Z – claude:opus:python-implementer:implementer – shell_pid=62537 – Started implementation via action command
- 2026-05-27T15:18:41Z – claude:opus:python-implementer:implementer – shell_pid=62537 – Ready for review: agent-mediated bounded profile capture (MCP profile_context_supported_fields + profile_context_record on default surface, thin CLI mirror, store-delegated allowlist enforcement)
- 2026-05-27T15:19:10Z – claude:opus:python-reviewer:reviewer – shell_pid=227 – Started review via action command
- 2026-05-27T15:22:49Z – claude:opus:python-reviewer:reviewer – shell_pid=227 – Review passed: profile_context_supported_fields + profile_context_record live on default agent surface (build_server->_register_default_tools, entrypoint.py:202); writable opener (read_only=False) distinct from read-only analytical opener; delegates to WP02 store with source_kind=agent_profile_capture; allowlist/type enforced at store boundary (age + wrong-type + bad-enum rejected, nothing written); thin CLI mirror; 13 black-box tests incl. live-entrypoint reachability asserting a real row; out-of-scope test edits are constant-only (2 tool names added to snapshots); 260 pytest passed; WP03 files ruff-clean, no new E501.
