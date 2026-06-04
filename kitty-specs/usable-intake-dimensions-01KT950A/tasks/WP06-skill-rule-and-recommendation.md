---
work_package_id: WP06
title: Skill intake path + add-a-dimension rule + recommendation
dependencies:
- WP01
- WP04
requirement_refs:
- C-003
- FR-007
- FR-009
- FR-010
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T027
- T028
- T029
- T030
agent: "claude:opus:python-implementer:implementer"
shell_pid: "22348"
history:
- 2026-06-04T11:52:07Z created by /spec-kitty.tasks
authoritative_surface: src/premura/skills/parser-generator/
execution_mode: code_change
owned_files:
- src/premura/skills/parser-generator/**
- docs/building/architecture/INTAKE_DIMENSIONS.md
- docs/building/planning/intake-dimension-contract-recommendation.md
tags: []
---

# WP06 — Skill intake path + add-a-dimension rule + recommendation

## Objective

Make the generalization real and durable: document the intake parser path in the
parser-generator skill (matching WP01's settled protocol), write the generalized
**add-a-dimension rule** (validated by both shipped domains), and the
**recommendation note** on whether/when a dedicated intake-dimension contract is
worth building. Satisfies the skill half of **FR-007**, plus **FR-009, FR-010,
SC-004, SC-005, SC-006**.

## Context (depends on real code, not plans)

- This WP depends on **WP01** (the protocol must be settled before the skill can
  document it — documenting an unbuilt path is exactly the drift this mission was
  created to fix) and **WP04** (the rule must reflect the real resolver+signal
  pattern that shipped).
- The parser-generator skill today covers only the observation path (`IngestBatch`
  + `dim_metric.yaml`); see `src/premura/skills/parser-generator/SKILL.md`.
- Keep the recommendation honest to **C-003**: this mission does **not** build a
  dedicated intake-dimension contract; WP06 only recommends.

## Subtasks

### T027 — Skill: document the intake parser path (FR-007 skill half)
- Update the parser-generator skill to document, generically, how a runtime agent
  builds an intake parser: emit an `IntakeBatch` (nutrition or supplement) via the
  **WP01 protocol**, persisted through the intake load path, with unmapped fields
  declared as gaps.
- State the build-and-use boundary: a runtime agent may build-and-use an intake
  parser on the operator's own data **with no review**; review gates only a
  contributed-back PR.
- The skill must describe the protocol **as WP01 implemented it** — quote the real
  shape, not a hypothetical one.

### T028 — Add-a-dimension rule (FR-009 / SC-005)
- Write `docs/building/architecture/INTAKE_DIMENSIONS.md`: the domain-agnostic
  steps to make a declared intake dimension usable —
  (1) the domain already exists in `SEMANTIC_DOMAINS`;
  (2) add a resolver module under `engine/views/` and register it in
  `_BUILTIN_RESOLVER_MODULES`;
  (3) add a descriptive signal in an already-registered signal module;
  (4) expose it as a default-surface tool.
- Show that **both** shipped domains (`nutrition_intake`, `supplement_intake`)
  followed exactly these steps with **no change to the shared resolution seam**
  (SC-005). Reference the WP03/WP04/WP05 files as the worked examples.

### T029 — Recommendation note (FR-010 / SC-006)
- Write `docs/building/planning/intake-dimension-contract-recommendation.md`:
  - **Go/no-go**: is a dedicated intake-dimension contract needed now? (Default
    expectation: no — two domains rode the existing seam cleanly.)
  - **Sketch**: what such a contract would look like if built later.
  - **Trigger condition**: the explicit signal that would make it worth doing
    (e.g. "the Nth intake dimension that needs a payload field the generic
    `ResolvedInput` cannot carry", or "a dimension whose freshness/sufficiency
    rules cannot be expressed per-family").

### T030 — Doc↔code consistency check (no drift)
- Verify the skill and the rule describe the protocol/contract **exactly as
  WP01/WP03/WP04 implemented it** (file paths, the parse output shape, the
  registration points). A mismatch here is the very drift dimension this mission
  guards against — fix the doc, never let it describe an aspiration.

## Branch Strategy

Plan/base branch **master**; final merge target **master**. Worktree per lane in
`lanes.json`. Implement with: `spec-kitty agent action implement WP06 --agent <name>`
(after WP01 and WP04 are approved).

## Test Strategy

Primarily documentation; no failing-test-first requirement. Where a cheap
structural assertion is possible (e.g. a test that the two resolver modules are
registered and the two signals are in `REGISTRY`, proving the rule's steps hold),
add it to back SC-005. Otherwise the DoD is reviewer-verifiable against the code.

## Definition of Done

- [ ] Skill documents the intake parser path as WP01 implemented it (FR-007 skill half / SC-004).
- [ ] `INTAKE_DIMENSIONS.md` states the domain-agnostic add-a-dimension steps, with both domains as worked examples and an explicit "no shared-seam change" claim (FR-009 / SC-005).
- [ ] Recommendation note has go/no-go + sketch + explicit trigger condition (FR-010 / SC-006).
- [ ] Doc↔code consistency verified; no aspirational/incorrect path described (C-003 honored — no contract built).
- [ ] ruff format --check passes on any touched markdown-adjacent code; docs render cleanly.

## Risks

- **Doc describes an unbuilt/incorrect path (D-style drift).** Mitigation: T030 +
  the WP01/WP04 dependency; the reviewer cross-checks every claim against code.
- **Recommendation is vague.** Mitigation: T029 requires an explicit trigger, not
  "maybe later".

## Reviewer Guidance

- Open the WP01 protocol and confirm the skill quotes it accurately.
- Confirm the add-a-dimension steps match what WP03/WP04/WP05 actually did.
- Confirm the recommendation's trigger is concrete enough to act on.

## Activity Log

- 2026-06-04T14:13:28Z – claude:opus:python-implementer:implementer – shell_pid=22348 – Started implementation via action command
- 2026-06-04T14:25:49Z – claude:opus:python-implementer:implementer – shell_pid=22348 – Ready for review: skill intake path (T027), add-a-dimension rule (T028), recommendation note (T029), doc-consistency test (T030). WP03 matcher carry-forward captured in INTAKE_DIMENSIONS.md + kitty-specs contract gap noted for mission-review.
