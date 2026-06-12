"""Slice 2 of OPERATING_ROLES.md: PubMed citation binding.

Synthetic warehouses, session logs, and canned provider outcomes only (no
network). Locks the two halves that must land together:

* evidence-source recording — PubMed lookups join the research trace through
  the same record → dispatch → finalize seam as the analytical tools, as
  ``call_kind = evidence_source`` rows that NEVER count toward the
  multiplicity disclosure ("N unique hypotheses examined" stays purely
  analytical);
* the deterministic citation check — every PMID a draft cites must have a
  successful in-session ``pubmed_fetch``; search candidates and failed
  fetches are never citeable.
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


def _fetched_evidence(warehouse: Path, session_id: str, pmid: str) -> trace_service.RecordedCall:
    return _record(
        warehouse,
        session_id,
        trace_service.PUBMED_FETCH_TOOL_NAME,
        {"pmid": pmid},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
    )


# ----- call kinds in the trace store ------------------------------------------ #


def test_call_kind_recorded_and_validated(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)
    recorded = _fetched_evidence(warehouse, session_id, "12345")
    assert recorded.call_kind == "evidence_source"
    assert recorded.to_dict()["call_kind"] == "evidence_source"

    with server._open_warehouse_writable(warehouse) as conn:
        stored = conn.execute(
            "SELECT call_kind FROM trace.tool_call WHERE call_id = ?", [recorded.call_id]
        ).fetchone()
        assert stored is not None and stored[0] == "evidence_source"

        bad = trace_service.start_recorded_call(
            conn, session_id, "pubmed_fetch", {"pmid": "1"}, call_kind="vibes"
        )
        assert isinstance(bad, trace_service.TraceError)
        assert bad.status == "validation_error" and bad.field == "call_kind"

        # The default stays analytical — pre-slice-2 callers are unchanged.
        pending = trace_service.start_recorded_call(
            conn, session_id, "change_point", {"metric_id": "resting_hr"}
        )
        assert isinstance(pending, trace_service.PendingCall)
        assert pending.call_kind == "analytical"


def test_migration_backfills_existing_rows_as_analytical(tmp_path: Path) -> None:
    """The true upgrade path: rows that PRE-DATE migration 008 read back analytical.

    Builds the genuine pre-008 schema (migrations 001-007 only), inserts a row
    the old way, then runs the full migration set as any writable open does —
    pinning that the ALTER's DEFAULT backfills the existing row.
    """
    import duckdb

    conn = duckdb.connect(str(tmp_path / "pre008.duckdb"))
    try:
        for path in sorted(duck._migration_paths()):
            if path.name.startswith("008"):
                continue
            conn.execute(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO trace.research_session (session_id, started_at_utc) VALUES ('s', now())"
        )
        conn.execute(
            """
            INSERT INTO trace.tool_call
                (call_id, session_id, tool_name, request_hash, hypothesis_identity,
                 started_at_utc)
            VALUES ('legacy-1', 's', 'change_point', 'h', 'i', now())
            """
        )
        duck.run_migrations(conn)
        row = conn.execute(
            "SELECT call_kind FROM trace.tool_call WHERE call_id = 'legacy-1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == "analytical"


# ----- multiplicity disclosure stays purely analytical ------------------------- #


def test_evidence_rows_never_count_toward_disclosure(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)

    _record(warehouse, session_id, "change_point", {"metric_id": "resting_hr"})
    _record(
        warehouse,
        session_id,
        "correlate",
        {"metric_a": "sleep", "metric_b": "hr"},
        terminal_status="refused",
        refusal_reason="insufficient_data",
    )
    # Evidence rows in every terminal state, plus a search.
    _fetched_evidence(warehouse, session_id, "12345")
    _record(
        warehouse,
        session_id,
        trace_service.PUBMED_FETCH_TOOL_NAME,
        {"pmid": "99999"},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
        terminal_status="refused",
        refusal_reason="unavailable",
    )
    _record(
        warehouse,
        session_id,
        "pubmed_search",
        {"query": "magnesium sleep", "sort": None},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
    )

    with server._open_warehouse(warehouse) as conn:
        disclosure = trace_service.get_research_disclosure(conn, session_id)
    assert isinstance(disclosure, trace_service.TraceDisclosure)
    assert disclosure.raw_analytical_call_count == 2
    assert disclosure.unique_hypothesis_count == 2
    # The evidence fetch that came back "unavailable" is not an analytical refusal.
    assert disclosure.refusal_breakdown == {"insufficient_data": 1}
    assert {c.tool_name for c in disclosure.calls} == {"change_point", "correlate"}


def test_mark_surfaced_refuses_evidence_rows(tmp_path: Path) -> None:
    """K counts analytical findings; a literature lookup cannot be one."""
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)
    evidence = _fetched_evidence(warehouse, session_id, "12345")
    with server._open_warehouse_writable(warehouse) as conn:
        out = trace_service.mark_surfaced(
            conn, session_id, evidence.call_id, role="claim", rationale="cited in answer"
        )
    assert isinstance(out, trace_service.TraceError)
    assert out.status == "validation_error" and "evidence-source" in out.message


# ----- the citeable set -------------------------------------------------------- #


def test_fetched_citation_pmids_is_exactly_the_successful_fetches(tmp_path: Path) -> None:
    warehouse = _warehouse(tmp_path)
    session_id = _open_session(warehouse)

    _fetched_evidence(warehouse, session_id, "11111")
    # A failed fetch and a search candidate must NOT become citeable.
    _record(
        warehouse,
        session_id,
        trace_service.PUBMED_FETCH_TOOL_NAME,
        {"pmid": "22222"},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
        terminal_status="refused",
        refusal_reason="invalid_pmid",
    )
    _record(
        warehouse,
        session_id,
        "pubmed_search",
        {"query": "33333", "sort": None},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
    )

    empty_session_id = _open_session(warehouse)
    with server._open_warehouse(warehouse) as conn:
        citeable = trace_service.fetched_citation_pmids(conn, session_id)
        unknown = trace_service.fetched_citation_pmids(conn, "no-such-session")
        nothing = trace_service.fetched_citation_pmids(conn, empty_session_id)

    assert citeable == {"11111"}
    assert isinstance(unknown, trace_service.TraceError) and unknown.status == "not_found"
    assert nothing == set()


# ----- the citation-extraction contract ---------------------------------------- #


def test_extraction_contract_covers_the_documented_forms() -> None:
    draft = (
        "Magnesium and sleep are associated in trials (PMID: 11111; see also "
        "PMID 22222 and https://pubmed.ncbi.nlm.nih.gov/33333). "
        "pmid:44444 is matched case-insensitively. PMID alone is not a citation."
    )
    assert server._extract_cited_pmids(draft) == {"11111", "22222", "33333", "44444"}
    assert server._extract_cited_pmids("no literature cited here") == set()


def test_extraction_contract_near_miss_forms_are_recognized() -> None:
    """The reviewer's evasion set: each near-miss form must be SEEN (fail-closed)."""
    cases = {
        "hyphen separator (PMID-77777) here": {"77777"},
        "plural list PMIDs: 77777 and 88888 support it": {"77777", "88888"},
        "comma list PMIDs 1, 2; 3 / 4 & 5": {"1", "2", "3", "4", "5"},
        "spelled out PubMed ID 77777": {"77777"},
        "legacy url https://www.ncbi.nlm.nih.gov/pubmed/77777": {"77777"},
        "no digit-length ceiling: PMID 123456789": {"123456789"},
        "glued pmid12345 still seen": {"12345"},
    }
    for draft, expected in cases.items():
        assert server._extract_cited_pmids(draft) == expected, draft
    # Leading zeros stay as written: a mismatch with the fetched canonical PMID
    # fails the audit (the strict direction), never silently passes.
    assert server._extract_cited_pmids("PMID 012345") == {"012345"}


