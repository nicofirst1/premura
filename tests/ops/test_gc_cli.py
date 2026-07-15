"""`premura gc` — prune data/raw/ + --dry-run (m7 WP2).

gc applies one cutoff rule (mtime older than --keep months) to N roots: the
exports dir always, and settings.raw_dir only when the opt-in --raw flag is
given (default OFF, because run_monthly calls gc(keep=3) unattended and must not
silently delete staged source artifacts). --dry-run previews exactly what would
be removed and removes nothing, from either root.

These tests drive the command through Typer's CliRunner over synthetic temp
dirs (no PHI) and cover the spec-named edge cases E2.1-E2.3 plus the
unchanged-programmatic-call invariant (FR-2.4).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from typer.testing import CliRunner

from premura import cli
from premura.config import settings

runner = CliRunner()

# Older than keep=3 months (3 * 31 days) — comfortably past the cutoff.
_OLD = time.time() - 200 * 24 * 3600
_FRESH = time.time()


def _point_data_dir(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    exports = settings.exports_dir
    raw = settings.raw_dir
    exports.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    return exports, raw


def _aged_dir(parent: Path, name: str, mtime: float) -> Path:
    d = parent / name
    d.mkdir()
    os.utime(d, (mtime, mtime))
    return d


def _aged_file(parent: Path, name: str, mtime: float) -> Path:
    f = parent / name
    f.write_text("x", encoding="utf-8")
    os.utime(f, (mtime, mtime))
    return f


def test_gc_dry_run_lists_but_does_not_delete(monkeypatch, tmp_path: Path) -> None:
    """E2.1 — --dry-run over a populated exports dir: listed, not deleted."""
    exports, _raw = _point_data_dir(monkeypatch, tmp_path)
    old = _aged_dir(exports, "2020-01", _OLD)

    result = runner.invoke(cli.app, ["gc", "--keep", "3", "--dry-run"])
    assert result.exit_code == 0, result.output
    # Unambiguous dry-run prefix and nothing actually removed.
    assert "would remove" in result.output.lower()
    assert old.exists()


def test_gc_default_removes_old_exports_only(monkeypatch, tmp_path: Path) -> None:
    exports, raw = _point_data_dir(monkeypatch, tmp_path)
    old_export = _aged_dir(exports, "2020-01", _OLD)
    fresh_export = _aged_dir(exports, "2026-06", _FRESH)
    old_raw = _aged_file(raw, "old_source.csv", _OLD)

    result = runner.invoke(cli.app, ["gc", "--keep", "3"])
    assert result.exit_code == 0, result.output
    assert not old_export.exists()
    assert fresh_export.exists()
    # Without --raw, the raw root is untouched.
    assert old_raw.exists()


def test_gc_raw_prunes_old_raw_keeps_fresh(monkeypatch, tmp_path: Path) -> None:
    """E2.2 — --raw deletes an old raw entry (file AND dir), keeps a fresh one."""
    _exports, raw = _point_data_dir(monkeypatch, tmp_path)
    old_file = _aged_file(raw, "old_source.csv", _OLD)
    old_dir = _aged_dir(raw, "old_staged", _OLD)
    fresh_file = _aged_file(raw, "fresh_source.csv", _FRESH)

    result = runner.invoke(cli.app, ["gc", "--keep", "3", "--raw"])
    assert result.exit_code == 0, result.output
    assert not old_file.exists()
    assert not old_dir.exists()
    assert fresh_file.exists()


def test_gc_raw_dry_run_previews_raw_without_deleting(monkeypatch, tmp_path: Path) -> None:
    """E2.2 + FR-2.5 — --raw with --dry-run previews raw pruning but removes
    nothing from either root."""
    _exports, raw = _point_data_dir(monkeypatch, tmp_path)
    old_file = _aged_file(raw, "old_source.csv", _OLD)

    result = runner.invoke(cli.app, ["gc", "--keep", "3", "--raw", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "old_source.csv" in result.output
    assert "would remove" in result.output.lower()
    assert old_file.exists()


def test_gc_missing_dirs_are_graceful(monkeypatch, tmp_path: Path) -> None:
    """E2.3 — missing exports dir / missing raw dir → graceful, exit 0."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    # Neither exports nor raw exists.
    result = runner.invoke(cli.app, ["gc", "--keep", "3", "--raw"])
    assert result.exit_code == 0, result.output


def test_gc_programmatic_call_unchanged(monkeypatch, tmp_path: Path) -> None:
    """FR-2.4 — run_monthly's gc(keep=3) call keeps working unchanged: raw is
    NOT pruned (default OFF), old exports are removed exactly as before."""
    exports, raw = _point_data_dir(monkeypatch, tmp_path)
    old_export = _aged_dir(exports, "2020-01", _OLD)
    old_raw = _aged_file(raw, "old_source.csv", _OLD)

    # Direct programmatic invocation, exactly as run_monthly does it.
    cli.gc(keep=3)

    assert not old_export.exists()
    assert old_raw.exists()
