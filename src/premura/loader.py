"""Loader: bulk-writes Measurement / Interval records into the warehouse.

Strategy (PLAN.md "Dedupe — 3 tiers"):
  1. Native unique key — enforced by hp.fact_*.dedupe_key UNIQUE.
     We use INSERT INTO … SELECT … WHERE NOT EXISTS (anti-join) to avoid raising.
  2. Cross-source priority overlap — anti-joined against any existing row with
     higher source priority within ±2s and ±0.01 value.
  3. Same-source upserts — handled by per-parser logic (synthesized stable UUIDs).

All inserts go through a per-call temp table for batch speed (one statement = one
trip across the Python/DuckDB boundary instead of N).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from ulid import ULID

from .dedupe import SOURCE_PRIORITY, TS_TOLERANCE, VALUE_TOLERANCE
from .parsers.base import Interval, Measurement, ParseResult, file_sha256
from .store.duck import upsert_dim_source

if TYPE_CHECKING:
    import duckdb


@dataclass(slots=True)
class LoadStats:
    batch_id: str
    rows_inserted: int = 0
    rows_skipped_dup: int = 0
    rows_skipped_priority: int = 0

    @property
    def rows_skipped(self) -> int:
        return self.rows_skipped_dup + self.rows_skipped_priority


def new_batch_id() -> str:
    return str(ULID())


def already_ingested(conn: duckdb.DuckDBPyConnection, sha256: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM hp.ingest_run WHERE source_sha256 = ? AND finished_at IS NOT NULL LIMIT 1",
        [sha256],
    ).fetchone()
    return row is not None


def start_ingest_run(
    conn: duckdb.DuckDBPyConnection,
    *,
    source_kind: str,
    source_path: Path,
    source_sha256: str,
) -> str:
    batch_id = new_batch_id()
    conn.execute(
        """
        INSERT INTO hp.ingest_run (batch_id, source_kind, source_path, source_sha256)
        VALUES (?, ?, ?, ?)
        """,
        [batch_id, source_kind, str(source_path), source_sha256],
    )
    return batch_id


def finish_ingest_run(
    conn: duckdb.DuckDBPyConnection,
    *,
    batch_id: str,
    stats: LoadStats,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE hp.ingest_run
        SET finished_at = now(),
            rows_inserted = ?,
            rows_skipped_dup = ?,
            notes = ?
        WHERE batch_id = ?
        """,
        [stats.rows_inserted, stats.rows_skipped, notes, batch_id],
    )


def load(
    conn: duckdb.DuckDBPyConnection,
    result: ParseResult,
    *,
    source_kind: str,
    source_dim_seed: dict[str, dict] | None = None,
) -> LoadStats:
    """Persist a ParseResult. Returns insert / skip counts."""
    if result.source_path is None or result.source_sha256 is None:
        raise ValueError("ParseResult requires source_path + source_sha256 before loading")

    batch_id = start_ingest_run(
        conn,
        source_kind=source_kind,
        source_path=result.source_path,
        source_sha256=result.source_sha256,
    )
    stats = LoadStats(batch_id=batch_id)

    # Seed dim_source for everything we're about to write.
    seen_sources: set[str] = set()
    for rec in (*result.measurements, *result.intervals):
        if rec.source_id in seen_sources:
            continue
        seen_sources.add(rec.source_id)
        meta = (source_dim_seed or {}).get(rec.source_id, {})
        upsert_dim_source(conn, source_id=rec.source_id, source_kind=source_kind, **meta)

    # Auto-seed unknown metric_ids (e.g. BMT custom columns) so the FK is satisfied.
    _autoseed_unknown_metrics(conn, result)

    if result.measurements:
        _bulk_insert_measurements(conn, result.measurements, batch_id=batch_id, stats=stats)
    if result.intervals:
        _bulk_insert_intervals(conn, result.intervals, batch_id=batch_id, stats=stats)

    finish_ingest_run(conn, batch_id=batch_id, stats=stats)
    return stats


# ---------- bulk insert helpers ----------


def _bulk_insert_measurements(
    conn: duckdb.DuckDBPyConnection,
    items: list[Measurement],
    *,
    batch_id: str,
    stats: LoadStats,
) -> None:
    df = _measurements_dataframe(items, batch_id=batch_id)
    conn.register("staging_m", df)
    try:
        # Skip rows already present (tier 1) — anti-join on dedupe_key.
        n_dup = conn.execute(
            """
            SELECT COUNT(*) FROM staging_m s
            WHERE EXISTS (SELECT 1 FROM hp.fact_measurement f WHERE f.dedupe_key = s.dedupe_key)
            """,
        ).fetchone()[0]

        # Skip rows beaten by a higher-priority source (tier 2).
        n_priority = _count_priority_dups(
            conn,
            staging="staging_m",
            target="hp.fact_measurement",
            ts_column="ts_utc",
        )

        # Insert what's left.
        higher_kinds = _higher_priority_kinds(items[0].source_kind if items else "")
        priority_clause = _priority_filter_sql("hp.fact_measurement", "ts_utc", higher_kinds)
        sql = f"""
            INSERT INTO hp.fact_measurement
                (ts_utc, local_tz, metric_id, value_num, value_text, unit,
                 source_id, source_uuid, dedupe_key, ingest_batch, raw_payload)
            SELECT s.ts_utc, s.local_tz, s.metric_id, s.value_num, s.value_text, s.unit,
                   s.source_id, s.source_uuid, s.dedupe_key, s.ingest_batch, s.raw_payload
            FROM staging_m s
            WHERE NOT EXISTS (
                SELECT 1 FROM hp.fact_measurement f WHERE f.dedupe_key = s.dedupe_key
            )
              AND {priority_clause}
        """
        before = conn.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
        conn.execute(sql)
        after = conn.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
        stats.rows_inserted += after - before
        stats.rows_skipped_dup += n_dup
        stats.rows_skipped_priority += n_priority
    finally:
        conn.unregister("staging_m")


