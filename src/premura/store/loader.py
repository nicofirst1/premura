"""Loader: applies one validated ingest batch to the warehouse in one transaction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from ulid import ULID

from .. import units
from ..parsers.base import IngestBatch
from .dedupe import DedupePlan, DedupePlanner
from .duck import upsert_dim_source

if TYPE_CHECKING:
    import duckdb


@dataclass(slots=True)
class UnitRefusal:
    """One measurement row refused at the load boundary: no conversion rule."""

    metric_id: str
    from_unit: str
    to_unit: str
    reason: str


@dataclass(slots=True)
class LoadStats:
    batch_id: str
    rows_inserted: int = 0
    rows_skipped_dup: int = 0
    rows_skipped_priority: int = 0
    rows_skipped_unit: int = 0
    unit_refusals: list[UnitRefusal] = field(default_factory=list)

    @property
    def rows_skipped(self) -> int:
        return self.rows_skipped_dup + self.rows_skipped_priority + self.rows_skipped_unit


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
        plan.measurement_rows, refusals = _enforce_canonical_units(conn, plan.measurement_rows)
        _persist_plan(conn, plan)
        note_count = _persist_clinical_notes(conn, batch, batch_id=batch_id)
        stats.rows_inserted = plan.rows_inserted + note_count
        stats.rows_skipped_dup = plan.rows_skipped_dup
        stats.rows_skipped_priority = plan.rows_skipped_priority
        stats.rows_skipped_unit = len(refusals)
        stats.unit_refusals = refusals
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
        if batch.measurements or batch.intervals:
            raise ValueError("IngestBatch with measurements or intervals requires declared_metrics")
        return

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


def _enforce_canonical_units(
    conn: duckdb.DuckDBPyConnection, rows: pl.DataFrame
) -> tuple[pl.DataFrame, list[UnitRefusal]]:
    """The load boundary's sole unit decision point for measurements.

    Every surviving row's `unit` is rewritten to its metric's
    `dim_metric.canonical_unit` and `value_num` is rescaled via `units.convert`
    to match — never merely relabeled. A row whose observed unit has no
    registered conversion rule for its metric is dropped and reported as a
    :class:`UnitRefusal` rather than passed through or silently relabeled.
    """
    if rows.height == 0:
        return rows, []

    metric_ids = rows["metric_id"].unique().to_list()
    placeholders = ", ".join(["?"] * len(metric_ids))
    canonical_by_metric = dict(
        conn.execute(
            f"SELECT metric_id, canonical_unit FROM hp.dim_metric "
            f"WHERE metric_id IN ({placeholders})",
            metric_ids,
        ).fetchall()
    )

    kept_indices: list[int] = []
    new_value_num: list[float | None] = []
    new_unit: list[str] = []
    refusals: list[UnitRefusal] = []

    for i, row in enumerate(rows.iter_rows(named=True)):
        metric_id = row["metric_id"]
        canonical_unit = canonical_by_metric.get(metric_id)
        if canonical_unit is None:
            # No dim_metric row for this metric_id would already have failed
            # validate_batch_against_warehouse; defensive no-op pass-through.
            kept_indices.append(i)
            new_value_num.append(row["value_num"])
            new_unit.append(row["unit"])
            continue

        observed_unit = units.normalize_unit(row["unit"])
        if observed_unit == canonical_unit:
            kept_indices.append(i)
            new_value_num.append(row["value_num"])
            new_unit.append(canonical_unit)
            continue

        value_num = row["value_num"]
        if value_num is None:
            # Nothing to rescale (e.g. text-valued row); relabeling a value-less
            # row does not violate the "convert, never relabel" guarantee.
            kept_indices.append(i)
            new_value_num.append(None)
            new_unit.append(canonical_unit)
            continue

        converted = units.convert(
            value_num, from_unit=observed_unit, to_unit=canonical_unit, metric_id=metric_id
        )
        if converted is None:
            refusals.append(
                UnitRefusal(
                    metric_id=metric_id,
                    from_unit=observed_unit,
                    to_unit=canonical_unit,
                    reason=f"no conversion rule from {observed_unit!r} to {canonical_unit!r} "
                    f"for metric {metric_id!r}",
                )
            )
            continue

        kept_indices.append(i)
        new_value_num.append(converted)
        new_unit.append(canonical_unit)

    survivors = rows[kept_indices].with_columns(
        pl.Series("value_num", new_value_num, dtype=rows.schema["value_num"]),
        pl.Series("unit", new_unit, dtype=rows.schema["unit"]),
    )
    return survivors, refusals


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
            # `unit` is sourced from the metric registry (dim_metric.canonical_unit),
            # never from a parser-supplied string — the warehouse is the single
            # source of unit truth. A row whose metric is absent
            # from dim_metric would already have been rejected at validate time, so
            # the LEFT JOIN is defensive: it leaves unit NULL rather than dropping
            # the row.
            conn.execute(
                """
                INSERT INTO hp.fact_interval
                    (metric_id, start_utc, end_utc, local_tz, value_num, value_text,
                     unit, source_id, source_uuid, parent_uuid, dedupe_key,
                     ingest_batch, raw_payload)
                SELECT p.metric_id, p.start_utc, p.end_utc, p.local_tz, p.value_num,
                       p.value_text, dm.canonical_unit, p.source_id, p.source_uuid,
                       p.parent_uuid, p.dedupe_key, p.ingest_batch, p.raw_payload
                FROM planned_intervals p
                LEFT JOIN hp.dim_metric dm ON dm.metric_id = p.metric_id
                """
            )
        finally:
            conn.unregister("planned_intervals")


def _persist_clinical_notes(
    conn: duckdb.DuckDBPyConnection,
    batch: IngestBatch,
    *,
    batch_id: str,
) -> int:
    if not batch.clinical_notes:
        return 0

    rows = [
        (
            note.ts_utc,
            note.source_id,
            note.language,
            note.text,
            note.dedupe_key,
            batch_id,
            None if note.raw_payload is None else json.dumps(note.raw_payload),
        )
        for note in batch.clinical_notes
    ]
    conn.executemany(
        """
        INSERT INTO hp.fact_clinical_note (
            ts_utc, source_id, language, text, dedupe_key, ingest_batch, raw_payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (dedupe_key) DO NOTHING
        """,
        rows,
    )
    row = conn.execute(
        "SELECT COUNT(*) FROM hp.fact_clinical_note WHERE ingest_batch = ?",
        [batch_id],
    ).fetchone()
    return int(row[0]) if row else 0


__all__ = [
    "LoadStats",
    "UnitRefusal",
    "already_ingested",
    "finish_ingest_run",
    "load",
    "new_batch_id",
    "start_ingest_run",
    "validate_batch_against_warehouse",
]
