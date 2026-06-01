"""WP05 — default MCP surface for the finished analytical tool set.

These lock FR-010 / C-005 at the MCP boundary for the two newly published
tools (``rolling_mean`` and ``paired_t_test``):

* the DEFAULT agent-safe surface (and the operator surface, which inherits the
  default set) publishes both new tools, taking the surface from 16 to 18 tools;
* each wrapper DELEGATES to the engine analytical path and only SERIALIZES the
  returned envelope — the serialized ``result`` is the engine envelope's
  ``to_dict()`` verbatim, and the wrapper authors no statistic, pairing, caveat,
  or estimate (proven by spying on the engine seams and by a static guard);
* a refusal flows back with a distinct reason and no estimate;
* caller-facing parameter validation rejects malformed shapes before dispatch.

Synthetic warehouses only.
"""

from __future__ import annotations

import ast
import asyncio
import importlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import premura.mcp.entrypoint as entrypoint
from premura.mcp import server
from premura.store import duck

build_operator_server = entrypoint.build_operator_server
build_server = entrypoint.build_server


@pytest.fixture(autouse=True)
def _ensure_live_analytical_registry() -> None:
    """Heal cross-test pollution of the analytical built-in registry.

    ``tests/test_engine_contract.py`` deletes ``premura.engine.*`` from
    ``sys.modules`` and re-imports the package to prove lazy loading. That leaves
    the already-imported MCP modules (``premura.mcp.server`` / ``.entrypoint``)
    bound to a *stale* engine module whose analytical ``REGISTRY`` is empty, so a
    later ``invoke_analytical_tool('rolling_mean')`` would raise ``KeyError``. We
    detect that state and rebind the MCP layer to the live engine module so these
    tests are order-independent (the wrappers themselves are unaffected — only the
    test process's module identity was corrupted by the sibling reload test).
    """
    global server, build_server, build_operator_server
    if not server.engine.list_analytical_tools():
        importlib.reload(server)
        importlib.reload(entrypoint)
        build_server = entrypoint.build_server
        build_operator_server = entrypoint.build_operator_server


# WP05 adds rolling_mean + paired_t_test to the prior sixteen default tools;
# pubmed-grounding-tools later adds pubmed_search + pubmed_fetch (-> 20).
_DEFAULT_TOOLS_FINISHED = sorted(
    [
        "list_metrics",
        "metric_summary",
        "resting_hr_status",
        "resting_hr_trend",
        "steps_trend",
        "weight_trend",
        "sleep_deep_pct_baseline",
        "hrv_change_around_date",
        "profile_context_supported_fields",
        "profile_context_record",
        "change_point",
        "smoothed_average",
        "correlate",
        "rolling_mean",
        "paired_t_test",
        "pubmed_search",
        "pubmed_fetch",
        "research_trace_open",
        "research_trace_mark_surfaced",
        "research_trace_disclosure",
    ]
)

_METRIC = "resting_hr"
_N = 40


def _series_base() -> datetime:
    """The newest point's instant: a fixed point ~12h ago.

    Anchored to the start of *today* (UTC) so two reads of the same warehouse in
    one test see an identical window regardless of sub-second ``now()`` drift
    between calls — the property the byte-equivalence regression needs. Still well
    within ``resting_hr``'s 2-day freshness window, so the series stays admissible.
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(hours=12)


def _empty_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _warehouse_with_series(tmp_path: Path) -> Path:
    """Seed a ~40-day ``resting_hr`` series with a clear upward step near midpoint."""
    db_path = tmp_path / "finished.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    base = _series_base()
    conn.execute("BEGIN")
    for i in range(_N):
        ts = (base - timedelta(days=(_N - 1 - i))).isoformat(sep=" ")
        value = 50.0 + (i % 3) + (10.0 if i > (_N // 2) else 0.0)
        conn.execute(
            """
            INSERT INTO hp.fact_measurement
                (ts_utc, metric_id, value_num, unit, source_id, dedupe_key)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [ts, _METRIC, value, "bpm", "test:source", f"k{i}"],
        )
    conn.execute("COMMIT")
    conn.close()
    return db_path


