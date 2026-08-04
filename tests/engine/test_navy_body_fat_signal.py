"""Navy body-fat % signal tests (issue #100).

Navy body-fat is the second cross-domain Stage 2 answer, built on the same
input-resolution seam BMI proved. It crosses three semantic reads:

* declared ``sex`` and ``standing_height_cm`` from ``profile_context``;
* ``waist_circumference`` and ``neck_circumference`` from
  ``observation_history`` (plus ``hip_circumference`` for female).

The U.S. Navy circumference method has only male and female variants, so a
declared ``sex`` outside that pair (e.g. ``intersex``) or an unset sex is an
honest refusal, never a guessed formula. These tests pin down:

* both sex variants compute the standard formula through the public
  ``compute("navy_body_fat", conn)`` surface;
* every refusal path returns an explicit :class:`MissingInputReport` and never
  fabricates a value or guesses a formula variant;
* male does not require a hip measurement; female does;
* the consumer reaches every input through the public seam
  (:func:`premura.engine.resolve_dependency`), never by poking the warehouse.

Patterns mirror ``tests/engine/test_bmi_signal.py``.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from premura.engine import (
    REGISTRY,
    MissingInputReport,
    ResolutionRequest,
    ResolvedInput,
    StatusResult,
    compute,
    resolve_dependency,
)
from premura.engine._results import FreshnessState
from premura.engine.descriptive_signals import navy_body_fat, register_builtin_signals
from premura.store.profile_intake import record_profile_context

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def anchor_ts() -> datetime:
    """A fixed timezone-aware anchor used across the tests."""
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def registered(empty_warehouse: Any) -> Any:
    """Warehouse with the built-in descriptive signals registered in REGISTRY.

    Snapshots and restores REGISTRY so registration does not leak across tests.
    """
    snapshot = dict(REGISTRY)
    register_builtin_signals()
    try:
        yield empty_warehouse
    finally:
        REGISTRY.clear()
        REGISTRY.update(snapshot)


def _naive(ts: datetime) -> datetime:
    """Strip tzinfo so the value lands in DuckDB as the same naive-UTC instant."""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


def _ensure_source(conn: Any, source_id: str = "wearable:test") -> str:
    """Insert a dim_source row so fact_measurement.source_id FKs resolve."""
    conn.execute(
        """
        INSERT INTO hp.dim_source (source_id, source_kind, first_seen, last_seen)
        VALUES (?, 'wearable', now(), now())
        ON CONFLICT (source_id) DO NOTHING
        """,
        [source_id],
    )
    return source_id


def _insert_circumference(
    conn: Any,
    *,
    metric_id: str,
    ts: datetime,
    value: float,
    source_id: str = "wearable:test",
) -> None:
    """Insert one circumference ``fact_measurement`` row (cm)."""
    key = f"{metric_id}-{ts.isoformat()}-{value}"
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, ?, ?, 'cm', ?, ?, ?)
        """,
        [_naive(ts), metric_id, value, source_id, key, key],
    )


def _record_profile(conn: Any, *, anchor: datetime, attribute_key: str, value: Any) -> None:
    """Record a declared profile assertion, dated well before the anchor."""
    record_profile_context(
        conn,
        attribute_key=attribute_key,
        value=value,
        effective_start_utc=_naive(anchor) - timedelta(days=30),
    )


def _seed_male(conn: Any, anchor: datetime) -> None:
    """A complete, fresh male measurement set."""
    _ensure_source(conn)
    _record_profile(conn, anchor=anchor, attribute_key="sex", value="male")
    _record_profile(conn, anchor=anchor, attribute_key="standing_height_cm", value=180.0)
    fresh = anchor - timedelta(hours=1)
    _insert_circumference(conn, metric_id="waist_circumference", ts=fresh, value=90.0)
    _insert_circumference(conn, metric_id="neck_circumference", ts=fresh, value=38.0)


