---
work_package_id: WP08
title: Doctrine docs update (FR-130) + live-doc sync
dependencies: []
requirement_refs:
- FR-130
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T029
- T030
- T031
- T032
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/building/planning/operating-agent-roles.md
- docs/building/adr/0010-runtime-orchestrator-and-operating-roles.md
- docs/shared/DOCTRINE.md
- docs/shared/STATUS.md
- docs/shared/ROADMAP.md
- tests/test_doctrine_build_and_use.py
tags: []
---

# WP08 — Doctrine docs update (FR-130) + live-doc sync

## Objective

Land the maintainer-settled **build-and-use-now parser rule** consistently across
the three docs that currently contradict it, and sync the live status docs
(FR-130, SC-007). The rule (verbatim target):

> An agent may build a parser and **use it immediately for the operator's own
> data, with no reviewer** — this is part of using an installed Premura. Review
> enters **only if the human consents to contribute that parser back** as a public
> PR; the PR (not the local use) goes through the existing development/review
> process.

Critically, **"operating role" stays narrow** (a job the orchestrator dispatches
through Premura's MCP tools); parser-building remains file-editing and **not** an
MCP operating role. Only the *review-before-use* clause changes. This aligns with
charter risk-boundary #4 (internal work autonomous; PR-back is the human-approved
external action), so **no charter amendment is required**.

This is a docs-only WP (no code behavior change). It is independent of all other
WPs and can land any time.

## Context / grounding (the exact spots to change)

- `docs/building/planning/operating-agent-roles.md` §"Dev-time boundary" contains:
  > "Parser extension is not an operating role. Runtime can discover and describe
  > the need for a parser... **The actual code change remains outside the runtime
  > orchestrator and goes through the existing development/review process.**"
  The **last sentence** is the contradiction to fix.
- `docs/building/adr/0010-runtime-orchestrator-and-operating-roles.md` has a
  framing line: "...product gaps found during operation become private improvement
  candidates **before** any user-approved issue or dev-time workflow. This keeps
  runtime operation **separate from... codebase extension**." Adjust so building +
  using a parser for the operator's own data at runtime is allowed; contribution
  back is the gated path.
- `docs/shared/DOCTRINE.md` already splits "Agent operating/extending the repo"
  from "Contributor opening a PR" — add one crisp clarifying line making
  build-and-use-now explicit so no reader infers review-before-use.

## Subtasks

### T029 — edit `operating-agent-roles.md`

**Purpose**: Remove the review-before-use sentence; state the new rule.

**Steps**:
1. In §"Dev-time boundary", **keep** "Parser extension is not an operating role"
   (still true — it's file-editing, not an MCP role).
2. **Replace** the "...goes through the existing development/review process"
   sentence with the build-and-use-now rule: at runtime an agent may build a
   parser and use it immediately for the operator's own data with no reviewer;
   only contributing it back (a PR) — which already requires the human's consent
   per the share-packet/draft-PR flow described elsewhere in this doc — goes
   through review.
3. Keep the existing "share packet" / user-approved draft-PR language; it already
   models the contribution-back half — make the two consistent.

**Validation**: no sentence remains asserting the local code change must be
reviewed before use; the orchestrator/operating-role definition is unchanged.

### T030 — ADR 0010 line + DOCTRINE.md clarifying line

**Steps**:
1. ADR 0010: adjust the "separate from codebase extension" framing so it
   distinguishes **runtime build-and-use for the operator's own data** (allowed)
   from **contribution back** (the gated dev-time/PR path). Do not weaken the
   orchestrator/operating-role separation; only the parser build-and-use boundary.
2. `DOCTRINE.md`: add one sentence under the relevant rule making build-and-use
   explicit — e.g. "Building and using a parser for the operator's own data is
   part of operating an installed Premura and needs no reviewer; only contributing
   a parser back (a PR) is reviewed."

**Validation**: the three docs now state the same rule; cross-references remain
valid.

### T031 — live-doc sync (STATUS / ROADMAP)

**Purpose**: Don't let live docs drift (a known recurring miss).

**Steps**:
1. Update `docs/shared/STATUS.md` to record this mission / the session-log
   substrate slice + the settled parser boundary, in the file's existing style.
2. If `docs/shared/ROADMAP.md` tracks missions/slices, add the session-log
   substrate entry; if it does not track at this granularity, leave it unchanged
   and note that in the WP's review notes (don't invent a section).

**Validation**: STATUS reflects the change; ROADMAP edit is either a real entry or
a justified no-op.

### T032 — SC-007 assertion test

**Purpose**: Pin the doctrine consistency so it can't silently regress.

**Steps** — `tests/test_doctrine_build_and_use.py`:
- `test_no_review_before_use_sentence`: assert the old review-before-use sentence
  string is **absent** from `operating-agent-roles.md`.
- `test_build_and_use_rule_present`: assert a build-and-use phrase (e.g.
  "use it immediately for the operator's own data" or an agreed canonical
  substring) is present in `operating-agent-roles.md` **and** `DOCTRINE.md`.
- Read the files via repo-relative paths; assert on file bytes (DIRECTIVE_036).

## Definition of Done

- [ ] All three docs state the build-and-use-now rule consistently; operating-role
      definition unchanged.
- [ ] STATUS synced; ROADMAP synced or justified no-op.
- [ ] `tests/test_doctrine_build_and_use.py` green (SC-007 pinned).
- [ ] `ruff`/`pytest -q tests/test_doctrine_build_and_use.py` green. (No mypy
      surface beyond the test.)

## Risks / reviewer guidance

- **Scope discipline**: change *only* the review-before-use boundary. Do not
  rewrite the orchestrator/operating-role model or the share-packet flow.
- Reviewer: confirm the SC-007 test would fail if any doc reverted — i.e. it pins
  a real substring, not a tautology.
- This is a governance-adjacent doc edit; the human (maintainer) has approved the
  rule in-session, satisfying risk-boundary #4. Reference that approval in the
  commit message.

## Implementation command

```bash
spec-kitty agent action implement WP08 --agent <name>
```