def _bulk_insert_intervals(
    conn: duckdb.DuckDBPyConnection,
    items: list[Interval],
    *,
    batch_id: str,
    stats: LoadStats,
) -> None:
    df = _intervals_dataframe(items, batch_id=batch_id)
    conn.register("staging_i", df)
    try:
        n_dup = conn.execute(
            """
            SELECT COUNT(*) FROM staging_i s
            WHERE EXISTS (SELECT 1 FROM hp.fact_interval f WHERE f.dedupe_key = s.dedupe_key)
            """
        ).fetchone()[0]

        n_priority = _count_priority_dups(
            conn,
            staging="staging_i",
            target="hp.fact_interval",
            ts_column="start_utc",
            staging_ts_column="start_utc",
        )

        higher_kinds = _higher_priority_kinds(items[0].source_kind if items else "")
        priority_clause = _priority_filter_sql(
            "hp.fact_interval", "start_utc", higher_kinds, staging_ts_column="start_utc"
        )
        sql = f"""
            INSERT INTO hp.fact_interval
                (metric_id, start_utc, end_utc, local_tz, value_num, value_text,
                 source_id, source_uuid, parent_uuid, dedupe_key, ingest_batch, raw_payload)
            SELECT s.metric_id, s.start_utc, s.end_utc, s.local_tz, s.value_num, s.value_text,
                   s.source_id, s.source_uuid, s.parent_uuid, s.dedupe_key, s.ingest_batch,
                   s.raw_payload
            FROM staging_i s
            WHERE NOT EXISTS (
                SELECT 1 FROM hp.fact_interval f WHERE f.dedupe_key = s.dedupe_key
            )
              AND {priority_clause}
        """
        before = conn.execute("SELECT COUNT(*) FROM hp.fact_interval").fetchone()[0]
        conn.execute(sql)
        after = conn.execute("SELECT COUNT(*) FROM hp.fact_interval").fetchone()[0]
        stats.rows_inserted += after - before
        stats.rows_skipped_dup += n_dup
        stats.rows_skipped_priority += n_priority
    finally:
        conn.unregister("staging_i")


def _autoseed_unknown_metrics(conn: duckdb.DuckDBPyConnection, result: ParseResult) -> None:
    """For metric_ids not present in dim_metric (e.g. bmt_custom:*), insert a placeholder row.

    Without this the FK from fact_* to dim_metric would block the bulk insert.
    """
    needed: set[tuple[str, str]] = set()
    for m in result.measurements:
        needed.add((m.metric_id, m.unit))
    for i in result.intervals:
        needed.add((i.metric_id, i.unit or "enum"))
    if not needed:
        return
    metric_ids = [mid for mid, _ in needed]
    rows = conn.execute(
        "SELECT metric_id FROM hp.dim_metric WHERE metric_id IN ("
        + ", ".join(["?"] * len(metric_ids))
        + ")",
        metric_ids,
    ).fetchall()
    have = {r[0] for r in rows}
    missing = [(mid, unit) for mid, unit in needed if mid not in have]
    for mid, unit in missing:
        conn.execute(
            """
            INSERT INTO hp.dim_metric (metric_id, display_name, canonical_unit, value_kind, description)
            VALUES (?, ?, ?, 'instantaneous', 'auto-seeded by ingest')
            """,
            [mid, mid, unit or "unknown"],
        )


def _higher_priority_kinds(source_kind: str) -> list[str]:
    rank = SOURCE_PRIORITY.get(source_kind, 0)
    return [k for k, v in SOURCE_PRIORITY.items() if v > rank]


