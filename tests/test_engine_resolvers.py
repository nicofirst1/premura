"""Behavioral tests for the WP02 concrete resolvers.

Every test drives behavior through the public engine seam
(``from premura.engine import resolve_dependency``) — there are *no* imports of
``premura.engine.views.observation`` or ``premura.engine.views.profile``. The
lazy loader inside :func:`premura.engine.resolve_dependency` is what binds the
``observation_history`` and ``profile_context`` resolvers to those modules, and
these tests prove the binding works end-to-end.

What is locked here:

1. Observation resolution honors the metric's ``validity_window`` against the
   declared ``anchor_ts``: same data is ``current`` at one anchor and ``stale``
   at another.
2. Profile resolution uses *as-of* semantics, never "latest row wins."
3. There is **no hidden fallback**: a declared profile dependency is never
   satisfied by an observation row, even when the keys happen to look related.
4. The two domains are isolated: same key, same anchor, different
   ``depends_on_domain`` produces different outcomes.
5. Resolvers register lazily — importing ``premura.engine`` does not import
   either resolver module.
"""
from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

# NOTE: ``premura.engine`` is intentionally NOT imported at module top. Other
# tests in the suite (e.g. ``test_engine_contract.py``) purge
# ``premura.engine*`` from ``sys.modules`` and re-import to simulate a fresh
# process; a module-level binding here would capture the pre-purge functions
# and look up ``RESOLVERS`` in a stale module object after that purge runs.
# Each test re-imports through :func:`_engine` so the public surface always
# resolves against the currently-active ``premura.engine`` module.


def _engine() -> Any:
    """Return the current ``premura.engine`` module.

    Always re-fetched per call so the resolver tests survive sibling tests
    that purge ``premura.engine*`` from ``sys.modules``.
    """
    import premura.engine as engine_pkg

    return engine_pkg


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def anchor_ts() -> datetime:
    """A fixed timezone-aware anchor used across the resolver tests."""
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


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


def _add_measurement(
    conn: Any,
    *,
    metric_id: str,
    ts: datetime,
    value: float,
    unit: str,
    source_id: str,
    key: str,
) -> None:
    """Insert a single observation row (naive UTC, matching warehouse storage)."""
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [ts, metric_id, value, unit, source_id, key, key],
    )


