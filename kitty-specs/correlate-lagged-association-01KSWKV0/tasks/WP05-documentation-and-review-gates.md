---
work_package_id: WP05
title: Documentation And Review Gates
dependencies:
- WP04
requirement_refs:
- FR-018
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
agent: "claude:opus:implementer:implementer"
shell_pid: "8426"
history:
- 2026-05-30T14:27:30Z tasks generated for correlate lagged association mission
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- src/premura/engine/CONTRACT.md
- docs/operations/STATUS.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- docs/adr/0008-correlate-pre-registered-lagged-association.md
tags: []
---

# WP05: Documentation And Review Gates

## Objective

Synchronize documentation after `correlate` ships and verify changed-scope gates.
This WP must state what landed and what remains deferred without reopening the
method decisions from ADR-0008 and the research note.

## Branch Strategy

Planning/base branch is `master`. Final merge target is `master`. Do not create a
manual worktree. Spec Kitty will allocate execution worktrees per computed lane
from `lanes.json` after task finalization.

Implementation command:

```bash
spec-kitty agent action implement WP05 --agent <name>
```

## Context

Depends on WP04. Do not update docs to claim runtime behavior is shipped until
the default surface exists. Keep docs agent-first and at doctrine altitude: rules
and seams, not a catalog of metric pairs or plausible causes.

## Subtasks

### T021: Update engine and analytical contributor docs for lag, association, paired inputs, and confound rules

Purpose: help future agents extend/review analytical tools without re-deciding
`correlate`.

Guidance:

- Update `src/premura/engine/CONTRACT.md`.
- Explain that `correlate` is association-only and pre-registered.
- Explain that lag is a caller-specified whole-day offset, not timestamp
  tolerance.
- Explain the paired-input seam and overlap narrowing.
- Explain `common_cause_plausible` as a rule-shaped confound, not a cause list.
- Keep PubMed/literature as authoring/review context only, never runtime.

Validation:

- Docs include no p-value/significance/causal framing.

### T022: Update product/status roadmap docs to show `correlate` shipped and ledger/PubMed still deferred

Purpose: keep roadmap/status truthful after implementation.

Guidance:

- Update `docs/operations/STATUS.md` to describe `correlate` once it is on the
  default surface.
- Update `docs/product/ROADMAP.md` and
  `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so `correlate` is no longer listed
  as still open.
- Keep `paired_t_test`, `rolling_mean`, PubMed grounding, reproducible research
  traces, and session ledger/audit trace deferred unless another WP actually
  ships them.

Validation:

- Status and roadmap agree with each other.
- No future work is accidentally marked shipped.

### T023: Add the ADR-0008 back-pointer that `common_cause_plausible` was resolved by the research note

Purpose: remove ambiguity noted during specify.

Guidance:

- Update `docs/adr/0008-correlate-pre-registered-lagged-association.md` only as
  a status/back-pointer clarification.
- State that the implementation research resolved the open confound-key question
  as `common_cause_plausible`.
- Do not rewrite ADR-0008's locked decisions.

Validation:

- ADR remains an architecture/honesty contract and points readers to the research
  note for statistical choices.

### T024: Run changed-scope documentation and quality-gate checks, recording any pre-existing unrelated failures

Purpose: close the mission honestly.

Guidance:

- Run the changed-scope tests listed in quickstart and any broader tests needed
  for touched files.
- Run `uv run ruff check .` and `uv run ruff format --check .` if feasible.
- Run `uv run mypy src/premura/engine src/premura/mcp` if feasible.
- If pre-existing unrelated failures remain, record them in the WP handoff with a
  one-line rationale.
- Do not hide skipped checks.

Validation:

- Handoff names exact commands and outcomes.

## Definition Of Done

- Engine contract docs explain how to review/extend `correlate`.
- Product/status docs agree about shipped and deferred analytical work.
- ADR-0008 points to the resolved confound-key research decision.
- Changed-scope quality gates are run or explicitly explained.

## Risks And Review Notes

- Watch for docs saying `correlate` proves cause or significance.
- Watch for docs implying the session ledger or PubMed grounding shipped.
- Watch for exhaustive metric-pair lists; the rule is the design, not examples.

## Activity Log

- 2026-05-30T15:39:46Z – claude:opus:implementer:implementer – shell_pid=8426 – Started implementation via action command
- 2026-05-30T15:47:36Z – claude:opus:implementer:implementer – shell_pid=8426 – Ready for review: synced docs to correlate-shipped truth (CONTRACT.md analytical/correlate section, STATUS/ROADMAP/PLAN show correlate SHIPPED + 13-tool surface + 554 tests, ledger/PubMed kept DEFERRED, ADR-0008 common_cause_plausible back-pointer); gates run, full suite 554 green
