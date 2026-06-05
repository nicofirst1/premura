"""Reference intake parser for the synthetic *alien* meals+supplements source.

This is the **layer-1 known-good operator** (FR-004): the honest baseline the
acceptance grader reconciles against. It is a test fixture, NOT a shipped
production parser — the "alien" source is a deliberately unsupported live-trial
target (foreign column names, epoch-microsecond timestamps, non-SI units), so
its reference parser is the committed honest fixture installed into the sandbox.

It conforms to the federated ``PluginParser`` protocol
(``src/premura/parsers/base.py``) and produces a :class:`ParseOutput` carrying an
:class:`IntakeBatch` — so it runs through the REAL intake load seam
(``premura.store.profile_intake.persist_intake_batch``), never the observation
loader. Nutrition and supplement intake are their own seam; nothing here touches
``hp.fact_*``.

What it does, against ``tests/fixtures/intake_scenario/alien_intake.csv``:

* routes ``kind=meal`` rows to ``NutritionIntakeInput`` and ``kind=supp`` rows to
  ``SupplementIntakeInput``;
* decodes ``logged_at_us`` (epoch **microseconds**, UTC) to the event timestamp,
  carrying ``local_tz`` so the warehouse can recover the local day of the
  midnight-crossing row (local-day ≠ UTC-date);
* converts the foreign / non-SI ``qty_uom`` units (``oz`` → grams, ``Cal`` →
  kcal energy, ``IU`` / ``mcg`` doses) to the intake quantity representation;
* declares the free-text ``note`` column — which has **no canonical home** in the
  intake seam — as a gap via ``unmapped_metrics``, **never silently dropped**;
* registers a ``source_descriptor`` for every event ``source_id`` so the batch
  ``validate()``s and persists.

**Standards-first resolution.** Each foreign source field is resolved by the
project rule (``AGENTS.md`` → existing alias via ``suggest_metric`` → LOINC →
IEEE 1752.1 → bare English → ``vendor:*``), not a frozen lookup table. For this
source the structural intake columns (``item``/``qty``/``qty_uom``) map by their
bare-English meaning to the intake quantity representation; ``note`` resolves to
nothing and so becomes a declared gap. ``MAPPED_SOURCE_COLUMNS`` records only the
columns this parser actually consumed (the self-reconcile gate reads it; it never
infers the consumed set from the produced batch — C-005).
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    ParseOutput,
    SkippedRow,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)

SOURCE_KIND = "alien_intake"
SOURCE_ID = "alien_intake:journal"

# The source declares its local wall-clock zone out of band (the grader-only
# manifest mirrors it). Carrying it on each event lets the warehouse recover the
# local day for the midnight-crossing row without re-deriving it from raw µs.
SOURCE_LOCAL_TZ = "America/New_York"

# The source columns this parser actually consumes. Declared explicitly (NOT
# inferred from the produced batch) so the self-reconcile gate has an honest
# witness of "what the parser claims to handle" — `note` is intentionally absent
# because it is a declared gap, not a consumed column (C-005).
MAPPED_SOURCE_COLUMNS: tuple[str, ...] = (
    "logged_at_us",
    "kind",
    "item",
    "qty",
    "qty_uom",
)

# Source columns with no canonical home in the intake seam. Declared as gaps via
# IntakeBatch.unmapped_metrics rather than dropped silently (standards-first: the
# resolution ladder produced no home for free-text commentary).
UNMAPPED_SOURCE_COLUMNS: tuple[str, ...] = ("note",)


def _decode_epoch_us(raw: str) -> datetime:
    """Decode an epoch-microsecond integer to a naive-UTC datetime.

    The warehouse stores UTC; ``local_tz`` on the event carries the wall-clock
    zone so a downstream local-day computation (the midnight-crossing edge) is
    recoverable.
    """
    micros = int(raw)
    aware = datetime.fromtimestamp(micros / 1_000_000, tz=UTC)
    return aware.replace(tzinfo=None)


def _nutrition_quantity(qty: float, uom: str) -> NutritionQuantityInput:
    """Map a foreign meal ``qty``/``qty_uom`` to a nutrition quantity.

    Resolution is by the bare-English meaning of the unit, not a vendor table:
    a food-energy unit (``Cal``/``kcal``) becomes the ``energy`` quantity in
    kcal; a mass unit (``oz``) becomes a ``mass`` quantity converted to grams
    (the intake quantity representation's SI base).
    """
    unit = uom.strip().lower()
    if unit in ("cal", "kcal"):
        return NutritionQuantityInput(quantity_key="energy", value_num=qty, unit="kcal")
    if unit == "oz":
        return NutritionQuantityInput(
            quantity_key="mass", value_num=round(qty * 28.349523125, 4), unit="g"
        )
    if unit in ("g", "gram", "grams"):
        return NutritionQuantityInput(quantity_key="mass", value_num=qty, unit="g")
    # Unknown unit: keep the amount honestly in its source unit rather than
    # fabricating a conversion (partial knowledge stays representable).
    return NutritionQuantityInput(quantity_key="amount", value_num=qty, unit=uom)


def _supplement_dose(qty: float, uom: str) -> SupplementDoseInput:
    """Map a foreign supplement ``qty``/``qty_uom`` to a dose.

    ``IU`` (international units) and ``mcg`` (micrograms) are kept as-is — both
    are legitimate dose units with no lossless single SI target across
    ingredients, so the honest representation is the source unit on the dose.
    """
    unit = uom.strip()
    return SupplementDoseInput(amount_num=qty, unit=unit)


def _dedupe_key(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AlienIntakeReferenceParser:
    """Honest reference parser for the alien meals+supplements source.

    Conforms to the ``PluginParser`` protocol: exposes ``source_kind`` /
    ``language_hint`` / ``declares_metrics`` and a ``parse(path)`` that returns a
    :class:`ParseOutput` carrying an :class:`IntakeBatch`.
    """

    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        # Intake has no dim_metric / metric_id surface (those are the observation
        # seam). The intake parser declares no observation metrics.
        return []

    def parse(self, path: Path) -> ParseOutput:
        batch = IntakeBatch(
            unmapped_metrics=list(UNMAPPED_SOURCE_COLUMNS),
        )
        batch.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID,
            source_kind=SOURCE_KIND,
            app_name="Alien Intake Journal (synthetic)",
        )

        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                kind = (row.get("kind") or "").strip().lower()
                item_label = (row.get("item") or "").strip()
                raw_ts = (row.get("logged_at_us") or "").strip()
                raw_qty = (row.get("qty") or "").strip()
                uom = (row.get("qty_uom") or "").strip()

                if not raw_ts or not item_label:
                    batch.skipped_rows.append(
                        SkippedRow(
                            raw_field=f"row[{line_no}]",
                            reason="missing logged_at_us or item",
                        )
                    )
                    continue

                ts = _decode_epoch_us(raw_ts)
                try:
                    qty = float(raw_qty)
                except ValueError:
                    batch.skipped_rows.append(
                        SkippedRow(
                            raw_field=f"row[{line_no}].qty",
                            reason=f"non-numeric qty {raw_qty!r}",
                        )
                    )
                    continue

                if kind == "meal":
                    quantity = _nutrition_quantity(qty, uom)
                    batch.nutrition_events.append(
                        NutritionIntakeInput(
                            source_id=SOURCE_ID,
                            source_kind=SOURCE_KIND,
                            start_utc=ts,
                            local_tz=SOURCE_LOCAL_TZ,
                            dedupe_key=_dedupe_key(SOURCE_KIND, "meal", raw_ts, item_label),
                            items=[
                                NutritionItemInput(
                                    item_label=item_label,
                                    quantities=[quantity],
                                )
                            ],
                        )
                    )
                elif kind == "supp":
                    dose = _supplement_dose(qty, uom)
                    batch.supplement_events.append(
                        SupplementIntakeInput(
                            source_id=SOURCE_ID,
                            source_kind=SOURCE_KIND,
                            ts_utc=ts,
                            local_tz=SOURCE_LOCAL_TZ,
                            dedupe_key=_dedupe_key(SOURCE_KIND, "supp", raw_ts, item_label),
                            items=[
                                SupplementItemInput(
                                    product_label=item_label,
                                    doses=[dose],
                                )
                            ],
                        )
                    )
                else:
                    batch.skipped_rows.append(
                        SkippedRow(
                            raw_field=f"row[{line_no}].kind",
                            reason=f"unknown kind {kind!r}",
                        )
                    )

        batch.validate()
        return ParseOutput(intake=batch)


__all__ = [
    "AlienIntakeReferenceParser",
    "MAPPED_SOURCE_COLUMNS",
    "SOURCE_ID",
    "SOURCE_KIND",
    "UNMAPPED_SOURCE_COLUMNS",
]
