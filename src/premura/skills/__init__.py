"""Premura Claude Code skills bundled as package data.

This package ships Claude Code "skills" — SKILL.md files (plus optional sibling
resources) — alongside the runtime code. The single helper exposed here,
:func:`install_skills`, materializes those files under a target project's
``.claude/skills/`` directory using ``importlib.resources`` so it works in
editable installs, wheels, and zipapps.

The helper is intentionally small: no external dependencies, no symlink magic,
deterministic sha256-based idempotency. See FR-011..FR-014 in the v2 skeleton
spec for the contract this module implements.
"""

from __future__ import annotations

import hashlib
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path

__all__ = ["install_skills"]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _iter_skill_dirs(root: Traversable) -> list[Traversable]:
    """Return every immediate child of ``root`` that contains a ``SKILL.md``.

    A "skill" is any directory under ``premura.skills`` that ships a
    ``SKILL.md`` manifest at its top level. We intentionally only look one
    level deep; nested subdirectories within a skill are still copied (see
    ``_iter_skill_files``), but only the top-level dir name is treated as the
    skill identifier.
    """
    skills: list[Traversable] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        manifest = child.joinpath("SKILL.md")
        if manifest.is_file():
            skills.append(child)
    return skills


def _iter_skill_files(skill_dir: Traversable) -> list[tuple[Traversable, tuple[str, ...]]]:
    """Walk a skill directory, yielding ``(traversable, relative_parts)``.

    ``relative_parts`` is the path of the file relative to the skill root,
    suitable for joining onto the destination directory.
    """
    out: list[tuple[Traversable, tuple[str, ...]]] = []

    def _walk(node: Traversable, parts: tuple[str, ...]) -> None:
        for child in node.iterdir():
            if child.is_dir():
                _walk(child, parts + (child.name,))
            else:
                out.append((child, parts + (child.name,)))

    _walk(skill_dir, ())
    return out


def install_skills(target_root: Path) -> list[Path]:
    """Materialize every shipped skill under ``target_root/.claude/skills/``.

    Parameters
    ----------
    target_root:
        Project root that should receive the skills. The function will
        create ``target_root/.claude/skills/<skill-name>/`` directories as
        needed. ``target_root`` itself must already exist.

    Returns
    -------
    list[Path]
        The files actually written or rewritten. Files whose on-disk sha256
        already matches the shipped resource are left untouched and are not
        included in the return value.
    """
    target_root = Path(target_root)
    skills_root = target_root / ".claude" / "skills"
    written: list[Path] = []

    package_root = files("premura.skills")
    for skill_dir in _iter_skill_dirs(package_root):
        dest_skill_dir = skills_root / skill_dir.name
        for resource, rel_parts in _iter_skill_files(skill_dir):
            dest_file = dest_skill_dir.joinpath(*rel_parts)
            with as_file(resource) as src_path:
                src_bytes = Path(src_path).read_bytes()
            src_sha = _sha256_bytes(src_bytes)
            if dest_file.exists() and _sha256_file(dest_file) == src_sha:
                continue
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_bytes(src_bytes)
            written.append(dest_file)
    return written
