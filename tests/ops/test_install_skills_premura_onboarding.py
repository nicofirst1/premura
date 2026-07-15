"""The `premura` first-run onboarding skill installs via the existing
single-home installer.

Verify-only regression test mirroring the other skill-install tests: proves the
public :func:`premura.skills.install_skills` discovers the new skill directory
(by its ``SKILL.md``) and materializes it idempotently under
``<target>/.claude/skills/premura/``. This skill ships no sibling resources -
it references the runtime/human-facing contracts rather than embedding them - so
only ``SKILL.md`` is asserted. All work happens under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

SKILL_NAME = "premura"


def test_premura_onboarding_skill_installs(tmp_path: Path) -> None:
    from premura.skills import install_skills

    written = install_skills(tmp_path)

    manifest = tmp_path / ".claude" / "skills" / SKILL_NAME / "SKILL.md"

    assert manifest.is_file(), "SKILL.md not materialised for premura onboarding skill"
    assert manifest in written, "SKILL.md should be reported as written on first install"
    assert manifest.read_text(encoding="utf-8").lstrip().startswith("---"), (
        "SKILL.md should carry YAML frontmatter"
    )


def test_premura_onboarding_install_is_idempotent(tmp_path: Path) -> None:
    from premura.skills import install_skills

    install_skills(tmp_path)

    manifest = tmp_path / ".claude" / "skills" / SKILL_NAME / "SKILL.md"
    before = manifest.read_bytes()

    rewritten = install_skills(tmp_path)

    assert manifest not in rewritten, "idempotent run rewrote the premura SKILL.md"
    assert manifest.read_bytes() == before, "SKILL.md mutated on idempotent run"
