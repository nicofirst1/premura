"""WP02 descriptive Stage 2 signal tests.

Behavior is driven through the public engine surface: signals are registered via
``descriptive_signals.register_builtin_signals()`` (the built-in registration
entrypoint) and then invoked through ``engine.compute(...)``. Assertions are on
externally visible result-envelope outputs (``to_dict()``), not on internal
helper behavior. Fixtures are temporary DuckDB warehouses like the existing
engine tests.

NOTE: ``descriptive_signals`` is not yet in ``engine._BUILTIN_SIGNAL_MODULES``
(that static list lives in WP01-owned ``__init__.py``). Registering explicitly
here both isolates these tests and proves the signals resolve through
``engine.compute`` once registered. See the WP02 report for the one-line
integration follow-up.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from premura import engine
from premura.engine import descriptive_signals
from premura.engine._results import FreshnessState, TrendDirection


@pytest.fixture()
def registered(empty_warehouse):
    """Warehouse with the WP02 descriptive signals registered in REGISTRY.

    Snapshots and restores REGISTRY so registration does not leak across tests.
    """
    snapshot = dict(engine.REGISTRY)
    descriptive_signals.register_builtin_signals()
    try:
        yield empty_warehouse
    finally:
        engine.REGISTRY.clear()
        engine.REGISTRY.update(snapshot)


def _now_naive() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _ensure_source(conn, source_id: str = "wearable:test") -> str:
    conn.execute(
        """
        INSERT INTO hp.dim_source (source_id, source_kind, first_seen, last_seen)
        VALUES (?, 'wearable', now(), now())
        ON CONFLICT (source_id) DO NOTHING
        """,
        [source_id],
    )
    return source_id


def _add_measurement(conn, *, metric_id, ts, value, unit, source_id, key) -> None:
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [ts, metric_id, value, unit, source_id, key, key],
    )


def _add_interval(conn, *, metric_id, start, end, value, source_id, key) -> None:
    conn.execute(
        """
        INSERT INTO hp.fact_interval (
            metric_id, start_utc, end_utc, value_num,
            source_id, source_uuid, dedupe_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [metric_id, start, end, value, source_id, key, key],
    )


# --------------------------------------------------------------------------- #
# Registration / reachability
# --------------------------------------------------------------------------- #
def test_signals_resolve_through_compute(registered) -> None:
    for name in ("resting_hr_status", "resting_hr_trend", "steps_trend", "weight_trend"):
        assert name in engine.REGISTRY
    # compute resolves the registered signal (no KeyError) and returns an envelope.
    result = engine.compute("resting_hr_status", registered)
    assert result.to_dict()["family"] == "status"


