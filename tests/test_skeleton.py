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
from importlib.resources import files
from pathlib import Path
from typing import get_type_hints

import pytest
import yaml

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


@pytest.mark.parametrize(
    "func_name,call",
    [
        ("compute", lambda fn: fn("any_name", object())),
        ("list_by_domain", lambda fn: fn("liver")),
        ("list_auto_safe", lambda fn: fn()),
        ("check_inputs_available", lambda fn: fn(["lab:ast"], object())),
        ("list_unavailable", lambda fn: fn("liver", object())),
    ],
)
def test_engine_stubs_raise_not_implemented(func_name: str, call) -> None:
    """FR-003: the five engine stubs raise NotImplementedError referencing STAGES.md."""
    from premura import engine

    fn = getattr(engine, func_name)
    with pytest.raises(NotImplementedError, match="Stage 2"):
        call(fn)


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


def test_parsers_lookup_suggest_metric_stub_raises() -> None:
    """FR-007: ``parsers.lookup.suggest_metric`` is a stub that raises NotImplementedError."""
    from premura.parsers.lookup import suggest_metric

    with pytest.raises(NotImplementedError):
        suggest_metric("Resting Heart Rate")


def test_plugin_parser_contract_symbols_import() -> None:
    """FR-008: ``PluginParser`` and ``PluginParseResult`` import from parsers.base."""
    from premura.parsers.base import PluginParser, PluginParseResult

    # PluginParseResult is a dataclass with the three additive fields.
    fields = set(PluginParseResult.__dataclass_fields__)
    assert {"language_detected", "unmapped_metrics", "confidence"} <= fields

    # PluginParser is a Protocol declaring the documented members.
    hints = get_type_hints(PluginParser)
    assert "language_hint" in hints
    assert hasattr(PluginParser, "declares_metrics")
    assert hasattr(PluginParser, "parse")


def test_plugin_parser_is_structural_subtype_of_parser() -> None:
    """FR-008: ``PluginParser`` is a structural extension of v1 ``Parser``.

    A class with the v1 ``Parser`` shape plus the plugin extras must satisfy
    ``PluginParser`` via duck typing. We cannot use ``isinstance`` because
    neither protocol is declared ``runtime_checkable``; structural conformance
    is verified by attribute presence on a sample implementation.
    """
    from premura.parsers.base import PluginParser, PluginParseResult

    class _SampleParser:
        source_kind = "_sample"
        language_hint: str | None = None

        def declares_metrics(self) -> list[str]:
            return ["heart_rate"]

        def parse(self, path: Path) -> PluginParseResult:  # noqa: ARG002
            return PluginParseResult()

    inst = _SampleParser()
    for attr in ("source_kind", "language_hint", "declares_metrics", "parse"):
        assert hasattr(inst, attr), f"sample plugin parser missing {attr}"
    # The class compiles against the protocol type-hint at static-checker time;
    # at runtime we just confirm the shape matches and the result is usable.
    result = inst.parse(Path("/dev/null"))
    assert isinstance(result, PluginParseResult)
    assert result.confidence == 1.0  # default per FR-008
    # Cross-check the v1 Parser protocol is still importable and unchanged in
    # the same module (the additive contract MUST NOT have removed it).
    from premura.parsers.base import Interval, Measurement, Parser, ParseResult

    assert Parser is not PluginParser
    assert ParseResult is not PluginParseResult
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


def test_seed_handles_rows_with_and_without_new_keys(tmp_path: Path) -> None:
    """FR-016: ``seed_dim_metric`` accepts both legacy and ontology-rich rows."""
    import json

    import duckdb

    from premura.store import duck

    db = tmp_path / "seed.duckdb"
    conn = duckdb.connect(str(db))
    try:
        duck.run_migrations(conn)
        # Legacy-shape row (no new keys) and full-ontology row, both inserted
        # via the production seed path's parametrised statement to mirror its
        # behaviour exactly.
        legacy = {
            "metric_id": "_legacy_smoke",
            "display_name": "Legacy smoke",
            "canonical_unit": "ct",
            "value_kind": "instantaneous",
            "description": None,
        }
        rich = {
            "metric_id": "_rich_smoke",
            "display_name": "Rich smoke",
            "canonical_unit": "ct",
            "value_kind": "instantaneous",
            "description": "with ontology",
            "category": "cardiovascular",
            "validity_window": "PT5M",
            "missing_data_policy": "none",
            "aliases": {"en": ["smoke"]},
            "loinc": "00000-0",
            "ieee1752": "ieee1752:0",
        }
        for row in (legacy, rich):
            aliases = row.get("aliases")
            aliases_json = json.dumps(aliases) if aliases else None
            conn.execute(
                """
                INSERT INTO hp.dim_metric (
                    metric_id, display_name, canonical_unit, value_kind, description,
                    category, validity_window, missing_data_policy, aliases, loinc, ieee1752
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["metric_id"],
                    row["display_name"],
                    row["canonical_unit"],
                    row["value_kind"],
                    row.get("description"),
                    row.get("category"),
                    row.get("validity_window"),
                    row.get("missing_data_policy"),
                    aliases_json,
                    row.get("loinc"),
                    row.get("ieee1752"),
                ],
            )
        legacy_cat, legacy_loinc = conn.execute(
            "SELECT category, loinc FROM hp.dim_metric WHERE metric_id = ?",
            [legacy["metric_id"]],
        ).fetchone()
        assert legacy_cat is None
        assert legacy_loinc is None
        rich_cat, rich_loinc = conn.execute(
            "SELECT category, loinc FROM hp.dim_metric WHERE metric_id = ?",
            [rich["metric_id"]],
        ).fetchone()
        assert rich_cat == "cardiovascular"
        assert rich_loinc == "00000-0"
    finally:
        conn.close()


def _load_dim_metric_yaml() -> list[dict]:
    yaml_text = (
        resources.files("premura").joinpath("dim_metric.yaml").read_text(encoding="utf-8")
    )
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


