# Quickstart: Implement Profile And Intake Storage

## Goal

Validate the first implementation of concrete profile/intake storage and the
agent-mediated profile capture path.

## Planned validation path

1. Apply the new warehouse migration that creates the profile, nutrition, and
   supplement domain tables.
2. Expose the bounded profile surface through MCP tools:
   - `profile_context_supported_fields`
   - `profile_context_record`
3. Add matching CLI wrappers for fallback/testing:
   - `hpipe profile schema`
   - `hpipe profile record`
4. Run a black-box test that:
   - asks for the supported schema,
   - records `birth_date`, `sex`, and `standing_height_cm`,
   - verifies the assertions exist in the profile-context tables,
   - verifies `age` is rejected as an unsupported direct field.
5. Run persistence tests that create synthetic normalized nutrition and
   supplement records and verify they land in the new intake tables rather than
   in `hp.fact_measurement` or note history.
6. Run quality gates for the changed scope:
   - `pytest -q`
   - `ruff check .`
   - `ruff format --check .`
   - `mypy` on the changed Python modules

## Acceptance focus

- Profile capture is agent-mediated and bounded.
- Nutrition/supplement storage is concrete and parser-ready.
- One-home rules are enforced by tests.
- No built-in nutrition/supplement importer is added in this mission.
