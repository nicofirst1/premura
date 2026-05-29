"""WP05 — resting_hr_status policy-evaluator proof-integration tests.

This is the FIRST behavior-touching slice of the evidence-admissibility
mission. It proves one narrow thing: the existing ``resting_hr_status`` status
signal can hand its latest evidence to the new policy evaluator
(:func:`premura.engine.evaluate_evidence`) and *still* return the existing
:class:`StatusResult` envelope, unchanged in shape and freshness meaning, with
only additional policy-derived caveat context attached.

It is NOT a migration: trend signals and BMI keep their existing paths. The
regression tests at the bottom pin that scope down.

Fixture style is deliberately copied from
``tests/test_engine_descriptive_signals.py`` (temporary DuckDB warehouse, the
WP02 signals registered into ``REGISTRY`` via a snapshot/restore fixture, rows
inserted through tiny helpers, assertions on the externally visible
``to_dict()`` envelope). That file is intentionally NOT edited here — this WP
owns a separate test module to avoid ownership overlap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from premura import engine
from premura.engine import descriptive_signals
from premura.engine._results import FreshnessState, StatusResult, TrendDirection, TrendResult


@pytest.fixture()
def registered(empty_warehouse: Any) -> Any:
    """Warehouse with the WP02/WP03 descriptive signals registered in REGISTRY.

    Snapshots and restores REGISTRY so registration does not leak across tests.
    Mirrors ``tests/test_engine_descriptive_signals.py``.
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


