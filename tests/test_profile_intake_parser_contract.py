"""Parser-seam tests for WP02 (parsers/base.py intake types + CONTRACT.md).

These lock the parser-facing contract a future nutrition/supplement parser will
implement against:

* the normalized intake types are real, validated shapes (not vague
  placeholders) and are distinct from the observation types,
* validation keeps one-home separation intact (a supplement item must name a
  product or ingredient; a dose must carry an amount; a quantity must have a
  parent subject),
* ``IntakeBatch`` is a separate seam from ``IngestBatch`` — intake never travels
  as observation rows,
* the shipped CONTRACT.md tells contributors which seam to use.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from premura.parsers import base
from premura.parsers.base import (
    IngestBatch,
    IntakeBatch,
    Interval,
    Measurement,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)

T0 = datetime(2026, 1, 1, 10, 0, 0)
CONTRACT_MD = Path(base.__file__).resolve().parent / "CONTRACT.md"


# --------------------------------------------------------------------------- #
# The intake types are distinct from the observation types.
# --------------------------------------------------------------------------- #
def test_intake_types_are_not_observation_types() -> None:
    for intake_type in (
        NutritionIntakeInput,
        NutritionItemInput,
        NutritionQuantityInput,
        SupplementIntakeInput,
        SupplementItemInput,
        SupplementDoseInput,
    ):
        assert not issubclass(intake_type, (Measurement, Interval))


def test_intake_batch_is_separate_from_ingest_batch() -> None:
    assert IntakeBatch is not IngestBatch
    assert not issubclass(IntakeBatch, IngestBatch)
    # IntakeBatch carries no observation-row fields.
    intake_fields = set(IntakeBatch.__dataclass_fields__)
    assert "measurements" not in intake_fields
    assert "intervals" not in intake_fields
    assert "clinical_notes" not in intake_fields
    # ...and IngestBatch carries no intake-row fields.
    ingest_fields = set(IngestBatch.__dataclass_fields__)
    assert "nutrition_events" not in ingest_fields
    assert "supplement_events" not in ingest_fields


# --------------------------------------------------------------------------- #
# Validation: the types describe a real seam, not a placeholder.
# --------------------------------------------------------------------------- #
def test_valid_nutrition_input_passes_validation() -> None:
    event = NutritionIntakeInput(
        source_id="s",
        source_kind="vendor_x",
        start_utc=T0,
        dedupe_key="k",
        items=[
            NutritionItemInput(
                item_label="apple",
                quantities=[NutritionQuantityInput(quantity_key="energy", value_num=95.0,
                                                    unit="kcal")],
            )
        ],
    )
    event.validate()  # must not raise


def test_nutrition_event_requires_dedupe_key() -> None:
    event = NutritionIntakeInput(source_id="s", source_kind="v", start_utc=T0, dedupe_key="")
    with pytest.raises(ValueError, match="dedupe_key"):
        event.validate()


def test_nutrition_event_rejects_end_before_start() -> None:
    event = NutritionIntakeInput(
        source_id="s", source_kind="v", start_utc=T0, dedupe_key="k",
        end_utc=datetime(2025, 1, 1),
    )
    with pytest.raises(ValueError, match="end_utc"):
        event.validate()


def test_quantity_subject_must_be_event_or_item() -> None:
    with pytest.raises(ValueError, match="subject"):
        NutritionQuantityInput(quantity_key="energy", value_num=1.0, subject="bogus").validate()


def test_event_level_quantity_must_declare_event_subject() -> None:
    event = NutritionIntakeInput(
        source_id="s", source_kind="v", start_utc=T0, dedupe_key="k",
        event_quantities=[NutritionQuantityInput(quantity_key="energy", value_num=1.0,
                                                  subject="item")],
    )
    with pytest.raises(ValueError, match="event"):
        event.validate()


def test_supplement_item_requires_product_or_ingredient() -> None:
    item = SupplementItemInput(doses=[SupplementDoseInput(amount_num=1.0)])
    with pytest.raises(ValueError, match="product_label or ingredient_label"):
        item.validate()


def test_supplement_dose_requires_an_amount() -> None:
    with pytest.raises(ValueError, match="amount_num or amount_text"):
        SupplementDoseInput().validate()


def test_supplement_dose_text_only_is_valid() -> None:
    SupplementDoseInput(amount_text="one scoop").validate()  # must not raise


def test_supplement_input_requires_provenance() -> None:
    with pytest.raises(ValueError):
        SupplementIntakeInput(source_id="", source_kind="v", ts_utc=T0,
                              dedupe_key="k").validate()


# --------------------------------------------------------------------------- #
# IntakeBatch-level validation (the seam the store consumes).
# --------------------------------------------------------------------------- #
def test_intake_batch_requires_source_descriptor_for_every_row() -> None:
    batch = IntakeBatch(
        source_descriptors={},
        nutrition_events=[
            NutritionIntakeInput(source_id="s", source_kind="v", start_utc=T0, dedupe_key="k")
        ],
    )
    with pytest.raises(ValueError, match="source descriptors"):
        batch.validate()


def test_intake_batch_rejects_duplicate_dedupe_keys() -> None:
    batch = IntakeBatch(
        source_descriptors={"s": SourceDescriptor(source_id="s", source_kind="v")},
        nutrition_events=[
            NutritionIntakeInput(source_id="s", source_kind="v", start_utc=T0, dedupe_key="dup"),
            NutritionIntakeInput(source_id="s", source_kind="v", start_utc=T0, dedupe_key="dup"),
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        batch.validate()


def test_intake_batch_propagates_child_validation() -> None:
    batch = IntakeBatch(
        source_descriptors={"s": SourceDescriptor(source_id="s", source_kind="v")},
        supplement_events=[
            SupplementIntakeInput(
                source_id="s", source_kind="v", ts_utc=T0, dedupe_key="k",
                items=[SupplementItemInput(product_label="p", doses=[SupplementDoseInput()])],
            )
        ],
    )
    with pytest.raises(ValueError, match="amount"):
        batch.validate()


def test_valid_mixed_intake_batch_passes() -> None:
    batch = IntakeBatch(
        source_descriptors={"s": SourceDescriptor(source_id="s", source_kind="v")},
        nutrition_events=[
            NutritionIntakeInput(source_id="s", source_kind="v", start_utc=T0, dedupe_key="n1")
        ],
        supplement_events=[
            SupplementIntakeInput(
                source_id="s", source_kind="v", ts_utc=T0, dedupe_key="s1",
                items=[
                    SupplementItemInput(
                        ingredient_label="zinc",
                        doses=[SupplementDoseInput(amount_num=15.0, unit="mg")],
                    )
                ],
            )
        ],
    )
    batch.validate()  # must not raise
    assert len(batch) == 2


# --------------------------------------------------------------------------- #
# Shipped CONTRACT.md documents both seams.
# --------------------------------------------------------------------------- #
def test_contract_doc_exists() -> None:
    assert CONTRACT_MD.is_file()


def test_contract_doc_describes_both_seams() -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8")
    # Both batch types are named.
    assert "IngestBatch" in text
    assert "IntakeBatch" in text
    # The store persistence path for intake is named so contributors find it.
    assert "persist_intake_batch" in text
    # The one-home rule is stated: intake does not become observation/note rows.
    lowered = text.lower()
    assert "not observations" in lowered or "are not observations" in lowered


def test_contract_doc_directs_profile_capture_to_the_bounded_path() -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8")
    assert "record_profile_context" in text
    assert "profile_fields" in text
