"""Slice 5 of OPERATING_ROLES.md: claim-to-trace binding (ADR 0014).

Synthetic warehouses, session logs, and service-built trace sessions only (no
network). Locks the deterministic extractor-and-query pair that stands beside
check 5's citation binding — never a fork of the audit flow:

* the marker extractor — a claim marked in the draft prose with a
  ``[trace: <call_id>]`` suffix carries the recorded call(s) it rests on;
* the per-marker trace query — a marked ``call_id`` binds only if this session
  recorded that call finishing ``available`` (any ``call_kind``);
* the audit wiring — an unbindable marked claim fails the gate, naming the id,
  and the disclosure line scopes itself to "recognized marker forms".
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from premura import trace as trace_service
from premura.mcp import entrypoint, server
from premura.store import duck

# ----- helpers ---------------------------------------------------------------- #


def _warehouse(tmp_path: Path) -> Path:
    db = tmp_path / "warehouse.duckdb"
    duck.initialize(db).close()
    return db


def _open_session(warehouse: Path) -> str:
    with server._open_warehouse_writable(warehouse) as conn:
        session = trace_service.open_research_session(conn, client_label="t")
    return session.session_id


def _record(
    warehouse: Path,
    session_id: str,
    tool_name: str,
    request: dict[str, Any],
    *,
    call_kind: str = trace_service.CALL_KIND_ANALYTICAL,
    terminal_status: str = trace_service.STATUS_AVAILABLE,
    refusal_reason: str | None = None,
) -> trace_service.RecordedCall:
    with server._open_warehouse_writable(warehouse) as conn:
        pending = trace_service.start_recorded_call(
            conn, session_id, tool_name, request, call_kind=call_kind
        )
        assert isinstance(pending, trace_service.PendingCall)
        recorded = trace_service.finish_recorded_call(
            conn,
            pending,
            terminal_status=terminal_status,
            refusal_reason=refusal_reason,
            result={"status": "available"} if terminal_status == "available" else None,
        )
        assert isinstance(recorded, trace_service.RecordedCall)
    return recorded


def _available_call(warehouse: Path, session_id: str, metric_id: str = "resting_hr") -> str:
    """A recorded analytical call that finished ``available`` — a bindable id."""
    return _record(warehouse, session_id, "change_point", {"metric_id": metric_id}).call_id


# ----- FR-1: the marker extractor --------------------------------------------- #


def test_marker_extractor_covers_the_documented_form() -> None:
    assert server._extract_claim_trace_refs("Resting HR fell [trace: call_ab12].") == {"call_ab12"}
    # A multi-id marker yields every id it lists.
    assert server._extract_claim_trace_refs(
        "Both moved together [trace: call_ab12, call_cd34]."
    ) == {"call_ab12", "call_cd34"}
    # Text with no marker yields the empty set.
    assert server._extract_claim_trace_refs("Sleep improved this month.") == set()


def test_marker_extractor_fails_closed_and_ignores_non_call_tokens() -> None:
    # Generous matching: flexible spacing and case inside the bracket.
    assert server._extract_claim_trace_refs("[TRACE:  call_ab12 ]") == {"call_ab12"}
    # A malformed / non-``call_`` token in the marker is simply not matched.
    assert server._extract_claim_trace_refs("[trace: sess_9, note, call_ab12]") == {"call_ab12"}
    assert server._extract_claim_trace_refs("[trace: not-an-id]") == set()
    # Two markers across the prose both contribute.
    assert server._extract_claim_trace_refs("First [trace: call_aa]. Second [trace: call_bb].") == {
        "call_aa",
        "call_bb",
    }


# ----- FR-2: the per-marker trace query --------------------------------------- #


def test_bound_claim_calls_binds_only_in_session_available_calls(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)
    other_id = _open_session(warehouse)

    ok = _available_call(warehouse, session_id)
    # An evidence-source row that finished available still binds (no call_kind filter).
    evidence = _record(
        warehouse,
        session_id,
        trace_service.PUBMED_FETCH_TOOL_NAME,
        {"pmid": "11111"},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
    ).call_id
    refused = _record(
        warehouse,
        session_id,
        "change_point",
        {"metric_id": "hrv"},
        terminal_status="refused",
        refusal_reason="insufficient_data",
    ).call_id
    errored = _record(
        warehouse,
        session_id,
        "change_point",
        {"metric_id": "steps"},
        terminal_status="error",
    ).call_id
    from_other = _available_call(warehouse, other_id, metric_id="weight")

    refs = {ok, evidence, refused, errored, from_other, "call_deadbeef"}
    with server._open_warehouse(warehouse) as conn:
        bound = trace_service.bound_claim_calls(conn, session_id, refs)
    assert bound == {ok, evidence}


def test_bound_claim_calls_session_shapes(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)
    with server._open_warehouse(warehouse) as conn:
        unknown = trace_service.bound_claim_calls(conn, "no-such-session", {"call_x"})
        # A valid session that binds nothing is an empty set, distinct from not_found.
        nothing = trace_service.bound_claim_calls(conn, session_id, {"call_x"})
        # No markers at all: empty set without a scan.
        no_refs = trace_service.bound_claim_calls(conn, session_id, set())
    assert isinstance(unknown, trace_service.TraceError) and unknown.status == "not_found"
    assert nothing == set()
    assert no_refs == set()


# ----- FR-3 + FR-4: binding through the audit gate ---------------------------- #


def _traced_session(warehouse: Path) -> str:
    """A session that satisfies check 1 (one recorded available analytical call)."""
    session_id = _open_session(warehouse)
    _available_call(warehouse, session_id)
    return session_id


def test_marked_and_bound_claim_passes_and_discloses(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)
    call_id = _available_call(warehouse, session_id)

    draft = f"Resting heart rate dropped after the change [trace: {call_id}]."
    verdict = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "passed"
    assert (
        "claims: 1 marked claim(s) (recognized forms), all bound this session"
        in verdict["disclosure"]
    )


def test_unbindable_marked_claim_fails_naming_the_id(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)

    draft = "This rests on nothing real [trace: call_deadbeef]."
    verdict = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "failed"
    assert any("call_deadbeef" in f and "do not bind" in f for f in verdict["failures"])
    assert "claims: 1 marked claim(s) (recognized forms), 1 not bound this session" in (
        verdict["disclosure"] or ""
    )


def test_unmarked_draft_binding_contributes_no_failures(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)

    verdict = server.answer_audit(
        "No claim in this answer names a trace ref.",
        session_id=session_id,
        warehouse_path=warehouse,
        session_log_path=log,
    )
    assert verdict["status"] == "passed"
    assert not any("bind" in f for f in verdict["failures"])
    assert "claims: none in the recognized marker forms" in verdict["disclosure"]


def test_refused_and_cross_session_marks_both_fail(tmp_path: Path) -> None:
    """A marker to a refused in-session call and to a call from another session both fail."""
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    refused = _record(
        warehouse,
        session_id,
        "change_point",
        {"metric_id": "hrv"},
        terminal_status="refused",
        refusal_reason="insufficient_data",
    ).call_id
    other = _available_call(warehouse, _open_session(warehouse), metric_id="weight")

    draft = f"Two shaky claims [trace: {refused}, {other}]."
    verdict = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "failed"
    assert any(refused in f and other in f for f in verdict["failures"])


def test_marking_without_a_session_names_the_binding_problem(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    verdict = server.answer_audit(
        "Backed by analysis [trace: call_ab12].",
        warehouse_path=_warehouse(tmp_path),
        session_log_path=log,
    )
    assert verdict["status"] == "failed"
    assert any(
        "marks claims" in f and "names no research-trace session" in f for f in verdict["failures"]
    )


# ----- the spec-named e2e through the live MCP surface ------------------------ #


def _call(mcp: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await mcp.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def test_e2e_marked_bound_draft_presents_and_unbindable_refuses(tmp_path: Path) -> None:
    """End to end through the real MCP surface: bind → audit → envelope, and the fail path."""
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)
    call_id = _available_call(warehouse, session_id)
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    # (a) a draft whose marker binds to a real in-session available call passes and presents.
    good = f"Resting HR fell after the change [trace: {call_id}]."
    verdict = _call(mcp, "answer_audit", {"draft": good, "session_id": session_id})
    assert verdict["status"] == "passed"
    blessed = _call(mcp, "present_answer", {"draft": good, "interprets_health": True})
    assert blessed["verified"] is True
    assert "all bound this session" in blessed["disclosure"]

    # (b) a draft with a marked-but-unbindable claim fails, naming the id, and is refused.
    bad = "This claim rests on nothing [trace: call_deadbeef]."
    bad_verdict = _call(mcp, "answer_audit", {"draft": bad, "session_id": session_id})
    assert bad_verdict["status"] == "failed"
    assert any("call_deadbeef" in f for f in bad_verdict["failures"])
    refused = _call(mcp, "present_answer", {"draft": bad, "interprets_health": True})
    assert refused["status"] == "refused"
