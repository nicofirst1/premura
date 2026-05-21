"""FR-6 regression: encrypt → decrypt round-trip with a per-test age keypair."""
from __future__ import annotations

import filecmp
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest

from premura import encrypt

pytestmark = pytest.mark.skipif(
    not encrypt.is_available(),
    reason="age / age-keygen not installed",
)


def _generate_keypair(key_path: Path) -> str:
    """Run `age-keygen` and return the public recipient string.

    age-keygen writes the private key (with a `# public key:` comment header)
    to the file, and ALSO prints `Public key: age1...` to stderr.
    """
    res = subprocess.run(
        ["age-keygen", "-o", str(key_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in res.stderr.splitlines():
        if line.lower().startswith("public key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"could not parse public key from age-keygen output: {res.stderr!r}")


def test_age_roundtrip_byte_identical(tmp_path: Path) -> None:
    """Encrypting a synthetic ~1KB blob and decrypting it yields the original bytes."""
    key_path = tmp_path / "age.key"
    recipients_path = tmp_path / "recipients.txt"
    plaintext_path = tmp_path / "warehouse.duckdb"
    ciphertext_path = tmp_path / "warehouse.duckdb.age"
    decrypted_path = tmp_path / "warehouse.decrypted.duckdb"

    recipient = _generate_keypair(key_path)
    recipients_path.write_text(recipient + "\n")
    # age-keygen creates the key file world-readable on macOS; tighten so age
    # doesn't warn when mode is too open.
    os.chmod(key_path, 0o600)

    plaintext = secrets.token_bytes(1024)
    plaintext_path.write_bytes(plaintext)

    encrypt.encrypt_file(plaintext_path, ciphertext_path, recipients_file=recipients_path)
    assert ciphertext_path.stat().st_size > 0
    assert ciphertext_path.read_bytes() != plaintext

    encrypt.decrypt_file(ciphertext_path, decrypted_path, identity_file=key_path)
    assert filecmp.cmp(plaintext_path, decrypted_path, shallow=False), "decrypted bytes diverged"
    assert decrypted_path.read_bytes() == plaintext


def test_recipient_fingerprint_matches_keygen(tmp_path: Path) -> None:
    """The recipient written into recipients.txt is what `recipient_fingerprint` reports."""
    key_path = tmp_path / "age.key"
    recipients_path = tmp_path / "recipients.txt"
    recipient = _generate_keypair(key_path)
    recipients_path.write_text(f"# generated for tests\n{recipient}\n")
    assert encrypt.recipient_fingerprint(recipients_path) == recipient


def test_decrypt_with_wrong_identity_fails(tmp_path: Path) -> None:
    """A keypair other than the recipient cannot decrypt the artifact."""
    key_a = tmp_path / "a.key"
    key_b = tmp_path / "b.key"
    recipients_a = tmp_path / "recipients_a.txt"
    plaintext_path = tmp_path / "data.bin"
    ciphertext_path = tmp_path / "data.bin.age"
    out_path = tmp_path / "data.out.bin"

    rec_a = _generate_keypair(key_a)
    _generate_keypair(key_b)
    os.chmod(key_a, 0o600)
    os.chmod(key_b, 0o600)
    recipients_a.write_text(rec_a + "\n")
    plaintext_path.write_bytes(secrets.token_bytes(512))

    encrypt.encrypt_file(plaintext_path, ciphertext_path, recipients_file=recipients_a)
    with pytest.raises(encrypt.AgeError):
        encrypt.decrypt_file(ciphertext_path, out_path, identity_file=key_b)


def test_age_unavailable_reports_cleanly(monkeypatch) -> None:
    """`is_available()` returns False when the binaries are not on PATH."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert encrypt.is_available() is False