def _add_profile_assertion(
    conn: Any,
    *,
    attribute_key: str,
    value_num: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    effective_start_utc: datetime,
    effective_end_utc: datetime | None = None,
    source_kind: str = "agent_profile_capture",
) -> None:
    """Insert one profile_context_assertion row directly.

    Bypasses :mod:`premura.store.profile_intake` so tests can construct
    historical/closed assertions a normal capture session would not produce.
    """
    conn.execute(
        """
        INSERT INTO hp.profile_context_assertion
            (attribute_key, value_text, value_num, value_date, unit,
             effective_start_utc, effective_end_utc, source_kind)
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        [
            attribute_key,
            value_text,
            value_num,
            unit,
            effective_start_utc,
            effective_end_utc,
            source_kind,
        ],
    )


def _naive(ts: datetime) -> datetime:
    """Strip tzinfo so the value lands in DuckDB as the same naive-UTC instant."""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


def _observation_dep(metric_id: str, consumer: str = "test_consumer") -> Any:
    return _engine().DependencyDeclaration(
        consumer_name=consumer,
        depends_on_domain="observation_history",
        required_key=metric_id,
        failure_mode="refuse",
    )


def _profile_dep(attribute_key: str, consumer: str = "test_consumer") -> Any:
    return _engine().DependencyDeclaration(
        consumer_name=consumer,
        depends_on_domain="profile_context",
        required_key=attribute_key,
        failure_mode="refuse",
    )


def _request(anchor_ts: datetime, dependency: Any) -> Any:
    return _engine().ResolutionRequest(anchor_ts=anchor_ts, dependency=dependency)


def _resolve(conn: Any, request: Any) -> Any:
    return _engine().resolve_dependency(conn, request)


def _freshness() -> Any:
    """Return the currently-active :class:`FreshnessState` enum."""
    from premura.engine._results import FreshnessState

    return FreshnessState


# ---------------------------------------------------------------------------
# 1. Observation resolver — current
# ---------------------------------------------------------------------------


def test_observation_current_value_resolves_usable(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A fresh ``weight`` observation within the P1W validity window resolves usable."""
    conn = empty_warehouse
    src = _ensure_source(conn)
    # 1 hour before the anchor — well within weight's P1W validity window.
    observed_at = _naive(anchor_ts) - timedelta(hours=1)
    _add_measurement(
        conn,
        metric_id="weight",
        ts=observed_at,
        value=72.5,
        unit="kg",
        source_id=src,
        key="weight-current",
    )

    out = _resolve(conn, _request(anchor_ts, _observation_dep("weight")))

    assert out.usable is True
    assert out.domain == "observation_history"
    assert out.required_key == "weight"
    assert out.absence_reason is None
    assert out.payload is not None
    assert out.payload["resolved_value"] == pytest.approx(72.5)
    assert out.payload["freshness_state"] == _freshness().CURRENT.value
    assert out.payload["unit"] == "kg"
    assert out.payload["observed_at"] == observed_at


# ---------------------------------------------------------------------------
# 2. Observation resolver — stale
# ---------------------------------------------------------------------------


def test_observation_stale_value_refuses_with_observed_payload(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A weight measurement older than P1W resolves as ``stale``, not silently reused."""
    conn = empty_warehouse
    src = _ensure_source(conn)
    # 30 days old — well past weight's P1W validity window.
    observed_at = _naive(anchor_ts) - timedelta(days=30)
    _add_measurement(
        conn,
        metric_id="weight",
        ts=observed_at,
        value=70.0,
        unit="kg",
        source_id=src,
        key="weight-stale",
    )

    out = _resolve(conn, _request(anchor_ts, _observation_dep("weight")))

    assert out.usable is False
    assert out.absence_reason == "stale"
    # The observed value is still surfaced so callers can inspect what was found.
    assert out.payload is not None
    assert out.payload["resolved_value"] == pytest.approx(70.0)
    assert out.payload["freshness_state"] == _freshness().STALE.value
    assert out.message is not None and "weight" in out.message


# ---------------------------------------------------------------------------
# 3. Observation resolver — missing
# ---------------------------------------------------------------------------


def test_observation_missing_value_resolves_missing(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """No observation rows -> ``absence_reason='missing'``."""
    conn = empty_warehouse

    out = _resolve(conn, _request(anchor_ts, _observation_dep("weight")))

    assert out.usable is False
    assert out.absence_reason == "missing"
    assert out.payload is not None
    assert out.payload["freshness_state"] == _freshness().UNAVAILABLE.value


# ---------------------------------------------------------------------------
# 4. Observation resolver — unknown metric
# ---------------------------------------------------------------------------


def test_observation_unknown_metric_refuses_explicitly(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """An unregistered metric_id yields ``unknown_metric``, not a crash."""
    conn = empty_warehouse

    out = _resolve(conn, _request(anchor_ts, _observation_dep("not_a_real_metric")))

    assert out.usable is False
    assert out.absence_reason == "unknown_metric"
    assert out.message is not None and "not_a_real_metric" in out.message


# ---------------------------------------------------------------------------
# 5. Profile resolver — valid as-of
# ---------------------------------------------------------------------------


def test_profile_valid_as_of_anchor_resolves_usable(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A standing-height assertion effective at the anchor resolves usable."""
    conn = empty_warehouse
    started_at = _naive(anchor_ts) - timedelta(days=30)
    _add_profile_assertion(
        conn,
        attribute_key="standing_height_cm",
        value_num=180.0,
        unit="cm",
        effective_start_utc=started_at,
        effective_end_utc=None,
    )

    out = _resolve(conn, _request(anchor_ts, _profile_dep("standing_height_cm")))

    assert out.usable is True
    assert out.domain == "profile_context"
    assert out.required_key == "standing_height_cm"
    assert out.payload is not None
    assert out.payload["resolved_value"] == pytest.approx(180.0)
    assert out.payload["unit"] == "cm"
    assert out.payload["effective_start_utc"] == started_at
    assert out.payload["effective_end_utc"] is None
    assert out.payload["source_kind"] == "agent_profile_capture"


# ---------------------------------------------------------------------------
# 6. Profile resolver — as-of picks the row valid at anchor, not "latest row"
# ---------------------------------------------------------------------------


def test_profile_as_of_picks_the_assertion_valid_at_anchor(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """Two historical assertions: the resolver chooses by anchor time, not recency.

    This is the structural difference between "latest open row" and
    "latest valid as-of": at ``anchor - 45 days`` the older assertion was still
    valid even though a newer one exists in the table.
    """
    conn = empty_warehouse
    anchor_naive = _naive(anchor_ts)
    # Assertion A: valid from anchor-60d to anchor-30d, value 170.
    a_start = anchor_naive - timedelta(days=60)
    a_end = anchor_naive - timedelta(days=30)
    _add_profile_assertion(
        conn,
        attribute_key="standing_height_cm",
        value_num=170.0,
        unit="cm",
        effective_start_utc=a_start,
        effective_end_utc=a_end,
    )
    # Assertion B: valid from anchor-30d onwards, value 180 (still open).
    _add_profile_assertion(
        conn,
        attribute_key="standing_height_cm",
        value_num=180.0,
        unit="cm",
        effective_start_utc=a_end,
        effective_end_utc=None,
    )

    # At the anchor, assertion B is the valid row.
    out_now = _resolve(conn, _request(anchor_ts, _profile_dep("standing_height_cm")))
    assert out_now.usable is True
    assert out_now.payload is not None
    assert out_now.payload["resolved_value"] == pytest.approx(180.0)

    # At anchor - 45 days, assertion A was the valid row — even though
    # assertion B exists in the table and is "newer."
    earlier_anchor = anchor_ts - timedelta(days=45)
    out_earlier = _resolve(
        conn, _request(earlier_anchor, _profile_dep("standing_height_cm"))
    )
    assert out_earlier.usable is True
    assert out_earlier.payload is not None
    assert out_earlier.payload["resolved_value"] == pytest.approx(170.0)


# ---------------------------------------------------------------------------
# 7. Profile resolver — missing
# ---------------------------------------------------------------------------


def test_profile_missing_attribute_resolves_missing(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """No assertion -> ``absence_reason='missing'``."""
    conn = empty_warehouse

    out = _resolve(conn, _request(anchor_ts, _profile_dep("standing_height_cm")))

    assert out.usable is False
    assert out.absence_reason == "missing"
    assert out.payload is None
    assert out.message is not None and "standing_height_cm" in out.message


# ---------------------------------------------------------------------------
# 8. NO HIDDEN FALLBACK (T009) — the central no-substitution guarantee
# ---------------------------------------------------------------------------


def test_profile_dependency_is_not_satisfied_by_an_observation_row(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A measured ``height`` observation must NOT satisfy a declared
    ``standing_height_cm`` profile dependency.

    This is the central no-hidden-fallback guarantee of the input-resolution
    seam. The profile resolver must consult ``hp.profile_context_assertion``
    only, never ``hp.fact_measurement``. If a future implementation ever
    "helpfully" reaches into observation history to fill a missing profile
    attribute, this test fails.
    """
    conn = empty_warehouse
    src = _ensure_source(conn)
    # A measured height exists in the observation history.
    _add_measurement(
        conn,
        metric_id="height",
        ts=_naive(anchor_ts) - timedelta(days=1),
        value=1.80,
        unit="m",
        source_id=src,
        key="height-measured",
    )
    # But there is NO profile assertion for ``standing_height_cm``.

    out = _resolve(conn, _request(anchor_ts, _profile_dep("standing_height_cm")))

    assert out.usable is False
    assert out.absence_reason == "missing", (
        "Profile resolver silently substituted an observation row — the "
        "no-hidden-fallback contract is broken."
    )
    assert out.payload is None


# ---------------------------------------------------------------------------
# 9. Cross-domain isolation
# ---------------------------------------------------------------------------


def test_observation_and_profile_domains_resolve_independently(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """Same warehouse, two different domains, two different outcomes.

    A weight observation exists but no profile assertion does. A
    ``observation_history`` request for ``weight`` is usable; a
    ``profile_context`` request for ``standing_height_cm`` (the closest
    analogue in the profile allowlist) is missing. The keys differ because
    the warehouse intentionally separates metric_ids from profile attribute
    keys — the test still demonstrates the central isolation rule: each
    domain consults only its own storage.
    """
    conn = empty_warehouse
    src = _ensure_source(conn)
    _add_measurement(
        conn,
        metric_id="weight",
        ts=_naive(anchor_ts) - timedelta(hours=1),
        value=70.0,
        unit="kg",
        source_id=src,
        key="weight-isolated",
    )

    obs_out = _resolve(conn, _request(anchor_ts, _observation_dep("weight")))
    profile_out = _resolve(
        conn, _request(anchor_ts, _profile_dep("standing_height_cm"))
    )

    assert obs_out.usable is True
    assert profile_out.usable is False
    assert profile_out.absence_reason == "missing"


# ---------------------------------------------------------------------------
# 10. Anchor-time honesty for observation
# ---------------------------------------------------------------------------


def test_observation_freshness_honors_anchor_ts_not_wallclock(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """Same observation: ``stale`` at one anchor, ``current`` at an earlier one.

    Proves the resolver actually uses ``request.anchor_ts`` instead of
    silently substituting ``datetime.now()``. With ``weight`` (validity_window
    P1W), an observation at anchor-30d is stale at the anchor and current at
    anchor-29d.
    """
    conn = empty_warehouse
    src = _ensure_source(conn)
    observed_at = _naive(anchor_ts) - timedelta(days=30)
    _add_measurement(
        conn,
        metric_id="weight",
        ts=observed_at,
        value=70.0,
        unit="kg",
        source_id=src,
        key="weight-anchor-honesty",
    )

    # At the anchor, 30 days old is stale.
    stale_out = _resolve(conn, _request(anchor_ts, _observation_dep("weight")))
    assert stale_out.usable is False
    assert stale_out.absence_reason == "stale"

    # Roll the anchor back to (observed_at + 1 day); the same observation is
    # 1 day old — well within weight's P1W window.
    earlier_anchor = anchor_ts - timedelta(days=29)
    current_out = _resolve(
        conn, _request(earlier_anchor, _observation_dep("weight"))
    )
    assert current_out.usable is True
    assert current_out.payload is not None
    assert current_out.payload["freshness_state"] == _freshness().CURRENT.value


# ---------------------------------------------------------------------------
# 11. Resolvers are loaded lazily — ``views.*`` not imported until first call
# ---------------------------------------------------------------------------


@pytest.fixture
def _purged_view_modules() -> Iterator[None]:
    """Force a fresh lazy load so the in-process module cache does not lie.

    Other tests in the suite drive ``resolve_dependency`` first; once that
    happens, ``premura.engine.views.observation`` is permanently in
    ``sys.modules`` for the rest of the test run. To prove the loader is
    *lazy*, this fixture pops the cached modules and flips
    ``_RESOLVERS_LOADED`` back to ``False``, then restores everything
    afterwards so sibling tests still see the loaded state.
    """
    engine_pkg = _engine()

    saved_flag = engine_pkg._RESOLVERS_LOADED
    saved_modules = {
        name: sys.modules.get(name)
        for name in (
            "premura.engine.views.observation",
            "premura.engine.views.profile",
        )
    }
    saved_resolvers = dict(engine_pkg.RESOLVERS)

    for name in saved_modules:
        sys.modules.pop(name, None)
    engine_pkg._RESOLVERS_LOADED = False
    # Clear any registry entries the soon-to-be-purged modules contributed; the
    # next resolve_dependency call should re-import the modules and re-register.
    engine_pkg.RESOLVERS.pop("observation_history", None)
    engine_pkg.RESOLVERS.pop("profile_context", None)

    try:
        yield
    finally:
        engine_pkg._RESOLVERS_LOADED = saved_flag
        for name, module in saved_modules.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)
        engine_pkg.RESOLVERS.clear()
        engine_pkg.RESOLVERS.update(saved_resolvers)


def test_view_resolver_modules_are_lazily_loaded(
    empty_warehouse: Any,
    anchor_ts: datetime,
    _purged_view_modules: None,
) -> None:
    """Before the first ``resolve_dependency`` call the resolver modules are
    not imported; after the first call they are.

    This is the lazy-loader contract the public engine surface promises. It
    matters because eager import would force every dependency these modules
    transitively bring in (currently small, but the doctrine is what we are
    locking) to be paid by every consumer that touches ``premura.engine``.
    """
    assert "premura.engine.views.observation" not in sys.modules
    assert "premura.engine.views.profile" not in sys.modules

    # First call triggers the lazy loader.
    _resolve(empty_warehouse, _request(anchor_ts, _observation_dep("weight")))

    assert "premura.engine.views.observation" in sys.modules
    assert "premura.engine.views.profile" in sys.modules
