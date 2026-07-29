"""Non-destructive warehouse restore: month resolution, integrity gate, swap.

The swap is the only data-loss path in `premura download`, so its seams are
tested directly rather than through the rclone subprocess wrapper.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from premura.ops import restore
from premura.store import duck


def test_parse_latest_month_picks_max() -> None:
    names = [
        "2026/05/health.duckdb.age",
        "2026/07/health.duckdb.age",
        "2025/12/manifest.json",
    ]
    assert restore.parse_latest_month(names) == "2026-07"


def test_parse_latest_month_ignores_unpartitioned_and_empty() -> None:
    assert restore.parse_latest_month(["health.duckdb.age", "notes.txt"]) is None
    assert restore.parse_latest_month([]) is None


def test_install_warehouse_fresh_target_moves_in_place(tmp_path: Path) -> None:
    restored = tmp_path / "restored.duckdb"
    target = tmp_path / "duck" / "health.duckdb"
    restored.write_bytes(b"new-db")

    backup = restore.install_warehouse(restored, target)

    assert backup is None
    assert target.read_bytes() == b"new-db"
    assert not restored.exists()  # moved, not copied


def test_install_warehouse_backs_up_existing_never_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "health.duckdb"
    target.write_bytes(b"old-db")
    restored = tmp_path / "restored.duckdb"
    restored.write_bytes(b"new-db")

    backup = restore.install_warehouse(restored, target)

    assert backup is not None
    assert backup.read_bytes() == b"old-db"  # prior warehouse preserved
    assert backup.name.startswith("health.duckdb.bak-")
    assert target.read_bytes() == b"new-db"  # restored copy installed


def test_verify_warehouse_opens_accepts_real_db(tmp_path: Path) -> None:
    db = tmp_path / "health.duckdb"
    duck.connect(db).close()  # materialize a valid DuckDB file
    restore.verify_warehouse_opens(db)  # does not raise


def test_verify_warehouse_opens_rejects_garbage(tmp_path: Path) -> None:
    db = tmp_path / "health.duckdb"
    db.write_bytes(struct.pack("64s", b"not a duckdb file"))
    with pytest.raises(restore.RestoreError):
        restore.verify_warehouse_opens(db)
