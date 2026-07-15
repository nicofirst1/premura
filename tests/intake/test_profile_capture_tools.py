"""WP03 — agent-mediated profile capture surface tests.

These are black-box tests over the public capture surface (the MCP server
helpers, the live FastMCP entrypoint, and the thin CLI mirror). They assert on
returned payloads and stored row effects, never on private helper internals.

They lock the WP03 contract:

* the supported-fields tool publishes exactly the bounded allowlist;
* the record tool stores ``birth_date`` / ``sex`` / ``standing_height_cm`` and
  reads them back with ``agent_profile_capture`` provenance;
* an unsupported/derived key (``age``) is rejected visibly, not silently;
* re-recording the same attribute supersedes the prior assertion and the tool
  surfaces the superseded id (append/supersede, never overwrite);
* both new tools are actually registered on the default agent-safe MCP surface
  and reachable through the live entrypoint;
* the CLI mirror routes through the same runtime behavior.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from premura.cli import app
from premura.mcp import server
from premura.mcp.entrypoint import build_server
from premura.profile_fields import SUPPORTED_PROFILE_FIELDS
from premura.store import duck, profile_intake


def _warehouse(tmp_path: Path) -> Path:
    """Initialize an empty warehouse (migrations applied) and return its path."""
    db_path = tmp_path / "profile.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _open(db_path: Path) -> object:
    return duck.connect(db_path, read_only=True)


# --------------------------------------------------------------------------- #
# Discovery: supported fields
# --------------------------------------------------------------------------- #
def test_supported_fields_publishes_bounded_allowlist() -> None:
    schema = server.supported_profile_fields()

    assert schema["supported_keys"] == list(SUPPORTED_PROFILE_FIELDS)
    assert sorted(schema["supported_keys"]) == ["birth_date", "sex", "standing_height_cm"]
    assert schema["source_kind"] == "agent_profile_capture"

    by_key = {f["attribute_key"]: f for f in schema["fields"]}
    assert by_key["sex"]["allowed_values"] == ["female", "male", "intersex"]
    assert by_key["standing_height_cm"]["unit"] == "cm"
    assert by_key["birth_date"]["value_kind"] == "date"


# --------------------------------------------------------------------------- #
# Happy path: the three supported fields land with agent provenance
# --------------------------------------------------------------------------- #
def test_record_birth_date_stores_and_reads_back(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    result = server.record_profile_context("birth_date", "1990-04-15", warehouse_path=db_path)

    assert result["status"] == "recorded"
    assert result["attribute_key"] == "birth_date"
    assert result["value_kind"] == "date"
    assert result["source_kind"] == "agent_profile_capture"
    assert result["superseded_assertion_id"] is None
    assert result["current"]["value_date"] == "1990-04-15"
    assert result["current"]["source_kind"] == "agent_profile_capture"

    # Stored-row effect, read back through the store boundary.
    conn = _open(db_path)
    try:
        stored = profile_intake.get_current_profile(conn, "birth_date")
    finally:
        conn.close()
    assert stored is not None
    assert stored.value_date == date(1990, 4, 15)
    assert stored.source_kind == "agent_profile_capture"


def test_record_sex_enum(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    result = server.record_profile_context("sex", "female", warehouse_path=db_path)

    assert result["status"] == "recorded"
    assert result["value_kind"] == "enum"
    assert result["current"]["value_text"] == "female"


def test_record_standing_height_quantity(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    result = server.record_profile_context("standing_height_cm", 178.5, warehouse_path=db_path)

    assert result["status"] == "recorded"
    assert result["value_kind"] == "quantity"
    assert result["current"]["value_num"] == 178.5
    assert result["current"]["unit"] == "cm"


# --------------------------------------------------------------------------- #
# Rejection: derived / unsupported keys are visible, not swallowed
# --------------------------------------------------------------------------- #
def test_record_age_is_rejected_explicitly(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    result = server.record_profile_context("age", 35, warehouse_path=db_path)

    assert result["status"] == "rejected"
    assert result["attribute_key"] == "age"
    assert "derived" in result["reason"]
    assert "birth_date" in result["reason"]
    assert "age" not in result["supported_keys"]

    # Nothing was written for the rejected key.
    conn = _open(db_path)
    try:
        assert profile_intake.get_current_profile(conn, "age") is None
    finally:
        conn.close()


def test_record_unknown_key_is_rejected(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    result = server.record_profile_context("favorite_color", "blue", warehouse_path=db_path)

    assert result["status"] == "rejected"
    assert "not in the bounded allowlist" in result["reason"]


def test_record_wrong_typed_value_is_rejected(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    # birth_date expects a date; a non-date string is a visible rejection.
    result = server.record_profile_context("birth_date", "not-a-date", warehouse_path=db_path)

    assert result["status"] == "rejected"
    # And nothing landed.
    conn = _open(db_path)
    try:
        assert profile_intake.get_current_profile(conn, "birth_date") is None
    finally:
        conn.close()


def test_record_disallowed_enum_value_is_rejected(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    result = server.record_profile_context("sex", "unknown", warehouse_path=db_path)

    assert result["status"] == "rejected"


# --------------------------------------------------------------------------- #
# Supersession: re-record surfaces the superseded id, keeps history
# --------------------------------------------------------------------------- #
def test_re_record_supersedes_prior_assertion(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    first = server.record_profile_context("standing_height_cm", 178.0, warehouse_path=db_path)
    second = server.record_profile_context("standing_height_cm", 179.0, warehouse_path=db_path)

    assert first["superseded_assertion_id"] is None
    # The second write closes the first and links back to it.
    assert second["superseded_assertion_id"] == first["assertion_id"]
    assert second["current"]["supersedes_assertion_id"] == first["assertion_id"]
    assert second["current"]["value_num"] == 179.0

    # History is appended, never overwritten: both assertions remain.
    conn = _open(db_path)
    try:
        history = profile_intake.get_profile_history(conn, "standing_height_cm")
        current = profile_intake.get_current_profile(conn, "standing_height_cm")
    finally:
        conn.close()
    assert len(history) == 2
    assert history[0].effective_end_utc is not None  # prior row closed
    assert current is not None
    assert current.value_num == 179.0


# --------------------------------------------------------------------------- #
# Live registration: tools are reachable through the default MCP entrypoint
# --------------------------------------------------------------------------- #
def test_profile_tools_registered_on_default_surface() -> None:
    async def run() -> None:
        srv = build_server()
        names = {tool.name for tool in await srv.list_tools()}
        assert "profile_context_supported_fields" in names
        assert "profile_context_record" in names

    asyncio.run(run())


def test_record_reachable_through_live_entrypoint(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)

    async def run() -> None:
        srv = build_server(warehouse_path=db_path)

        async def call(name: str, args: dict[str, object]) -> dict[str, object]:
            result = await srv.call_tool(name, args)
            return result[1] if isinstance(result, tuple) else result

        fields = await call("profile_context_supported_fields", {})
        assert sorted(fields["supported_keys"]) == [
            "birth_date",
            "sex",
            "standing_height_cm",
        ]

        recorded = await call(
            "profile_context_record",
            {"attribute_key": "sex", "value": "male"},
        )
        assert recorded["status"] == "recorded"
        assert recorded["source_kind"] == "agent_profile_capture"

        rejected = await call(
            "profile_context_record",
            {"attribute_key": "age", "value": 40},
        )
        assert rejected["status"] == "rejected"

    asyncio.run(run())

    # Confirm the live call actually wrote a row.
    conn = _open(db_path)
    try:
        stored = profile_intake.get_current_profile(conn, "sex")
    finally:
        conn.close()
    assert stored is not None
    assert stored.value_text == "male"


# --------------------------------------------------------------------------- #
# CLI mirror: thin, derivative, same behavior
# --------------------------------------------------------------------------- #
def test_cli_profile_fields_lists_allowlist() -> None:
    # Assert on the structured source of truth the command renders from, not the
    # width-wrapped Rich table text.
    keys = server.supported_profile_fields()["supported_keys"]
    assert "birth_date" in keys
    assert "standing_height_cm" in keys


def _point_default_warehouse_at(tmp_path: Path, monkeypatch) -> Path:  # type: ignore[no-untyped-def]
    """Redirect the configured default warehouse into ``tmp_path`` for the CLI.

    The CLI commands mirror the MCP surface and use the configured default
    warehouse (no ``--warehouse-path`` flag), so we move ``data_dir`` — from
    which ``warehouse_path`` is derived — to an isolated temp location.
    """
    data_dir = tmp_path / "data"
    monkeypatch.setattr(server.settings, "data_dir", data_dir)
    db_path = server.settings.warehouse_path
    duck.initialize(db_path).close()
    return db_path


def test_cli_profile_record_happy_and_rejected(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    db_path = _point_default_warehouse_at(tmp_path, monkeypatch)

    runner = CliRunner(env={"COLUMNS": "200"})

    ok = runner.invoke(app, ["profile-record", "standing_height_cm", "181.0"])
    assert ok.exit_code == 0
    assert "recorded" in ok.stdout

    bad = runner.invoke(app, ["profile-record", "age", "35"])
    assert bad.exit_code == 1
    assert "rejected" in bad.stdout

    conn = _open(db_path)
    try:
        stored = profile_intake.get_current_profile(conn, "standing_height_cm")
    finally:
        conn.close()
    assert stored is not None
    assert stored.value_num == 181.0
