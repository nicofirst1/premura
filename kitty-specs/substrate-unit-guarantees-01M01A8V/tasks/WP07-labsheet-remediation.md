---
work_package_id: "WP07"
title: "Labsheet remediation: one-shot delete script + runtime procedure"
dependencies:
  - "WP05"
requirement_refs:
  - "FR-009"
planning_base_branch: "master"
merge_target_branch: "master"
branch_strategy: "Planning artifacts were generated on master; completed changes must merge back into master."
owned_files:
  - "ops/delete_labsheet_rows.sql"
  - "docs/operating/RUNTIME_AGENT.md"
subtasks:
  - "T020"
  - "T021"
phase: "Phase 4 - Remediation"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2026-08-15T00:00:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP07 – Labsheet remediation mechanism

## Objective

Ship the mechanism (not the execution): a reviewed one-shot SQL file deleting the incident's `source_kind='labsheet'` rows, and the runtime-agent procedure that replaces the bypass. Execution happens post-merge on the operator machine.

## Read first

`kitty-specs/substrate-unit-guarantees-01M01A8V/{research.md,contracts/ingest-row-tool.md}`; `docs/operating/RUNTIME_AGENT.md` (esp. the improvement-candidates section); `src/premura/store/UPDATE_STRATEGY.md` (why this is NOT a migration).

## Subtasks

- **T020**: `ops/delete_labsheet_rows.sql` — comment block naming the incident and the rule (rows written outside the sanctioned seam under an unregistered source kind are removed, then re-entered through the paved road); a dry-run `SELECT COUNT(*)` companion query FIRST; then DELETEs for `hp.fact_measurement` rows tied to the labsheet source kind plus any matching `hp.dim_source`/`hp.ingest_run` bookkeeping (write the DELETEs defensively — the bypass may not have created descriptor rows at all; verify both shapes).
- **T021**: `docs/operating/RUNTIME_AGENT.md` — new subsection "Getting one-off / manually-transcribed data in": use `ingest_row` (`suggest_metric` → `load`, provenance required); state plainly that opening or writing the warehouse file directly is out of bounds for a runtime agent, no exceptions, regardless of dataset size; recurring formats still deserve a build-and-use parser (unchanged policy, cite it).

## Done criteria

`bash ops/lint_docs.sh` passes; SQL file reviewed (no pytest for a hand-run one-shot); doc diff carries the explicit "never write the warehouse file directly" sentence.

## Constraints

NOT a numbered migration (C-002). No PHI: the script references the source-kind string, never data values. Doc prose minimal — this repo's agent-docs bar.
