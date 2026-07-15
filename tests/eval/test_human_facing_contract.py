"""Phase 5 slice 3: the ``human_facing`` role contract (HUMAN_FACING.md §Part A).

The role declaration is filled out from its one-liner into the four numbered
boundaries + the ``present_answer``-only surface. No new gate: the e2e fixtures
reuse the existing ``present_answer`` / ``answer_audit`` / ``record_profile_context``
surfaces unchanged. Synthetic warehouses / session logs only; no PHI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from premura import trace as trace_service
from premura.mcp import server
from premura.store import duck, profile_intake
from premura.ui.roles import get_role

# ----- helpers (mirror test_operating_roles_slice5.py) ------------------------ #


def _warehouse(tmp_path: Path) -> Path:
    db = tmp_path / "warehouse.duckdb"
    duck.initialize(db).close()
    return db


def _traced_session(warehouse: Path) -> str:
    """A session with one recorded available analytical call — an audit-passable base."""
    with server._open_warehouse_writable(warehouse) as conn:
        session = trace_service.open_research_session(conn, client_label="t")
        pending = trace_service.start_recorded_call(
            conn, session.session_id, "change_point", {"metric_id": "resting_hr"}
        )
        assert isinstance(pending, trace_service.PendingCall)
        trace_service.finish_recorded_call(
            conn,
            pending,
            terminal_status=trace_service.STATUS_AVAILABLE,
            result={"status": "available"},
        )
    return session.session_id


# ----- Part A: the role declaration ------------------------------------------- #


def test_human_facing_carries_the_four_boundaries_and_present_answer_surface() -> None:
    role = get_role("human_facing")
    assert role is not None, "human_facing must be registered"

    # Exactly the four numbered boundaries of HUMAN_FACING.md §Part A.
    assert len(role.boundaries) == 4, "expected the four numbered boundaries"
    joined = " ".join(role.boundaries).lower()
    # 1: present only through present_answer.
    assert "present_answer" in role.boundaries[0]
    # 2: never diagnose / name a cause / invent an effect.
    assert "diagnos" in joined and "cause" in joined
    # 3: never silently store lifestyle context; one allowlisted fact at a time.
    assert "silently store" in joined and "one allowlisted fact" in joined
    # 4: never off-machine / public GitHub.
    assert "off-machine" in joined and "github" in joined

    # The present_answer-only surface is granted.
    surfaces = " ".join(role.surfaces)
    assert "present_answer" in surfaces
    assert "record_profile_context" in surfaces

    # Analytical / warehouse / SQL surfaces are ABSENT from the granted surfaces.
    forbidden = ("analytical", "warehouse", "sql")
    assert not any(tok in surfaces.lower() for tok in forbidden), (
        f"human_facing must not be granted analytical/warehouse/SQL surfaces: {role.surfaces}"
    )


# ----- e2e fixture 1: health-interpreting draft reaches the human only through
#       present_answer; a bypass is refused by the existing gate (not forked). -- #


def test_bypass_of_present_answer_is_refused_and_sanctioned_path_presents(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    draft = "Your resting heart rate trended down over the logged month."

    # Bypass attempt: present a health-interpreting draft with no passing audit.
    bypass = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert bypass["status"] == "refused", "the existing gate must refuse an unaudited health draft"

    # Sanctioned path: audit first (passes on an unmarked draft over a traced session),
    # then the same gate presents.
    verdict = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "passed"
    presented = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert presented["status"] == "presented" and presented["verified"] is True


# ----- e2e fixture 2: lifestyle-context capture is a proposal requiring
#       confirmation; an unconfirmed capture stores nothing (no allowlist write). #


def test_unconfirmed_capture_stores_nothing_only_confirmed_write_persists(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)

    def _stored(key: str) -> Any:
        with server._open_warehouse_writable(warehouse) as conn:
            return profile_intake.get_current_profile(conn, key)

    # A proposal the human has not confirmed = no record_profile_context call = nothing stored.
    assert _stored("sex") is None, "nothing may be stored before a confirmed capture"

    # An unsupported/derived key is a visible rejection that also stores nothing.
    rejected = server.record_profile_context("age", 41, warehouse_path=warehouse)
    assert rejected["status"] == "rejected"
    assert _stored("sex") is None

    # Only an explicit, confirmed capture of an allowlisted fact writes.
    recorded = server.record_profile_context("sex", "female", warehouse_path=warehouse)
    assert recorded["status"] == "recorded"
    assert _stored("sex") is not None, "the confirmed allowlisted fact must persist"


# ----- real e2e: draft narration through answer_audit -> present_answer with the
#       revision loop honoring answer_audit > analysis > human_facing. ---------- #


def test_revision_loop_honors_fixed_priority(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)

    # A first narration that overreaches on the trace (marks a claim to a call this
    # session never recorded) fails the audit gate.
    bad = "This rests on analysis that was never run [trace: call_deadbeef]."
    bad_verdict = server.answer_audit(
        bad, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert bad_verdict["status"] == "failed"

    # The gate refuses it and routes it back for the one revision loop, naming the
    # fixed priority — comprehensibility never overrides evidence.
    refused = server.present_answer(bad, interprets_health=True, session_log_path=log)
    assert refused["status"] == "refused"
    assert "answer_audit > analysis > human_facing" in refused["revision_path"]

    # The revised narration (a new hash) drops the unsupported claim, re-audits clean,
    # and the same gate now presents it.
    revised = "Your resting heart rate trended down over the logged month."
    revised_verdict = server.answer_audit(
        revised, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert revised_verdict["status"] == "passed"
    presented = server.present_answer(revised, interprets_health=True, session_log_path=log)
    assert presented["status"] == "presented" and presented["verified"] is True
