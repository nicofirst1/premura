"""Shared parser types.

Two seams live here:

* the observation seam — ``Measurement`` / ``Interval`` / ``ClinicalNote``
  carried in an :class:`IngestBatch` and persisted via ``premura.store.loader``;
* the normalized intake seam — ``NutritionIntakeInput`` /
  ``SupplementIntakeInput`` carried in an :class:`IntakeBatch` and persisted via
  ``premura.store.profile_intake.persist_intake_batch``.

Nutrition and supplement intake never become observation rows; the two seams
are intentionally separate so a future parser cannot back-fill intake into the
fact tables just because that path already exists.
"""

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
class ClinicalNote:
    """Narrative commentary or diagnosis text extracted from one report."""

    ts_utc: datetime
    source_id: str
    source_kind: str
    text: str
    language: str | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def dedupe_key(self) -> str:
        payload = f"{self.source_kind}|{self.source_id}|{self.ts_utc.isoformat()}|{self.text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class SkippedRow:
    """One source row that resolved to no loadable measurement or interval."""

    raw_field: str
    reason: str


# --------------------------------------------------------------------------- #
# Normalized intake seam.
#
# Nutrition and supplement intake are NOT observations. They never become
# Measurement / Interval / ClinicalNote rows and never travel inside an
# IngestBatch (see CONTRACT.md, "Two seams"). They are their own normalized
# inputs that a parser emits and the store persists into the dedicated
# hp.nutrition_intake_* / hp.supplement_intake_* tables via
# premura.store.profile_intake.persist_intake_batch.
#
# The types are deliberately source-agnostic: no vendor-specific fields, only
# the shapes the warehouse seam needs. Validation enforces one-home separation
# (a quantity must have a parent, a supplement item must name a product or
# ingredient, a dose must carry an amount) so a future parser cannot emit a
# half-formed intake row that the loader would have to repair.
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class NutritionQuantityInput:
    """One energy or nutrient amount within a nutrition event or item.

    A quantity attaches to either the whole event (``subject="event"``) or a
    single item (``subject="item"``); the store resolves which parent it links
    to. Quantity keys (``energy``, ``protein``, ...) stay distinct from
    body-observation metric_ids — a meal's kcal is intake, a wearable's expended
    kcal is an observation.
    """

    quantity_key: str
    value_num: float
    unit: str | None = None
    # Which parent this amount is attributed to within its item/event.
    subject: str = "item"
    raw_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.quantity_key:
            raise ValueError("NutritionQuantityInput requires quantity_key")
        if self.subject not in ("event", "item"):
            raise ValueError(
                f"NutritionQuantityInput.subject must be 'event' or 'item', got {self.subject!r}"
            )


@dataclass(slots=True)
class NutritionItemInput:
    """One consumed food or drink inside a nutrition event."""

    item_label: str
    brand_label: str | None = None
    serving_text: str | None = None
    quantities: list[NutritionQuantityInput] = field(default_factory=list)
    raw_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.item_label:
            raise ValueError("NutritionItemInput requires item_label")
        for quantity in self.quantities:
            quantity.validate()


@dataclass(slots=True)
class NutritionIntakeInput:
    """One eating or drinking occurrence to persist as nutrition intake.

    This is the nutrition counterpart of an observation row. It lands in
    ``hp.nutrition_intake_event`` (+ items + quantities), never in
    ``hp.fact_measurement`` or note storage. ``event_quantities`` carry
    event-level totals (e.g. whole-meal kcal); per-item quantities live on each
    :class:`NutritionItemInput`.
    """

    source_id: str
    source_kind: str
    start_utc: datetime
    dedupe_key: str
    end_utc: datetime | None = None
    local_tz: str | None = None
    meal_label: str | None = None
    source_uuid: str | None = None
    items: list[NutritionItemInput] = field(default_factory=list)
    event_quantities: list[NutritionQuantityInput] = field(default_factory=list)
    raw_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.source_id:
            raise ValueError("NutritionIntakeInput requires source_id")
        if not self.source_kind:
            raise ValueError("NutritionIntakeInput requires source_kind")
        if not self.dedupe_key:
            raise ValueError("NutritionIntakeInput requires dedupe_key")
        if self.end_utc is not None and self.end_utc < self.start_utc:
            raise ValueError("NutritionIntakeInput end_utc precedes start_utc")
        for item in self.items:
            item.validate()
        for quantity in self.event_quantities:
            if quantity.subject != "event":
                raise ValueError("event_quantities must use subject='event'")
            quantity.validate()


