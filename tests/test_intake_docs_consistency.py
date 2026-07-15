"""Doc<->code consistency guards for WP06 (T030).

These tests do not freeze prose. They assert only that the load-bearing
**symbols and registration points** the WP06 docs name actually exist in code,
so the parser-generator skill and the add-a-dimension rule cannot silently drift
into describing an API that WP01/WP03/WP04/WP05 did not ship. A mismatch here is
the exact drift dimension this mission guards against.

The docs themselves live at:
* ``src/premura/skills/parser-generator/SKILL.md`` (FR-007 skill half / SC-004)
* ``docs/building/architecture/INTAKE_DIMENSIONS.md`` (FR-009 / SC-005)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import premura.engine as engine
import premura.parsers.base as parser_base
from premura.engine._resolution import SEMANTIC_DOMAINS

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "src" / "premura" / "skills" / "parser-generator" / "SKILL.md"
RULE = REPO_ROOT / "docs" / "building" / "architecture" / "INTAKE_DIMENSIONS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# T027 / FR-007 — the skill must describe the WP01 protocol as implemented.
# --------------------------------------------------------------------------- #


def test_skill_names_only_real_wp01_protocol_symbols() -> None:
    """Every parser-protocol symbol the skill quotes must exist in base.py."""
    text = _read(SKILL)
    # The intake parser path the skill documents.
    for symbol in (
        "ParseOutput",
        "ParserOutput",
        "IntakeBatch",
        "IngestBatch",
        "normalize_parse_output",
        "NutritionIntakeInput",
        "NutritionItemInput",
        "NutritionQuantityInput",
        "SupplementIntakeInput",
        "SupplementItemInput",
        "SupplementDoseInput",
        "SourceDescriptor",
        "SkippedRow",
    ):
        assert symbol in text, f"SKILL.md should reference {symbol}"
        assert hasattr(parser_base, symbol), f"{symbol} missing from parsers.base"


def test_skill_persist_path_matches_code() -> None:
    """The skill's named runtime load path must be the real one."""
    text = _read(SKILL)
    assert "premura.store.profile_intake.persist_intake_batch" in text
    profile_intake = importlib.import_module("premura.store.profile_intake")
    assert hasattr(profile_intake, "persist_intake_batch")


def test_skill_documents_build_and_use_boundary() -> None:
    """FR-007: runtime build-and-use with no review; review only on contribute-back."""
    text = _read(SKILL).lower()
    assert "build-and-use" in text
    assert "no review" in text
    # The boundary is that review gates only a contributed-back PR.
    assert "contribute back" in text or "contribute it back" in text or "contributed back" in text


def test_parse_returns_documented_union() -> None:
    """A bare IngestBatch and a ParseOutput both normalize, as the skill claims."""
    obs, intake = parser_base.normalize_parse_output(
        parser_base.IngestBatch(source_kind="x", declared_metrics=["m"])
    )
    assert intake is None and obs is not None
    out = parser_base.ParseOutput(intake=parser_base.IntakeBatch())
    obs2, intake2 = parser_base.normalize_parse_output(out)
    assert obs2 is None and intake2 is not None


# --------------------------------------------------------------------------- #
# T028 / FR-009 / SC-005 — the rule's four steps must match the real seams.
# --------------------------------------------------------------------------- #


def test_rule_step1_domains_are_declared() -> None:
    """Step 1: both shipped intake domains are members of SEMANTIC_DOMAINS."""
    text = _read(RULE)
    assert "SEMANTIC_DOMAINS" in text
    assert "nutrition_intake" in SEMANTIC_DOMAINS
    assert "supplement_intake" in SEMANTIC_DOMAINS


def test_rule_step2_resolver_modules_registered() -> None:
    """Step 2: both resolver modules are in _BUILTIN_RESOLVER_MODULES and register."""
    text = _read(RULE)
    assert "_BUILTIN_RESOLVER_MODULES" in text
    assert "engine/views/nutrition_intake.py" in text
    assert "engine/views/supplement_intake.py" in text
    assert "premura.engine.views.nutrition_intake" in engine._BUILTIN_RESOLVER_MODULES
    assert "premura.engine.views.supplement_intake" in engine._BUILTIN_RESOLVER_MODULES
    # The decorator the rule names must register both domains.
    engine._ensure_builtin_resolvers_loaded()
    assert "nutrition_intake" in engine.RESOLVERS
    assert "supplement_intake" in engine.RESOLVERS


def test_rule_step3_signals_registered() -> None:
    """Step 3: both intake signals are in REGISTRY via an already-listed module."""
    text = _read(RULE)
    assert "nutrition_intake_trend" in text
    assert "supplement_intake_adherence" in text
    engine._ensure_builtin_signals_loaded()
    assert "nutrition_intake_trend" in engine.REGISTRY
    assert "supplement_intake_adherence" in engine.REGISTRY


def test_rule_step4_default_surface_tools_exist() -> None:
    """Step 4: both thin tool wrappers exist on the MCP server surface."""
    text = _read(RULE)
    server = importlib.import_module("premura.mcp.server")
    for tool in ("supplement_intake_adherence", "nutrition_intake_trend"):
        assert tool in text
        assert hasattr(server, tool), f"{tool} missing from mcp.server"


def test_rule_pins_matcher_to_authoritative_symbol() -> None:
    """The matcher semantics the rule states must point at the real function."""
    text = _read(RULE)
    assert "matches_supplement" in text
    sup = importlib.import_module("premura.engine.views.supplement_intake")
    assert hasattr(sup, "matches_supplement")
    # Spot-check the pinned semantics the doc describes are the real behavior:
    # case-insensitive substring, product-then-ingredient, AND tokens.
    assert sup.matches_supplement("vitamin d3", "Vitamin D3 5000IU", None)
    assert sup.matches_supplement("d3", None, "cholecalciferol d3")
    assert not sup.matches_supplement("vitamin zinc", "Vitamin D3", None)


def test_rule_cites_nfr005_structural_proof() -> None:
    """SC-005: the rule cites the real 'no shared-seam branch' test, which exists."""
    text = _read(RULE)
    assert "test_shared_seam_has_no_per_domain_branch" in text
    nfr = REPO_ROOT / "tests" / "test_intake_resolvers.py"
    assert "def test_shared_seam_has_no_per_domain_branch" in _read(nfr)
