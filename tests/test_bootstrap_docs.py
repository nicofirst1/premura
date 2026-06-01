"""Lightweight docs-drift guards for the shipped ``hpipe bootstrap`` command.

These tests do not freeze prose. They assert only stable command names and
boundary words so the docs cannot silently drop the fresh-clone setup command or
oversell it as a runtime health-data operation. Read the doc files at runtime
relative to the repo root so the checks survive prose edits.
"""

from __future__ import annotations

from pathlib import Path

# tests/ lives at the repo root, so the repo root is one directory up.
REPO_ROOT = Path(__file__).resolve().parent.parent

README = REPO_ROOT / "README.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
STATUS = REPO_ROOT / "docs" / "operations" / "STATUS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_mentions_hpipe_bootstrap() -> None:
    """The root README must route a fresh clone to ``hpipe bootstrap``."""
    text = _read(README).lower()
    assert "hpipe bootstrap" in text
    # The command lives in the setup / quick-start area, not buried elsewhere.
    assert "quick start" in text


def test_contributing_mentions_bootstrap_without_dropping_dev_checks() -> None:
    """CONTRIBUTING names bootstrap AND keeps the dev validation guidance."""
    text = _read(CONTRIBUTING).lower()
    assert "hpipe bootstrap" in text
    # Development validation guidance must survive.
    for check in ("pytest", "ruff", "mypy"):
        assert check in text, f"CONTRIBUTING dropped the {check} dev check"


def test_status_records_setup_only_boundary() -> None:
    """STATUS records bootstrap as setup-only, not as ingest/upload/analysis."""
    text = _read(STATUS).lower()
    assert "hpipe bootstrap" in text
    assert "setup" in text
    # The shipped boundary: bootstrap is not a runtime health-data operation.
    # Guard against the doc describing it as the things it must never do.
    forbidden_claims = [
        "bootstrap ingests",
        "bootstrap uploads",
        "bootstrap analyzes",
        "bootstrap analyses",
    ]
    for claim in forbidden_claims:
        assert claim not in text, f"STATUS overstates bootstrap as: {claim!r}"
