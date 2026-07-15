"""Slice 3 of OPERATING_ROLES.md: the runtime improvement queue.

Synthetic session logs only. Locks:

* the item shape exactly as the draft adopts it (id, created_at, status,
  kind, summary, suggested_action, privacy_level, trace_refs, github_refs);
* the ``kind`` field as a BOUNDED, OPEN registry (DOCTRINE rule 2) — a new
  kind registers with a short description, never a central-edit enum;
* ``status`` / ``privacy_level`` as FIXED, closed vocabularies that reject an
  unknown value;
* the queue is PRIVATE and LOCAL — nothing here ever reaches GitHub;
* the runtime queue (``log_improvement_item``) is a genuinely separate table
  from the harness-only ``log_improvement`` proposals table (FR-5).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from premura.mcp import entrypoint, server
from premura.session_log import store as sl
from premura.store import duck
from premura.ui import improvement_kinds

# ----- the open kind registry -------------------------------------------------- #


def test_seeded_kinds_registered() -> None:
    ids = improvement_kinds.known_kind_ids()
    assert ids >= {
        "parser_gap",
        "analysis_gap",
        "teaching_gap",
        "workflow_gap",
        "docs_gap",
        "other",
    }
    for kind in improvement_kinds.list_kinds():
        assert kind.description.strip()


def test_kind_registry_rejects_bad_declarations() -> None:
    with pytest.raises(ValueError, match="non-empty kind_id"):
        improvement_kinds.ImprovementKind(" ", "x").validate()
    with pytest.raises(ValueError, match="lowercase functional identifier"):
        improvement_kinds.ImprovementKind("Parser Gap", "x").validate()
    with pytest.raises(ValueError, match="short, non-empty description"):
        improvement_kinds.ImprovementKind("some_kind", "  ").validate()
    with pytest.raises(ValueError, match="already registered"):
        improvement_kinds.register_kind(improvement_kinds.ImprovementKind("other", "dup"))


# ----- store-level writer/reader ------------------------------------------------ #


def _log(tmp_path: Path) -> Path:
    return tmp_path / "session_log.duckdb"


def _open(log: Path) -> Any:
    conn = sl.connect(log)
    sl.init_schema(conn)
    return conn


def test_record_and_list_round_trip(tmp_path: Path) -> None:
    conn = _open(_log(tmp_path))
    try:
        item_id = sl.record_improvement_item(
            conn,
            kind="parser_gap",
            summary="Unmapped vendor field 'foo_bar' in a new export.",
            privacy_level="structural",
            suggested_action="Add a suggest_metric alias.",
            trace_refs=["handoff:abc123"],
            github_refs=None,
        )
        item = sl.get_improvement_item(conn, item_id=item_id)
        assert item is not None
        assert item["status"] == "open"  # default
        assert item["kind"] == "parser_gap"
        assert item["trace_refs"] == ["handoff:abc123"]
        assert item["github_refs"] == []  # never populated in this slice

        items = sl.list_improvement_items(conn)
        assert [row["item_id"] for row in items] == [item_id]
    finally:
        conn.close()


def test_record_rejects_unknown_status_and_privacy_level(tmp_path: Path) -> None:
    conn = _open(_log(tmp_path))
    try:
        with pytest.raises(ValueError, match="status must be one of"):
            sl.record_improvement_item(
                conn,
                kind="other",
                summary="x",
                privacy_level="minimal",
                status="not_a_status",
            )
        with pytest.raises(ValueError, match="privacy_level must be one of"):
            sl.record_improvement_item(
                conn,
                kind="other",
                summary="x",
                privacy_level="not_a_level",
            )
    finally:
        conn.close()


def test_list_rejects_unknown_status_filter(tmp_path: Path) -> None:
    conn = _open(_log(tmp_path))
    try:
        with pytest.raises(ValueError, match="status must be one of"):
            sl.list_improvement_items(conn, status="not_a_status")
    finally:
        conn.close()


def test_get_missing_item_returns_none(tmp_path: Path) -> None:
    conn = _open(_log(tmp_path))
    try:
        assert sl.get_improvement_item(conn, item_id="does-not-exist") is None
    finally:
        conn.close()


def test_runtime_queue_needs_no_harness_session_or_judgment(tmp_path: Path) -> None:
    """FR-5: log_improvement_item is genuinely decoupled from log_improvement.

    The harness-only ``record_improvement`` (log_improvement) requires an
    existing ``log_session`` + ``log_judgment`` row (FK-checked). The runtime
    queue's ``record_improvement_item`` needs neither — proof the two never
    share a code path, on a session log with ZERO log_session rows.
    """
    conn = _open(_log(tmp_path))
    try:
        assert conn.execute("SELECT count(*) FROM log_session").fetchone()[0] == 0
        item_id = sl.record_improvement_item(
            conn, kind="workflow_gap", summary="no harness row needed", privacy_level="minimal"
        )
        assert sl.get_improvement_item(conn, item_id=item_id) is not None
    finally:
        conn.close()


# ----- MCP-layer wrapper: the add-a-kind rule + fixed vocabularies -------------- #


def test_unregistered_kind_without_description_is_rejected(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    out = server.improvement_queue_record(
        "brand_new_kind_xyz", "summary", "minimal", session_log_path=log
    )
    assert out["status"] == "rejected"
    assert "kind_description" in out["reason"]
    assert improvement_kinds.get_kind("brand_new_kind_xyz") is None


def test_new_kind_registers_with_no_central_edit(tmp_path: Path) -> None:
    """The open-registry claim: a new kind works end to end without editing core code."""
    log = tmp_path / "session_log.duckdb"
    new_kind = "supplement_matcher_gap"
    try:
        assert improvement_kinds.get_kind(new_kind) is None
        out = server.improvement_queue_record(
            new_kind,
            "The matcher semantics need a documented worked example.",
            "structural",
            kind_description="A supplement/nutrition matcher behaved unexpectedly.",
            session_log_path=log,
        )
        assert out["status"] == "recorded"
        assert improvement_kinds.get_kind(new_kind) is not None

        # A second item of the same new kind needs no description again.
        out2 = server.improvement_queue_record(
            new_kind, "Another one.", "minimal", session_log_path=log
        )
        assert out2["status"] == "recorded"

        listed = server.improvement_queue_list(kind=new_kind, session_log_path=log)
        assert listed["count"] == 2
    finally:
        improvement_kinds._REGISTRY.pop(new_kind, None)


def test_mcp_layer_rejects_unknown_status_structurally(tmp_path: Path) -> None:
    log = tmp_path / "session_log.duckdb"
    out = server.improvement_queue_record(
        "other", "x", "minimal", status="not_a_status", session_log_path=log
    )
    assert out["status"] == "rejected"


def test_queue_list_empty_on_missing_file(tmp_path: Path) -> None:
    """No session log written yet: an honest empty result, never a crash."""
    out = server.improvement_queue_list(session_log_path=tmp_path / "nope.duckdb")
    assert out == {"items": [], "count": 0}


# ----- through the real MCP surface (FastMCP.call_tool) ------------------------- #


def _warehouse(tmp_path: Path) -> Path:
    db = tmp_path / "warehouse.duckdb"
    duck.initialize(db).close()
    return db


def _call(mcp: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await mcp.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def test_e2e_real_friction_recorded_and_read_back_through_mcp_surface(tmp_path: Path) -> None:
    """Real e2e exercise: hit real friction, record an item, read it back.

    Drives the tool surface as a connected agent would: an unaudited draft is
    refused by ``present_answer`` (real friction the improvement_scan role
    would notice), the friction is recorded as a private local improvement
    item referencing that handoff, and the item is read back through the
    strictly read-only ``improvement_queue_list`` tool. Also the
    session-log threadability regression pin: everything must land in the
    ``session_log_path`` given to ``build_server``, never the operator's real
    session log.
    """
    warehouse = _warehouse(tmp_path)
    log = tmp_path / "threaded_session_log.duckdb"
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    # Real friction: an unaudited health-interpreting draft is refused.
    draft = "Your resting heart rate shifted after the declared change."
    refused = _call(mcp, "present_answer", {"draft": draft, "interprets_health": True})
    assert refused["status"] == "refused"

    handoff = _call(
        mcp,
        "orchestrator_handoff",
        {
            "runtime_session_id": "sess-e2e-3",
            "from_id": "answer_audit",
            "to_id": "improvement_scan",
            "task_summary": "unaudited draft refused by present_answer",
            "status": "returned",
            "reason": "no audit verdict recorded for this draft",
        },
    )
    assert handoff["status"] == "recorded"

    recorded = _call(
        mcp,
        "improvement_queue_record",
        {
            "kind": "workflow_gap",
            "summary": "human_facing routed a draft to present_answer before an audit ran.",
            "privacy_level": "structural",
            "suggested_action": "Teach the runtime contract to call answer_audit first.",
            "trace_refs": [f"handoff:{handoff['handoff_id']}"],
        },
    )
    assert recorded["status"] == "recorded"
    item_id = recorded["item_id"]

    listed = _call(mcp, "improvement_queue_list", {"kind": "workflow_gap"})
    assert listed["count"] == 1
    assert listed["items"][0]["item_id"] == item_id
    assert listed["items"][0]["trace_refs"] == [f"handoff:{handoff['handoff_id']}"]
    assert listed["items"][0]["github_refs"] == []

    # Malformed input through the surface is a structured rejection.
    unknown_kind = _call(
        mcp,
        "improvement_queue_record",
        {"kind": "totally_unknown", "summary": "x", "privacy_level": "minimal"},
    )
    assert unknown_kind["status"] == "rejected"

    # Everything landed in the threaded session-log file, never a default path.
    assert log.exists()
    with sl.connect(log, read_only=True) as conn:
        rows = sl.list_improvement_items(conn)
    assert [r["item_id"] for r in rows] == [item_id]


def test_session_log_store_never_imports_stage4_ui() -> None:
    """Architecture boundary (CONTRIBUTING.md): the session_log substrate is
    shared by the harness and the runtime layer and must stay decoupled from
    Stage 4 — importing the store must not pull in ``premura.ui``."""
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import premura.session_log.store; "
            "bad = [m for m in sys.modules if m.startswith('premura.ui')]; "
            "sys.exit(1 if bad else 0)",
        ],
        check=False,
    )
    assert proc.returncode == 0, "premura.session_log.store imported premura.ui"