# --------------------------------------------------------------------------- #
# T007 — resting_hr_status: current / stale / no value
# --------------------------------------------------------------------------- #
def test_resting_hr_status_current(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    _add_measurement(
        conn,
        metric_id="resting_hr",
        ts=now - timedelta(hours=2),
        value=54.0,
        unit="bpm",
        source_id=src,
        key="rhr-fresh",
    )
    out = engine.compute("resting_hr_status", conn).to_dict()
    assert out["freshness_state"] == FreshnessState.CURRENT.value
    assert out["value"] == 54.0
    assert out["unit"] == "bpm"
    assert out["observed_at"] is not None
    assert out["caveats"] == []


def test_resting_hr_status_stale_not_presented_as_current(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # resting_hr validity_window is P1D; 5 days old is stale.
    _add_measurement(
        conn,
        metric_id="resting_hr",
        ts=now - timedelta(days=5),
        value=60.0,
        unit="bpm",
        source_id=src,
        key="rhr-stale",
    )
    out = engine.compute("resting_hr_status", conn).to_dict()
    assert out["freshness_state"] == FreshnessState.STALE.value
    # Value still returned, but explicitly flagged — never relabeled current.
    assert out["value"] == 60.0
    assert out["caveats"], "stale status must carry a caveat"
    assert any("older" in c.lower() for c in out["caveats"])


def test_resting_hr_status_no_value(registered) -> None:
    out = engine.compute("resting_hr_status", registered).to_dict()
    assert out["freshness_state"] == FreshnessState.UNAVAILABLE.value
    assert out["value"] is None
    assert out["observed_at"] is None
    assert out["caveats"]


# --------------------------------------------------------------------------- #
# T008 — resting_hr_trend: clear / sparse / insufficient
# --------------------------------------------------------------------------- #
def test_resting_hr_trend_clear_direction(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # Daily readings climbing from 50 -> 60 over recent weeks.
    for i in range(14):
        ts = now - timedelta(days=13 - i)
        _add_measurement(
            conn,
            metric_id="resting_hr",
            ts=ts,
            value=50.0 + i,
            unit="bpm",
            source_id=src,
            key=f"rhr-{i}",
        )
    out = engine.compute("resting_hr_trend", conn).to_dict()
    assert out["family"] == "trend"
    assert out["trend_direction"] == TrendDirection.UP.value
    assert out["current_freshness_state"] == FreshnessState.CURRENT.value
    # 14 consecutive daily readings -> the window is dominated by observed
    # points. (A daily cadence may produce at most one carry-forward at a bucket
    # boundary; it must never invent a dense imputed series.)
    observed = [p for p in out["points"] if not p["is_imputed"]]
    assert len(observed) >= 14
    assert out["imputed_point_count"] <= 1


def test_resting_hr_trend_sparse_shows_carried_forward(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # Two readings a few days apart; LOCF fills the gap within the P1D window
    # only one day forward, so we still expect visible carried-forward + gaps.
    _add_measurement(
        conn,
        metric_id="resting_hr",
        ts=now - timedelta(days=10),
        value=55.0,
        unit="bpm",
        source_id=src,
        key="rhr-a",
    )
    _add_measurement(
        conn,
        metric_id="resting_hr",
        ts=now - timedelta(days=1),
        value=56.0,
        unit="bpm",
        source_id=src,
        key="rhr-b",
    )
    out = engine.compute("resting_hr_trend", conn).to_dict()
    # Only two observed points -> not enough to claim a direction.
    assert out["trend_direction"] == TrendDirection.UNKNOWN.value
    # Carried-forward points appear and are flagged imputed.
    assert out["imputed_point_count"] >= 1
    assert any(p["is_imputed"] for p in out["points"])
    # Gaps beyond the freshness window are visible, not silently filled.
    assert out["gap_count"] > 0
    assert out["caveats"]


def test_resting_hr_trend_insufficient_data(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    _add_measurement(
        conn,
        metric_id="resting_hr",
        ts=now - timedelta(days=1),
        value=58.0,
        unit="bpm",
        source_id=src,
        key="rhr-only",
    )
    out = engine.compute("resting_hr_trend", conn).to_dict()
    assert out["trend_direction"] == TrendDirection.UNKNOWN.value
    assert any("enough" in c.lower() for c in out["caveats"])


# --------------------------------------------------------------------------- #
# T009 — steps_trend: gaps stay gaps, NEVER imputed
# --------------------------------------------------------------------------- #
def test_steps_trend_gaps_stay_gaps(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # Steps recorded only on a handful of days, leaving holes in between.
    recorded_days = [0, 1, 2, 7, 8]  # days ago
    for i, days_ago in enumerate(recorded_days):
        end = now - timedelta(days=days_ago)
        start = end - timedelta(hours=23)
        _add_interval(
            conn,
            metric_id="steps",
            start=start,
            end=end,
            value=8000.0 + i * 10,
            source_id=src,
            key=f"steps-{i}",
        )
    out = engine.compute("steps_trend", conn).to_dict()
    assert out["family"] == "trend"
    # steps has missing_data_policy: none -> ZERO imputed points, ever.
    assert out["imputed_point_count"] == 0
    assert all(p["is_imputed"] is False for p in out["points"])
    # Missing days are visible as gaps, not invented continuity.
    assert out["gap_count"] > 0
    # Number of observed points equals number of recorded days.
    assert len(out["points"]) == len(recorded_days)


def test_steps_trend_no_data(registered) -> None:
    out = engine.compute("steps_trend", registered).to_dict()
    assert out["trend_direction"] == TrendDirection.UNKNOWN.value
    assert out["imputed_point_count"] == 0
    assert out["points"] == []


# --------------------------------------------------------------------------- #
# T010 — weight_trend: carried-forward flagged, stale not misreported
# --------------------------------------------------------------------------- #
def test_weight_trend_carried_forward_flagged(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # Weekly-ish weigh-ins; weight validity_window is P1W, so in-between days
    # carry forward and are flagged. Trend down 80 -> 78.
    _add_measurement(
        conn,
        metric_id="weight",
        ts=now - timedelta(days=14),
        value=80.0,
        unit="kg",
        source_id=src,
        key="wt-a",
    )
    _add_measurement(
        conn,
        metric_id="weight",
        ts=now - timedelta(days=7),
        value=79.0,
        unit="kg",
        source_id=src,
        key="wt-b",
    )
    _add_measurement(
        conn,
        metric_id="weight",
        ts=now - timedelta(days=1),
        value=78.0,
        unit="kg",
        source_id=src,
        key="wt-c",
    )
    out = engine.compute("weight_trend", conn).to_dict()
    assert out["family"] == "trend"
    assert out["trend_direction"] == TrendDirection.DOWN.value
    assert out["current_freshness_state"] == FreshnessState.CURRENT.value
    # In-between days carried forward within the P1W window, flagged imputed.
    assert out["imputed_point_count"] >= 1
    assert any(p["is_imputed"] for p in out["points"])
    assert any("carried forward" in c.lower() for c in out["caveats"])


def test_weight_trend_stale_not_misreported_as_current(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # Single weigh-in well outside the P1W window -> latest point is stale and
    # must NOT be carried forward across the whole window as if current.
    _add_measurement(
        conn,
        metric_id="weight",
        ts=now - timedelta(days=20),
        value=82.0,
        unit="kg",
        source_id=src,
        key="wt-stale",
    )
    out = engine.compute("weight_trend", conn).to_dict()
    assert out["current_freshness_state"] == FreshnessState.STALE.value
    # The reading is older than P1W, so recent days are gaps, not carried-forward.
    assert out["gap_count"] > 0
    assert out["caveats"]
    # Direction can't be claimed from a single stale point.
    assert out["trend_direction"] == TrendDirection.UNKNOWN.value
