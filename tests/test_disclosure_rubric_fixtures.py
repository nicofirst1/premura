"""Phase 5 slice 4: lightweight deterministic guard for the disclosure-rubric
fixtures.

The rubric's add-rule demands every admitted criterion ship a *verdict-changing*
fixture pair: a fail narration and a pass narration over the **same** structured
tool output, whose criterion verdict flips between them. These fixtures are a
product-skill resource (mirroring ``research-trace-audit/fixtures/``), read by
the ``human-facing-teaching`` agent skill. This guard is a plain assert test — it
is **not** the issue #12 acceptance harness (no tool-loop / judge / grader /
fixture-gen rig runs here; ADR 0012 freeze).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "src" / "premura" / "skills" / "human-facing-teaching" / "fixtures"
DOCS_RUBRIC = REPO_ROOT / "docs" / "building" / "architecture" / "DISCLOSURE_RUBRIC.md"

# The three exercisable criteria this slice admits (teach-back-confirmation stays
# deferred to #12 — no deterministic fixture can flip it).
EXPECTED_CRITERIA = {
    "denominator-preserved-gist": "gist_fidelity",
    "progressive-sequencing": "load_management",
    "simplification-stays-descriptive": "boundary_integrity",
}
STRUCTURED_OUTPUT_FIELDS = {
    "effect",
    "n",
    "p",
    "ci",
    "is_imputed_pct",
    "validity_status",
}


def _load_fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURE_DIR.glob("*.json"))]


def _group_by_criterion(fixtures: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for fx in fixtures:
        groups.setdefault(fx["criterion_id"], []).append(fx)
    return groups


def _verdict_changes(pair: list[dict]) -> bool:
    """The guard: a fixture pair is verdict-changing iff it is exactly one pass
    and one fail, narrated differently, over byte-identical structured output.

    A criterion whose fixtures do not satisfy this is aspirational, not admitted.
    """
    if len(pair) != 2:
        return False
    if {fx["verdict"] for fx in pair} != {"pass", "fail"}:
        return False
    outputs = {json.dumps(fx["structured_output"], sort_keys=True) for fx in pair}
    if len(outputs) != 1:  # verdict must flip over the SAME evidence
        return False
    return pair[0]["narration"] != pair[1]["narration"]


def test_each_criterion_has_a_verdict_changing_pair() -> None:
    """Every admitted criterion ships a fail-fixture and a pass-fixture over the
    same structured output; the guard confirms the verdict flips between them."""
    groups = _group_by_criterion(_load_fixtures())
    for criterion_id in EXPECTED_CRITERIA:
        assert criterion_id in groups, f"no fixtures for admitted criterion {criterion_id}"
        assert _verdict_changes(groups[criterion_id]), (
            f"{criterion_id} lacks a verdict-changing fixture pair (add-rule 4)"
        )


def test_every_fixture_group_is_verdict_changing() -> None:
    """No fixture criterion may be aspirational: every criterion_id present in the
    fixtures directory must carry a flipping pair, so a new criterion cannot be
    admitted without exercising it."""
    for criterion_id, pair in _group_by_criterion(_load_fixtures()).items():
        assert _verdict_changes(pair), f"{criterion_id} fixtures do not change a verdict"


def test_fixtures_are_grounded_in_the_rubric() -> None:
    """Each fixture's (criterion_id, dimension) is a real rubric heading — the
    fixtures cannot drift from the criteria they exercise."""
    rubric = DOCS_RUBRIC.read_text(encoding="utf-8")
    for fx in _load_fixtures():
        heading = f"### `{fx['criterion_id']}` — `{fx['dimension']}`"
        assert heading in rubric, f"fixture criterion not declared in rubric: {heading}"


def test_structured_output_shape_and_no_phi() -> None:
    """Every fixture narrates the locked structured-output shape and declares
    itself synthetic — the deterministic PHI rail for this resource."""
    for fx in _load_fixtures():
        assert set(fx["structured_output"]) == STRUCTURED_OUTPUT_FIELDS, (
            f"fixture structured_output must carry exactly {STRUCTURED_OUTPUT_FIELDS}"
        )
        note = fx.get("_note", "")
        assert "Synthetic" in note and "No PHI" in note, (
            "fixture must declare itself synthetic with no PHI in its _note"
        )


def test_guard_bites_on_a_non_flipping_pair() -> None:
    """Meta-test: the guard rejects a criterion authored without a verdict-changing
    fixture — two fails over the same output do not flip, so the guard returns
    False (proving it bites, not merely passes)."""
    fail = {
        "verdict": "fail",
        "narration": "narration a",
        "structured_output": {k: 1 for k in STRUCTURED_OUTPUT_FIELDS},
    }
    same_verdict_pair = [fail, {**fail, "narration": "narration b"}]
    assert not _verdict_changes(same_verdict_pair), "guard failed to reject a non-flipping pair"

    # It also rejects a pass/fail pair whose evidence differs (verdict could be
    # explained by the changed output, not the narration).
    passing = {**fail, "verdict": "pass", "narration": "narration b"}
    passing["structured_output"] = {k: 2 for k in STRUCTURED_OUTPUT_FIELDS}
    assert not _verdict_changes([fail, passing]), "guard failed to reject a shifted-evidence pair"

    # And it accepts a genuine flip over identical evidence.
    good_pass = {**fail, "verdict": "pass", "narration": "narration b"}
    assert _verdict_changes([fail, good_pass]), "guard rejected a genuine verdict-changing pair"
