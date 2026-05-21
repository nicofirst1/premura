"""Dedupe planner for applying one validated ingest batch at the warehouse seam."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

import polars as pl

from .parsers.base import IngestBatch

if TYPE_CHECKING:
    import duckdb


# Highest = wins. docs/SPEC.md §5 cross-source priority.
SOURCE_PRIORITY: dict[str, int] = {
    "garmin_gdpr": 100,
    "health_connect": 80,
    "sleep_as_android": 60,
    "bmt": 40,
}

TS_TOLERANCE = timedelta(seconds=2)
VALUE_TOLERANCE = 0.01


@dataclass(slots=True)
class DedupePlan:
    measurement_rows: pl.DataFrame = field(default_factory=pl.DataFrame)
    interval_rows: pl.DataFrame = field(default_factory=pl.DataFrame)
    skip_counts: dict[str, int] = field(default_factory=dict)

    @property
    def rows_inserted(self) -> int:
        return self.measurement_rows.height + self.interval_rows.height

    @property
    def rows_skipped_dup(self) -> int:
        return self.skip_counts.get("native_duplicate", 0)

    @property
    def rows_skipped_priority(self) -> int:
        return self.skip_counts.get("higher_priority_match", 0)


@dataclass(slots=True)
class _NormalizedRow:
    kind: Literal["measurement", "interval"]
    metric_id: str
    ts_utc: datetime
    source_id: str
    source_kind: str
    source_uuid: str | None
    dedupe_key: str
    local_tz: str | None
    value_num: float | None
    value_text: str | None
    raw_payload: dict | None
    unit: str | None = None
    end_utc: datetime | None = None
    parent_uuid: str | None = None


class DedupePlanner:
    """Owns dedupe policy and planning for both fact shapes."""

    def plan(
        self,
        conn: duckdb.DuckDBPyConnection,
        batch: IngestBatch,
        *,
        batch_id: str,
    ) -> DedupePlan:
        normalized = _normalize_batch(batch)
        measurement_rows = _measurement_frame(normalized, batch_id=batch_id)
        interval_rows = _interval_frame(normalized, batch_id=batch_id)

        measurement_plan, measurement_counts = _plan_frame(
            conn,
            frame=measurement_rows,
            staging="staging_measurements",
            target="hp.fact_measurement",
            ts_column="ts_utc",
        )
        interval_plan, interval_counts = _plan_frame(
            conn,
            frame=interval_rows,
            staging="staging_intervals",
            target="hp.fact_interval",
            ts_column="start_utc",
        )

        return DedupePlan(
            measurement_rows=measurement_plan,
            interval_rows=interval_plan,
            skip_counts={
                "native_duplicate": measurement_counts["native_duplicate"]
                + interval_counts["native_duplicate"],
                "higher_priority_match": measurement_counts["higher_priority_match"]
                + interval_counts["higher_priority_match"],
            },
        )


def _normalize_batch(batch: IngestBatch) -> list[_NormalizedRow]:
    rows: list[_NormalizedRow] = []
    for measurement in batch.measurements:
        rows.append(
            _NormalizedRow(
                kind="measurement",
                metric_id=measurement.metric_id,
                ts_utc=measurement.ts_utc,
                source_id=measurement.source_id,
                source_kind=measurement.source_kind,
                source_uuid=measurement.source_uuid,
                dedupe_key=measurement.dedupe_key,
                local_tz=measurement.local_tz,
                value_num=measurement.value_num,
                value_text=measurement.value_text,
                raw_payload=measurement.raw_payload,
                unit=measurement.unit,
            )
        )
    for interval in batch.intervals:
        rows.append(
            _NormalizedRow(
                kind="interval",
                metric_id=interval.metric_id,
                ts_utc=interval.start_utc,
                source_id=interval.source_id,
                source_kind=interval.source_kind,
                source_uuid=interval.source_uuid,
                dedupe_key=interval.dedupe_key,
                local_tz=interval.local_tz,
                value_num=interval.value_num,
                value_text=interval.value_text,
                raw_payload=interval.raw_payload,
                unit=interval.unit,
                end_utc=interval.end_utc,
                parent_uuid=interval.parent_uuid,
            )
        )
    return rows


def _measurement_frame(rows: list[_NormalizedRow], *, batch_id: str) -> pl.DataFrame:
    items = [row for row in rows if row.kind == "measurement"]
    if not items:
        return pl.DataFrame(
            schema={
                "ts_utc": pl.Datetime("us"),
                "local_tz": pl.Utf8,
                "metric_id": pl.Utf8,
                "value_num": pl.Float64,
                "value_text": pl.Utf8,
                "unit": pl.Utf8,
                "source_id": pl.Utf8,
                "source_uuid": pl.Utf8,
                "source_kind": pl.Utf8,
                "dedupe_key": pl.Utf8,
                "ingest_batch": pl.Utf8,
                "raw_payload": pl.Utf8,
            }
        )
    return pl.DataFrame(
        {
            "ts_utc": [row.ts_utc for row in items],
            "local_tz": [row.local_tz for row in items],
            "metric_id": [row.metric_id for row in items],
            "value_num": [row.value_num for row in items],
            "value_text": [row.value_text for row in items],
            "unit": [row.unit for row in items],
            "source_id": [row.source_id for row in items],
            "source_uuid": [row.source_uuid for row in items],
            "source_kind": [row.source_kind for row in items],
            "dedupe_key": [row.dedupe_key for row in items],
            "ingest_batch": [batch_id] * len(items),
            "raw_payload": [_dumps(row.raw_payload) for row in items],
        },
        schema_overrides={"ts_utc": pl.Datetime("us")},
    ).unique(subset=["dedupe_key"], keep="first", maintain_order=True)


def _interval_frame(rows: list[_NormalizedRow], *, batch_id: str) -> pl.DataFrame:
    items = [row for row in rows if row.kind == "interval"]
    if not items:
        return pl.DataFrame(
            schema={
                "metric_id": pl.Utf8,
                "start_utc": pl.Datetime("us"),
                "end_utc": pl.Datetime("us"),
                "local_tz": pl.Utf8,
                "value_num": pl.Float64,
                "value_text": pl.Utf8,
                "source_id": pl.Utf8,
                "source_uuid": pl.Utf8,
                "source_kind": pl.Utf8,
                "parent_uuid": pl.Utf8,
                "dedupe_key": pl.Utf8,
                "ingest_batch": pl.Utf8,
                "raw_payload": pl.Utf8,
            }
        )
    return pl.DataFrame(
        {
            "metric_id": [row.metric_id for row in items],
            "start_utc": [row.ts_utc for row in items],
            "end_utc": [row.end_utc for row in items],
            "local_tz": [row.local_tz for row in items],
            "value_num": [row.value_num for row in items],
            "value_text": [row.value_text for row in items],
            "source_id": [row.source_id for row in items],
            "source_uuid": [row.source_uuid for row in items],
            "source_kind": [row.source_kind for row in items],
            "parent_uuid": [row.parent_uuid for row in items],
            "dedupe_key": [row.dedupe_key for row in items],
            "ingest_batch": [batch_id] * len(items),
            "raw_payload": [_dumps(row.raw_payload) for row in items],
        },
        schema_overrides={
            "start_utc": pl.Datetime("us"),
            "end_utc": pl.Datetime("us"),
        },
    ).unique(subset=["dedupe_key"], keep="first", maintain_order=True)


def _plan_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    frame: pl.DataFrame,
    staging: str,
    target: str,
    ts_column: str,
) -> tuple[pl.DataFrame, dict[str, int]]:
    if frame.height == 0:
        return frame, {"native_duplicate": 0, "higher_priority_match": 0}

    conn.register(staging, frame)
    try:
        native_duplicate = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM {staging} s
            WHERE EXISTS (SELECT 1 FROM {target} f WHERE f.dedupe_key = s.dedupe_key)
            """
        ).fetchone()[0]

        higher_priority_match = _count_priority_dups(
            conn,
            staging=staging,
            target=target,
            ts_column=ts_column,
        )

        higher_kinds = _higher_priority_kinds(_source_kind_from_staging(conn, staging))
        priority_clause = _priority_filter_sql(target, ts_column, higher_kinds)
        reader = conn.execute(
            f"""
            SELECT s.*
            FROM {staging} s
            WHERE NOT EXISTS (
                SELECT 1 FROM {target} f WHERE f.dedupe_key = s.dedupe_key
            )
              AND {priority_clause}
            """
        ).arrow()
        table = reader.read_all()
        survivors = frame.clear() if table.num_rows == 0 else pl.from_arrow(table)
        return survivors, {
            "native_duplicate": native_duplicate,
            "higher_priority_match": higher_priority_match,
        }
    finally:
        conn.unregister(staging)


