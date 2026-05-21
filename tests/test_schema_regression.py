"""Regression test against the real Health Connect export.

Skipped if the file isn't present — keeps CI green elsewhere.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from premura.parsers.health_connect import (
    EXPECTED_USER_VERSION,
    INTERVAL_SPECS,
    SIMPLE_SPECS,
    HealthConnectParser,
)

REAL_EXPORT = Path("/Users/nbrandizzi/Downloads/health_connect_export.db")

pytestmark = pytest.mark.regression


def _require_export():
    if not REAL_EXPORT.is_file():
        pytest.skip(f"real HC export not present: {REAL_EXPORT}")


def test_user_version_matches_expected():
    _require_export()
    con = sqlite3.connect(REAL_EXPORT)
    try:
        v = con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()
    assert v == EXPECTED_USER_VERSION


def test_every_column_the_parser_reads_exists():
    _require_export()
    con = sqlite3.connect(REAL_EXPORT)
    try:
        for spec in SIMPLE_SPECS:
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({spec.table})")}
            if not cols:
                continue
            for required in ("uuid", "time", "zone_offset", spec.value_col):
                assert required in cols, f"{spec.table} missing {required}"
        for spec in INTERVAL_SPECS:
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({spec.table})")}
            if not cols:
                continue
            for required in ("uuid", "start_time", "end_time", "start_zone_offset"):
                assert required in cols, f"{spec.table} missing {required}"
            if spec.value_col:
                assert spec.value_col in cols, f"{spec.table} missing {spec.value_col}"
    finally:
        con.close()


def test_ingest_smoke_then_idempotent(empty_warehouse):
    """Full HC ingest + a second-pass dedupe confirmation."""
    _require_export()
    from premura import loader

    p = HealthConnectParser()
    batch = p.parse(REAL_EXPORT)
    loader.load(empty_warehouse, batch)
    fm = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    fi = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_interval").fetchone()[0]
    assert fm > 100_000, f"expected >>100k measurement rows, got {fm}"
    assert fi > 10_000, f"expected >>10k interval rows, got {fi}"

    w_min, w_max = empty_warehouse.execute(
        "SELECT MIN(value_num), MAX(value_num) FROM hp.fact_measurement WHERE metric_id='weight'"
    ).fetchone()
    assert 40 <= (w_min or 0) <= 200, f"weight min out of plausible kg range: {w_min}"
    assert 40 <= (w_max or 0) <= 200, f"weight max out of plausible kg range: {w_max}"

    p2 = HealthConnectParser()
    batch2 = p2.parse(REAL_EXPORT)
    stats2 = loader.load(empty_warehouse, batch2)
    assert stats2.rows_inserted == 0
    assert stats2.rows_skipped_dup > 0
    fm2 = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    fi2 = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_interval").fetchone()[0]
    assert fm == fm2 and fi == fi2
