"""`hpipe inspect <path>` — read-only routing preview (m7 WP1).

inspect is the read-only twin of ingest discovery: it resolves the parser for a
path with the SAME logic ingest uses, enumerates member names without ingesting,
calls the structural routing-preview capability, and prints per-member routing
plus a summary. It never writes (no warehouse connection, no data/ mutation,
no ingest_run row).

These tests drive the command through Typer's CliRunner over synthetic fixtures
(no PHI), and cover the spec-named edge cases E1.1-E1.3.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from typer.testing import CliRunner

from premura import cli

runner = CliRunner()


def _write_garmin_zip(tmp_path: Path) -> Path:
    """A minimal synthetic Garmin GDPR zip: a routable member and an unknown one.

    Contents are empty JSON arrays — inspect never reads them, it routes by name.
    """
    p = tmp_path / "garmin_export.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("DI_CONNECT/sleepData.json", "[]")
        zf.writestr("DI_CONNECT/UDSFile_20240101.json", "[]")
        zf.writestr("DI_CONNECT/mystery_export.json", "[]")
    return p


def test_inspect_garmin_zip_prints_routing_and_summary(tmp_path: Path) -> None:
    fixture = _write_garmin_zip(tmp_path)
    result = runner.invoke(cli.app, ["inspect", str(fixture)])
    assert result.exit_code == 0, result.output
    out = result.output
    # Per-member routing.
    assert "sleepData.json" in out
    assert "_handle_sleep_data" in out
    assert "mystery_export.json" in out
    assert "unhandled" in out
    # Summary count: 2 routed, 1 unhandled.
    assert "2 routed" in out
    assert "1 unhandled" in out


def test_inspect_nonexistent_path_exits_nonzero(tmp_path: Path) -> None:
    """E1.1 — path does not exist → non-zero exit, clear message."""
    missing = tmp_path / "nope.zip"
    result = runner.invoke(cli.app, ["inspect", str(missing)])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "not found" in result.output.lower()


def test_inspect_unmatched_path_exits_zero(tmp_path: Path) -> None:
    """E1.2 — path exists but no parser claims it → exit 0, honest message."""
    weird = tmp_path / "data.xyz"
    weird.write_text("nothing routable here", encoding="utf-8")
    result = runner.invoke(cli.app, ["inspect", str(weird)])
    assert result.exit_code == 0, result.output
    assert "no parser" in result.output.lower()


def test_inspect_parser_without_capability_reports_honestly(tmp_path: Path) -> None:
    """E1.3 / FR-1.3 — a parser matched but lacking preview_routing is reported
    honestly: exit 0, names the parser, states it does not support preview, and
    names the rule for adding it (expose the capability)."""
    # A .db file routes to the Health Connect parser, which does not implement
    # the routing-preview capability tonight.
    db = tmp_path / "health.db"
    db.write_bytes(b"\x00")  # inspect must not open/read it
    result = runner.invoke(cli.app, ["inspect", str(db)])
    assert result.exit_code == 0, result.output
    low = result.output.lower()
    assert "does not support routing preview" in low
    assert "preview_routing" in result.output


def test_inspect_never_creates_warehouse(tmp_path: Path, monkeypatch) -> None:
    """FR-1.5 — inspect writes nothing: no warehouse file appears under data/."""
    from premura.config import settings

    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    fixture = _write_garmin_zip(tmp_path)

    result = runner.invoke(cli.app, ["inspect", str(fixture)])
    assert result.exit_code == 0, result.output
    # No warehouse directory/file was created as a side effect of inspect.
    assert not (data_dir / "duck").exists()
