"""Public-surface tests for the Stage 3 analytical facade (WP05).

These tests lock the *MCP-facing* surface of the analytical layer through public
``premura.engine`` imports only — the same discipline as
``tests/test_engine_policy_public_surface.py``. MCP/WP06 must be able to load
the built-in tools, list them, invoke one by name, and read the serialized
result envelope without ever importing a private contract helper or poking the
registry dict directly.

The structural guarantees this file pins down:

* The built-in proof tools (``change_point`` and ``smoothed_average``) are
  available **after** ``load_builtin_analytical_tools`` runs, via a *static
  import* of an explicit module list — never a filesystem scan.
* Invocation returns a serialized (JSON-safe) envelope.
* Repeated invocation over the same fixture is byte-deterministic.
* An unknown tool name raises a clear public ``KeyError`` (not a silent ``None``
  and not a per-tool branch).
* Adding a future tool is registration against the contract + (if needed) a
  static built-in module entry — **not** an edit to a dispatch ladder. The
  facade's invoke path goes through the single shared
  ``analytical_contract.dispatch``; there is no per-tool branch to grow.
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta

import pytest

# Everything a caller needs comes from the public engine surface only.
# Fixture scaffolding mirrors tests/test_engine_analytical_tools.py: hand-built
# policy + candidate + explicit PreparedPoint series. The policy model is part
# of the public engine surface (re-exported for policy authors), so we reach it
# there too.
from premura.engine import (
    Admissibility,
    AnalyticalInputSeries,
    AnalyticalQuestionType,
    AnalyticalResultEnvelope,
    AnalyticalStatus,
    AnalyticalToolSpec,
    EvidenceCandidate,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    MissingDataBehavior,
    PolicyShape,
    PreparedPoint,
    QuestionRule,
    QuestionType,
    RefusalOutcome,
    SufficiencyRule,
    TemporalMeaning,
    invoke_analytical_tool,
    list_analytical_tools,
    load_builtin_analytical_tools,
    prepare_input_series,
)

REFERENCE = datetime(2026, 5, 29, 12, 0, 0)
FAMILY = "rolling_recent_family"
METRIC = "resting_heart_rate"

CHANGE_POINT = "change_point"
SMOOTHED_AVERAGE = "smoothed_average"
BUILTIN_TOOL_NAMES = frozenset({CHANGE_POINT, SMOOTHED_AVERAGE})


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers (mirrors the WP03/WP04 test scaffolding)
# ---------------------------------------------------------------------------


def _recent_trend_policy() -> MetricFamilyPolicy:
    rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(
            mode=FreshnessMode.STRICT_WINDOW,
            max_age=timedelta(days=3650),
        ),
        sufficiency=SufficiencyRule(
            min_observations=None,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
    )
    return MetricFamilyPolicy(
        policy_id="rolling_recent@1",
        version=1,
        metric_family=FAMILY,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={
            QuestionType.RECENT_TREND: rule,
            QuestionType.LEVEL_SHIFT_DETECTION: rule,
            QuestionType.SMOOTHED_PATTERN: rule,
        },
        applies_to_metrics=(METRIC,),
    )


def _candidate(*, observed_at: datetime, point_count: int) -> EvidenceCandidate:
    return EvidenceCandidate(
        metric_id=METRIC,
        metric_family=FAMILY,
        value_kind="aggregate",
        observed_at=observed_at,
        source_id="fixture",
        point_count=point_count,
    )


def _usable_series(
    values: list[float],
    *,
    question_type: AnalyticalQuestionType,
) -> AnalyticalInputSeries:
    """Build a usable prepared series from explicit values, oldest-first."""
    n = len(values)
    points = [
        PreparedPoint(ts=REFERENCE - timedelta(days=(n - 1 - i)), value=values[i]) for i in range(n)
    ]
    series = prepare_input_series(
        METRIC,
        question_type,
        candidate=_candidate(observed_at=REFERENCE, point_count=n),
        policies=_recent_trend_policy(),
        points=points,
        reference_time=REFERENCE,
        freshness_status="current",
    )
    assert series.is_usable
    return series


# A clear before/after level shift so change_point produces a stable estimate.
_CHANGE_POINT_VALUES = [60.0, 61.0, 59.0, 60.0, 72.0, 73.0, 71.0, 72.0]
# A monotone-ish run long enough for at least one full smoothing window.
_SMOOTHED_VALUES = [60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0, 67.0, 68.0, 69.0]


# ---------------------------------------------------------------------------
# 1. Facade symbols import from the public engine surface
# ---------------------------------------------------------------------------


def test_facade_symbols_import_from_premura_engine() -> None:
    """The facade functions + result/input types are reachable publicly."""
    assert callable(load_builtin_analytical_tools)
    assert callable(list_analytical_tools)
    assert callable(invoke_analytical_tool)
    # The types MCP must construct or read are public too.
    assert AnalyticalResultEnvelope is not None
    assert AnalyticalStatus is not None
    assert AnalyticalToolSpec is not None
    assert RefusalOutcome is not None
    assert AnalyticalInputSeries is not None
    assert PreparedPoint is not None


def test_facade_names_are_listed_in_engine_all() -> None:
    """Every exported analytical name is in ``__all__`` so tooling sees it."""
    import premura.engine as engine

    expected = {
        "load_builtin_analytical_tools",
        "list_analytical_tools",
        "invoke_analytical_tool",
        "AnalyticalResultEnvelope",
        "AnalyticalStatus",
        "AnalyticalToolSpec",
        "RefusalOutcome",
        "ConfoundEntry",
        "ConfoundKey",
        "Uncertainty",
        "AnalyticalQuestionType",
        "AnalyticalInputSeries",
        "PreparedPoint",
        "InputRefusalReason",
        "prepare_input_series",
    }
    assert expected <= set(engine.__all__)


# ---------------------------------------------------------------------------
# 2. Built-in tools are available AFTER analytical built-in loading
# ---------------------------------------------------------------------------


def test_builtin_tools_available_after_loading() -> None:
    """``load_builtin_analytical_tools`` makes both proof tools discoverable."""
    load_builtin_analytical_tools()

    names = {spec.name for spec in list_analytical_tools()}
    assert BUILTIN_TOOL_NAMES <= names

    # Each is a real spec with a callable implementation (dispatchable).
    by_name = {spec.name: spec for spec in list_analytical_tools()}
    for tool_name in BUILTIN_TOOL_NAMES:
        spec = by_name[tool_name]
        assert isinstance(spec, AnalyticalToolSpec)
        assert spec.fn is not None


def test_list_analytical_tools_loads_builtins_implicitly() -> None:
    """``list_analytical_tools`` loads the built-ins on its own (no manual load).

    Run in a clean subprocess so a sibling test that already loaded the
    built-ins cannot mask a regression where listing forgot to load them.
    """
    import subprocess

    code = (
        "from premura.engine import list_analytical_tools;"
        "names = {s.name for s in list_analytical_tools()};"
        "assert {'change_point', 'smoothed_average'} <= names, names;"
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_builtin_loading_is_static_import_not_filesystem_scan() -> None:
    """The built-in module list is an explicit, in-tree tuple — no scanning.

    A reviewer must be able to read every built-in tool module from one tuple.
    We assert the facade declares such a tuple and that it imports none of the
    scanning/plugin machinery (``glob``/``os``/``pkgutil``/
    ``importlib.metadata``) — only ``importlib.import_module`` over a fixed
    list.
    """
    import ast

    import premura.engine.analytical as facade

    assert isinstance(facade._BUILTIN_ANALYTICAL_MODULES, tuple)
    assert "premura.engine.analytical_tools" in facade._BUILTIN_ANALYTICAL_MODULES

    # Inspect the facade's actual imports via AST so a substring like "glob"
    # inside "global" cannot create a false positive.
    tree = ast.parse(inspect.getsource(facade))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".")[0])

    forbidden_modules = {"glob", "os", "pkgutil"}
    assert forbidden_modules.isdisjoint(imported_roots), (
        f"facade must not import scanning machinery; imported roots: {sorted(imported_roots)}"
    )

    # No plugin entry-point discovery, even by name, anywhere in the source.
    source = inspect.getsource(facade)
    for forbidden in ("iter_entry_points", "entry_points(", "importlib.metadata"):
        assert forbidden not in source, f"facade must not use {forbidden!r} (no plugins)"


# ---------------------------------------------------------------------------
# 3. Tool invocation returns serialized envelopes
# ---------------------------------------------------------------------------


def test_invoke_change_point_returns_serialized_envelope() -> None:
    """Invoking ``change_point`` by name returns a JSON-safe available envelope."""
    series = _usable_series(
        _CHANGE_POINT_VALUES,
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    envelope = invoke_analytical_tool(CHANGE_POINT, series)

    assert isinstance(envelope, AnalyticalResultEnvelope)
    assert envelope.tool_name == CHANGE_POINT
    assert envelope.status is AnalyticalStatus.AVAILABLE

    serialized = envelope.to_dict()
    # JSON-safe: round-trips through the stdlib json encoder unchanged.
    import json

    assert json.loads(json.dumps(serialized)) == serialized
    assert serialized["tool_name"] == CHANGE_POINT
    assert serialized["status"] == AnalyticalStatus.AVAILABLE.value
    assert serialized["estimate"] is not None


def test_invoke_smoothed_average_returns_serialized_envelope() -> None:
    """Invoking ``smoothed_average`` by name returns a JSON-safe envelope."""
    series = _usable_series(
        _SMOOTHED_VALUES,
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    envelope = invoke_analytical_tool(SMOOTHED_AVERAGE, series, window=3)

    assert isinstance(envelope, AnalyticalResultEnvelope)
    assert envelope.tool_name == SMOOTHED_AVERAGE
    assert envelope.status is AnalyticalStatus.AVAILABLE

    serialized = envelope.to_dict()
    import json

    assert json.loads(json.dumps(serialized)) == serialized


# ---------------------------------------------------------------------------
# 4. Repeated invocation over the same fixture is deterministic
# ---------------------------------------------------------------------------


def test_repeated_invocation_is_byte_deterministic() -> None:
    """Same prepared series + params -> byte-identical serialized envelopes."""
    series = _usable_series(
        _CHANGE_POINT_VALUES,
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    )
    first = invoke_analytical_tool(CHANGE_POINT, series).to_dict()
    second = invoke_analytical_tool(CHANGE_POINT, series).to_dict()

    import json

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ---------------------------------------------------------------------------
# 5. Unknown tool names raise a clear public error
# ---------------------------------------------------------------------------


def test_unknown_tool_name_raises_keyerror() -> None:
    """An unregistered tool name raises a clear public ``KeyError``.

    This is distinct from a *refusal*: a refusal is a valid envelope for an
    admissibility/parameter problem. An unknown name is a programming error and
    surfaces as ``KeyError`` from the shared dispatch path.
    """
    with pytest.raises(KeyError):
        invoke_analytical_tool("definitely_not_a_real_tool")


def test_refused_input_returns_refusal_envelope_not_error() -> None:
    """A refused input yields a refusal envelope through invoke (not a raise).

    Confirms the facade does not collapse the contract's first-class refusal
    outcome into an exception — MCP must be able to read the machine-readable
    refusal.
    """
    refused = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        candidate=_candidate(observed_at=REFERENCE, point_count=0),
        policies=_recent_trend_policy(),
        points=[],
        reference_time=REFERENCE,
    )
    assert not refused.is_usable

    envelope = invoke_analytical_tool(CHANGE_POINT, refused)
    assert envelope.status is AnalyticalStatus.REFUSED
    assert envelope.refusal is not None
    assert envelope.estimate is None


# ---------------------------------------------------------------------------
# 6. No dispatch ladder: invoke goes through the shared dispatch path
# ---------------------------------------------------------------------------


def test_invoke_has_no_per_tool_dispatch_branch() -> None:
    """The facade's invoke path delegates to the shared contract dispatch.

    Doctrine (WP05 T020): adding a tool is registration against the contract +
    a static built-in module entry — never a new ``if tool == ...`` branch.
    We pin this two ways:

    * the facade source contains no per-tool name comparison in its invoke path,
      and
    * the facade invoke actually routes through
      ``analytical_contract.dispatch`` (proven by monkeypatching it).
    """
    import premura.engine.analytical as facade

    source = inspect.getsource(facade.invoke_analytical_tool)
    # No per-tool branching on the built-in names inside the facade invoke.
    for tool_name in BUILTIN_TOOL_NAMES:
        assert f'"{tool_name}"' not in source
        assert f"'{tool_name}'" not in source
    # It calls the shared dispatch helper.
    assert "dispatch(" in source


def test_invoke_routes_through_contract_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behavioral proof that invoke defers to ``analytical_contract.dispatch``."""
    import premura.engine.analytical as facade

    sentinel = AnalyticalResultEnvelope(
        tool_name="sentinel",
        status=AnalyticalStatus.REFUSED,
        refusal=RefusalOutcome(reason="probe", message="probe sentinel"),
    )
    calls: list[tuple[str, tuple[object, ...]]] = []

    def _fake_dispatch(tool_name: str, *args: object, **kwargs: object) -> AnalyticalResultEnvelope:
        calls.append((tool_name, args))
        return sentinel

    monkeypatch.setattr(facade, "dispatch", _fake_dispatch)

    result = facade.invoke_analytical_tool(CHANGE_POINT, "marker")
    assert result is sentinel
    assert calls == [(CHANGE_POINT, ("marker",))]


# ---------------------------------------------------------------------------
# 7. The facade does not leak MCP / warehouse imports
# ---------------------------------------------------------------------------


def test_facade_import_does_not_leak_mcp_or_warehouse() -> None:
    """Importing the facade must not pull in MCP, DuckDB, or network modules.

    Run in a clean subprocess: in the full test run sibling tests may already
    have loaded these, so scanning the live process would report their imports.
    """
    import subprocess

    code = (
        "import sys;"
        "import premura.engine.analytical;"
        "from premura.engine import load_builtin_analytical_tools;"
        "load_builtin_analytical_tools();"
        "forbidden = ('duckdb', 'mcp', 'httpx', 'aiohttp', 'premura.mcp', 'premura.warehouse');"
        "leaked = sorted(n for n in sys.modules"
        " if any(t in n.lower() for t in forbidden));"
        "assert leaked == [], 'facade import leaked: ' + repr(leaked);"
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"
