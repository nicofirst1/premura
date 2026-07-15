"""Docs-structure gate: CHANGELOG.md stays the append-only narrative home.

Shipped-state counts have no doc home — they live in the code (`premura --help`,
`premura status`, the pinned inventory tests). Mission narratives belong in
docs/shared/CHANGELOG.md, append-only.
"""

from tests import REPO_ROOT

CHANGELOG = REPO_ROOT / "docs" / "shared" / "CHANGELOG.md"


def test_changelog_exists_and_declares_append_only() -> None:
    assert CHANGELOG.is_file(), "docs/shared/CHANGELOG.md must exist (issue #21)"
    assert "append-only" in CHANGELOG.read_text(), (
        "CHANGELOG.md must keep its append-only header rule"
    )
