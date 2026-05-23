"""Initial Stage 3 analytical helpers over the local warehouse.

This module is the first executable slice of M2. It does not replace the
``premura.mcp`` package contract stub yet; instead it provides small,
read-only helpers that an eventual MCP SDK wrapper can expose as tools.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..config import settings
from ..store import duck

_READ_ONLY_PREFIXES = ("select", "with", "describe", "show")
_DEFAULT_QUERY_MAX_ROWS = 200
_MAX_QUERY_MAX_ROWS = 1000


def query_warehouse(
    sql: str,
    params: Sequence[object] | None = None,
    *,
    warehouse_path: Path | None = None,
    max_rows: int = _DEFAULT_QUERY_MAX_ROWS,
) -> dict[str, Any]:
    """Execute one read-only query against the warehouse and return JSON-safe rows."""
    _ensure_read_only_sql(sql)
    _ensure_bounded_positive_int("max_rows", max_rows, maximum=_MAX_QUERY_MAX_ROWS)
    conn = duck.connect(warehouse_path or settings.warehouse_path, read_only=True)
    try:
        result = conn.execute(sql, params or [])
        columns = [col[0] for col in (result.description or [])]
        fetched_rows = result.fetchmany(max_rows + 1)
        truncated = len(fetched_rows) > max_rows
        rows = [_row_to_dict(columns, row) for row in fetched_rows[:max_rows]]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "max_rows": max_rows,
            "truncated": truncated,
        }
    finally:
        conn.close()


def list_metrics(
    *, warehouse_path: Path | None = None, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List canonical metrics with lightweight warehouse coverage counts."""
    _ensure_non_negative_int("limit", limit)
    _ensure_non_negative_int("offset", offset)
    result = query_warehouse(
        """
        SELECT
            m.metric_id,
            m.display_name,
            m.canonical_unit,
            m.value_kind,
            m.category,
            COALESCE(fm.measurement_count, 0) AS measurement_count,
            COALESCE(fi.interval_count, 0) AS interval_count
        FROM hp.dim_metric AS m
        LEFT JOIN (
            SELECT metric_id, COUNT(*) AS measurement_count
            FROM hp.fact_measurement
            GROUP BY metric_id
        ) AS fm USING (metric_id)
        LEFT JOIN (
            SELECT metric_id, COUNT(*) AS interval_count
            FROM hp.fact_interval
            GROUP BY metric_id
        ) AS fi USING (metric_id)
        ORDER BY m.metric_id
        LIMIT ? OFFSET ?
        """,
        [limit, offset],
        warehouse_path=warehouse_path,
    )
    return result["rows"]


def metric_summary(metric_id: str, *, warehouse_path: Path | None = None) -> dict[str, Any] | None:
    """Return metadata and basic numeric coverage for one canonical metric."""
    if not metric_id.strip():
        raise ValueError("metric_id must not be empty")
    metadata = query_warehouse(
        """
        SELECT metric_id, display_name, canonical_unit, value_kind, description, category,
               validity_window, missing_data_policy, loinc, ieee1752
        FROM hp.dim_metric
        WHERE metric_id = ?
        """,
        [metric_id],
        warehouse_path=warehouse_path,
    )["rows"]
    if not metadata:
        return None

    measurement = query_warehouse(
        """
        SELECT
            COUNT(*) AS measurement_count,
            MAX(ts_utc) AS latest_measurement_at,
            MIN(value_num) FILTER (WHERE value_num IS NOT NULL) AS min_value,
            MAX(value_num) FILTER (WHERE value_num IS NOT NULL) AS max_value,
            AVG(value_num) FILTER (WHERE value_num IS NOT NULL) AS avg_value
        FROM hp.fact_measurement
        WHERE metric_id = ?
        """,
        [metric_id],
        warehouse_path=warehouse_path,
    )["rows"][0]
    interval = query_warehouse(
        """
        SELECT
            COUNT(*) AS interval_count,
            MAX(end_utc) AS latest_interval_end
        FROM hp.fact_interval
        WHERE metric_id = ?
        """,
        [metric_id],
        warehouse_path=warehouse_path,
    )["rows"][0]

    summary = metadata[0] | {
        "measurement_count": measurement["measurement_count"],
        "interval_count": interval["interval_count"],
        "latest_measurement_at": measurement["latest_measurement_at"],
        "latest_interval_end": interval["latest_interval_end"],
    }
    if measurement["min_value"] is not None:
        summary["numeric_summary"] = {
            "min": measurement["min_value"],
            "max": measurement["max_value"],
            "avg": measurement["avg_value"],
        }
    else:
        summary["numeric_summary"] = None
    return summary


def _ensure_read_only_sql(sql: str) -> None:
    normalized = sql.strip()
    if not normalized:
        raise ValueError("query must not be empty")
    body = normalized[:-1].strip() if normalized.endswith(";") else normalized
    if ";" in body:
        raise ValueError("query_warehouse accepts exactly one read-only statement")
    if not body.lower().startswith(_READ_ONLY_PREFIXES):
        raise ValueError("query_warehouse only allows read-only SQL")


def _ensure_non_negative_int(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0")


def _ensure_bounded_positive_int(name: str, value: int, *, maximum: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    if value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")


def _row_to_dict(columns: list[str], row: Sequence[object]) -> dict[str, Any]:
    return {name: _json_safe(value) for name, value in zip(columns, row, strict=False)}


def _json_safe(value: object) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


__all__ = ["list_metrics", "metric_summary", "query_warehouse"]
