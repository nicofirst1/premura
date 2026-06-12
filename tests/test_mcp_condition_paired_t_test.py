"""m8 WP3 — MCP exposure of ``condition_paired_t_test`` + trace identity (E3).

These lock the MCP boundary for the sixth analytical tool:

* the default agent-safe surface (and the operator surface) publishes
  ``condition_paired_t_test`` (the exact count is pinned in the test below);
* the wrapper DELEGATES to the engine analytical path
  (``prepare_condition_label_paired_input`` then ``invoke_analytical_tool``) and
  only SERIALIZES the returned envelope verbatim — it authors no statistic,
  pairing, caveat, or estimate (spied + statically guarded);
* a refusal flows back with a distinct reason and no estimate;
* caller-facing parameter validation rejects malformed shapes before dispatch
  (E3: empty metric, bad direction, malformed episodes, scan-shaped kwargs);
* the tool declares its normalized hypothesis identity in the trace registry.

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
from premura import trace
from premura.mcp import server
from premura.store import duck

build_operator_server = entrypoint.build_operator_server
build_server = entrypoint.build_server


@pytest.fixture(autouse=True)
def _ensure_live_analytical_registry() -> None:
    global server, build_server, build_operator_server
    if not server.engine.list_analytical_tools():
        importlib.reload(server)
        importlib.reload(entrypoint)
        build_server = entrypoint.build_server
        build_operator_server = entrypoint.build_operator_server


_METRIC = "resting_hr"
_N = 90


def _series_base() -> datetime:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(hours=12)


def _empty_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _warehouse_with_episodic_series(tmp_path: Path) -> Path:
    """Seed a ~90-day daily ``resting_hr`` series with a higher level on the two
    declared on-condition windows so each episode has clean off + on data."""
    db_path = tmp_path / "condition.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    base = _series_base()
    conn.execute("BEGIN")
    ep_bounds = _episode_bounds()
    ep1_days = set(_days_in(ep_bounds[0]))
    ep2_days = set(_days_in(ep_bounds[1]))
    for i in range(_N):
        day = (base - timedelta(days=(_N - 1 - i))).date()
        ts = (base - timedelta(days=(_N - 1 - i))).isoformat(sep=" ")
        # Baseline off-label level, with a touch of spread. Each on-condition
        # window lifts the level by a DIFFERENT amount so the two per-episode
        # differences are not identical (a constant difference would refuse).
        value = 50.0 + (i % 2)
        if day in ep1_days:
            value += 10.0
        elif day in ep2_days:
            value += 16.0
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


def _episode_bounds() -> list[tuple[str, str]]:
    base = _series_base().date()
    ep1_start = base - timedelta(days=60)
    ep2_start = base - timedelta(days=30)
    return [
        (ep1_start.isoformat(), (ep1_start + timedelta(days=4)).isoformat()),
        (ep2_start.isoformat(), (ep2_start + timedelta(days=4)).isoformat()),
    ]


def _days_in(bounds: tuple[str, str]) -> list:
    from datetime import date

    start = date.fromisoformat(bounds[0])
    end = date.fromisoformat(bounds[1])
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def _episodes_payload() -> list[dict[str, str]]:
    return [{"start_day": s, "end_day": e} for s, e in _episode_bounds()]


def _pin_engine_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = _series_base() + timedelta(hours=6)
    monkeypatch.setattr(server.engine_query, "_naive_utc_now", lambda: fixed)


# ---------------------------------------------------------------------------
# 1. Surface: condition_paired_t_test on default + operator surfaces (-> 23).
# ---------------------------------------------------------------------------


def test_default_surface_includes_condition_tool() -> None:
    async def run() -> None:
        server_ = build_server()
        names = {tool.name for tool in await server_.list_tools()}
        assert "condition_paired_t_test" in names
        assert len(names) == 26

    asyncio.run(run())


def test_operator_surface_includes_condition_tool() -> None:
    async def run() -> None:
        server_ = build_operator_server()
        names = {tool.name for tool in await server_.list_tools()}
        assert "condition_paired_t_test" in names

    asyncio.run(run())


# ---------------------------------------------------------------------------
# 2. Wrapper: delegation + verbatim envelope, no computation in MCP.
# ---------------------------------------------------------------------------


def test_available_payload_shape(tmp_path: Path) -> None:
    payload = server.condition_paired_t_test(
        _METRIC,
        condition_label="on_magnesium",
        episodes=_episodes_payload(),
        before_days=10,
        after_days=5,
        expected_direction="increase",
        warehouse_path=_warehouse_with_episodic_series(tmp_path),
    )
    assert payload["status"] == "available"
    assert payload["tool_name"] == "condition_paired_t_test"
    estimate = payload["result"]["estimate"]
    assert "mean_difference" in estimate
    assert estimate["condition_label"] == "on_magnesium"
    assert estimate["method_revision"] == "1"
    serialized = str(payload).lower()
    assert "p_value" not in serialized
    assert "p-value" not in serialized
    assert "significan" not in serialized


def test_delegates_prep_and_dispatch_to_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _warehouse_with_episodic_series(tmp_path)
    seen: dict[str, object] = {}
    real_prepare = server.engine.prepare_condition_label_paired_input
    real_invoke = server.engine.invoke_analytical_tool

    def spy_prepare(series, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["prepare_called"] = True
        seen["request"] = request
        return real_prepare(series, request, *args, **kwargs)

    def spy_invoke(tool_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["tool_name"] = tool_name
        return real_invoke(tool_name, *args, **kwargs)

    monkeypatch.setattr(server.engine, "prepare_condition_label_paired_input", spy_prepare)
    monkeypatch.setattr(server.engine, "invoke_analytical_tool", spy_invoke)

    payload = server.condition_paired_t_test(
        _METRIC,
        condition_label="on_magnesium",
        episodes=_episodes_payload(),
        before_days=10,
        after_days=5,
        expected_direction="increase",
        warehouse_path=db_path,
    )
    assert payload["status"] == "available"
    assert seen.get("prepare_called") is True
    assert seen.get("tool_name") == "condition_paired_t_test"
    assert isinstance(seen.get("request"), server.ConditionLabelPairedRequest)


def test_returns_engine_envelope_verbatim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_engine_clock(monkeypatch)
    db_path = _warehouse_with_episodic_series(tmp_path)
    args = dict(
        condition_label="on_magnesium",
        episodes=_episodes_payload(),
        before_days=10,
        after_days=5,
        expected_direction="increase",
        warehouse_path=db_path,
    )
    first = server.condition_paired_t_test(_METRIC, **args)
    second = server.condition_paired_t_test(_METRIC, **args)
    assert first["status"] == "available"
    assert first["result"]["tool_name"] == "condition_paired_t_test"
    assert "method_revision" in first["result"]["estimate"]
    assert first["result"] == second["result"]


def test_refuses_with_no_estimate_on_empty_warehouse(tmp_path: Path) -> None:
    payload = server.condition_paired_t_test(
        _METRIC,
        condition_label="on_magnesium",
        episodes=_episodes_payload(),
        before_days=10,
        after_days=5,
        expected_direction="increase",
        warehouse_path=_empty_warehouse(tmp_path),
    )
    assert payload["status"] == "refused"
    assert payload["result"]["refusal"]["reason"]
    assert payload["result"]["estimate"] is None


# ---------------------------------------------------------------------------
# 3. E3 — caller-facing parameter validation rejects malformed shapes.
# ---------------------------------------------------------------------------


def test_rejects_empty_metric_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="metric_id"):
        server.condition_paired_t_test(
            "  ",
            condition_label="on_magnesium",
            episodes=_episodes_payload(),
            before_days=10,
            after_days=5,
            expected_direction="increase",
            warehouse_path=_warehouse_with_episodic_series(tmp_path),
        )


def test_rejects_empty_condition_label(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="condition_label"):
        server.condition_paired_t_test(
            _METRIC,
            condition_label="   ",
            episodes=_episodes_payload(),
            before_days=10,
            after_days=5,
            expected_direction="increase",
            warehouse_path=_warehouse_with_episodic_series(tmp_path),
        )


def test_rejects_unknown_direction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected_direction"):
        server.condition_paired_t_test(
            _METRIC,
            condition_label="on_magnesium",
            episodes=_episodes_payload(),
            before_days=10,
            after_days=5,
            expected_direction="sideways",
            warehouse_path=_warehouse_with_episodic_series(tmp_path),
        )


def test_rejects_malformed_episode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="episode"):
        server.condition_paired_t_test(
            _METRIC,
            condition_label="on_magnesium",
            episodes=[{"start_day": "not-a-date", "end_day": "2026-05-05"}],
            before_days=10,
            after_days=5,
            expected_direction="increase",
            warehouse_path=_warehouse_with_episodic_series(tmp_path),
        )


def test_e3_rejects_label_list_at_the_boundary(tmp_path: Path) -> None:
    # A scan attempt: a list of labels where one operator-declared string is
    # required is rejected at the boundary, before any computation.
    with pytest.raises((ValueError, TypeError)):
        server.condition_paired_t_test(
            _METRIC,
            condition_label=["on_magnesium", "off_magnesium"],  # type: ignore[arg-type]
            episodes=_episodes_payload(),
            before_days=10,
            after_days=5,
            expected_direction="increase",
            warehouse_path=_warehouse_with_episodic_series(tmp_path),
        )


def test_e3_rejects_p_value_kwarg_at_the_boundary(tmp_path: Path) -> None:
    # A p_value-style kwarg is not part of the wrapper surface.
    with pytest.raises(TypeError):
        server.condition_paired_t_test(  # type: ignore[call-arg]
            _METRIC,
            condition_label="on_magnesium",
            episodes=_episodes_payload(),
            before_days=10,
            after_days=5,
            expected_direction="increase",
            p_value=True,
            warehouse_path=_warehouse_with_episodic_series(tmp_path),
        )


# ---------------------------------------------------------------------------
# 4. Static guard: wrapper performs no statistics in the MCP layer.
# ---------------------------------------------------------------------------


def test_wrapper_performs_no_statistics() -> None:
    import inspect

    for func in (server.condition_paired_t_test, server._parse_condition_episodes):
        tree = ast.parse(inspect.getsource(func))
        forbidden = {"mean", "stdev", "pstdev", "variance", "sqrt", "spearmanr", "pearsonr"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden, (
                    f"{func.__name__} must not call {node.func.id}"
                )
        literals = [
            n.value.lower()
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        for lit in literals:
            assert "from hp.fact_measurement" not in lit
            assert "from hp.fact_interval" not in lit


# ---------------------------------------------------------------------------
# 5. FR-6 — trace identity for the new tool.
# ---------------------------------------------------------------------------


def test_condition_tool_registered_in_identity_registry() -> None:
    assert "condition_paired_t_test" in trace._IDENTITY_REGISTRY


def test_identity_exact_retry_collapses() -> None:
    req = {
        "metric_id": _METRIC,
        "condition_label": "on_magnesium",
        "episodes": _episodes_payload(),
        "before_days": 10,
        "after_days": 5,
        "expected_direction": "increase",
    }
    a = trace.hypothesis_identity("condition_paired_t_test", dict(req))
    b = trace.hypothesis_identity("condition_paired_t_test", dict(req))
    assert a == b


def test_identity_different_label_is_distinct() -> None:
    base = {
        "metric_id": _METRIC,
        "episodes": _episodes_payload(),
        "before_days": 10,
        "after_days": 5,
        "expected_direction": "increase",
    }
    a = trace.hypothesis_identity("condition_paired_t_test", {**base, "condition_label": "a"})
    b = trace.hypothesis_identity("condition_paired_t_test", {**base, "condition_label": "b"})
    assert a != b


def test_identity_different_episode_set_is_distinct() -> None:
    base = {
        "metric_id": _METRIC,
        "condition_label": "on_magnesium",
        "before_days": 10,
        "after_days": 5,
        "expected_direction": "increase",
    }
    eps1 = _episodes_payload()
    eps2 = [eps1[0]]  # a different episode set
    a = trace.hypothesis_identity("condition_paired_t_test", {**base, "episodes": eps1})
    b = trace.hypothesis_identity("condition_paired_t_test", {**base, "episodes": eps2})
    assert a != b


def test_identity_episode_order_is_insensitive() -> None:
    # The declared SET of episodes bears on the hypothesis, not the listing order.
    base = {
        "metric_id": _METRIC,
        "condition_label": "on_magnesium",
        "before_days": 10,
        "after_days": 5,
        "expected_direction": "increase",
    }
    eps = _episodes_payload()
    a = trace.hypothesis_identity("condition_paired_t_test", {**base, "episodes": eps})
    b = trace.hypothesis_identity(
        "condition_paired_t_test", {**base, "episodes": list(reversed(eps))}
    )
    assert a == b
