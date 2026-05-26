# Quickstart - Implement Grounded Stage 2 Functions

This quickstart is for the implementation phase that follows planning.

## 1. Sync and verify the local environment

From `/Users/nbrandizzi/repos/personal/premura`:

```bash
uv sync --extra dev
uv run python -m pytest tests/test_engine.py tests/test_mcp_server.py -q
```

## 2. Start with failing tests

Write failing tests first for:

- the four result families: status, trend, own-baseline, change-around-date
- stale and missing-input behavior
- the six new Stage 3 MCP tools
- unchanged behavior for `query_warehouse`, `list_metrics`, and `metric_summary`

Preferred first loop:

```bash
uv run python -m pytest tests/test_engine.py -q
uv run python -m pytest tests/test_mcp_server.py -q
```

## 3. Implement in the lowest-risk order

1. Engine seam helpers and standard result envelopes
2. `resting_hr_status`
3. `resting_hr_trend`
4. `steps_trend`
5. `weight_trend`
6. Stage 3 MCP wrappers for the descriptive signals
7. `sleep_deep_pct_baseline`
8. `hrv_change_around_date`
9. Stage 3 MCP wrappers for the two caveat-heavier signals
10. Documentation and engine contributor contract alignment

## 4. Validate the new MCP surface

When the new tools exist, the MCP server should expose both the old raw tools and the new signal-backed tools.

Expected raw tools:

- `query_warehouse`
- `list_metrics`
- `metric_summary`

Expected new signal tools:

- `resting_hr_status`
- `resting_hr_trend`
- `steps_trend`
- `weight_trend`
- `sleep_deep_pct_baseline`
- `hrv_change_around_date`

## 5. Run full gates before review handoff

```bash
uv run ruff check
uv run mypy src/premura
uv run python -m pytest -q
```

If any pre-existing unrelated failure appears, call it out explicitly in the work-package handoff.

## 6. Manual acceptance checklist

- Each of the six approved questions returns either a grounded answer or an explicit unavailable reason.
- The answer always carries freshness or sufficiency information.
- No tool in this mission returns significance, confidence intervals, causal language, or external reference lookups.
- Existing raw MCP tools still work.
- No profile-dependent function or storage path is introduced.
- The updated docs describe what changed and what remains deferred to issue `#6`.
