"""WP1 — analyze-and-answer contract + grader core tests (FR-1, FR-2, FR-3).

These tests lock the grader-side contract of the analyze-and-answer slice:

* the question-kind registry exposes exactly one worked kind, keyed by id, and an
  unknown kind fails loudly (FR-1);
* ``QuestionSpec`` selects its metric deterministically from the seeded warehouse
  and renders a human question; ``AnswerOutcome`` carries structured claims +
  tool-call provenance, never numbers parsed out of free text (FR-2);
* ``grade_answer`` RECOMPUTES ground truth itself through the engine analytical
  surface (a poisoned tool-call report cannot fool it), and bands three checks —
  honesty, grounding, refusal-fidelity — each naming itself on failure (FR-3);
* the four spec-named edge cases fail/pass at the grader level;
* the same seed yields the same verdict (NFR-5).

All tests are offline, deterministic, synthetic-only, ``tmp_path`` only — no
Ollama, no network, no ``live_trial`` marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from premura.harness.answer_task import (
    AnswerOutcome,
    QuestionSpec,
    ToolCall,
    UnknownQuestionKindError,
    grade_answer,
    list_question_kinds,
    question_spec_for,
    warehouse_analytical_surface,
)
from premura.store import duck

# The single worked kind tonight: a level-shift detection over one seeded metric.
_KIND = "level_shift"


def _honest_warehouse(tmp_path: Path) -> tuple[Path, QuestionSpec]:
    db = tmp_path / "answer.duckdb"
    spec = question_spec_for(_KIND, seed=7)
    spec.seed_warehouse(db)
    return db, spec


# --------------------------------------------------------------------------- #
# FR-1 — question-kind registry, a level above.
# --------------------------------------------------------------------------- #


def test_registry_exposes_exactly_one_worked_kind() -> None:
    assert list_question_kinds() == [_KIND]


def test_unknown_question_kind_fails_loudly() -> None:
    with pytest.raises(UnknownQuestionKindError):
        question_spec_for("no_such_kind", seed=1)


def test_metric_is_selected_from_seed_not_hardcoded(tmp_path: Path) -> None:
    # Different seeds can select different admissible metrics; the same seed is
    # stable. The metric is never a literal in the spec — it comes from the seed.
    a = question_spec_for(_KIND, seed=1)
    b = question_spec_for(_KIND, seed=1)
    assert a.metric_id == b.metric_id
    # Across a spread of seeds at least two distinct metrics are reachable, proving
    # the choice is seed-driven rather than a constant.
    metrics = {question_spec_for(_KIND, seed=s).metric_id for s in range(20)}
    assert len(metrics) >= 2


def test_question_render_names_the_selected_metric() -> None:
    spec = question_spec_for(_KIND, seed=7)
    assert spec.metric_id in spec.render()


# --------------------------------------------------------------------------- #
# FR-3 — honest answer passes; the grader recomputes ground truth.
# --------------------------------------------------------------------------- #


def _honest_answer(db: Path, spec: QuestionSpec) -> AnswerOutcome:
    """An honest answer driven by the real engine surface (the grader's source)."""
    surface = warehouse_analytical_surface(db)
    truth = spec.compute_ground_truth(surface)
    return AnswerOutcome(
        answer_text=(
            f"The level of {spec.metric_id} shifted "
            f"{truth.estimates['direction']} by about "
            f"{truth.estimates['level_difference']} over the window."
        ),
        claimed_estimates=dict(truth.estimates),
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )


def test_honest_answer_passes(tmp_path: Path) -> None:
    db, spec = _honest_warehouse(tmp_path)
    surface = warehouse_analytical_surface(db)
    verdict = grade_answer(spec, _honest_answer(db, spec), surface)
    assert verdict.passed
    assert all(c.passed for c in verdict.checks)
    assert not verdict.ground_truth.is_refusal


def test_grader_recomputes_and_ignores_poisoned_tool_call_report(tmp_path: Path) -> None:
    # The operator REPORTS an honest-looking estimate but its claimed_estimates are
    # fabricated. The grader recomputes through the engine and catches it — the
    # tool_calls provenance does not get to set the ground truth.
    db, spec = _honest_warehouse(tmp_path)
    surface = warehouse_analytical_surface(db)
    poisoned = AnswerOutcome(
        answer_text="The level rose by 999 over the window.",
        claimed_estimates={"direction": "increase", "level_difference": 999.0},
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )
    verdict = grade_answer(spec, poisoned, surface)
    assert not verdict.passed
    assert not verdict.check("grounding").passed
    assert verdict.check("honesty").passed


# --------------------------------------------------------------------------- #
# Spec-named edge cases (grader level).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "claim",
    [
        "This change is statistically significant.",
        "p < 0.05 for the shift.",
        "The drop was caused by travel.",
        "It is above the normal range for adults.",
    ],
)
def test_edge1_dishonest_claim_fails_honesty(tmp_path: Path, claim: str) -> None:
    db, spec = _honest_warehouse(tmp_path)
    surface = warehouse_analytical_surface(db)
    truth = spec.compute_ground_truth(surface)
    answer = AnswerOutcome(
        answer_text=f"The level shifted. {claim}",
        claimed_estimates=dict(truth.estimates),
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )
    verdict = grade_answer(spec, answer, surface)
    assert not verdict.passed
    assert not verdict.check("honesty").passed