def _seed_female(conn: Any, anchor: datetime) -> None:
    """A complete, fresh female measurement set (includes hip)."""
    _ensure_source(conn)
    _record_profile(conn, anchor=anchor, attribute_key="sex", value="female")
    _record_profile(conn, anchor=anchor, attribute_key="standing_height_cm", value=165.0)
    fresh = anchor - timedelta(hours=1)
    _insert_circumference(conn, metric_id="waist_circumference", ts=fresh, value=80.0)
    _insert_circumference(conn, metric_id="neck_circumference", ts=fresh, value=34.0)
    _insert_circumference(conn, metric_id="hip_circumference", ts=fresh, value=100.0)


def _expected_male(*, waist: float, neck: float, height: float) -> float:
    return (
        495.0 / (1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height)) - 450.0
    )


def _expected_female(*, waist: float, hip: float, neck: float, height: float) -> float:
    return (
        495.0 / (1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.22100 * math.log10(height))
        - 450.0
    )


# ---------------------------------------------------------------------------
# 1. Happy path — male, no hip required
# ---------------------------------------------------------------------------


def test_navy_body_fat_male_success(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _seed_male(conn, anchor_ts)

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, StatusResult)
    assert result.metric_id == "body_fat_pct"
    assert result.signal_name == "navy_body_fat"
    assert result.unit == "pct"
    assert result.freshness_state is FreshnessState.CURRENT
    assert result.value == pytest.approx(
        round(_expected_male(waist=90.0, neck=38.0, height=180.0), 2)
    )
    assert any("estimate" in caveat.lower() for caveat in result.caveats)


# ---------------------------------------------------------------------------
# 2. Happy path — female, hip required and used
# ---------------------------------------------------------------------------


def test_navy_body_fat_female_success(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _seed_female(conn, anchor_ts)

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, StatusResult)
    assert result.metric_id == "body_fat_pct"
    assert result.value == pytest.approx(
        round(_expected_female(waist=80.0, hip=100.0, neck=34.0, height=165.0), 2)
    )


# ---------------------------------------------------------------------------
# 3. Refusal — intersex sex has no formula variant (honest refusal, no guess)
# ---------------------------------------------------------------------------


