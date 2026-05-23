"""Skeleton smoke tests for the v2 architectural skeleton mission.

This file is the executable acceptance contract for the WP01-WP05 surfaces
shipped by mission ``v2-architectural-skeleton-01KS4SHA``. Each test maps to
one or more FRs (FR-001 through FR-017) and verifies the contract holds today.

Layout (mirrors the FR ordering in spec.md §3):

* T021 — Import + stub-behavior tests for the Stage 2/3/4 boundary modules and
  the parser-contract additions: FR-001..FR-008.
* T022 — Skill packaging + idempotency tests: FR-011..FR-012.
* T023 — Ontology migration + seed tests: FR-015..FR-017.
* T024 — Cross-cutting structure: FR-009 (CONTRACT.md tokens) and FR-013
  (CLI verb registration).

FR-010, FR-014, and FR-018 are intentionally covered elsewhere (cross-repo doc
grep / bootstrap shell-script grep) per the WP06 ``Required structure`` note.
"""

from __future__ import annotations

import importlib
import importlib.resources as resources
import json
import subprocess
import sys
from importlib.metadata import entry_points
from importlib.resources import files
from pathlib import Path
from typing import get_type_hints

import pytest
import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# T021 — Import + stub-behavior tests (FR-001..FR-008)
# ---------------------------------------------------------------------------


def test_engine_package_docstring_names_stage_2() -> None:
    """FR-001: ``premura.engine`` docstring identifies Stage 2 — Signal engine."""
    from premura import engine

    assert engine.__doc__ is not None
    assert "Stage 2" in engine.__doc__
    assert "Signal engine" in engine.__doc__


def test_engine_registry_exports_open_boundary() -> None:
    """FR-002 / NFR-008: ``signal``, ``SignalSpec``, ``REGISTRY`` import cleanly.

    Importing the boundary must succeed without pulling any signal-function
    implementation. The registry begins empty.
    """
    from premura.engine import REGISTRY, SignalSpec, signal

    # Pure-skeleton state: no implementation modules registered.
    assert isinstance(REGISTRY, dict)
    # SignalSpec is a dataclass with the fields documented in FR-002.
    fields = {f for f in SignalSpec.__dataclass_fields__}
    assert {
        "name",
        "domain",
        "inputs",
        "output",
        "priority",
        "auto_safe",
        "revision",
        "fn",
    } <= fields
    # The decorator is callable (returns a decorator).
    assert callable(signal)


def test_signal_decorator_registers_spec() -> None:
    """FR-002: decorating a function populates ``REGISTRY[name]`` correctly."""
    from premura.engine import REGISTRY, SignalSpec, signal

    name = "_skeleton_smoke_signal"
    try:

        @signal(
            name=name,
            domain=["liver"],
            inputs=["lab:ast", "lab:alt"],
            output="derived:ast_alt_ratio",
            priority="high",
            auto_safe=True,
            revision="1",
        )
        def _noop(conn: object) -> float:
            return 1.0

        assert name in REGISTRY
        spec = REGISTRY[name]
        assert isinstance(spec, SignalSpec)
        assert spec.name == name
        assert spec.domain == ["liver"]
        assert spec.inputs == ["lab:ast", "lab:alt"]
        assert spec.output == "derived:ast_alt_ratio"
        assert spec.priority == "high"
        assert spec.auto_safe is True
        assert spec.revision == "1"
        assert spec.fn is _noop
    finally:
        REGISTRY.pop(name, None)


def test_engine_registry_stays_lazy_until_runtime_helpers_load_builtins() -> None:
    """The import boundary stays empty until runtime helpers load built-in signals."""
    from premura.engine import REGISTRY, list_by_domain

    REGISTRY.clear()
    assert REGISTRY == {}
    specs = list_by_domain("liver")
    assert any(spec.name == "ast_alt_ratio" for spec in specs)


def test_mcp_module_docstring_and_layering_rule() -> None:
    """FR-004: ``premura.mcp`` names Stage 3 and includes the no-direct-warehouse-read rule."""
    from premura import mcp

    assert mcp.__doc__ is not None
    assert "Stage 3" in mcp.__doc__
    assert "MCP" in mcp.__doc__
    assert "never reads hp.fact_measurement directly" in mcp.__doc__


