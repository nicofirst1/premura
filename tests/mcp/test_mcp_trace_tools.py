"""WP03 — MCP trace-tool surface tests (session/mark/disclosure).

These exercise the three session-research-trace tools THROUGH the MCP boundary
(``FastMCP.call_tool``), exactly as a connected agent would reach them, and lock
the contract from ``contracts/mcp-trace-tools.md``:

* ``research_trace_open`` returns the required session fields on the DEFAULT
  agent-safe surface (the trace is the supported agent workflow);
* ``research_trace_mark_surfaced`` succeeds for a call in the same session and
  returns explicit structured errors otherwise;
* ``research_trace_disclosure`` for an unknown session returns an explicit
  ``not_found`` — never an empty successful disclosure;
* the operator surface inherits the trace tools and adds only ``query_warehouse``;
* disclosure derives its counts without ``query_warehouse`` / raw ``hp.*`` rows.

Synthetic warehouses only; the trace service writes to ``trace.*`` tables created
by the idempotent migrations the writable connection re-runs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from premura.mcp.entrypoint import build_operator_server, build_server
from premura.store import duck


def _warehouse(tmp_path: Path) -> Path:
    """A minimal initialized warehouse (migrations create the ``trace.*`` schema).

    The file is deliberately NOT named ``trace.duckdb``: DuckDB names the default
    catalog after the file stem, and a catalog named ``trace`` collides with the
    ``trace`` SCHEMA the migrations create ("ambiguous reference to catalog or
    schema").
    """
    db_path = tmp_path / "warehouse.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _call(server: FastMCP, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool through the MCP surface and return its structured payload.

    ``FastMCP.call_tool`` returns ``(content_blocks, structured_dict)``; tests read
    the structured dict, which is the same object the wrapper returned.
    """

    async def run() -> dict[str, Any]:
        _content, structured = await server.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


# --------------------------------------------------------------------------- #
# research_trace_open
# --------------------------------------------------------------------------- #
def test_research_trace_open_returns_required_session_fields(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))

    payload = _call(server, "research_trace_open", {"client_label": "opencode"})

    assert payload["status"] == "opened"
    assert isinstance(payload["session_id"], str) and payload["session_id"]
    # Contract Response fields.
    assert payload["started_at_utc"]
    assert payload["warehouse_fingerprint"]
    assert payload["schema_version"]
    assert payload["client_label"] == "opencode"


def test_research_trace_open_without_label(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))

    payload = _call(server, "research_trace_open", {})

    assert payload["status"] == "opened"
    assert payload["client_label"] is None


# --------------------------------------------------------------------------- #
# research_trace_mark_surfaced
# --------------------------------------------------------------------------- #
def test_mark_surfaced_succeeds_for_same_session_call(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    # A recorded analytical call (empty warehouse -> refused, but still recorded).
    cp = _call(server, "change_point", {"metric_id": "resting_hr", "session_id": session_id})
    call_id = cp["trace"]["call_id"]

    marked = _call(
        server,
        "research_trace_mark_surfaced",
        {
            "session_id": session_id,
            "call_id": call_id,
            "role": "summary",
            "rationale": "Used as the main pattern in the final answer",
        },
    )

    assert marked["status"] == "marked"
    assert marked["call_id"] == call_id
    assert marked["session_id"] == session_id
    assert marked["role"] == "summary"
    assert marked["mark_id"]


def test_mark_surfaced_unknown_session_is_not_found(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))

    payload = _call(
        server,
        "research_trace_mark_surfaced",
        {
            "session_id": "sess_does_not_exist",
            "call_id": "call_x",
            "role": "summary",
            "rationale": "n/a",
        },
    )

    assert payload["status"] == "not_found"
    assert payload["field"] == "session_id"


def test_mark_surfaced_empty_role_is_validation_error(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(
        server,
        "research_trace_mark_surfaced",
        {"session_id": session_id, "call_id": "call_x", "role": "  ", "rationale": "x"},
    )

    assert payload["status"] == "validation_error"
    assert payload["field"] == "role"


def test_mark_surfaced_call_from_other_session_is_invalid_reference(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))
    session_a = _call(server, "research_trace_open", {})["session_id"]
    session_b = _call(server, "research_trace_open", {})["session_id"]

    cp = _call(server, "change_point", {"metric_id": "resting_hr", "session_id": session_a})
    call_in_a = cp["trace"]["call_id"]

    payload = _call(
        server,
        "research_trace_mark_surfaced",
        {
            "session_id": session_b,
            "call_id": call_in_a,
            "role": "summary",
            "rationale": "cross-session",
        },
    )

    assert payload["status"] == "invalid_reference"
    assert payload["field"] == "call_id"