def test_navy_body_fat_refuses_intersex(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _seed_male(conn, anchor_ts)
    # Override the declared sex to intersex (present, but no Navy variant).
    _record_profile(conn, anchor=anchor_ts, attribute_key="sex", value="intersex")

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert result.tool_name == "navy_body_fat"
    # It is present-but-unusable, not missing: the refusal names sex and does
    # not fabricate a value.
    assert "profile:sex" in (result.missing_inputs + result.stale_inputs)
    assert "intersex" in result.message.lower() or "sex" in result.message.lower()


# ---------------------------------------------------------------------------
# 4. Refusal — sex not declared at all
# ---------------------------------------------------------------------------


def test_navy_body_fat_refuses_when_sex_unset(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _ensure_source(conn)
    _record_profile(conn, anchor=anchor_ts, attribute_key="standing_height_cm", value=180.0)
    fresh = anchor_ts - timedelta(hours=1)
    _insert_circumference(conn, metric_id="waist_circumference", ts=fresh, value=90.0)
    _insert_circumference(conn, metric_id="neck_circumference", ts=fresh, value=38.0)

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert "profile:sex" in result.missing_inputs


# ---------------------------------------------------------------------------
# 5. Refusal — female with no hip measurement
# ---------------------------------------------------------------------------


def test_navy_body_fat_female_refuses_without_hip(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _ensure_source(conn)
    _record_profile(conn, anchor=anchor_ts, attribute_key="sex", value="female")
    _record_profile(conn, anchor=anchor_ts, attribute_key="standing_height_cm", value=165.0)
    fresh = anchor_ts - timedelta(hours=1)
    _insert_circumference(conn, metric_id="waist_circumference", ts=fresh, value=80.0)
    _insert_circumference(conn, metric_id="neck_circumference", ts=fresh, value=34.0)
    # No hip.

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert "observation:hip_circumference" in result.missing_inputs


# ---------------------------------------------------------------------------
# 6. Male success needs no hip (hip absence is not a refusal for male)
# ---------------------------------------------------------------------------


def test_navy_body_fat_male_ignores_missing_hip(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _seed_male(conn, anchor_ts)  # deliberately no hip inserted

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, StatusResult)


# ---------------------------------------------------------------------------
# 7. Refusal — a required circumference is missing
# ---------------------------------------------------------------------------


def test_navy_body_fat_refuses_when_waist_missing(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _ensure_source(conn)
    _record_profile(conn, anchor=anchor_ts, attribute_key="sex", value="male")
    _record_profile(conn, anchor=anchor_ts, attribute_key="standing_height_cm", value=180.0)
    fresh = anchor_ts - timedelta(hours=1)
    _insert_circumference(conn, metric_id="neck_circumference", ts=fresh, value=38.0)
    # No waist.

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert "observation:waist_circumference" in result.missing_inputs


# ---------------------------------------------------------------------------
# 8. Refusal — a required circumference is stale
# ---------------------------------------------------------------------------


def test_navy_body_fat_refuses_when_circumference_stale(
    registered: Any, anchor_ts: datetime
) -> None:
    conn = registered
    _ensure_source(conn)
    _record_profile(conn, anchor=anchor_ts, attribute_key="sex", value="male")
    _record_profile(conn, anchor=anchor_ts, attribute_key="standing_height_cm", value=180.0)
    fresh = anchor_ts - timedelta(hours=1)
    stale = anchor_ts - timedelta(days=30)  # past P1W
    _insert_circumference(conn, metric_id="waist_circumference", ts=stale, value=90.0)
    _insert_circumference(conn, metric_id="neck_circumference", ts=fresh, value=38.0)

    result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert "observation:waist_circumference" in result.stale_inputs


# ---------------------------------------------------------------------------
# 9. Registered in the engine registry under the status family
# ---------------------------------------------------------------------------


def test_navy_body_fat_is_registered(registered: Any) -> None:
    assert "navy_body_fat" in REGISTRY
    assert REGISTRY["navy_body_fat"].fn is navy_body_fat
    assert REGISTRY["navy_body_fat"].family == "status"


# ---------------------------------------------------------------------------
# 10. Dispatches through the public compute() surface
# ---------------------------------------------------------------------------


def test_navy_body_fat_dispatches_through_compute(empty_warehouse: Any) -> None:
    conn = empty_warehouse
    now = datetime.now(tz=UTC)
    _seed_male(conn, now)

    result = compute("navy_body_fat", conn)

    assert isinstance(result, StatusResult)
    assert result.metric_id == "body_fat_pct"


# ---------------------------------------------------------------------------
# 11. Reaches every input through the seam, never by direct reads
# ---------------------------------------------------------------------------


def test_navy_body_fat_uses_resolver_seam(registered: Any, anchor_ts: datetime) -> None:
    conn = registered
    _seed_female(conn, anchor_ts)

    calls: list[ResolutionRequest] = []

    def spy(*, conn: Any, request: ResolutionRequest) -> ResolvedInput:
        calls.append(request)
        return resolve_dependency(conn, request)

    with patch(
        "premura.engine.descriptive_signals.resolve_dependency",
        side_effect=spy,
    ):
        result = navy_body_fat(conn, anchor_ts=anchor_ts)

    assert isinstance(result, StatusResult)
    # Female path resolves sex + height (profile) and waist + neck + hip (obs).
    seen = sorted(req.dependency.required_key for req in calls)
    assert seen == [
        "hip_circumference",
        "neck_circumference",
        "sex",
        "standing_height_cm",
        "waist_circumference",
    ]
