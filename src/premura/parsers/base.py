"""Shared parser types: Measurement, Interval, ParseResult, Parser protocol."""

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
    """A bounded observation (sleep stage, exercise session, daily step total).

    `unit` is in-memory only — fact_interval does not store a unit column; the metric
    determines the unit. Kept here so parsers can use a uniform constructor signature.
    """

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
class ParseResult:
    """What a parser hands back to the loader."""

    measurements: list[Measurement] = field(default_factory=list)
    intervals: list[Interval] = field(default_factory=list)
    source_path: Path | None = None
    source_sha256: str | None = None
    notes: str | None = None

    def extend(self, other: ParseResult) -> None:
        self.measurements.extend(other.measurements)
        self.intervals.extend(other.intervals)

    def __len__(self) -> int:
        return len(self.measurements) + len(self.intervals)


class Parser(Protocol):
    """All parsers expose .parse(path) -> ParseResult."""

    source_kind: str

    def parse(self, path: Path) -> ParseResult: ...


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
