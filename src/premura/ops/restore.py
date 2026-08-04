"""Non-destructive local install of a decrypted warehouse pulled from Drive.

`premura upload` is additive on the remote; the only destructive risk in the
inverse `premura download` is the local warehouse swap. These helpers keep that
swap safe: resolve which month to pull, prove the decrypted DB opens, and back
up any existing warehouse before moving the restored copy into place.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from ..store import duck

_MONTH_RE = re.compile(r"(?:^|/)(\d{4})/(\d{2})/")


class RestoreError(RuntimeError):
    pass


def parse_latest_month(names: list[str]) -> str | None:
    """Latest ``YYYY-MM`` among month-partitioned remote paths, or ``None``.

    ``names`` are rclone-lsl relative paths like ``2026/07/health.duckdb.age``;
    entries that are not under a ``YYYY/MM/`` partition are ignored.
    """
    months = {f"{m.group(1)}-{m.group(2)}" for n in names if (m := _MONTH_RE.search(n))}
    return max(months) if months else None


def verify_warehouse_opens(db_path: Path) -> None:
    """Prove a decrypted warehouse is a readable DuckDB file before the swap.

    Opens ``db_path`` read-only and runs a trivial query. Raises
    :class:`RestoreError` if the file is missing or not a valid DuckDB database,
    so a corrupt download never replaces a good local warehouse.
    """
    try:
        con = duck.connect(db_path, read_only=True)
    except Exception as exc:  # duckdb raises its own IOException hierarchy
        raise RestoreError(f"decrypted warehouse does not open: {exc}") from exc
    try:
        con.execute("SELECT 1")
    finally:
        con.close()


def install_warehouse(restored: Path, target: Path) -> Path | None:
    """Move ``restored`` to ``target``, backing up any existing warehouse first.

    Never overwrites in place: an existing ``target`` is renamed to a
    timestamped ``<name>.bak-<ts>`` sibling before the restored copy is moved in.
    Returns the backup path, or ``None`` when there was no prior warehouse.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if target.exists():
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup = target.with_name(f"{target.name}.bak-{ts}")
        target.rename(backup)
    shutil.move(str(restored), str(target))
    return backup


__all__ = ["RestoreError", "install_warehouse", "parse_latest_month", "verify_warehouse_opens"]
