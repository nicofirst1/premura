---
work_package_id: WP04
title: Public Surface And Contributor Contract
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-008
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
history:
- timestamp: '2026-05-29T11:59:19Z'
  agent: gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/__init__.py
- src/premura/engine/CONTRACT.md
- tests/test_engine_policy_public_surface.py
tags: []
---

# Work Package Prompt: WP04 - Public Surface And Contributor Contract

## Implement Command

```bash
spec-kitty agent action implement WP04 --agent <name>
```

## Objective

Expose the policy declaration/evaluation surface through `premura.engine` and update the Stage 2 contributor contract so future agents know how to use it.

## Context

Depends on WP01-WP03.

This WP is about discoverability and contributor guidance. It must not change existing signal behavior.

## Owned Files

- `src/premura/engine/__init__.py`
- `src/premura/engine/CONTRACT.md`
- `tests/test_engine_policy_public_surface.py`

Do not edit files outside this list.

## Subtasks

### T016: Export Public Policy Surface

Update `src/premura/engine/__init__.py` to re-export the stable policy types and evaluator helpers needed by future agents.

Guidance:

- Follow the existing explicit `__all__` style.
- Export only the intended contributor surface, not private helpers.
- Preserve lazy-load behavior for existing signals and resolvers.

### T017: Update Stage 2 Contributor Contract

Update `src/premura/engine/CONTRACT.md`.

Add guidance explaining:

- Future agents declare evidence policies through the frozen dataclass policy surface.
- Policies are family-level declarations with per-question modifiers.
- Declarations are parameters-only; no expressions, conditionals, callables, SQL, or network calls.
- PubMed MCP can support authoring/review outside runtime, but Stage 2 must not call PubMed.
- New question types or result families require a future mission.

Keep the wording aligned with `CONTEXT.md`: guide agents with bounded abstractions rather than exhaustive lists.

### T018: Add Public-Surface Tests

Create `tests/test_engine_policy_public_surface.py`.

Required tests:

- Policy enums/types can be imported from `premura.engine`.
- Evaluator helper can be imported from `premura.engine`.
- Built-in policy list/lookup can be imported from `premura.engine` if WP03 exposes it.
- Importing `premura.engine` does not perform a network call or require PubMed tooling.

### T019: Add Reviewer Guidance

Add a concise reviewer section to `CONTRACT.md` covering future policy changes.

Reviewer should check:

- Does the new policy use existing question types and rejection reasons?
- Does it avoid clinical authority claims?
- Does it keep rejection reasons distinct?
- Are PubMed/literature notes rationale only, not runtime dependencies?
- Are examples included for both admissible and refusal behavior?

## Implementation Notes

The top-level `premura.engine` surface is the contributor entrypoint. It should be explicit enough that a future agent can import the policy types without spelunking private modules.

Export guidance:

- Add policy exports to `__all__` near the existing result-envelope and input-resolution exports.
- Avoid exporting private helpers if a stable helper exists.
- Preserve the existing lazy built-in signal loading behavior.
- Do not import Stage 3 or MCP modules.

Contract documentation guidance:

- Explain why this is not YAML: no human domain reviewer reads policy files directly, and typed code-native declarations match current Stage 2 patterns.
- Explain the PubMed boundary: agent-side policy authoring/review only, never Stage 2 runtime.
- Explain policy keying: family-level declarations with per-question modifiers.
- Explain parameters-only declarations: no expressions, no callables, no hidden SQL, no network calls.
- Explain what adding a new question type means: future mission because it changes the authoring contract.

Testing guidance:

- Tests should import from `premura.engine`, not from private policy modules.
- A smoke test should confirm import does not require PubMed packages or network setup.
- If there is an easy way to monkeypatch a network sentinel, use it only at the boundary. Do not overfit tests to import internals.

## Edge Cases To Cover

- Importing `premura.engine` with policy exports still leaves signal registry lazy.
- Public exports include enough to author a policy and evaluate candidates.
- Contract text does not imply PubMed is runtime evidence.
- Contract text does not invite exhaustive metric enumeration.

## Documentation Requirements

The contract update should include a short "How to add a policy" flow for future agents:

1. Use PubMed MCP or other sources only during research/review if needed.
2. Choose an existing question type and policy shape where possible.
3. Add a family-level declaration with per-question behavior.
4. Include rationale, caveats, and examples.
5. Run the policy model, evaluator, and defaults tests.

The contract should also explicitly say what not to do:

- Do not add YAML policy files in this mission.
- Do not add runtime literature fetching.
- Do not add custom evaluator branches for one metric unless a future mission approves it.
- Do not introduce a fifth result family.

## Reviewer Checklist

- `premura.engine` exports are intentionally limited.
- `CONTRACT.md` teaches the abstraction rather than listing every metric family.
- PubMed is described as an agent review aid, not a runtime dependency.
- The public surface supports future agents without requiring private imports.
- No existing engine behavior changes are bundled into this WP.

## Common Failure Modes

- Adding broad imports that eagerly load built-in signals.
- Exporting `_model` or `_evaluator` private names instead of stable public names.
- Making the contract too abstract to guide future agents.
- Making the contract too specific by enumerating every family as if it were final.

## Suggested Test Names

- `test_policy_surface_imports_from_premura_engine`
- `test_engine_import_does_not_require_pubmed_runtime`
- `test_policy_exports_do_not_eagerly_load_signal_registry`
- `test_builtin_policy_lookup_available_from_public_surface`

## Handoff Notes For Future Agents

Future policy authors should be able to read `CONTRACT.md` and know where to start without reading the whole mission folder. If the contract still requires spelunking through `data-model.md` to understand basic policy authoring, this WP is not done.

Keep the final prose short enough to maintain, but concrete enough to prevent drift. The reference pattern is the parser contract: it does not list every vendor export, but it tells an agent exactly what shape a parser must satisfy.

## Validation Command

Run this WP's focused test first:

```bash
uv run pytest tests/test_engine_policy_public_surface.py -q
```

Then run a broader import sanity check if the implementation changed exports substantially:

```bash
uv run pytest tests/test_engine.py tests/test_engine_contract.py -q
```

## Definition Of Done

- Public imports work through `premura.engine`.
- Contract explains the new authoring pattern clearly for future agents.
- Tests verify no runtime PubMed/network dependency.
- No existing signal behavior is changed.

## Branch Strategy

Planning/base branch: `master`.
Final merge target: `master`.
Implementation worktrees are allocated later per computed lane from `lanes.json`; do not create worktrees manually.

## Reviewer Guidance

Review for surface area discipline. The public API should be useful but not expose every internal helper.
