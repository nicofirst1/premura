---
work_package_id: WP02
title: Baseline Result-Shape Honesty
dependencies: []
requirement_refs:
- FR-005
- NFR-001
- NFR-003
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-harden-grounded-stage-2-contract-01KSJ654
base_commit: dbd7aa862c6182fe0f050d524dd8835872693d5c
created_at: '2026-05-26T13:13:55.432708+00:00'
subtasks:
- T003
- T004
- T005
shell_pid: "35810"
history: []
authoritative_surface: src/premura/engine/
execution_mode: code_change
owned_files:
- src/premura/engine/_results.py
- src/premura/engine/comparative_signals.py
- tests/test_engine_comparative_signals.py
tags: []
agent: "claude:opus:implementer:implementer"
---

# Work Package Prompt: WP02 — Baseline Result-Shape Honesty

## Objective

Stop `sleep_deep_pct_baseline` from fabricating numbers. Today, when there is no
trustworthy comparison, `BaselineComparisonResult.latest_value` and
`baseline_mean` are coerced to `0.0` (the dataclass types them as bare `float`),
so a downstream consumer that ignores the status field renders a false
"0.0% vs 0.0%". Make the numeric fields honestly optional and enforce their
absence when there is nothing trustworthy to report — mirroring how
`StatusResult.value` is already `float | None` with a `validate()` that forbids a
value when unavailable.

## Owned Surface

- `src/premura/engine/_results.py`
- `src/premura/engine/comparative_signals.py`
- `tests/test_engine_comparative_signals.py`

Do not modify files outside this list. In particular, do NOT change
`__init__.py` (owned by WP01) or the MCP server (owned by WP03).

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed from `lanes.json` during implement.

## Background to read first

- `src/premura/engine/_results.py`: study `StatusResult` (its `value: float | None`
  and `validate()` that raises when a value is present but `freshness_state` is
  `UNAVAILABLE`). Mirror that pattern for the baseline envelope. Note
  `ComparisonState.UNKNOWN` and `FreshnessState.UNAVAILABLE`.
- `src/premura/engine/comparative_signals.py`: the `_baseline_comparison` helper
  that builds `BaselineComparisonResult` and currently does
  `latest_value=computed.latest_value if computed.latest_value is not None else 0.0`
  (and likewise for `baseline_mean`).
- `data-model.md` in the mission folder describes the exact target shape.

## Subtasks

### T003 — Optional numeric fields + `validate()`

**Required changes** (`src/premura/engine/_results.py`)

- Change `BaselineComparisonResult.latest_value` and `baseline_mean` to
  `float | None = None`.
- Add a `validate()` method (return `self`, raise `ValueError` on violation):
  - If `freshness_state is FreshnessState.UNAVAILABLE` → `latest_value` MUST be
    `None`.
  - If `comparison_state is ComparisonState.UNKNOWN` → `baseline_mean` MUST be
    `None` (no trustworthy baseline was formed).
- `to_dict()` keeps the same keys; it will now serialize `None` for these fields
  in unavailable/unknown cases. Confirm no key is dropped.

**Constraints**

- Do not change the other result families' value-field requirements.
- Keep the dataclass frozen and the existing field order stable where possible
  (only the two type annotations + defaults change).

### T004 — Stop the `0.0` coercion

**Required changes** (`src/premura/engine/comparative_signals.py`)

- In the baseline construction, pass `computed.latest_value` and
  `computed.baseline_mean` straight through (they may be `None`); remove the
  `... else 0.0` fallbacks.
- Call `.validate()` on the constructed `BaselineComparisonResult` before
  returning it (so an internal inconsistency fails loudly rather than serializing
  a half-truth). The "available" path with real values must still validate
  cleanly.
- Do not change the caveat text, comparison logic, freshness logic, or the
  `engine.compute`-resolvable registration.

### T005 — No-fabrication test

**Required changes** (`tests/test_engine_comparative_signals.py`)

- Add/extend tests so that:
  - The "no deep-sleep value" case asserts the serialized `latest_value is None`
    (NOT `0.0`) and `freshness_state == "unavailable"`.
  - The "too few prior nights / unknown baseline" case asserts
    `baseline_mean is None` (NOT `0.0`) and `comparison_state == "unknown"`.
  - A successful comparison still returns real numeric `latest_value` /
    `baseline_mean` and passes validation.
- Drive behavior through the public engine interface (`engine.compute(...)` /
  the public function) and assert on `to_dict()` output, consistent with the
  existing tests in this file.

## Validation

```bash
uv run python -m pytest tests/test_engine_comparative_signals.py -q
uv run python -m pytest tests/ -q -k engine    # no regression
```

## Definition of Done

- `BaselineComparisonResult` numeric fields are `float | None` with a `validate()`
  enforcing absence when unavailable/unknown.
- `sleep_deep_pct_baseline` no longer emits `0.0` placeholders.
- Tests prove no fabricated numbers in the unavailable/unknown cases and that the
  happy path still reports real values.

## Risks & Watchouts

- Some existing baseline test may currently assert `0.0` or a numeric default in
  an unavailable case — update it to the honest `None` expectation rather than
  preserving the old false assertion.
- Ensure `validate()` is also satisfied on the happy path (values present,
  state not unknown/unavailable).

## Reviewer Guidance

Check the actual diff: the two field types are now optional, `validate()` mirrors
`StatusResult`'s honesty rule, the `0.0` coercions are gone, and the tests assert
`None` (not `0.0`). Confirm no MCP or loader files were touched.

## Activity Log

- 2026-05-26T13:13:56Z – claude:opus:implementer:implementer – shell_pid=35810 – Assigned agent via action command
