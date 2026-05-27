"""Persistence service for bounded profile capture and normalized intake.

Two write paths land here, matching the planning model:

* :func:`record_profile_context` — bounded agent-mediated profile capture. It
  writes one :class:`~premura.parsers.base` -independent assertion into
  ``hp.profile_context_assertion``, optionally superseding a prior open
  assertion for the same attribute (append/supersede, never overwrite).
* :func:`persist_intake_batch` — normalized nutrition/supplement records emitted
  by a future parser as an
  :class:`premura.parsers.base.IntakeBatch`. Events land in their dedicated
  ``hp.nutrition_intake_*`` / ``hp.supplement_intake_*`` tables, deduped on the
  ``dedupe_key`` UNIQUE constraint so re-loading the same source artifact is a
  no-op.

The store boundary is authoritative for validation: an unsupported profile
attribute fails *here* (via ``premura.profile_fields``), not later in the tool
layer. There is deliberately no generic attribute writer — that is the central
risk this WP guards against.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from ..parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    SupplementIntakeInput,
)
from ..profile_fields import ProfileValueKind, get_profile_field
from .duck import upsert_dim_source

if TYPE_CHECKING:
    import duckdb

DEFAULT_PROFILE_SOURCE_KIND = "agent_profile_capture"


# --------------------------------------------------------------------------- #
# Profile capture.
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ProfileAssertionRecord:
    """Read-back view of one stored profile assertion."""

    assertion_id: int
    attribute_key: str
    value_text: str | None
    value_num: float | None
    value_date: date | None
    unit: str | None
    effective_start_utc: datetime
    effective_end_utc: datetime | None
    source_kind: str
    supersedes_assertion_id: int | None


def start_profile_capture_session(
    conn: duckdb.DuckDBPyConnection,
    *,
    actor_kind: str = "agent",
    actor_ref: str | None = None,
    started_at: datetime | None = None,
    notes: str | None = None,
) -> int:
    """Open a bounded profile-capture session and return its id.

    Session rows hold bookkeeping only; they must never store health
    interpretation text (that is note history's job).
    """
    row = conn.execute(
        """
        INSERT INTO hp.profile_capture_session (started_at, actor_kind, actor_ref, notes)
        VALUES (COALESCE(?, now()), ?, ?, ?)
        RETURNING capture_session_id
        """,
        [started_at, actor_kind, actor_ref, notes],
    ).fetchone()
    assert row is not None
    return int(row[0])


def _typed_slots(attribute_key: str, value: Any) -> tuple[str | None, float | None, date | None]:
    """Map a value onto exactly one typed slot per the field's value_kind.

    Raises on a value that does not fit the declared kind, so a wrong-typed
    assertion fails at the store boundary rather than silently landing in the
    wrong slot.
    """
    field = get_profile_field(attribute_key)
    kind = field.value_kind

    if kind is ProfileValueKind.DATE:
        if isinstance(value, datetime):
            return None, None, value.date()
        if isinstance(value, date):
            return None, None, value
        if isinstance(value, str):
            return None, None, date.fromisoformat(value)
        raise ValueError(f"{attribute_key!r} expects a date value, got {type(value).__name__}")

    if kind is ProfileValueKind.QUANTITY:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"{attribute_key!r} expects a numeric value, got {type(value).__name__}"
            )
        return None, float(value), None

    if kind is ProfileValueKind.ENUM:
        if not isinstance(value, str):
            raise ValueError(f"{attribute_key!r} expects a text value, got {type(value).__name__}")
        if field.allowed_values is not None and value not in field.allowed_values:
            raise ValueError(
                f"{attribute_key!r} value {value!r} not in allowed set {field.allowed_values}"
            )
        return value, None, None

    # ProfileValueKind.TEXT
    if not isinstance(value, str):
        raise ValueError(f"{attribute_key!r} expects a text value, got {type(value).__name__}")
    return value, None, None


def current_assertion_id(
    conn: duckdb.DuckDBPyConnection,
    attribute_key: str,
) -> int | None:
    """Return the open (effective_end_utc IS NULL) assertion id for an attribute."""
    row = conn.execute(
        """
        SELECT assertion_id
        FROM hp.profile_context_assertion
        WHERE attribute_key = ? AND effective_end_utc IS NULL
        ORDER BY effective_start_utc DESC, assertion_id DESC
        LIMIT 1
        """,
        [attribute_key],
    ).fetchone()
    return int(row[0]) if row else None


def record_profile_context(
    conn: duckdb.DuckDBPyConnection,
    *,
    attribute_key: str,
    value: Any,
    effective_start_utc: datetime,
    capture_session_id: int | None = None,
    source_kind: str = DEFAULT_PROFILE_SOURCE_KIND,
    source_ref: str | None = None,
    supersede: bool = True,
    raw_payload: dict[str, Any] | None = None,
) -> int:
    """Record one bounded baseline profile assertion; return its assertion_id.

    The attribute must be in the bounded allowlist (``premura.profile_fields``);
    anything else — including the derived ``age`` key — raises
    ``UnsupportedProfileFieldError`` here at the store boundary.

    When ``supersede`` is true and an open assertion already exists for the same
    attribute, the prior row's ``effective_end_utc`` is closed at this
    assertion's ``effective_start_utc`` and the new row links back via
    ``supersedes_assertion_id``. History is appended, never overwritten.
    """
    # Validate + map the value first so a bad value never opens a transaction
    # that mutates prior history.
    value_text, value_num, value_date = _typed_slots(attribute_key, value)
    unit = get_profile_field(attribute_key).unit

    conn.execute("BEGIN")
    try:
        superseded_id: int | None = None
        if supersede:
            superseded_id = current_assertion_id(conn, attribute_key)
            if superseded_id is not None:
                conn.execute(
                    """
                    UPDATE hp.profile_context_assertion
                    SET effective_end_utc = ?
                    WHERE assertion_id = ?
                    """,
                    [effective_start_utc, superseded_id],
                )
        row = conn.execute(
            """
            INSERT INTO hp.profile_context_assertion
                (capture_session_id, attribute_key, value_text, value_num, value_date,
                 unit, effective_start_utc, source_kind, source_ref,
                 supersedes_assertion_id, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING assertion_id
            """,
            [
                capture_session_id,
                attribute_key,
                value_text,
                value_num,
                value_date,
                unit,
                effective_start_utc,
                source_kind,
                source_ref,
                superseded_id,
                _dumps(raw_payload),
            ],
        ).fetchone()
        conn.execute("COMMIT")
        assert row is not None
        return int(row[0])
    except Exception:
        conn.execute("ROLLBACK")
        raise


def get_current_profile(
    conn: duckdb.DuckDBPyConnection,
    attribute_key: str,
) -> ProfileAssertionRecord | None:
    """Return the current open assertion for an attribute, if any."""
    row = conn.execute(
        """
        SELECT assertion_id, attribute_key, value_text, value_num, value_date, unit,
               effective_start_utc, effective_end_utc, source_kind, supersedes_assertion_id
        FROM hp.profile_context_assertion
        WHERE attribute_key = ? AND effective_end_utc IS NULL
        ORDER BY effective_start_utc DESC, assertion_id DESC
        LIMIT 1
        """,
        [attribute_key],
    ).fetchone()
    return _to_assertion_record(row) if row else None


def get_profile_history(
    conn: duckdb.DuckDBPyConnection,
    attribute_key: str,
) -> list[ProfileAssertionRecord]:
    """Return every assertion for an attribute, oldest first (full lineage)."""
    rows = conn.execute(
        """
        SELECT assertion_id, attribute_key, value_text, value_num, value_date, unit,
               effective_start_utc, effective_end_utc, source_kind, supersedes_assertion_id
        FROM hp.profile_context_assertion
        WHERE attribute_key = ?
        ORDER BY effective_start_utc ASC, assertion_id ASC
        """,
        [attribute_key],
    ).fetchall()
    return [_to_assertion_record(row) for row in rows]


def _to_assertion_record(row: tuple) -> ProfileAssertionRecord:
    return ProfileAssertionRecord(
        assertion_id=int(row[0]),
        attribute_key=row[1],
        value_text=row[2],
        value_num=row[3],
        value_date=row[4],
        unit=row[5],
        effective_start_utc=row[6],
        effective_end_utc=row[7],
        source_kind=row[8],
        supersedes_assertion_id=None if row[9] is None else int(row[9]),
    )


# --------------------------------------------------------------------------- #
# Normalized intake.
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class IntakeLoadStats:
    """Insert / skip counts for one persisted intake batch."""

    nutrition_events_inserted: int = 0
    nutrition_events_skipped_dup: int = 0
    supplement_events_inserted: int = 0
    supplement_events_skipped_dup: int = 0

    @property
    def events_inserted(self) -> int:
        return self.nutrition_events_inserted + self.supplement_events_inserted

    @property
    def events_skipped_dup(self) -> int:
        return self.nutrition_events_skipped_dup + self.supplement_events_skipped_dup


def persist_intake_batch(
    conn: duckdb.DuckDBPyConnection,
    batch: IntakeBatch,
) -> IntakeLoadStats:
    """Persist one normalized intake batch in a single transaction.

    Events are deduped on their ``dedupe_key`` UNIQUE constraint: an event whose
    key already exists is skipped wholesale (its children are not re-inserted),
    so re-running the same source artifact is idempotent. Returns insert / skip
    counts per domain.
    """
    batch.validate()

    conn.execute("BEGIN")
    try:
        for descriptor in batch.source_descriptors.values():
            upsert_dim_source(
                conn,
                source_id=descriptor.source_id,
                source_kind=descriptor.source_kind,
                app_package=descriptor.app_package,
                app_name=descriptor.app_name,
                device_manufacturer=descriptor.device_manufacturer,
                device_model=descriptor.device_model,
            )

        stats = IntakeLoadStats()
        for event in batch.nutrition_events:
            inserted = _persist_nutrition_event(conn, event, ingest_batch=batch.ingest_batch)
            if inserted:
                stats.nutrition_events_inserted += 1
            else:
                stats.nutrition_events_skipped_dup += 1
        for sup_event in batch.supplement_events:
            inserted = _persist_supplement_event(conn, sup_event, ingest_batch=batch.ingest_batch)
            if inserted:
                stats.supplement_events_inserted += 1
            else:
                stats.supplement_events_skipped_dup += 1

        conn.execute("COMMIT")
        return stats
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _dedupe_key_exists(conn: duckdb.DuckDBPyConnection, table: str, dedupe_key: str) -> bool:
    row = conn.execute(
        f"SELECT 1 FROM hp.{table} WHERE dedupe_key = ? LIMIT 1",  # noqa: S608 (table is internal)
        [dedupe_key],
    ).fetchone()
    return row is not None


def _persist_nutrition_event(
    conn: duckdb.DuckDBPyConnection,
    event: NutritionIntakeInput,
    *,
    ingest_batch: str | None,
) -> bool:
    """Insert one nutrition event + children. Returns False if deduped (skipped)."""
    if _dedupe_key_exists(conn, "nutrition_intake_event", event.dedupe_key):
        return False

    row = conn.execute(
        """
        INSERT INTO hp.nutrition_intake_event
            (source_id, source_uuid, start_utc, end_utc, local_tz, meal_label,
             dedupe_key, ingest_batch, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING nutrition_event_id
        """,
        [
            event.source_id,
            event.source_uuid,
            event.start_utc,
            event.end_utc,
            event.local_tz,
            event.meal_label,
            event.dedupe_key,
            ingest_batch,
            _dumps(event.raw_payload),
        ],
    ).fetchone()
    assert row is not None
    event_id = int(row[0])

    for quantity in event.event_quantities:
        conn.execute(
            """
            INSERT INTO hp.nutrition_quantity
                (nutrition_event_id, quantity_key, value_num, unit, raw_payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            [event_id, quantity.quantity_key, quantity.value_num, quantity.unit,
             _dumps(quantity.raw_payload)],
        )

    for item in event.items:
        item_row = conn.execute(
            """
            INSERT INTO hp.nutrition_intake_item
                (nutrition_event_id, item_label, brand_label, serving_text, raw_payload)
            VALUES (?, ?, ?, ?, ?)
            RETURNING nutrition_item_id
            """,
            [event_id, item.item_label, item.brand_label, item.serving_text,
             _dumps(item.raw_payload)],
        ).fetchone()
        assert item_row is not None
        item_id = int(item_row[0])
        for quantity in item.quantities:
            conn.execute(
                """
                INSERT INTO hp.nutrition_quantity
                    (nutrition_item_id, quantity_key, value_num, unit, raw_payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                [item_id, quantity.quantity_key, quantity.value_num, quantity.unit,
                 _dumps(quantity.raw_payload)],
            )
    return True


def _persist_supplement_event(
    conn: duckdb.DuckDBPyConnection,
    event: SupplementIntakeInput,
    *,
    ingest_batch: str | None,
) -> bool:
    """Insert one supplement event + children. Returns False if deduped (skipped)."""
    if _dedupe_key_exists(conn, "supplement_intake_event", event.dedupe_key):
        return False

    row = conn.execute(
        """
        INSERT INTO hp.supplement_intake_event
            (source_id, source_uuid, ts_utc, local_tz, dedupe_key, ingest_batch, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING supplement_event_id
        """,
        [
            event.source_id,
            event.source_uuid,
            event.ts_utc,
            event.local_tz,
            event.dedupe_key,
            ingest_batch,
            _dumps(event.raw_payload),
        ],
    ).fetchone()
    assert row is not None
    event_id = int(row[0])

    for item in event.items:
        item_row = conn.execute(
            """
            INSERT INTO hp.supplement_item
                (supplement_event_id, product_label, ingredient_label, form_label, raw_payload)
            VALUES (?, ?, ?, ?, ?)
            RETURNING supplement_item_id
            """,
            [event_id, item.product_label, item.ingredient_label, item.form_label,
             _dumps(item.raw_payload)],
        ).fetchone()
        assert item_row is not None
        item_id = int(item_row[0])
        for dose in item.doses:
            conn.execute(
                """
                INSERT INTO hp.supplement_dose
                    (supplement_item_id, ingredient_label, amount_num, amount_text, unit,
                     raw_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [item_id, dose.ingredient_label, dose.amount_num, dose.amount_text, dose.unit,
                 _dumps(dose.raw_payload)],
            )
    return True


def _dumps(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, default=_json_default)


def _json_default(o: object) -> object:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(f"Unserializable: {type(o).__name__}")


__all__ = [
    "DEFAULT_PROFILE_SOURCE_KIND",
    "IntakeLoadStats",
    "ProfileAssertionRecord",
    "current_assertion_id",
    "get_current_profile",
    "get_profile_history",
    "persist_intake_batch",
    "record_profile_context",
    "start_profile_capture_session",
]
