# Quickstart — Close the Stage 3 Direct-Read Exception

## Branch contract

- Current branch at workflow start: `master`
- Planning/base branch: `master`
- Final merge target: `master`

## Goal

Make the default MCP surface fully validity-gated, and move raw SQL behind a separate operator entrypoint.

## Expected artifacts

- Engine helpers for metric catalog and metric validity summary
- Updated MCP server/core registration
- Separate operator entrypoint that adds `query_warehouse`
- Updated tests and docs
- New ADR documenting the closed exception

## Suggested implementation order

1. Add failing tests for default-vs-operator tool registration.
2. Add failing tests for validity-gated `list_metrics` output.
3. Add failing tests for validity-gated `metric_summary` output.
4. Introduce engine result types and helper functions for catalog/summary.
5. Rewire MCP server code to consume engine helpers.
6. Split entrypoints so the operator surface is separate.
7. Update docs and add the ADR removing the "known exception" language.
8. Run `ruff`, `mypy` for changed scope, and `pytest -q`.

## Validation commands

```bash
pytest -q tests/test_mcp_server.py tests/test_mcp_signal_tools.py tests/test_engine.py tests/test_engine_contract.py tests/test_skeleton.py
pytest -q
```

## Manual verification

1. Start the default entrypoint and confirm `query_warehouse` is absent.
2. Start the operator entrypoint and confirm `query_warehouse` is present.
3. Seed fresh, stale, and empty metrics in a test warehouse and confirm:
   - catalog entries return `current` / `stale` / `unavailable`
   - summary responses expose `sample_size`, `imputed_proportion`, and `gap_count`
   - unknown or empty metrics return honest absence with no fabricated numeric values
