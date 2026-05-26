---
work_package_id: WP01
title: Engine Seam And Contributor Contract
dependencies: []
requirement_refs:
- FR-005
- FR-006
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-grounded-stage-2-functions-01KSHZPC
base_commit: 81022fcda1a4b14c1f84b658248886adecb67f6f
created_at: '2026-05-26T11:44:18.209297+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
shell_pid: '66395'
history:
- timestamp: '2026-05-26T11:32:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/_registry.py
- src/premura/engine/__init__.py
- src/premura/engine/_results.py
- src/premura/engine/CONTRACT.md
- src/premura/parsers/CONTRACT.md
- tests/test_engine_contract.py
tags: []
---

# Work Package Prompt: WP01 - Engine Seam And Contributor Contract

## Objective

Make the Stage 2 seam more contributor-ready without redesigning the registry or taking on the deferred profile-data problem.

This WP is the load-bearing foundation for the rest of the mission. The six new Stage 2 answers should land on top of a seam that future contributors and agents can understand, extend, and review through normal PRs.

## Owned Surface

- `src/premura/engine/_registry.py`
- `src/premura/engine/__init__.py`
- `src/premura/engine/_results.py`
- `src/premura/engine/CONTRACT.md`
- `src/premura/parsers/CONTRACT.md`
- `tests/test_engine_contract.py`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP01 --agent <name>`

## Subtasks

### T001 - Add contributor-ready Stage 2 registry metadata

**Purpose**

Extend the Stage 2 registry surface just enough that future contributors can declare what a signal answers and how Stage 3 should surface caveats, while keeping the current registry semantics intact.

**Required changes**

- Update `src/premura/engine/_registry.py` additively.
- Preserve the existing core registration contract: `name`, `domain`, `inputs`, `output`, `priority`, `auto_safe`, `revision`, `fn`.
- Add only the minimum new metadata needed for future grounded Stage 2 extensions. The planning docs expect support for:
  - the plain-English question the signal answers
  - the result family it belongs to (`status`, `trend`, `baseline`, `change`)
  - a user-facing hint for missing inputs
  - a short caveat summary that Stage 3 can expose without inventing health claims
- Keep duplicate-name behavior aligned with the current registry model unless a spec-level reason demands otherwise.

**Constraints**

- Do not add profile-precondition support here.
- Do not add a plugin loader or manifest system.
- Do not make the registry depend on MCP code.

**Validation expectations**

- Existing built-in lab-ratio registrations remain valid.
- New metadata is optional where appropriate so current registrations do not need fragile churn.

### T002 - Add shared Stage 2 result-envelope helpers

**Purpose**

Give the six new functions a consistent output vocabulary so Stage 3 wrappers do not have to reverse-engineer ad-hoc dicts.

**Required changes**

- Add `src/premura/engine/_results.py`.
- Implement the four shared logical result families from planning:
  - status
  - trend
  - own-baseline comparison
  - change-around-date
- Keep the result helpers easy to serialize into MCP responses.
- Include explicit support for:
  - freshness state
  - caveat lists
  - missing/sparse-data refusal states
  - counts or point lists where the family needs them

**Design guidance**

- Prefer simple typed structures or clear helper constructors.
- Avoid over-generalizing into one giant catch-all object.
- Keep names plain and aligned with `data-model.md`.

### T003 - Update lazy built-in loading

**Purpose**

Ensure the engine can load built-in signal modules beyond `lab_ratios.py` without losing the current import-safety and open-boundary behavior.

**Required changes**

- Update `src/premura/engine/__init__.py` so built-in signal loading can encompass the upcoming non-lab modules.
- Preserve the current guarantee that importing `premura.engine` alone does not eagerly load signal implementations.
- Keep current lab-ratio discovery working.

**Design guidance**

- Do the smallest thing that works.
- Avoid filesystem scanning.
- A static list of built-in modules or another low-risk additive mechanism is preferred over clever discovery.

### T004 - Add an engine-side contributor contract

**Purpose**

Turn the research findings into a shipped contributor guide so future agents and contributors know how to extend Stage 2 safely.

**Required changes**

- Add `src/premura/engine/CONTRACT.md`.
- Cover the parts of the research that matter for contributors:
  - what kinds of Stage 2 functions belong here
  - what evidence basis is expected
  - what caveats must be named
  - what Stage 2 must not claim
  - what tests and review notes a contributor should include
- Update `src/premura/parsers/CONTRACT.md` with a short sibling pointer so agent readers can discover the engine-side contract from the already-shipped parser surface.

**Constraints**

- Do not restate the whole research document verbatim.
- Do not imply a third-party plugin system decision.
- Do not describe profile-dependent functions as supported.

### T005 - Add seam and contract tests

**Purpose**

Lock the extension surface before signal implementation begins.

**Required changes**

- Add `tests/test_engine_contract.py`.
- Cover:
  - the additive registry metadata contract
  - the importability of the result-helper surface
  - lazy built-in loading still behaving correctly
  - the existence of the engine contributor contract and the parser-contract pointer
- Assert through public imports and observable behavior where possible.

**Testing stance**

- Follow the repo's test-first rule.
- Keep the tests focused on the extension surface, not future signal behavior.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest tests/test_engine_contract.py -q
uv run python -c "from premura.engine import REGISTRY; print(len(REGISTRY))"
```

Expected outcomes:

- The engine still imports cleanly.
- Result-envelope helpers are importable.
- Built-in loading stays lazy.
- The new engine-side contract exists and is discoverable from the parser-side contract.

## Definition Of Done

- The Stage 2 registry is additively more contributor-ready.
- Shared result envelopes exist for the four planned signal families.
- Lazy built-in loading supports the later signal WPs.
- The engine contributor contract is shipped and linked from the parser contract.
- Focused seam tests pass.

## Risks And Watchouts

- The easiest mistake is to over-engineer the seam and create a second system that later WPs have to work around.
- Another common mistake is to make the new metadata mandatory and accidentally churn the existing built-in lab-ratio registrations.

## Reviewer Guidance

Review this WP against the research findings and `data-model.md`, not against imagined future needs. The seam should be clearly better for contributors, but still simple, local-first, and compatible with the current engine model.
