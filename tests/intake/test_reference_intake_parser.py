"""End-to-end test for the WP02 reference intake parser (FR-008).

Stance: black-box, warehouse-asserting. We drive the reference parser through
the *real* WP01 protocol — ``parse() -> normalize_parse_output ->
persist_intake_batch`` — and assert on persisted rows, never on parser
internals. The fixtures bundled under ``tests/fixtures/intake/`` carry the
parser-side edge cases the DoD enumerates:

* event-level AND item-level nutrition quantities (persist distinctly);
* a nutrition event whose ``local_tz`` puts it on a different local calendar day
  than its UTC date;
* a text-only supplement dose AND a numeric supplement dose;
* an unmapped source field per fixture, surfaced as a gap (never dropped).

Re-running the persist is idempotent (second pass inserts nothing).
"""

from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from premura.parsers.base import IntakeBatch, normalize_parse_output
from premura.store.profile_intake import persist_intake_batch
from tests import FIXTURES_DIR

# The reference parser lives under tests/fixtures/intake/ (C-005: proof anchor,
# not a shipped parser). Import it via the fixtures package.
sys.path.insert(0, str(FIXTURES_DIR))
from intake.reference_parser import (  # type: ignore[import-not-found]  # noqa: E402, I001
    ReferenceIntakeParser,
)


def _parse_intake() -> IntakeBatch:
    observation, intake = normalize_parse_output(ReferenceIntakeParser().parse())
    # Intake-only reference parser: no observation batch, exactly one intake batch.
    assert observation is None
    assert isinstance(intake, IntakeBatch)
    return intake


# --------------------------------------------------------------------------- #
# The batch is well-formed before it ever touches the store.
# --------------------------------------------------------------------------- #
def test_reference_parser_emits_valid_intake_batch() -> None:
    batch = _parse_intake()
    batch.validate()  # raises if the WP01 contract is violated
    assert len(batch.nutrition_events) == 2
    assert len(batch.supplement_events) == 2


def test_unmapped_source_fields_surfaced_as_gaps() -> None:
    """Each fixture's annotation column is declared, never silently dropped (D7)."""
    batch = _parse_intake()
    # mood_tag (nutrition) and reminder_channel (supplement) have no intake home.
    assert any(g.endswith(":mood_tag") for g in batch.unmapped_metrics)
    assert any(g.endswith(":reminder_channel") for g in batch.unmapped_metrics)
    # The gap surface is review metadata, not loadable rows — batch still valid.
    batch.validate()


# --------------------------------------------------------------------------- #
# End-to-end persistence into the real warehouse.
# --------------------------------------------------------------------------- #
def test_reference_intake_lands_in_warehouse(empty_warehouse) -> None:
    batch = _parse_intake()
    stats = persist_intake_batch(empty_warehouse, batch)

    assert stats.nutrition_events_inserted == 2
    assert stats.supplement_events_inserted == 2

    # Nutrition events + items landed.
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 2
    )
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_item").fetchone()[0] == 3
    )
    # Supplement events + items landed.
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.supplement_intake_event").fetchone()[0]
        == 2
    )
    # Intake never coerced into the observation home (two-seam / one-home rule).
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 0


def test_event_and_item_quantities_persist_distinctly(empty_warehouse) -> None:
    """Event-level totals and item-level amounts are stored on different parents,
    so a meal's whole-event kcal is never double-counted against its items (D7)."""
    persist_intake_batch(empty_warehouse, _parse_intake())

    # Event-level quantities hang off nutrition_event_id (item id NULL).
    event_qty = empty_warehouse.execute(
        """
        SELECT COUNT(*) FROM hp.nutrition_quantity
        WHERE nutrition_event_id IS NOT NULL AND nutrition_item_id IS NULL
        """
    ).fetchone()[0]
    # Item-level quantities hang off nutrition_item_id (event id NULL).
    item_qty = empty_warehouse.execute(
        """
        SELECT COUNT(*) FROM hp.nutrition_quantity
        WHERE nutrition_item_id IS NOT NULL AND nutrition_event_id IS NULL
        """
    ).fetchone()[0]

    # Breakfast event totals (energy + protein) + snack event total (energy) = 3.
    assert event_qty == 3
    # oats(energy+protein) + blueberries(energy+protein) + chocolate(energy) = 5.
    assert item_qty == 5
    # No quantity is ever attributed to both a meal and an item at once.
    both = empty_warehouse.execute(
        """
        SELECT COUNT(*) FROM hp.nutrition_quantity
        WHERE nutrition_event_id IS NOT NULL AND nutrition_item_id IS NOT NULL
        """
    ).fetchone()[0]
    assert both == 0


def test_text_only_and_numeric_supplement_doses_persist(empty_warehouse) -> None:
    """A descriptive 'one heaping scoop' dose persists alongside a numeric IU dose
    without either being fabricated into the other's slot (D7)."""
    persist_intake_batch(empty_warehouse, _parse_intake())

    text_only = empty_warehouse.execute(
        "SELECT amount_text FROM hp.supplement_dose WHERE amount_num IS NULL"
    ).fetchall()
    assert text_only == [("one heaping scoop",)]

    numeric = empty_warehouse.execute(
        "SELECT amount_num, unit FROM hp.supplement_dose WHERE amount_text IS NULL"
    ).fetchall()
    assert numeric == [(2000.0, "IU")]


def test_local_tz_event_diverges_from_utc_day(empty_warehouse) -> None:
    """The late-night Auckland snack lands on a different LOCAL calendar day than
    its UTC date — the divergence WP03/WP04 depend on (D7)."""
    persist_intake_batch(empty_warehouse, _parse_intake())

    row = empty_warehouse.execute(
        """
        SELECT start_utc, local_tz FROM hp.nutrition_intake_event
        WHERE local_tz = 'Pacific/Auckland'
        """
    ).fetchone()
    assert row is not None
    start_utc, local_tz = row
    assert isinstance(start_utc, datetime)
    # UTC calendar day vs local calendar day must differ.
    utc_day = start_utc.date()
    local_day = start_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(local_tz)).date()
    assert utc_day != local_day, (utc_day, local_day)


# --------------------------------------------------------------------------- #
# Idempotency: re-persisting the same batch inserts nothing new.
# --------------------------------------------------------------------------- #
def test_reference_intake_persist_is_idempotent(empty_warehouse) -> None:
    first = persist_intake_batch(empty_warehouse, _parse_intake())
    assert first.events_inserted == 4

    second = persist_intake_batch(empty_warehouse, _parse_intake())
    assert second.events_inserted == 0
    assert second.events_skipped_dup == 4

    # Row counts are unchanged after the re-run.
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 2
    )
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.supplement_intake_event").fetchone()[0]
        == 2
    )
