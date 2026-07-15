"""Docs-structure gates (issue #21): STATUS.md stays a bounded snapshot.

STATUS.md is the single home for shipped-state counts and must remain a short,
fully rewritable snapshot. Mission narratives belong in docs/shared/CHANGELOG.md
(append-only). The line cap here is the machine gate that keeps the next twenty
missions from growing STATUS.md back into a changelog.
"""

from tests import REPO_ROOT

STATUS = REPO_ROOT / "docs" / "shared" / "STATUS.md"
CHANGELOG = REPO_ROOT / "docs" / "shared" / "CHANGELOG.md"

STATUS_MAX_LINES = 250


def test_status_is_a_bounded_snapshot() -> None:
    line_count = len(STATUS.read_text().splitlines())
    assert line_count <= STATUS_MAX_LINES, (
        f"STATUS.md is {line_count} lines (cap {STATUS_MAX_LINES}). It is a "
        "rewritable snapshot, not a changelog: move mission narratives to "
        "docs/shared/CHANGELOG.md and rewrite superseded lines instead of "
        "appending new sections."
    )


def test_changelog_exists_and_declares_append_only() -> None:
    assert CHANGELOG.is_file(), "docs/shared/CHANGELOG.md must exist (issue #21)"
    assert "append-only" in CHANGELOG.read_text(), (
        "CHANGELOG.md must keep its append-only header rule"
    )
