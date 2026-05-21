"""Cross-source deduplication (tier 2 of the 3-tier scheme in PLAN.md).

  1. Native-key UNIQUE on dedupe_key — enforced by schema (no code here).
  2. Cross-source overlap by (metric_id, ts±2s, value±0.01) with source priority — THIS module.
  3. Same-source recomputed-summary upserts — per-parser logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

# Highest = wins. PLAN.md §"Cross-source priority".
SOURCE_PRIORITY: dict[str, int] = {
    "garmin_gdpr": 100,
    "health_connect": 80,   # default if writer unknown
    "sleep_as_android": 60,
    "bmt": 40,
}

TS_TOLERANCE = timedelta(seconds=2)
VALUE_TOLERANCE = 0.01


def find_higher_priority_match(
    conn: duckdb.DuckDBPyConnection,
    *,
    metric_id: str,
    ts_utc: datetime,
    value_num: float | None,
    source_kind: str,
    table: str,
    ts_column: str = "ts_utc",
) -> str | None:
    """Return the dedupe_key of an existing higher-priority row that matches.

    None if no such row exists (i.e. we should insert).
    """
    my_rank = SOURCE_PRIORITY.get(source_kind, 0)
    higher = [k for k, v in SOURCE_PRIORITY.items() if v > my_rank]
    if not higher:
        return None

    placeholders = ", ".join(["?"] * len(higher))
    value_clause = "t.value_num IS NULL" if value_num is None else "t.value_num BETWEEN ? AND ?"
    sql = f"""
        SELECT t.dedupe_key
        FROM {table} t
        JOIN hp.dim_source s ON s.source_id = t.source_id
        WHERE t.metric_id = ?
          AND s.source_kind IN ({placeholders})
          AND t.{ts_column} BETWEEN ? AND ?
          AND ({value_clause})
        LIMIT 1
    """
    params: list[object] = [metric_id, *higher, ts_utc - TS_TOLERANCE, ts_utc + TS_TOLERANCE]
    if value_num is not None:
        params.extend([value_num - VALUE_TOLERANCE, value_num + VALUE_TOLERANCE])
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


__all__ = ["SOURCE_PRIORITY", "TS_TOLERANCE", "VALUE_TOLERANCE", "find_higher_priority_match"]
