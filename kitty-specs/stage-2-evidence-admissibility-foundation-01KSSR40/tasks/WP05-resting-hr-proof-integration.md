---
work_package_id: WP05
title: Resting HR Proof Integration
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
agent: "claude:opus:implementer:implementer"
shell_pid: "37978"
history:
- timestamp: '2026-05-29T11:59:19Z'
  agent: gpt-5.5
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/engine/descriptive_signals.py
execution_mode: code_change
owned_files:
- src/premura/engine/descriptive_signals.py
- tests/test_engine_descriptive_policy_integration.py
tags: []
---

# Work Package Prompt: WP05 - Resting HR Proof Integration

## Implement Command

```bash
spec-kitty agent action implement WP05 --agent <name>
```

## Objective

Prove the new policy evaluator can be used by one existing Stage 2 signal without turning this mission into a broad refactor. Integrate only `resting_hr_status` and preserve its existing `StatusResult` output shape.

## Context

Depends on WP01-WP04.

This WP is intentionally narrow. It should demonstrate the handoff from existing Stage 2 evidence selection to the new evidence-admissibility evaluator.

## Owned Files

- `src/premura/engine/descriptive_signals.py`
- `tests/test_engine_descriptive_policy_integration.py`

Do not edit files outside this list.

## Subtasks

### T020: Add Failing Proof-Integration Test

Create `tests/test_engine_descriptive_policy_integration.py`.

Test goal:

- A stale `resting_hr_status` current-status request is evaluated through the new policy layer.
- The result remains a `StatusResult`.
- The result does not present stale evidence as current.
- Policy-derived rejection or caveat context is visible in `caveats` without changing the result envelope shape.

Use existing test fixture style from `tests/test_engine_descriptive_signals.py` where practical, but do not edit that existing test file.

### T021: Wire `resting_hr_status` Through Evaluator

Modify `src/premura/engine/descriptive_signals.py` only.

Guidance:

- Keep `_status(...)` behavior for other status-like uses unless the change is clearly safe.
- Prefer a small helper local to `resting_hr_status` or `_status` that converts the latest value into an `EvidenceCandidate` and invokes the policy evaluator.
- Preserve `StatusResult` fields and serialized shape.
- Do not migrate trend signals in this WP.

### T022: Preserve Caveats And Add Policy Context

Ensure stale results still carry the existing freshness-window caveat.

Add only concise policy-derived context that helps explain why stale evidence cannot answer current status.

Constraints:

- No diagnosis.
- No reference ranges.
- No population norms.
- No advice about treatment, medication, emergency care, or clinical action.

### T023: Add Regression Checks For Non-Target Signals

Add tests proving the proof integration did not broadly refactor unrelated behavior.

Minimum checks:

- Trend signals still return `TrendResult` behavior through their existing path.
- BMI behavior is not touched by this WP.
- `StatusResult.to_dict()` shape remains compatible.

## Implementation Notes

This WP is a proof integration, not a migration project. If implementation starts pulling trend signals, BMI, MCP wrappers, or query helpers into scope, stop and narrow it back to `resting_hr_status`.

Integration guidance:

- Reuse the built-in resting-HR or baseline-relative policy from WP03 if available.
- Convert the latest resting-HR value into an `EvidenceCandidate` with metric ID, family, observed timestamp, source/provenance when available, and point count if known.
- Evaluate it as `QuestionType.CURRENT_STATUS`.
- Map evaluator outcome back into the existing `StatusResult` shape.
- Preserve `FreshnessState.STALE` behavior for stale values unless the existing contract explicitly changes.
- Add policy-derived caveat text only as additional context.

Do not change:

- `TrendResult` shape.
- `resting_hr_trend` behavior.
- `steps_trend` behavior.
- `weight_trend` behavior.
- BMI dependency resolution.
- MCP wrappers.

Testing guidance:

- Start with a failing test that captures the desired proof behavior.
- Use existing fixture style from descriptive signal tests, but keep this test file separate to avoid ownership overlap.
- Assert on observable `StatusResult` values and caveats.
- Do not assert on private helper call counts unless no observable output can prove the integration.

## Edge Cases To Cover

- No resting-HR metric definition still returns unavailable behavior.
- No resting-HR observation still returns unavailable behavior.
- Stale resting-HR observation is not presented as current.
- Current resting-HR observation remains current.
- Existing caveats are preserved and no diagnosis text appears.

## Reviewer Checklist

- Only `resting_hr_status` is behaviorally integrated with the evaluator.
- The `StatusResult` dataclass and `to_dict()` schema are unchanged.
- Stale/current/unavailable states still mean what they meant before.
- New caveat text explains policy admissibility without sounding like medical advice.
- Existing trend and BMI tests still pass without modification.
- No MCP surface changes are present.

## Common Failure Modes

- Trying to make all descriptive signals use the evaluator in one WP.
- Turning evaluator rejection into a different result family.
- Dropping the old freshness caveat when adding policy context.
- Adding PubMed or source-note references to runtime output.
- Patching private helper calls in tests instead of asserting observable results.

## Rollback Boundary

If this WP proves too invasive, the fallback is to keep the policy layer and built-ins from WP01-WP04 and remove only the `resting_hr_status` integration. Do not roll back the foundation to avoid a proof-integration issue.

## Handoff Note

This WP should be implemented after all prior WPs are reviewed. It is the first behavior-touching slice and therefore should be reviewed more conservatively than the declaration/model WPs.

## Suggested Test Names

- `test_resting_hr_status_uses_policy_for_stale_current_status_evidence`
- `test_resting_hr_status_shape_is_preserved`
- `test_resting_hr_status_current_path_still_available`
- `test_trend_signals_not_migrated_by_proof_integration`
- `test_bmi_behavior_not_changed_by_policy_proof`

## Validation Command

Run this WP's focused test first:

```bash
uv run pytest tests/test_engine_descriptive_policy_integration.py -q
```

Then run the adjacent existing behavior tests:

```bash
uv run pytest tests/test_engine_descriptive_signals.py tests/test_bmi_signal.py -q
```

If any adjacent test fails, identify whether the failure is introduced by this WP or pre-existing. Do not update unrelated expected outputs just to make the proof integration pass.

## Acceptance Notes

The intended proof is narrow: a current-status signal can consult the policy layer and still return the existing result envelope. The proof does not require every signal to become policy-backed in this mission.

## Definition Of Done

- New proof-integration test passes.
- Existing descriptive signal tests still pass.
- No MCP files are modified.
- No Stage 3 behavior is introduced.
- Only `resting_hr_status` is integrated unless a reviewer explicitly approves a narrower helper affecting equivalent status behavior.

## Branch Strategy

Planning/base branch: `master`.
Final merge target: `master`.
Implementation worktrees are allocated later per computed lane from `lanes.json`; do not create worktrees manually.

## Reviewer Guidance

Review for scope control. This WP succeeds when one existing signal proves the policy handoff and everything else remains stable.

## Activity Log

- 2026-05-29T12:47:45Z – claude:opus:implementer:implementer – shell_pid=37978 – Started implementation via action command
- 2026-05-29T12:56:48Z – claude:opus:implementer:implementer – shell_pid=37978 – Ready for review: resting_hr_status proof integration, StatusResult shape preserved, trends/BMI untouched
