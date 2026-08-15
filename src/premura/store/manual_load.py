"""Single-row manual measurement load — the store side of the `ingest_row` MCP tool.

A thin builder only: one :class:`~premura.parsers.base.Measurement` +
:class:`~premura.parsers.base.SourceDescriptor` become a single-row
:class:`~premura.parsers.base.IngestBatch` with
``source_kind=MANUAL_LOAD_SOURCE_KIND``, which then goes through
``store.loader.load`` — the exact same boundary every parser uses. No unit
conversion or validation logic lives here; the loader boundary owns both
(unit convert-or-refuse via `units.convert`, source-kind vocabulary rail via
`validate_batch_against_warehouse`).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..parsers.base import IngestBatch, Measurement, SourceDescriptor
from . import loader

if TYPE_CHECKING:
    import duckdb

#: The `dim_source` identity every manual load shares — one operator-facing
#: "source" for all agent-transcribed rows, distinguished per-row by
#: `source_uuid` / `source_ref` rather than by a fabricated per-row source_id.
MANUAL_LOAD_SOURCE_ID = "manual_load:agent"


def load_manual_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    metric_id: str,
    ts_utc: datetime,
    unit: str,
    source_ref: str,
    value_num: float | None = None,
    value_text: str | None = None,
) -> loader.LoadStats:
    """Build a single-row IngestBatch for one manually transcribed observation and load it.

    ``source_ref`` is mandatory plain-text provenance (e.g. "operator
    spreadsheet row 14"); it is never fabricated and rides in the
    measurement's ``raw_payload`` for durable provenance. ``source_uuid`` is
    derived deterministically from the row's content (metric, timestamp,
    value, unit, source_ref) so re-submitting the identical row dedupes
    instead of double-counting, while a genuinely different row gets a
    distinct identity.
    """
    source_uuid = _stable_source_uuid(
        metric_id=metric_id,
        ts_utc=ts_utc,
        unit=unit,
        value_num=value_num,
        value_text=value_text,
        source_ref=source_ref,
    )
    measurement = Measurement(
        ts_utc=ts_utc,
        metric_id=metric_id,
        unit=unit,
        source_id=MANUAL_LOAD_SOURCE_ID,
        source_kind=loader.MANUAL_LOAD_SOURCE_KIND,
        value_num=value_num,
        value_text=value_text,
        source_uuid=source_uuid,
        raw_payload={"source_ref": source_ref},
    )
    batch = IngestBatch(
        source_kind=loader.MANUAL_LOAD_SOURCE_KIND,
        declared_metrics=[metric_id],
        measurements=[measurement],
        source_descriptors={
            MANUAL_LOAD_SOURCE_ID: SourceDescriptor(
                source_id=MANUAL_LOAD_SOURCE_ID,
                source_kind=loader.MANUAL_LOAD_SOURCE_KIND,
            )
        },
    )
    batch.source_path = _synthetic_source_path(source_uuid)
    batch.source_sha256 = source_uuid
    return loader.load(conn, batch)


def _stable_source_uuid(
    *,
    metric_id: str,
    ts_utc: datetime,
    unit: str,
    value_num: float | None,
    value_text: str | None,
    source_ref: str,
) -> str:
    payload = "|".join(
        [
            metric_id,
            ts_utc.isoformat(),
            unit,
            "" if value_num is None else repr(value_num),
            value_text or "",
            source_ref,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _synthetic_source_path(source_uuid: str) -> Path:
    return Path(f"manual_load://{source_uuid}")


__all__ = ["MANUAL_LOAD_SOURCE_ID", "load_manual_row"]
