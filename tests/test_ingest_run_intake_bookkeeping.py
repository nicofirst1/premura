"""The nutrition/intake ingest path writes an `hp.ingest_run` row (issue #88, defect B).

Before this fix, `_ingest_one` persisted `IntakeBatch` rows straight through
`persist_intake_batch` without ever calling `start_ingest_run`/
`finish_ingest_run`, so MFP never appeared under "Recent ingest runs" and
never participated in the sha256 already-ingested skip. Synthetic MFP export
only (no real operator data), mirroring tests/test_parsers/test_myfitnesspal.py.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from premura import cli
from premura.cli import _ingest_one

NUTRITION_HEADER = (
    "Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,"
    "Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,"
    "Protein (g),Vitamin A,Vitamin C,Calcium,Iron,Note"
)

NUTRITION_CSV = (
    NUTRITION_HEADER + "\n"
    "2026-01-05,Breakfast,400.0,10.0,3.0,1.0,4.0,0.0,50.0,300.0,400.0,"
    "55.0,6.0,12.0,20.0,10.0,40.0,15.0,8.0,\n"
    "2026-01-05,Lunch,650.5,22.0,,2.0,8.0,0.0,80.0,900.0,600.0,"
    "70.0,9.0,10.0,35.0,5.0,20.0,10.0,12.0,\n"
)


def _export_zip(tmp_path: Path) -> Path:
    path = tmp_path / "File-Export-2026-01-01-to-2026-01-31.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Nutrition-Summary-2026-01-01-to-2026-01-31.csv", NUTRITION_CSV)
    return path


def test_mfp_ingest_writes_one_ingest_run_row(empty_warehouse, tmp_path: Path) -> None:
    zip_path = _export_zip(tmp_path)

    _ingest_one(empty_warehouse, "mfp", zip_path)

    rows = empty_warehouse.execute(
        "SELECT source_kind, rows_inserted, finished_at FROM hp.ingest_run"
    ).fetchall()
    assert len(rows) == 1
    source_kind, rows_inserted, finished_at = rows[0]
    assert source_kind == "myfitnesspal"
    assert rows_inserted == 2
    assert finished_at is not None


def test_mfp_reingest_is_skipped_via_sha256(empty_warehouse, tmp_path: Path) -> None:
    zip_path = _export_zip(tmp_path)

    _ingest_one(empty_warehouse, "mfp", zip_path)
    _ingest_one(empty_warehouse, "mfp", zip_path)

    count = empty_warehouse.execute("SELECT COUNT(*) FROM hp.ingest_run").fetchone()
    assert count is not None
    assert count[0] == 1


def test_failed_intake_persist_leaves_no_orphan_run_row(
    empty_warehouse, tmp_path: Path, monkeypatch
) -> None:
    """A raise during persist must roll back the started run row (no orphan)."""
    zip_path = _export_zip(tmp_path)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("synthetic persist failure")

    monkeypatch.setattr(cli, "persist_intake_batch", _boom)
    with pytest.raises(RuntimeError, match="synthetic persist failure"):
        _ingest_one(empty_warehouse, "mfp", zip_path)

    count = empty_warehouse.execute("SELECT COUNT(*) FROM hp.ingest_run").fetchone()
    assert count is not None
    assert count[0] == 0, "started run row must be rolled back on persist failure"

    # A later successful ingest of the same file then creates exactly one
    # finished row (the failed attempt must not have poisoned the sha256 skip).
    monkeypatch.undo()
    _ingest_one(empty_warehouse, "mfp", zip_path)
    rows = empty_warehouse.execute(
        "SELECT source_kind, rows_inserted, finished_at FROM hp.ingest_run"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "myfitnesspal"
    assert rows[0][2] is not None


def test_force_reingest_bypasses_skip_without_duplicating_rows(
    empty_warehouse, tmp_path: Path
) -> None:
    """--force (issue #93) bypasses the sha256 skip but the dedupe layer still
    catches the re-inserted rows, so fact-table row counts don't change."""
    zip_path = _export_zip(tmp_path)

    _ingest_one(empty_warehouse, "mfp", zip_path)
    row_count_before = empty_warehouse.execute(
        "SELECT COUNT(*) FROM hp.nutrition_intake_event"
    ).fetchone()[0]

    _ingest_one(empty_warehouse, "mfp", zip_path, force=True)
    row_count_after = empty_warehouse.execute(
        "SELECT COUNT(*) FROM hp.nutrition_intake_event"
    ).fetchone()[0]

    assert row_count_after == row_count_before, "force must not duplicate previously loaded rows"

    runs = empty_warehouse.execute(
        "SELECT finished_at FROM hp.ingest_run ORDER BY started_at"
    ).fetchall()
    assert len(runs) == 2, "force must write a fresh ingest_run row instead of skipping"
    assert all(r[0] is not None for r in runs)
