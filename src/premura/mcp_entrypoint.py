"""Thin MCP server entrypoint over Premura's warehouse helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import mcp_server

JsonScalar = str | int | float | bool | None


def build_server(*, warehouse_path: Path | None = None) -> FastMCP:
    """Build Premura's first MCP server surface."""
    server = FastMCP(
        "premura",
        instructions="Read-only access to the local Premura warehouse.",
    )

    @server.tool()
    def query_warehouse(
        sql: str, params: list[JsonScalar] | None = None
    ) -> dict[str, Any]:
        """Run one read-only SQL query against the local Premura warehouse."""
        return mcp_server.query_warehouse(sql, params, warehouse_path=warehouse_path)

    @server.tool()
    def list_metrics(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List canonical metrics with warehouse coverage counts."""
        metrics = mcp_server.list_metrics(
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

    @server.tool()
    def metric_summary(metric_id: str) -> dict[str, Any]:
        """Return metadata and coverage stats for one canonical metric."""
        return {"summary": mcp_server.metric_summary(metric_id, warehouse_path=warehouse_path)}

    return server


def main() -> None:
    build_server().run(transport="stdio")


__all__ = ["build_server", "main"]


if __name__ == "__main__":
    main()
