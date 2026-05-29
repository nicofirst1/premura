# Quickstart: Stage 3 Analytical Tools

This quickstart is for implementers after `/spec-kitty.tasks` creates work
packages. Do not start implementation directly from this plan.

## Preconditions

- Read `kitty-specs/stage-3-analytical-tools-01KST48C/spec.md`.
- Read `kitty-specs/stage-3-analytical-tools-01KST48C/plan.md`.
- Read `kitty-specs/stage-3-analytical-tools-01KST48C/research.md`.
- Read `src/premura/engine/CONTRACT.md`.
- Confirm the implementation worktree is created by Spec Kitty later; planning
  happens in the project root only.

## Implementation Order

1. Write or update the analytical-depth research note if the assigned work
   package covers Phase 0.
2. Add failing public-surface tests for the assigned behavior.
3. Implement the smallest engine/MCP change needed to pass those tests.
4. Keep default MCP wrappers thin: no raw fact-table SQL and no statistical logic
   in wrappers.
5. Keep runtime local-first: no network calls.
6. Run the relevant fast tests first, then the full quality gate.

## Suggested Verification Commands

Run relevant subsets while developing:

```bash
pytest tests/test_engine_analytical_contract.py -q
pytest tests/test_engine_analytical_tools.py -q
pytest tests/test_mcp_analytical_tools.py -q
```

Before review handoff:

```bash
ruff check .
ruff format --check .
mypy src
pytest -q
```

If a command exposes pre-existing unrelated failures, record them in the work
package result instead of hiding them.

## Review Checklist

- Tests were written before production code for new behavior.
- Assertions use public engine/MCP surfaces where possible.
- No real private health artifacts were added.
- `change_point` is not a Stage 2 `change` family signal.
- Smoothed average does not imply prediction, causation, or significance.
- Every non-refusal analytical result includes validity/confound metadata.
- Every refusal has a distinct machine-readable reason and no estimate.
