---
affected_files: []
cycle_number: 5
mission_slug: close-stage-3-direct-read-exception-01KSJVFG
reproduction_command:
reviewed_at: '2026-05-27T07:39:19Z'
reviewer_agent: unknown
verdict: rejected
wp_id: WP02
---

# WP02 Review — Cycle 1

**Verdict: Changes Requested**

---

## Validation Results

- `pytest -q`: **154 passed** (all tests pass)
- `mypy src/premura/mcp`: **Success: no issues found in 3 source files**
- `ruff check .`: **9 errors, all E501 (line-too-long)** — all pre-existing from WP01 (lines 662–704 of `test_mcp_signal_tools.py`) and an unrelated parser test file. No new violations introduced by WP02.

---

## Per-Criterion Review

### Integration is real, not dead code — PASS

`grep -n "list_metric_catalog\|metric_summary\|import engine" src/premura/mcp/server.py` confirms:

- Line 34: `from .. import engine`
- Line 113: `entries = engine.list_metric_catalog(metric_ids, conn)` — return value serialized at line 114 via `[entry.to_dict() for entry in entries]`
- Line 133: `entry = engine.metric_summary(metric_id, conn)` — return value serialized at line 134 via `entry.to_dict()`

No inline SQL shaping; the returned envelope is what gets serialized.

### No raw row counts / no all-time extrema — PASS

All aggregate SQL (COUNT/MIN/MAX/AVG, `measurement_count`, `interval_count`, `numeric_summary`) has been removed from both `list_metrics` and `metric_summary`. Verified via diff and grep of `server.py`. New tests assert their absence explicitly.

### `query_warehouse` untouched — PASS

`query_warehouse` function body is unchanged. `list_metrics` retains a narrow use of `query_warehouse` solely to page metric IDs from `dim_metric` before delegating to the engine — this is consistent with WP02 scope (WP03 handles the surface split of `query_warehouse` itself).

### Six signal tools + `_serialize_signal_result()` unchanged — PASS

`resting_hr_status`, `resting_hr_trend`, `steps_trend`, `weight_trend`, `sleep_deep_pct_baseline`, `hrv_change_around_date`, and `_serialize_signal_result()` are untouched in the WP02 diff.

### Machine-branchable discrete fields — PASS

Both `MetricCatalogEntry.to_dict()` and `MetricSummaryEntry.to_dict()` expose explicit top-level fields: `validity_status`, `validity_window`, `missing_data_policy`, `unit`, `sample_size`, `imputed_proportion`, `gap_count`, `window_days`. Not embedded in prose.

### Files changed outside WP02 scope — PASS

Only `src/premura/mcp/server.py`, `tests/test_mcp_server.py`, `tests/test_mcp_signal_tools.py` are modified. Confirmed via `git show HEAD --name-only`.

---

## Issue: Missing unknown/unregistered metric test for `list_metrics` catalog — FAIL

**Criterion**: The review requires: "Verify coverage of fresh(current)/stale/empty AND unknown (unregistered) metric for BOTH `list_metrics` and `metric_summary`."

**Finding**: The T009 tests in `tests/test_mcp_signal_tools.py` cover:

- `list_metrics` catalog: fresh (`test_list_metrics_fresh_catalog_entry`), stale (`test_list_metrics_stale_catalog_entry`), empty (`test_list_metrics_empty_catalog_entry`)
- `metric_summary`: unknown (`test_metric_summary_unknown_metric`) — COVERED

**Missing**: There is no test for an unknown/unregistered metric at the `list_metrics` MCP surface level.

**Architectural note**: `list_metrics` pre-filters IDs via `SELECT metric_id FROM hp.dim_metric`, so it cannot naturally pass an unknown ID to `engine.list_metric_catalog`. However, the engine handles unknown IDs correctly (returns `unavailable` with message "metric '{id}' is not registered in the catalog"). The behavior at the `list_metrics` surface (omission of unknown metrics, rather than an `unavailable` entry) is architecturally intentional but:

1. Is not tested or documented at the MCP surface level.
2. The review's acceptance criterion explicitly requires the unknown case to be tested for the catalog tool.

**Required fix** (choose one approach, document the choice):

**Option A — Document the architectural boundary**: Add a test that explicitly verifies the omission behavior and explains why it differs from `metric_summary`:

```python
def test_list_metrics_omits_unregistered_metric_ids(tmp_path: Path) -> None:
    """T009: list_metrics only surfaces registered metrics; unregistered IDs are
    never passed to the engine because IDs are sourced from hp.dim_metric.
    The unknown-metric guarantee lives at the engine level (tested in WP01).
    """
    rows = server.list_metrics(warehouse_path=_empty_warehouse(tmp_path), limit=5)
    # All returned entries are registered; no entry has an unknown metric_id.
    for entry in rows:
        assert entry["validity_status"] in ("current", "stale", "unavailable")
    # No entry carries a fabricated or crash-inducing id.
    returned_ids = {r["metric_id"] for r in rows}
    assert "nonexistent_metric_xyz" not in returned_ids
```

**Option B — Expose the engine's unknown-metric capability at the surface**: Consider adding a separate `get_metric_catalog_entry(metric_id)` tool for single-metric lookup (WP03/WP04 scope), or change `list_metrics` to optionally accept explicit IDs. This is larger scope and likely not appropriate for WP02.

**Recommended**: Option A — a comment-documented test that explicitly captures the boundary. This satisfies the review criterion and prevents future regressions if the implementation changes.

---

## Summary

All criteria pass except the missing test for unknown/unregistered metric at the `list_metrics` surface. The implementation is correct and the architectural reasoning is sound, but the review requires the unknown case to be explicitly tested (or documented via test) for the catalog tool, not just for `metric_summary`.
