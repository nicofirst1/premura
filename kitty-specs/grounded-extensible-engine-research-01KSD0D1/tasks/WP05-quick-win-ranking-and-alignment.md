---
work_package_id: WP05
title: Quick-Win Ranking And Alignment
dependencies:
- WP01
- WP02
- WP04
requirement_refs:
- FR-008
- FR-009
- FR-010
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-24T13:02:16Z'
subtasks:
- T018
- T019
- T020
- T021
- T022
agent: "claude:opus:research-reviewer:reviewer"
shell_pid: "67798"
history:
- timestamp: '2026-05-24T13:02:16Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/
execution_mode: planning_artifact
owned_files:
- kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/05-quick-win-ranking-and-alignment.md
tags: []
---

# Work Package Prompt: WP05 - Quick-Win Ranking And Alignment

## Objective

Turn the earlier research framework into a decision-ready shortlist of quick-win engine functions, plus the recommended next mission order and doc-alignment list.

The output is `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/05-quick-win-ranking-and-alignment.md`.

## Why This WP Exists

The mission should not end as pure meta-work. It must identify what Premura should build next, using data many people already have when possible, and it must say which docs will need alignment after those conclusions are accepted.

This WP directly supports:

- `FR-008`
- `FR-009`
- `FR-010`
- `NFR-002`
- `NFR-004`
- `NFR-005`

## Owned Surface

- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/05-quick-win-ranking-and-alignment.md`

Do not modify files outside this list.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP05 --agent <name>`

Do not start until WP01, WP02, and WP04 are available.

## Required Inputs

- `research/01-repo-baseline.md`
- `research/02-stage2-taxonomy.md`
- `research/04-engine-seam-and-profile-dependency.md`
- `docs/operations/STATUS.md`
- `src/premura/dim_metric.yaml`

## Subtasks

### T018 - Build the quick-win candidate pool

**Purpose**

Generate the set of plausible early functions before ranking them.

**Required work**

- Bias the candidate set toward data already visible in shipped sources and ontology coverage.
- Prefer ideas usable with common data such as steps, weight, height, heart rate, and similar widely available observations when present.
- Include only candidates that clearly belong in Stage 2.

### T019 - Score the candidates

**Purpose**

Make the ranking transparent rather than intuitive.

**Required work**

- Score candidates against:
  - user value
  - input availability
  - scientific clarity
  - caveat burden
  - Stage 2 fit
  - dependency on baseline profile attributes
- Keep the scoring understandable and reproducible.

### T020 - Rank 3 to 7 quick wins

**Purpose**

Produce the shortlist the maintainer can act on next.

**Required work**

- Rank between 3 and 7 candidates.
- For each candidate include:
  - short rationale
  - required inputs
  - confidence level (`strong`, `moderate`, or `exploratory`)
  - scientific caveats
  - profile-data dependency, if any

### T021 - Recommend the next mission sequence

**Purpose**

Translate the ranking into a practical follow-on order.

**Required work**

- Say which next steps should be implementation missions.
- Say which questions still need research.
- Say which items should remain deferred for now.

### T022 - Name the docs that need alignment

**Purpose**

Make the doc-sync work explicit so repo intent stays aligned with the research conclusions.

**Required work**

- Name the specific docs that should be updated after acceptance.
- Explain why each one needs an update.
- Keep the list focused on docs materially affected by the mission's conclusions.

## Validation Strategy

This WP is complete when:

- `research/05-quick-win-ranking-and-alignment.md` exists.
- It contains a ranked shortlist of 3 to 7 candidates.
- Each shortlisted candidate includes rationale, confidence, caveats, inputs, and profile-data dependency.
- The artifact ends with follow-on mission order and doc-alignment recommendations.

## Definition Of Done

- Candidate pool generated.
- Scoring method documented.
- Ranked shortlist produced.
- Next mission order written.
- Doc-alignment list written.

## Risks And Watchouts

- The shortlist may prefer easy math over useful and grounded functions.
- The mission order may ignore unresolved profile-data dependencies unless they are made explicit.

## Reviewer Guidance

- Check that at least two shortlisted candidates are useful with commonly available non-lab data.
- Check that the ranking is evidence-backed and not arbitrary.
- Check that the doc update list is concrete and scoped.

## Activity Log

- 2026-05-24T13:30:17Z – claude:opus:research-implementer:implementer – shell_pid=52169 – Started implementation via action command
- 2026-05-24T13:33:44Z – claude:opus:research-implementer:implementer – shell_pid=52169 – Ready for review: scored candidate pool, ranked 3-7 quick wins with confidence tags, next-mission sequence, doc-alignment list
- 2026-05-24T13:34:13Z – claude:opus:research-reviewer:reviewer – shell_pid=67798 – Started review via action command
