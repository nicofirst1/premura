# Specification Quality Checklist: Intake Parser Acceptance Scenario

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-05
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, and C-### entries
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **On "no implementation details":** Premura is an agent-operated codebase whose
  spec audience is the maintainer + operating agents, and the established
  convention (see the merged `usable-intake-dimensions` spec) is to **anchor**
  requirements to the existing shipped seams they extend (the live-trial harness,
  the three-rule grader, the intake load path, the warehouse drawers). The spec
  uses those names as *anchors and dependencies* while the requirements
  themselves are stated as **outcomes** (rows landed in the right drawer; a
  mis-filed row fails; no per-source branch in the shared path). This is
  intentional and consistent with the repo, not leakage of a chosen tech stack.
- All requirement rows carry a Status; every NFR carries a measurable threshold;
  Success Criteria are outcome-stated and verifiable.
- No `[NEEDS CLARIFICATION]` markers — the two product-level forks (scope across
  the three layers; alien vs. reused source) were resolved with the maintainer
  during discovery before writing.
- All checklist items pass on iteration 1.

### Iteration 2 — drift-hardening pass (maintainer review)

Five tightenings applied, each mapped to a known drift class in the audit history:

1. **`honest_about_gaps` source of truth (FR-005).** Parser-declared gap metadata
   is now "evidence to verify, never proof to accept"; a field neither truly
   loaded nor declared is a silent-drop failure. Codifies the shipped grader's
   existing behavior so the intake path cannot regress it.
2. **`runtime_valid` bounded, not fuzzy (FR-010, new).** Pinned to the exact
   clause set the shipped `check_runtime_contract` enforces (observation form
   enumerated) plus its intake analogue, explicitly **not** the full
   parser-review contract. Spec clause list and implementation must agree
   (plan-verified). Guards the D5 "broad label silently expands" drift.
3. **Named edge cases are end-to-end (SC-001/002/004/007).** Mis-filed row,
   unmappable field, and malformed parser are each proved by an end-to-end harness
   run, not a component test (D7). The malformed-parser failure path is made
   **deterministic in the default suite** via a stub operator — stronger than a
   live-only check.
4. **Scenario boundary is a testable failure clause (FR-001).** "Adding a scenario
   must require no change to shared grading logic"; boundary-truth tables and the
   runtime-valid clause set are carried by the scenario, not hardwired. Mirrors the
   cross-scope drift focus of the audit method.
5. **Failure path produces a completed record (FR-009, new).** A completed,
   persisted, failing graded record must exist even on import/parse failure —
   guards the session-log-substrate RCA where the failure path crashed before a
   gradeable record existed.

Renumbering: the old FR-009 (layer-3 attach) is now FR-011. All cross-references
re-verified. All checklist items still pass.
