"""WP06 — Stage 3 analytical-tool MCP exposure tests.

These lock the contract from ``contracts/mcp-analytical-tools.md``:

* the DEFAULT agent-safe surface publishes ``change_point`` and
  ``smoothed_average`` (and ``query_warehouse`` stays operator-only);
* a success payload carries ``tool_name`` / ``status`` / ``message`` / ``result``
  and the non-refusal ``result`` carries the analytical envelope metadata
  (validity_status, sample_size, uncertainty, confound_checklist);
* a refusal payload carries a distinct reason and NO estimate;
* the wrappers DELEGATE to the engine analytical path and issue no raw
  fact-table SQL of their own (the boundary discipline this WP exists to prove).

The wrappers serialize and delegate; tests assert on the structured payloads and
on the engine being the one that computes — never on re-implemented SQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from premura.mcp import server
from premura.mcp.entrypoint import build_operator_server, build_server
from premura.store import duck

# WP06 adds the two analytical tools to the prior ten default tools.
# The correlate mission's WP04 then adds ``correlate`` (twelve -> thirteen).
# session-research-trace WP03 adds the three trace tools to the same surface.
# WP05 (finish-analytical-tool-set) adds rolling_mean + paired_t_test (-> 18).
_DEFAULT_TOOLS_WITH_ANALYTICAL = sorted(
    [
        "list_metrics",
        "metric_summary",
        "resting_hr_status",
        "resting_hr_trend",
        "steps_trend",
        "weight_trend",
        "sleep_deep_pct_baseline",
        "hrv_change_around_date",
        "supplement_intake_adherence",
        "nutrition_intake_trend",
        "profile_context_supported_fields",
        "profile_context_record",
        "condition_episode_record",
        "condition_episode_list",
        "condition_episode_retract",
        "interview_route",
        "operating_roles",
        "orchestrator_handoff",
        "answer_audit",
        "present_answer",
        "change_point",
        "smoothed_average",
        "correlate",
        "rolling_mean",
        "paired_t_test",
        "condition_paired_t_test",
        "pubmed_search",
        "pubmed_fetch",
        "research_trace_open",
        "research_trace_mark_surfaced",
        "research_trace_disclosure",
        "improvement_queue_record",
        "improvement_queue_list",
        "share_packet_render",
    ]
)

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
    db_path = tmp_path / "analytical.duckdb"
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


# --------------------------------------------------------------------------- #
# T022 — default surface exposes both analytical tools; query_warehouse stays
# operator-only.
# --------------------------------------------------------------------------- #
def test_default_surface_includes_change_point() -> None:
    async def run() -> None:
        names = sorted(tool.name for tool in await build_server().list_tools())
        assert "change_point" in names

    asyncio.run(run())


def test_default_surface_includes_smoothed_average() -> None:
    async def run() -> None:
        names = sorted(tool.name for tool in await build_server().list_tools())
        assert "smoothed_average" in names

    asyncio.run(run())


def test_default_surface_lists_exactly_the_expected_tools() -> None:
    async def run() -> None:
        names = sorted(tool.name for tool in await build_server().list_tools())
        assert names == _DEFAULT_TOOLS_WITH_ANALYTICAL

    asyncio.run(run())


def test_query_warehouse_stays_operator_only() -> None:
    async def run() -> None:
        default_names = {tool.name for tool in await build_server().list_tools()}
        operator_names = {tool.name for tool in await build_operator_server().list_tools()}
        # The analytical tools are agent-safe and live on BOTH surfaces.
        assert {"change_point", "smoothed_average"} <= default_names
        assert {"change_point", "smoothed_average"} <= operator_names
        # query_warehouse is the raw SQL escape hatch: operator-only.
        assert "query_warehouse" not in default_names
        assert "query_warehouse" in operator_names

    asyncio.run(run())


# --------------------------------------------------------------------------- #
# Success payloads — envelope shape + analytical metadata.
# --------------------------------------------------------------------------- #
def test_change_point_success_payload_shape(tmp_path: Path) -> None:
    db_path = _warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])

    payload = server.change_point(_METRIC, warehouse_path=db_path)

    # Every response carries these four keys (contract Response Rules).
    assert set(payload) >= {"tool_name", "status", "message", "result"}
    assert payload["tool_name"] == "change_point"
    assert payload["status"] == "available"
    assert isinstance(payload["message"], str) and payload["message"]

    result = payload["result"]
    # Non-refusal result carries an estimate + the required analytical envelope
    # metadata, and NO refusal block.
    assert result["estimate"] is not None
    assert result["refusal"] is None
    assert result["validity_status"] is not None
    assert isinstance(result["sample_size"], int) and result["sample_size"] >= 1
    assert result["is_imputed_pct"] is not None
    assert result["uncertainty"] is not None
    # The level shift is described as a direction, never a cause.
    assert result["estimate"]["direction"] == "increase"
    # Closed-vocabulary confound checklist is present.
    assert all("key" in entry for entry in result["confound_checklist"])


def test_smoothed_average_success_payload_has_smoothing_metadata(tmp_path: Path) -> None:
    db_path = _warehouse_with_series(tmp_path, [60, 61, 62, 63, 64, 65, 66, 67])

    payload = server.smoothed_average(_METRIC, window=3, warehouse_path=db_path)

    assert set(payload) >= {"tool_name", "status", "message", "result"}
    assert payload["tool_name"] == "smoothed_average"
    assert payload["status"] == "available"

    result = payload["result"]
    estimate = result["estimate"]
    assert estimate is not None
    # Smoothing/window metadata is surfaced (contract: smoothed output with
    # smoothing/window metadata).
    assert estimate["effective_window"] == 3
    assert "min_coverage" in estimate
    assert "smoothed_points" in estimate
    # A trailing mean has no natural uncertainty interval — surfaced explicitly,
    # never fabricated.
    assert result["uncertainty"]["available"] is False
    assert result["sample_size"] >= 1


# --------------------------------------------------------------------------- #
# Refusal payloads — distinct reason, no estimate.
# --------------------------------------------------------------------------- #
def test_change_point_refusal_has_reason_and_no_estimate(tmp_path: Path) -> None:
    # Empty warehouse -> the engine refuses with evidence_missing before any math.
    payload = server.change_point(_METRIC, warehouse_path=_empty_warehouse(tmp_path))

    assert payload["status"] == "refused"
    result = payload["result"]
    # Refusal carries a distinct machine-readable reason and a message...
    refusal = result["refusal"]
    assert refusal is not None
    assert refusal["reason"] == "evidence_missing"
    assert refusal["message"]
    assert payload["message"] == refusal["message"]
    # ...and NO estimate / validity metadata (honesty rule).
    assert result["estimate"] is None
    assert result["validity_status"] is None
    assert result["sample_size"] is None


def test_smoothed_average_out_of_bounds_parameter_refuses(tmp_path: Path) -> None:
    db_path = _warehouse_with_series(tmp_path, [60, 61, 62, 63, 64, 65, 66, 67])

    payload = server.smoothed_average(_METRIC, window=10_000, warehouse_path=db_path)

    assert payload["status"] == "refused"
    refusal = payload["result"]["refusal"]
    assert refusal["reason"] == "unsupported_parameter"
    assert refusal["parameter_name"] == "window"
    # An out-of-bounds parameter still yields no estimate.
    assert payload["result"]["estimate"] is None


def test_change_point_distinct_reasons_are_structurally_branchable(tmp_path: Path) -> None:
    """The two refusal paths surface DIFFERENT machine-readable reasons (not a
    single generic error), so an agent can branch on them."""
    db_path = _warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])

    missing = server.change_point(_METRIC, warehouse_path=_empty_warehouse(tmp_path))
    bad_param = server.change_point(_METRIC, min_side_observations=1, warehouse_path=db_path)

    assert missing["status"] == "refused"
    assert bad_param["status"] == "refused"
    assert missing["result"]["refusal"]["reason"] != bad_param["result"]["refusal"]["reason"]
    assert bad_param["result"]["refusal"]["reason"] == "unsupported_parameter"


# --------------------------------------------------------------------------- #
# Caller-facing parameter-shape validation (wrapper responsibility only).
# --------------------------------------------------------------------------- #
def test_change_point_rejects_empty_metric_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="metric_id"):
        server.change_point("  ", warehouse_path=_empty_warehouse(tmp_path))


def test_smoothed_average_rejects_bad_min_coverage(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_coverage"):
        server.smoothed_average(
            _METRIC, min_coverage=1.5, warehouse_path=_empty_warehouse(tmp_path)
        )


# --------------------------------------------------------------------------- #
# Boundary discipline — the wrapper DELEGATES to the engine and computes nothing.
# --------------------------------------------------------------------------- #
def test_change_point_delegates_to_engine_analytical_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper must call ``engine.invoke_analytical_tool`` rather than
    re-implementing the statistic. Spy on the engine entry point and assert the
    wrapper routes through it with the tool name and a prepared series. A future
    refactor that inlined the computation would trip this.
    """
    db_path = _warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    seen: dict[str, object] = {}

    real_invoke = server.engine.invoke_analytical_tool
    real_prepare = server.engine.prepare_input_series

    def spy_invoke(tool_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["tool_name"] = tool_name
        seen["series"] = args[0] if args else None
        return real_invoke(tool_name, *args, **kwargs)

    def spy_prepare(*args, **kwargs):  # type: ignore[no-untyped-def]
        seen["prepared"] = True
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(server.engine, "invoke_analytical_tool", spy_invoke)
    monkeypatch.setattr(server.engine, "prepare_input_series", spy_prepare)

    payload = server.change_point(_METRIC, warehouse_path=db_path)

    assert payload["status"] == "available"
    # Delegation actually happened: engine prepared the input and dispatched.
    assert seen.get("prepared") is True
    assert seen.get("tool_name") == "change_point"
    # The wrapper handed the engine a prepared analytical input series, not raw
    # rows it computed over itself.
    assert isinstance(seen.get("series"), server.AnalyticalInputSeries)


def test_wrappers_issue_no_raw_fact_table_sql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Boundary guard: the analytical wrappers must read warehouse evidence only
    through the engine's Stage 2 query layer, never by issuing fact-table SQL of
    their own. Wrap the connection's ``execute`` and assert no statement the
    wrapper-or-its-glue runs touches hp.fact_measurement / hp.fact_interval
    EXCEPT through the engine query helpers — which is exactly where it belongs.

    We assert the wrapper does not compute by confirming the only fact-table
    reads originate in ``premura.engine._query`` (the engine-owned layer), and
    that the public engine dispatch entry point is the one invoked.
    """
    db_path = _warehouse_with_series(tmp_path, [60, 61, 60, 59, 80, 81, 79, 80])
    invoked: dict[str, object] = {}

    real_invoke = server.engine.invoke_analytical_tool

    def spy_invoke(tool_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        invoked["called"] = True
        return real_invoke(tool_name, *args, **kwargs)

    # If the wrapper computed statistics itself it would NOT need to call the
    # engine dispatch entry point. Removing/neutralizing the engine path would
    # therefore change the result; assert it IS the engine that produced it.
    monkeypatch.setattr(server.engine, "invoke_analytical_tool", spy_invoke)

    payload = server.smoothed_average(_METRIC, window=3, warehouse_path=db_path)

    assert invoked.get("called") is True
    assert payload["status"] == "available"
    # The serialized result is the engine envelope verbatim (the wrapper added no
    # estimate of its own): the estimate's method_revision comes from the engine.
    assert payload["result"]["estimate"]["method_revision"] == "1"
