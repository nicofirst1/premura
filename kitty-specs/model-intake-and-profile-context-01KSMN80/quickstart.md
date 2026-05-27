# Quickstart / Validation: Model Intake And Profile Context

Run from the future implementation branch or worktree once `/spec-kitty.tasks`
has produced the implementation work packages.

## Targeted validation

```bash
# Contract artifacts remain internally consistent and machine-readable
uv run python -m pytest tests/test_profile_intake_contracts.py -q

# Existing engine contract still aligns with explicit dependency declarations
uv run python -m pytest tests/test_engine_contract.py -q

# Static and formatting gates for the changed scope
uv run ruff check .
uv run ruff format --check .
```

## Manual review checklist

1. Confirm each canonical example still maps to exactly one home:
   `profile_context`, `nutrition_intake`, `supplement_intake`,
   `observation_history`, or `note_history`.
2. Confirm overlap examples still stay distinct:
   declared height vs measured height, meal calories vs wearable kcal,
   supplement dose vs body observation.
3. Confirm every load-bearing invariant in
   `kitty-specs/model-intake-and-profile-context-01KSMN80/contracts/semantic-invariants.yaml`
   has at least one validation path in the implementation.
4. Confirm future function prerequisites are declared through an explicit
   dependency shape rather than by assuming values exist in measurement history.

## Expected outcomes

- The implementation keeps storage flexible but cannot change the meaning of the
  canonical entities.
- Contract tests fail if a PR collapses profile, intake, and observation
  semantics into one generic record type.
- The engine-facing contract can name profile and intake prerequisites without
  treating them as opportunistic measurement rows.
- Docs and contract artifacts stay aligned in the same change.
