"""WP03 — BMI proof consumer tests.

BMI is the first Stage 2 answer that crosses two semantic domains: declared
standing height from ``profile_context`` and body weight from
``observation_history``. These tests pin down the proof slice of the consumer:

* the happy path actually produces a :class:`StatusResult` through the public
  ``compute("bmi", conn)`` surface, not just via a direct import;
* every refusal path returns an explicit :class:`MissingInputReport` and never
  silently substitutes a measured-height observation for a declared profile
  height;
* the consumer reaches its inputs through the public input-resolution seam
  (:func:`premura.engine.resolve_dependency`) rather than poking the warehouse
  directly;
* unresolved future intake domains (nutrition, supplements) do not contaminate
  BMI's behavior.

Patterns mirrored from ``tests/test_engine_resolvers.py`` and
``tests/test_engine_descriptive_signals.py``: each test re-registers the
WP03 signal into ``REGISTRY`` via the fixture below and inserts rows directly
into the warehouse through the same small helpers those siblings use.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from premura.engine import (
    REGISTRY,
    DependencyDeclaration,
    MissingInputReport,
    ResolutionRequest,
    ResolvedInput,
    StatusResult,
    compute,
    resolve_dependency,
)
from premura.engine._results import FreshnessState
from premura.engine.descriptive_signals import bmi, register_builtin_signals
from premura.store.profile_intake import record_profile_context

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def anchor_ts() -> datetime:
    """A fixed timezone-aware anchor used across the BMI tests."""
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def registered(empty_warehouse: Any) -> Any:
    """Warehouse with the WP02 + WP03 descriptive signals registered in REGISTRY.

    Snapshots and restores REGISTRY so registration does not leak across tests.
    Mirrors the pattern in ``tests/test_engine_descriptive_signals.py``.
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


def _insert_weight(
    conn: Any,
    *,
    ts: datetime,
    value: float,
    source_id: str = "wearable:test",
    key: str | None = None,
) -> None:
    """Insert one weight ``fact_measurement`` row for testing.

    Weight is instantaneous, so it goes in ``hp.fact_measurement`` (not
    ``hp.fact_interval``). Mirrors the helper in
    ``tests/test_engine_resolvers.py``.
    """
    if key is None:
        key = f"weight-{ts.isoformat()}-{value}"
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, 'weight', ?, 'kg', ?, ?, ?)
        """,
        [_naive(ts), value, source_id, key, key],
    )


def _insert_measured_height(
    conn: Any,
    *,
    ts: datetime,
    value: float,
    source_id: str = "wearable:test",
    key: str | None = None,
) -> None:
    """Insert one ``height`` observation (NOT a profile assertion).

    Used to prove BMI never silently substitutes a measured-height observation
    for a declared profile height.
    """
    if key is None:
        key = f"height-{ts.isoformat()}-{value}"
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, 'height', ?, 'm', ?, ?, ?)
        """,
        [_naive(ts), value, source_id, key, key],
    )


def _record_height(
    conn: Any,
    *,
    anchor: datetime,
    value_cm: float = 180.0,
) -> None:
    """Record a declared standing-height profile assertion via the public API.

    The assertion is dated comfortably before the anchor so it is valid as-of
    the anchor under the profile resolver's latest-valid-as-of semantics.
    """
    record_profile_context(
        conn,
        attribute_key="standing_height_cm",
        value=value_cm,
        effective_start_utc=_naive(anchor) - timedelta(days=30),
    )


# ---------------------------------------------------------------------------
# 1. Happy path — declared height + usable weight => StatusResult
# ---------------------------------------------------------------------------


def test_bmi_success_with_declared_height_and_usable_weight(
    registered: Any, anchor_ts: datetime
) -> None:
    """A declared height + a fresh weight within P1W yields a usable BMI.

    Asserts on the externally visible :class:`StatusResult` fields — the
    metric id, the rounded value, the freshness state, and the proof-consumer
    caveat. The unit and family stay inside the four-family Stage 2 contract
    (``status``).
    """
    conn = registered
    _ensure_source(conn)
    _record_height(conn, anchor=anchor_ts, value_cm=180.0)
    # 1 hour before the anchor — well within weight's P1W validity window.
    _insert_weight(conn, ts=anchor_ts - timedelta(hours=1), value=72.0)

    result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, StatusResult)
    assert result.metric_id == "bmi"
    assert result.signal_name == "bmi"
    assert result.unit == "kg_per_m2"
    assert result.freshness_state is FreshnessState.CURRENT
    assert result.value == pytest.approx(round(72.0 / (1.80**2), 2))
    assert any("proof consumer" in caveat.lower() for caveat in result.caveats)


# ---------------------------------------------------------------------------
# 2. Refusal — declared height missing (FR-005 scenario 2)
# ---------------------------------------------------------------------------


