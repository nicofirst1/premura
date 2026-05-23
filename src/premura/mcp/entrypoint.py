"""Thin MCP server entrypoint over Premura's warehouse helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import server as warehouse_server

JsonScalar = str | int | float | bool | None


def build_server(*, warehouse_path: Path | None = None) -> FastMCP:
    """Build Premura's first MCP server surface."""
    mcp = FastMCP(
        "premura",
        instructions="Read-only access to the local Premura warehouse.",
    )

    @mcp.tool()
    def query_warehouse(
        sql: str, params: list[JsonScalar] | None = None
    ) -> dict[str, Any]:
        """Run one read-only SQL query against the local Premura warehouse."""
        return warehouse_server.query_warehouse(sql, params, warehouse_path=warehouse_path)

    @mcp.tool()
    def list_metrics(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List canonical metrics with warehouse coverage counts."""
        metrics = warehouse_server.list_metrics(
            warehouse_path=warehouse_path,
            limit=limit,
            offset=offset,
        )
        return {
            "metrics": metrics,
            "count": len(metrics),
            "limit": limit,
            "offset": offset,
        }

    @mcp.tool()
    def metric_summary(metric_id: str) -> dict[str, Any]:
        """Return metadata and coverage stats for one canonical metric."""
        return {
            "summary": warehouse_server.metric_summary(
                metric_id,
                warehouse_path=warehouse_path,
            )
        }

    return mcp


def main() -> None:
    build_server().run(transport="stdio")


__all__ = ["build_server", "main"]


if __name__ == "__main__":
    main()
