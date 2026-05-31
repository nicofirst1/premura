"""WP03 — analytical-call recording + engine-purity regression (through the MCP surface).

These exercise the opt-in trace recording on the three analytical wrappers
(``change_point`` / ``smoothed_average`` / ``correlate``) THROUGH the MCP boundary
(``FastMCP.call_tool``), and the engine-purity regression that enforces NFR-001:

* a successful analytical call in an open session is recorded (raw + N);
* a refused analytical call is recorded and counts toward raw and N;
* an exact retry increases raw calls but NOT the unique-hypothesis count;
* ``list_metrics`` / ``metric_summary`` are NOT analytical calls — no trace row;
* a call with NO ``session_id`` writes no trace row and the response shape is
  unchanged (opt-in by explicit session association, T015);
* the engine result envelope is BYTE-IDENTICAL with tracing on vs off — trace
  metadata lives only under a top-level ``trace`` key at the wrapper layer (T016 /
  T018 / NFR-001).

Synthetic warehouses only.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from premura.mcp.entrypoint import build_server
from premura.store import duck

# resting_hr is covered by a RECENT_TREND-admissible built-in policy, so a fresh
# seeded run is admissible and the analytical tools actually compute over it.
_METRIC = "resting_hr"


def _now() -> datetime:
    return datetime.utcnow()


def _empty_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _warehouse_with_series(tmp_path: Path, values: list[float]) -> Path:
    """Seed one daily metric series (oldest-first) and return its warehouse path."""
    db_path = tmp_path / "recording.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    now = _now()
    n = len(values)
    conn.execute("BEGIN")
    for i, value in enumerate(values):
        ts = (now - timedelta(days=(n - 1 - i))).isoformat(sep=" ")
        conn.execute(
            """
            INSERT INTO hp.fact_measurement (
                ts_utc, metric_id, value_num, unit, source_id, dedupe_key
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [ts, _METRIC, value, "bpm", "test:source", f"k{i}"],
        )
    conn.execute("COMMIT")
    conn.close()
    return db_path


def _call(server: FastMCP, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await server.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def _disclosure(server: FastMCP, session_id: str) -> dict[str, Any]:
    return _call(server, "research_trace_disclosure", {"session_id": session_id})


# --------------------------------------------------------------------------- #
# A successful analytical call is recorded.
# --------------------------------------------------------------------------- #
def test_successful_analytical_call_is_recorded(tmp_path: Path) -> None:
    server = build_server(
        warehouse_path=_warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    )
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "change_point", {"metric_id": _METRIC, "session_id": session_id})

    # The engine envelope says available; the wrapper attached trace refs beside it.
    assert payload["status"] == "available"
    assert payload["trace"]["session_id"] == session_id
    assert payload["trace"]["call_id"]
    assert payload["trace"]["result_id"]  # an available call gets a result reference

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 1
    assert d["unique_hypothesis_count"] == 1
    assert d["refusal_breakdown"] == {}


# --------------------------------------------------------------------------- #
# A refused analytical call is recorded and counted (toward raw and N).
# --------------------------------------------------------------------------- #
def test_refused_analytical_call_is_recorded_and_counted(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_empty_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "change_point", {"metric_id": _METRIC, "session_id": session_id})

    assert payload["status"] == "refused"
    assert payload["trace"]["terminal_status"] == "refused"

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 1
    assert d["unique_hypothesis_count"] == 1
    # The refusal reason appears in the machine-readable breakdown.
    assert sum(d["refusal_breakdown"].values()) == 1


# --------------------------------------------------------------------------- #
# Exact retry increases raw calls but NOT the unique-hypothesis count.
# --------------------------------------------------------------------------- #
def test_exact_retry_increases_raw_but_not_unique(tmp_path: Path) -> None:
    server = build_server(
        warehouse_path=_warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    )
    session_id = _call(server, "research_trace_open", {})["session_id"]

    args = {"metric_id": _METRIC, "session_id": session_id}
    _call(server, "change_point", args)
    _call(server, "change_point", args)  # exact retry

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 2  # two recorded calls
    assert d["unique_hypothesis_count"] == 1  # same hypothesis collapses


def test_distinct_hypotheses_increase_unique_count(tmp_path: Path) -> None:
    server = build_server(
        warehouse_path=_warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    )
    session_id = _call(server, "research_trace_open", {})["session_id"]

    _call(server, "change_point", {"metric_id": _METRIC, "session_id": session_id})
    # Different tool => different hypothesis identity.
    _call(
        server,
        "smoothed_average",
        {"metric_id": _METRIC, "window": 3, "session_id": session_id},
    )

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 2
    assert d["unique_hypothesis_count"] == 2


