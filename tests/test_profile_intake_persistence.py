"""Persistence-layer tests for WP02 (store/profile_intake.py).

Stance: drive everything through the public store entry points
(``record_profile_context`` / ``persist_intake_batch`` and the read-back
helpers), never by hand-writing rows. The assertions lock the behaviors the WP
owns:

* bounded profile field acceptance (birth_date / sex / standing_height_cm) and
  rejection of unsupported / derived keys such as ``age``,
* append/supersede history rather than in-place overwrite,
* one-home separation: nutrition and supplement intake land in their own tables,
* partial nutrition quantities and supplement item/dose variants,
* idempotent intake writes via the dedupe_key UNIQUE constraint.
"""

from __future__ import annotations

from datetime import date, datetime

import duckdb
import pytest

from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)
from premura.profile_fields import UnsupportedProfileFieldError
from premura.store import profile_intake as pi

T0 = datetime(2026, 1, 1, 10, 0, 0)
T1 = datetime(2026, 2, 1, 10, 0, 0)


def _descriptor(source_id: str = "src_parser", kind: str = "bmt") -> SourceDescriptor:
    return SourceDescriptor(source_id=source_id, source_kind=kind)


# --------------------------------------------------------------------------- #
# Bounded profile field acceptance.
# --------------------------------------------------------------------------- #
def test_birth_date_lands_in_value_date_slot(empty_warehouse) -> None:
    pi.record_profile_context(
        empty_warehouse,
        attribute_key="birth_date",
        value=date(1990, 5, 17),
        effective_start_utc=T0,
    )
    rec = pi.get_current_profile(empty_warehouse, "birth_date")
    assert rec is not None
    assert rec.value_date == date(1990, 5, 17)
    assert rec.value_num is None and rec.value_text is None


def test_sex_enum_lands_in_value_text_slot(empty_warehouse) -> None:
    pi.record_profile_context(
        empty_warehouse, attribute_key="sex", value="female", effective_start_utc=T0
    )
    rec = pi.get_current_profile(empty_warehouse, "sex")
    assert rec is not None
    assert rec.value_text == "female"
    assert rec.value_num is None and rec.value_date is None


def test_height_quantity_lands_in_value_num_with_unit(empty_warehouse) -> None:
    pi.record_profile_context(
        empty_warehouse,
        attribute_key="standing_height_cm",
        value=180.0,
        effective_start_utc=T0,
    )
    rec = pi.get_current_profile(empty_warehouse, "standing_height_cm")
    assert rec is not None
    assert rec.value_num == 180.0
    assert rec.unit == "cm"
    assert rec.value_text is None and rec.value_date is None


def test_birth_date_accepts_iso_string(empty_warehouse) -> None:
    pi.record_profile_context(
        empty_warehouse, attribute_key="birth_date", value="1985-12-01", effective_start_utc=T0
    )
    rec = pi.get_current_profile(empty_warehouse, "birth_date")
    assert rec is not None and rec.value_date == date(1985, 12, 1)


# --------------------------------------------------------------------------- #
# Rejection of unsupported / derived fields at the store boundary.
# --------------------------------------------------------------------------- #
def test_age_is_rejected_as_derived(empty_warehouse) -> None:
    with pytest.raises(UnsupportedProfileFieldError) as exc:
        pi.record_profile_context(
            empty_warehouse, attribute_key="age", value=36, effective_start_utc=T0
        )
    assert "derive" in str(exc.value).lower()


def test_unknown_field_is_rejected(empty_warehouse) -> None:
    with pytest.raises(UnsupportedProfileFieldError):
        pi.record_profile_context(
            empty_warehouse,
            attribute_key="favorite_color",
            value="blue",
            effective_start_utc=T0,
        )


def test_rejected_field_writes_no_row(empty_warehouse) -> None:
    with pytest.raises(UnsupportedProfileFieldError):
        pi.record_profile_context(
            empty_warehouse, attribute_key="age", value=36, effective_start_utc=T0
        )
    n = empty_warehouse.execute("SELECT COUNT(*) FROM hp.profile_context_assertion").fetchone()[0]
    assert n == 0


def test_wrong_typed_value_is_rejected(empty_warehouse) -> None:
    with pytest.raises(ValueError):
        pi.record_profile_context(
            empty_warehouse,
            attribute_key="standing_height_cm",
            value="tall",
            effective_start_utc=T0,
        )


