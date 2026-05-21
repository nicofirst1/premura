"""Shared parser types: Measurement, Interval, SourceDescriptor, IngestBatch."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class Measurement:
    """A point-in-time observation. Lands in hp.fact_measurement."""

    ts_utc: datetime
    metric_id: str
    unit: str
    source_id: str
    source_kind: str
    value_num: float | None = None
    value_text: str | None = None
    local_tz: str | None = None
    source_uuid: str | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def dedupe_key(self) -> str:
        return f"{self.source_kind}:{self.source_uuid}"


@dataclass(slots=True)
class Interval:
    """A bounded observation (sleep stage, exercise session, daily step total)."""

    start_utc: datetime
    end_utc: datetime
    metric_id: str
    source_id: str
    source_kind: str
    unit: str | None = None
    value_num: float | None = None
    value_text: str | None = None
    local_tz: str | None = None
    source_uuid: str | None = None
    parent_uuid: str | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def dedupe_key(self) -> str:
        return f"{self.source_kind}:{self.source_uuid}"


@dataclass(slots=True)
class SourceDescriptor:
    """Warehouse-facing provenance for one ``source_id`` in an ingest batch."""

    source_id: str
    source_kind: str
    app_package: str | None = None
    app_name: str | None = None
    device_manufacturer: str | None = None
    device_model: str | None = None


@dataclass(slots=True)
class IngestBatch:
    """The parser-to-loader seam for one source artifact.

    The batch contains only loadable rows plus the provenance and declarations
    needed to validate them at the warehouse seam. Review metadata such as
    ``unmapped_metrics`` stays on the batch, but never becomes a loadable row.
    """

    source_kind: str
    declared_metrics: list[str]
    measurements: list[Measurement] = field(default_factory=list)
    intervals: list[Interval] = field(default_factory=list)
    source_descriptors: dict[str, SourceDescriptor] = field(default_factory=dict)
    unmapped_metrics: list[str] = field(default_factory=list)
    source_path: Path | None = None
    source_sha256: str | None = None
    notes: str | None = None
    language_detected: str | None = None
    confidence: float = 1.0

    def extend(self, other: IngestBatch) -> None:
        self.measurements.extend(other.measurements)
        self.intervals.extend(other.intervals)
        self.source_descriptors.update(other.source_descriptors)
        self.unmapped_metrics.extend(other.unmapped_metrics)
        if other.notes:
            self.notes = f"{self.notes}; {other.notes}" if self.notes else other.notes
        if other.language_detected and self.language_detected is None:
            self.language_detected = other.language_detected

    def __len__(self) -> int:
        return len(self.measurements) + len(self.intervals)

    @property
    def emitted_metrics(self) -> set[str]:
        return {m.metric_id for m in self.measurements} | {i.metric_id for i in self.intervals}

    def attach_source_artifact(self, path: Path) -> IngestBatch:
        self.source_path = path
        self.source_sha256 = file_sha256(path)
        return self

    def validate(self) -> None:
        if not self.source_kind:
            raise ValueError("IngestBatch requires source_kind")
        if not self.declared_metrics:
            raise ValueError("IngestBatch requires declared_metrics")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("IngestBatch confidence must be within [0.0, 1.0]")

        declared = set(self.declared_metrics)
        emitted = self.emitted_metrics
        undeclared = emitted - declared
        if undeclared:
            raise ValueError(f"IngestBatch emitted undeclared metrics: {sorted(undeclared)}")

        derived_metrics = {metric for metric in emitted if metric.startswith("derived:")}
        if derived_metrics:
            raise ValueError(f"Parsers must not emit derived metrics: {sorted(derived_metrics)}")

        row_source_ids = {m.source_id for m in self.measurements} | {
            i.source_id for i in self.intervals
        }
        missing_descriptors = row_source_ids - set(self.source_descriptors)
        if missing_descriptors:
            raise ValueError(
                f"IngestBatch missing source descriptors for: {sorted(missing_descriptors)}"
            )

        mismatched_kinds = [
            source_id
            for source_id, descriptor in self.source_descriptors.items()
            if descriptor.source_kind != self.source_kind
        ]
        if mismatched_kinds:
            raise ValueError(
                f"IngestBatch source descriptors must match source_kind={self.source_kind}: "
                f"{sorted(mismatched_kinds)}"
            )


class Parser(Protocol):
    """All parsers expose ``parse(path) -> IngestBatch``."""

    source_kind: str

    def declares_metrics(self) -> list[str]: ...

    def parse(self, path: Path) -> IngestBatch: ...


class PluginParser(Parser, Protocol):
    """Structural protocol for federated, community-contributed parsers."""

    language_hint: str | None

    def parse(self, path: Path) -> IngestBatch:
        """Parse ``path`` and return an :class:`IngestBatch`."""
        ...


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    """Stream-hash a file. Used for ingest_run idempotency."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()
