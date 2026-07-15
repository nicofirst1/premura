"""WP3 — rubric/playbook extension proof for the analyze-and-answer slice (FR-6).

FR-6 requires extending the judge rubric with analytical-honesty coverage and the
improvement playbook with the matching area *by their own add rules*, such that it
needs **no engine, judge, or scan code edits**. These tests are that proof: the
existing rubric/playbook parsers (``judge.load_rubric`` / ``improvement.load_playbook``)
accept the extended documents unchanged, the new criterion is parsed, its category is
one of the four closed categories, and it maps to an existing playbook area — so no
new code and no schema change is required.
"""

from __future__ import annotations

from premura.harness.improvement import load_playbook
from premura.harness.judge import load_rubric

# The analyze-and-answer rubric criterion added under an EXISTING closed category.
_ANALYTICAL_CRITERION = "analytical-claims-match-engine"


def test_rubric_parses_and_carries_the_analytical_criterion() -> None:
    rubric = load_rubric()
    assert _ANALYTICAL_CRITERION in rubric.criterion_ids


def test_analytical_criterion_uses_a_closed_category() -> None:
    rubric = load_rubric()
    category = rubric.category_of(_ANALYTICAL_CRITERION)
    # The four closed rubric categories (a new one would need a spec amendment).
    assert category in {
        "process_honesty",
        "goal_adherence",
        "tool_use_economy",
        "failure_recovery",
    }


def test_analytical_criterion_category_already_has_a_playbook_area() -> None:
    # FR-6's no-code-edit proof: because the criterion uses a category that already
    # has an area, adding it requires NO playbook area edit and NO code change — the
    # store records whatever criterion id / area id the documents define.
    rubric = load_rubric()
    playbook = load_playbook()
    category = rubric.category_of(_ANALYTICAL_CRITERION)
    assert category is not None
    assert playbook.area_for_category(category) is not None


def test_playbook_still_loads_with_required_areas() -> None:
    # The playbook parser enforces the required area set; this proves the extended
    # document still satisfies it (no area dropped, version bumped, parser unchanged).
    playbook = load_playbook()
    assert playbook.version  # a parseable version header survived the edit
    for required in (
        "process_honesty",
        "goal_adherence",
        "tool_use_economy",
        "failure_recovery",
        playbook.harness_reliability_area,
        playbook.rubric_drift_area,
    ):
        assert required in playbook.areas
