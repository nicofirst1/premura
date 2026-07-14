"""Seam tests for the Stage 2 engine contributor contract (WP01).

These lock the extension surface before signal implementation begins. They
assert through public imports and observable behavior, not future signal
behavior.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
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


@contextmanager
def _fresh_engine_state():
    """Yield ``premura.engine`` reset to its pre-lazy-load state, then restore it.

    The "fresh import" the lazy-load tests below want is the empty-registry,
    nothing-lazily-imported state -- NOT a brand-new module object. Deleting
    ``premura.engine`` (and its submodules) from ``sys.modules`` and re-importing
    builds a SECOND module world with its own ``REGISTRY``/``RESOLVERS`` dicts;
    the test files that bind the engine at collection time
    (``from premura import engine`` / ``import premura.engine as engine``) keep
    pointing at the ORPHANED originals, and once a loader repopulates the new
    world their ``engine.*`` names still read the old, now-empty dicts. Under
    pytest-xdist that leaks whenever such a reset test lands first on a worker
    that later runs those siblings, and even serially it decouples the
    ``__init__`` re-exported ``RESOLVERS`` from the live ``_registry`` dict.

    Reset in place instead: clear the registries, drop the load flags, and purge
    only the *lazily* imported implementation submodules (the built-in signal
    modules + the ``views`` resolver modules). The core modules (``premura.engine``
    itself, ``_registry``, ``_resolution``, ``_results``) keep their identity, so
    every collection-time binding stays valid. Teardown restores the registries,
    flags, and purged submodules so the reset does not leak into later tests.
    """
    engine = importlib.import_module("premura.engine")

    def _lazy_names() -> set[str]:
        names = set(engine._BUILTIN_SIGNAL_MODULES)
        names |= {
            name
            for name in sys.modules
            if name == "premura.engine.views" or name.startswith("premura.engine.views.")
        }
        return names

    saved_registry = dict(engine.REGISTRY)
    saved_resolvers = dict(engine.RESOLVERS)
    saved_builtins_flag = engine._BUILTINS_LOADED
    saved_resolvers_flag = engine._RESOLVERS_LOADED
    saved_lazy = {name: sys.modules[name] for name in _lazy_names() if name in sys.modules}

    engine.REGISTRY.clear()
    engine.RESOLVERS.clear()
    engine._BUILTINS_LOADED = False
    engine._RESOLVERS_LOADED = False
    for name in list(saved_lazy):
        del sys.modules[name]
    try:
        yield engine
    finally:
        engine.REGISTRY.clear()
        engine.REGISTRY.update(saved_registry)
        engine.RESOLVERS.clear()
        engine.RESOLVERS.update(saved_resolvers)
        engine._BUILTINS_LOADED = saved_builtins_flag
        engine._RESOLVERS_LOADED = saved_resolvers_flag
        for name in list(_lazy_names()):
            sys.modules.pop(name, None)
        sys.modules.update(saved_lazy)


def test_importing_engine_does_not_eagerly_load_signal_modules() -> None:
    # Reset the engine to its pre-lazy-load state (empty registry, no lazily
    # imported signal modules) and assert using the engine keeps REGISTRY empty
    # until a public helper triggers the lazy load.
    with _fresh_engine_state() as engine:
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


# --- WP03: engine contract requires explicit profile/intake prerequisites ----


def _engine_contract_text() -> str:
    """The shipped engine contributor contract, read through the package surface.

    Black-box: we read the same artifact a contributor or reviewer would, via the
    package resource, not via a filesystem path that assumes a layout.
    """
    return files("premura.engine").joinpath("CONTRACT.md").read_text(encoding="utf-8")


def test_engine_contract_names_profile_and_intake_domains() -> None:
    """The contract acknowledges the three new semantic domains by name.

    Semantic guarantee, not exact prose: each domain must be discoverable so a
    contributor knows these are recognised data domains, not ad-hoc fields.
    """
    text = _engine_contract_text().lower()
    assert "profile" in text
    assert "intake" in text
    for domain in ("nutrition", "supplement"):
        assert domain in text, f"engine contract should name the {domain!r} domain"


def test_engine_contract_requires_explicit_prerequisite_declaration() -> None:
    """A future profile/intake-consuming signal must DECLARE its prerequisite.

    Asserts the guidance exists (the words 'declare' and 'prerequisite' appear in
    the contract) without freezing any specific sentence.
    """
    text = _engine_contract_text().lower()
    assert "declare" in text
    assert "prerequisite" in text


def test_engine_contract_rejects_opportunistic_fallbacks() -> None:
    """The contract forbids 'use a value if it happens to be there' fallbacks.

    The semantic guarantee is that opportunistic substitution for a declared
    dependency is explicitly rejected; we check for the discoverable signal
    ("happens to be" + a rejection verb) rather than an exact phrasing.
    """
    text = _engine_contract_text().lower()
    assert "happens to be" in text
    assert any(verb in text for verb in ("reject", "not a substitute", "never silently"))


def test_engine_contract_points_to_dependency_declaration_contract() -> None:
    """Guidance is discoverable: the contract points at the WP01 declaration shape.

    A reviewer following the contract must be able to reach the machine-readable
    dependency-declaration contract, so its filename must be referenced.
    """
    text = _engine_contract_text()
    assert "profile_and_intake_dependencies.yaml" in text


def test_engine_contract_keeps_non_diagnostic_boundary() -> None:
    """Regression guard: WP03 must not weaken the Stage 2 non-diagnostic boundary."""
    text = _engine_contract_text().lower()
    assert "no diagnosis" in text
    # No population norms / reference ranges, and no significance/causal claims.
    assert "reference range" in text or "population norm" in text
    assert "p-value" in text or "significance" in text


# --- T005: WP01 Stage 2 catalog/summary helpers lazy-load contract ----------


def test_catalog_and_summary_helpers_exported_from_public_surface() -> None:
    """list_metric_catalog and metric_summary must be on the public engine surface."""
    import premura.engine as engine

    for symbol in ("list_metric_catalog", "metric_summary"):
        assert symbol in engine.__all__, f"{symbol!r} missing from engine.__all__"
        assert hasattr(engine, symbol), f"{symbol!r} not accessible on engine"


def test_catalog_and_summary_result_envelopes_exported_from_public_surface() -> None:
    """MetricCatalogEntry and MetricSummaryEntry must be in engine.__all__."""
    import premura.engine as engine

    for symbol in ("MetricCatalogEntry", "MetricSummaryEntry"):
        assert symbol in engine.__all__, f"{symbol!r} missing from engine.__all__"
        assert hasattr(engine, symbol), f"{symbol!r} not accessible on engine"


def test_importing_engine_after_reset_does_not_populate_registry(monkeypatch) -> None:
    """Importing premura.engine for catalog/summary does not eagerly load signal modules.

    The new catalog helpers (list_metric_catalog, metric_summary) must not
    call _ensure_builtin_signals_loaded at import time, leaving REGISTRY empty
    until a query or compute helper forces the lazy load.
    """
    # Reset engine state to simulate a fresh import.
    with _fresh_engine_state() as engine:
        # REGISTRY is still empty -- no signal module was eagerly imported.
        assert engine.REGISTRY == {}
        assert "premura.engine.lab_ratios" not in sys.modules
        assert "premura.engine.descriptive_signals" not in sys.modules

        # The new helpers are accessible without triggering the loader.
        assert hasattr(engine, "list_metric_catalog")
        assert hasattr(engine, "metric_summary")

        # REGISTRY remains empty because we haven't called any loader-triggering helper.
        assert engine.REGISTRY == {}


def test_catalog_helpers_do_not_populate_registry_on_call(monkeypatch) -> None:
    """Calling list_metric_catalog / metric_summary must not load signal modules.

    These are catalog-metadata helpers; they should NOT invoke
    _ensure_builtin_signals_loaded and therefore must not cause REGISTRY to
    grow with built-in signals.
    """
    import duckdb

    import premura.engine as engine

    # Snapshot state so this test is safe even if built-ins are already loaded.
    saved_registry = dict(engine.REGISTRY)
    saved_flag = engine._BUILTINS_LOADED

    # Force the "not yet loaded" precondition.
    engine.REGISTRY.clear()
    engine._BUILTINS_LOADED = False

    try:
        # Use an in-memory DuckDB to satisfy the function signature without
        # needing the full warehouse schema — both helpers handle unknown
        # metrics gracefully.
        conn = duckdb.connect(":memory:")
        conn.execute(
            """
            CREATE SCHEMA IF NOT EXISTS hp;
            CREATE TABLE IF NOT EXISTS hp.dim_metric (
                metric_id VARCHAR PRIMARY KEY,
                display_name VARCHAR,
                canonical_unit VARCHAR,
                value_kind VARCHAR,
                validity_window VARCHAR,
                missing_data_policy VARCHAR
            );
            CREATE TABLE IF NOT EXISTS hp.fact_measurement (
                ts_utc TIMESTAMP,
                metric_id VARCHAR,
                value_num DOUBLE,
                value_text VARCHAR,
                unit VARCHAR,
                source_id VARCHAR,
                source_uuid VARCHAR,
                dedupe_key VARCHAR PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS hp.fact_interval (
                start_utc TIMESTAMP,
                end_utc TIMESTAMP,
                metric_id VARCHAR,
                value_num DOUBLE,
                unit VARCHAR,
                source_id VARCHAR,
                source_uuid VARCHAR,
                dedupe_key VARCHAR PRIMARY KEY
            );
            """
        )

        # Call both helpers with an unknown metric — they must not raise and
        # must not load signal modules.
        entries = engine.list_metric_catalog(["metric:unknown_for_contract_test"], conn)
        assert len(entries) == 1
        assert entries[0].validity_status.value == "unavailable"

        summary = engine.metric_summary("metric:unknown_for_contract_test", conn)
        assert summary.validity_status.value == "unavailable"

        # REGISTRY must still be empty — no built-in loader was triggered.
        assert engine.REGISTRY == {}, (
            "list_metric_catalog / metric_summary must not populate REGISTRY"
        )
        assert engine._BUILTINS_LOADED is False
        conn.close()
    finally:
        engine.REGISTRY.clear()
        engine.REGISTRY.update(saved_registry)
        engine._BUILTINS_LOADED = saved_flag
