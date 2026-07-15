"""Phase 5 slice 3: the ``human-facing-teaching`` skill installs via the existing
single-home installer, bundled rubric and all.

Mirrors ``test_install_skills_research_trace_audit.py``: no installer code is
added — :func:`premura.skills.install_skills` already discovers any directory
with a ``SKILL.md`` and copies every sibling resource idempotently.
``DISCLOSURE_RUBRIC.md``'s single authoritative home is this skill dir (like
``AUDIT_RUBRIC.md``); nothing else keeps a copy.
"""

from __future__ import annotations

from pathlib import Path

from tests import REPO_ROOT

SKILL_NAME = "human-facing-teaching"
BUNDLED_RUBRIC = REPO_ROOT / "src" / "premura" / "skills" / SKILL_NAME / "DISCLOSURE_RUBRIC.md"


def test_human_facing_teaching_skill_and_resources_install(tmp_path: Path) -> None:
    """The new skill + its bundled rubric materialize under
    ``<target>/.claude/skills/human-facing-teaching/`` via the existing
    single-home installer (discovered by its ``SKILL.md``, no new installer code)."""
    from premura.skills import install_skills

    written = install_skills(tmp_path)

    skill_dir = tmp_path / ".claude" / "skills" / SKILL_NAME
    manifest = skill_dir / "SKILL.md"
    rubric = skill_dir / "DISCLOSURE_RUBRIC.md"

    assert manifest.is_file(), "SKILL.md not materialised for human-facing-teaching"
    assert manifest in written, "SKILL.md should be reported as written on first install"

    assert rubric.is_file(), "DISCLOSURE_RUBRIC.md sibling resource was not bundled"
    assert rubric in written, "DISCLOSURE_RUBRIC.md should be reported as written on first install"

    assert manifest.read_text(encoding="utf-8").lstrip().startswith("---"), (
        "SKILL.md should carry YAML frontmatter"
    )
    assert rubric.read_bytes(), "DISCLOSURE_RUBRIC.md copied empty"


def test_human_facing_teaching_install_is_idempotent(tmp_path: Path) -> None:
    """A second ``install_skills`` run rewrites nothing for the new skill (sha256
    skip) and leaves the on-disk bytes untouched."""
    from premura.skills import install_skills

    install_skills(tmp_path)

    skill_dir = tmp_path / ".claude" / "skills" / SKILL_NAME
    tracked = [skill_dir / "SKILL.md", skill_dir / "DISCLOSURE_RUBRIC.md"]
    before = {p: p.read_bytes() for p in tracked}

    rewritten = install_skills(tmp_path)

    assert not any(p in rewritten for p in tracked), (
        f"idempotent run rewrote human-facing-teaching files: {rewritten}"
    )
    for path, original in before.items():
        assert path.read_bytes() == original, f"{path.name} mutated on idempotent run"