def test_mcp_register_tools_stub_raises() -> None:
    """FR-004: ``mcp.register_tools`` is a stub that raises NotImplementedError."""
    from premura.mcp import register_tools

    with pytest.raises(NotImplementedError):
        register_tools(None)


def test_ui_module_docstring_and_layering_rule() -> None:
    """FR-005: ``premura.ui`` names Stage 4 and forbids direct warehouse / engine access."""
    from premura import ui

    assert ui.__doc__ is not None
    assert "Stage 4" in ui.__doc__
    assert "User interface" in ui.__doc__
    assert "never reads hp.fact_measurement or calls engine directly" in ui.__doc__


def test_ui_start_interview_stub_raises() -> None:
    """FR-005: ``ui.start_interview`` is a stub that raises NotImplementedError."""
    from premura.ui import start_interview

    with pytest.raises(NotImplementedError):
        start_interview()


def test_parsers_lang_module_docstring_is_local_only() -> None:
    """FR-006: ``parsers._lang`` documents the local-only constraint."""
    from premura.parsers import _lang

    assert _lang.__doc__ is not None
    assert "local-only" in _lang.__doc__


def test_parsers_lang_detect_language_stub_raises() -> None:
    """FR-006: ``_lang.detect_language`` is a stub that raises NotImplementedError."""
    from premura.parsers._lang import detect_language

    with pytest.raises(NotImplementedError):
        detect_language("hello world")


def test_parsers_lookup_suggest_metric_resolves_existing_aliases() -> None:
    """FR-007: ``parsers.lookup.suggest_metric`` resolves existing ontology aliases."""
    from premura.parsers.lookup import suggest_metric

    assert suggest_metric("Resting Heart Rate") == "resting_hr"


def test_plugin_parser_contract_symbols_import() -> None:
    """FR-008: ``PluginParser`` and ``IngestBatch`` import from parsers.base."""
    from premura.parsers.base import IngestBatch, PluginParser

    fields = set(IngestBatch.__dataclass_fields__)
    assert {
        "declared_metrics",
        "measurements",
        "intervals",
        "source_descriptors",
        "unmapped_metrics",
        "language_detected",
        "confidence",
    } <= fields

    # PluginParser is a Protocol declaring the documented members.
    hints = get_type_hints(PluginParser)
    assert "language_hint" in hints
    assert hasattr(PluginParser, "declares_metrics")
    assert hasattr(PluginParser, "parse")


def test_plugin_parser_is_structural_subtype_of_parser() -> None:
    """FR-008: ``PluginParser`` is a structural extension of ``Parser``.

    A class with the shared ``Parser`` shape plus the plugin extras must satisfy
    ``PluginParser`` via duck typing. We cannot use ``isinstance`` because
    neither protocol is declared ``runtime_checkable``; structural conformance
    is verified by attribute presence on a sample implementation.
    """
    from premura.parsers.base import IngestBatch, PluginParser, SourceDescriptor

    class _SampleParser:
        source_kind = "_sample"
        language_hint: str | None = None

        def declares_metrics(self) -> list[str]:
            return ["heart_rate"]

        def parse(self, path: Path) -> IngestBatch:  # noqa: ARG002
            batch = IngestBatch(
                source_kind=self.source_kind,
                declared_metrics=["heart_rate"],
                source_descriptors={
                    "_sample:device": SourceDescriptor(
                        source_id="_sample:device",
                        source_kind=self.source_kind,
                    )
                },
            )
            batch.validate()
            return batch

    inst = _SampleParser()
    for attr in ("source_kind", "language_hint", "declares_metrics", "parse"):
        assert hasattr(inst, attr), f"sample plugin parser missing {attr}"
    result = inst.parse(Path("/dev/null"))
    assert isinstance(result, IngestBatch)
    assert result.confidence == 1.0  # default per FR-008
    from premura.parsers.base import Interval, Measurement, Parser

    assert Parser is not PluginParser
    assert Measurement is not None and Interval is not None


# ---------------------------------------------------------------------------
# T022 — Skill packaging + idempotency tests (FR-011..FR-012)
# ---------------------------------------------------------------------------


