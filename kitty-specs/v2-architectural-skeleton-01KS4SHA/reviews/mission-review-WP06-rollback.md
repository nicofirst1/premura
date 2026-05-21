# Mission Review Rollback Feedback: WP06

## Verdict

Move `WP06` back to `planned`.

## Blocking findings

1. The `FR-016` acceptance test is a false positive.
   - `src/premura/store/duck.py:seed_dim_metric()` is the production behavior that must read the six new ontology keys, serialize `aliases`, and upsert them.
   - `tests/test_skeleton.py::test_seed_handles_rows_with_and_without_new_keys` does not call `seed_dim_metric()` at all.
   - Instead, it manually inserts rows with ad hoc SQL, so it would still pass even if `seed_dim_metric()` stopped reading the new YAML keys or broke alias serialization.

2. The test/verification surface overstates the mission status for the CLI path.
   - `tests/test_skeleton.py` checks only that `install-skills` is registered on the Typer app.
   - It does not verify that `uv run hpipe install-skills` is actually invokable.
   - The real CLI path currently fails in this checkout with `Failed to spawn: hpipe`.

## Why this blocks acceptance

`WP06` owns the executable acceptance contract for the mission. A false-positive FR test and missing end-to-end CLI coverage mean the mission can appear green while the shipped workflow is still broken.

## Required correction

- Replace the `FR-016` test with one that exercises `seed_dim_metric()` itself.
- Add end-to-end coverage for the real CLI path promised by the mission, not only app registration.