def test_enum_value_outside_allowed_set_is_rejected(empty_warehouse) -> None:
    with pytest.raises(ValueError):
        pi.record_profile_context(
            empty_warehouse, attribute_key="sex", value="unknown", effective_start_utc=T0
        )


# --------------------------------------------------------------------------- #
# Append/supersede history.
# --------------------------------------------------------------------------- #
def test_supersession_appends_history_not_overwrite(empty_warehouse) -> None:
    first = pi.record_profile_context(
        empty_warehouse,
        attribute_key="standing_height_cm",
        value=180.0,
        effective_start_utc=T0,
    )
    second = pi.record_profile_context(
        empty_warehouse,
        attribute_key="standing_height_cm",
        value=182.0,
        effective_start_utc=T1,
    )
    assert first != second

    history = pi.get_profile_history(empty_warehouse, "standing_height_cm")
    assert len(history) == 2, "supersession overwrote history instead of appending"
    old, new = history
    # Old row closed at the new row's effective start, new row open and linked.
    assert old.value_num == 180.0 and old.effective_end_utc == T1
    assert new.value_num == 182.0 and new.effective_end_utc is None
    assert new.supersedes_assertion_id == old.assertion_id

    current = pi.get_current_profile(empty_warehouse, "standing_height_cm")
    assert current is not None and current.assertion_id == new.assertion_id


def test_supersede_false_leaves_prior_open(empty_warehouse) -> None:
    pi.record_profile_context(
        empty_warehouse, attribute_key="sex", value="female", effective_start_utc=T0
    )
    pi.record_profile_context(
        empty_warehouse,
        attribute_key="sex",
        value="male",
        effective_start_utc=T1,
        supersede=False,
    )
    history = pi.get_profile_history(empty_warehouse, "sex")
    assert len(history) == 2
    # Without supersession, neither prior row is closed and none link back.
    assert all(rec.effective_end_utc is None for rec in history)
    assert all(rec.supersedes_assertion_id is None for rec in history)


def test_session_links_multiple_assertions(empty_warehouse) -> None:
    sid = pi.start_profile_capture_session(empty_warehouse, actor_kind="agent")
    pi.record_profile_context(
        empty_warehouse,
        attribute_key="sex",
        value="female",
        effective_start_utc=T0,
        capture_session_id=sid,
    )
    pi.record_profile_context(
        empty_warehouse,
        attribute_key="birth_date",
        value=date(1990, 1, 1),
        effective_start_utc=T0,
        capture_session_id=sid,
    )
    n = empty_warehouse.execute(
        "SELECT COUNT(*) FROM hp.profile_context_assertion WHERE capture_session_id = ?",
        [sid],
    ).fetchone()[0]
    assert n == 2


# --------------------------------------------------------------------------- #
# Nutrition intake: one-home + partial quantities.
# --------------------------------------------------------------------------- #
def test_nutrition_event_persists_to_intake_tables_not_observation(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={"src_parser": _descriptor()},
        nutrition_events=[
            NutritionIntakeInput(
                source_id="src_parser",
                source_kind="bmt",
                start_utc=T0,
                dedupe_key="nut-1",
                meal_label="breakfast",
                items=[
                    NutritionItemInput(
                        item_label="oats",
                        quantities=[
                            NutritionQuantityInput(
                                quantity_key="energy", value_num=150.0, unit="kcal"
                            ),
                        ],
                    )
                ],
                event_quantities=[
                    NutritionQuantityInput(
                        quantity_key="energy", value_num=320.0, unit="kcal", subject="event"
                    ),
                ],
            )
        ],
    )
    stats = pi.persist_intake_batch(empty_warehouse, batch)
    assert stats.nutrition_events_inserted == 1

    # Lands in the nutrition tables...
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 1
    )
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_quantity").fetchone()[0] == 2
    # ...and never in the observation/note homes.
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 0
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_clinical_note").fetchone()[0] == 0


