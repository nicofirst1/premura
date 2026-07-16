"""Phase 5 slice 2: the ``interview_route`` MCP tool + engine-backed resolver wiring.

Locks the interview phase-1 (Direction) routing surface over the #41 track
registry:

* the engine-backed resolver is actually installed — a track admits only routes
  the engine signal selector resolves; a synthetic no-signal route is refused
  through the LIVE resolver, not the module's default-deny stub;
* ``interview_route`` resolves a seeded direction to its route + required slots,
  and reports ``missing_slots`` against the closed profile allowlist;
* an unresolvable direction is refused with the registry's dead-end message —
  the routing decision never fabricates a route (interview-before-metrics);
* the tool writes NO profile fact;
* the real end-to-end grounding loop: resolve → read ``missing_slots`` → capture
  one fact → re-resolve shows the slot filled;
* ``interview_route`` is registered on the live default MCP surface.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from premura.mcp import server
from premura.mcp.entrypoint import build_server
from premura.store import duck
from premura.ui import interview_tracks as it


@pytest.fixture(autouse=True)
def _isolate_registry():
    """The interview-track registry is a mutable module global. Each test starts
    from import state (empty registry, reject-all resolver, unseeded) and restores
    it afterwards."""
    saved_reg = dict(it._REGISTRY)
    saved_resolver = it._route_resolver
    saved_seeded = it._seeded
    it._REGISTRY.clear()
    it._route_resolver = it._reject_all
    it._seeded = False
    try:
        yield
    finally:
        it._REGISTRY.clear()
        it._REGISTRY.update(saved_reg)
        it._route_resolver = saved_resolver
        it._seeded = saved_seeded


def _warehouse(tmp_path: Path) -> Path:
    """Initialize an empty warehouse (migrations applied) and return its path."""
    db_path = tmp_path / "interview.duckdb"
    duck.initialize(db_path).close()
    return db_path


# --------------------------------------------------------------------------- #
# Resolver installation
# --------------------------------------------------------------------------- #
def test_resolver_installed_admits_only_engine_routes() -> None:
    """The live resolver (not the default-deny stub) admits ``sleep`` (a real
    signal domain) and refuses a synthetic route with no signals behind it."""
    server.install_interview_route_resolver()

    assert it._route_resolver is not it._reject_all
    assert it._route_resolver("signal_selector:sleep") is True
    assert it._route_resolver("signal_selector:florbleep") is False
    # Malformed / non-selector routes never resolve.
    assert it._route_resolver("sleep") is False
    assert it._route_resolver("signal_selector:") is False


def test_synthetic_no_signal_track_refused_through_live_resolver() -> None:
    """A track whose route has no signals is refused at registration by the LIVE
    resolver — the safety rail, not the default-deny stub, does the refusing."""
    server.install_interview_route_resolver()
    with pytest.raises(ValueError, match=r"signal_selector:hydration"):
        it.register_track(
            it.InterviewTrack(
                track_id="hydration_deep_dive",
                signal_route="signal_selector:hydration",
            )
        )
    assert it.get_track("hydration_deep_dive") is None


def test_stages8_seed_admits_only_resolvable_directions() -> None:
    """Seeding offers all STAGES-8 but the safety rail admits only directions with
    a live signal selector behind them — a dead-end seed is skipped, not crashed
    on. ``sleep`` (a real signal domain) is admitted."""
    server.install_interview_route_resolver()
    admitted = it.known_track_ids()
    assert "sleep" in admitted
    # cardio is interview vocabulary but its signals register under the engine
    # "cardiovascular" domain; the route must bridge that gap or the track dies.
    assert "cardio" in admitted
    assert it.get_track("cardio").signal_route == "signal_selector:cardiovascular"
    assert admitted <= set(it._STAGES8)  # never invents a direction outside the seeds


# --------------------------------------------------------------------------- #
# interview_route: resolve, refuse, missing_slots
# --------------------------------------------------------------------------- #
def test_route_sleep_returns_seeded_route(tmp_path: Path) -> None:
    server.install_interview_route_resolver()
    result = server.interview_route("sleep", warehouse_path=_warehouse(tmp_path))
    assert result["status"] == "routed"
    assert result["track_id"] == "sleep"
    assert result["signal_route"] == "signal_selector:sleep"
    assert result["required_slots"] == []
    assert result["missing_slots"] == []


def test_unresolvable_direction_refused_never_fabricates_route() -> None:
    """e2e spec-named edge case: routing an unresolvable direction is refused with
    the dead-end message and yields NO route — the no-dead-end invariant."""
    server.install_interview_route_resolver()
    result = server.interview_route("hydration")
    assert result["status"] == "refused"
    assert result["direction"] == "hydration"
    assert "does not resolve" in result["reason"]
    assert "signal_route" not in result
    assert "track_id" not in result
    assert it.get_track("hydration") is None


def test_blank_direction_refused() -> None:
    server.install_interview_route_resolver()
    assert server.interview_route("   ")["status"] == "refused"


def test_missing_slots_reflects_unset_allowlist_facts(tmp_path: Path) -> None:
    """``missing_slots`` is the track's required slots that are allowlisted profile
    facts still unset; a required slot outside the allowlist is not proposed."""
    server.install_interview_route_resolver()
    # A track that resolves (route behind sleep) but declares grounding slots.
    it.register_track(
        it.InterviewTrack(
            track_id="sleep_grounded",
            signal_route="signal_selector:sleep",
            required_slots=("sex", "not_a_profile_field"),
        )
    )
    result = server.interview_route("sleep_grounded", warehouse_path=_warehouse(tmp_path))
    assert result["required_slots"] == ["sex", "not_a_profile_field"]
    assert result["missing_slots"] == ["sex"]  # allowlisted + unset; the other is skipped


# --------------------------------------------------------------------------- #
# The tool writes no profile fact
# --------------------------------------------------------------------------- #
def test_route_writes_no_profile_fact(tmp_path: Path) -> None:
    """A route call proposes slots but never asserts one — no
    ``hp.profile_context_assertion`` row is written."""
    warehouse = _warehouse(tmp_path)
    server.install_interview_route_resolver()
    it.register_track(
        it.InterviewTrack(
            track_id="sleep_grounded",
            signal_route="signal_selector:sleep",
            required_slots=("sex",),
        )
    )
    server.interview_route("sleep_grounded", warehouse_path=warehouse)
    conn = duck.connect(warehouse, read_only=True)
    try:
        row = conn.execute("SELECT COUNT(*) FROM hp.profile_context_assertion").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == 0


# --------------------------------------------------------------------------- #
# Real end-to-end grounding loop (acceptance: resolve -> capture -> re-resolve)
# --------------------------------------------------------------------------- #
def test_e2e_missing_slot_fills_after_capture(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    server.install_interview_route_resolver()
    it.register_track(
        it.InterviewTrack(
            track_id="sleep_grounded",
            signal_route="signal_selector:sleep",
            required_slots=("sex",),
        )
    )
    before = server.interview_route("sleep_grounded", warehouse_path=warehouse)
    assert before["missing_slots"] == ["sex"]

    captured = server.record_profile_context("sex", "male", warehouse_path=warehouse)
    assert captured["status"] == "recorded"

    after = server.interview_route("sleep_grounded", warehouse_path=warehouse)
    assert after["missing_slots"] == []


# --------------------------------------------------------------------------- #
# Live surface registration
# --------------------------------------------------------------------------- #
def test_interview_route_registered_on_default_surface() -> None:
    srv = build_server()
    names = {tool.name for tool in asyncio.run(srv.list_tools())}
    assert "interview_route" in names