def _source_kind_from_staging(conn: duckdb.DuckDBPyConnection, staging: str) -> str:
    row = conn.execute(f"SELECT source_kind FROM {staging} LIMIT 1").fetchone()
    return row[0] if row else ""


def _higher_priority_kinds(source_kind: str) -> list[str]:
    rank = SOURCE_PRIORITY.get(source_kind, 0)
    return [kind for kind, priority in SOURCE_PRIORITY.items() if priority > rank]


def _priority_filter_sql(target: str, target_ts_column: str, higher_kinds: list[str]) -> str:
    if not higher_kinds:
        return "TRUE"
    kinds_csv = ", ".join(f"'{kind}'" for kind in higher_kinds)
    tolerance_seconds = TS_TOLERANCE.total_seconds()
    value_tolerance = VALUE_TOLERANCE
    return f"""
        NOT EXISTS (
            SELECT 1 FROM {target} f
            JOIN hp.dim_source ds ON ds.source_id = f.source_id
            WHERE ds.source_kind IN ({kinds_csv})
              AND f.metric_id = s.metric_id
              AND f.{target_ts_column} BETWEEN
                    s.{target_ts_column} - INTERVAL '{tolerance_seconds}' SECOND
                AND s.{target_ts_column} + INTERVAL '{tolerance_seconds}' SECOND
              AND (
                    (f.value_num IS NULL AND s.value_num IS NULL)
                 OR (
                        f.value_num BETWEEN s.value_num - {value_tolerance}
                        AND s.value_num + {value_tolerance}
                    )
              )
        )
    """


