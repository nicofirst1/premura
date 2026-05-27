"""Migration-level verification for 004_profile_intake.sql (WP01).

Black-box stance: the warehouse is always initialized through the public
``premura.store.duck`` initialization path (``initialize`` /
``run_migrations``), never by feeding raw SQL fragments. The assertions target
the storage-shape contract WP01 owns:

  * the three new domains (profile / nutrition / supplement) get their own
    explicit tables under ``hp.`` (no generic JSON catch-all bucket),
  * the pre-existing observation/note tables survive untouched,
  * the migration re-runs idempotently through the normal loader,
  * profile assertions are append/supersede-capable rather than overwrite-based,
  * nutrition and supplement storage are distinct from each other and from the
    observation/note homes.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from premura.store import duck

# Tables this migration is responsible for creating.
NEW_PROFILE_TABLES = {"profile_capture_session", "profile_context_assertion"}
NEW_NUTRITION_TABLES = {
    "nutrition_intake_event",
    "nutrition_intake_item",
    "nutrition_quantity",
}
NEW_SUPPLEMENT_TABLES = {
    "supplement_intake_event",
    "supplement_item",
    "supplement_dose",
}
NEW_TABLES = NEW_PROFILE_TABLES | NEW_NUTRITION_TABLES | NEW_SUPPLEMENT_TABLES

# Pre-existing observation/note homes that must NOT be disturbed by this WP.
EXISTING_FACT_TABLES = {
    "fact_measurement",
    "fact_interval",
    "fact_clinical_note",
}


def _hp_tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'hp'
        """
    ).fetchall()
    return {r[0] for r in rows}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'hp' AND table_name = ?
        """,
        [table],
    ).fetchall()
    return {r[0] for r in rows}


def _seed_source(conn: duckdb.DuckDBPyConnection, source_id: str = "src_test") -> str:
    duck.upsert_dim_source(conn, source_id=source_id, source_kind="bmt")
    return source_id


# --------------------------------------------------------------------------- #
# T003 — the new tables exist via the public init path.
# --------------------------------------------------------------------------- #
def test_new_domain_tables_exist_after_initialize(empty_warehouse) -> None:
    present = _hp_tables(empty_warehouse)
    missing = NEW_TABLES - present
    assert not missing, f"migration did not create expected tables: {sorted(missing)}"


def test_existing_observation_and_note_tables_survive(empty_warehouse) -> None:
    present = _hp_tables(empty_warehouse)
    missing = EXISTING_FACT_TABLES - present
    assert not missing, f"existing fact/note tables were lost: {sorted(missing)}"


def test_migration_is_idempotent_through_the_normal_loader(tmp_path: Path) -> None:
    """Re-running run_migrations on an initialized warehouse must not error and
    must not change the table inventory."""
    db = tmp_path / "idem.duckdb"
    conn = duck.initialize(db)
    try:
        before = _hp_tables(conn)
        # Normal loader path, run a second (and third) time.
        duck.run_migrations(conn)
        duck.run_migrations(conn)
        after = _hp_tables(conn)
        assert before == after
        assert NEW_TABLES.issubset(after)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# One-home separation is structural, not a generic bucket.
# --------------------------------------------------------------------------- #
def test_new_tables_are_not_reusing_observation_or_note_homes(empty_warehouse) -> None:
    """The new domains must have their own tables, distinct from the existing
    observation/note tables — i.e. they are not aliases or views over them."""
    present = _hp_tables(empty_warehouse)
    # Nutrition, supplement, and profile homes are all separately named tables.
    assert NEW_NUTRITION_TABLES.isdisjoint(EXISTING_FACT_TABLES)
    assert NEW_SUPPLEMENT_TABLES.isdisjoint(EXISTING_FACT_TABLES)
    assert NEW_PROFILE_TABLES.isdisjoint(EXISTING_FACT_TABLES)
    # And nutrition vs supplement are not the same storage.
    assert NEW_NUTRITION_TABLES.isdisjoint(NEW_SUPPLEMENT_TABLES)
    assert NEW_TABLES.issubset(present)


def test_provenance_and_dedupe_columns_present_for_intake(empty_warehouse) -> None:
    """Parser-driven writes will rely on provenance + dedupe columns existing."""
    nut = _columns(empty_warehouse, "nutrition_intake_event")
    assert {"source_id", "dedupe_key", "ingest_batch", "raw_payload"}.issubset(nut)

    sup = _columns(empty_warehouse, "supplement_intake_event")
    assert {"source_id", "dedupe_key", "ingest_batch", "raw_payload"}.issubset(sup)


def test_dedupe_keys_are_unique_per_intake_domain(empty_warehouse) -> None:
    """The UNIQUE dedupe constraint is what future idempotent loads depend on."""
    src = _seed_source(empty_warehouse)
    empty_warehouse.execute(
        "INSERT INTO hp.nutrition_intake_event (source_id, start_utc, dedupe_key) "
        "VALUES (?, TIMESTAMP '2026-01-01 08:00:00', 'nut-1')",
        [src],
    )
    with pytest.raises(duckdb.ConstraintException):
        empty_warehouse.execute(
            "INSERT INTO hp.nutrition_intake_event (source_id, start_utc, dedupe_key) "
            "VALUES (?, TIMESTAMP '2026-01-01 09:00:00', 'nut-1')",
            [src],
        )

    empty_warehouse.execute(
        "INSERT INTO hp.supplement_intake_event (source_id, ts_utc, dedupe_key) "
        "VALUES (?, TIMESTAMP '2026-01-01 08:00:00', 'sup-1')",
        [src],
    )
    with pytest.raises(duckdb.ConstraintException):
        empty_warehouse.execute(
            "INSERT INTO hp.supplement_intake_event (source_id, ts_utc, dedupe_key) "
            "VALUES (?, TIMESTAMP '2026-01-01 09:00:00', 'sup-1')",
            [src],
        )


# --------------------------------------------------------------------------- #
# Profile assertions are append/supersede capable, not overwrite-based.
# --------------------------------------------------------------------------- #
def test_profile_assertion_supports_supersession_history(empty_warehouse) -> None:
    """A corrected assertion is a NEW row pointing at the old one; both remain."""
    empty_warehouse.execute(
        "INSERT INTO hp.profile_capture_session (started_at, actor_kind) "
        "VALUES (TIMESTAMP '2026-01-01 10:00:00', 'agent')"
    )
    session_id = empty_warehouse.execute(
        "SELECT capture_session_id FROM hp.profile_capture_session"
    ).fetchone()[0]

    # Original assertion: height = 180 cm, effective from 2026-01-01.
    empty_warehouse.execute(
        """
        INSERT INTO hp.profile_context_assertion
            (capture_session_id, attribute_key, value_num, unit,
             effective_start_utc, source_kind)
        VALUES (?, 'standing_height_cm', 180.0, 'cm',
                TIMESTAMP '2026-01-01 10:00:00', 'agent_profile_capture')
        """,
        [session_id],
    )
    original_id = empty_warehouse.execute(
        "SELECT assertion_id FROM hp.profile_context_assertion "
        "WHERE attribute_key = 'standing_height_cm'"
    ).fetchone()[0]

    # Correction: supersede the original (close its window) and insert a new row.
    empty_warehouse.execute(
        "UPDATE hp.profile_context_assertion SET effective_end_utc = TIMESTAMP "
        "'2026-02-01 10:00:00' WHERE assertion_id = ?",
        [original_id],
    )
    empty_warehouse.execute(
        """
        INSERT INTO hp.profile_context_assertion
            (capture_session_id, attribute_key, value_num, unit,
             effective_start_utc, source_kind, supersedes_assertion_id)
        VALUES (?, 'standing_height_cm', 182.0, 'cm',
                TIMESTAMP '2026-02-01 10:00:00', 'agent_profile_capture', ?)
        """,
        [session_id, original_id],
    )

    # History is preserved: two rows for the attribute, old one closed, new one
    # open and pointing back at the row it corrected.
    rows = empty_warehouse.execute(
        "SELECT assertion_id, value_num, effective_end_utc, supersedes_assertion_id "
        "FROM hp.profile_context_assertion "
        "WHERE attribute_key = 'standing_height_cm' ORDER BY effective_start_utc"
    ).fetchall()
    assert len(rows) == 2, "supersession overwrote history instead of appending"
    old, new = rows
    assert old[1] == 180.0 and old[2] is not None, "original assertion was not retained/closed"
    assert new[1] == 182.0 and new[2] is None, "correction is not the current open assertion"
    assert new[3] == original_id, "correction does not link to the assertion it supersedes"


def test_profile_session_can_hold_multiple_assertions(empty_warehouse) -> None:
    """ProfileCaptureSession 1:N ProfileContextAssertion relationship works."""
    empty_warehouse.execute(
        "INSERT INTO hp.profile_capture_session (started_at, actor_kind) "
        "VALUES (TIMESTAMP '2026-01-01 10:00:00', 'agent')"
    )
    session_id = empty_warehouse.execute(
        "SELECT capture_session_id FROM hp.profile_capture_session"
    ).fetchone()[0]
    for key, val in (("sex", "value_text"), ("standing_height_cm", "value_num")):
        slot = "value_text" if val == "value_text" else "value_num"
        payload = "'female'" if slot == "value_text" else "165.0"
        empty_warehouse.execute(
            f"""
            INSERT INTO hp.profile_context_assertion
                (capture_session_id, attribute_key, {slot},
                 effective_start_utc, source_kind)
            VALUES (?, '{key}', {payload},
                    TIMESTAMP '2026-01-01 10:00:00', 'agent_profile_capture')
            """,
            [session_id],
        )
    n = empty_warehouse.execute(
        "SELECT COUNT(*) FROM hp.profile_context_assertion WHERE capture_session_id = ?",
        [session_id],
    ).fetchone()[0]
    assert n == 2


# --------------------------------------------------------------------------- #
# Parent-child joins for the intake hierarchies are real FKs.
# --------------------------------------------------------------------------- #
def test_nutrition_event_item_quantity_hierarchy(empty_warehouse) -> None:
    src = _seed_source(empty_warehouse)
    empty_warehouse.execute(
        "INSERT INTO hp.nutrition_intake_event (source_id, start_utc, meal_label, dedupe_key) "
        "VALUES (?, TIMESTAMP '2026-01-01 08:00:00', 'breakfast', 'nut-evt-1')",
        [src],
    )
    event_id = empty_warehouse.execute(
        "SELECT nutrition_event_id FROM hp.nutrition_intake_event"
    ).fetchone()[0]
    empty_warehouse.execute(
        "INSERT INTO hp.nutrition_intake_item (nutrition_event_id, item_label) VALUES (?, 'oats')",
        [event_id],
    )
    item_id = empty_warehouse.execute(
        "SELECT nutrition_item_id FROM hp.nutrition_intake_item"
    ).fetchone()[0]
    # Item-level quantity.
    empty_warehouse.execute(
        "INSERT INTO hp.nutrition_quantity (nutrition_item_id, quantity_key, value_num, unit) "
        "VALUES (?, 'energy', 150.0, 'kcal')",
        [item_id],
    )
    # Event-level quantity.
    empty_warehouse.execute(
        "INSERT INTO hp.nutrition_quantity (nutrition_event_id, quantity_key, value_num, unit) "
        "VALUES (?, 'energy', 320.0, 'kcal')",
        [event_id],
    )
    joined = empty_warehouse.execute(
        """
        SELECT COUNT(*)
        FROM hp.nutrition_quantity q
        LEFT JOIN hp.nutrition_intake_item i ON q.nutrition_item_id = i.nutrition_item_id
        LEFT JOIN hp.nutrition_intake_event e ON q.nutrition_event_id = e.nutrition_event_id
        """
    ).fetchone()[0]
    assert joined == 2


def test_nutrition_quantity_requires_a_parent(empty_warehouse) -> None:
    """A quantity with neither an event nor an item parent is meaningless."""
    with pytest.raises(duckdb.ConstraintException):
        empty_warehouse.execute(
            "INSERT INTO hp.nutrition_quantity (quantity_key, value_num, unit) "
            "VALUES ('energy', 100.0, 'kcal')"
        )


def test_supplement_event_item_dose_hierarchy(empty_warehouse) -> None:
    src = _seed_source(empty_warehouse)
    empty_warehouse.execute(
        "INSERT INTO hp.supplement_intake_event (source_id, ts_utc, dedupe_key) "
        "VALUES (?, TIMESTAMP '2026-01-01 08:00:00', 'sup-evt-1')",
        [src],
    )
    event_id = empty_warehouse.execute(
        "SELECT supplement_event_id FROM hp.supplement_intake_event"
    ).fetchone()[0]
    empty_warehouse.execute(
        "INSERT INTO hp.supplement_item (supplement_event_id, product_label, form_label) "
        "VALUES (?, 'VitaCo D3', 'capsule')",
        [event_id],
    )
    item_id = empty_warehouse.execute(
        "SELECT supplement_item_id FROM hp.supplement_item"
    ).fetchone()[0]
    empty_warehouse.execute(
        "INSERT INTO hp.supplement_dose (supplement_item_id, ingredient_label, amount_num, unit) "
        "VALUES (?, 'vitamin_d3', 2000.0, 'IU')",
        [item_id],
    )
    joined = empty_warehouse.execute(
        """
        SELECT d.amount_num, d.unit, i.product_label, e.dedupe_key
        FROM hp.supplement_dose d
        JOIN hp.supplement_item i ON d.supplement_item_id = i.supplement_item_id
        JOIN hp.supplement_intake_event e ON i.supplement_event_id = e.supplement_event_id
        """
    ).fetchall()
    assert joined == [(2000.0, "IU", "VitaCo D3", "sup-evt-1")]


def test_supplement_dose_requires_an_amount(empty_warehouse) -> None:
    """A dose must carry either a numeric or textual amount, not neither."""
    src = _seed_source(empty_warehouse)
    empty_warehouse.execute(
        "INSERT INTO hp.supplement_intake_event (source_id, ts_utc, dedupe_key) "
        "VALUES (?, TIMESTAMP '2026-01-01 08:00:00', 'sup-evt-2')",
        [src],
    )
    event_id = empty_warehouse.execute(
        "SELECT supplement_event_id FROM hp.supplement_intake_event"
    ).fetchone()[0]
    empty_warehouse.execute(
        "INSERT INTO hp.supplement_item (supplement_event_id, ingredient_label) VALUES (?, 'zinc')",
        [event_id],
    )
    item_id = empty_warehouse.execute(
        "SELECT supplement_item_id FROM hp.supplement_item"
    ).fetchone()[0]
    with pytest.raises(duckdb.ConstraintException):
        empty_warehouse.execute(
            "INSERT INTO hp.supplement_dose (supplement_item_id, ingredient_label) "
            "VALUES (?, 'zinc')",
            [item_id],
        )
    # Qualitative-only amount is allowed.
    empty_warehouse.execute(
        "INSERT INTO hp.supplement_dose (supplement_item_id, amount_text) VALUES (?, 'one scoop')",
        [item_id],
    )