def _priority_filter_sql(
    target: str,
    target_ts_column: str,
    higher_kinds: list[str],
    *,
    staging_ts_column: str = "ts_utc",
) -> str:
    """SQL fragment selecting staging rows NOT beaten by a higher-priority existing row."""
    if not higher_kinds:
        return "TRUE"
    kinds_csv = ", ".join(f"'{k}'" for k in higher_kinds)
    return f"""
        NOT EXISTS (
            SELECT 1 FROM {target} f
            JOIN hp.dim_source ds ON ds.source_id = f.source_id
            WHERE ds.source_kind IN ({kinds_csv})
              AND f.metric_id = s.metric_id
              AND f.{target_ts_column} BETWEEN s.{staging_ts_column} - INTERVAL '{TS_TOLERANCE.total_seconds()}' SECOND
                                            AND s.{staging_ts_column} + INTERVAL '{TS_TOLERANCE.total_seconds()}' SECOND
              AND (
                    (f.value_num IS NULL AND s.value_num IS NULL)
                 OR (f.value_num BETWEEN s.value_num - {VALUE_TOLERANCE} AND s.value_num + {VALUE_TOLERANCE})
              )
        )
    """


def _count_priority_dups(
    conn: duckdb.DuckDBPyConnection,
    *,
    staging: str,
    target: str,
    ts_column: str,
    staging_ts_column: str | None = None,
) -> int:
    if not staging:
        return 0
    # Use the first row's source_kind for the priority compare; all rows in a batch share kind.
    kinds_row = conn.execute(f"SELECT DISTINCT source_id FROM {staging} LIMIT 1").fetchone()
    if not kinds_row:
        return 0
    # All rows are same source_kind (loader called once per parser-run).
    source_kind_row = conn.execute(
        f"SELECT source_kind FROM hp.dim_source WHERE source_id = ?",
        [kinds_row[0]],
    ).fetchone()
    if not source_kind_row:
        return 0
    higher = _higher_priority_kinds(source_kind_row[0])
    if not higher:
        return 0
    kinds_csv = ", ".join(f"'{k}'" for k in higher)
    stg_ts = staging_ts_column or ts_column
    sql = f"""
        SELECT COUNT(*) FROM {staging} s
        WHERE EXISTS (
            SELECT 1 FROM {target} f
            JOIN hp.dim_source ds ON ds.source_id = f.source_id
            WHERE ds.source_kind IN ({kinds_csv})
              AND f.metric_id = s.metric_id
              AND f.{ts_column} BETWEEN s.{stg_ts} - INTERVAL '{TS_TOLERANCE.total_seconds()}' SECOND
                                     AND s.{stg_ts} + INTERVAL '{TS_TOLERANCE.total_seconds()}' SECOND
              AND (
                    (f.value_num IS NULL AND s.value_num IS NULL)
                 OR (f.value_num BETWEEN s.value_num - {VALUE_TOLERANCE} AND s.value_num + {VALUE_TOLERANCE})
              )
        )
    """
    return conn.execute(sql).fetchone()[0]


# ---------- dataclass → polars DataFrame ----------


def _measurements_dataframe(items: list[Measurement], *, batch_id: str) -> pl.DataFrame:
    df = pl.DataFrame(
        {
            "ts_utc": [m.ts_utc for m in items],
            "local_tz": [m.local_tz for m in items],
            "metric_id": [m.metric_id for m in items],
            "value_num": [m.value_num for m in items],
            "value_text": [m.value_text for m in items],
            "unit": [m.unit for m in items],
            "source_id": [m.source_id for m in items],
            "source_uuid": [m.source_uuid for m in items],
            "dedupe_key": [m.dedupe_key for m in items],
            "ingest_batch": [batch_id] * len(items),
            "raw_payload": [_dumps(m.raw_payload) for m in items],
        },
        schema_overrides={"ts_utc": pl.Datetime("us")},
    )
    return df.unique(subset=["dedupe_key"], keep="first", maintain_order=True)


def _intervals_dataframe(items: list[Interval], *, batch_id: str) -> pl.DataFrame:
    df = pl.DataFrame(
        {
            "metric_id": [i.metric_id for i in items],
            "start_utc": [i.start_utc for i in items],
            "end_utc": [i.end_utc for i in items],
            "local_tz": [i.local_tz for i in items],
            "value_num": [i.value_num for i in items],
            "value_text": [i.value_text for i in items],
            "source_id": [i.source_id for i in items],
            "source_uuid": [i.source_uuid for i in items],
            "parent_uuid": [i.parent_uuid for i in items],
            "dedupe_key": [i.dedupe_key for i in items],
            "ingest_batch": [batch_id] * len(items),
            "raw_payload": [_dumps(i.raw_payload) for i in items],
        },
        schema_overrides={
            "start_utc": pl.Datetime("us"),
            "end_utc": pl.Datetime("us"),
        },
    )
    return df.unique(subset=["dedupe_key"], keep="first", maintain_order=True)


def _dumps(payload: dict | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, default=_json_default)


def _json_default(o: object) -> object:
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(f"Unserializable: {type(o).__name__}")


def attach_source_metadata(result: ParseResult, path: Path) -> ParseResult:
    result.source_path = path
    result.source_sha256 = file_sha256(path)
    return result


__all__ = [
    "LoadStats",
    "SOURCE_PRIORITY",
    "already_ingested",
    "attach_source_metadata",
    "finish_ingest_run",
    "load",
    "new_batch_id",
    "start_ingest_run",
]
