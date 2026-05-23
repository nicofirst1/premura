"""Thin subprocess wrapper around `rclone` for Drive uploads."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class RcloneError(RuntimeError):
    pass


def is_available() -> bool:
    return shutil.which("rclone") is not None


def remote_reachable(remote: str) -> bool:
    cmd = ["rclone", "about", f"{remote}:"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.returncode == 0


def upload_directory(
    local_dir: Path,
    *,
    remote: str,
    remote_prefix: str,
    year: int | str,
    month: int | str,
    extra_flags: tuple[str, ...] = ("--transfers", "2", "--checksum", "--immutable"),
) -> str:
    """`rclone copy local_dir remote:prefix/YYYY/MM/`. Returns the destination URI."""
    mo_str = f"{int(month):02d}"
    yr_str = str(year)
    dst = f"{remote}:{remote_prefix.rstrip('/')}/{yr_str}/{mo_str}/"
    cmd = ["rclone", "copy", str(local_dir), dst, *extra_flags]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RcloneError(f"rclone copy failed (rc={res.returncode}): {res.stderr.strip()}")
    return dst


def list_remote(remote_path: str) -> list[tuple[int, str]]:
    """`rclone lsl remote:path/` → [(size_bytes, filename), ...]."""
    cmd = ["rclone", "lsl", remote_path]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RcloneError(f"rclone lsl failed (rc={res.returncode}): {res.stderr.strip()}")
    out: list[tuple[int, str]] = []
    for line in res.stdout.splitlines():
        parts = line.strip().split(maxsplit=3)
        if len(parts) >= 4:
            try:
                size = int(parts[0])
            except ValueError:
                continue
            out.append((size, parts[3]))
    return out


__all__ = ["RcloneError", "is_available", "list_remote", "remote_reachable", "upload_directory"]