# ----- citation binding through the audit gate ---------------------------------- #


def _traced_session(warehouse: Path) -> str:
    session_id = _open_session(warehouse)
    _record(
        warehouse,
        session_id,
        "change_point",
        {"metric_id": "resting_hr"},
        terminal_status="refused",
        refusal_reason="insufficient_data",
    )
    return session_id


def test_cited_and_fetched_pmid_passes_and_envelope_discloses_it(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    _fetched_evidence(warehouse, session_id, "11111")

    draft = "The trial literature (PMID: 11111) discusses this pattern."
    verdict = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "passed"
    assert verdict["cited_pmids"] == ["11111"]
    assert (
        "citations: 1 cited PMID(s) (recognized forms), all fetched this session"
        in verdict["disclosure"]
    )

    blessed = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert blessed["status"] == "presented" and blessed["verified"] is True
    assert "citations: 1 cited PMID(s)" in blessed["disclosure"]


def test_unfetched_citation_fails_even_if_searched(tmp_path: Path) -> None:
    """The candidate-vs-fetched rule at the gate: searching is never citing."""
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    _record(
        warehouse,
        session_id,
        "pubmed_search",
        {"query": "magnesium sleep", "sort": None},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
    )

    draft = "Trials support this (https://pubmed.ncbi.nlm.nih.gov/55555)."
    verdict = server.answer_audit(
        draft, session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "failed"
    assert any("55555" in f and "never successfully fetched" in f for f in verdict["failures"])
    assert "1 not fetched this session" in verdict["disclosure"]

    refused = server.present_answer(draft, interprets_health=True, session_log_path=log)
    assert refused["status"] == "refused"


def test_failed_fetch_is_not_citeable(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    _record(
        warehouse,
        session_id,
        trace_service.PUBMED_FETCH_TOOL_NAME,
        {"pmid": "66666"},
        call_kind=trace_service.CALL_KIND_EVIDENCE_SOURCE,
        terminal_status="refused",
        refusal_reason="unavailable",
    )
    verdict = server.answer_audit(
        "See PMID 66666.", session_id=session_id, warehouse_path=warehouse, session_log_path=log
    )
    assert verdict["status"] == "failed"
    assert any("66666" in f for f in verdict["failures"])


def test_uncited_draft_passes_vacuously_with_honest_line(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    verdict = server.answer_audit(
        "No literature is cited in this answer.",
        session_id=session_id,
        warehouse_path=warehouse,
        session_log_path=log,
    )
    assert verdict["status"] == "passed"
    assert verdict["cited_pmids"] == []
    assert "citations: none in the recognized PMID forms" in verdict["disclosure"]


def test_citing_without_a_session_names_the_citation_problem(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    verdict = server.answer_audit(
        "Backed by PMID 11111.", warehouse_path=_warehouse(tmp_path), session_log_path=log
    )
    assert verdict["status"] == "failed"
    assert any("cites PMIDs but names no research-trace session" in f for f in verdict["failures"])


# ----- evidence recording through the MCP wrappers ------------------------------ #


_FETCH_AVAILABLE = {
    "status": "available",
    "record": {"pmid": "11111", "citation_status": "citeable_fetched_record"},
}


def _call(mcp: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await mcp.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def test_untraced_pubmed_calls_are_byte_identical_to_before(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(server, "pubmed_fetch", lambda pmid: dict(_FETCH_AVAILABLE))
    mcp = entrypoint.build_server(warehouse_path=_warehouse(tmp_path))
    payload = _call(mcp, "pubmed_fetch", {"pmid": "11111"})
    assert payload == _FETCH_AVAILABLE  # no trace key, nothing recorded


def test_traced_fetch_records_an_evidence_row_and_binds_citations(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The whole slice through the real MCP surface: fetch → audit → envelope."""
    monkeypatch.setattr(server, "pubmed_fetch", lambda pmid: dict(_FETCH_AVAILABLE))
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    payload = _call(mcp, "pubmed_fetch", {"pmid": "11111", "session_id": session_id})
    assert payload["status"] == "available"
    assert payload["trace"]["terminal_status"] == "available"
    assert payload["trace"]["session_id"] == session_id

    draft = "The literature (PMID 11111) describes this association."
    verdict = _call(mcp, "answer_audit", {"draft": draft, "session_id": session_id})
    assert verdict["status"] == "passed"
    blessed = _call(mcp, "present_answer", {"draft": draft, "interprets_health": True})
    assert blessed["verified"] is True
    assert (
        "citations: 1 cited PMID(s) (recognized forms), all fetched this session"
        in blessed["disclosure"]
    )

    # The evidence row never contaminated the analytical multiplicity.
    with server._open_warehouse(warehouse) as conn:
        disclosure = trace_service.get_research_disclosure(conn, session_id)
    assert isinstance(disclosure, trace_service.TraceDisclosure)
    assert disclosure.raw_analytical_call_count == 1
    assert disclosure.unique_hypothesis_count == 1


def test_traced_fetch_against_unknown_session_refuses_without_dispatch(
    tmp_path: Path, monkeypatch: Any
) -> None:
    calls: list[str] = []

    def never(pmid: str) -> dict[str, Any]:  # pragma: no cover - must not run
        calls.append(pmid)
        return dict(_FETCH_AVAILABLE)

    monkeypatch.setattr(server, "pubmed_fetch", never)
    mcp = entrypoint.build_server(warehouse_path=_warehouse(tmp_path))
    payload = _call(mcp, "pubmed_fetch", {"pmid": "11111", "session_id": "no-such"})
    assert payload["status"] == "not_found"
    assert calls == []


def test_evidence_outcomes_map_to_honest_terminal_statuses(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """unavailable → refused row; provider_error → error row; neither is citeable."""
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    outcomes = iter(
        [
            {"status": "unavailable", "pmid": "77777", "message": "x", "retryable": True},
            {"status": "provider_error", "pmid": "88888", "message": "x", "retryable": True},
        ]
    )
    monkeypatch.setattr(server, "pubmed_fetch", lambda pmid: next(outcomes))

    gone = _call(mcp, "pubmed_fetch", {"pmid": "77777", "session_id": session_id})
    assert gone["trace"]["terminal_status"] == "refused"
    flaky = _call(mcp, "pubmed_fetch", {"pmid": "88888", "session_id": session_id})
    assert flaky["trace"]["terminal_status"] == "error"

    with server._open_warehouse(warehouse) as conn:
        citeable = trace_service.fetched_citation_pmids(conn, session_id)
    assert citeable == set()


def test_traced_search_records_but_never_citeably(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        server,
        "pubmed_search",
        lambda query, limit=20, sort=None: {
            "status": "available",
            "count": 1,
            "candidates": [{"pmid": "11111", "citation_status": "candidate_only"}],
        },
    )
    log = tmp_path / "session_log.duckdb"
    warehouse = _warehouse(tmp_path)
    session_id = _traced_session(warehouse)
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    payload = _call(mcp, "pubmed_search", {"query": "magnesium sleep", "session_id": session_id})
    assert payload["trace"]["terminal_status"] == "available"

    # Recorded, yes — citeable, never.
    verdict = _call(
        mcp,
        "answer_audit",
        {"draft": "Candidates say so (PMID 11111).", "session_id": session_id},
    )
    assert verdict["status"] == "failed"
    assert any("never successfully fetched" in f for f in verdict["failures"])