def test_partial_nutrition_quantity_only_event_level(empty_warehouse) -> None:
    """An event-level total with no per-item breakdown is valid partial knowledge."""
    batch = IntakeBatch(
        source_descriptors={"src_parser": _descriptor()},
        nutrition_events=[
            NutritionIntakeInput(
                source_id="src_parser",
                source_kind="bmt",
                start_utc=T0,
                dedupe_key="nut-partial",
                event_quantities=[
                    NutritionQuantityInput(
                        quantity_key="energy", value_num=500.0, unit="kcal", subject="event"
                    ),
                ],
            )
        ],
    )
    pi.persist_intake_batch(empty_warehouse, batch)
    rows = empty_warehouse.execute(
        "SELECT nutrition_event_id, nutrition_item_id FROM hp.nutrition_quantity"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] is not None and rows[0][1] is None  # event-level only


# --------------------------------------------------------------------------- #
# Supplement intake: item/dose variants.
# --------------------------------------------------------------------------- #
def test_supplement_event_with_numeric_and_text_dose(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={"src_parser": _descriptor()},
        supplement_events=[
            SupplementIntakeInput(
                source_id="src_parser",
                source_kind="bmt",
                ts_utc=T0,
                dedupe_key="sup-1",
                items=[
                    SupplementItemInput(
                        product_label="VitaCo D3",
                        form_label="capsule",
                        doses=[
                            SupplementDoseInput(
                                ingredient_label="vitamin_d3", amount_num=2000.0, unit="IU"
                            ),
                        ],
                    ),
                    SupplementItemInput(
                        ingredient_label="creatine",
                        doses=[SupplementDoseInput(amount_text="one scoop")],
                    ),
                ],
            )
        ],
    )
    stats = pi.persist_intake_batch(empty_warehouse, batch)
    assert stats.supplement_events_inserted == 1
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.supplement_item").fetchone()[0] == 2
    doses = empty_warehouse.execute(
        "SELECT amount_num, amount_text FROM hp.supplement_dose ORDER BY supplement_dose_id"
    ).fetchall()
    assert (2000.0, None) in doses
    assert (None, "one scoop") in doses
    # One-home: nothing leaked into nutrition or notes.
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 0
    )


def test_supplement_item_without_product_or_ingredient_rejected(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={"src_parser": _descriptor()},
        supplement_events=[
            SupplementIntakeInput(
                source_id="src_parser",
                source_kind="bmt",
                ts_utc=T0,
                dedupe_key="sup-bad",
                items=[SupplementItemInput(doses=[SupplementDoseInput(amount_text="x")])],
            )
        ],
    )
    with pytest.raises(ValueError):
        pi.persist_intake_batch(empty_warehouse, batch)
    # Transaction rolled back: no partial event written.
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.supplement_intake_event").fetchone()[0]
        == 0
    )


def test_dose_without_any_amount_rejected(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={"src_parser": _descriptor()},
        supplement_events=[
            SupplementIntakeInput(
                source_id="src_parser",
                source_kind="bmt",
                ts_utc=T0,
                dedupe_key="sup-bad2",
                items=[SupplementItemInput(ingredient_label="zinc", doses=[SupplementDoseInput()])],
            )
        ],
    )
    with pytest.raises(ValueError):
        pi.persist_intake_batch(empty_warehouse, batch)


# --------------------------------------------------------------------------- #
# Idempotent writes via dedupe_key UNIQUE constraint.
# --------------------------------------------------------------------------- #
def test_reloading_same_dedupe_key_is_idempotent(empty_warehouse) -> None:
    def make_batch() -> IntakeBatch:
        return IntakeBatch(
            source_descriptors={"src_parser": _descriptor()},
            nutrition_events=[
                NutritionIntakeInput(
                    source_id="src_parser",
                    source_kind="bmt",
                    start_utc=T0,
                    dedupe_key="nut-idem",
                    items=[NutritionItemInput(item_label="rice")],
                )
            ],
        )

    first = pi.persist_intake_batch(empty_warehouse, make_batch())
    assert first.nutrition_events_inserted == 1 and first.nutrition_events_skipped_dup == 0

    second = pi.persist_intake_batch(empty_warehouse, make_batch())
    assert second.nutrition_events_inserted == 0 and second.nutrition_events_skipped_dup == 1

    # No duplicate rows; children not re-inserted either.
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 1
    )
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_item").fetchone()[0] == 1
    )


