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
    from premura.mcp_server import query_warehouse

    result = query_warehouse(
        "SELECT metric_id, display_name FROM hp.dim_metric ORDER BY metric_id LIMIT 2",
        warehouse_path=_initialized_warehouse(tmp_path),
    )

    assert result["row_count"] == 2
    assert result["columns"] == ["metric_id", "display_name"]
    assert len(result["rows"]) == 2
    assert result["rows"][0]["metric_id"] < result["rows"][1]["metric_id"]


def test_query_warehouse_rejects_non_read_queries(tmp_path: Path) -> None:
    from premura.mcp_server import query_warehouse

    with pytest.raises(ValueError, match="read-only"):
        query_warehouse(
            "DELETE FROM hp.dim_metric",
            warehouse_path=_initialized_warehouse(tmp_path),
        )


def test_list_metrics_reports_seeded_metrics(tmp_path: Path) -> None:
    from premura.mcp_server import list_metrics

    rows = list_metrics(warehouse_path=_initialized_warehouse(tmp_path), limit=5)

    assert len(rows) == 5
    assert {"metric_id", "display_name", "canonical_unit", "value_kind", "category"} <= set(
        rows[0]
    )


def test_metric_summary_reports_measurement_stats(tmp_path: Path) -> None:
    from premura.mcp_server import metric_summary

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
    assert summary["measurement_count"] == 2
    assert summary["interval_count"] == 0
    assert summary["latest_measurement_at"] == "2026-01-02 10:00:00"
    assert summary["numeric_summary"] == {
        "min": 70.0,
        "max": 71.5,
        "avg": 70.75,
    }


def test_metric_summary_returns_none_for_missing_metric(tmp_path: Path) -> None:
    from premura.mcp_server import metric_summary

    assert metric_summary("missing_metric", warehouse_path=_initialized_warehouse(tmp_path)) is None


def test_build_server_registers_expected_tools() -> None:
    from premura.mcp_entrypoint import build_server

    async def run() -> None:
        server = build_server()
        assert sorted(tool.name for tool in await server.list_tools()) == [
            "list_metrics",
            "metric_summary",
            "query_warehouse",
        ]

    asyncio.run(run())


def test_stdio_mcp_server_exposes_tools(tmp_path: Path) -> None:
    data_dir = _initialized_data_dir(tmp_path)

    async def run() -> None:
        env = dict(os.environ)
        env["HPIPE_DATA_DIR"] = str(data_dir)
        params = StdioServerParameters(
            command="uv",
            args=["run", "premura-mcp"],
            env=env,
            cwd=Path(__file__).resolve().parent.parent,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert sorted(tool.name for tool in tools.tools) == [
                    "list_metrics",
                    "metric_summary",
                    "query_warehouse",
                ]

                metrics = await session.call_tool("list_metrics", {"limit": 2})
                assert metrics.isError is False
                assert metrics.structuredContent is not None
                assert metrics.structuredContent["count"] == 2

                summary = await session.call_tool("metric_summary", {"metric_id": "weight"})
                assert summary.isError is False
                assert summary.structuredContent is not None
                assert summary.structuredContent["summary"]["measurement_count"] == 2

    asyncio.run(run())
