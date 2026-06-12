"""MCP exposure of condition-episode capture + stored-declaration consumption.

Locks the new agent-mediated capture surface (``condition_episode_record`` /
``condition_episode_list`` / ``condition_episode_retract``) and the consumption
seam: ``condition_paired_t_test`` with ``episodes`` omitted loads the stored
current closed declaration for the label, returns an envelope numerically
identical to declaring the same set by hand, and adds a wrapper-layer
``episodes_source`` disclosure (the explicit path stays byte-identical to
before). Synthetic warehouses only.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import premura.mcp.entrypoint as entrypoint
from premura.mcp import server
from premura.store import duck

build_server = entrypoint.build_server


@pytest.fixture(autouse=True)
def _ensure_live_analytical_registry() -> None:
    global server, build_server
    if not server.engine.list_analytical_tools():
        importlib.reload(server)
        importlib.reload(entrypoint)
        build_server = entrypoint.build_server


def _call(server_: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await server_.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def _warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "warehouse.duckdb"
    duck.initialize(db_path).close()
    return db_path


# --------------------------------------------------------------------------- #
# Capture: record / list / retract through the MCP surface.
# --------------------------------------------------------------------------- #


def test_record_list_retract_round_trip(tmp_path: Path) -> None:
    server_ = build_server(warehouse_path=_warehouse(tmp_path))

    recorded = _call(
        server_,
        "condition_episode_record",
        {
            "condition_label": "cold",
            "start_day": "2026-03-03",
            "end_day": "2026-03-10",
            "note": "declared at checkup prep",
        },
    )
    assert recorded["status"] == "recorded"
    assert recorded["source_kind"] == "agent_condition_capture"
    episode = recorded["episode"]
    assert episode["condition_label"] == "cold"
    assert episode["start_day"] == "2026-03-03"
    assert episode["ongoing"] is False
    assert recorded["capture_session_id"]

    listed = _call(server_, "condition_episode_list", {"condition_label": "cold"})
    assert listed["count"] == 1
    assert listed["episodes"][0]["episode_id"] == episode["episode_id"]

    retracted = _call(
        server_,
        "condition_episode_retract",
        {"episode_id": episode["episode_id"], "reason": "was allergies"},
    )
    assert retracted["status"] == "retracted"
    assert retracted["episode"]["retraction_reason"] == "was allergies"

    assert _call(server_, "condition_episode_list", {"condition_label": "cold"})["count"] == 0
    history = _call(
        server_,
        "condition_episode_list",
        {"condition_label": "cold", "include_history": True},
    )
    assert history["count"] == 1


def test_rejections_are_structured_not_silent(tmp_path: Path) -> None:
    server_ = build_server(warehouse_path=_warehouse(tmp_path))

    bad_date = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "cold", "start_day": "March 3rd"},
    )
    assert bad_date["status"] == "rejected"
    assert "YYYY-MM-DD" in bad_date["reason"]

    first = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "cold", "start_day": "2026-03-03", "end_day": "2026-03-10"},
    )
    assert first["status"] == "recorded"
    overlap = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "cold", "start_day": "2026-03-08", "end_day": "2026-03-12"},
    )
    assert overlap["status"] == "rejected"
    assert "overlaps current episode" in overlap["reason"]

    stale_retract = _call(
        server_, "condition_episode_retract", {"episode_id": 999, "reason": "oops"}
    )
    assert stale_retract["status"] == "rejected"
    assert "does not exist" in stale_retract["reason"]


def test_ongoing_episode_recordable_but_not_analyzable(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    server_ = build_server(warehouse_path=warehouse)

    recorded = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "new med", "start_day": "2026-05-01"},
    )
    assert recorded["status"] == "recorded"
    assert recorded["episode"]["ongoing"] is True
    # Listable for record-keeping…
    assert _call(server_, "condition_episode_list", {})["count"] == 1
    # …but never part of the analysis read path.
    assert server.stored_condition_episodes("new med", warehouse_path=warehouse) == []


def test_supersede_through_mcp_keeps_history(tmp_path: Path) -> None:
    server_ = build_server(warehouse_path=_warehouse(tmp_path))
    original = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "med", "start_day": "2026-05-01"},
    )["episode"]["episode_id"]

    corrected = _call(
        server_,
        "condition_episode_record",
        {
            "condition_label": "med",
            "start_day": "2026-05-01",
            "end_day": "2026-06-01",
            "supersedes_episode_id": original,
        },
    )
    assert corrected["status"] == "recorded"
    assert corrected["superseded_episode_id"] == original

    current = _call(server_, "condition_episode_list", {"condition_label": "med"})
    assert [ep["episode_id"] for ep in current["episodes"]] == [corrected["episode"]["episode_id"]]


def test_list_on_pre_migration_warehouse_is_empty_not_crash(tmp_path: Path) -> None:
    import duckdb as duckdb_module

    bare = tmp_path / "bare.duckdb"
    duckdb_module.connect(str(bare)).close()  # no hp schema, no migrations
    payload = server.list_condition_episodes(warehouse_path=bare)
    assert payload == {
        "episodes": [],
        "count": 0,
        "condition_label": None,
        "include_history": False,
    }
    assert server.stored_condition_episodes("cold", warehouse_path=bare) == []


# --------------------------------------------------------------------------- #
# Consumption: stored declaration vs explicit declaration parity.
# --------------------------------------------------------------------------- #

_METRIC = "resting_hr"
_N = 90


def _series_base() -> datetime:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(hours=12)


def _episode_bounds() -> list[tuple[str, str]]:
    base = _series_base().date()
    ep1_start = base - timedelta(days=60)
    ep2_start = base - timedelta(days=30)
    return [
        (ep1_start.isoformat(), (ep1_start + timedelta(days=4)).isoformat()),
        (ep2_start.isoformat(), (ep2_start + timedelta(days=4)).isoformat()),
    ]


def _days_in(bounds: tuple[str, str]) -> set[date]:
    start = date.fromisoformat(bounds[0])
    end = date.fromisoformat(bounds[1])
    days = set()
    d = start
    while d <= end:
        days.add(d)
        d += timedelta(days=1)
    return days


def _warehouse_with_episodic_series(tmp_path: Path) -> Path:
    """A ~90-day daily series with a different lift on each on-condition window
    (mirrors the m8 MCP test fixture so both episodes pair cleanly)."""
    db_path = tmp_path / "condition.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    base = _series_base()
    ep_bounds = _episode_bounds()
    ep1_days = _days_in(ep_bounds[0])
    ep2_days = _days_in(ep_bounds[1])
    conn.execute("BEGIN")
    for i in range(_N):
        day = (base - timedelta(days=(_N - 1 - i))).date()
        ts = (base - timedelta(days=(_N - 1 - i))).isoformat(sep=" ")
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


def _episodes_payload() -> list[dict[str, str]]:
    return [{"start_day": s, "end_day": e} for s, e in _episode_bounds()]


def _pin_engine_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = _series_base() + timedelta(hours=6)
    monkeypatch.setattr(server.engine_query, "_naive_utc_now", lambda: fixed)


def _analysis_args(episodes: list[dict[str, str]] | None) -> dict[str, Any]:
    args: dict[str, Any] = {
        "metric_id": _METRIC,
        "condition_label": "on_magnesium",
        "before_days": 10,
        "after_days": 5,
        "expected_direction": "increase",
    }
    if episodes is not None:
        args["episodes"] = episodes
    return args


def test_stored_declaration_matches_explicit_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_engine_clock(monkeypatch)
    warehouse = _warehouse_with_episodic_series(tmp_path)
    server_ = build_server(warehouse_path=warehouse)

    recorded_ids = []
    for start, end in _episode_bounds():
        payload = _call(
            server_,
            "condition_episode_record",
            {"condition_label": "on_magnesium", "start_day": start, "end_day": end},
        )
        assert payload["status"] == "recorded"
        recorded_ids.append(payload["episode"]["episode_id"])

    explicit = _call(server_, "condition_paired_t_test", _analysis_args(_episodes_payload()))
    stored = _call(server_, "condition_paired_t_test", _analysis_args(None))

    # The wrapper-layer disclosure is the ONLY difference: engine envelopes are
    # byte-identical between hand-declared and stored declarations of one set.
    disclosure = stored.pop("episodes_source")
    assert explicit == stored
    assert explicit["status"] == "available"
    assert disclosure["kind"] == "stored_declaration"
    assert disclosure["condition_label"] == "on_magnesium"
    assert disclosure["episode_ids"] == recorded_ids
    assert disclosure["episodes"] == _episodes_payload()
    assert "episodes_source" not in explicit  # explicit path stays byte-identical


def test_empty_stored_declaration_flows_into_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_engine_clock(monkeypatch)
    warehouse = _warehouse_with_episodic_series(tmp_path)
    server_ = build_server(warehouse_path=warehouse)

    payload = _call(server_, "condition_paired_t_test", _analysis_args(None))
    assert payload["status"] == "refused"
    assert payload["episodes_source"]["kind"] == "stored_declaration"
    assert payload["episodes_source"]["episode_ids"] == []


def test_stored_consumption_skips_ongoing_and_retracted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_engine_clock(monkeypatch)
    warehouse = _warehouse_with_episodic_series(tmp_path)
    server_ = build_server(warehouse_path=warehouse)

    (ep1_start, ep1_end), (ep2_start, ep2_end) = _episode_bounds()
    kept = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "on_magnesium", "start_day": ep1_start, "end_day": ep1_end},
    )["episode"]["episode_id"]
    dropped = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "on_magnesium", "start_day": ep2_start, "end_day": ep2_end},
    )["episode"]["episode_id"]
    _call(server_, "condition_episode_retract", {"episode_id": dropped, "reason": "wrong"})
    ongoing = _call(
        server_,
        "condition_episode_record",
        {"condition_label": "on_magnesium", "start_day": ep2_start},
    )
    assert ongoing["status"] == "recorded"

    payload = _call(server_, "condition_paired_t_test", _analysis_args(None))
    assert payload["episodes_source"]["episode_ids"] == [kept]
    # One episode is below the declared-set minimum -> the normal refusal, with
    # the disclosure still naming exactly what was used.
    assert payload["status"] == "refused"
