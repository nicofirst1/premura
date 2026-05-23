"""macOS user-facing notifications via osascript."""

from __future__ import annotations

import shutil
import subprocess


def is_available() -> bool:
    return shutil.which("osascript") is not None


def notify(title: str, body: str, *, subtitle: str | None = None) -> bool:
    """Fire a macOS notification. Best-effort: returns True on success."""
    if not is_available():
        return False
    safe_title = title.replace('"', "'")
    safe_body = body.replace('"', "'")
    parts = [f'display notification "{safe_body}"', f'with title "{safe_title}"']
    if subtitle:
        safe_sub = subtitle.replace('"', "'")
        parts.append(f'subtitle "{safe_sub}"')
    script = " ".join(parts)
    res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    return res.returncode == 0


__all__ = ["is_available", "notify"]
