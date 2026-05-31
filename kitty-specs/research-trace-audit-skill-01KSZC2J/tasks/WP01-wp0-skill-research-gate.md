---
work_package_id: WP01
title: WP0 Skill Research Gate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
agent: "claude:opus:planning-researcher:implementer"
shell_pid: "10688"
history:
- timestamp: '2026-05-31T16:16:44Z'
  agent: openai:gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/research-trace-audit-skill-01KSZC2J/research/
execution_mode: planning_artifact
owned_files:
- kitty-specs/research-trace-audit-skill-01KSZC2J/research/wp0-skill-research.md
tags: []
---

# Work Package Prompt: WP01 - WP0 Skill Research Gate

## Objective

Produce the mission's required WP0 research deliverable before any audit-skill implementation locks in rubric details or installation scope.

This WP exists because the maintainer explicitly corrected the scope: WP0 must research how agent skills are written in general, how skills are installed, whether a write-once packaging or library approach exists, and how that should shape this specific Premura audit skill.

## Branch Strategy

Planning artifacts were generated on `master`. Completed changes must merge back into `master`. During implementation, Spec Kitty allocates execution worktrees per computed lane from `lanes.json`; do not create your own worktree or branch manually.

Use this command for implementation:

```bash
spec-kitty agent action implement WP01 --agent <name>
```

## Authoritative Context

Read these before editing:

- `kitty-specs/research-trace-audit-skill-01KSZC2J/spec.md`
- `kitty-specs/research-trace-audit-skill-01KSZC2J/plan.md`
- `kitty-specs/research-trace-audit-skill-01KSZC2J/research.md`
- `docs/product/DOCTRINE.md`
- `CONTEXT.md` sections on maintainer mental model and planning language

The planning `research.md` contains anchor hypotheses, not final WP0 conclusions. Treat it as context to test, not as a completed research result.

## Owned Files

You may create or modify only:

- `kitty-specs/research-trace-audit-skill-01KSZC2J/research/wp0-skill-research.md`

Do not edit source code, docs, `research.md`, or later WP artifacts in this WP.

## Detailed Guidance

### T001 - Research general agent skill authoring standards and current external guidance

Find current external guidance on how agent skills are written. Use internet sources where useful. At minimum, evaluate the open Agent Skills standard referenced in planning and any per-client documentation it links to.

The deliverable must cite at least three relevant external sources, or explicitly explain why fewer authoritative sources were available. Prefer primary sources over blog posts.

Extract decision-useful guidance only:

- required file/folder shape
- expected frontmatter fields
- progressive disclosure model
- bundled resources such as references, scripts, assets, and fixtures
- what makes a skill discoverable versus what belongs in the activated instructions

Avoid turning this into a long generic literature review.

### T002 - Research local skill discovery and installation patterns

Research where locally-installed skills are discovered for Claude-style and OpenCode-style environments. Confirm the path and verification mechanism from current sources instead of relying on memory.

For each target, capture:

- installation home or scan path
- whether repo-local skills are supported
- whether global/user-level skills are supported
- how the user or reviewer can verify discovery locally
- any naming or metadata requirements that differ from the standard

If an environment's path is unclear, state that plainly and recommend defer rather than guessing.

### T003 - Evaluate write-once packaging or installer approaches

Evaluate whether this mission should adopt, defer, or reject a write-once packaging/install approach.

The leading planning hypothesis is: the skill content should be write-once by conforming to the Agent Skills standard, while installer behavior may need multiple target paths. Validate or reject that hypothesis.

The recommendation must be one of:

- `adopt`: implement additional installer support in WP04
- `defer`: document the additional target but do not implement now
- `reject`: keep only existing Claude-style install support for this mission

Include tradeoffs for blast radius, local-first behavior, maintenance burden, and reviewer verification.

### T004 - Translate findings into Premura-specific rules

End the deliverable with concrete rules for this audit skill:

- what `SKILL.md` frontmatter should emphasize
- what should live in `SKILL.md` versus `AUDIT_RUBRIC.md`
- how fixtures should be packaged
- which installation targets are in scope for this mission
- what checks later WPs should run to verify install behavior

Tie these rules to Premura constraints: local-first runtime, no PHI in fixtures, no changed trace semantics, and guide-don't-enumerate rubric design.

## Required Output Shape

Create `research/wp0-skill-research.md` with these sections:

- `# WP0 Skill Research`
- `## Sources`
- `## Skill Authoring Findings`
- `## Installation Findings`
- `## Packaging Recommendation`
- `## Premura-Specific Rules`
- `## Follow-On Scope for WP04`

Keep the main body to no more than 1,500 words excluding citations and appendices.

## Validation

- The file exists at the owned path.
- It cites at least three relevant external sources, or explains why fewer authoritative sources were available.
- It gives a clear adopt/defer/reject recommendation.
- It names a locally-verifiable check for every supported install target.
- It explicitly says ordinary audit execution must remain offline.

## Research Quality Bar

This WP is successful only if the output changes what later agents can safely do. A list of links is not enough. Each cited source should be converted into a planning consequence.

For every important source, ask:

- What does this source say a skill must contain?
- What does this source say a client discovers automatically?
- What is specific to one client versus portable across skill-compatible agents?
- What would break if Premura assumed this behavior incorrectly?
- How can a reviewer verify the finding locally?

Use plain English. The maintainer is technical but does not want tool-ecosystem jargon without a short explanation.

## Expected Decision Granularity

The final recommendation should be specific enough for WP04 to act without another research pass.

Good examples:

- `adopt`: "Add target X because client docs say repo-local skills live at Y; verification is command Z or file inspection Q."
- `defer`: "The standard supports write-once content, but client X's local path is not stable enough; keep skill content portable and revisit installer later."
- `reject`: "Client X does not load local skills in a way Premura can verify; adding installer code would create dead files."

Bad examples:

- "Maybe support OpenCode later."
- "There are many ways to install skills."
- "Use the standard" without naming what that means for files in this repo.

## Integration Points For Later WPs

WP02 needs to know whether fixtures and rubric should follow a standard resource layout. WP03 needs to know what frontmatter and description style improves skill discovery. WP04 needs the exact installation decision. If your output does not answer all three, it is incomplete.

## Stop Conditions

Stop and surface a blocker if:

- current internet sources contradict the planning assumption that Agent Skills are folder-based with `SKILL.md`
- no authoritative source can confirm an OpenCode-style local skill home
- a target requires network-backed installation or a package registry, because this mission needs local-first behavior
- a suggested packaging library would own more scope than this mission can review safely

If blocked, still write the research artifact with the blocker and a conservative recommendation.

## Definition of Done

- `research/wp0-skill-research.md` is complete and decision-ready.
- Downstream WPs can tell whether OpenCode-style installer support should be implemented.
- The deliverable does not modify implementation artifacts.

## Reviewer Guidance

Reviewers should reject this WP if it merely repeats `research.md`, if it does not use current external sources, or if it makes an installer recommendation without a local verification check.

## Activity Log

- 2026-05-31T16:25:42Z – claude:opus:planning-researcher:implementer – shell_pid=10688 – Assigned agent via action command