@dataclass(slots=True)
class SupplementDoseInput:
    """One taken dose attached to a supplement item.

    A dose must carry at least one amount representation: a numeric
    ``amount_num`` (with optional ``unit``) or a qualitative ``amount_text``
    (e.g. "one scoop"). Partial knowledge stays representable rather than being
    fabricated.
    """

    ingredient_label: str | None = None
    amount_num: float | None = None
    amount_text: str | None = None
    unit: str | None = None
    raw_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        if self.amount_num is None and not self.amount_text:
            raise ValueError(
                "SupplementDoseInput requires at least one of amount_num or amount_text"
            )


@dataclass(slots=True)
class SupplementItemInput:
    """The product or ingredient taken in one supplement event.

    At least one of ``product_label`` / ``ingredient_label`` must be present so
    an unknown brand-vs-ingredient situation is honestly representable rather
    than forced into an invented name.
    """

    product_label: str | None = None
    ingredient_label: str | None = None
    form_label: str | None = None
    doses: list[SupplementDoseInput] = field(default_factory=list)
    raw_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.product_label and not self.ingredient_label:
            raise ValueError(
                "SupplementItemInput requires at least one of product_label or ingredient_label"
            )
        for dose in self.doses:
            dose.validate()


@dataclass(slots=True)
class SupplementIntakeInput:
    """One supplement-taking occurrence to persist as supplement intake.

    Lands in ``hp.supplement_intake_event`` (+ items + doses). Kept deliberately
    separate from :class:`NutritionIntakeInput` so the two meanings never merge.
    """

    source_id: str
    source_kind: str
    ts_utc: datetime
    dedupe_key: str
    local_tz: str | None = None
    source_uuid: str | None = None
    items: list[SupplementItemInput] = field(default_factory=list)
    raw_payload: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.source_id:
            raise ValueError("SupplementIntakeInput requires source_id")
        if not self.source_kind:
            raise ValueError("SupplementIntakeInput requires source_kind")
        if not self.dedupe_key:
            raise ValueError("SupplementIntakeInput requires dedupe_key")
        for item in self.items:
            item.validate()


