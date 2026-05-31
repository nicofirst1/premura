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
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-research-trace-audit-skill-01KSZC2J
base_commit: c34d53a586923cf86618cd761c286ae6fde350e2
created_at: '2026-05-31T16:31:20.474918+00:00'
subtasks:
- T005
- T006
- T007
- T008
shell_pid: "21852"
agent: "claude:opus:python-reviewer:reviewer"
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

## Fixture Design Notes

The fixtures are the test-first surface for a prose skill. Treat expected verdicts as the red tests and the rubric as the artifact that turns them green.

Each fixture should be small enough for a reviewer agent to read in one pass, but complete enough to exercise the relevant contract fields. Do not add sprawling call histories when one or two representative calls prove the point.

Recommended fixture intent:

- `pass.json`: includes search-effort disclosure, available surfaced marks, no hidden refusals, and cautious wording.
- `omitted-search-effort.json`: final answer presents a finding but omits the denominator or search-effort framing.
- `hidden-refusal.json`: trace includes a refused call relevant to the answer, and prose hides it.
- `surfaced-unavailable.json`: trace has calls but no surfaced marks; answer behaves as if surfaced count were known.
- `overclaim.json`: answer turns association or change into cause, diagnosis, treatment, prediction, or unsupported certainty.

## Rubric Design Notes

`AUDIT_RUBRIC.md` should be useful to an agent, not just acceptable to a reviewer. Prefer criterion questions that force the agent to look at structured evidence.

Good criterion style:

- "Does the answer disclose `unique_hypothesis_count` or equivalent search effort when it presents selected findings?"
- "If `surfaced.status = unavailable`, does the answer avoid implying a known surfaced count?"
- "Does the answer frame association as association rather than cause?"

Bad criterion style:

- "Flag the word significant."
- "Never say caused."
- "Check if the answer sounds honest."

The issue is not one word; it is whether a claim exceeds the structured evidence.

## Contract Boundaries To Preserve

The audit skill consumes the trace; it does not repair the trace. Do not add fixture fields that imply the skill can set `surfaced` marks or recompute `unique_hypothesis_count`.

The trace's rendered `disclosure_text` may appear as a convenience field, but fixture expectations must be grounded in structured fields. If you include `disclosure_text`, add a comment-like field or README note explaining it is not authoritative for counts.

The rubric may suggest opening an issue or revising prose, but it must not suggest changing trace storage as the ordinary fix for an answer problem.

## Stop Conditions

Stop and ask for review if the audit-consumer contract lacks a field you need for the rubric. Do not invent a new required disclosure field in fixtures without explicit approval, because that would silently change the upstream trace contract.

## Definition of Done

- Five fixtures exist with expected verdicts.
- `AUDIT_RUBRIC.md` exists and satisfies guide-don't-enumerate design.
- Every fixture maps to an expected verdict through concrete evidence.
- No PHI, raw health facts, or changed trace semantics are introduced.

## Reviewer Guidance

Reject if the rubric becomes a banned-word list, if the fixtures rely on prose `disclosure_text` for counts, or if any fixture contains real operator data.

## Activity Log

- 2026-05-31T16:31:21Z – claude:opus:python-implementer:implementer – shell_pid=17596 – Assigned agent via action command
- 2026-05-31T16:37:11Z – claude:opus:python-implementer:implementer – shell_pid=17596 – Ready for review: 5 synthetic fixtures + bounded rubric
- 2026-05-31T16:37:40Z – claude:opus:python-reviewer:reviewer – shell_pid=21852 – Started review via action command
- 2026-05-31T16:42:04Z – claude:opus:python-reviewer:reviewer – shell_pid=21852 – Review cycle 1: calls_truncated=false inconsistent with subset calls list in 4/5 fixtures
