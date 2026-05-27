"""Thin MCP server entrypoint over Premura's warehouse helpers.

Two entrypoints are provided:

* **Default surface** (``premura-mcp``, :func:`build_server`) — the agent-safe
  surface.  Exposes catalog, summary, and all six approved Stage 2 signal tools.
  ``query_warehouse`` is intentionally absent; agents should use the
  signal-backed tools and the catalog helpers instead.

* **Operator surface** (``premura-mcp-operator``, :func:`build_operator_server``)
  — lower-guarantee expert mode intended for operator/developer use only,
  **not** for autonomous agent consumption.  Adds :func:`query_warehouse` on top
  of the full default tool set.  No Stage 2 validity guarantees apply to results
  returned by ``query_warehouse``.

The explicit-approval rule is enforced two ways, not by prose alone: (1) surface
separation — ``query_warehouse`` is simply absent from the default
``premura-mcp`` surface, so an agent connected there cannot reach it; and (2) an
explicit launch acknowledgment — the ``premura-mcp-operator`` console entry
(:func:`main_operator`) refuses to start unless the launcher passes ``--ack`` or
sets ``PREMURA_OPERATOR_ACK``.  The lower-guarantee disclosure to the end user
remains a client/agent-layer responsibility the server cannot enforce.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import server as warehouse_server

JsonScalar = str | int | float | bool | None

#: Environment variable an operator may set (to a truthy value) to acknowledge
#: lower-guarantee operator mode instead of passing ``--ack`` on the CLI.
_OPERATOR_ACK_ENV = "PREMURA_OPERATOR_ACK"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _register_default_tools(mcp: FastMCP, *, warehouse_path: Path | None) -> None:
    """Register the full agent-safe default tool set on *mcp*.

    This is the shared core.  It does NOT include ``query_warehouse`` — that
    raw SQL escape hatch lives exclusively on the operator surface.
    """

    @mcp.tool()
    def list_metrics(
        metric_ids: list[str] | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List canonical metrics as validity-gated catalog entries.

        With no arguments, enumerates registered metrics (paged by
        ``limit`` / ``offset``).  Pass ``metric_ids`` to fetch catalog entries
        for specific metrics; an unknown id returns an explicit ``unavailable``
        entry rather than being omitted.  Each entry reports a validity status
        and declared policy — never raw fact-table row counts.
        """
        metrics = warehouse_server.list_metrics(
            metric_ids=metric_ids,
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
        """Return a validity/imputation envelope for one canonical metric.

        Reports validity status, latest value, declared policy, and recent-window
        coverage (sample size / imputed proportion / gap count).  An unknown
        metric returns an explicit ``unavailable`` summary, never raw extrema.
        """
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


def build_server(*, warehouse_path: Path | None = None) -> FastMCP:
    """Build the default agent-safe MCP server surface.

    Exposes catalog, summary, and the six approved Stage 2 signal tools.
    ``query_warehouse`` is intentionally excluded — use :func:`build_operator_server`
    to obtain a surface that includes the raw SQL escape hatch.
    """
    mcp = FastMCP(
        "premura",
        instructions="Read-only access to the local Premura warehouse.",
    )
    _register_default_tools(mcp, warehouse_path=warehouse_path)
    return mcp


def build_operator_server(*, warehouse_path: Path | None = None) -> FastMCP:
    """Build the operator MCP server surface — lower-guarantee expert mode.

    Registers the full default tool set PLUS ``query_warehouse``, the raw SQL
    escape hatch.  This surface is intended for operator/developer use only and
    MUST NOT be used by an autonomous agent without explicit user approval.

    No Stage 2 validity or freshness guarantees apply to results returned by
    ``query_warehouse``; callers own all result interpretation.  The signal-backed
    and catalog tools on this surface retain their normal Stage 2 guarantees.
    """
    mcp = FastMCP(
        "premura-operator",
        instructions=(
            "OPERATOR MODE — lower-guarantee expert surface. "
            "Includes query_warehouse (raw SQL escape hatch). "
            "No Stage 2 validity guarantees apply to query_warehouse results. "
            "This surface must only be used after explicit user approval; "
            "it is not safe for autonomous agent consumption."
        ),
    )
    _register_default_tools(mcp, warehouse_path=warehouse_path)

    @mcp.tool()
    def query_warehouse(
        sql: str, params: list[JsonScalar] | None = None, max_rows: int = 200
    ) -> dict[str, Any]:
        """Run one read-only SQL query against the local Premura warehouse.

        OPERATOR-ONLY ESCAPE HATCH.  This tool runs arbitrary read-only SQL and
        returns raw rows without any Stage 2 validity, freshness, or imputation
        guarantees.  Results must be interpreted by the caller without assuming
        coverage or correctness.  Requires explicit user approval before use;
        autonomous agents must not invoke this tool unsupervised.
        """
        return warehouse_server.query_warehouse(
            sql,
            params,
            warehouse_path=warehouse_path,
            max_rows=max_rows,
        )

    return mcp


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv, prog="premura-mcp", operator_mode=False)
    build_server(warehouse_path=args.warehouse_path).run(transport="stdio")


