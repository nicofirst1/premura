"""Throwaway sandbox for parser-build ingest isolation (FR-020).

A :class:`Sandbox` is a temp copy of the **tracked** repo tree (from
``git ls-files``, never a blind recursive copy) with the warehouse and the
session-log paths redirected into the temp dir. It lets an agent edit parser
files and run a real ingest without ever touching the real repo or the real
warehouse; teardown removes everything so no extracted data persists (NFR-004).

The runner that consumes a sandbox lives in
:mod:`premura.harness.ingest_runner`; this module only builds and disposes the
isolation boundary.
"""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from ulid import ULID

# Tracked paths whose top-level segment matches one of these are never copied
# into the sandbox: they are either huge, derived, or noise that breaks
# reproducibility from a clean clone (R2 / NFR-002). ``.git`` and ``.venv``
# never appear in ``git ls-files``; ``kitty-specs`` / ``.worktrees`` / ``data``
# can, so they are filtered explicitly.
EXCLUDED_TOP_LEVEL: frozenset[str] = frozenset(
    {".git", ".venv", "data", "kitty-specs", ".worktrees"}
)


def _premura_version() -> str:
    try:
        return importlib.metadata.version("premura")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - dev fallback
        return "0+unknown"


def _git_paths(repo_root: Path, *git_args: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo_root), *git_args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def _tracked_files(repo_root: Path) -> list[str]:
    """Return the working-tree paths to copy (relative, POSIX).

    Tracked files only (``git ls-files``) so the sandbox input is deterministic
    from a clean checkout (R2 / NFR-002) and never scoops up arbitrary
    untracked scratch from the parent working tree (NFR-004 containment). The
    explicit :data:`EXCLUDED_TOP_LEVEL` filter then drops the huge/derived trees
    (``data``, ``kitty-specs``, ``.worktrees``, …) that git may still track in a
    given checkout. Reference parsers and agent edits arrive *into* the sandbox
    via :func:`install_parser` and in-sandbox edits — never by copying parent
    untracked files in.
    """
    paths = _git_paths(repo_root, "ls-files")
    kept: list[str] = []
    seen: set[str] = set()
    for rel in paths:
        if rel in seen:
            continue
        seen.add(rel)
        top = rel.split("/", 1)[0]
        if top in EXCLUDED_TOP_LEVEL:
            continue
        kept.append(rel)
    return kept


@dataclass(slots=True)
class Sandbox:
    """A throwaway copy of the tracked repo tree with redirected data paths.

    ``root`` is the temp copy; ``warehouse_path`` and ``session_log_path`` point
    at (not-yet-created) temp files inside it so a real ingest can run without
    touching the real warehouse or the real session log.
    """

    root: Path
    warehouse_path: Path
    session_log_path: Path
    isolation_tag: str
    premura_version: str

    def teardown(self) -> None:
        """Recursively remove the entire sandbox tree (NFR-004 PHI containment)."""
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.teardown()


def build_sandbox(repo_root: Path) -> Sandbox:
    """Build a sandbox from the tracked tree of ``repo_root``.

    Copies only ``git ls-files`` paths (minus :data:`EXCLUDED_TOP_LEVEL`) into a
    fresh temp dir, preserving relative structure, and redirects the warehouse
    and session-log paths into ``<root>/data/``.
    """
    repo_root = repo_root.resolve()
    root = Path(tempfile.mkdtemp(prefix="premura-sandbox-"))

    for rel in _tracked_files(repo_root):
        src = repo_root / rel
        if not src.is_file():
            # tracked path that is absent in this checkout (e.g. a submodule
            # gitlink) — nothing to copy.
            continue
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    return Sandbox(
        root=root,
        warehouse_path=data_dir / "warehouse.duckdb",
        session_log_path=data_dir / "session_log.duckdb",
        isolation_tag=str(ULID()),
        premura_version=_premura_version(),
    )


def install_parser(sandbox: Sandbox, parser_src: Path, dest_relpath: str) -> Path:
    """Copy a reference parser module into the sandbox tree (models an agent edit).

    ``dest_relpath`` is relative to the sandbox root, e.g.
    ``"src/premura/parsers/<name>.py"``. Returns the installed absolute path.

    Note on dim_metric: slice-one reference parsers only emit ``heart_rate``,
    which already exists in ``dim_metric.yaml``, so no append is needed. A parser
    declaring a NEW canonical metric would also require the agent to append a row
    to the sandbox's ``src/premura/dim_metric.yaml`` before the ingest seam would
    validate it — out of scope for the committed reference parsers.
    """
    dest = sandbox.root / dest_relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(parser_src, dest)
    return dest


__all__ = ["EXCLUDED_TOP_LEVEL", "Sandbox", "build_sandbox", "install_parser"]