def test_bmi_refuses_when_declared_height_missing(registered: Any, anchor_ts: datetime) -> None:
    """No declared standing height -> :class:`MissingInputReport`.

    Weight is present and fresh; BMI must still refuse because the declared
    profile prerequisite is absent. There is no silent fallback into a
    measured-height observation.
    """
    conn = registered
    _ensure_source(conn)
    _insert_weight(conn, ts=anchor_ts - timedelta(hours=1), value=72.0)

    result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert result.tool_name == "bmi"
    assert "profile:standing_height_cm" in result.missing_inputs
    # Weight is present and fresh, so it must NOT appear in either bucket.
    assert "observation:weight" not in result.missing_inputs
    assert "observation:weight" not in result.stale_inputs


# ---------------------------------------------------------------------------
# 3. Refusal — weight missing (FR-005 scenario 3, missing variant)
# ---------------------------------------------------------------------------


def test_bmi_refuses_when_weight_missing(registered: Any, anchor_ts: datetime) -> None:
    """Declared height + no weight observation -> :class:`MissingInputReport`.

    The profile assertion is in place, but no weight row exists at all. The
    refusal must name weight as missing, not stale, and must not invent a
    value.
    """
    conn = registered
    _record_height(conn, anchor=anchor_ts, value_cm=180.0)

    result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert result.tool_name == "bmi"
    assert "observation:weight" in result.missing_inputs
    assert "profile:standing_height_cm" not in result.missing_inputs


# ---------------------------------------------------------------------------
# 4. Refusal — weight stale (FR-005 scenario 3, stale variant)
# ---------------------------------------------------------------------------


def test_bmi_refuses_when_weight_stale(registered: Any, anchor_ts: datetime) -> None:
    """Declared height + a 30-day-old weight (past P1W) -> stale refusal.

    The most-recent weight reading is outside the freshness window for the
    anchor; BMI must refuse and surface ``observation:weight`` in the stale
    bucket rather than silently reusing the old value as current.
    """
    conn = registered
    _ensure_source(conn)
    _record_height(conn, anchor=anchor_ts, value_cm=180.0)
    # 30 days old — well past weight's P1W validity window.
    _insert_weight(conn, ts=anchor_ts - timedelta(days=30), value=70.0)

    result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert result.tool_name == "bmi"
    assert "observation:weight" in result.stale_inputs
    assert "observation:weight" not in result.missing_inputs


# ---------------------------------------------------------------------------
# 5. Refusal — measured height must NOT satisfy declared profile dependency
# ---------------------------------------------------------------------------


def test_bmi_no_hidden_fallback_from_measured_height(registered: Any, anchor_ts: datetime) -> None:
    """A measured-height observation must not satisfy the declared dependency.

    A ``height`` observation row exists in the warehouse, and a fresh weight
    exists too. There is NO profile assertion for ``standing_height_cm``. BMI
    must still refuse with ``profile:standing_height_cm`` in
    ``missing_inputs`` — the no-hidden-fallback guarantee from FR-005.

    The message must not advertise an observation-shaped fallback path; the
    only honest fix is to set a declared profile height.
    """
    conn = registered
    _ensure_source(conn)
    _insert_weight(conn, ts=anchor_ts - timedelta(hours=1), value=72.0)
    # A measured height exists. BMI must not pick this up.
    _insert_measured_height(
        conn,
        ts=anchor_ts - timedelta(days=1),
        value=1.80,
    )

    result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert "profile:standing_height_cm" in result.missing_inputs
    # The honest-refusal message must not hint that an observation can take
    # the declared profile dependency's place.
    assert "observation" not in result.message.lower(), (
        "BMI refusal message implies an observation-shaped fallback is "
        "available; that contradicts the no-hidden-fallback contract."
    )


# ---------------------------------------------------------------------------
# 6. Refusal — both prerequisites missing => one combined report
# ---------------------------------------------------------------------------


def test_bmi_refuses_when_both_missing(registered: Any, anchor_ts: datetime) -> None:
    """No profile, no observation -> a single combined :class:`MissingInputReport`.

    The caller should see both unmet prerequisites in one refusal so they can
    fix everything at once rather than chasing one failure at a time.
    """
    conn = registered

    result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, MissingInputReport)
    assert "profile:standing_height_cm" in result.missing_inputs
    assert "observation:weight" in result.missing_inputs


# ---------------------------------------------------------------------------
# 7. BMI is actually in the engine registry (proves not dead code)
# ---------------------------------------------------------------------------


def test_bmi_is_registered_in_engine_registry(registered: Any) -> None:
    """BMI lands in ``REGISTRY`` via the built-in registration entrypoint.

    A signal that is never registered is dead code — the live ``compute()``
    path can never reach it. This test proves the WP03 registration actually
    happened.
    """
    assert "bmi" in REGISTRY
    assert REGISTRY["bmi"].fn is bmi
    assert REGISTRY["bmi"].family == "status"


# ---------------------------------------------------------------------------
# 8. BMI dispatches through the public compute() surface
# ---------------------------------------------------------------------------