# --------------------------------------------------------------------------- #
# Non-analytical calls do NOT count (no trace row).
# --------------------------------------------------------------------------- #
def test_list_metrics_and_metric_summary_are_not_recorded(tmp_path: Path) -> None:
    server = build_server(
        warehouse_path=_warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    )
    session_id = _call(server, "research_trace_open", {})["session_id"]

    # These take no session_id and are not analytical questions: no trace row.
    lm = _call(server, "list_metrics", {"limit": 3})
    ms = _call(server, "metric_summary", {"metric_id": _METRIC})
    assert "trace" not in lm
    assert "trace" not in ms

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 0
    assert d["unique_hypothesis_count"] == 0


# --------------------------------------------------------------------------- #
# T015 — opt-in only: no session_id => no trace row, unchanged response shape.
# --------------------------------------------------------------------------- #
def test_analytical_call_without_session_writes_no_trace_row(tmp_path: Path) -> None:
    server = build_server(
        warehouse_path=_warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    )
    # A session exists, but the analytical call is NOT associated with it.
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "change_point", {"metric_id": _METRIC})

    assert payload["status"] == "available"
    # Untraced response shape is unchanged: no wrapper trace key.
    assert "trace" not in payload

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 0
    assert d["unique_hypothesis_count"] == 0


# --------------------------------------------------------------------------- #
# T018 — engine-purity regression: traced and untraced engine envelopes are
# byte-identical (enforces NFR-001). Trace metadata stays at the wrapper layer.
# --------------------------------------------------------------------------- #
def _engine_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """The engine-envelope portion of a wrapper payload: everything but the
    wrapper-layer ``trace`` metadata."""
    return {k: v for k, v in payload.items() if k != "trace"}


def test_change_point_envelope_byte_identical_traced_vs_untraced(tmp_path: Path) -> None:
    import json

    server = build_server(
        warehouse_path=_warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    )

    untraced = _call(server, "change_point", {"metric_id": _METRIC})
    session_id = _call(server, "research_trace_open", {})["session_id"]
    traced = _call(server, "change_point", {"metric_id": _METRIC, "session_id": session_id})

    # Tracing added ONLY the wrapper-layer trace metadata; the engine envelope is
    # byte-identical. If this fails, fix the boundary — do NOT weaken the assert.
    assert "trace" in traced
    assert "trace" not in untraced
    assert json.dumps(_engine_envelope(untraced), sort_keys=True) == json.dumps(
        _engine_envelope(traced), sort_keys=True
    )


def test_correlate_envelope_byte_identical_traced_vs_untraced(tmp_path: Path) -> None:
    import json

    # Two metrics from different families so the lagged association is admissible.
    db_path = tmp_path / "corr.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    now = _now()
    left = [60, 61, 62, 63, 64, 65, 66, 67, 68, 69]
    right = [50.0, 51, 52, 53, 54, 55, 56, 57, 58, 59]
    n = len(left)
    insert_sql = (
        "INSERT INTO hp.fact_measurement "
        "(ts_utc, metric_id, value_num, unit, source_id, dedupe_key) "
        "VALUES (?,?,?,?,?,?)"
    )
    conn.execute("BEGIN")
    for i in range(n):
        ts = (now - timedelta(days=(n - 1 - i))).isoformat(sep=" ")
        conn.execute(insert_sql, [ts, "resting_hr", left[i], "bpm", "test:source", f"l{i}"])
        conn.execute(insert_sql, [ts, "sleep_efficiency", right[i], "pct", "test:source", f"r{i}"])
    conn.execute("COMMIT")
    conn.close()

    server = build_server(warehouse_path=db_path)
    args = {
        "left_metric_id": "resting_hr",
        "right_metric_id": "sleep_efficiency",
        "lag_days": 1,
        "expected_direction": "positive",
    }
    untraced = _call(server, "correlate", dict(args))
    session_id = _call(server, "research_trace_open", {})["session_id"]
    traced = _call(server, "correlate", {**args, "session_id": session_id})

    assert "trace" in traced
    assert json.dumps(_engine_envelope(untraced), sort_keys=True) == json.dumps(
        _engine_envelope(traced), sort_keys=True
    )
