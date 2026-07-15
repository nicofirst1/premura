"""Every backticked file reference in a package doc must resolve to a real file.

Convention (CONTRIBUTING.md §"Architecture boundaries"): cross-file references in
the ``src/premura`` docs are written as an inline-code path in backticks -
``` `src/premura/engine/CONTRACT.md` ```. The backticks are the marker that tells
"this is a checkable reference" apart from prose that merely names a file, so this
test can extract them mechanically and confirm the target exists. Markdown links
and bare prose mentions are intentionally *not* checked - if you want a reference
guarded, put its path in backticks.

Resolution is lenient on the base directory (repo root, the doc's own directory,
or the ``src/premura`` package root) because the codebase cites both full paths and
package-relative ones; a reference passes if it resolves under any of them.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC_ROOT = _REPO_ROOT / "src" / "premura"

#: Extensions that mark a backticked token as a file reference worth checking.
_EXTENSIONS = (".md", ".py", ".yaml", ".yml", ".sql")


#: Bases a reference may be written relative to (first hit wins).
def _bases(doc: Path) -> tuple[Path, ...]:
    return (_REPO_ROOT, doc.parent, _DOC_ROOT)


_BACKTICK = re.compile(r"`([^`]+)`")
_TRAILING_LINE = re.compile(r":\d+(?:-\d+)?$")


def _candidate(token: str) -> str | None:
    """Reduce a backticked token to a bare path, or None if it is not a reference."""
    token = token.strip()
    if token.startswith(("http://", "https://")) or "*" in token:
        return None
    if "<" in token or ">" in token:  # a placeholder like views/<domain>.py, not a path
        return None
    # Drop a trailing section (§), anchor (#), or whitespace-delimited suffix.
    token = re.split(r"[\s§#]", token, maxsplit=1)[0]
    token = _TRAILING_LINE.sub("", token)
    token = token.lstrip("./").lstrip("/")
    if not token.endswith(_EXTENSIONS):
        return None
    return token


def _resolves(path: str, doc: Path) -> bool:
    return any((base / path).is_file() for base in _bases(doc))


def _iter_references() -> list[tuple[Path, str]]:
    refs: list[tuple[Path, str]] = []
    for doc in sorted(_DOC_ROOT.rglob("*.md")):
        for token in _BACKTICK.findall(doc.read_text(encoding="utf-8")):
            path = _candidate(token)
            if path is not None:
                refs.append((doc, path))
    return refs


def test_backticked_doc_references_resolve() -> None:
    broken = [
        f"{doc.relative_to(_REPO_ROOT)}: `{path}`"
        for doc, path in _iter_references()
        if not _resolves(path, doc)
    ]
    assert not broken, "Backticked file references that do not resolve:\n" + "\n".join(
        sorted(broken)
    )
