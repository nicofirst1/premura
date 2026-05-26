"""WP04 — Stage 3 signal-backed MCP tool tests.

These lock the new MCP surface that exposes the six grounded Stage 2 answers:

* registration publishes all nine tools (3 raw + 6 signal-backed);
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

_NINE_TOOLS = sorted(
    [
        "query_warehouse",
        "list_metrics",
        "metric_summary",
        "resting_hr_status",
        "resting_hr_trend",
        "steps_trend",
        "weight_trend",
        "sleep_deep_pct_baseline",
        "hrv_change_around_date",
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
# T021 — registration includes all nine tools
# --------------------------------------------------------------------------- #
def test_build_server_publishes_all_nine_tools() -> None:
    async def run() -> None:
        srv = build_server()
        names = sorted(tool.name for tool in await srv.list_tools())
        assert names == _NINE_TOOLS

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


def test_raw_list_metrics_still_lists(tmp_path: Path) -> None:
    rows = server.list_metrics(warehouse_path=_empty_warehouse(tmp_path), limit=5)
    assert len(rows) == 5
    assert {"metric_id", "display_name", "canonical_unit"} <= set(rows[0])


def test_raw_metric_summary_still_summarizes(tmp_path: Path) -> None:
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
    assert summary["measurement_count"] == 2
    assert summary["numeric_summary"] == {"min": 70.0, "max": 71.5, "avg": 70.75}


# --------------------------------------------------------------------------- #
# Public MCP entrypoint reachability for a representative signal tool
# --------------------------------------------------------------------------- #
def test_signal_tool_reachable_through_public_entrypoint(tmp_path: Path) -> None:
    db_path, conn = _warehouse_with(tmp_path, "entrypoint")
    try:
        fresh = (_now() - timedelta(hours=2)).isoformat(sep=" ")
        _seed(conn, [(fresh, "resting_hr", 59.0, "e1")])
    finally:
        conn.close()

    async def run() -> None:
        srv = build_server(warehouse_path=db_path)
        result = await srv.call_tool("resting_hr_status", {})
        # FastMCP returns (content, structured) for tools; assert on the structured payload.
        structured = result[1] if isinstance(result, tuple) else result
        assert structured["status"] == "available"
        assert structured["result"]["metric_id"] == "resting_hr"
        assert structured["result"]["value"] == 59.0

    asyncio.run(run())
