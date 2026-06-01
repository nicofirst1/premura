"""WP05 — default-surface discovery for the finished analytical tool set.

These tests pin FR-001 / SC-001 / NFR-007 / NFR-008: after WP05 wires the
default loader, the public engine discovery surface
``premura.engine.list_analytical_tools()`` returns exactly the FIVE shipped
built-ins (``change_point``, ``smoothed_average``, ``correlate``,
``rolling_mean``, ``paired_t_test``) — the two tools WP02/WP04 registered into
the shared REGISTRY but deliberately left off the static default loader are now
published.

The structural guarantees this file locks down:

* the static built-in module/name lists carry both new tools (no filesystem
  scan, no plugin loader);
* the full catalog is exactly five named tools, each dispatchable;
* the before/after paired-input seam the ``paired_t_test`` MCP wrapper needs is
  re-exported from the public engine surface;
* listing the catalog stays well under one second (NFR-007).

Pure engine surface only — no MCP, no warehouse.
"""

from __future__ import annotations

import sys
import time

from premura.engine import (
    AnalyticalToolSpec,
    BeforeAfterDirection,
    BeforeAfterPairedRequest,
    before_after_pairs_for_computation,
    list_analytical_tools,
    load_builtin_analytical_tools,
    prepare_before_after_paired_input,
)

# The full, exact catalog FR-001 / SC-001 require after WP05.
_EXPECTED_TOOLS = frozenset(
    {
        "change_point",
        "smoothed_average",
        "correlate",
        "rolling_mean",
        "paired_t_test",
    }
)

# The two tools earlier WPs deferred to the default surface.
_NEWLY_PUBLISHED = frozenset({"rolling_mean", "paired_t_test"})


# ---------------------------------------------------------------------------
# 1. The default catalog is EXACTLY five tools (the headline requirement).
# ---------------------------------------------------------------------------


def test_default_catalog_is_exactly_five_tools() -> None:
    """``list_analytical_tools`` returns exactly the five shipped built-ins."""
    names = sorted(spec.name for spec in list_analytical_tools())
    assert names == sorted(_EXPECTED_TOOLS)
    assert len(names) == 5


def test_both_deferred_tools_are_now_published() -> None:
    """``rolling_mean`` and ``paired_t_test`` reach the default surface (FR-001)."""
    names = {spec.name for spec in list_analytical_tools()}
    assert _NEWLY_PUBLISHED <= names


def test_every_catalog_tool_is_dispatchable() -> None:
    """Each of the five built-ins is a real spec with a callable implementation."""
    by_name = {spec.name: spec for spec in list_analytical_tools()}
    assert set(by_name) == set(_EXPECTED_TOOLS)
    for name in _EXPECTED_TOOLS:
        spec = by_name[name]
        assert isinstance(spec, AnalyticalToolSpec)
        assert spec.fn is not None


def test_list_loads_five_builtins_in_clean_process() -> None:
    """Listing loads all five built-ins on its own (no prior manual load).

    Run in a clean subprocess so a sibling test that already triggered the load
    cannot mask a regression where the static loader forgot one of the two newly
    published tools.
    """
    import subprocess

    code = (
        "from premura.engine import list_analytical_tools;"
        "names = sorted(s.name for s in list_analytical_tools());"
        "expected = sorted(["
        "'change_point','smoothed_average','correlate','rolling_mean','paired_t_test'"
        "]);"
        "assert names == expected, names;"
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


# ---------------------------------------------------------------------------
# 2. Static loader, not scanning: both new modules are in the explicit tuple.
# ---------------------------------------------------------------------------


def test_static_loader_lists_both_new_modules() -> None:
    """The built-in module/name lists carry both new tools as explicit entries."""
    import premura.engine.analytical as facade

    assert isinstance(facade._BUILTIN_ANALYTICAL_MODULES, tuple)
    assert "premura.engine.rolling_mean" in facade._BUILTIN_ANALYTICAL_MODULES
    assert "premura.engine.paired_t_test" in facade._BUILTIN_ANALYTICAL_MODULES
    # The reload-guard name set is kept in sync with the published catalog.
    assert _EXPECTED_TOOLS <= facade._BUILTIN_ANALYTICAL_NAMES


def test_loader_did_not_grow_a_plugin_or_scan() -> None:
    """No plugin/entry-point/filesystem-scan machinery sneaks in with the new tools."""
    import inspect

    import premura.engine.analytical as facade

    source = inspect.getsource(facade)
    for forbidden in ("iter_entry_points", "entry_points(", "importlib.metadata", "glob("):
        assert forbidden not in source, f"loader must not use {forbidden!r} (static list only)"


# ---------------------------------------------------------------------------
# 3. The before/after paired-input seam is on the public engine surface.
# ---------------------------------------------------------------------------


def test_before_after_paired_seam_is_publicly_exported() -> None:
    """The ``paired_t_test`` wrapper's paired-input seam imports from ``premura.engine``."""
    import premura.engine as engine

    expected = {
        "BeforeAfterDirection",
        "BeforeAfterPairedRequest",
        "prepare_before_after_paired_input",
        "before_after_pairs_for_computation",
    }
    assert expected <= set(engine.__all__)
    assert callable(prepare_before_after_paired_input)
    assert callable(before_after_pairs_for_computation)
    # The closed direction vocabulary and request dataclass are constructible.
    request = BeforeAfterPairedRequest(
        metric_id="resting_hr",
        anchor_date=__import__("datetime").date(2026, 5, 1),
        before_days=8,
        after_days=8,
        expected_direction=BeforeAfterDirection.INCREASE,
    )
    assert request.metric_id == "resting_hr"


# ---------------------------------------------------------------------------
# 4. NFR-007 — listing the catalog stays well under one second.
# ---------------------------------------------------------------------------


def test_listing_catalog_is_fast() -> None:
    """Discovery of the five-tool catalog completes comfortably under one second."""
    load_builtin_analytical_tools()  # warm the lazy import out of the measured path
    start = time.perf_counter()
    for _ in range(50):
        names = {spec.name for spec in list_analytical_tools()}
    elapsed = time.perf_counter() - start
    assert names == set(_EXPECTED_TOOLS)
    # 50 listings in well under a second; one listing is far under the 1s budget.
    assert elapsed < 1.0, f"50 catalog listings took {elapsed:.3f}s"
