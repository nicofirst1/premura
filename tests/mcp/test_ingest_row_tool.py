"""MCP exposure of the `ingest_row` tool — the paved road for manual data (issue #113).

Locks the two ops (`suggest_metric` / `load`) against the contract in
the ingest-row tool contract:
`load` routes through the exact same boundary every parser uses
(`store.loader.load`, via `store.manual_load`), so unit convert-or-refuse and
`hp.ingest_skip` persistence apply with zero special-casing here. Synthetic
warehouses only.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import duckdb
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from premura.mcp.entrypoint import build_server
from premura.parsers import lookup
from premura.store import duck


def _call(server_: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        _content, structured = await server_.call_tool(name, arguments)
        assert isinstance(structured, dict)
        return structured

    return asyncio.run(run())


def _warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "warehouse.duckdb"
    duck.initialize(db_path).close()
    return db_path


# --------------------------------------------------------------------------- #
# op="load"
# --------------------------------------------------------------------------- #


def test_load_valid_row_lands_in_fact_measurement_with_canonical_unit(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)
    server_ = build_server(warehouse_path=db_path)

    result = _call(
        server_,
        "ingest_row",
        {
            "op": "load",
            "metric_id": "weight",
            "ts_utc": "2026-04-01T08:00:00",
            "unit": "lb",
            "source_ref": "operator spreadsheet row 14",
            "value_num": 154.0,
        },
    )

    assert result["status"] == "loaded"
    assert result["unit"] == "kg"
    assert result["rows_inserted"] == 1

    conn = duck.connect(db_path, read_only=True)
    try:
        row = conn.execute(
            "SELECT metric_id, unit, value_num, source_id, raw_payload FROM hp.fact_measurement"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    metric_id, unit, value_num, source_id, raw_payload = row
    assert metric_id == "weight"
    assert unit == "kg"
    assert value_num == pytest.approx(154.0 * 0.45359237)
    assert "manual_load" in source_id
    assert "operator spreadsheet row 14" in raw_payload

    conn = duck.connect(db_path, read_only=True)
    try:
        (source_kind,) = conn.execute("SELECT DISTINCT source_kind FROM hp.ingest_run").fetchone()
    finally:
        conn.close()
    assert source_kind == "manual_load"


def test_load_unconvertible_unit_refuses_and_persists_ingest_skip(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)
    server_ = build_server(warehouse_path=db_path)

    result = _call(
        server_,
        "ingest_row",
        {
            "op": "load",
            "metric_id": "heart_rate",
            "ts_utc": "2026-04-01T09:00:00",
            "unit": "furlongs_per_fortnight",
            "source_ref": "operator spreadsheet row 15",
            "value_num": 72.0,
        },
    )

    assert result["status"] == "refused"
    assert "furlongs_per_fortnight" in result["reason"]

    conn = duck.connect(db_path, read_only=True)
    try:
        n_measurements = conn.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
        skip_rows = conn.execute("SELECT kind, metric_id, from_unit FROM hp.ingest_skip").fetchall()
    finally:
        conn.close()
    assert n_measurements == 0
    assert skip_rows == [("unit_unconvertible", "heart_rate", "furlongs_per_fortnight")]


def test_load_missing_source_ref_refuses_before_loader_opens(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)
    server_ = build_server(warehouse_path=db_path)

    result = _call(
        server_,
        "ingest_row",
        {
            "op": "load",
            "metric_id": "weight",
            "ts_utc": "2026-04-01T08:00:00",
            "unit": "kg",
            "value_num": 70.0,
            # source_ref omitted entirely.
        },
    )

    assert result["status"] == "refused"
    assert "source_ref" in result["reason"]

    conn = duck.connect(db_path, read_only=True)
    try:
        n_runs = conn.execute("SELECT COUNT(*) FROM hp.ingest_run").fetchone()[0]
        n_measurements = conn.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    finally:
        conn.close()
    assert n_runs == 0
    assert n_measurements == 0


def test_load_empty_source_ref_also_refused(tmp_path: Path) -> None:
    db_path = _warehouse(tmp_path)
    server_ = build_server(warehouse_path=db_path)

    result = _call(
        server_,
        "ingest_row",
        {
            "op": "load",
            "metric_id": "weight",
            "ts_utc": "2026-04-01T08:00:00",
            "unit": "kg",
            "source_ref": "   ",
            "value_num": 70.0,
        },
    )

    assert result["status"] == "refused"
    assert "source_ref" in result["reason"]


# --------------------------------------------------------------------------- #
# op="suggest_metric"
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("field_name", ["Weight", "Heart Rate", "totally unknown field xyz"])
def test_suggest_metric_matches_parsers_lookup(tmp_path: Path, field_name: str) -> None:
    server_ = build_server(warehouse_path=_warehouse(tmp_path))

    result = _call(server_, "ingest_row", {"op": "suggest_metric", "field_name": field_name})

    assert result["metric_id"] == lookup.suggest_metric(field_name)


def test_suggest_metric_requires_field_name() -> None:
    async def run() -> None:
        server_ = build_server()
        with pytest.raises(ToolError, match="field_name"):
            await server_.call_tool("ingest_row", {"op": "suggest_metric"})

    asyncio.run(run())


def test_unknown_op_raises() -> None:
    async def run() -> None:
        server_ = build_server()
        with pytest.raises(ToolError, match="unknown ingest_row op"):
            await server_.call_tool("ingest_row", {"op": "bogus"})

    asyncio.run(run())


# --------------------------------------------------------------------------- #
# Combined-hardening smoke: rail + read-only default, together.
# --------------------------------------------------------------------------- #


def test_bare_duck_connect_write_attempt_fails_by_default(tmp_path: Path) -> None:
    """Opening the warehouse the way `_open_warehouse` (read-only tools) does
    must refuse a write — the read-only default is not something a caller has
    to opt into."""
    db_path = _warehouse(tmp_path)
    conn = duck.connect(db_path)  # no read_only kwarg: must default to True
    try:
        with pytest.raises(duckdb.Error):
            conn.execute("INSERT INTO hp.fact_measurement (metric_id) VALUES ('weight')")
    finally:
        conn.close()
