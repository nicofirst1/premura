"""WP04 — Stage 3 signal-backed MCP tool tests.

These lock the new MCP surface that exposes the six grounded Stage 2 answers:

* registration publishes all eight default tools (2 catalog + 6 signal-backed;
  query_warehouse is operator-only per WP03);
* one successful call per result family (status / trend / baseline / change);
* a missing-or-stale-input path and an insufficient-data path are
  structurally distinguishable (not a generic error);
* the three raw tools keep their existing behavior;
* the ``hrv_change_around_date`` tool routes the user-supplied anchor date
  through the engine's explicit-anchor path (not the midpoint default).

The signal wrappers delegate to ``premura.engine``; tests assert on the
structured tool payloads, not on any re-implemented SQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from premura.mcp import server
from premura.mcp.entrypoint import build_server
from premura.store import duck

# WP03: query_warehouse moved to operator surface; the default surface carries
# the catalog + six signal tools and the two bounded profile-capture tools.
# WP06 adds the two Stage 3 analytical tools (change_point / smoothed_average) to
# the same default surface.
_EIGHT_DEFAULT_TOOLS = sorted(
    [
        "list_metrics",
        "metric_summary",
        "resting_hr_status",
        "resting_hr_trend",
        "steps_trend",
        "weight_trend",
        "sleep_deep_pct_baseline",
        "hrv_change_around_date",
        "profile_context_supported_fields",
        "profile_context_record",
        "change_point",
        "smoothed_average",
    ]
)


def _now() -> datetime:
    # Naive UTC, matching DuckDB's timezone-naive TIMESTAMP storage and the
    # engine's freshness math.
    return datetime.utcnow()


def _empty_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _seed(conn: object, rows: list[tuple[str, str, float, str]]) -> None:
    """Insert (ts_iso, metric_id, value, dedupe_key) point measurements."""
    conn.execute("BEGIN")
    for ts_iso, metric_id, value, key in rows:
        conn.execute(
            """
            INSERT INTO hp.fact_measurement (
                ts_utc, metric_id, value_num, unit, source_id, dedupe_key
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [ts_iso, metric_id, value, "x", "test:source", key],
        )
    conn.execute("COMMIT")


