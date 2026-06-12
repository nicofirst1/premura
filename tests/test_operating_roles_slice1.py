"""Slice 1 of OPERATING_ROLES.md: registry, handoff trace, blocking gate.

Synthetic warehouses and session logs only. Locks: the bounded role registry
(five reference instances + the rule for adding one), the handoff trace in
the session-log store (never the research trace), and the structural gate —
no verified envelope without a passing audit for exactly that draft.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from premura.mcp import server
from premura.session_log import store as sl
from premura.store import duck
from premura.ui import roles

# ----- registry -------------------------------------------------------------- #


def test_reference_roles_registered() -> None:
    ids = [r.role_id for r in roles.list_roles()]
    assert ids == sorted(ids)
    assert {"ingest", "analysis", "human_facing", "answer_audit", "improvement_scan"} <= set(ids)


def test_registry_rules_reject_bad_declarations() -> None:
    with pytest.raises(ValueError, match="non-empty role_id"):
        roles.RoleDeclaration(role_id=" ", job="x").validate()
    with pytest.raises(ValueError, match="lowercase functional identifier"):
        roles.RoleDeclaration(role_id="The Librarian", job="x").validate()
    with pytest.raises(ValueError, match="already registered"):
        roles.register_role(roles.RoleDeclaration(role_id="ingest", job="dup"))


def test_operating_roles_tool_lists_declarations() -> None:
    payload = server.operating_roles()
    assert payload["count"] >= 5
    by_id = {r["role_id"]: r for r in payload["roles"]}
    assert "creates no new evidence" in by_id["answer_audit"]["boundaries"]


# ----- handoff trace ---------------------------------------------------------- #


def test_handoff_round_trip_and_vocabulary(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    out = server.orchestrator_handoff(
        "sess-1",
        "orchestrator",
        "analysis",
        "run declared comparison",
        "dispatched",
        session_log_path=log,
    )
    assert out["status"] == "recorded"
    assert out["unregistered_ids"] is None
    bad = server.orchestrator_handoff(
        "sess-1", "orchestrator", "analysis", "x", "exploded", session_log_path=log
    )
    assert bad["status"] == "rejected" and "status must be one of" in bad["reason"]
    typo = server.orchestrator_handoff(
        "sess-1", "orchestraator", "analysis", "x", "returned", session_log_path=log
    )
    assert typo["unregistered_ids"] == ["orchestraator"]

    with sl.connect(log, read_only=True) as conn:
        rows = sl.list_handoffs(conn, runtime_session_id="sess-1")
    assert [r["status"] for r in rows] == ["dispatched", "returned"]
    assert rows[0]["to_id"] == "analysis"


# ----- the blocking gate ------------------------------------------------------ #


def _warehouse(tmp_path: Path) -> Path:
    db = tmp_path / "warehouse.duckdb"
    duck.initialize(db).close()
    return db


def test_no_envelope_without_audit(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    refused = server.present_answer(
        "Your HRV rose after magnesium.", interprets_health=True, session_log_path=log
    )
    assert refused["status"] == "refused"
    assert "call answer_audit" in refused["reason"]


def test_non_interpreting_draft_passes_through_unverified(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    out = server.present_answer("Loaded 412 rows.", interprets_health=False, session_log_path=log)
    assert out["status"] == "presented" and out["verified"] is False
    assert out["interprets_health"] is False


def test_audit_without_session_fails_and_gate_offers_unverified_path(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    draft = "Your sleep looked different on magnesium."
    verdict = server.answer_audit(draft, session_log_path=log, warehouse_path=_warehouse(tmp_path))
    assert verdict["status"] == "failed" and verdict["trace_verified"] is False
    assert any("session_id" in f for f in verdict["failures"])

    refused = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert refused["status"] == "refused"
    assert refused["audit_failures"]
    assert "human_facing" in refused["revision_path"]

    warned = server.present_answer(
        draft, interprets_health=True, acknowledge_unverified=True, session_log_path=log
    )
    assert warned["status"] == "presented" and warned["verified"] is False
    assert "NOT TRACE-VERIFIED" in warned["warning"]


def test_traced_session_passes_and_envelope_carries_measured_disclosure(tmp_path: Path) -> None:
    from premura import trace as trace_service

    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    with server._open_warehouse_writable(warehouse) as conn:
        session = trace_service.open_research_session(conn, client_label="t")
        pending = trace_service.start_recorded_call(
            conn, session.session_id, "change_point", {"metric_id": "resting_hr"}
        )
        trace_service.finish_recorded_call(
            conn, pending, terminal_status="refused", refusal_reason="insufficient_data"
        )

    draft = "The data cannot support a level-shift conclusion yet."
    verdict = server.answer_audit(
        draft, session_id=session.session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "passed" and verdict["trace_verified"] is True
    assert verdict["refusal_count"] == 1
    assert verdict["disclosure"]

    blessed = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert blessed["status"] == "presented" and blessed["verified"] is True
    assert blessed["disclosure"] == verdict["disclosure"]  # measured, attached by the gate
    assert blessed["refusal_count"] == 1
    assert blessed["caveats"]

    # A revised draft is a new hash: the old verdict must not bless it.
    revised = server.present_answer(
        draft + " Revised.", interprets_health=True, session_log_path=log
    )
    assert revised["status"] == "refused"
