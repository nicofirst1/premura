"""`status`'s domain-table summary (issue #88, defect A).

`domain_table_summaries` is the pure, testable helper `status` calls into: it
must report every populated table in `duck.DOMAIN_TABLE_REGISTRY`, not just the
two generic fact tables. Driven by the registry rather than a hardcoded list,
so a new domain table becomes visible by registering it once.
"""

from __future__ import annotations

from datetime import date, datetime

from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionQuantityInput,
    SourceDescriptor,
)
from premura.store import duck
from premura.store.profile_intake import persist_intake_batch

T0 = datetime(2026, 1, 5, 8, 0, 0)


def test_domain_table_summaries_includes_populated_nutrition_tables(empty_warehouse) -> None:
    batch = IntakeBatch(
        source_descriptors={"mfp_src": SourceDescriptor(source_id="mfp_src", source_kind="mfp")},
        nutrition_events=[
            NutritionIntakeInput(
                source_id="mfp_src",
                source_kind="mfp",
                source_uuid="evt-1",
                start_utc=T0,
                meal_label="Breakfast",
                dedupe_key="mfp:evt-1",
                event_quantities=[
                    NutritionQuantityInput(
                        quantity_key="calories", value_num=400.0, unit="kcal", subject="event"
                    ),
                    NutritionQuantityInput(
                        quantity_key="protein", value_num=20.0, unit="g", subject="event"
                    ),
                ],
            )
        ],
    )
    persist_intake_batch(empty_warehouse, batch)

    summaries = {s.table: s for s in duck.domain_table_summaries(empty_warehouse)}

    assert "hp.nutrition_intake_event" in summaries
    assert summaries["hp.nutrition_intake_event"].row_count == 1
    assert summaries["hp.nutrition_intake_event"].earliest == "2026-01-05 08:00:00"

    assert "hp.nutrition_quantity" in summaries
    assert summaries["hp.nutrition_quantity"].row_count == 2


def test_domain_table_summaries_skips_empty_tables(empty_warehouse) -> None:
    summaries = duck.domain_table_summaries(empty_warehouse)
    assert summaries == []


def test_domain_table_summaries_reports_condition_episode(empty_warehouse) -> None:
    empty_warehouse.execute(
        """
        INSERT INTO hp.condition_episode
            (condition_label, start_day, end_day, source_kind)
        VALUES (?, ?, ?, ?)
        """,
        ["synthetic-condition", date(2026, 1, 1), None, "agent_condition_capture"],
    )

    summaries = {s.table: s for s in duck.domain_table_summaries(empty_warehouse)}
    assert summaries["hp.condition_episode"].row_count == 1
    assert summaries["hp.condition_episode"].earliest == "2026-01-01"
