"""`premura audit-integrity` — read-only detection of unit + source-kind drift.

Two findings, always exit 0 (detection, not a gate): (a) fact_measurement rows
whose unit differs from dim_metric.canonical_unit, (b) ingest_run.source_kind
values outside registered_source_kinds(). Synthetic fixtures only, no PHI.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from premura import cli
from premura.config import settings
from premura.store import duck

runner = CliRunner()


def _point_warehouse(monkeypatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    return settings.warehouse_path


def test_clean_warehouse_reports_zero_findings(monkeypatch, tmp_path: Path) -> None:
    db_path = _point_warehouse(monkeypatch, tmp_path)
    conn = duck.initialize(db_path)
    conn.close()

    result = runner.invoke(cli.app, ["audit-integrity"])
    assert result.exit_code == 0, result.output
    assert "no fact_measurement unit mismatches" in result.output
    assert "no unregistered ingest_run source kinds" in result.output


def test_seeded_unit_mismatch_and_bad_source_kind_are_reported(monkeypatch, tmp_path: Path) -> None:
    db_path = _point_warehouse(monkeypatch, tmp_path)
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="src_1", source_kind="bmt")
    # dim_metric seed carries a real metric with a known canonical_unit.
    metric_id, canonical_unit = conn.execute(
        "SELECT metric_id, canonical_unit FROM hp.dim_metric LIMIT 1"
    ).fetchone()
    bad_unit = canonical_unit + "_BOGUS"
    conn.execute(
        """
        INSERT INTO hp.fact_measurement
            (ts_utc, metric_id, value_num, unit, source_id, dedupe_key)
        VALUES (TIMESTAMP '2026-01-01 08:00:00', ?, 1.0, ?, 'src_1', 'audit-1')
        """,
        [metric_id, bad_unit],
    )
    conn.execute(
        "INSERT INTO hp.ingest_run (batch_id, source_kind) VALUES ('batch-1', 'not_a_real_parser')"
    )
    conn.close()

    result = runner.invoke(cli.app, ["audit-integrity"])
    assert result.exit_code == 0, result.output
    assert metric_id in result.output
    assert bad_unit in result.output
    assert canonical_unit in result.output
    assert "not_a_real_parser" in result.output


def test_missing_warehouse_is_graceful(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    result = runner.invoke(cli.app, ["audit-integrity"])
    assert result.exit_code == 0, result.output
