---
work_package_id: WP02
title: Fixtures and Bounded Rubric
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-008
- FR-009
- FR-010
- FR-011
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T005
- T006
- T007
- T008
history:
- timestamp: '2026-05-31T16:16:44Z'
  agent: openai:gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/skills/research-trace-audit/
execution_mode: code_change
owned_files:
- src/premura/skills/research-trace-audit/AUDIT_RUBRIC.md
- src/premura/skills/research-trace-audit/fixtures/**
tags: []
---

# Work Package Prompt: WP02 - Fixtures and Bounded Rubric

## Objective

Create the synthetic audit fixtures and the bounded rubric that defines how a Premura answer is audited against a session research trace disclosure.

This WP is the core audit behavior. It must follow WP01's accepted skill-authoring findings and must not change trace semantics.

## Branch Strategy

Planning artifacts were generated on `master`. Completed changes must merge back into `master`. During implementation, Spec Kitty allocates execution worktrees per computed lane from `lanes.json`; do not create your own worktree or branch manually.

Use this command for implementation after WP01 is done:

```bash
spec-kitty agent action implement WP02 --agent <name>
```

## Authoritative Context

Read these before editing:

- `kitty-specs/research-trace-audit-skill-01KSZC2J/research/wp0-skill-research.md`
- `kitty-specs/research-trace-audit-skill-01KSZC2J/data-model.md`
- `kitty-specs/research-trace-audit-skill-01KSZC2J/contracts/audit-result-contract.md`
- `kitty-specs/research-trace-audit-skill-01KSZC2J/contracts/rubric-criterion-contract.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`
- `docs/product/DOCTRINE.md`

The audit-consumer contract wins over this mission if there is a field-level disagreement.

## Owned Files

You may create or modify only:

- `src/premura/skills/research-trace-audit/AUDIT_RUBRIC.md`
- `src/premura/skills/research-trace-audit/fixtures/**`

Do not create `SKILL.md` in this WP; that belongs to WP03.

## Detailed Guidance

### T005 - Author five synthetic audit fixtures with expected verdicts first

Create these fixture files under `fixtures/`:

- `pass.json`
- `omitted-search-effort.json`
- `hidden-refusal.json`
- `surfaced-unavailable.json`
- `overclaim.json`

Each fixture should follow the data model shape:

```json
{
  "disclosure": {},
  "final_answer": "...",
  "expected_verdict": "pass|needs_revision|blocked",
  "expected_reason_categories": []
}
```

Use synthetic trace fields only. Include the structured fields the audit-consumer contract requires: `schema_version`, `session_id`, `started_at_utc`, `warehouse_fingerprint`, `raw_analytical_call_count`, `unique_hypothesis_count`, `surfaced`, `refusal_breakdown`, and `calls`.

Do not include real health data, real operator identifiers, or raw `hp.*` rows. Hashes and IDs may be obviously fake but structurally plausible.

### T006 - Write `AUDIT_RUBRIC.md` as a bounded criteria registry

Write `AUDIT_RUBRIC.md` after the fixtures exist. It should define categories and criterion rules, not a flat banned-token list.

It must cover at least these closed categories from the contract:

- `search_effort_disclosure`
- `refused_or_unavailable_handling`
- `contradiction_handling`
- `overclaim_boundary`

For each criterion, include:

- stable criterion id
- category
- review question
- evidence source
- common failure modes as examples
- suggested revision hint

Make clear that failure modes are illustrative, not exhaustive.

### T007 - Cross-check rubric criteria against contract and fixtures

For each fixture, verify the expected verdict can be reached by applying the rubric and citing concrete evidence from the fixture disclosure or answer span.

Confirm that non-pass fixtures have at least one available evidence reference:

- omitted search effort: `unique_hypothesis_count` or related disclosure field
- hidden refusal: `refusal_breakdown` or per-call `terminal_status`
- surfaced unavailable: `surfaced.status = unavailable`
- overclaim: quoted answer span versus tool semantics

Confirm `pass.json` still records that all four categories were reviewed.

### T008 - Verify fixture hygiene and trace-semantics boundaries

Check that:

- all fixtures are synthetic
- no fixture contains real health facts or PHI
- no fixture redefines `unique_hypothesis_count`
- no fixture infers surfaced count when `surfaced.status = unavailable`
- no rubric line introduces p-values, significance, multiplicity correction, causation, diagnosis, treatment, or prediction as a valid claim

## Validation

- Inspect JSON syntax for all fixtures.
- Compare fixture fields against the audit-consumer contract.
- Read `AUDIT_RUBRIC.md` against `rubric-criterion-contract.md`.
- Run formatting/lint checks relevant to changed files; if only Markdown/JSON changed, at minimum ensure files are parseable and consistently formatted.

## Definition of Done

- Five fixtures exist with expected verdicts.
- `AUDIT_RUBRIC.md` exists and satisfies guide-don't-enumerate design.
- Every fixture maps to an expected verdict through concrete evidence.
- No PHI, raw health facts, or changed trace semantics are introduced.

## Reviewer Guidance

Reject if the rubric becomes a banned-word list, if the fixtures rely on prose `disclosure_text` for counts, or if any fixture contains real operator data.
