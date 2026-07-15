"""WP04 (FR-003, FR-004): the ``research-trace-audit`` skill installs via the
existing single-home installer, bundled resources and all.

This is a *verify-only* regression test. WP01's research (Packaging
Recommendation, ``research/wp0-skill-research.md``) ADOPTED write-once-by-
conformance content but **rejected** a separate OpenCode / multi-home installer
target: OpenCode scans the same ``.claude/skills/`` path Premura already writes
to, so a second writer would only create dead, redundant files. Therefore this
WP adds *no* installer code and *no* multi-home test — it proves that the
existing public :func:`premura.skills.install_skills` already discovers the new
skill directory (by its ``SKILL.md``) and copies every sibling resource
(``AUDIT_RUBRIC.md`` and ``fixtures/*.json``) recursively, idempotently.

Per DIRECTIVE_036 the proof is through the public ``install_skills`` function
and observable on-disk bytes only; no private helpers are patched or asserted
on. Per DIRECTIVE_034 the test precedes (and now guards) the behavior. All work
happens under ``tmp_path``; nothing is written into the repo.
"""

from __future__ import annotations

from pathlib import Path

SKILL_NAME = "research-trace-audit"


def test_research_trace_audit_skill_and_resources_install(tmp_path: Path) -> None:
    """FR-003: the new skill + its bundled resources materialize under
    ``<target>/.claude/skills/research-trace-audit/`` via the existing
    single-home installer (no OpenCode/multi-home target — WP01 rejected it)."""
    from premura.skills import install_skills

    written = install_skills(tmp_path)

    skill_dir = tmp_path / ".claude" / "skills" / SKILL_NAME
    manifest = skill_dir / "SKILL.md"
    rubric = skill_dir / "AUDIT_RUBRIC.md"

    assert manifest.is_file(), "SKILL.md not materialised for research-trace-audit"
    assert manifest in written, "SKILL.md should be reported as written on first install"

    # Sibling resource (non-SKILL.md) must be copied — the WP04 packaging risk.
    assert rubric.is_file(), "AUDIT_RUBRIC.md sibling resource was not bundled"
    assert rubric in written, "AUDIT_RUBRIC.md should be reported as written on first install"

    # At least one fixture JSON must land under the recursively-copied fixtures/ dir.
    fixtures = sorted((skill_dir / "fixtures").glob("*.json"))
    assert fixtures, "no fixtures/*.json copied under research-trace-audit/"
    assert all(f in written for f in fixtures), "fixtures should be reported as written"

    # The bundled bytes must match the shipped resource bytes (real copy, not stub).
    assert manifest.read_text(encoding="utf-8").lstrip().startswith("---"), (
        "SKILL.md should carry YAML frontmatter"
    )
    assert rubric.read_bytes(), "AUDIT_RUBRIC.md copied empty"


def test_research_trace_audit_install_is_idempotent(tmp_path: Path) -> None:
    """FR-004: a second ``install_skills`` run rewrites nothing for the new
    skill (sha256 skip) and leaves the on-disk bytes untouched."""
    from premura.skills import install_skills

    install_skills(tmp_path)

    skill_dir = tmp_path / ".claude" / "skills" / SKILL_NAME
    tracked = [
        skill_dir / "SKILL.md",
        skill_dir / "AUDIT_RUBRIC.md",
        *sorted((skill_dir / "fixtures").glob("*.json")),
    ]
    before = {p: p.read_bytes() for p in tracked}

    rewritten = install_skills(tmp_path)

    # None of the research-trace-audit files should be rewritten on the 2nd run.
    assert not any(p in rewritten for p in tracked), (
        f"idempotent run rewrote research-trace-audit files: {rewritten}"
    )
    for path, original in before.items():
        assert path.read_bytes() == original, f"{path.name} mutated on idempotent run"
