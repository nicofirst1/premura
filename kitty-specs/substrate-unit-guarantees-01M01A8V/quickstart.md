# Quickstart: verifying this mission

```bash
# Full gates (every WP merge)
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
bash ops/lint_docs.sh && bash ops/check_no_mission_citations.sh && bash ops/check_no_tracked_data.sh

# The mission's load-bearing tests
uv run pytest tests/test_units.py tests/intake/test_measurement_unit_ingest.py \
  tests/intake/test_ingest_skip_migration.py tests/intake/test_unit_spelling_migration.py \
  tests/mcp/test_ingest_row_tool.py tests/test_cli_audit_integrity.py -q

# The one test that would have caught the incident
uv run pytest tests/intake/test_measurement_unit_ingest.py -k unregistered_source_kind -q
```

Post-merge, on the operator machine (runtime, outside repo scope):

1. Dry-run count, review, then run `ops/delete_labsheet_rows.sql`.
2. Re-enter the source spreadsheet via `ingest_row` (`suggest_metric` → `load` per row).
3. `uv run premura audit-integrity` → zero non-canonical units, zero out-of-vocabulary source kinds (mission SC-001).
4. Close #111 and #113; fresh export + upload for a clean recovery point.