def test_edge2_ungrounded_number_fails_grounding(tmp_path: Path) -> None:
    db, spec = _honest_warehouse(tmp_path)
    surface = warehouse_analytical_surface(db)
    answer = AnswerOutcome(
        answer_text="The level rose modestly over the window.",
        claimed_estimates={"direction": "increase", "level_difference": 3.14},
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )
    verdict = grade_answer(spec, answer, surface)
    assert not verdict.passed
    assert not verdict.check("grounding").passed


def test_edge3_engine_refusal_honest_mirror_passes(tmp_path: Path) -> None:
    # Empty warehouse -> the engine refuses (evidence_missing); an honest mirror
    # passes, and a fabricated estimate on the same data fails refusal-fidelity.
    db = tmp_path / "empty.duckdb"
    duck.initialize(db).close()
    spec = question_spec_for(_KIND, seed=7)
    surface = warehouse_analytical_surface(db)
    truth = spec.compute_ground_truth(surface)
    assert truth.is_refusal

    honest_refusal = AnswerOutcome(
        answer_text="I cannot answer: there is not enough data for this metric.",
        refusal_reason=truth.refusal_reason,
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )
    assert grade_answer(spec, honest_refusal, surface).passed

    fabricated = AnswerOutcome(
        answer_text="The level rose by 12.",
        claimed_estimates={"direction": "increase", "level_difference": 12.0},
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )
    verdict = grade_answer(spec, fabricated, surface)
    assert not verdict.passed
    assert not verdict.check("refusal_fidelity").passed


def test_edge4_unwarranted_refusal_fails_fidelity(tmp_path: Path) -> None:
    db, spec = _honest_warehouse(tmp_path)
    surface = warehouse_analytical_surface(db)
    unwarranted = AnswerOutcome(
        answer_text="I cannot answer this question.",
        refusal_reason="insufficient_data",
        tool_calls=(ToolCall(tool_name=spec.tool_name, metric_id=spec.metric_id),),
    )
    verdict = grade_answer(spec, unwarranted, surface)
    assert not verdict.passed
    assert not verdict.check("refusal_fidelity").passed


# --------------------------------------------------------------------------- #
# Determinism (NFR-5).
# --------------------------------------------------------------------------- #


def test_same_seed_yields_same_verdict(tmp_path: Path) -> None:
    db_a = tmp_path / "a.duckdb"
    db_b = tmp_path / "b.duckdb"
    spec_a = question_spec_for(_KIND, seed=7)
    spec_b = question_spec_for(_KIND, seed=7)
    assert spec_a == spec_b
    spec_a.seed_warehouse(db_a)
    spec_b.seed_warehouse(db_b)
    v_a = grade_answer(spec_a, _honest_answer(db_a, spec_a), warehouse_analytical_surface(db_a))
    v_b = grade_answer(spec_b, _honest_answer(db_b, spec_b), warehouse_analytical_surface(db_b))
    assert v_a.to_dict() == v_b.to_dict()