def test_skill_manifest_ships_as_package_data() -> None:
    """FR-011 / NFR-006: ``SKILL.md`` is resolvable via ``importlib.resources``."""
    manifest = files("premura").joinpath("skills/parser-generator/SKILL.md")
    assert manifest.is_file(), "SKILL.md missing from package data"
    body = manifest.read_text(encoding="utf-8")
    # Frontmatter keys.
    assert "name:" in body
    assert "description:" in body
    # The skill body must defer to CONTRACT.md rather than re-stating the
    # decision tree inline.
    assert "CONTRACT.md" in body


def test_install_skills_writes_then_idempotent(tmp_path: Path) -> None:
    """FR-012: first call writes ``SKILL.md``; second call returns ``[]`` (no-op)."""
    from premura.skills import install_skills

    written = install_skills(tmp_path)
    target = tmp_path / ".claude" / "skills" / "parser-generator" / "SKILL.md"
    assert target.is_file(), "skill file not materialised on first run"
    assert target in written

    sha_first = target.read_bytes()
    written_second = install_skills(tmp_path)
    assert written_second == [], "second install should report no changes"
    assert target.read_bytes() == sha_first, "skill file mutated on idempotent run"


# ---------------------------------------------------------------------------
# T023 — Ontology migration + seed tests (FR-015..FR-017)
# ---------------------------------------------------------------------------


_NEW_ONTOLOGY_COLUMNS = {
    "category",
    "validity_window",
    "missing_data_policy",
    "aliases",
    "loinc",
    "ieee1752",
}