def test_bmi_dispatches_through_compute(empty_warehouse: Any) -> None:
    """``compute("bmi", conn)`` returns a real :class:`StatusResult`.

    This is the cross-WP integration test: BMI must be reachable through the
    live engine API (not just through a direct import), proving the
    registration + lazy-loader chain wires it into production behavior.

    Uses the bare ``empty_warehouse`` fixture (not ``registered``) so the test
    exercises ``compute()`` lazy loading itself. Unlike the other BMI tests it
    calls ``compute("bmi", conn)`` with no anchor, so ``bmi`` falls back to
    ``datetime.now(UTC)`` for its freshness window — the seeded weight must
    therefore be anchored to real ``now`` (not the fixed ``anchor_ts`` fixture),
    or it ages out of the freshness window as wall-clock time advances.
    """
    conn = empty_warehouse
    _ensure_source(conn)
    now = datetime.now(tz=UTC)
    _record_height(conn, anchor=now, value_cm=180.0)
    _insert_weight(conn, ts=now - timedelta(hours=1), value=72.0)

    result = compute("bmi", conn)

    assert isinstance(result, StatusResult)
    assert result.metric_id == "bmi"
    assert result.value == pytest.approx(round(72.0 / (1.80**2), 2))


# ---------------------------------------------------------------------------
# 9. BMI calls the seam exactly twice and never bypasses it
# ---------------------------------------------------------------------------


def test_bmi_uses_resolver_seam_not_direct_warehouse_reads(
    registered: Any, anchor_ts: datetime
) -> None:
    """BMI must reach its inputs through ``resolve_dependency``, not by direct reads.

    The spy patches the module-level ``resolve_dependency`` symbol on
    ``premura.engine.descriptive_signals`` (the binding BMI actually uses) and
    forwards each call to the real seam so behavior stays unchanged. We then
    assert:

    * the seam was called exactly twice (one per declared dependency), and
    * the two ``depends_on_domain`` values are exactly the contracted pair
      (``profile_context`` + ``observation_history``).
    """
    conn = registered
    _ensure_source(conn)
    _record_height(conn, anchor=anchor_ts, value_cm=180.0)
    _insert_weight(conn, ts=anchor_ts - timedelta(hours=1), value=72.0)

    calls: list[ResolutionRequest] = []

    def spy(*, conn: Any, request: ResolutionRequest) -> ResolvedInput:
        calls.append(request)
        return resolve_dependency(conn, request)

    with patch(
        "premura.engine.descriptive_signals.resolve_dependency",
        side_effect=spy,
    ) as mock_resolve:
        result = bmi(conn, anchor_ts=anchor_ts)

    assert isinstance(result, StatusResult)
    assert mock_resolve.call_count == 2, (
        "BMI must resolve its two declared dependencies through the seam "
        "exactly once each; bypassing it is a contract violation."
    )

    seen_domains = sorted(req.dependency.depends_on_domain for req in calls)
    assert seen_domains == ["observation_history", "profile_context"]

    # And the keys must be the contracted pair, not opportunistic substitutes.
    seen_keys = sorted(req.dependency.required_key for req in calls)
    assert seen_keys == ["standing_height_cm", "weight"]


# ---------------------------------------------------------------------------
# 10. BMI is unaffected by unresolved intake-domain declarations (T013)
# ---------------------------------------------------------------------------


def test_bmi_unaffected_by_unresolved_intake_domains(registered: Any, anchor_ts: datetime) -> None:
    """Unresolved future domains do not leak into BMI's flow.

    Two things are proved in one targeted test:

    1. BMI succeeds normally on its declared profile + observation
       prerequisites, regardless of whether other declarations exist in the
       wider system. The proof consumer's behavior is determined by *its own*
       declared dependencies, not by what other declarations are floating
       around.
    2. A direct ``resolve_dependency`` call against ``nutrition_intake``
       refuses honestly without coercing into another domain. (Before the
       usable-intake-dimensions mission this asserted ``unsupported_domain``;
       FR-001 of that mission ships a real ``nutrition_intake`` resolver, so an
       empty warehouse now resolves to the honest ``missing`` outcome instead.
       Either way the seam never silently substitutes another domain's value —
       which is the invariant this point protects: declaring an intake
       dependency does not contaminate BMI's behavior.
    """
    conn = registered
    _ensure_source(conn)
    _record_height(conn, anchor=anchor_ts, value_cm=180.0)
    _insert_weight(conn, ts=anchor_ts - timedelta(hours=1), value=72.0)

    # 1. BMI works as normal — unresolved intake domains are not even
    #    consulted by BMI itself, because BMI does not declare them.
    result = bmi(conn, anchor_ts=anchor_ts)
    assert isinstance(result, StatusResult)
    assert result.metric_id == "bmi"

    # 2. Resolving a nutrition_intake dependency directly through the seam
    #    proves the outcome is honest (no nutrition rows seeded → missing), not
    #    silently coerced into another domain.
    nutrition_request = ResolutionRequest(
        anchor_ts=anchor_ts,
        dependency=DependencyDeclaration(
            consumer_name="future_nutrition_consumer",
            depends_on_domain="nutrition_intake",
            required_key="protein_g",
            failure_mode="explicit_missing_input",
        ),
    )
    nutrition_outcome = resolve_dependency(conn, nutrition_request)
    assert nutrition_outcome.usable is False
    assert nutrition_outcome.absence_reason == "missing"
