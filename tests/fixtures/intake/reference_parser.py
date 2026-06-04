"""Minimal reference intake parser (WP02 / FR-008).

Proof that the build path holds end-to-end: ``parse -> IntakeBatch ->
persist_intake_batch``. It reads the two synthetic fixtures in this package and
emits a single :class:`~premura.parsers.base.IntakeBatch` via the WP01 protocol
(observation-free intake output). It is **not** a production vendor parser
(C-005): it lives under ``tests/fixtures/`` precisely so it cannot be mistaken
for one, and it parses only the made-up shapes bundled here (C-001).

Gap posture (CONTRACT.md decision tree): every source column that has no home
in the normalized intake seam is declared on ``IntakeBatch.unmapped_metrics``,
never silently dropped. Quantity keys such as ``energy`` / ``protein`` are
intrinsic to the intake seam (not observation ``metric_id`` values), so they do
not travel the ``suggest_metric`` ladder; the *extra* source columns do, and
when the ladder produces no canonical home they are surfaced as gaps.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    ParseOutput,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)
from premura.parsers.lookup import suggest_metric

SOURCE_KIND = "reference_intake"

# Directory holding the bundled synthetic fixtures.
FIXTURE_DIR = Path(__file__).parent
NUTRITION_FIXTURE = FIXTURE_DIR / "nutrition_log.json"
SUPPLEMENT_FIXTURE = FIXTURE_DIR / "supplement_log.json"

# Quantity keys this reference parser maps directly onto the intake seam. These
# are intake amounts (a meal's *consumed* energy), not body observations, so
# they are intentionally outside the observation metric_id ontology.
_NUTRITION_QUANTITY_KEYS: dict[str, tuple[str, str]] = {
    # source field -> (quantity_key, unit)
    "energy_kcal": ("energy", "kcal"),
    "protein_g": ("protein", "g"),
}

# Structural fields the parser consumes by position/meaning rather than mapping
# to a quantity or canonical metric. They are not gaps — they have a home in the
# event/item shape itself.
_NUTRITION_STRUCTURAL = {
    "entry_id",
    "logged_at_utc",
    "tz",
    "meal",
    "totals",
    "foods",
    "name",
    "brand",
    "serving",
}
_SUPPLEMENT_STRUCTURAL = {
    "entry_id",
    "taken_at_utc",
    "tz",
    "product",
    "ingredient",
    "form",
    "dose_amount",
    "dose_unit",
    "dose_note",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe_key(source_kind: str, entry_id: str) -> str:
    payload = f"{source_kind}|{entry_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _declare_gap(unmapped: set[str], source: str, field_name: str) -> None:
    """Run a source column through the decision tree; declare it if homeless.

    Step 1 of CONTRACT.md's ladder is ``suggest_metric``. For these synthetic
    annotation columns it returns ``None`` (no existing alias) and the field is
    genuinely source-specific metadata with no place in the intake shape, so it
    is declared as a gap (``vendor:<source>:<field>`` label) rather than dropped.
    """
    if suggest_metric(field_name) is not None:  # pragma: no cover - defensive
        return
    unmapped.add(f"vendor:{source}:{field_name}")


class ReferenceIntakeParser:
    """Parses both bundled synthetic fixtures into one ``IntakeBatch``."""

    source_kind = SOURCE_KIND
    language_hint: str | None = "en"

    def declares_metrics(self) -> list[str]:
        # Intake-only: emits no observation metric_ids.
        return []

    def parse(self, path: Path | None = None) -> ParseOutput:  # noqa: ARG002
        """Return a ``ParseOutput`` carrying an intake-only ``IntakeBatch``.

        ``path`` is accepted for protocol shape but ignored: this reference
        parser reads its two bundled fixtures, not an arbitrary artifact.
        """
        unmapped: set[str] = set()
        batch = IntakeBatch(ingest_batch="reference-intake-fixture")

        self._parse_nutrition(batch, unmapped)
        self._parse_supplements(batch, unmapped)

        batch.unmapped_metrics = sorted(unmapped)
        return ParseOutput(intake=batch)

    # ----- nutrition ------------------------------------------------------- #
    def _parse_nutrition(self, batch: IntakeBatch, unmapped: set[str]) -> None:
        doc = _read_json(NUTRITION_FIXTURE)
        source = doc["source"]
        source_id = f"{SOURCE_KIND}:{source['app_package']}"
        batch.source_descriptors[source_id] = SourceDescriptor(
            source_id=source_id,
            source_kind=SOURCE_KIND,
            app_package=source["app_package"],
            app_name=source["app_name"],
        )

        for entry in doc["entries"]:
            self._scan_gaps(entry, _NUTRITION_STRUCTURAL, source, unmapped)

            event_quantities = [
                NutritionQuantityInput(
                    quantity_key=key,
                    value_num=float(entry["totals"][field_name]),
                    unit=unit,
                    subject="event",
                )
                for field_name, (key, unit) in _NUTRITION_QUANTITY_KEYS.items()
                if field_name in entry.get("totals", {})
            ]

            items: list[NutritionItemInput] = []
            for food in entry.get("foods", []):
                self._scan_gaps(food, _NUTRITION_STRUCTURAL, source, unmapped)
                item_quantities = [
                    NutritionQuantityInput(
                        quantity_key=key,
                        value_num=float(food[field_name]),
                        unit=unit,
                        subject="item",
                    )
                    for field_name, (key, unit) in _NUTRITION_QUANTITY_KEYS.items()
                    if field_name in food
                ]
                items.append(
                    NutritionItemInput(
                        item_label=food["name"],
                        brand_label=food.get("brand"),
                        serving_text=food.get("serving"),
                        quantities=item_quantities,
                    )
                )

            batch.nutrition_events.append(
                NutritionIntakeInput(
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    start_utc=_parse_utc(entry["logged_at_utc"]),
                    dedupe_key=_dedupe_key(SOURCE_KIND, entry["entry_id"]),
                    local_tz=entry.get("tz"),
                    meal_label=entry.get("meal"),
                    source_uuid=entry["entry_id"],
                    items=items,
                    event_quantities=event_quantities,
                )
            )

    # ----- supplements ----------------------------------------------------- #
    def _parse_supplements(self, batch: IntakeBatch, unmapped: set[str]) -> None:
        doc = _read_json(SUPPLEMENT_FIXTURE)
        source = doc["source"]
        source_id = f"{SOURCE_KIND}:{source['app_package']}"
        batch.source_descriptors[source_id] = SourceDescriptor(
            source_id=source_id,
            source_kind=SOURCE_KIND,
            app_package=source["app_package"],
            app_name=source["app_name"],
        )

        for entry in doc["entries"]:
            self._scan_gaps(entry, _SUPPLEMENT_STRUCTURAL, source, unmapped)

            amount_num = entry.get("dose_amount")
            dose = SupplementDoseInput(
                ingredient_label=entry.get("ingredient"),
                amount_num=None if amount_num is None else float(amount_num),
                amount_text=entry.get("dose_note"),
                unit=entry.get("dose_unit"),
            )
            item = SupplementItemInput(
                product_label=entry.get("product"),
                ingredient_label=entry.get("ingredient"),
                form_label=entry.get("form"),
                doses=[dose],
            )
            batch.supplement_events.append(
                SupplementIntakeInput(
                    source_id=source_id,
                    source_kind=SOURCE_KIND,
                    ts_utc=_parse_utc(entry["taken_at_utc"]),
                    dedupe_key=_dedupe_key(SOURCE_KIND, entry["entry_id"]),
                    local_tz=entry.get("tz"),
                    source_uuid=entry["entry_id"],
                    items=[item],
                )
            )

    @staticmethod
    def _scan_gaps(
        record: dict[str, Any],
        structural: set[str],
        source: dict[str, Any],
        unmapped: set[str],
    ) -> None:
        """Declare any column that is neither structural nor a known quantity."""
        for field_name in record:
            if field_name in structural or field_name in _NUTRITION_QUANTITY_KEYS:
                continue
            _declare_gap(unmapped, source["app_name"], field_name)


def _parse_utc(value: str) -> Any:
    from datetime import datetime

    # Fixtures use a trailing 'Z'; normalize to an aware UTC datetime, then drop
    # tzinfo to a naive UTC datetime to match the warehouse's UTC convention.
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=None)
