---
work_package_id: WP04
title: Decision Record And Product Planning Alignment
dependencies:
- WP01
- WP03
requirement_refs:
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
created_at: '2026-05-27T12:27:28Z'
subtasks:
- T014
- T015
- T016
- T017
- T018
agent: "claude:opus:implementer:implementer"
shell_pid: "19322"
history:
- timestamp: '2026-05-27T12:27:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/product/
execution_mode: code_change
owned_files:
- docs/adr/0005-profile-and-intake-contract.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- docs/product/ROADMAP.md
- docs/product/ROADMAP_BOOTSTRAP_PLAN.md
- docs/product/VISION.md
tags: []
---

# Work Package Prompt: WP04 - Decision Record And Product Planning Alignment

## Objective

Record the winning architectural decision and align the product-planning docs so
future missions start from the new contract baseline.

This WP should leave the repo with one clear answer to the original dilemma:

- storage remains flexible,
- semantics are strict at the contract boundary,
- agent review depends on invariants that are enforceable rather than merely
  tasteful.

## Owned Surface

- `docs/adr/0005-profile-and-intake-contract.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/product/ROADMAP.md`
- `docs/product/ROADMAP_BOOTSTRAP_PLAN.md`
- `docs/product/VISION.md`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP04 --agent <name>`

## Context

By the time this WP starts, the authoritative contract surface and the core
architecture docs should already reflect the new boundary. This WP turns that
into a durable decision record and updates the longer-range product docs so they
stop talking as if the boundary question were still unresolved.

Be careful not to overstate shipped behavior. This mission defines a contract and
future implementation path; it does not ship user-facing intake capture or new
signals.

## Subtasks

### T014 - Add the design decision note

**Purpose**

Record the winning architectural choice in one place that later missions can cite.

**Required changes**

- Add `docs/adr/0005-profile-and-intake-contract.md`.
- Capture:
  - the problem being solved
  - the chosen decision
  - why "strict contract, flexible storage" won
  - why invariant-first review matters in an agent-reviewed repo
  - what remains intentionally deferred

**Constraints**

- Keep it a decision note, not a second full spec.
- Make the rationale concrete and tied to this repo's agent-review reality.

### T015 - Update FULL_APP_DEVELOPMENT_PLAN.md

**Purpose**

Re-sequence later work from the new contract baseline rather than the older,
profile-only unresolved framing.

**Required changes**

- Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`.
- Make clear that the boundary question is now answered at the contract level.
- Reframe the next work as implementation missions over that contract: storage,
  manual entry, import, signal use, and review gates.

### T016 - Update ROADMAP.md

**Purpose**

Ensure the medium-term roadmap starts from the resolved contract split and the
need for machine-checkable review gates.

**Required changes**

- Update `docs/product/ROADMAP.md`.
- Reflect the new seam and the likely follow-on order.
- Preserve the local-first and non-diagnostic posture.

### T017 - Update ROADMAP_BOOTSTRAP_PLAN.md

**Purpose**

Keep the backlog framing around issue `#6` honest and consistent with this new
broader contract direction.

**Required changes**

- Update `docs/product/ROADMAP_BOOTSTRAP_PLAN.md`.
- Replace stale language that treats the gap as profile-only when the new mission
  intentionally covers profile context plus nutrition and supplement intake.
- Keep historical context readable instead of rewriting the past confusingly.

### T018 - Update VISION.md lightly

**Purpose**

Make the long-range vision acknowledge the new contract seam without pretending a
new end-user capability shipped.

**Required changes**

- Update `docs/product/VISION.md` lightly.
- Acknowledge that the system now has a clearer semantic path for profile and
  intake-aware reasoning.
- Do not present intake capture or profile-aware analysis as already delivered.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -m pytest -q
```

Manual spot-checks:

1. Read the decision note and confirm it records one choice plus rationale.
2. Read the product docs and confirm they no longer talk as if the boundary were
   still undefined.
3. Confirm no doc overstates user-facing capability.

## Definition Of Done

- A design decision note exists for the contract-vs-storage choice.
- Product-planning docs consistently start from the new contract baseline.
- Issue-`#6`-related planning language is no longer narrowly or ambiguously framed.
- The vision doc acknowledges the seam without claiming shipped runtime behavior.

## Risks And Watchouts

- The biggest risk is overclaiming: this mission solves the semantic boundary,
  not the full user workflow.
- Another risk is rewriting historical planning docs so aggressively that their
  original context becomes unreadable.

## Reviewer Guidance

Review for consistency and honesty:

1. Do all product docs now point to the same architectural answer?
2. Does the decision note explain why this answer is robust in an agent-reviewed
   repo?
3. Has the wording stayed non-diagnostic, local-first, and accurate about what
   is and is not shipped?

## Activity Log

- 2026-05-27T12:27:28Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T12:59:16Z – claude:opus:implementer:implementer – shell_pid=19322 – Started implementation via action command
- 2026-05-27T13:05:08Z – claude:opus:implementer:implementer – shell_pid=19322 – Ready for review
