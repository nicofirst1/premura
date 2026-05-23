"""Loader: applies one validated ingest batch to the warehouse in one transaction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ulid import ULID

from ..parsers.base import IngestBatch
from .dedupe import DedupePlan, DedupePlanner
from .duck import upsert_dim_source

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


def load(conn: duckdb.DuckDBPyConnection, batch: IngestBatch) -> LoadStats:
    """Persist one ingest batch. Returns insert / skip counts."""
    if batch.source_path is None or batch.source_sha256 is None:
        raise ValueError("IngestBatch requires source_path + source_sha256 before loading")

    conn.execute("BEGIN")
    try:
        validate_batch_against_warehouse(conn, batch)
        batch_id = start_ingest_run(
            conn,
            source_kind=batch.source_kind,
            source_path=batch.source_path,
            source_sha256=batch.source_sha256,
        )
        stats = LoadStats(batch_id=batch_id)
        _upsert_source_descriptors(conn, batch)
        plan = DedupePlanner().plan(conn, batch, batch_id=batch_id)
        _persist_plan(conn, plan)
        _compute_auto_safe_signals(conn, batch)
        stats.rows_inserted = plan.rows_inserted
        stats.rows_skipped_dup = plan.rows_skipped_dup
        stats.rows_skipped_priority = plan.rows_skipped_priority
        finish_ingest_run(conn, batch_id=batch_id, stats=stats, notes=batch.notes)
        conn.execute("COMMIT")
        return stats
    except Exception:
        conn.execute("ROLLBACK")
        raise


def validate_batch_against_warehouse(
    conn: duckdb.DuckDBPyConnection,
    batch: IngestBatch,
) -> None:
    batch.validate()
    metric_ids = batch.declared_metrics
    if not metric_ids:
        raise ValueError("IngestBatch requires declared_metrics")

    placeholders = ", ".join(["?"] * len(metric_ids))
    rows = conn.execute(
        f"SELECT metric_id FROM hp.dim_metric WHERE metric_id IN ({placeholders})",
        metric_ids,
    ).fetchall()
    present = {row[0] for row in rows}
    missing = sorted(set(metric_ids) - present)
    if missing:
        raise ValueError(f"IngestBatch declared metrics missing from dim_metric: {missing}")


def _upsert_source_descriptors(conn: duckdb.DuckDBPyConnection, batch: IngestBatch) -> None:
    for descriptor in batch.source_descriptors.values():
        upsert_dim_source(
            conn,
            source_id=descriptor.source_id,
            source_kind=descriptor.source_kind,
            app_package=descriptor.app_package,
            app_name=descriptor.app_name,
            device_manufacturer=descriptor.device_manufacturer,
            device_model=descriptor.device_model,
        )


def _persist_plan(conn: duckdb.DuckDBPyConnection, plan: DedupePlan) -> None:
    if plan.measurement_rows.height:
        conn.register("planned_measurements", plan.measurement_rows)
        try:
            conn.execute(
                """
                INSERT INTO hp.fact_measurement
                    (ts_utc, local_tz, metric_id, value_num, value_text, unit,
                     source_id, source_uuid, dedupe_key, ingest_batch, raw_payload)
                SELECT ts_utc, local_tz, metric_id, value_num, value_text, unit,
                       source_id, source_uuid, dedupe_key, ingest_batch, raw_payload
                FROM planned_measurements
                """
            )
        finally:
            conn.unregister("planned_measurements")

    if plan.interval_rows.height:
        conn.register("planned_intervals", plan.interval_rows)
        try:
            conn.execute(
                """
                INSERT INTO hp.fact_interval
                    (metric_id, start_utc, end_utc, local_tz, value_num, value_text,
                     source_id, source_uuid, parent_uuid, dedupe_key, ingest_batch, raw_payload)
                SELECT metric_id, start_utc, end_utc, local_tz, value_num, value_text,
                       source_id, source_uuid, parent_uuid, dedupe_key, ingest_batch, raw_payload
                FROM planned_intervals
                """
            )
        finally:
            conn.unregister("planned_intervals")


def _compute_auto_safe_signals(conn: duckdb.DuckDBPyConnection, batch: IngestBatch) -> None:
    from .. import engine

    emitted_metrics = batch.emitted_metrics
    for spec in engine.list_auto_safe():
        if not emitted_metrics.intersection(spec.inputs):
            continue
        if not engine.check_inputs_available(spec.inputs, conn):
            continue
        engine.compute(spec.name, conn)


__all__ = [
    "LoadStats",
    "already_ingested",
    "finish_ingest_run",
    "load",
    "new_batch_id",
    "start_ingest_run",
    "validate_batch_against_warehouse",
]
