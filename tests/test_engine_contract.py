"""Seam tests for the Stage 2 engine contributor contract (WP01).

These lock the extension surface before signal implementation begins. They
assert through public imports and observable behavior, not future signal
behavior.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date, datetime
from importlib.resources import files

import pytest

# --- T001: additive registry metadata contract ---------------------------


def test_signal_spec_exposes_optional_stage2_metadata_with_safe_defaults() -> None:
    from premura.engine import SignalSpec

    spec = SignalSpec(name="x", domain=["d"], inputs=["lab:x"])
    assert spec.question is None
    assert spec.family is None
    assert spec.missing_input_hint is None
    assert spec.caveat_summary == ()


def test_signal_decorator_records_new_metadata() -> None:
    from premura.engine import REGISTRY, signal

    name = "_seam_meta_signal"

    @signal(
        name=name,
        domain=["test"],
        inputs=["lab:x"],
        question="What is X right now?",
        family="status",
        missing_input_hint="Add a source that records X.",
        caveat_summary=["X is a vendor estimate."],
    )
    def _fn(conn):  # noqa: ANN001
        return []

    try:
        spec = REGISTRY[name]
        assert spec.question == "What is X right now?"
        assert spec.family == "status"
        assert spec.missing_input_hint == "Add a source that records X."
        assert spec.caveat_summary == ("X is a vendor estimate.",)
    finally:
        REGISTRY.pop(name, None)


def test_signal_decorator_rejects_unknown_family() -> None:
    from premura.engine import RESULT_FAMILIES, signal

    assert RESULT_FAMILIES == frozenset({"status", "trend", "baseline", "change"})

    with pytest.raises(ValueError, match="family"):
        signal(name="_bad", domain=["t"], inputs=[], family="bogus")


def test_existing_lab_ratio_registrations_stay_valid_without_new_metadata() -> None:
    from premura.engine import REGISTRY, list_auto_safe

    # Trigger lazy load via a public helper.
    auto_safe = {spec.name for spec in list_auto_safe()}
    assert {"ast_alt_ratio", "ldl_hdl_ratio", "tg_hdl_ratio"} <= auto_safe

    ratio = REGISTRY["ast_alt_ratio"]
    # Core contract intact.
    assert ratio.output == "derived:ast_alt_ratio"
    assert ratio.priority == "high"
    # Additive metadata left at defaults — no churn.
    assert ratio.family is None
    assert ratio.caveat_summary == ()


# --- T002: result-helper surface is importable and serializable -----------


def test_result_envelopes_importable_from_public_engine_surface() -> None:
    import premura.engine as engine

    for symbol in (
        "FreshnessState",
        "TrendDirection",
        "ComparisonState",
        "StatusResult",
        "TrendPoint",
        "TrendResult",
        "BaselineComparisonResult",
        "ChangeAroundDateResult",
        "MissingInputReport",
    ):
        assert symbol in engine.__all__
        assert hasattr(engine, symbol)


def test_status_result_serializes_and_validates() -> None:
    from premura.engine import FreshnessState, StatusResult

    ok = StatusResult(
        signal_name="resting_hr_status",
        metric_id="resting_heart_rate",
        display_name="Resting heart rate",
        unit="bpm",
        value=58.0,
        observed_at=datetime(2026, 5, 1, 7, 0, 0),
        freshness_state=FreshnessState.CURRENT,
        validity_window="P2D",
        caveats=["vendor estimate"],
    ).validate()
    d = ok.to_dict()
    assert d["family"] == "status"
    assert d["value"] == 58.0
    assert d["freshness_state"] == "current"
    assert d["observed_at"] == "2026-05-01T07:00:00"

    with pytest.raises(ValueError, match="unavailable"):
        StatusResult(
            signal_name="s",
            metric_id="m",
            display_name="M",
            unit="bpm",
            value=58.0,
            freshness_state=FreshnessState.UNAVAILABLE,
            validity_window="P2D",
        ).validate()


def test_trend_result_orders_points_and_serializes() -> None:
    from premura.engine import FreshnessState, TrendDirection, TrendPoint, TrendResult

    pts = [
        TrendPoint(ts=datetime(2026, 5, 1), value=10.0),
        TrendPoint(ts=datetime(2026, 5, 2), value=11.0, is_imputed=True),
    ]
    res = TrendResult(
        signal_name="steps_trend",
        metric_id="steps",
        window_start=datetime(2026, 5, 1),
        window_end=datetime(2026, 5, 2),
        trend_direction=TrendDirection.UP,
        current_freshness_state=FreshnessState.CURRENT,
        points=pts,
        imputed_point_count=1,
        gap_count=0,
    ).validate()
    d = res.to_dict()
    assert d["family"] == "trend"
    assert d["trend_direction"] == "up"
    assert len(d["points"]) == 2
    assert d["points"][1]["is_imputed"] is True

    with pytest.raises(ValueError, match="time-ordered"):
        TrendResult(
            signal_name="s",
            metric_id="m",
            window_start=datetime(2026, 5, 1),
            window_end=datetime(2026, 5, 2),
            trend_direction=TrendDirection.UNKNOWN,
            current_freshness_state=FreshnessState.CURRENT,
            points=[
                TrendPoint(ts=datetime(2026, 5, 2), value=1.0),
                TrendPoint(ts=datetime(2026, 5, 1), value=2.0),
            ],
        ).validate()


def test_baseline_comparison_result_serializes() -> None:
    from premura.engine import BaselineComparisonResult, ComparisonState, FreshnessState

    d = BaselineComparisonResult(
        signal_name="sleep_deep_pct_baseline",
        metric_id="sleep_deep_pct",
        latest_value=12.0,
        baseline_mean=18.0,
        baseline_window="last 30 nights",
        comparison_state=ComparisonState.BELOW,
        freshness_state=FreshnessState.CURRENT,
        caveats=["vendor estimate"],
    ).to_dict()
    assert d["family"] == "baseline"
    assert d["comparison_state"] == "below"


def test_change_around_date_result_blocks_delta_without_data() -> None:
    from premura.engine import ChangeAroundDateResult

    ok = ChangeAroundDateResult(
        signal_name="hrv_change_around_date",
        metric_id="hrv",
        anchor_date=date(2026, 5, 1),
        before_mean=45.0,
        after_mean=50.0,
        delta=5.0,
        before_count=10,
        after_count=10,
        sufficient_data=True,
        caveats=["not a significance or causal claim"],
    ).validate()
    assert ok.to_dict()["family"] == "change"
    assert ok.to_dict()["delta"] == 5.0

    with pytest.raises(ValueError, match="sufficient_data"):
        ChangeAroundDateResult(
            signal_name="s",
            metric_id="m",
            anchor_date=date(2026, 5, 1),
            delta=5.0,
            before_count=0,
            after_count=0,
            sufficient_data=False,
        ).validate()


def test_missing_input_report_serializes() -> None:
    from premura.engine import MissingInputReport

    d = MissingInputReport(
        tool_name="resting_hr_status",
        required_inputs=["resting_heart_rate"],
        missing_inputs=["resting_heart_rate"],
        message="No resting heart rate data is available yet.",
    ).to_dict()
    assert d["family"] == "missing_input"
    assert d["missing_inputs"] == ["resting_heart_rate"]


# --- T003: lazy built-in loading still behaves correctly ------------------


def test_importing_engine_does_not_eagerly_load_signal_modules() -> None:
    # Drop the engine package and built-in module from sys.modules, then
    # re-import just the engine package and assert REGISTRY stays empty and the
    # signal module was not imported as a side effect.
    for mod in list(sys.modules):
        if mod == "premura.engine" or mod.startswith("premura.engine."):
            del sys.modules[mod]

    engine = importlib.import_module("premura.engine")
    assert engine.REGISTRY == {}
    assert "premura.engine.lab_ratios" not in sys.modules

    # The static built-in module list exists and includes lab_ratios.
    assert "premura.engine.lab_ratios" in engine._BUILTIN_SIGNAL_MODULES

    # A public helper triggers lazy loading.
    engine.list_auto_safe()
    assert engine.REGISTRY  # now populated
    assert "premura.engine.lab_ratios" in sys.modules


# --- WP01: custom pre-registration must not suppress built-ins ------------


def test_custom_pre_registration_does_not_suppress_builtins() -> None:
    # Regression for the loader footgun: before the fix the loader returned
    # early whenever ``REGISTRY`` was non-empty, so registering ANY custom
    # signal before the first lazy load silently suppressed every built-in
    # signal. The explicit ``_BUILTINS_LOADED`` flag must key the early-return
    # off load state, not registry truthiness.
    import premura.engine as engine

    # Snapshot global state so this test cannot pollute later tests.
    saved_registry = dict(engine.REGISTRY)
    saved_flag = engine._BUILTINS_LOADED
    custom_name = "_wp01_custom_pre_registration"
    try:
        # Force the "built-ins not yet loaded" precondition (mirror the lazy
        # test's reset of REGISTRY / the load flag).
        engine.REGISTRY.clear()
        engine._BUILTINS_LOADED = False

        # A contributor registers a custom signal BEFORE built-ins load.
        engine.REGISTRY[custom_name] = engine.SignalSpec(
            name=custom_name, domain=["test"], inputs=["lab:x"]
        )
        assert engine.REGISTRY  # registry is non-empty pre-load

        engine._ensure_builtin_signals_loaded()

        # Built-ins (a lab ratio AND a grounded answer) are now present...
        assert "ast_alt_ratio" in engine.REGISTRY
        assert "resting_hr_status" in engine.REGISTRY
        # ...and the custom pre-registration survived.
        assert custom_name in engine.REGISTRY
    finally:
        engine.REGISTRY.clear()
        engine.REGISTRY.update(saved_registry)
        engine._BUILTINS_LOADED = saved_flag


# --- T004: engine contract exists and parser contract points to it --------


def test_engine_contract_doc_ships_with_package() -> None:
    text = files("premura.engine").joinpath("CONTRACT.md").read_text(encoding="utf-8")
    assert "Stage 2" in text
    for family in ("status", "trend", "baseline", "change"):
        assert family in text


def test_parser_contract_points_to_engine_contract() -> None:
    text = files("premura.parsers").joinpath("CONTRACT.md").read_text(encoding="utf-8")
    assert "src/premura/engine/CONTRACT.md" in text
