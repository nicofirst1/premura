"""WP05 — trace identity + recording for the finished analytical tool set.

These pin FR-011 / FR-012 / SC-005 / NFR-006 for the two newly published tools
(``rolling_mean`` and ``paired_t_test``):

* normalized hypothesis identity registered through the trace registry seam
  (not a disclosure-counting branch): omitted defaults collapse where the engine
  supports them; different windows / anchors are different hypotheses;
* through the MCP boundary, a traced call to either new tool records EXACTLY one
  analytical call (NFR-006) — no double-count, no zero-count;
* exact retries collapse in the unique-hypothesis count while raw climbs;
* a refused call still counts toward the examined-hypothesis denominator and the
  refusal breakdown;
* a surfaced mark can target a call from either new tool;
* a traced and an untraced engine envelope are BYTE-EQUIVALENT aside from the
  wrapper-layer ``trace`` metadata (FR-011 / NFR-001).

The identity tests use the pure ``premura.trace`` service; the recording tests
go through the real MCP ``build_server`` surface over a synthetic warehouse.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

import premura.mcp.entrypoint as entrypoint
from premura import trace
from premura.mcp import server as mcp_server
from premura.store import duck

build_server = entrypoint.build_server

_METRIC = "resting_hr"


@pytest.fixture(autouse=True)
def _ensure_live_analytical_registry() -> None:
    """Heal cross-test pollution of the analytical built-in registry.

    ``tests/test_engine_contract.py`` deletes ``premura.engine.*`` from
    ``sys.modules`` and re-imports the package, leaving the already-imported MCP
    layer bound to a stale engine module whose analytical ``REGISTRY`` is empty.
    A later traced ``rolling_mean`` / ``paired_t_test`` dispatch would then raise
    ``KeyError``. Detect that and rebind the MCP layer to the live engine module so
    these tests are order-independent.
    """
    global build_server
    if not mcp_server.engine.list_analytical_tools():
        importlib.reload(mcp_server)
        importlib.reload(entrypoint)
        build_server = entrypoint.build_server


# ===========================================================================
# Part A — normalized hypothesis identity through the registry seam (T023)
# ===========================================================================


def test_both_new_tools_are_registered_in_the_identity_registry() -> None:
    """Identity is declared via the registry seam, not a counting branch."""
    assert "rolling_mean" in trace._IDENTITY_REGISTRY
    assert "paired_t_test" in trace._IDENTITY_REGISTRY


def test_rolling_mean_default_window_collapses_with_explicit_default() -> None:
    """Omitted ``window`` / ``min_coverage`` share identity with the engine default."""
    omitted = trace.hypothesis_identity("rolling_mean", {"metric_id": _METRIC})
    explicit = trace.hypothesis_identity(
        "rolling_mean",
        {"metric_id": _METRIC, "window": 7, "min_coverage": 0.5},
    )
    assert omitted == explicit


def test_rolling_mean_default_literals_match_engine_constants() -> None:
    """The duplicated default literals must not drift from the engine constants."""
    from premura.engine.rolling_mean import DEFAULT_MIN_COVERAGE, DEFAULT_WINDOW

    assert trace._DEFAULT_ROLLING_WINDOW == DEFAULT_WINDOW
    assert trace._DEFAULT_ROLLING_MIN_COVERAGE == DEFAULT_MIN_COVERAGE


def test_rolling_mean_different_window_is_distinct_hypothesis() -> None:
    """A different declared window is a different examined hypothesis."""
    w7 = trace.hypothesis_identity("rolling_mean", {"metric_id": _METRIC, "window": 7})
    w14 = trace.hypothesis_identity("rolling_mean", {"metric_id": _METRIC, "window": 14})
    assert w7 != w14


def test_paired_t_test_exact_retry_collapses() -> None:
    """Same metric/anchor/windows/direction → same identity (exact retry collapses)."""
    req = {
        "metric_id": _METRIC,
        "anchor_date": "2026-05-01",
        "before_days": 14,
        "after_days": 14,
        "expected_direction": "increase",
    }
    first = trace.hypothesis_identity("paired_t_test", dict(req))
    second = trace.hypothesis_identity("paired_t_test", dict(req))
    assert first == second


def test_paired_t_test_anchor_date_normalizes_date_and_string() -> None:
    """A ``date`` anchor and its ISO string form share identity."""
    as_str = trace.hypothesis_identity(
        "paired_t_test",
        {
            "metric_id": _METRIC,
            "anchor_date": "2026-05-01",
            "before_days": 14,
            "after_days": 14,
            "expected_direction": "increase",
        },
    )
    as_date = trace.hypothesis_identity(
        "paired_t_test",
        {
            "metric_id": _METRIC,
            "anchor_date": date(2026, 5, 1),
            "before_days": 14,
            "after_days": 14,
            "expected_direction": "increase",
        },
    )
    assert as_str == as_date


def test_paired_t_test_different_anchor_is_distinct_hypothesis() -> None:
    """A different anchor date is a distinct examined hypothesis."""
    base = {
        "metric_id": _METRIC,
        "before_days": 14,
        "after_days": 14,
        "expected_direction": "increase",
    }
    may1 = trace.hypothesis_identity("paired_t_test", {**base, "anchor_date": "2026-05-01"})
    may2 = trace.hypothesis_identity("paired_t_test", {**base, "anchor_date": "2026-05-02"})
    assert may1 != may2


def test_paired_t_test_different_direction_is_distinct_hypothesis() -> None:
    """A different declared expected direction is a distinct hypothesis (FR-005)."""
    base = {
        "metric_id": _METRIC,
        "anchor_date": "2026-05-01",
        "before_days": 14,
        "after_days": 14,
    }
    up = trace.hypothesis_identity("paired_t_test", {**base, "expected_direction": "increase"})
    down = trace.hypothesis_identity("paired_t_test", {**base, "expected_direction": "decrease"})
    assert up != down


# ===========================================================================
# Part B — recording through the MCP surface (T024 / NFR-006)
# ===========================================================================


def _series_base() -> datetime:
    """The newest point's instant: a fixed point ~12h ago (start-of-today UTC).

    Anchored so two reads of one warehouse in a single test see an identical
    window regardless of sub-second ``now()`` drift between calls — the property
    the byte-equivalence regression needs — while staying inside ``resting_hr``'s
    2-day freshness window.
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(hours=12)