def main_operator(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv, prog="premura-mcp-operator", operator_mode=True)
    if not _operator_ack_granted(args):
        raise SystemExit(
            "Refusing to start premura-mcp-operator without explicit operator "
            "acknowledgment.\n"
            "This surface registers query_warehouse — arbitrary read-only SQL with "
            "NO Stage 2 validity, freshness, or imputation guarantees. It is not "
            "safe for autonomous agent use without explicit user approval.\n"
            f"To proceed, re-run with --ack, or set {_OPERATOR_ACK_ENV}=1."
        )
    build_operator_server(warehouse_path=args.warehouse_path).run(transport="stdio")


def _operator_ack_granted(args: argparse.Namespace) -> bool:
    """True iff the operator explicitly acknowledged lower-guarantee mode.

    The acknowledgment is the system-enforced realization of the operator
    contract's ``explicit_user_approval_required_for_agent_use`` rule: the
    ``premura-mcp-operator`` console entry will not expose ``query_warehouse``
    unless the launcher opts in via ``--ack`` or the ``PREMURA_OPERATOR_ACK``
    environment variable.  The in-process :func:`build_operator_server` builder
    stays ungated so tests and embedders can construct the surface directly.
    """
    if getattr(args, "ack", False):
        return True
    return (os.environ.get(_OPERATOR_ACK_ENV) or "").strip().lower() in _TRUTHY


def _parse_args(
    argv: Sequence[str] | None = None,
    *,
    prog: str,
    operator_mode: bool,
) -> argparse.Namespace:
    description = (
        "Run Premura's operator MCP server over one DuckDB warehouse. "
        "Includes query_warehouse (raw SQL escape hatch). "
        "Lower-guarantee expert mode — requires explicit user approval."
        if operator_mode
        else "Run Premura's read-only MCP server over one DuckDB warehouse."
    )
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "--warehouse-path",
        type=Path,
        help=(
            "Explicit path to the DuckDB warehouse file. Defaults to "
            "HPIPE_DATA_DIR/duck/health.duckdb."
        ),
    )
    if operator_mode:
        parser.add_argument(
            "--ack",
            action="store_true",
            help=(
                "Acknowledge lower-guarantee operator mode. Required to launch "
                "(exposing query_warehouse, the raw read-only SQL escape hatch with "
                "no Stage 2 validity guarantees) unless PREMURA_OPERATOR_ACK is set "
                "to a truthy value."
            ),
        )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.warehouse_path is not None and not args.warehouse_path.exists():
        parser.error(f"warehouse does not exist: {args.warehouse_path}")
    return args


__all__ = ["build_operator_server", "build_server", "main", "main_operator"]


if __name__ == "__main__":
    main()
