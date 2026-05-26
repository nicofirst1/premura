"""Thin MCP server entrypoint over Premura's warehouse helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
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
        sql: str, params: list[JsonScalar] | None = None, max_rows: int = 200
    ) -> dict[str, Any]:
        """Run one read-only SQL query against the local Premura warehouse."""
        return warehouse_server.query_warehouse(
            sql,
            params,
            warehouse_path=warehouse_path,
            max_rows=max_rows,
        )

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

    # --- Signal-backed tools (WP04) -------------------------------------- #
    # These are the supported path for the six approved Stage 2 answers. Each
    # delegates to the grounded signal engine and returns a structured payload
    # whose ``status`` field distinguishes available / missing_input /
    # stale_input / insufficient_data without collapsing into a generic error.

    @mcp.tool()
    def resting_hr_status() -> dict[str, Any]:
        """Latest resting heart rate with an explicit freshness verdict."""
        return warehouse_server.resting_hr_status(warehouse_path=warehouse_path)

    @mcp.tool()
    def resting_hr_trend(lookback_days: int | None = None) -> dict[str, Any]:
        """Recent resting-heart-rate trend with gap and imputation visibility."""
        return warehouse_server.resting_hr_trend(
            lookback_days=lookback_days, warehouse_path=warehouse_path
        )

    @mcp.tool()
    def steps_trend(lookback_days: int | None = None) -> dict[str, Any]:
        """Recent daily-steps trend; missing days stay gaps and are never imputed."""
        return warehouse_server.steps_trend(
            lookback_days=lookback_days, warehouse_path=warehouse_path
        )

    @mcp.tool()
    def weight_trend(lookback_days: int | None = None) -> dict[str, Any]:
        """Recent body-weight trend with freshness and carried-forward caveats."""
        return warehouse_server.weight_trend(
            lookback_days=lookback_days, warehouse_path=warehouse_path
        )

    @mcp.tool()
    def sleep_deep_pct_baseline(baseline_days: int | None = None) -> dict[str, Any]:
        """Compare the latest deep-sleep percentage to the user's own recent baseline."""
        return warehouse_server.sleep_deep_pct_baseline(
            baseline_days=baseline_days, warehouse_path=warehouse_path
        )

    @mcp.tool()
    def hrv_change_around_date(
        anchor_date: str, window_days: int | None = None
    ) -> dict[str, Any]:
        """Compare overnight HRV before/after the given anchor date (YYYY-MM-DD).

        No significance or causation is claimed; ``anchor_date`` is the
        user-supplied change date the comparison is centered on.
        """
        return warehouse_server.hrv_change_around_date(
            anchor_date,
            window_days=window_days,
            warehouse_path=warehouse_path,
        )

    return mcp


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    build_server(warehouse_path=args.warehouse_path).run(transport="stdio")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="premura-mcp",
        description="Run Premura's read-only MCP server over one DuckDB warehouse.",
    )
    parser.add_argument(
        "--warehouse-path",
        type=Path,
        help=(
            "Explicit path to the DuckDB warehouse file. Defaults to "
            "HPIPE_DATA_DIR/duck/health.duckdb."
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.warehouse_path is not None and not args.warehouse_path.exists():
        parser.error(f"warehouse does not exist: {args.warehouse_path}")
    return args


__all__ = ["build_server", "main"]


if __name__ == "__main__":
    main()
