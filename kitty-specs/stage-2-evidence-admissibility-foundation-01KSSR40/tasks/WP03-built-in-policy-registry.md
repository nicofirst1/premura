---
work_package_id: WP03
title: Built-In Policy Registry
dependencies:
- WP01
- WP02
requirement_refs:
- FR-002
- FR-008
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master.
subtasks:
- T011
- T012
- T013
- T014
- T015
history:
- timestamp: '2026-05-29T11:59:19Z'
  agent: gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/policies/
execution_mode: code_change
owned_files:
- src/premura/engine/policies/_registry.py
- src/premura/engine/policies/_defaults.py
- tests/test_engine_policy_defaults.py
tags: []
---

# Work Package Prompt: WP03 - Built-In Policy Registry

## Implement Command

```bash
spec-kitty agent action implement WP03 --agent <name>
```

## Objective

Add representative built-in policy declarations and a lightweight registry. The goal is to satisfy initial coverage through reusable family shapes, not to create a bespoke clinical rule table.

## Context

Depends on WP01 and WP02.

Key constraints:

- At least 10 metric families or family groups must be named and covered.
- Use a smaller number of reusable policy shapes.
- Policies are local Premura admissibility defaults, not clinical authority.
- Built-ins may include rationale/source notes, but the evaluator must not use external sources at runtime.

## Owned Files

- `src/premura/engine/policies/_registry.py`
- `src/premura/engine/policies/_defaults.py`
- `tests/test_engine_policy_defaults.py`

Do not edit files outside this list.

## Subtasks

### T011: Add Lightweight Policy Registry

Create registry helpers in `_registry.py`.

Expected behavior:

- Register `MetricFamilyPolicy` declarations.
- Detect duplicate `policy_id` values.
- Detect duplicate metric-family ownership unless explicitly allowed by the model.
- Return policies by metric family.
- Return the full built-in policy list in deterministic order.

Do not mirror the Stage 2 signal registry exactly if that would allow silent overwrites. For policy declarations, accidental duplicate registration should fail loudly.

### T012: Add Built-In Policy Declarations

Create representative built-ins in `_defaults.py`.

Cover at least these 10 family groups from the research note:

- stable profile facts
- acute spot measures
- home blood pressure or serial short-run averages
- CGM or dense rolling recent patterns
- A1C-like long-term control markers
- lipids or slow chronic-control markers
- sparse lab panels
- weight or slow trajectory metrics
- body composition or method-sensitive estimates
- activity metrics
- sleep metrics
- HRV/resting-HR/recovery metrics

It is acceptable to cover more than 10. It is also acceptable for multiple families to share the same `policy_shape`.

### T013: Add Caveats, Rationale, And Source Notes

Every built-in declaration should carry:

- short rationale text
- standing caveats where needed
- source notes pointing to mission research or general source anchors

Do not write caveats as diagnosis, treatment advice, or population-norm interpretation.

### T014: Add Registry Coverage Tests

Create `tests/test_engine_policy_defaults.py`.

Required tests:

- At least 10 family groups are covered.
- Multiple families share reusable shapes, proving this is not a bespoke matrix.
- Duplicate policy IDs fail.
- Duplicate family ownership fails.
- No policy creates a full per-question duplicate block when a family-level rule would do.

### T015: Add Default Policy Smoke Tests

Use the evaluator from WP02 to test representative built-ins.

Required smoke cases:

- A long-term marker is rejected for current status and admitted for long-term control.
- A valid-until-superseded profile fact is not rejected only because it is old.
- A method-sensitive family carries caveats.
- Sparse evidence becomes insufficient where the policy requires density.

## Implementation Notes

The built-in registry should demonstrate the abstraction level, not become a medical encyclopedia. Prefer fewer reusable shapes with clear family assignment.

Suggested reusable policy shapes:

- `assertion_until_superseded` for stable profile facts.
- `point_in_time_acute` for acute spot measures.
- `serial_average_short_run` for home blood pressure style evidence.
- `rolling_recent_pattern` for CGM, activity, and sleep pattern evidence.
- `integrated_long_term_control` for A1C-like and lipid-like markers.
- `baseline_relative` for HRV/resting-HR/recovery-style evidence.
- `slow_trajectory_method_sensitive` for weight and body composition.
- `sparse_lab_analyte_specific` for sparse lab panels.

Family coverage can be broader than shape count. The point is to name at least 10 family groups while avoiding 10 bespoke implementations.

Registry behavior:

- Duplicate `policy_id` should fail.
- Duplicate family ownership should fail unless the model explicitly supports aliases.
- Built-in listing should be deterministic.
- Lookup by family should be explicit and should not fuzzy-match.

Source notes and rationale:

- Reference `docs/history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md` where useful.
- Keep source notes informational. They do not become runtime evidence.
- Do not encode exact clinical thresholds unless already present in the mission docs and framed as an admissibility default.

## Edge Cases To Cover

- A metric family that is intentionally inadmissible for current status.
- A method-sensitive family that is admissible only with caveats.
- A stable profile fact that remains usable despite old effective date.
- A sparse lab family whose rule refuses when evidence density is insufficient.
- A duplicate policy declaration.

## Reviewer Checklist

- Built-ins cover at least 10 family groups named in the research note.
- The number of policy shapes is smaller than the number of family groups.
- Built-ins do not contain arbitrary functions, expressions, SQL, or network references.
- Rationale and source notes are explanatory only.
- Caveats are concise and non-diagnostic.
- Policy lookup behavior is deterministic and exact.

## Common Failure Modes

- Creating a separate bespoke declaration for every family when one shape would do.
- Smuggling clinical thresholds into declarations without framing them as Premura admissibility defaults.
- Making a source note sound like runtime evidence.
- Overfitting to the current metric catalog instead of defining reusable family groups.
- Allowing duplicate family mappings to silently overwrite earlier policy declarations.

## Suggested Test Names

- `test_builtin_policies_cover_at_least_ten_family_groups`
- `test_builtin_policies_reuse_policy_shapes`
- `test_duplicate_policy_id_fails`
- `test_duplicate_metric_family_fails`
- `test_long_term_control_policy_rejects_current_status`
- `test_profile_fact_policy_uses_valid_until_superseded`
- `test_method_sensitive_policy_always_carries_caveat`

## Definition Of Done

- Coverage meets NFR-005 without a large bespoke table.
- Built-ins are declarative dataclass instances.
- No YAML policy files are introduced.
- Defaults remain descriptive and non-diagnostic.

## Branch Strategy

Planning/base branch: `master`.
Final merge target: `master`.
Implementation worktrees are allocated later per computed lane from `lanes.json`; do not create worktrees manually.

## Reviewer Guidance

Check that family coverage is broad but policy shapes are few. Push back on any declaration that reads like a clinical rule rather than a Premura admissibility default.