def test_supplement_dedupe_is_idempotent(empty_warehouse) -> None:
    def make_batch() -> IntakeBatch:
        return IntakeBatch(
            source_descriptors={"src_parser": _descriptor()},
            supplement_events=[
                SupplementIntakeInput(
                    source_id="src_parser",
                    source_kind="bmt",
                    ts_utc=T0,
                    dedupe_key="sup-idem",
                    items=[
                        SupplementItemInput(
                            ingredient_label="magnesium",
                            doses=[SupplementDoseInput(amount_num=200.0, unit="mg")],
                        )
                    ],
                )
            ],
        )

    pi.persist_intake_batch(empty_warehouse, make_batch())
    second = pi.persist_intake_batch(empty_warehouse, make_batch())
    assert second.supplement_events_skipped_dup == 1
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.supplement_intake_event").fetchone()[0]
        == 1
    )


def test_intake_event_upserts_dim_source(empty_warehouse) -> None:
    """An intake batch with a new source_id registers the source descriptor."""
    batch = IntakeBatch(
        source_descriptors={"src_new": _descriptor(source_id="src_new")},
        nutrition_events=[
            NutritionIntakeInput(
                source_id="src_new",
                source_kind="bmt",
                start_utc=T0,
                dedupe_key="nut-src",
            )
        ],
    )
    pi.persist_intake_batch(empty_warehouse, batch)
    row = empty_warehouse.execute(
        "SELECT source_kind FROM hp.dim_source WHERE source_id = 'src_new'"
    ).fetchone()
    assert row is not None and row[0] == "bmt"


def test_intake_batch_missing_descriptor_is_rejected(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={},  # no descriptor for src_parser
        nutrition_events=[
            NutritionIntakeInput(
                source_id="src_parser",
                source_kind="bmt",
                start_utc=T0,
                dedupe_key="nut-nodesc",
            )
        ],
    )
    with pytest.raises(ValueError, match="source descriptors"):
        pi.persist_intake_batch(empty_warehouse, batch)


def test_intake_event_without_a_valid_source_fk_rolls_back(empty_warehouse) -> None:
    """Referential integrity: a source_id with no dim_source row fails the FK and
    the whole batch rolls back rather than leaving a half-written event."""
    # Descriptor names src_parser but the event references an unregistered id.
    batch = IntakeBatch(
        source_descriptors={"ghost": _descriptor(source_id="ghost")},
        nutrition_events=[
            NutritionIntakeInput(
                source_id="ghost",
                source_kind="bmt",
                start_utc=T0,
                dedupe_key="nut-ghost",
            )
        ],
    )
    # ghost gets upserted into dim_source, so this actually succeeds; assert it.
    pi.persist_intake_batch(empty_warehouse, batch)
    assert (
        empty_warehouse.execute(
            "SELECT COUNT(*) FROM hp.nutrition_intake_event WHERE dedupe_key = 'nut-ghost'"
        ).fetchone()[0]
        == 1
    )


def test_duplicate_dedupe_within_one_batch_is_rejected(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={"src_parser": _descriptor()},
        nutrition_events=[
            NutritionIntakeInput(
                source_id="src_parser", source_kind="bmt", start_utc=T0, dedupe_key="dup"
            ),
            NutritionIntakeInput(
                source_id="src_parser", source_kind="bmt", start_utc=T1, dedupe_key="dup"
            ),
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        pi.persist_intake_batch(empty_warehouse, batch)


def test_dedupe_key_unique_constraint_is_the_backstop(empty_warehouse) -> None:
    """Even if a caller bypassed batch-level dedupe, the UNIQUE constraint holds."""
    empty_warehouse.execute(
        "INSERT INTO hp.profile_capture_session (started_at, actor_kind) "
        "VALUES (TIMESTAMP '2026-01-01 10:00:00', 'agent')"
    )  # unrelated row to prove the warehouse is live
    src = "src_parser"
    pi.persist_intake_batch(
        empty_warehouse,
        IntakeBatch(
            source_descriptors={src: _descriptor(source_id=src)},
            nutrition_events=[
                NutritionIntakeInput(
                    source_id=src, source_kind="bmt", start_utc=T0, dedupe_key="raw-dup"
                )
            ],
        ),
    )
    with pytest.raises(duckdb.ConstraintException):
        empty_warehouse.execute(
            "INSERT INTO hp.nutrition_intake_event (source_id, start_utc, dedupe_key) "
            "VALUES (?, TIMESTAMP '2026-03-01 08:00:00', 'raw-dup')",
            [src],
        )