def _empty_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _warehouse_with_series(tmp_path: Path, n: int = 40) -> Path:
    """Seed a ~40-day ``resting_hr`` series (oldest-first, newest ~12h ago).

    The series has a clear upward step near the midpoint so both an available
    rolling_mean and an available before/after paired difference are produced.
    """
    db_path = tmp_path / "finished.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    base = _series_base()
    conn.execute("BEGIN")
    for i in range(n):
        ts = (base - timedelta(days=(n - 1 - i))).isoformat(sep=" ")
        value = 50.0 + (i % 3) + (10.0 if i > (n // 2) else 0.0)
        conn.execute(
            """
            INSERT INTO hp.fact_measurement
                (ts_utc, metric_id, value_num, unit, source_id, dedupe_key)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [ts, _METRIC, value, "bpm", "test:source", f"k{i}"],
        )
    conn.execute("COMMIT")
    conn.close()
    return db_path


def _anchor(n: int = 40) -> str:
    """An anchor date with ~equal admissible days on each side of the seeded series."""
    return (_series_base() - timedelta(days=(n // 2))).date().isoformat()


def _call(server: FastMCP, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await server.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def _disclosure(server: FastMCP, session_id: str) -> dict[str, Any]:
    return _call(server, "research_trace_disclosure", {"session_id": session_id})


def _paired_args(session_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    args: dict[str, Any] = {
        "metric_id": _METRIC,
        "anchor_date": _anchor(),
        "before_days": 18,
        "after_days": 18,
        "expected_direction": "increase",
    }
    args.update(overrides)
    if session_id is not None:
        args["session_id"] = session_id
    return args


def test_traced_rolling_mean_records_exactly_one_call(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "rolling_mean", {"metric_id": _METRIC, "session_id": session_id})

    assert payload["status"] == "available"
    assert payload["trace"]["session_id"] == session_id
    assert payload["trace"]["call_id"]
    assert payload["trace"]["result_id"]

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 1  # NFR-006: exactly one row
    assert d["unique_hypothesis_count"] == 1


def test_traced_paired_t_test_records_exactly_one_call(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "paired_t_test", _paired_args(session_id))

    assert payload["status"] == "available"
    assert payload["trace"]["call_id"]
    assert payload["trace"]["result_id"]

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 1  # NFR-006
    assert d["unique_hypothesis_count"] == 1


def test_exact_retry_collapses_for_both_new_tools(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    rm = {"metric_id": _METRIC, "session_id": session_id}
    _call(server, "rolling_mean", dict(rm))
    _call(server, "rolling_mean", dict(rm))
    pt = _paired_args(session_id)
    _call(server, "paired_t_test", dict(pt))
    _call(server, "paired_t_test", dict(pt))

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 4  # four recorded calls
    assert d["unique_hypothesis_count"] == 2  # rolling_mean + paired_t_test, retries collapse


def test_distinct_windows_and_anchors_increase_unique_count(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    _call(server, "rolling_mean", {"metric_id": _METRIC, "window": 5, "session_id": session_id})
    _call(server, "rolling_mean", {"metric_id": _METRIC, "window": 9, "session_id": session_id})
    _call(server, "paired_t_test", _paired_args(session_id, before_days=10, after_days=10))
    _call(server, "paired_t_test", _paired_args(session_id, before_days=15, after_days=15))

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 4
    # Two distinct windows + two distinct before/after windows = 4 unique hypotheses.
    assert d["unique_hypothesis_count"] == 4


def test_refused_new_tool_call_counts_as_examined_hypothesis(tmp_path: Path) -> None:
    """A refusal (no evidence) still counts toward raw + N and the refusal breakdown."""
    server = build_server(warehouse_path=_empty_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    rm = _call(server, "rolling_mean", {"metric_id": _METRIC, "session_id": session_id})
    pt = _call(server, "paired_t_test", _paired_args(session_id))

    assert rm["status"] == "refused"
    assert pt["status"] == "refused"

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 2
    assert d["unique_hypothesis_count"] == 2  # refusals still count as examined
    assert sum(d["refusal_breakdown"].values()) == 2


def test_surfaced_mark_targets_a_new_tool_call(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "paired_t_test", _paired_args(session_id))
    call_id = payload["trace"]["call_id"]

    mark = _call(
        server,
        "research_trace_mark_surfaced",
        {
            "session_id": session_id,
            "call_id": call_id,
            "role": "claim",
            "rationale": "Reported the before/after change to the user.",
        },
    )
    assert mark["status"] == "marked"

    d = _disclosure(server, session_id)
    assert d["surfaced"]["status"] == "available"
    assert d["surfaced"]["count"] == 1


def test_non_analytical_calls_still_do_not_count(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    _call(server, "list_metrics", {"limit": 2})
    _call(server, "metric_summary", {"metric_id": _METRIC})

    d = _disclosure(server, session_id)
    assert d["raw_analytical_call_count"] == 0
    assert d["unique_hypothesis_count"] == 0


# ===========================================================================
# Part C — byte-equivalence of traced vs untraced envelopes (T025 / FR-011)
# ===========================================================================


def _engine_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """The engine-envelope portion of a wrapper payload: all but the ``trace`` key."""
    return {k: v for k, v in payload.items() if k != "trace"}


def _pin_engine_clock(monkeypatch: Any) -> None:
    """Freeze the Stage 2 evidence-read clock so two reads of one warehouse are
    byte-identical.

    The engine's window read buckets ``[now - span, now]`` and may carry an
    observation forward into the trailing bucket whose timestamp is derived from
    ``now()``. That is genuine *evidence-read* non-determinism between two separate
    dispatches, independent of tracing. Pinning the clock isolates the property
    FR-011 actually governs: tracing must not change the engine envelope produced
    for one dispatch. The pinned instant stays inside ``resting_hr``'s freshness
    window so the series remains admissible.

    Patch the clock on the *exact* ``_query`` module object the live MCP wrapper
    uses (``mcp_server.engine_query``) so a sibling reload test that left a second
    ``premura.engine._query`` object in play cannot make the patch miss the one
    ``ordered_window`` actually reads.
    """
    fixed = _series_base() + timedelta(hours=6)
    monkeypatch.setattr(mcp_server.engine_query, "_naive_utc_now", lambda: fixed)


def test_rolling_mean_envelope_byte_identical_traced_vs_untraced(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _pin_engine_clock(monkeypatch)
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))

    untraced = _call(server, "rolling_mean", {"metric_id": _METRIC, "window": 5})
    session_id = _call(server, "research_trace_open", {})["session_id"]
    traced = _call(
        server, "rolling_mean", {"metric_id": _METRIC, "window": 5, "session_id": session_id}
    )

    assert "trace" in traced
    assert "trace" not in untraced
    assert json.dumps(_engine_envelope(untraced), sort_keys=True) == json.dumps(
        _engine_envelope(traced), sort_keys=True
    )


def test_paired_t_test_envelope_byte_identical_traced_vs_untraced(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _pin_engine_clock(monkeypatch)
    server = build_server(warehouse_path=_warehouse_with_series(tmp_path))

    args = _paired_args()
    untraced = _call(server, "paired_t_test", dict(args))
    session_id = _call(server, "research_trace_open", {})["session_id"]
    traced = _call(server, "paired_t_test", {**args, "session_id": session_id})

    assert "trace" in traced
    assert "trace" not in untraced
    assert json.dumps(_engine_envelope(untraced), sort_keys=True) == json.dumps(
        _engine_envelope(traced), sort_keys=True
    )
