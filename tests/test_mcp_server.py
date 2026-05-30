from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from premura.store import duck


def _initialized_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.duckdb"
    conn = duck.initialize(db_path)
    conn.close()
    return db_path


def _initialized_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    db_path = data_dir / "duck" / "health.duckdb"
    conn = duck.initialize(db_path)
    try:
        duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
        conn.execute(
            """
            INSERT INTO hp.fact_measurement (
                ts_utc, metric_id, value_num, unit, source_id, dedupe_key
            ) VALUES
                ('2026-01-01 10:00:00', 'weight', 70.0, 'kg', 'test:source', 'k1'),
                ('2026-01-02 10:00:00', 'weight', 71.5, 'kg', 'test:source', 'k2')
            """
        )
    finally:
        conn.close()
    return data_dir


def test_query_warehouse_returns_rows_from_read_only_connection(tmp_path: Path) -> None:
    from premura.mcp.server import query_warehouse

    result = query_warehouse(
        "SELECT metric_id, display_name FROM hp.dim_metric ORDER BY metric_id LIMIT 2",
        warehouse_path=_initialized_warehouse(tmp_path),
    )

    assert result["row_count"] == 2
    assert result["columns"] == ["metric_id", "display_name"]
    assert len(result["rows"]) == 2
    assert result["truncated"] is False
    assert result["rows"][0]["metric_id"] < result["rows"][1]["metric_id"]


def test_query_warehouse_rejects_non_read_queries(tmp_path: Path) -> None:
    from premura.mcp.server import query_warehouse

    with pytest.raises(ValueError, match="read-only"):
        query_warehouse(
            "DELETE FROM hp.dim_metric",
            warehouse_path=_initialized_warehouse(tmp_path),
        )


def test_query_warehouse_truncates_large_result_sets(tmp_path: Path) -> None:
    from premura.mcp.server import query_warehouse

    result = query_warehouse(
        "SELECT metric_id FROM hp.dim_metric ORDER BY metric_id",
        warehouse_path=_initialized_warehouse(tmp_path),
        max_rows=1,
    )

    assert result["row_count"] == 1
    assert result["max_rows"] == 1
    assert result["truncated"] is True


def test_query_warehouse_rejects_invalid_max_rows(tmp_path: Path) -> None:
    from premura.mcp.server import query_warehouse

    with pytest.raises(ValueError, match="max_rows"):
        query_warehouse(
            "SELECT 1",
            warehouse_path=_initialized_warehouse(tmp_path),
            max_rows=0,
        )


def test_list_metrics_reports_seeded_metrics(tmp_path: Path) -> None:
    from premura.mcp.server import list_metrics

    rows = list_metrics(warehouse_path=_initialized_warehouse(tmp_path), limit=5)

    assert len(rows) == 5
    # WP02: new catalog payload carries validity fields, not raw row-counts.
    required_fields = {
        "metric_id", "validity_status", "validity_window", "missing_data_policy", "unit"
    }
    assert required_fields <= set(rows[0])
    # Raw count fields must not be present in the new payload.
    assert "measurement_count" not in rows[0]
    assert "interval_count" not in rows[0]


def test_metric_summary_reports_validity_fields(tmp_path: Path) -> None:
    """WP02: metric_summary returns validity/imputation envelope, not all-time extrema."""
    from premura.mcp.server import metric_summary

    db_path = tmp_path / "summary.duckdb"
    conn = duck.initialize(db_path)
    try:
        duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
        conn.execute(
            """
            INSERT INTO hp.fact_measurement (
                ts_utc, metric_id, value_num, unit, source_id, dedupe_key
            ) VALUES
                ('2026-01-01 10:00:00', 'weight', 70.0, 'kg', 'test:source', 'k1'),
                ('2026-01-02 10:00:00', 'weight', 71.5, 'kg', 'test:source', 'k2')
            """
        )
    finally:
        conn.close()

    summary = metric_summary("weight", warehouse_path=db_path)

    assert summary["metric_id"] == "weight"
    # WP02: new explicit validity/imputation fields, not raw counts or all-time extrema.
    assert "validity_status" in summary
    assert "sample_size" in summary
    assert "imputed_proportion" in summary
    assert "gap_count" in summary
    assert "window_days" in summary
    # Old all-time extrema must not be present.
    assert "measurement_count" not in summary
    assert "numeric_summary" not in summary