def _count_priority_dups(
    conn: duckdb.DuckDBPyConnection,
    *,
    staging: str,
    target: str,
    ts_column: str,
) -> int:
    higher = _higher_priority_kinds(_source_kind_from_staging(conn, staging))
    if not higher:
        return 0
    kinds_csv = ", ".join(f"'{kind}'" for kind in higher)
    tolerance_seconds = TS_TOLERANCE.total_seconds()
    value_tolerance = VALUE_TOLERANCE
    sql = f"""
        SELECT COUNT(*) FROM {staging} s
        WHERE EXISTS (
            SELECT 1 FROM {target} f
            JOIN hp.dim_source ds ON ds.source_id = f.source_id
            WHERE ds.source_kind IN ({kinds_csv})
              AND f.metric_id = s.metric_id
              AND f.{ts_column} BETWEEN
                    s.{ts_column} - INTERVAL '{tolerance_seconds}' SECOND
                AND s.{ts_column} + INTERVAL '{tolerance_seconds}' SECOND
              AND (
                    (f.value_num IS NULL AND s.value_num IS NULL)
                 OR (
                        f.value_num BETWEEN s.value_num - {value_tolerance}
                        AND s.value_num + {value_tolerance}
                    )
              )
        )
    """
    return conn.execute(sql).fetchone()[0]


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


__all__ = [
    "DedupePlan",
    "DedupePlanner",
    "SOURCE_PRIORITY",
    "TS_TOLERANCE",
    "VALUE_TOLERANCE",
]
