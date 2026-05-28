---
work_package_id: WP01
title: Repo Baseline Inventory
dependencies: []
requirement_refs:
- FR-001
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-24T13:02:16Z'
subtasks:
- T001
- T002
- T003
- T004
agent: "claude:opus:research-reviewer:reviewer"
shell_pid: "41936"
history:
- timestamp: '2026-05-24T13:02:16Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/
execution_mode: planning_artifact
owned_files:
- kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/01-repo-baseline.md
tags: []
---

# Work Package Prompt: WP01 - Repo Baseline Inventory

## Objective

Produce the source-backed baseline artifact that future research work can trust. This WP answers one question: what has Premura already committed about Stage 2, what is explicitly temporary debt, and what is still open design space?

The output is a planning artifact, not code: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/01-repo-baseline.md`.

## Why This WP Exists

Every later WP depends on an honest baseline. If this mission starts from imagined architecture instead of shipped behavior and current docs, the grounding rubric, seam evaluation, and quick-win ranking will all drift.

This WP directly supports:

- `FR-001` by producing the source-backed Stage 2 baseline inventory
- later WPs by naming the source set and the terminology they should reuse

## Owned Surface

- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/01-repo-baseline.md`

Do not modify files outside this list.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP01 --agent <name>`

Stay inside the execution worktree that Spec Kitty assigns for this WP. Do not create manual branches or worktrees.

## Context You Must Use

Primary repo sources for this WP:

- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/spec.md`
- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/plan.md`
- `CONTEXT.md`
- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- `docs/history/product/VISION.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/operations/STATUS.md`
- `docs/adr/0002-mcp-local-warehouse-boundary.md`
- `src/premura/engine/__init__.py`
- `src/premura/engine/_registry.py`

Work from shipped intent and shipped code first. Treat roadmap prose as useful only when it does not conflict with shipped docs or code.

## Subtasks

### T001 - Compile the authoritative Stage 2 source set

**Purpose**

Create the explicit list of repo materials that define the current Stage 2 picture.

**Required work**

- Read the Stage 2 docs and code named in `plan.md`.
- Record each source in the artifact with one short note explaining why it matters.
- Separate authoritative sources from supporting or historical context.

**Expected output shape**

- A short "Sources used" section near the top of `01-repo-baseline.md`.
- One-line role notes, not long summaries.

**Watchouts**

- Do not treat old roadmap ideas as equal to shipped boundaries.
- Do not pull in unrelated Stage 1 or Stage 4 details unless they directly affect Stage 2 framing.

### T002 - Separate stable commitments, known debt, and open questions

**Purpose**

Build the inventory that later WPs will rely on.

**Required work**

- Create three clearly labeled sections or one clearly structured comparison:
  - stable commitments
  - known debt / temporary exceptions
  - open design questions
- Stable commitments should include what Stage 2 is for, how it relates to Stage 3 and Stage 4, and what kinds of responsibilities are already assigned to it.
- Known debt must include the documented direct-read MCP exception while Stage 2 remains thin.
- Open questions should include contribution shape, evidence rules, and profile-data dependency where appropriate.

**Acceptance cues**

- A future reader should be able to point to one bullet and say "this is already committed" versus "this is still undecided".

### T003 - Capture terminology drift and normalize vocabulary

**Purpose**

Prevent later WPs from mixing product, architecture, and research terms inconsistently.

**Required work**

- Compare terms across `CONTEXT.md`, product docs, and engine docs.
- Note any drift or ambiguity relevant to this mission, especially around:
  - health direction
  - signal
  - derived signal
  - engine function
  - contribution contract
- Choose the plain-English wording this mission should reuse.

**Constraints**

- Follow `CONTEXT.md` and avoid unnecessary software-process jargon.
- This is not a glossary rewrite for the whole repo; only note the drift that matters for this mission.

### T004 - Draft the baseline artifact

**Purpose**

Turn the prior research into the reusable baseline document for downstream WPs.

**Required work**

- Write `research/01-repo-baseline.md`.
- Include:
  - concise source list
  - stable commitments
  - known debt / temporary exceptions
  - open design questions
  - terminology notes
- Add citations or inline file references wherever a top-level claim depends on a repo source.

**Definition of good output**

- Short, navigable, and citation-backed.
- Strong enough that WP02-WP05 can cite it instead of repeating all baseline evidence.

## Validation Strategy

This WP is complete when:

- `research/01-repo-baseline.md` exists.
- It clearly separates stable intent, debt, and open questions.
- It names the Stage 3 direct-read exception as known debt.
- It uses repo citations for top-level claims.

## Definition Of Done

- Source set compiled and recorded.
- Stage 2 commitments, debt, and open questions separated.
- Terminology drift notes included.
- `research/01-repo-baseline.md` is ready to be consumed by later WPs.

## Risks And Watchouts

- The most likely failure is treating aspirational docs as if they were already shipped behavior.
- The second most likely failure is using inconsistent vocabulary that makes later WPs harder to compare.

## Reviewer Guidance

- Check that every top-level claim has a clear repo source.
- Check that the artifact is concise rather than a giant doc dump.
- Check that the known-debt section honestly reflects current shipped Stage 2 reality.

## Activity Log

- 2026-05-24T13:07:27Z – claude:opus:research-implementer:implementer – shell_pid=756 – Started implementation via action command
- 2026-05-24T13:12:16Z – claude:opus:research-implementer:implementer – shell_pid=756 – Ready for review: baseline inventory with sources, commitments/debt/open-questions, terminology notes. Deliverable committed in 87cb580; mission planning artifacts (spec/plan/meta/checklists) left uncommitted per instruction to only add the one owned file.
- 2026-05-24T13:13:02Z – claude:opus:research-reviewer:reviewer – shell_pid=41936 – Started review via action command
- 2026-05-24T13:14:52Z – claude:opus:research-reviewer:reviewer – shell_pid=41936 – Review passed: single owned file; sources split authoritative vs supporting; commitments/debt/open-questions cleanly separated; direct-read MCP exception matches STAGES.md+ADR0002; 5 terminology terms covered; spot-checked engine __all__, SignalSpec fields, lab_ratios, dim_metric policy enum, STATUS 82/82 — all citations accurate.