def _seed_intervals(conn: object, rows: list[tuple[str, str, str, float, str]]) -> None:
    """Insert (start_iso, end_iso, metric_id, value, dedupe_key) interval rows."""
    conn.execute("BEGIN")
    for start_iso, end_iso, metric_id, value, key in rows:
        conn.execute(
            """
            INSERT INTO hp.fact_interval (
                start_utc, end_utc, metric_id, value_num, source_id, dedupe_key
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [start_iso, end_iso, metric_id, value, "test:source", key],
        )
    conn.execute("COMMIT")


def _warehouse_with(tmp_path: Path, name: str) -> tuple[Path, object]:
    db_path = tmp_path / f"{name}.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    return db_path, conn


# --------------------------------------------------------------------------- #
# T021 — registration includes all eight default tools (WP03: query_warehouse
# moved to operator surface only)
# --------------------------------------------------------------------------- #
def test_build_server_publishes_all_eight_default_tools() -> None:
    async def run() -> None:
        srv = build_server()
        names = sorted(tool.name for tool in await srv.list_tools())
        assert names == _EIGHT_DEFAULT_TOOLS

    asyncio.run(run())


# --------------------------------------------------------------------------- #
# Status family — one successful call
# --------------------------------------------------------------------------- #
def test_resting_hr_status_available(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "status_ok")
    try:
        fresh = (_now() - timedelta(hours=2)).isoformat(sep=" ")
        _seed(conn, [(fresh, "resting_hr", 58.0, "rhr1")])
    finally:
        conn.close()

    payload = server.resting_hr_status(warehouse_path=db_path)

    assert payload["tool_name"] == "resting_hr_status"
    assert payload["status"] == "available"
    assert payload["result"]["family"] == "status"
    assert payload["result"]["metric_id"] == "resting_hr"
    assert payload["result"]["value"] == 58.0
    assert payload["result"]["freshness_state"] == "current"
    assert isinstance(payload["message"], str)


def test_resting_hr_status_missing_input(tmp_path: Path) -> None:
    payload = server.resting_hr_status(warehouse_path=_empty_warehouse(tmp_path))

    # No recorded value -> structurally distinct missing_input, not a trend/baseline
    # collapse and not a generic error.
    assert payload["status"] == "missing_input"
    assert payload["result"]["freshness_state"] == "unavailable"
    assert payload["result"]["value"] is None

    # FR-008: the user-facing message is the signal's actionable hint, not a
    # generic "no value" string. Assert the specific authored substring.
    assert "resting heart rate" in payload["message"]
    assert "Connect a wearable" in payload["message"]

    # The structured report names what data is needed without parsing prose.
    report = payload["missing_input"]
    assert report["family"] == "missing_input"
    assert report["tool_name"] == "resting_hr_status"
    assert report["required_inputs"] == ["resting_hr"]
    assert report["missing_inputs"] == ["resting_hr"]
    assert report["stale_inputs"] == []
    # Structured message mirrors the actionable hint shown to the user.
    assert report["message"] == payload["message"]


def test_resting_hr_status_stale_input(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "status_stale")
    try:
        # resting_hr validity_window is P1D; a reading a week old is present-but-stale.
        old = (_now() - timedelta(days=7)).isoformat(sep=" ")
        _seed(conn, [(old, "resting_hr", 61.0, "rhr_old")])
    finally:
        conn.close()

    payload = server.resting_hr_status(warehouse_path=db_path)

    assert payload["status"] == "stale_input"
    assert payload["result"]["freshness_state"] == "stale"
    # Stale keeps the value (distinct from missing_input which drops it).
    assert payload["result"]["value"] == 61.0

    # FR-008: a present-but-stale input still surfaces the actionable hint and a
    # structured report, but the input lands in stale_inputs (not missing_inputs).
    assert "resting heart rate" in payload["message"]
    report = payload["missing_input"]
    assert report["family"] == "missing_input"
    assert report["required_inputs"] == ["resting_hr"]
    assert report["stale_inputs"] == ["resting_hr"]
    assert report["missing_inputs"] == []
    assert report["message"] == payload["message"]


# --------------------------------------------------------------------------- #
# Trend family — one successful call + insufficient-data path
# --------------------------------------------------------------------------- #
def test_resting_hr_trend_available(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "trend_ok")
    try:
        now = _now()
        offsets = [
            (timedelta(days=20), 55.0),
            (timedelta(days=15), 57.0),
            (timedelta(days=10), 60.0),
            (timedelta(days=5), 63.0),
            (timedelta(hours=2), 66.0),  # latest point fresh (within P1D window)
        ]
        rows = [
            ((now - delta).isoformat(sep=" "), "resting_hr", value, f"t{i}")
            for i, (delta, value) in enumerate(offsets)
        ]
        _seed(conn, rows)
    finally:
        conn.close()

    payload = server.resting_hr_trend(warehouse_path=db_path)

    assert payload["status"] == "available"
    assert payload["result"]["family"] == "trend"
    assert payload["result"]["trend_direction"] == "up"
    assert payload["result"]["current_freshness_state"] == "current"
    assert len(payload["result"]["points"]) >= 5


def test_steps_trend_insufficient_data(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "steps_sparse")
    try:
        now = _now()
        # Only two observed days: too sparse to name a direction -> unknown.
        _seed_intervals(
            conn,
            [
                (
                    (now - timedelta(days=3)).isoformat(sep=" "),
                    (now - timedelta(days=3)).isoformat(sep=" "),
                    "steps",
                    4000.0,
                    "s1",
                ),
                (
                    (now - timedelta(days=1)).isoformat(sep=" "),
                    (now - timedelta(days=1)).isoformat(sep=" "),
                    "steps",
                    5000.0,
                    "s2",
                ),
            ],
        )
    finally:
        conn.close()

    payload = server.steps_trend(warehouse_path=db_path)

    assert payload["status"] == "insufficient_data"
    assert payload["result"]["trend_direction"] == "unknown"
    # steps policy is `none`: never imputes.
    assert payload["result"]["imputed_point_count"] == 0


def test_weight_trend_available(tmp_path: Path) -> None:
    # FR-006 / NFR-002: weight_trend is exercised end-to-end through the Stage 3
    # surface, completing the "all six approved questions covered" promise.
    db_path, conn = _warehouse_with(tmp_path, "weight_trend_ok")
    try:
        now = _now()
        offsets = [
            (timedelta(days=28), 82.0),
            (timedelta(days=21), 81.0),
            (timedelta(days=14), 80.0),
            (timedelta(days=7), 79.0),
            (timedelta(hours=6), 78.0),  # latest weigh-in fresh
        ]
        rows = [
            ((now - delta).isoformat(sep=" "), "weight", value, f"w{i}")
            for i, (delta, value) in enumerate(offsets)
        ]
        _seed(conn, rows)
    finally:
        conn.close()

    payload = server.weight_trend(warehouse_path=db_path)

    assert payload["tool_name"] == "weight_trend"
    assert payload["status"] == "available"
    assert payload["result"]["family"] == "trend"
    assert payload["result"]["metric_id"] == "weight"
    # A populated, fresh series yields a named direction (a downward weigh-in run).
    assert payload["result"]["trend_direction"] == "down"
    assert payload["result"]["current_freshness_state"] == "current"
    # An available answer carries no structured missing-input block.
    assert "missing_input" not in payload


# --------------------------------------------------------------------------- #
# Baseline family — one successful call
# --------------------------------------------------------------------------- #
def test_sleep_deep_pct_baseline_available(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "baseline_ok")
    try:
        now = _now()
        rows = [
            (
                (now - timedelta(days=offset)).isoformat(sep=" "),
                "sleep_deep_pct",
                value,
                f"b{offset}",
            )
            for offset, value in [(10, 20.0), (8, 21.0), (6, 19.0), (4, 20.5), (0, 5.0)]
        ]
        _seed(conn, rows)
    finally:
        conn.close()

    payload = server.sleep_deep_pct_baseline(warehouse_path=db_path)

    assert payload["status"] == "available"
    assert payload["result"]["family"] == "baseline"
    assert payload["result"]["metric_id"] == "sleep_deep_pct"
    # Latest (5.0) is well below the ~20 baseline.
    assert payload["result"]["comparison_state"] == "below"


def test_sleep_deep_pct_baseline_unavailable_has_null_numerics(tmp_path: Path) -> None:
    # Consumes WP02: an unavailable baseline must report null numerics, not a
    # fabricated 0.0. With no recorded sleep-stage data the answer is unavailable.
    payload = server.sleep_deep_pct_baseline(warehouse_path=_empty_warehouse(tmp_path))

    assert payload["status"] != "available"
    result = payload["result"]
    assert result["family"] == "baseline"
    # Honesty rule: no fabricated numeric value when the answer is not available.
    assert result["latest_value"] is None
    assert result["baseline_mean"] is None


# --------------------------------------------------------------------------- #
# Change family — one successful call + anchor-date passthrough
# --------------------------------------------------------------------------- #
def test_hrv_change_around_date_available_uses_supplied_anchor(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "change_ok")
    try:
        anchor = (_now() - timedelta(days=20)).date()
        rows: list[tuple[str, str, float, str]] = []
        # 4 readings before the anchor, 4 after — both sides above the minimum.
        for i, days_before in enumerate((10, 8, 6, 4)):
            ts = datetime.combine(anchor - timedelta(days=days_before), datetime.min.time())
            rows.append((ts.isoformat(sep=" "), "hrv_rmssd_overnight", 40.0, f"hb{i}"))
        for i, days_after in enumerate((2, 4, 6, 8)):
            ts = datetime.combine(anchor + timedelta(days=days_after), datetime.min.time())
            rows.append((ts.isoformat(sep=" "), "hrv_rmssd_overnight", 55.0, f"ha{i}"))
        _seed(conn, rows)
    finally:
        conn.close()

    payload = server.hrv_change_around_date(anchor.isoformat(), warehouse_path=db_path)

    assert payload["status"] == "available"
    assert payload["result"]["family"] == "change"
    # The user-supplied anchor flows through verbatim (explicit-anchor path,
    # not the midpoint default).
    assert payload["result"]["anchor_date"] == anchor.isoformat()
    assert payload["result"]["sufficient_data"] is True
    assert payload["result"]["before_count"] == 4
    assert payload["result"]["after_count"] == 4
    assert payload["result"]["delta"] is not None


def test_hrv_change_around_date_insufficient_data(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "change_sparse")
    try:
        anchor = (_now() - timedelta(days=20)).date()
        # Only one reading on each side: too thin to answer.
        ts_before = datetime.combine(anchor - timedelta(days=3), datetime.min.time())
        ts_after = datetime.combine(anchor + timedelta(days=3), datetime.min.time())
        _seed(
            conn,
            [
                (ts_before.isoformat(sep=" "), "hrv_rmssd_overnight", 42.0, "hb"),
                (ts_after.isoformat(sep=" "), "hrv_rmssd_overnight", 48.0, "ha"),
            ],
        )
    finally:
        conn.close()

    payload = server.hrv_change_around_date(anchor.isoformat(), warehouse_path=db_path)

    assert payload["status"] == "insufficient_data"
    assert payload["result"]["sufficient_data"] is False
    assert payload["result"]["delta"] is None
    assert payload["result"]["anchor_date"] == anchor.isoformat()


def test_hrv_change_around_date_rejects_bad_anchor(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="anchor_date"):
        server.hrv_change_around_date("not-a-date", warehouse_path=_empty_warehouse(tmp_path))


def test_requested_window_adds_transparent_caveat(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "window_caveat")
    try:
        fresh = (_now() - timedelta(days=1)).isoformat(sep=" ")
        _seed(conn, [(fresh, "resting_hr", 60.0, "w1")])
    finally:
        conn.close()

    payload = server.resting_hr_trend(lookback_days=14, warehouse_path=db_path)

    assert any("14 day" in caveat for caveat in payload["result"]["caveats"])


# --------------------------------------------------------------------------- #
# T018 — preserved behavior of the three raw tools
# --------------------------------------------------------------------------- #
def test_raw_query_warehouse_still_returns_rows(tmp_path: Path) -> None:
    result = server.query_warehouse(
        "SELECT metric_id, display_name FROM hp.dim_metric ORDER BY metric_id LIMIT 2",
        warehouse_path=_empty_warehouse(tmp_path),
    )
    assert result["row_count"] == 2
    assert result["columns"] == ["metric_id", "display_name"]
    assert result["truncated"] is False


def test_list_metrics_returns_validity_catalog_entries(tmp_path: Path) -> None:
    """T010 regression: list_metrics returns Stage 2 catalog entries (not raw counts)."""
    rows = server.list_metrics(warehouse_path=_empty_warehouse(tmp_path), limit=5)
    assert len(rows) == 5
    # WP02: catalog entries carry validity fields.
    expected_fields = {
        "metric_id", "validity_status", "validity_window", "missing_data_policy", "unit"
    }
    assert expected_fields <= set(rows[0])
    # Raw count fields must not be present.
    assert "measurement_count" not in rows[0]
    assert "interval_count" not in rows[0]
    # All-time extrema must not be present.
    assert "numeric_summary" not in rows[0]


def test_metric_summary_returns_validity_summary_entry(tmp_path: Path) -> None:
    """T010 regression: metric_summary returns Stage 2 summary entry (not all-time extrema)."""
    db_path, conn = _warehouse_with(tmp_path, "raw_summary")
    try:
        _seed(
            conn,
            [
                ("2026-01-01 10:00:00", "weight", 70.0, "k1"),
                ("2026-01-02 10:00:00", "weight", 71.5, "k2"),
            ],
        )
    finally:
        conn.close()

    summary = server.metric_summary("weight", warehouse_path=db_path)
    assert summary["metric_id"] == "weight"
    # WP02: explicit validity/imputation fields.
    assert "validity_status" in summary
    assert "sample_size" in summary
    assert "imputed_proportion" in summary
    assert "gap_count" in summary
    assert "window_days" in summary
    # All-time extrema must NOT be present.
    assert "measurement_count" not in summary
    assert "numeric_summary" not in summary


# --------------------------------------------------------------------------- #
# T009 — MCP payload tests: fresh/stale/empty/unknown for catalog and summary
# --------------------------------------------------------------------------- #

def test_list_metrics_fresh_catalog_entry(tmp_path: Path) -> None:
    """T009: a recently-observed metric returns a current catalog entry."""
    db_path, conn = _warehouse_with(tmp_path, "catalog_fresh")
    try:
        fresh_ts = (_now() - timedelta(hours=2)).isoformat(sep=" ")
        _seed(conn, [(fresh_ts, "weight", 72.0, "cf1")])
    finally:
        conn.close()

    # weight is at the end of the catalog (index ~190), so use a large limit.
    rows = server.list_metrics(warehouse_path=db_path, limit=200)
    weight_entries = [r for r in rows if r["metric_id"] == "weight"]
    assert len(weight_entries) == 1
    entry = weight_entries[0]
    assert entry["validity_status"] == "current"
    assert entry["latest_value"] == 72.0
    assert entry["latest_observation_at"] is not None
    # No raw counts or all-time extrema.
    assert "measurement_count" not in entry
    assert "numeric_summary" not in entry


def test_list_metrics_stale_catalog_entry(tmp_path: Path) -> None:
    """T009: an old-but-present metric observation returns a stale catalog entry."""
    db_path, conn = _warehouse_with(tmp_path, "catalog_stale")
    try:
        # weight validity_window is P7D; a reading 30 days old is stale.
        stale_ts = (_now() - timedelta(days=30)).isoformat(sep=" ")
        _seed(conn, [(stale_ts, "weight", 80.0, "cs1")])
    finally:
        conn.close()

    # weight is at the end of the catalog (index ~190), so use a large limit.
    rows = server.list_metrics(warehouse_path=db_path, limit=200)
    weight_entries = [r for r in rows if r["metric_id"] == "weight"]
    assert len(weight_entries) == 1
    entry = weight_entries[0]
    assert entry["validity_status"] == "stale"
    # Stale entries still carry the value (distinct from unavailable which drops it).
    assert entry["latest_value"] == 80.0


def test_list_metrics_empty_catalog_entry(tmp_path: Path) -> None:
    """T009: a registered metric with no data returns an unavailable catalog entry."""
    rows = server.list_metrics(warehouse_path=_empty_warehouse(tmp_path), limit=50)
    # Every known metric has no data in an empty warehouse.
    for entry in rows:
        assert entry["validity_status"] == "unavailable"
        assert entry["latest_value"] is None
        assert entry["latest_observation_at"] is None


def test_list_metrics_unknown_metric_id_returns_unavailable_entry(tmp_path: Path) -> None:
    """FR-004 (acceptance scenario 4): when the catalog tool is asked about an
    unknown metric id, it must return an explicit ``unavailable`` entry with no
    fabricated numeric values — not silently omit it.
    """
    rows = server.list_metrics(
        metric_ids=["nonexistent_metric_xyz"],
        warehouse_path=_empty_warehouse(tmp_path),
    )
    assert len(rows) == 1
    entry = rows[0]
    assert entry["metric_id"] == "nonexistent_metric_xyz"
    assert entry["validity_status"] == "unavailable"
    # No fabricated numerics.
    assert entry["latest_value"] is None
    assert entry["latest_observation_at"] is None
    # An explanation is present (distinguishes unknown from known-but-empty).
    assert entry["message"]


def test_list_metrics_mixes_known_and_unknown_ids(tmp_path: Path) -> None:
    """FR-004: a mixed request returns one entry per requested id, in order, with
    the unknown id surfaced as an explicit unavailable entry (never dropped)."""
    db_path = _empty_warehouse(tmp_path)
    rows = server.list_metrics(
        metric_ids=["weight", "nonexistent_metric_xyz"],
        warehouse_path=db_path,
    )
    returned_ids = [r["metric_id"] for r in rows]
    assert returned_ids == ["weight", "nonexistent_metric_xyz"]
    unknown = rows[1]
    assert unknown["validity_status"] == "unavailable"
    assert unknown["latest_value"] is None


def test_list_metrics_enumeration_returns_only_known_states(tmp_path: Path) -> None:
    """Enumeration mode (no metric_ids) surfaces registered metrics only, each
    carrying a known validity status — never a fabricated/crash state."""
    rows = server.list_metrics(warehouse_path=_empty_warehouse(tmp_path), limit=5)
    for entry in rows:
        assert entry["validity_status"] in ("current", "stale", "unavailable")
    assert "nonexistent_metric_xyz" not in {r["metric_id"] for r in rows}


def test_catalog_and_summary_tools_route_through_engine(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """FR-001 guard: the catalog/summary tools must delegate to the validity-gated
    Stage 2 engine rather than reading the fact tables directly. Spy on the engine
    helpers and assert the tools call them. A future refactor that reintroduced
    direct fact-table SQL while keeping the same payload shape would trip this.
    """
    db_path = _empty_warehouse(tmp_path)
    seen: dict[str, object] = {}

    real_catalog = server.engine.list_metric_catalog
    real_ids = server.engine.list_metric_ids
    real_summary = server.engine.metric_summary

    def spy_catalog(ids, conn):  # type: ignore[no-untyped-def]
        seen["catalog_ids"] = list(ids)
        return real_catalog(ids, conn)

    def spy_ids(conn, **kwargs):  # type: ignore[no-untyped-def]
        seen["enumerated"] = True
        return real_ids(conn, **kwargs)

    def spy_summary(metric_id, conn):  # type: ignore[no-untyped-def]
        seen["summary_id"] = metric_id
        return real_summary(metric_id, conn)

    monkeypatch.setattr(server.engine, "list_metric_catalog", spy_catalog)
    monkeypatch.setattr(server.engine, "list_metric_ids", spy_ids)
    monkeypatch.setattr(server.engine, "metric_summary", spy_summary)

    server.list_metrics(warehouse_path=db_path, limit=3)
    server.list_metrics(metric_ids=["weight"], warehouse_path=db_path)
    server.metric_summary("weight", warehouse_path=db_path)

    assert seen.get("enumerated") is True
    assert seen.get("catalog_ids") == ["weight"]
    assert seen.get("summary_id") == "weight"


def test_metric_summary_unknown_metric(tmp_path: Path) -> None:
    """T009: requesting summary for an unknown metric_id returns unavailable, not None."""
    summary = server.metric_summary(
        "nonexistent_metric_xyz", warehouse_path=_empty_warehouse(tmp_path)
    )
    assert summary is not None
    assert summary["validity_status"] == "unavailable"
    assert summary["metric_id"] == "nonexistent_metric_xyz"
    assert summary["latest_value"] is None
    assert summary["sample_size"] is None
    assert summary["imputed_proportion"] is None
    assert summary["gap_count"] is None
    # Machine-branchable: structured field identifies the issue.
    assert "not registered" in (summary.get("message") or "")


def test_metric_summary_explicit_coverage_fields(tmp_path: Path) -> None:
    """T009: summary carries explicit sample_size, imputed_proportion, gap_count."""
    db_path, conn = _warehouse_with(tmp_path, "summary_coverage")
    try:
        now = _now()
        # Three recent observations within the 30-day window.
        _seed(
            conn,
            [
                ((now - timedelta(days=10)).isoformat(sep=" "), "weight", 80.0, "sc1"),
                ((now - timedelta(days=5)).isoformat(sep=" "), "weight", 79.0, "sc2"),
                ((now - timedelta(hours=6)).isoformat(sep=" "), "weight", 78.0, "sc3"),
            ],
        )
    finally:
        conn.close()

    summary = server.metric_summary("weight", warehouse_path=db_path)
    assert summary["validity_status"] in ("current", "stale")
    # Explicit top-level coverage fields — not embedded in a nested dict.
    assert isinstance(summary["sample_size"], int)
    assert summary["sample_size"] >= 1
    assert isinstance(summary["imputed_proportion"], float)
    assert 0.0 <= summary["imputed_proportion"] <= 1.0
    assert isinstance(summary["gap_count"], int)
    assert summary["window_days"] == 30


def test_metric_summary_no_all_time_extrema(tmp_path: Path) -> None:
    """T009: metric_summary must never expose all-time min/max/avg fields."""
    db_path, conn = _warehouse_with(tmp_path, "no_extrema")
    try:
        _seed(conn, [("2026-01-01 10:00:00", "weight", 70.0, "ne1")])
    finally:
        conn.close()

    summary = server.metric_summary("weight", warehouse_path=db_path)
    # All-time extrema fields must be absent.
    assert "numeric_summary" not in summary
    assert "min_value" not in summary
    assert "max_value" not in summary
    assert "avg_value" not in summary
    assert "measurement_count" not in summary
    assert "interval_count" not in summary


# --------------------------------------------------------------------------- #
# Public MCP entrypoint reachability for all six approved signal tools
# --------------------------------------------------------------------------- #
def test_all_signal_tools_reachable_through_public_entrypoint(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "entrypoint_all")
    try:
        now = _now()

        # resting_hr_status + resting_hr_trend
        _seed(
            conn,
            [
                ((now - timedelta(days=20)).isoformat(sep=" "), "resting_hr", 55.0, "r1"),
                ((now - timedelta(days=15)).isoformat(sep=" "), "resting_hr", 57.0, "r2"),
                ((now - timedelta(days=10)).isoformat(sep=" "), "resting_hr", 60.0, "r3"),
                ((now - timedelta(days=5)).isoformat(sep=" "), "resting_hr", 63.0, "r4"),
                ((now - timedelta(hours=2)).isoformat(sep=" "), "resting_hr", 66.0, "r5"),
            ],
        )

        # weight_trend
        _seed(
            conn,
            [
                ((now - timedelta(days=28)).isoformat(sep=" "), "weight", 82.0, "w1"),
                ((now - timedelta(days=21)).isoformat(sep=" "), "weight", 81.0, "w2"),
                ((now - timedelta(days=14)).isoformat(sep=" "), "weight", 80.0, "w3"),
                ((now - timedelta(days=7)).isoformat(sep=" "), "weight", 79.0, "w4"),
                ((now - timedelta(hours=6)).isoformat(sep=" "), "weight", 78.0, "w5"),
            ],
        )

        # sleep_deep_pct_baseline
        _seed(
            conn,
            [
                ((now - timedelta(days=10)).isoformat(sep=" "), "sleep_deep_pct", 20.0, "s1"),
                ((now - timedelta(days=8)).isoformat(sep=" "), "sleep_deep_pct", 21.0, "s2"),
                ((now - timedelta(days=6)).isoformat(sep=" "), "sleep_deep_pct", 19.0, "s3"),
                ((now - timedelta(days=4)).isoformat(sep=" "), "sleep_deep_pct", 20.5, "s4"),
                ((now - timedelta(hours=5)).isoformat(sep=" "), "sleep_deep_pct", 5.0, "s5"),
            ],
        )

        # steps_trend
        _seed_intervals(
            conn,
            [
                (
                    (now - timedelta(days=5)).isoformat(sep=" "),
                    (now - timedelta(days=5)).isoformat(sep=" "),
                    "steps",
                    4000.0,
                    "st1",
                ),
                (
                    (now - timedelta(days=4)).isoformat(sep=" "),
                    (now - timedelta(days=4)).isoformat(sep=" "),
                    "steps",
                    5000.0,
                    "st2",
                ),
                (
                    (now - timedelta(days=3)).isoformat(sep=" "),
                    (now - timedelta(days=3)).isoformat(sep=" "),
                    "steps",
                    6000.0,
                    "st3",
                ),
                (
                    (now - timedelta(days=2)).isoformat(sep=" "),
                    (now - timedelta(days=2)).isoformat(sep=" "),
                    "steps",
                    7000.0,
                    "st4",
                ),
                (
                    (now - timedelta(days=1)).isoformat(sep=" "),
                    (now - timedelta(days=1)).isoformat(sep=" "),
                    "steps",
                    8000.0,
                    "st5",
                ),
            ],
        )

        # hrv_change_around_date
        anchor = (now - timedelta(days=20)).date()
        _seed(
            conn,
            [
                (
                    datetime.combine(anchor - timedelta(days=10), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    40.0,
                    "h1",
                ),
                (
                    datetime.combine(anchor - timedelta(days=8), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    41.0,
                    "h2",
                ),
                (
                    datetime.combine(anchor - timedelta(days=6), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    42.0,
                    "h3",
                ),
                (
                    datetime.combine(anchor - timedelta(days=4), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    43.0,
                    "h4",
                ),
                (
                    datetime.combine(anchor + timedelta(days=2), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    55.0,
                    "h5",
                ),
                (
                    datetime.combine(anchor + timedelta(days=4), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    56.0,
                    "h6",
                ),
                (
                    datetime.combine(anchor + timedelta(days=6), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    57.0,
                    "h7",
                ),
                (
                    datetime.combine(anchor + timedelta(days=8), datetime.min.time()).isoformat(sep=" "),
                    "hrv_rmssd_overnight",
                    58.0,
                    "h8",
                ),
            ],
        )
    finally:
        conn.close()

    async def run() -> None:
        srv = build_server(warehouse_path=db_path)

        async def call(name: str, args: dict[str, object]) -> dict[str, object]:
            result = await srv.call_tool(name, args)
            # FastMCP returns (content, structured) for tools; assert on the structured payload.
            return result[1] if isinstance(result, tuple) else result

        status_payload = await call("resting_hr_status", {})
        assert status_payload["status"] == "available"
        assert status_payload["result"]["metric_id"] == "resting_hr"
        assert status_payload["result"]["value"] == 66.0

        rhr_trend_payload = await call("resting_hr_trend", {})
        assert rhr_trend_payload["status"] == "available"
        assert rhr_trend_payload["result"]["metric_id"] == "resting_hr"
        assert rhr_trend_payload["result"]["trend_direction"] == "up"

        steps_payload = await call("steps_trend", {})
        assert steps_payload["status"] == "available"
        assert steps_payload["result"]["metric_id"] == "steps"
        assert steps_payload["result"]["trend_direction"] == "up"

        weight_payload = await call("weight_trend", {})
        assert weight_payload["status"] == "available"
        assert weight_payload["result"]["metric_id"] == "weight"
        assert weight_payload["result"]["trend_direction"] == "down"

        baseline_payload = await call("sleep_deep_pct_baseline", {})
        assert baseline_payload["status"] == "available"
        assert baseline_payload["result"]["metric_id"] == "sleep_deep_pct"
        assert baseline_payload["result"]["comparison_state"] == "below"

        change_payload = await call("hrv_change_around_date", {"anchor_date": anchor.isoformat()})
        assert change_payload["status"] == "available"
        assert change_payload["result"]["metric_id"] == "hrv_rmssd_overnight"
        assert change_payload["result"]["anchor_date"] == anchor.isoformat()
        assert change_payload["result"]["sufficient_data"] is True

    asyncio.run(run())