def test_metric_summary_returns_unavailable_for_missing_metric(tmp_path: Path) -> None:
    """WP02: unknown metric yields unavailable entry, not None."""
    from premura.mcp.server import metric_summary

    summary = metric_summary("missing_metric", warehouse_path=_initialized_warehouse(tmp_path))
    # New behavior: structured unavailable entry, not None.
    assert summary is not None
    assert summary["validity_status"] == "unavailable"
    assert summary["metric_id"] == "missing_metric"
    assert summary["latest_value"] is None


def test_list_metrics_rejects_negative_paging_arguments(tmp_path: Path) -> None:
    from premura.mcp.server import list_metrics

    with pytest.raises(ValueError, match="limit"):
        list_metrics(warehouse_path=_initialized_warehouse(tmp_path), limit=-1)

    with pytest.raises(ValueError, match="offset"):
        list_metrics(warehouse_path=_initialized_warehouse(tmp_path), offset=-1)


def test_metric_summary_rejects_blank_metric_id(tmp_path: Path) -> None:
    from premura.mcp.server import metric_summary

    with pytest.raises(ValueError, match="metric_id"):
        metric_summary("   ", warehouse_path=_initialized_warehouse(tmp_path))


# WP03: default surface omits query_warehouse; the agent-safe tools = the six
# Stage 2 signals + two catalog tools + the two bounded profile-capture tools.
# WP06: the two Stage 3 analytical tools (change_point / smoothed_average) join
# the same default surface.
# WP04 (correlate mission): the pre-registered lagged-association tool
# ``correlate`` joins the same default surface (twelve -> thirteen tools).
_DEFAULT_TOOLS = sorted(
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
        "correlate",
    ]
)

# WP03: operator surface = default tools + query_warehouse (exactly one extra).
_OPERATOR_TOOLS = sorted(_DEFAULT_TOOLS + ["query_warehouse"])


def test_build_server_registers_expected_tools() -> None:
    """Default surface must not include query_warehouse."""
    from premura.mcp.entrypoint import build_server

    async def run() -> None:
        server = build_server()
        assert sorted(tool.name for tool in await server.list_tools()) == _DEFAULT_TOOLS

    asyncio.run(run())


def test_default_server_excludes_query_warehouse() -> None:
    """query_warehouse must be absent from the default agent-safe surface."""
    from premura.mcp.entrypoint import build_server

    async def run() -> None:
        server = build_server()
        tool_names = {tool.name for tool in await server.list_tools()}
        assert "query_warehouse" not in tool_names

    asyncio.run(run())


def test_operator_server_includes_query_warehouse() -> None:
    """Operator surface must expose query_warehouse."""
    from premura.mcp.entrypoint import build_operator_server

    async def run() -> None:
        server = build_operator_server()
        tool_names = {tool.name for tool in await server.list_tools()}
        assert "query_warehouse" in tool_names

    asyncio.run(run())


def test_operator_server_registers_expected_tools() -> None:
    """Operator surface must expose exactly the default tools plus query_warehouse."""
    from premura.mcp.entrypoint import build_operator_server

    async def run() -> None:
        server = build_operator_server()
        assert sorted(tool.name for tool in await server.list_tools()) == _OPERATOR_TOOLS

    asyncio.run(run())


def test_operator_surface_differs_from_default_by_exactly_query_warehouse() -> None:
    """The exact difference between operator and default surfaces is query_warehouse."""
    from premura.mcp.entrypoint import build_operator_server, build_server

    async def run() -> None:
        default_server = build_server()
        operator_server = build_operator_server()
        default_names = {tool.name for tool in await default_server.list_tools()}
        operator_names = {tool.name for tool in await operator_server.list_tools()}
        assert operator_names - default_names == {"query_warehouse"}
        assert default_names - operator_names == set()

    asyncio.run(run())


