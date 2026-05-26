"""WP03 comparative Stage 2 signal tests.

Behavior is driven through the public engine surface: signals are registered via
``comparative_signals.register_builtin_signals()`` (the built-in registration
entrypoint) and then exercised either through ``engine.compute(...)`` or through
the module-level public functions. Assertions are on externally visible
result-envelope outputs (``to_dict()``) and their caveats, never on internal
helper functions. Fixtures are temporary DuckDB warehouses like the existing
engine tests.

Why the public functions for HRV: ``engine.compute`` only passes ``conn`` to a
signal, with no channel for a user-supplied anchor date. The public
``comparative_signals.hrv_change_around_date(conn, anchor_date)`` is the
user-facing call that accepts the anchor; ``engine.compute`` exercises the
default-anchor wrapper. Both are public engine interfaces — neither is an
internal helper.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from premura import engine
from premura.engine import comparative_signals
from premura.engine._results import ComparisonState, FreshnessState


@pytest.fixture()
def registered(empty_warehouse):
    """Warehouse with the WP03 comparative signals registered in REGISTRY.

    Snapshots and restores REGISTRY so registration does not leak across tests.
    """
    snapshot = dict(engine.REGISTRY)
    comparative_signals.register_builtin_signals()
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


# --------------------------------------------------------------------------- #
# Registration / reachability
# --------------------------------------------------------------------------- #
def test_signals_resolve_through_compute(registered) -> None:
    for name in ("sleep_deep_pct_baseline", "hrv_change_around_date"):
        assert name in engine.REGISTRY
    # Both resolve through compute (no KeyError) and return their envelopes.
    baseline = engine.compute("sleep_deep_pct_baseline", registered).to_dict()
    assert baseline["family"] == "baseline"
    change = engine.compute("hrv_change_around_date", registered).to_dict()
    assert change["family"] == "change"


# --------------------------------------------------------------------------- #
# T013 — sleep_deep_pct_baseline: successful own-baseline comparison
# --------------------------------------------------------------------------- #
def test_sleep_deep_pct_baseline_below_own_normal(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # A run of prior nights around 20% deep sleep, then a low latest night (12%).
    for i in range(8):
        ts = now - timedelta(days=8 - i)
        _add_measurement(
            conn, metric_id="sleep_deep_pct", ts=ts, value=20.0,
            unit="pct", source_id=src, key=f"deep-{i}",
        )
    _add_measurement(
        conn, metric_id="sleep_deep_pct", ts=now - timedelta(hours=6), value=12.0,
        unit="pct", source_id=src, key="deep-latest",
    )
    # Happy path: the public function returns a result that validates cleanly
    # with real numeric values present (state not unknown/unavailable).
    result = comparative_signals.sleep_deep_pct_baseline(conn)
    assert result.validate() is result
    assert result.latest_value == 12.0
    assert result.baseline_mean == pytest.approx(20.0)
    out = engine.compute("sleep_deep_pct_baseline", conn).to_dict()
    assert out["family"] == "baseline"
    assert out["latest_value"] == 12.0
    assert out["baseline_mean"] == pytest.approx(20.0)
    assert out["comparison_state"] == ComparisonState.BELOW.value
    assert out["freshness_state"] == FreshnessState.CURRENT.value
    # Caveat must frame this as a device estimate vs the user's OWN normal, and
    # must not imply a medical threshold.
    assert any(
        "device" in c.lower() and "own recent" in c.lower() for c in out["caveats"]
    )
    assert any("not a clinical" in c.lower() for c in out["caveats"])


def test_sleep_deep_pct_baseline_within_own_normal(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    for i in range(8):
        ts = now - timedelta(days=8 - i)
        _add_measurement(
            conn, metric_id="sleep_deep_pct", ts=ts, value=20.0,
            unit="pct", source_id=src, key=f"deep-{i}",
        )
    # Latest within the relative deadband of the baseline mean.
    _add_measurement(
        conn, metric_id="sleep_deep_pct", ts=now - timedelta(hours=6), value=20.5,
        unit="pct", source_id=src, key="deep-latest",
    )
    out = engine.compute("sleep_deep_pct_baseline", conn).to_dict()
    assert out["comparison_state"] == ComparisonState.WITHIN.value


# --------------------------------------------------------------------------- #
# T013 — sleep_deep_pct_baseline: insufficient data for a baseline
# --------------------------------------------------------------------------- #
def test_sleep_deep_pct_baseline_insufficient_prior_nights(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    # Only one prior night + the latest: too few to describe a baseline.
    _add_measurement(
        conn, metric_id="sleep_deep_pct", ts=now - timedelta(days=2), value=18.0,
        unit="pct", source_id=src, key="deep-prior",
    )
    _add_measurement(
        conn, metric_id="sleep_deep_pct", ts=now - timedelta(hours=6), value=12.0,
        unit="pct", source_id=src, key="deep-latest",
    )
    out = engine.compute("sleep_deep_pct_baseline", conn).to_dict()
    assert out["comparison_state"] == ComparisonState.UNKNOWN.value
    # No trustworthy baseline was formed: baseline_mean is honestly None, never
    # a fabricated 0.0. The latest value still exists (freshness is current).
    assert out["baseline_mean"] is None
    assert out["latest_value"] == 12.0
    assert any("too few" in c.lower() for c in out["caveats"])
    # Even with no comparison, the device-estimate framing is always present.
    assert any("device" in c.lower() for c in out["caveats"])


def test_sleep_deep_pct_baseline_no_value(registered) -> None:
    out = engine.compute("sleep_deep_pct_baseline", registered).to_dict()
    assert out["comparison_state"] == ComparisonState.UNKNOWN.value
    assert out["freshness_state"] == FreshnessState.UNAVAILABLE.value
    # No usable value exists: latest_value must be honestly None, NOT 0.0, so a
    # downstream consumer cannot render a false "0.0% vs 0.0%".
    assert out["latest_value"] is None
    assert out["baseline_mean"] is None
    assert out["caveats"]


# --------------------------------------------------------------------------- #
# T015 — hrv_change_around_date: successful before/after comparison
# --------------------------------------------------------------------------- #
def test_hrv_change_around_date_sufficient(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    anchor = date(2026, 3, 15)
    anchor_dt = datetime(2026, 3, 15, 12, 0, 0)
    # Five nights before the anchor around 50ms, five after around 40ms.
    for i in range(5):
        _add_measurement(
            conn, metric_id="hrv_rmssd_overnight",
            ts=anchor_dt - timedelta(days=i + 1), value=50.0,
            unit="ms", source_id=src, key=f"hrv-before-{i}",
        )
    for i in range(5):
        _add_measurement(
            conn, metric_id="hrv_rmssd_overnight",
            ts=anchor_dt + timedelta(days=i + 1), value=40.0,
            unit="ms", source_id=src, key=f"hrv-after-{i}",
        )
    out = comparative_signals.hrv_change_around_date(conn, anchor).to_dict()
    assert out["family"] == "change"
    assert out["anchor_date"] == anchor.isoformat()
    assert out["sufficient_data"] is True
    assert out["before_count"] == 5
    assert out["after_count"] == 5
    assert out["before_mean"] == pytest.approx(50.0)
    assert out["after_mean"] == pytest.approx(40.0)
    assert out["delta"] == pytest.approx(-10.0)
    # HARD BOUNDARY: no statistical machinery or positive causal claim. The
    # only allowed mention of significance/causation is the explicit disclaimer
    # that this is NOT a significance test and does NOT imply causation.
    blob = " ".join(out["caveats"]).lower()
    assert "p-value" not in blob and "p value" not in blob
    assert "confidence interval" not in blob
    # Any "significance" mention must be a disclaimer ("does not test ...").
    assert "significan" not in blob or "does not test statistical significance" in blob
    # Any "cause" mention must be a disclaimer ("does not ... caused ...").
    assert "cause" not in blob or "does not imply that anything on that date caused" in blob


# --------------------------------------------------------------------------- #
# T015 — hrv_change_around_date: insufficient windows around anchor
# --------------------------------------------------------------------------- #
def test_hrv_change_around_date_insufficient(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    anchor = date(2026, 3, 15)
    anchor_dt = datetime(2026, 3, 15, 12, 0, 0)
    # Plenty before, but only one reading after -> not enough to answer.
    for i in range(5):
        _add_measurement(
            conn, metric_id="hrv_rmssd_overnight",
            ts=anchor_dt - timedelta(days=i + 1), value=50.0,
            unit="ms", source_id=src, key=f"hrv-before-{i}",
        )
    _add_measurement(
        conn, metric_id="hrv_rmssd_overnight",
        ts=anchor_dt + timedelta(days=1), value=42.0,
        unit="ms", source_id=src, key="hrv-after-only",
    )
    out = comparative_signals.hrv_change_around_date(conn, anchor).to_dict()
    assert out["sufficient_data"] is False
    # delta MUST be None when insufficient (envelope validation enforces it).
    assert out["delta"] is None
    assert out["before_mean"] is None
    assert out["after_mean"] is None
    assert out["after_count"] == 1
    assert any("not enough" in c.lower() for c in out["caveats"])


def test_hrv_change_around_date_no_data(registered) -> None:
    out = comparative_signals.hrv_change_around_date(
        registered, date(2026, 3, 15)
    ).to_dict()
    assert out["sufficient_data"] is False
    assert out["before_count"] == 0
    assert out["after_count"] == 0
    assert out["delta"] is None


def test_hrv_change_around_date_default_anchor_via_compute(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    base = datetime(2026, 3, 1, 12, 0, 0)
    # A continuous span so the midpoint fallback anchor lands inside the data.
    for i in range(30):
        _add_measurement(
            conn, metric_id="hrv_rmssd_overnight",
            ts=base + timedelta(days=i), value=45.0 + (i % 3),
            unit="ms", source_id=src, key=f"hrv-{i}",
        )
    # Resolves through compute (no anchor channel) and returns a valid envelope.
    out = engine.compute("hrv_change_around_date", conn).to_dict()
    assert out["family"] == "change"
    assert out["anchor_date"] is not None


# --------------------------------------------------------------------------- #
# Caveat presence for BOTH functions (explicit cross-check)
# --------------------------------------------------------------------------- #
def test_both_signals_always_carry_caveats(registered) -> None:
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    for i in range(8):
        _add_measurement(
            conn, metric_id="sleep_deep_pct", ts=now - timedelta(days=8 - i),
            value=20.0, unit="pct", source_id=src, key=f"deep-{i}",
        )
    _add_measurement(
        conn, metric_id="sleep_deep_pct", ts=now - timedelta(hours=6), value=12.0,
        unit="pct", source_id=src, key="deep-latest",
    )
    baseline = engine.compute("sleep_deep_pct_baseline", conn).to_dict()
    assert baseline["caveats"], "baseline result must always carry caveats"

    anchor = date(2026, 3, 15)
    anchor_dt = datetime(2026, 3, 15, 12, 0, 0)
    for i in range(5):
        _add_measurement(
            conn, metric_id="hrv_rmssd_overnight",
            ts=anchor_dt - timedelta(days=i + 1), value=50.0,
            unit="ms", source_id=src, key=f"hrv-before-{i}",
        )
        _add_measurement(
            conn, metric_id="hrv_rmssd_overnight",
            ts=anchor_dt + timedelta(days=i + 1), value=40.0,
            unit="ms", source_id=src, key=f"hrv-after-{i}",
        )
    change = comparative_signals.hrv_change_around_date(conn, anchor).to_dict()
    assert change["caveats"], "change result must always carry caveats"
    # The disclaimer must be present even when the comparison succeeds.
    assert any("does not test statistical" in c.lower() for c in change["caveats"])
