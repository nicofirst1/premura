---
work_package_id: WP06
title: Documentation And Validation Sync
dependencies:
- WP05
requirement_refs:
- FR-013
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During implementation this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
- T030
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/operations/STATUS.md
- docs/architecture/STAGES.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- src/premura/engine/CONTRACT.md
tags: []
---

# Work Package Prompt: WP06 - Documentation And Validation Sync

## Implement Command

```bash
spec-kitty agent action implement WP06 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Synchronize live docs and contributor guidance after the completed analytical
tool set is publicly available. This WP also records validation results for the
mission handoff. It should not change source behavior.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/plan.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/quickstart.md`
- Final public names and behavior from WP05

## Owned Files

- `docs/operations/STATUS.md`
- `docs/architecture/STAGES.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `src/premura/engine/CONTRACT.md`

Do not edit implementation code, MCP wrappers, trace logic, or tests in this WP.

## Subtasks

### T026: Sync live roadmap/status/stage docs to name the completed analytical tool set

Update live docs to reflect final behavior:

- `docs/operations/STATUS.md`: list `rolling_mean` and `paired_t_test` as shipped
  alongside the existing analytical tools once implementation is complete.
- `docs/architecture/STAGES.md`: update the default MCP surface and long-term
  surface language so these tools are no longer deferred.
- `docs/product/ROADMAP.md`: remove `rolling_mean` and `paired_t_test` from the
  open analytical-tool list and keep PubMed grounding deferred.
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`: summarize the completed tool set
  and keep later phases correctly sequenced.

Keep prose concise. Do not duplicate the full contracts in live docs.

### T027: Update the Stage 2/3 contributor contract with the new bounded tool shapes

Update `src/premura/engine/CONTRACT.md` so future agents understand how to add or
review these shapes.

The contract should state:

- `rolling_mean` is a declared-window moving summary and must not scan windows.
- `paired_t_test` in this mission means simple anchor-date before/after pairing.
- Broader condition-label pairing requires a future contract extension.
- Both tools keep the same no-diagnosis/no-causation/no-hidden-search boundary.

### T028: Add documentation checks for deferred PubMed and condition-pairing scope

Read the changed docs for accidental scope drift.

Confirm docs do not imply:

- PubMed grounding shipped in this mission.
- A teaching UI shipped in this mission.
- Nutrition/supplement intake shipped in this mission.
- `paired_t_test` supports arbitrary condition labels or pair maps.
- The tools diagnose, treat, or establish cause.

If a doc needs a brief future-work sentence, keep it short and point to the
mission contracts rather than reopening design.

### T029: Run focused validation commands and record any pre-existing unrelated failures

Run the quickstart validation commands appropriate to the final changed scope:

```bash
uv run python -m pytest tests/test_engine_analytical_tools.py -q
uv run python -m pytest tests/test_engine_analytical_inputs.py -q
uv run python -m pytest tests/test_engine_analytical_public_surface.py -q
uv run python -m pytest tests/test_mcp_analytical_tools.py tests/test_mcp_trace_recording.py tests/test_trace_store.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/premura/engine src/premura/mcp src/premura/trace.py
```

If command names differ after implementation, use the nearest focused test files
created by earlier WPs and explain the substitution in the handoff.

### T030: Prepare final mission handoff notes for review and downstream task execution

Add a concise handoff note in the WP completion result, not a new repository doc,
covering:

- Which tools now ship.
- Which validation commands passed.
- Any pre-existing unrelated failures.
- The explicit deferred work: PubMed grounding and broader condition-pairing.

Definition of done:

- Live docs accurately reflect shipped behavior.
- Contributor contract names the bounded extension rules.
- Focused validation results are recorded in the WP handoff.

## Test Strategy

This is docs/validation work. Run the commands in T029 and report results.

## Risks

- Docs can overstate what shipped. Keep PubMed and condition-label pairing
  clearly deferred.
- Rewriting large roadmap sections creates review noise. Make the smallest
  accurate updates.

## Reviewer Guidance

Review for factual synchronization, not prose preference. The key question is
whether a future agent can tell what shipped and what remains deferred.