def test_stdio_mcp_server_exposes_tools(tmp_path: Path) -> None:
    data_dir = _initialized_data_dir(tmp_path)
    warehouse_path = data_dir / "duck" / "health.duckdb"

    async def run() -> None:
        params = StdioServerParameters(
            command="uv",
            args=["run", "premura-mcp", "--warehouse-path", str(warehouse_path)],
            env=dict(os.environ),
            cwd=Path(__file__).resolve().parent.parent,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                # WP03: default surface no longer includes query_warehouse.
                assert sorted(tool.name for tool in tools.tools) == _DEFAULT_TOOLS

                metrics = await session.call_tool("list_metrics", {"limit": 2})
                assert metrics.isError is False
                assert metrics.structuredContent is not None
                assert metrics.structuredContent["count"] == 2

                summary = await session.call_tool("metric_summary", {"metric_id": "weight"})
                assert summary.isError is False
                assert summary.structuredContent is not None
                # WP02: new payload carries validity fields, not raw measurement_count.
                assert summary.structuredContent["summary"]["validity_status"] in (
                    "current", "stale", "unavailable"
                )

    asyncio.run(run())


def test_operator_entry_refuses_without_ack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator console entry refuses to start (exposing query_warehouse)
    unless the launcher explicitly acknowledges lower-guarantee mode."""
    from premura.mcp.entrypoint import main_operator

    monkeypatch.delenv("PREMURA_OPERATOR_ACK", raising=False)
    warehouse_path = _initialized_data_dir(tmp_path) / "duck" / "health.duckdb"
    with pytest.raises(SystemExit):
        main_operator(["--warehouse-path", str(warehouse_path)])


def test_operator_entry_starts_with_flag_ack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--ack satisfies the operator acknowledgment gate and starts the server."""
    from premura.mcp import entrypoint

    monkeypatch.delenv("PREMURA_OPERATOR_ACK", raising=False)
    started: dict[str, object] = {}

    class _StubServer:
        def run(self, *, transport: str) -> None:
            started["transport"] = transport

    monkeypatch.setattr(entrypoint, "build_operator_server", lambda **kwargs: _StubServer())
    warehouse_path = _initialized_data_dir(tmp_path) / "duck" / "health.duckdb"
    entrypoint.main_operator(["--warehouse-path", str(warehouse_path), "--ack"])
    assert started["transport"] == "stdio"


def test_operator_entry_starts_with_env_ack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PREMURA_OPERATOR_ACK=1 satisfies the gate without the CLI flag."""
    from premura.mcp import entrypoint

    monkeypatch.setenv("PREMURA_OPERATOR_ACK", "1")
    started: dict[str, object] = {}

    class _StubServer:
        def run(self, *, transport: str) -> None:
            started["transport"] = transport

    monkeypatch.setattr(entrypoint, "build_operator_server", lambda **kwargs: _StubServer())
    warehouse_path = _initialized_data_dir(tmp_path) / "duck" / "health.duckdb"
    entrypoint.main_operator(["--warehouse-path", str(warehouse_path)])
    assert started["transport"] == "stdio"


def test_stdio_operator_server_exposes_query_warehouse(tmp_path: Path) -> None:
    """End-to-end: the premura-mcp-operator console script (launched with --ack)
    starts over stdio, exposes exactly the operator tool set, and query_warehouse
    is usable. Guards the operator packaging/entrypoint wiring against regression."""
    data_dir = _initialized_data_dir(tmp_path)
    warehouse_path = data_dir / "duck" / "health.duckdb"

    async def run() -> None:
        params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "premura-mcp-operator",
                "--warehouse-path",
                str(warehouse_path),
                "--ack",
            ],
            env=dict(os.environ),
            cwd=Path(__file__).resolve().parent.parent,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert sorted(tool.name for tool in tools.tools) == _OPERATOR_TOOLS

                result = await session.call_tool("query_warehouse", {"sql": "SELECT 1 AS one"})
                assert result.isError is False

    asyncio.run(run())
