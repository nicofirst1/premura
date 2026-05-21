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


# ---------------------------------------------------------------------------
# Federated parser contract (additive — does not affect v1 parsers).
#
# These symbols define the Phase 2 plugin parser surface described by
# ``src/premura/parsers/CONTRACT.md``. They are intentionally additive: the
# existing ``Parser`` Protocol and ``ParseResult`` dataclass above remain the
# canonical v1 contract and MUST NOT be migrated as part of this mission.
# ---------------------------------------------------------------------------


@dataclass
class PluginParseResult(ParseResult):
    """Federated-parser return type with mapping-quality metadata.

    Extends :class:`ParseResult` with three additive fields that future
    community-contributed parsers use to surface mapping gaps for human
    review. See ``src/premura/parsers/CONTRACT.md`` for the full contract.

    The planning contract document specifies ``frozen=True``; Python's
    dataclass machinery forbids a frozen subclass of the non-frozen
    :class:`ParseResult`, and ``T008`` of this WP requires that
    ``ParseResult`` itself remain unchanged. The Phase 1 ship therefore
    keeps the dataclass mutable to honour the stronger "do not touch
    ParseResult" rule; a future mission may revisit the frozen requirement
    if ``ParseResult`` itself is migrated to ``frozen=True``.
    """

    language_detected: str | None = None
    """ISO 639-1 (or similar) code reported by ``_lang.detect_language`` on a
    representative sample of the source file, or ``None`` when the parser did
    not run detection. Local-only — no external API calls."""

    unmapped_metrics: list[str] = field(default_factory=list)
    """Raw vendor field names the parser deliberately skipped because the
    decision tree in ``CONTRACT.md`` produced no canonical ``metric_id``. The
    PR reviewer decides what to do with them."""

    confidence: float = 1.0
    """Parser's self-rating in ``[0.0, 1.0]`` for the batch as a whole. Used
    later by Stage 2/3 to discount low-confidence sources when surfacing
    signals. Defaults to ``1.0`` for parity with ``ParseResult``."""


class PluginParser(Parser, Protocol):
    """Structural protocol for federated, community-contributed parsers.

    A ``PluginParser`` is the v2 extensibility surface: any object satisfying
    this Protocol can be discovered and invoked by the federated ingest
    pipeline. The structural-subtype relationship with :class:`Parser` is
    intentional — existing v1 parsers remain valid against the original
    ``Parser`` Protocol without migration, while new plugins layer the
    plugin-specific fields and methods on top.

    Implementers MUST follow the decision tree in
    ``src/premura/parsers/CONTRACT.md`` when resolving vendor fields to
    canonical ``metric_id`` values, and MUST NOT emit any ``derived:*``
    ``metric_id`` (those are reserved for the Stage 2 engine).
    """

    language_hint: str | None
    """Known source language as an ISO 639-1 code, or ``None`` when the
    plugin defers detection to ``_lang.detect_language``."""

    def declares_metrics(self) -> list[str]:
        """Return every canonical ``metric_id`` ``parse()`` may emit.

        Reviewers cross-check the returned list against the ``dim_metric.yaml``
        rows the plugin's PR adds; the runtime may also use it for sanity
        checks in a future implementation mission.
        """
        ...

    def parse(self, path: Path) -> PluginParseResult:
        """Parse ``path`` and return a :class:`PluginParseResult`.

        Overrides the ``Parser.parse`` return type with the richer
        plugin-flavored result. Implementations must populate
        ``unmapped_metrics`` with any vendor fields the decision tree could
        not resolve, rather than fabricating ``metric_id`` values.
        """
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
