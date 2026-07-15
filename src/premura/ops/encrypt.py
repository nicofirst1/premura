"""Thin subprocess wrapper around `age` for at-rest encryption."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class AgeError(RuntimeError):
    pass


def is_available() -> bool:
    return shutil.which("age") is not None and shutil.which("age-keygen") is not None


def _public_key(key_path: Path) -> str | None:
    """The ``age1…`` recipient from an ``age-keygen`` identity file, or None."""
    for line in key_path.read_text().splitlines():
        if line.startswith("# public key:"):
            return line.split(":", 1)[1].strip()
    return None


def generate_keypair(*, key_path: Path, recipients_path: Path) -> str:
    """Create an age identity at ``key_path`` and write its public key to
    ``recipients_path`` (0600 both). Returns the public recipient string.

    Portable equivalent of the macOS ``ops/bootstrap.sh`` keygen step, so any
    OS can create the single secret via ``premura bootstrap``. Raises
    :class:`AgeError` if ``age-keygen`` is absent or generation fails.
    """
    if shutil.which("age-keygen") is None:
        raise AgeError("age-keygen not installed")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["age-keygen", "-o", str(key_path)], capture_output=True, text=True, check=False
    )
    if res.returncode != 0:
        raise AgeError(f"age-keygen failed (rc={res.returncode}): {res.stderr.strip()}")
    key_path.chmod(0o600)
    pub = _public_key(key_path)
    if pub is None:
        raise AgeError(f"could not read public key from {key_path}")
    recipients_path.parent.mkdir(parents=True, exist_ok=True)
    recipients_path.write_text(pub + "\n")
    recipients_path.chmod(0o600)
    return pub


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


def roundtrip_check(*, recipients_file: Path, identity_file: Path) -> str | None:
    """Encrypt+decrypt a tiny probe; returns None on success, a reason on failure.

    Proves the on-disk identity (key) file can decrypt what the current
    recipients file encrypts — a rotated or mismatched key/recipients pair
    fails here even when both files exist and are readable.
    """
    if not is_available():
        return "age / age-keygen not installed"
    probe = b"premura doctor backup round-trip probe\n"
    with tempfile.TemporaryDirectory(prefix="premura-doctor-") as td:
        tmp = Path(td)
        plain = tmp / "probe.txt"
        plain.write_bytes(probe)
        try:
            encrypt_file(plain, tmp / "probe.age", recipients_file=recipients_file)
            decrypt_file(tmp / "probe.age", tmp / "probe.out", identity_file=identity_file)
        except AgeError as exc:
            return str(exc)
        if (tmp / "probe.out").read_bytes() != probe:
            return "decrypted probe does not match original"
    return None


def recipient_fingerprint(recipients_file: Path) -> str | None:
    if not recipients_file.is_file():
        return None
    for line in recipients_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


__all__ = [
    "AgeError",
    "decrypt_file",
    "encrypt_file",
    "generate_keypair",
    "is_available",
    "recipient_fingerprint",
    "roundtrip_check",
]
