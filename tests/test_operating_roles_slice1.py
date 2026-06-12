"""Slice 1 of OPERATING_ROLES.md: registry, handoff trace, blocking gate.

Synthetic warehouses and session logs only. Locks: the bounded role registry
(five reference instances + the rule for adding one), the handoff trace in
the session-log store (never the research trace), and the structural gate —
no verified envelope without a passing audit for exactly that draft.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from premura.mcp import entrypoint, server
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


def _traced_session(warehouse: Path) -> str:
    """Open a research session with one recorded (refused) analytical call."""
    from premura import trace as trace_service

    with server._open_warehouse_writable(warehouse) as conn:
        session = trace_service.open_research_session(conn, client_label="t")
        pending = trace_service.start_recorded_call(
            conn, session.session_id, "change_point", {"metric_id": "resting_hr"}
        )
        trace_service.finish_recorded_call(
            conn, pending, terminal_status="refused", refusal_reason="insufficient_data"
        )
    return session.session_id


def test_malformed_drafts_are_structured_rejections(tmp_path: Path) -> None:
    """Bad input is a branchable ``rejected`` response, never a raised error.

    The same error model as ``orchestrator_handoff``; the lone surrogate pins
    the path that previously escaped as ``UnicodeEncodeError`` from the
    sha256 keying.
    """
    log = tmp_path / "session_log.duckdb"
    for bad in ("", "   ", "x\ud800y"):
        verdict = server.answer_audit(bad, session_log_path=log)
        assert verdict["status"] == "rejected" and verdict["reason"]
        gate = server.present_answer(bad, interprets_health=True, session_log_path=log)
        assert gate["status"] == "rejected" and gate["reason"]


def test_latest_verdict_governs_either_direction(tmp_path: Path) -> None:
    """The newest audit of a draft hash wins: a later FAIL revokes, a later PASS re-blesses."""
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    draft = "The trace cannot support a level-shift conclusion yet."

    passing = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert passing["status"] == "passed"
    assert server.present_answer(draft, interprets_health=True, session_log_path=log)["verified"]

    # Re-audit the same draft without a session: the newer FAIL revokes the PASS.
    failing = server.answer_audit(draft, warehouse_path=warehouse, session_log_path=log)
    assert failing["status"] == "failed"
    revoked = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert revoked["status"] == "refused"

    # A still-newer passing audit (real traced session required) re-blesses.
    server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    again = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert again["status"] == "presented" and again["verified"] is True


def test_new_role_registers_with_no_central_edit(tmp_path: Path) -> None:
    """The open-registry claim: a sixth role works end to end without editing core code."""
    log = tmp_path / "session_log.duckdb"
    declaration = roles.RoleDeclaration(
        role_id="lifestyle_capture",
        job="Capture consented lifestyle context through the bounded intake seam.",
        boundaries=("never stores context without explicit consent",),
    )
    roles.register_role(declaration)
    try:
        listed = {r["role_id"] for r in server.operating_roles()["roles"]}
        assert "lifestyle_capture" in listed
        out = server.orchestrator_handoff(
            "sess-6",
            "orchestrator",
            "lifestyle_capture",
            "capture declared context",
            "dispatched",
            session_log_path=log,
        )
        assert out["status"] == "recorded"
        assert out["unregistered_ids"] is None  # recognized, not a phantom role
    finally:
        roles._REGISTRY.pop("lifestyle_capture", None)


def test_orchestrator_records_never_touch_research_trace(tmp_path: Path) -> None:
    """Row-count proof that handoffs/audits stay out of trace.* (multiplicity intact)."""
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    draft = "Sleep looked different in the declared window."

    def trace_counts() -> tuple[int, int]:
        with server._open_warehouse(warehouse) as conn:
            calls = conn.execute("SELECT count(*) FROM trace.tool_call").fetchone()
            sessions = conn.execute("SELECT count(*) FROM trace.research_session").fetchone()
        assert calls is not None and sessions is not None
        return calls[0], sessions[0]

    before = trace_counts()
    for status in ("dispatched", "returned", "refused"):
        server.orchestrator_handoff(
            "sess-c",
            "orchestrator",
            "analysis",
            "declared comparison",
            status,
            session_log_path=log,
        )
    server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert trace_counts() == before


# ----- through the real MCP surface (FastMCP.call_tool) ----------------------- #


def _call(mcp: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool through the MCP boundary and return its structured payload."""

    async def run() -> dict[str, Any]:
        _content, structured = await mcp.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def test_gate_e2e_through_mcp_surface_with_threaded_session_log(tmp_path: Path) -> None:
    """Drive all four orchestrator tools as a connected agent would.

    Also the regression pin for session-log threadability: every record must
    land in the ``session_log_path`` given to ``build_server``, so a sandboxed
    server never writes into the operator's real session log.
    """
    warehouse = _warehouse(tmp_path)
    log = tmp_path / "threaded_session_log.duckdb"
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    assert _call(mcp, "operating_roles", {})["count"] >= 5

    recorded = _call(
        mcp,
        "orchestrator_handoff",
        {
            "runtime_session_id": "sess-e2e",
            "from_id": "orchestrator",
            "to_id": "analysis",
            "task_summary": "run declared comparison",
            "status": "dispatched",
        },
    )
    assert recorded["status"] == "recorded"

    draft = "Your resting heart rate shifted after the declared change."
    refused = _call(mcp, "present_answer", {"draft": draft, "interprets_health": True})
    assert refused["status"] == "refused"

    failed = _call(mcp, "answer_audit", {"draft": draft})
    assert failed["status"] == "failed"

    warned = _call(
        mcp,
        "present_answer",
        {"draft": draft, "interprets_health": True, "acknowledge_unverified": True},
    )
    assert warned["verified"] is False and "NOT TRACE-VERIFIED" in warned["warning"]

    session_id = _traced_session(warehouse)
    passed = _call(mcp, "answer_audit", {"draft": draft, "session_id": session_id})
    assert passed["status"] == "passed"
    blessed = _call(mcp, "present_answer", {"draft": draft, "interprets_health": True})
    assert blessed["verified"] is True
    assert blessed["disclosure"] == passed["disclosure"]

    # Malformed input through the surface is a structured rejection, not a ToolError.
    assert _call(mcp, "answer_audit", {"draft": "   "})["status"] == "rejected"

    # Everything above landed in the threaded session-log file.
    assert log.exists()
    with sl.connect(log, read_only=True) as conn:
        rows = sl.list_handoffs(conn, runtime_session_id="sess-e2e")
    assert [r["status"] for r in rows] == ["dispatched"]