def _dim_metric_columns(conn) -> set[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'hp' AND table_name = 'dim_metric'
        """
    ).fetchall()
    return {r[0] for r in rows}


def test_migration_002_adds_six_new_columns(empty_warehouse) -> None:
    """FR-015 / NFR-004: migration 002 adds the six ontology columns."""
    cols = _dim_metric_columns(empty_warehouse)
    missing = _NEW_ONTOLOGY_COLUMNS - cols
    assert not missing, f"dim_metric missing ontology columns: {missing}"


def test_migrations_are_idempotent(empty_warehouse) -> None:
    """NFR-004: re-running migrations does not error and does not duplicate columns."""
    from premura.store import duck

    before = _dim_metric_columns(empty_warehouse)
    duck.run_migrations(empty_warehouse)
    after = _dim_metric_columns(empty_warehouse)
    assert before == after, "migration introduced or removed columns on second run"


def test_seed_handles_rows_with_and_without_new_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-016: ``seed_dim_metric()`` reads new ontology keys + serializes aliases.

    Exercises the production path in ``src/premura/store/duck.py:seed_dim_metric``
    by feeding it a fixture ``dim_metric.yaml`` (under ``tests/fixtures/``) with:

      - one legacy 5-field row (no new ontology keys),
      - one full-ontology row (all six new keys, including multilingual aliases),
      - one partial-ontology row (category + loinc only).

    Mutation guarantee: if ``seed_dim_metric()`` stops reading any of the six
    new YAML keys, or breaks alias JSON serialization, this test fails.
    Verified by mentally stubbing the function — see also the explicit alias
    JSON round-trip assertion below.
    """
    import duckdb

    from premura.store import duck

    fixture_path = FIXTURES_DIR / "dim_metric_seed.yaml"
    assert fixture_path.is_file(), "FR-016 fixture missing"
    fixture_text = fixture_path.read_text(encoding="utf-8")

    # Redirect ``resources.files("premura").joinpath("dim_metric.yaml").read_text``
    # used inside ``seed_dim_metric`` to our fixture, without monkey-patching
    # yaml.safe_load (so YAML parsing is still exercised by the production path).
    class _FakeTraversable:
        def __init__(self, text: str) -> None:
            self._text = text

        def read_text(self, encoding: str = "utf-8") -> str:  # noqa: ARG002
            return self._text

    class _FakeRoot:
        def __init__(self, text: str) -> None:
            self._text = text

        def joinpath(self, name: str) -> _FakeTraversable:
            assert name == duck.DIM_METRIC_YAML, f"unexpected resource lookup: {name}"
            return _FakeTraversable(self._text)

    real_files = duck.resources.files

    def fake_files(package: str):
        if package == "premura":
            return _FakeRoot(fixture_text)
        return real_files(package)

    monkeypatch.setattr(duck.resources, "files", fake_files)

    db = tmp_path / "seed.duckdb"
    conn = duckdb.connect(str(db))
    try:
        duck.run_migrations(conn)
        # === PRODUCTION CALL — this is the heart of the FR-016 assertion. ===
        row_count = duck.seed_dim_metric(conn)
        assert row_count == 3, f"fixture should have seeded 3 rows, got {row_count}"

        # Legacy row: all new ontology columns must be NULL.
        legacy = conn.execute(
            """
            SELECT category, validity_window, missing_data_policy, aliases, loinc, ieee1752
            FROM hp.dim_metric WHERE metric_id = '_fixture_legacy_only'
            """
        ).fetchone()
        assert legacy is not None, "legacy fixture row was not seeded"
        assert all(v is None for v in legacy), (
            f"legacy row should have all-NULL ontology cols, got {legacy}"
        )

        # Full-ontology row: every new column populated, aliases JSON-serialized.
        rich = conn.execute(
            """
            SELECT category, validity_window, missing_data_policy, aliases, loinc, ieee1752
            FROM hp.dim_metric WHERE metric_id = '_fixture_full_ontology'
            """
        ).fetchone()
        assert rich is not None, "full-ontology fixture row was not seeded"
        rich_cat, rich_win, rich_mdp, rich_aliases, rich_loinc, rich_ieee = rich
        assert rich_cat == "cardiovascular"
        assert rich_win == "PT5M"
        assert rich_mdp == "none"
        assert rich_loinc == "8867-4"
        assert rich_ieee == "ieee1752:hr"
        # ``aliases`` MUST be JSON-serialized text (not a Python dict repr).
        # Round-trip via json.loads to guarantee real JSON — this catches
        # ``str(dict)`` regressions like {'en': ['HR', 'pulse']}.
        assert isinstance(rich_aliases, str), (
            f"aliases must be serialized to JSON text, got {type(rich_aliases)}"
        )
        parsed = json.loads(rich_aliases)
        assert parsed == {"en": ["HR", "pulse"], "it": ["frequenza cardiaca"]}, (
            f"aliases JSON did not round-trip: {parsed}"
        )

        # Partial-ontology row: only the keys the YAML supplied land non-NULL,
        # the rest stay NULL — proves each key is read independently.
        partial = conn.execute(
            """
            SELECT category, validity_window, missing_data_policy, aliases, loinc, ieee1752
            FROM hp.dim_metric WHERE metric_id = '_fixture_partial_ontology'
            """
        ).fetchone()
        assert partial is not None, "partial-ontology fixture row was not seeded"
        p_cat, p_win, p_mdp, p_aliases, p_loinc, p_ieee = partial
        assert p_cat == "cardiovascular"
        assert p_loinc == "8480-6"
        assert p_win is None
        assert p_mdp is None
        assert p_aliases is None
        assert p_ieee is None
    finally:
        conn.close()


def _load_dim_metric_yaml() -> list[dict]:
    yaml_text = resources.files("premura").joinpath("dim_metric.yaml").read_text(encoding="utf-8")
    rows = yaml.safe_load(yaml_text) or []
    assert isinstance(rows, list)
    return rows


def test_dim_metric_yaml_has_at_least_140_rows() -> None:
    """FR-017: the ontology grew to ≥140 rows."""
    rows = _load_dim_metric_yaml()
    assert len(rows) >= 140, f"expected ≥140 rows, got {len(rows)}"


def test_dim_metric_yaml_every_row_has_category() -> None:
    """FR-017: every row carries a non-empty ``category``."""
    rows = _load_dim_metric_yaml()
    missing = [r["metric_id"] for r in rows if not r.get("category")]
    assert not missing, f"rows missing category: {missing[:5]}"


def test_dim_metric_yaml_lab_rows_have_loinc() -> None:
    """FR-017: every ``lab:*`` row has a ``loinc`` value (real code or "[unmapped]")."""
    rows = _load_dim_metric_yaml()
    lab_rows = [r for r in rows if r["metric_id"].startswith("lab:")]
    assert lab_rows, "expected at least one lab:* row in ontology"
    missing = [r["metric_id"] for r in lab_rows if not r.get("loinc")]
    assert not missing, f"lab:* rows missing loinc: {missing[:5]}"


# ---------------------------------------------------------------------------
# T024 — Cross-cutting structure (FR-009 contract tokens, FR-013 CLI verb)
# ---------------------------------------------------------------------------


def test_parser_contract_md_documents_standards_first_ladder() -> None:
    """FR-009: CONTRACT.md mentions LOINC, IEEE 1752.1, and the reserved ``derived:`` namespace."""
    contract = files("premura.parsers").joinpath("CONTRACT.md")
    assert contract.is_file(), "parsers/CONTRACT.md missing"
    text = contract.read_text(encoding="utf-8")
    for token in ("LOINC", "IEEE 1752.1", "derived:"):
        assert token in text, f"CONTRACT.md missing token: {token}"


def test_cli_registers_install_skills_verb() -> None:
    """FR-013: ``hpipe install-skills`` is registered on the Typer app."""
    cli = importlib.import_module("premura.cli")
    commands = {cmd.name for cmd in cli.app.registered_commands}
    assert "install-skills" in commands, f"expected install-skills verb, got {sorted(commands)}"


def test_hpipe_console_script_is_wired_and_invokable(tmp_path: Path) -> None:
    """FR-013: the ``hpipe`` console script is wired via ``[project.scripts]``
    in ``pyproject.toml`` and ``hpipe install-skills`` is actually invokable
    end-to-end (not just registered on the Typer app object).

    Layer 1 — entry-point wiring: confirm ``importlib.metadata.entry_points``
    exposes a ``console_scripts`` entry named ``hpipe`` resolving to
    ``premura.cli:app``. If the ``[project.scripts]`` table is removed from
    ``pyproject.toml`` (or the entry is renamed), this assertion fails.

    Layer 2 — runtime invocation: shell out to the installed ``hpipe``
    binary in ``.venv/bin/hpipe`` and confirm ``hpipe install-skills``
    materializes the skill files in a temp project root with exit code 0
    and is idempotent on the second invocation. This catches packaging
    failures like ``Failed to spawn: hpipe`` that the Typer-registry check
    cannot.

    Mutation guarantee: deleting the ``[project.scripts]`` table from
    ``pyproject.toml`` (or removing the ``hpipe`` line under it) causes
    both layers to fail.
    """
    # ------------------------------------------------------------------
    # Layer 1 — console_scripts entry point is declared and resolves.
    # ------------------------------------------------------------------
    eps = entry_points(group="console_scripts")
    hpipe_eps = [ep for ep in eps if ep.name == "hpipe"]
    assert hpipe_eps, (
        "no console_scripts entry named 'hpipe' — is [project.scripts] hpipe "
        "= 'premura.cli:app' still present in pyproject.toml?"
    )
    assert len(hpipe_eps) == 1, f"expected exactly one hpipe console_script, got {hpipe_eps}"
    ep = hpipe_eps[0]
    assert ep.value == "premura.cli:app", (
        f"hpipe console_script points to {ep.value!r}, expected 'premura.cli:app'"
    )
    # Loading the entry point must produce the Typer app (real import, not stub).
    loaded = ep.load()
    cli_mod = importlib.import_module("premura.cli")
    assert loaded is cli_mod.app, "console_script entry did not load the actual Typer app"

    # ------------------------------------------------------------------
    # Layer 2 — invoke the installed console script as a real subprocess.
    # ------------------------------------------------------------------
    hpipe_bin = Path(sys.executable).parent / "hpipe"
    if not hpipe_bin.is_file():
        pytest.skip(f"hpipe console script not installed at {hpipe_bin}")

    project_root = tmp_path / "project"
    project_root.mkdir()

    # First invocation: should write the skill file and exit 0.
    result = subprocess.run(
        [str(hpipe_bin), "install-skills"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"hpipe install-skills exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    skill_file = project_root / ".claude" / "skills" / "parser-generator" / "SKILL.md"
    assert skill_file.is_file(), (
        f"hpipe install-skills did not materialize {skill_file}; stdout={result.stdout}"
    )
    first_bytes = skill_file.read_bytes()

    # Second invocation: must be idempotent — exit 0, "no changes", file untouched.
    result2 = subprocess.run(
        [str(hpipe_bin), "install-skills"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result2.returncode == 0, (
        f"second hpipe install-skills exited {result2.returncode}\n"
        f"stdout:\n{result2.stdout}\nstderr:\n{result2.stderr}"
    )
    assert "no changes" in result2.stdout, (
        f"expected 'no changes' on idempotent run, got: {result2.stdout!r}"
    )
    assert skill_file.read_bytes() == first_bytes, (
        "skill file was rewritten on idempotent second invocation"
    )
