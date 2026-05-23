"""Thin subprocess wrapper around `age` for at-rest encryption."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class AgeError(RuntimeError):
    pass


def is_available() -> bool:
    return shutil.which("age") is not None and shutil.which("age-keygen") is not None


def encrypt_file(input_path: Path, output_path: Path, *, recipients_file: Path) -> Path:
    """`age -R recipients.txt -o output.age input` — overwrites output."""
    if not recipients_file.is_file():
        raise AgeError(f"recipients file not found: {recipients_file}")
    if not input_path.is_file():
        raise AgeError(f"input not found: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["age", "-R", str(recipients_file), "-o", str(output_path), str(input_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise AgeError(f"age failed (rc={res.returncode}): {res.stderr.strip()}")
    return output_path


def decrypt_file(input_path: Path, output_path: Path, *, identity_file: Path) -> Path:
    """`age -d -i age.key -o output input.age`."""
    if not identity_file.is_file():
        raise AgeError(f"identity file not found: {identity_file}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["age", "-d", "-i", str(identity_file), "-o", str(output_path), str(input_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise AgeError(f"age decrypt failed (rc={res.returncode}): {res.stderr.strip()}")
    return output_path


def recipient_fingerprint(recipients_file: Path) -> str | None:
    if not recipients_file.is_file():
        return None
    for line in recipients_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


__all__ = ["AgeError", "decrypt_file", "encrypt_file", "is_available", "recipient_fingerprint"]
