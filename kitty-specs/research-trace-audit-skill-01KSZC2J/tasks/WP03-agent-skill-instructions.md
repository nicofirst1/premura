---
work_package_id: WP03
title: Agent Skill Instructions
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
- FR-007
- FR-011
- FR-012
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T009
- T010
- T011
- T012
history:
- timestamp: '2026-05-31T16:16:44Z'
  agent: openai:gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/skills/research-trace-audit/
execution_mode: code_change
owned_files:
- src/premura/skills/research-trace-audit/SKILL.md
tags: []
---

# Work Package Prompt: WP03 - Agent Skill Instructions

## Objective

Write the agent-facing `SKILL.md` for the Premura research trace audit skill. The skill should activate for the right requests, name required inputs clearly, and guide an agent from structured disclosure plus final answer to an actionable audit result.

## Branch Strategy

Planning artifacts were generated on `master`. Completed changes must merge back into `master`. During implementation, Spec Kitty allocates execution worktrees per computed lane from `lanes.json`; do not create your own worktree or branch manually.

Use this command for implementation after WP01 and WP02 are done:

```bash
spec-kitty agent action implement WP03 --agent <name>
```

## Authoritative Context

Read these before editing:

- `kitty-specs/research-trace-audit-skill-01KSZC2J/research/wp0-skill-research.md`
- `src/premura/skills/research-trace-audit/AUDIT_RUBRIC.md`
- `src/premura/skills/research-trace-audit/fixtures/*.json`
- `kitty-specs/research-trace-audit-skill-01KSZC2J/contracts/audit-result-contract.md`
- `src/premura/skills/parser-generator/SKILL.md` as local style reference

## Owned Files

You may create or modify only:

- `src/premura/skills/research-trace-audit/SKILL.md`

Do not edit `AUDIT_RUBRIC.md` or fixtures unless you stop and coordinate, because those belong to WP02.

## Detailed Guidance

### T009 - Author frontmatter for discoverability and invocation

Use standard skill frontmatter. The `name` should be stable and Premura-specific, for example `premura-research-trace-audit` unless WP01 recommends a different naming convention.

The `description` must make activation precise. It should trigger when the user or agent wants to audit a Premura analytical answer against a session research trace, multiplicity disclosure, or audit-consumer contract.

It should not claim to audit arbitrary agent answers. This is a Premura-specific skill first.

### T010 - Write required-input and review workflow instructions

Within the first two minutes of reading, a first-time user should be able to identify the required inputs:

- structured Session Disclosure object from `research_trace_disclosure`
- final analytical answer text

The workflow should tell the agent to:

1. verify both inputs are present
2. inspect structured counts and surfaced summary
3. inspect refusals, errors, unavailable surfaced state, and call records
4. compare final-answer claims against tool boundaries
5. emit `pass`, `needs_revision`, or `blocked`
6. include concrete evidence references for every non-pass result

Do not instruct agents to parse `disclosure_text` for counts.

### T011 - Link to rubric, fixtures, and authoritative contracts

`SKILL.md` should point to `AUDIT_RUBRIC.md` as the detailed rubric. It may cite fixture names as examples, but the rubric remains the source of criteria detail.

It should mention the audit-consumer contract path from the session trace mission and the audit-result contract in this mission.

Make the precedence clear:

- audit-consumer contract defines trace input shape
- `AUDIT_RUBRIC.md` defines audit criteria
- `SKILL.md` defines how an agent runs the skill

### T012 - Validate clarity and offline runtime behavior

Read the finished `SKILL.md` as a first-time operator.

Confirm:

- required inputs are obvious near the top
- runtime use requires no network call
- the skill does not tell agents to mutate trace storage
- the skill does not introduce p-values, significance, causation, diagnosis, treatment, or prediction as valid claims
- the skill keeps packaging guidance out of audit logic

## Validation

- Read the frontmatter against WP01's skill-format findings.
- Read the workflow against the five fixtures.
- Confirm the file can be installed as a standard skill resource by WP04.
- Confirm there is no duplicate rubric table that can drift from `AUDIT_RUBRIC.md`.

## Definition of Done

- `SKILL.md` exists with conformant frontmatter.
- Required inputs are findable in under 2 minutes.
- The skill emits or instructs a concrete audit-result shape.
- The skill stays Premura-specific and offline at runtime.

## Reviewer Guidance

Reject if `SKILL.md` is generic, if it hides the required inputs, if it duplicates the full rubric instead of linking it, or if it suggests changing trace counts.