@dataclass(slots=True)
class IntakeBatch:
    """The parser-to-store seam for normalized nutrition/supplement intake.

    Distinct from :class:`IngestBatch`: that carries observation rows
    (measurements / intervals / clinical notes) bound to ``dim_metric``; this
    carries intake occurrences bound to the dedicated intake tables. A parser
    that produces both observation and intake data emits one of each rather than
    folding intake into observation rows.
    """

    source_descriptors: dict[str, SourceDescriptor] = field(default_factory=dict)
    nutrition_events: list[NutritionIntakeInput] = field(default_factory=list)
    supplement_events: list[SupplementIntakeInput] = field(default_factory=list)
    # Review metadata, mirroring IngestBatch.unmapped_metrics / skipped_rows: an
    # intake parser declares fields the decision tree produced no home for here.
    # These ride on the batch for human review; they are NEVER loadable rows and
    # persist_intake_batch does not write them (same posture as
    # IngestBatch.unmapped_metrics).
    unmapped_metrics: list[str] = field(default_factory=list)
    skipped_rows: list[SkippedRow] = field(default_factory=list)
    ingest_batch: str | None = None
    notes: str | None = None

    def __len__(self) -> int:
        return len(self.nutrition_events) + len(self.supplement_events)

    def validate(self) -> None:
        for event in self.nutrition_events:
            event.validate()
        for sup_event in self.supplement_events:
            sup_event.validate()

        # Every intake row's source_id must be backed by a descriptor so the
        # store can upsert hp.dim_source without out-of-band parser state.
        row_source_ids = {e.source_id for e in self.nutrition_events} | {
            e.source_id for e in self.supplement_events
        }
        missing = row_source_ids - set(self.source_descriptors)
        if missing:
            raise ValueError(f"IntakeBatch missing source descriptors for: {sorted(missing)}")

        # Dedupe keys are the idempotency contract; they must be unique within
        # the batch, per domain (the UNIQUE constraint enforces it cross-batch).
        for label, keys in (
            ("nutrition", [e.dedupe_key for e in self.nutrition_events]),
            ("supplement", [e.dedupe_key for e in self.supplement_events]),
        ):
            if len(keys) != len(set(keys)):
                raise ValueError(f"IntakeBatch has duplicate {label} dedupe_key values")


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
    clinical_notes: list[ClinicalNote] = field(default_factory=list)
    source_descriptors: dict[str, SourceDescriptor] = field(default_factory=dict)
    unmapped_metrics: list[str] = field(default_factory=list)
    skipped_rows: list[SkippedRow] = field(default_factory=list)
    source_path: Path | None = None
    source_sha256: str | None = None
    notes: str | None = None
    language_detected: str | None = None
    confidence: float = 1.0

    def extend(self, other: IngestBatch) -> None:
        self.measurements.extend(other.measurements)
        self.intervals.extend(other.intervals)
        self.clinical_notes.extend(other.clinical_notes)
        self.source_descriptors.update(other.source_descriptors)
        self.unmapped_metrics.extend(other.unmapped_metrics)
        self.skipped_rows.extend(other.skipped_rows)
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

        row_source_ids = (
            {m.source_id for m in self.measurements}
            | {i.source_id for i in self.intervals}
            | {n.source_id for n in self.clinical_notes}
        )
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


@dataclass(slots=True)
class ParseOutput:
    """The backward-compatible union a parser may return from ``parse()``.

    Today's parsers return a bare :class:`IngestBatch` (observation-only) and
    keep working unchanged — the runtime normalizes that case. A parser that
    needs the intake seam (or both seams from one source artifact) instead
    returns a :class:`ParseOutput` carrying whichever batches it produced.

    This is the *smallest backward-compatible shape*: it adds an optional return
    type rather than swapping the existing one, so no existing parser is touched.
    See ``CONTRACT.md`` ("Parser runtime output: observation, intake, or both").
    """

    observation: IngestBatch | None = None
    intake: IntakeBatch | None = None


# A parser's ``parse()`` may return today's bare ``IngestBatch`` (observation
# only) or a ``ParseOutput`` carrying observation and/or intake batches.
ParserOutput = IngestBatch | ParseOutput


def normalize_parse_output(output: ParserOutput) -> tuple[IngestBatch | None, IntakeBatch | None]:
    """Map any parser output to ``(observation_batch | None, intake_batch | None)``.

    The single runtime dispatch helper. Every call site routes through this so
    none re-implements the union handling (the risk that a call site is left on
    the old path). A bare :class:`IngestBatch` — what every existing parser
    returns — normalizes to observation-only, so their behavior is unchanged.
    """
    if isinstance(output, ParseOutput):
        return output.observation, output.intake
    if isinstance(output, IngestBatch):
        return output, None
    raise TypeError(
        f"parse() must return an IngestBatch or a ParseOutput, got {type(output).__name__}"
    )


class Parser(Protocol):
    """All parsers expose ``parse(path)``.

    Observation-only parsers return a bare :class:`IngestBatch` (unchanged). A
    parser that emits intake — or both observation and intake from one source —
    returns a :class:`ParseOutput`; the runtime normalizes either via
    :func:`normalize_parse_output`.
    """

    source_kind: str

    def declares_metrics(self) -> list[str]: ...

    def parse(self, path: Path) -> ParserOutput: ...


class PluginParser(Parser, Protocol):
    """Structural protocol for federated, community-contributed parsers."""

    language_hint: str | None

    def parse(self, path: Path) -> ParserOutput:
        """Parse ``path`` and return an :class:`IngestBatch` or :class:`ParseOutput`."""
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