def _ensure_source(conn: Any, source_id: str = "wearable:test") -> str:
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
    conn.execute(
        """
        INSERT INTO hp.fact_measurement (
            ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [ts, metric_id, value, unit, source_id, key, key],
    )


# Words that would betray the signal having strayed into diagnosis, reference
# ranges, population norms, or clinical/treatment advice. None of these belong
# in any caveat string produced by the proof integration.
_FORBIDDEN_SUBSTRINGS = (
    "diagnos",
    "normal range",
    "reference range",
    "population",
    "treatment",
    "medication",
    "emergency",
    "doctor",
    "physician",
    "disease",
    "abnormal",
    "p-value",
    "p value",
    "significant",
    "pubmed",
)


def _assert_no_clinical_language(caveats: list[str]) -> None:
    joined = " ".join(caveats).lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in joined, (
            f"caveat text must stay descriptive; found forbidden token {forbidden!r} in {caveats!r}"
        )


# --------------------------------------------------------------------------- #
# T020 — stale current-status evidence flows through the policy layer
# --------------------------------------------------------------------------- #
def test_resting_hr_status_uses_policy_for_stale_current_status_evidence(
    registered: Any,
) -> None:
    """A stale resting-HR current-status request consults the policy layer.

    The proof: the result REMAINS a ``StatusResult``, the stale value is NOT
    relabelled current, the existing freshness-window caveat survives, and an
    additional policy-derived caveat explaining why stale evidence cannot answer
    a present-tense question is visible — all without changing the envelope.
    """
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

    result = engine.compute("resting_hr_status", conn)
    assert isinstance(result, StatusResult)
    out = result.to_dict()

    # Result family/shape is preserved.
    assert out["family"] == "status"
    assert out["signal_name"] == "resting_hr_status"

    # Stale evidence is NOT presented as current; the value is retained but
    # explicitly flagged.
    assert out["freshness_state"] == FreshnessState.STALE.value
    assert out["value"] == 60.0

    # The existing freshness-window caveat survives (T022).
    assert any("older" in c.lower() for c in out["caveats"]), (
        "the original freshness-window caveat must be preserved"
    )

    # Policy-derived context is visible and explains the admissibility verdict
    # without becoming a different result family.
    assert any("policy" in c.lower() or "current status" in c.lower() for c in out["caveats"]), (
        "a policy-derived caveat must be present"
    )

    # The added context must stay descriptive, never clinical.
    _assert_no_clinical_language(out["caveats"])


# --------------------------------------------------------------------------- #
# T021/T022 — shape preserved, edge cases, current path still works
# --------------------------------------------------------------------------- #
def test_resting_hr_status_shape_is_preserved(registered: Any) -> None:
    """``StatusResult.to_dict()`` keeps exactly its documented keys."""
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
    result = engine.compute("resting_hr_status", conn)
    assert isinstance(result, StatusResult)
    out = result.to_dict()
    assert set(out.keys()) == {
        "family",
        "signal_name",
        "metric_id",
        "display_name",
        "unit",
        "value",
        "observed_at",
        "freshness_state",
        "validity_window",
        "caveats",
    }


def test_resting_hr_status_current_path_still_available(registered: Any) -> None:
    """A fresh reading still resolves as CURRENT with the live value retained.

    The policy handoff must not turn an admissible current reading into a
    refusal or a different family. (The resting-HR family is baseline-relative,
    so it may add standing context, but it must never override the freshness
    verdict or drop the value.)
    """
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
    result = engine.compute("resting_hr_status", conn)
    assert isinstance(result, StatusResult)
    out = result.to_dict()
    assert out["family"] == "status"
    assert out["freshness_state"] == FreshnessState.CURRENT.value
    assert out["value"] == 54.0
    assert out["unit"] == "bpm"
    assert out["observed_at"] is not None
    _assert_no_clinical_language(out["caveats"])


def test_resting_hr_status_no_metric_definition_still_unavailable(
    empty_warehouse: Any,
) -> None:
    """No metric definition -> UNAVAILABLE, no value, no policy crash.

    Uses the direct function entry point against a warehouse whose
    ``resting_hr`` row has been removed, so the metric-policy lookup returns
    None and the early-out path is exercised end to end.
    """
    conn = empty_warehouse
    conn.execute("DELETE FROM hp.dim_metric WHERE metric_id = 'resting_hr'")
    result = descriptive_signals.resting_hr_status(conn)
    out = result.to_dict()
    assert out["freshness_state"] == FreshnessState.UNAVAILABLE.value
    assert out["value"] is None
    assert out["observed_at"] is None
    assert out["caveats"]
    _assert_no_clinical_language(out["caveats"])


def test_resting_hr_status_no_observation_still_unavailable(
    registered: Any,
) -> None:
    """No resting-HR observation -> UNAVAILABLE behavior unchanged."""
    result = engine.compute("resting_hr_status", registered)
    assert isinstance(result, StatusResult)
    out = result.to_dict()
    assert out["freshness_state"] == FreshnessState.UNAVAILABLE.value
    assert out["value"] is None
    assert out["observed_at"] is None
    assert out["caveats"]
    _assert_no_clinical_language(out["caveats"])


def test_resting_hr_status_preserves_existing_caveat_and_adds_only_context(
    registered: Any,
) -> None:
    """Stale result keeps the freshness caveat AND adds (not replaces) context."""
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    _add_measurement(
        conn,
        metric_id="resting_hr",
        ts=now - timedelta(days=5),
        value=61.0,
        unit="bpm",
        source_id=src,
        key="rhr-stale2",
    )
    result = engine.compute("resting_hr_status", conn)
    assert isinstance(result, StatusResult)
    out = result.to_dict()
    caveats = out["caveats"]
    # The original freshness caveat is still there...
    assert any("older" in c.lower() for c in caveats)
    # ...AND a separate policy-derived caveat was appended (more than one entry).
    assert len(caveats) >= 2
    _assert_no_clinical_language(caveats)


# --------------------------------------------------------------------------- #
# T023 — regression: non-target signals are NOT migrated
# --------------------------------------------------------------------------- #
def test_trend_signals_not_migrated_by_proof_integration(registered: Any) -> None:
    """Trend signals still return ``TrendResult`` through their existing path."""
    conn = registered
    src = _ensure_source(conn)
    now = _now_naive()
    for i in range(14):
        ts = now - timedelta(days=13 - i)
        _add_measurement(
            conn,
            metric_id="resting_hr",
            ts=ts,
            value=50.0 + i,
            unit="bpm",
            source_id=src,
            key=f"rhr-trend-{i}",
        )
    result = engine.compute("resting_hr_trend", conn)
    assert isinstance(result, TrendResult)
    out = result.to_dict()
    # Still the trend family, still a direction verdict — the policy layer did
    # not change this path.
    assert out["family"] == "trend"
    assert out["trend_direction"] == TrendDirection.UP.value
    # No status-only / policy keys leaked into the trend envelope.
    assert "value" not in out
    assert "freshness_state" not in out


def test_bmi_behavior_not_changed_by_policy_proof(registered: Any) -> None:
    """BMI with no inputs still refuses via ``MissingInputReport``, unchanged.

    The proof integration touches only ``resting_hr_status``; BMI's
    cross-domain resolver-seam behavior must be untouched.

    Asserts on the serialized envelope (``family``) rather than ``isinstance``
    so the check is robust to the dataclass being reachable under both its
    private module path and the re-exported public name.
    """
    conn = registered
    result = descriptive_signals.bmi(conn)
    out = result.to_dict()
    assert out["family"] == "missing_input"
    assert out["missing_inputs"]  # at least one prerequisite named as missing
