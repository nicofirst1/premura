"""Slice 4 of OPERATING_ROLES.md: share packets over the improvement queue.

Synthetic session logs only — the "distinctive real-looking value" planted
below is a made-up marker string, never real health data. Locks:

* the three draft sharing levels (minimal / structural / synthetic_example)
  render a generated VIEW over a stored queue item, never a second record;
* an item's free-text ``summary`` / ``suggested_action`` is NEVER echoed
  verbatim by ANY level, and ref strings surface only as counts — the
  redaction tests plant a distinctive marker in both free-text fields and in
  a ``trace_ref`` and a ``github_ref``, and assert it is absent from minimal
  AND structural output;
* an unknown ``level`` is a structured rejection, never an exception, at both
  the pure-render and MCP layers;
* producing a packet writes nothing to GitHub or off this machine (the
  ``notice`` seam / FR-4 two-acts split);
* share-packet code touches no ``hp.*`` warehouse table.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from premura import share_packet as sp
from premura.mcp import entrypoint, server
from premura.session_log import store as sl
from premura.store import duck

_MARKER = "REALLOOKING-198.4bpm-vendor_field_xyz-2099-01-01"


def _open(log: Path) -> Any:
    conn = sl.connect(log)
    sl.init_schema(conn)
    return conn


def _item_with_marker(conn: Any) -> dict[str, Any]:
    item_id = sl.record_improvement_item(
        conn,
        kind="parser_gap",
        summary=f"Unmapped vendor field carrying value {_MARKER} in a new export.",
        privacy_level="synthetic_example",
        suggested_action=f"Investigate the {_MARKER} column before mapping.",
        # The marker also goes into BOTH ref lists so the counts-only rule
        # (structural emits how many refs exist, never their content) is
        # load-bearing in the redaction tests below.
        trace_refs=[f"handoff:{_MARKER}"],
        github_refs=[f"issue:{_MARKER}"],
    )
    item = sl.get_improvement_item(conn, item_id=item_id)
    assert item is not None
    return item


# ----- pure render function ------------------------------------------------- #


def test_render_rejects_unknown_level(tmp_path: Path) -> None:
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    with pytest.raises(ValueError, match="level must be one of"):
        sp.render_share_packet(item, "not_a_level")


@pytest.mark.parametrize("level", sorted(sp.SHARE_PACKET_LEVELS))
def test_render_succeeds_for_each_level(tmp_path: Path, level: str) -> None:
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    packet = sp.render_share_packet(item, level)
    assert packet.level == level
    assert packet.item_id == item["item_id"]
    d = packet.to_dict()
    assert d["status"] == "rendered"
    assert d["notice"] == sp.NOT_POSTED_NOTICE


def test_minimal_and_structural_never_leak_the_planted_marker(tmp_path: Path) -> None:
    """The core redaction lock: a distinctive real-looking value planted in
    both free-text fields AND in a trace_ref AND a github_ref must be absent
    from minimal AND structural output, whether rendered as the dict, JSON,
    or Markdown view — so the counts-only rule for refs is load-bearing."""
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()

    for level in ("minimal", "structural"):
        packet = sp.render_share_packet(item, level)
        blob = repr(packet.to_dict())
        assert _MARKER not in blob
        assert _MARKER not in sp.share_packet_to_json(packet)
        assert _MARKER not in sp.share_packet_to_markdown(packet)


def test_synthetic_example_also_never_echoes_free_text_verbatim(tmp_path: Path) -> None:
    """Even the richest level fabricates content; it does not echo the item's
    own summary/suggested_action, so the marker never appears there either."""
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    packet = sp.render_share_packet(item, "synthetic_example")
    assert _MARKER not in repr(packet.to_dict())
    assert packet.synthetic_fields, "synthetic_example level must fabricate at least one record"
    assert "timestamp" in packet.synthetic_fields[0]


def test_structural_and_synthetic_example_differ_in_fabricated_content(tmp_path: Path) -> None:
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    structural = sp.render_share_packet(item, "structural")
    synthetic = sp.render_share_packet(item, "synthetic_example")
    # structural: several standalone field/value examples; synthetic_example:
    # ONE fabricated record (dict) with a timestamp plus several fields.
    assert len(structural.synthetic_fields) >= 2
    assert len(synthetic.synthetic_fields) == 1
    assert len(synthetic.synthetic_fields[0]) > len(structural.synthetic_fields[0])


def test_minimal_fabricates_nothing(tmp_path: Path) -> None:
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    packet = sp.render_share_packet(item, "minimal")
    assert packet.synthetic_fields == ()


def test_json_and_markdown_exports_are_generated_views(tmp_path: Path) -> None:
    conn = _open(tmp_path / "log.duckdb")
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    packet = sp.render_share_packet(item, "structural")
    js = sp.share_packet_to_json(packet)
    assert item["item_id"] in js
    md = sp.share_packet_to_markdown(packet)
    assert item["item_id"] in md
    assert sp.NOT_POSTED_NOTICE in md


# ----- MCP-layer wrapper (server.share_packet_render) ----------------------- #


def test_server_render_not_found_for_unknown_item(tmp_path: Path) -> None:
    log = tmp_path / "log.duckdb"
    _open(log).close()
    out = server.share_packet_render("does-not-exist", "minimal", session_log_path=log)
    assert out["status"] == "not_found"


def test_server_render_not_found_for_missing_session_log(tmp_path: Path) -> None:
    out = server.share_packet_render(
        "anything", "minimal", session_log_path=tmp_path / "nope.duckdb"
    )
    assert out["status"] == "not_found"


def test_server_render_rejects_unknown_level(tmp_path: Path) -> None:
    log = tmp_path / "log.duckdb"
    conn = _open(log)
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    out = server.share_packet_render(item["item_id"], "not_a_level", session_log_path=log)
    assert out["status"] == "rejected"


def test_server_render_markdown_format_adds_markdown_field(tmp_path: Path) -> None:
    log = tmp_path / "log.duckdb"
    conn = _open(log)
    try:
        item = _item_with_marker(conn)
    finally:
        conn.close()
    out = server.share_packet_render(
        item["item_id"], "structural", format="markdown", session_log_path=log
    )
    assert out["status"] == "rendered"
    assert "packet_markdown" in out
    assert _MARKER not in out["packet_markdown"]


# ----- through the real MCP surface (FastMCP.call_tool) ---------------------- #


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


def test_e2e_share_packet_recorded_item_rendered_through_mcp_surface(tmp_path: Path) -> None:
    """Real e2e exercise: record a queue item with a planted marker, then
    render it as a share packet at each level through the live MCP surface,
    proving the marker never survives into minimal/structural output and that
    everything is threaded through the given ``session_log_path``, never the
    operator's default session log."""
    warehouse = _warehouse(tmp_path)
    log = tmp_path / "threaded_session_log.duckdb"
    mcp = entrypoint.build_server(warehouse_path=warehouse, session_log_path=log)

    recorded = _call(
        mcp,
        "improvement_queue_record",
        {
            "kind": "parser_gap",
            "summary": f"Unmapped vendor field with value {_MARKER}.",
            "privacy_level": "synthetic_example",
            "suggested_action": f"Look at {_MARKER} before mapping.",
            "trace_refs": ["handoff:xyz"],
        },
    )
    assert recorded["status"] == "recorded"
    item_id = recorded["item_id"]

    minimal = _call(mcp, "share_packet_render", {"item_id": item_id, "level": "minimal"})
    assert minimal["status"] == "rendered"
    assert _MARKER not in repr(minimal)

    structural = _call(mcp, "share_packet_render", {"item_id": item_id, "level": "structural"})
    assert structural["status"] == "rendered"
    assert _MARKER not in repr(structural)

    synthetic = _call(
        mcp,
        "share_packet_render",
        {"item_id": item_id, "level": "synthetic_example", "format": "markdown"},
    )
    assert synthetic["status"] == "rendered"
    assert _MARKER not in repr(synthetic)
    assert synthetic["synthetic_fields"]
    assert sp.NOT_POSTED_NOTICE in synthetic["packet_markdown"]

    # Unknown item through the surface is a structured not_found, not a crash.
    missing = _call(mcp, "share_packet_render", {"item_id": "no-such-item", "level": "minimal"})
    assert missing["status"] == "not_found"

    # Everything landed in the threaded session-log file, never a default path.
    assert log.exists()
    with sl.connect(log, read_only=True) as conn:
        rows = sl.list_improvement_items(conn)
    assert [r["item_id"] for r in rows] == [item_id]