# --------------------------------------------------------------------------- #
# research_trace_disclosure
# --------------------------------------------------------------------------- #
def test_disclosure_unknown_session_is_not_found(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))

    payload = _call(server, "research_trace_disclosure", {"session_id": "sess_nope"})

    # Explicit not-found, NOT an empty successful disclosure (FR-015).
    assert payload["status"] == "not_found"
    assert "raw_analytical_call_count" not in payload


def test_disclosure_empty_session_is_available_not_found(tmp_path: Path) -> None:
    """A real but empty session is ``available`` with zero counts — distinct from
    a never-opened session's ``not_found``."""
    server = build_server(warehouse_path=_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(server, "research_trace_disclosure", {"session_id": session_id})

    assert payload["status"] == "available"
    assert payload["raw_analytical_call_count"] == 0
    assert payload["unique_hypothesis_count"] == 0
    # No marks -> surfaced is unavailable (never a guessed 0).
    assert payload["surfaced"]["status"] == "unavailable"


def test_disclosure_markdown_export_added_beside_structured_counts(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]

    payload = _call(
        server,
        "research_trace_disclosure",
        {"session_id": session_id, "format": "markdown"},
    )

    assert payload["status"] == "available"
    # Structured counts remain; markdown is a generated export beside them.
    assert "raw_analytical_call_count" in payload
    assert "disclosure_markdown" in payload
    assert "unique hypotheses examined" in payload["disclosure_markdown"]


def test_disclosure_never_says_significant_results(tmp_path: Path) -> None:
    server = build_server(warehouse_path=_warehouse(tmp_path))
    session_id = _call(server, "research_trace_open", {})["session_id"]
    _call(server, "change_point", {"metric_id": "resting_hr", "session_id": session_id})

    payload = _call(server, "research_trace_disclosure", {"session_id": session_id})

    text = payload["disclosure_text"]
    assert "unique hypotheses examined" in text
    assert "significant results" not in text
    assert "tests" not in text


# --------------------------------------------------------------------------- #
# Surface registration (T013 / T019)
# --------------------------------------------------------------------------- #
def test_trace_tools_on_default_surface() -> None:
    async def run() -> None:
        names = {tool.name for tool in await build_server().list_tools()}
        assert {
            "research_trace_open",
            "research_trace_mark_surfaced",
            "research_trace_disclosure",
        } <= names

    asyncio.run(run())


def test_operator_surface_inherits_trace_tools_plus_query_warehouse() -> None:
    async def run() -> None:
        default_names = {tool.name for tool in await build_server().list_tools()}
        operator_names = {tool.name for tool in await build_operator_server().list_tools()}
        trace_tools = {
            "research_trace_open",
            "research_trace_mark_surfaced",
            "research_trace_disclosure",
        }
        # Operator inherits the full default set (including trace tools) ...
        assert trace_tools <= operator_names
        assert default_names <= operator_names
        # ... and differs from default by EXACTLY query_warehouse.
        assert operator_names - default_names == {"query_warehouse"}

    asyncio.run(run())


def test_disclosure_does_not_expose_query_warehouse_on_default_surface(tmp_path: Path) -> None:
    """Trace disclosure is agent-safe provenance: it derives counts from the
    ``trace.*`` rows and never needs the raw SQL escape hatch, which stays
    operator-only."""
    server = build_server(warehouse_path=_warehouse(tmp_path))

    async def run() -> None:
        names = {tool.name for tool in await server.list_tools()}
        assert "query_warehouse" not in names

    asyncio.run(run())
    # And the disclosure payload carries derived counts, not raw hp.* rows.
    session_id = _call(server, "research_trace_open", {})["session_id"]
    payload = _call(server, "research_trace_disclosure", {"session_id": session_id})
    assert set(payload) >= {"raw_analytical_call_count", "unique_hypothesis_count", "surfaced"}
    assert "rows" not in payload  # not a raw query_warehouse result envelope