def _anchor() -> str:
    return (_series_base() - timedelta(days=(_N // 2))).date().isoformat()


def _pin_engine_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the Stage 2 evidence-read clock so two separate reads of one
    warehouse produce a byte-identical trailing window.

    The engine buckets ``[now - span, now]`` and may carry an observation forward
    into the trailing bucket at a ``now()``-derived timestamp; that drifts between
    two dispatches. Pinning isolates the wrapper's serialize-only behavior from the
    evidence read. The fixed instant stays inside ``resting_hr``'s freshness window.

    Patch the clock on the *exact* ``_query`` module object the live MCP wrapper
    uses (``server.engine_query``). A sibling reload test can leave a second
    ``premura.engine._query`` object in play; patching a freshly-imported copy would
    miss the one ``ordered_window`` actually reads.
    """
    fixed = _series_base() + timedelta(hours=6)
    monkeypatch.setattr(server.engine_query, "_naive_utc_now", lambda: fixed)


# ---------------------------------------------------------------------------
# 1. Both tools are on the default (and operator) surface — now 20 tools total.
# ---------------------------------------------------------------------------


def test_default_surface_lists_exactly_twenty_tools() -> None:
    async def run() -> None:
        server_ = build_server()
        names = sorted(tool.name for tool in await server_.list_tools())
        assert names == _DEFAULT_TOOLS_FINISHED
        assert len(names) == 20

    asyncio.run(run())


def test_default_surface_includes_both_new_tools() -> None:
    async def run() -> None:
        server_ = build_server()
        names = {tool.name for tool in await server_.list_tools()}
        assert {"rolling_mean", "paired_t_test"} <= names

    asyncio.run(run())


def test_operator_surface_inherits_both_new_tools() -> None:
    async def run() -> None:
        server_ = build_operator_server()
        names = {tool.name for tool in await server_.list_tools()}
        assert {"rolling_mean", "paired_t_test"} <= names

    asyncio.run(run())


# ---------------------------------------------------------------------------
# 2. rolling_mean wrapper: delegation + verbatim envelope, no computation.
# ---------------------------------------------------------------------------


def test_rolling_mean_available_payload_shape(tmp_path: Path) -> None:
    payload = server.rolling_mean(
        _METRIC, window=5, warehouse_path=_warehouse_with_series(tmp_path)
    )
    assert payload["status"] == "available"
    assert payload["tool_name"] == "rolling_mean"
    assert payload["result"]["tool_name"] == "rolling_mean"
    # The estimate metadata is the engine's; the wrapper authored none of it.
    assert "method_revision" in payload["result"]["estimate"]
    assert payload["result"]["estimate"]["window"] == 5


def test_rolling_mean_delegates_to_engine_invoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper hands off to ``engine.invoke_analytical_tool('rolling_mean')``."""
    db_path = _warehouse_with_series(tmp_path)
    seen: dict[str, object] = {}
    real_invoke = server.engine.invoke_analytical_tool

    def spy_invoke(tool_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["tool_name"] = tool_name
        return real_invoke(tool_name, *args, **kwargs)

    monkeypatch.setattr(server.engine, "invoke_analytical_tool", spy_invoke)

    payload = server.rolling_mean(_METRIC, window=5, warehouse_path=db_path)
    assert payload["status"] == "available"
    assert seen.get("tool_name") == "rolling_mean"


def test_rolling_mean_returns_engine_envelope_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper's ``result`` is the engine envelope verbatim — it authors no estimate.

    The envelope carries only engine-owned metadata (``tool_name`` /
    ``method_revision`` / ``estimate`` shape), and two pinned-clock dispatches over
    one warehouse are byte-identical, proving the wrapper serializes the engine's
    envelope and adds nothing of its own.
    """
    _pin_engine_clock(monkeypatch)
    db_path = _warehouse_with_series(tmp_path)
    first = server.rolling_mean(_METRIC, window=5, warehouse_path=db_path)
    second = server.rolling_mean(_METRIC, window=5, warehouse_path=db_path)

    assert first["status"] == "available"
    # Engine-authored fields the wrapper does not (and must not) compute.
    assert first["result"]["tool_name"] == "rolling_mean"
    assert "method_revision" in first["result"]["estimate"]
    # Verbatim + deterministic: the serialized engine envelope is reproduced exactly.
    assert first["result"] == second["result"]


def test_rolling_mean_refuses_missing_evidence_with_no_estimate(tmp_path: Path) -> None:
    payload = server.rolling_mean(_METRIC, warehouse_path=_empty_warehouse(tmp_path))
    assert payload["status"] == "refused"
    assert payload["result"]["refusal"]["reason"]
    assert payload["result"]["estimate"] is None


def test_rolling_mean_rejects_empty_metric_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="metric_id"):
        server.rolling_mean("   ", warehouse_path=_warehouse_with_series(tmp_path))


# ---------------------------------------------------------------------------
# 3. paired_t_test wrapper: delegation + verbatim envelope, no computation.
# ---------------------------------------------------------------------------


def test_paired_t_test_available_payload_shape(tmp_path: Path) -> None:
    payload = server.paired_t_test(
        _METRIC,
        anchor_date=_anchor(),
        before_days=18,
        after_days=18,
        expected_direction="increase",
        warehouse_path=_warehouse_with_series(tmp_path),
    )
    assert payload["status"] == "available"
    assert payload["tool_name"] == "paired_t_test"
    estimate = payload["result"]["estimate"]
    assert "mean_difference" in estimate
    assert "method_revision" in estimate
    # Descriptive only: no p-value / significance escaped the engine.
    serialized = str(payload).lower()
    assert "p_value" not in serialized
    assert "p-value" not in serialized


def test_paired_t_test_delegates_prep_and_dispatch_to_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper builds the request and hands off to the engine seams:
    ``prepare_before_after_paired_input`` then ``invoke_analytical_tool``."""
    db_path = _warehouse_with_series(tmp_path)
    seen: dict[str, object] = {}
    real_prepare = server.engine.prepare_before_after_paired_input
    real_invoke = server.engine.invoke_analytical_tool

    def spy_prepare(series, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["prepare_called"] = True
        seen["request"] = request
        return real_prepare(series, request, *args, **kwargs)

    def spy_invoke(tool_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["tool_name"] = tool_name
        return real_invoke(tool_name, *args, **kwargs)

    monkeypatch.setattr(server.engine, "prepare_before_after_paired_input", spy_prepare)
    monkeypatch.setattr(server.engine, "invoke_analytical_tool", spy_invoke)

    payload = server.paired_t_test(
        _METRIC,
        anchor_date=_anchor(),
        before_days=18,
        after_days=18,
        expected_direction="increase",
        warehouse_path=db_path,
    )
    assert payload["status"] == "available"
    assert seen.get("prepare_called") is True
    assert seen.get("tool_name") == "paired_t_test"
    assert isinstance(seen.get("request"), server.BeforeAfterPairedRequest)


def test_paired_t_test_returns_engine_envelope_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper's ``result`` is the engine envelope verbatim — it authors no estimate.

    The envelope carries only engine-owned metadata (``tool_name`` /
    ``method_revision`` / ``mean_difference``), and two pinned-clock dispatches over
    one warehouse are byte-identical, proving the wrapper serializes the engine's
    envelope and computes nothing of its own.
    """
    _pin_engine_clock(monkeypatch)
    db_path = _warehouse_with_series(tmp_path)
    args = dict(
        anchor_date=_anchor(),
        before_days=18,
        after_days=18,
        expected_direction="increase",
        warehouse_path=db_path,
    )
    first = server.paired_t_test(_METRIC, **args)
    second = server.paired_t_test(_METRIC, **args)

    assert first["status"] == "available"
    # Engine-authored fields the wrapper does not (and must not) compute.
    assert first["result"]["tool_name"] == "paired_t_test"
    assert "method_revision" in first["result"]["estimate"]
    assert "mean_difference" in first["result"]["estimate"]
    # Verbatim + deterministic: the serialized engine envelope is reproduced exactly.
    assert first["result"] == second["result"]


def test_paired_t_test_refuses_too_few_pairs_with_no_estimate(tmp_path: Path) -> None:
    """An anchor with too little data on one side returns a refusal, no estimate."""
    payload = server.paired_t_test(
        _METRIC,
        anchor_date=_anchor(),
        before_days=2,  # far below the raw-pair floor
        after_days=2,
        expected_direction="increase",
        warehouse_path=_warehouse_with_series(tmp_path),
    )
    assert payload["status"] == "refused"
    assert payload["result"]["refusal"]["reason"]
    assert payload["result"]["estimate"] is None


def test_paired_t_test_rejects_empty_metric_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="metric_id"):
        server.paired_t_test(
            "  ",
            anchor_date=_anchor(),
            before_days=18,
            after_days=18,
            expected_direction="increase",
            warehouse_path=_warehouse_with_series(tmp_path),
        )


def test_paired_t_test_rejects_unknown_direction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected_direction"):
        server.paired_t_test(
            _METRIC,
            anchor_date=_anchor(),
            before_days=18,
            after_days=18,
            expected_direction="sideways",
            warehouse_path=_warehouse_with_series(tmp_path),
        )


def test_paired_t_test_rejects_bad_anchor_date(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="anchor_date"):
        server.paired_t_test(
            _METRIC,
            anchor_date="not-a-date",
            before_days=18,
            after_days=18,
            expected_direction="increase",
            warehouse_path=_warehouse_with_series(tmp_path),
        )


# ---------------------------------------------------------------------------
# 4. Static guard: neither wrapper performs statistics in the MCP layer (C-005).
# ---------------------------------------------------------------------------


def test_new_wrappers_perform_no_statistics() -> None:
    """The two new wrappers must not implement statistics or pairing in MCP code.

    The wrapper functions build a request and delegate; they must not compute a
    mean/std/difference or author fact-table SQL. We scan their executable
    surface (call names + literals), not prose.
    """
    for func in (server.rolling_mean, server.paired_t_test, server._parse_before_after_direction):
        import inspect

        tree = ast.parse(inspect.getsource(func))
        forbidden_call_names = {
            "mean",
            "stdev",
            "pstdev",
            "variance",
            "sqrt",
            "spearmanr",
            "pearsonr",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_call_names, (
                    f"{func.__name__} must not call {node.func.id!r}"
                )
        literals = [
            n.value.lower()
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        for lit in literals:
            assert "from hp.fact_measurement" not in lit
            assert "from hp.fact_interval" not in lit
