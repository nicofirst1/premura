"""WP2 — analyze-and-answer seam + capture tests (FR-4, FR-5).

End-to-end over ``run_answer_trial``:

* the honest scripted operator answers through the bounded engine surface and the
  trial passes; the seeded warehouse is synthetic by construction;
* all four spec-named edge cases fail/pass through the seam;
* the session log holds the exchange (the dossier shows the question + answer);
* the result persists to the scoreboard under the open tier axis with an
  analyze-task tier value, marked synthetic;
* the operator never receives a connection / path / raw SQL — only the bounded
  surface;
* the sole-writer invariant holds (the dossier read surface is read-only).

Offline, deterministic, synthetic-only, ``tmp_path`` only — no Ollama, no network,
no ``live_trial`` marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from premura.harness.answer_task import (
    AnalyticalSurface,
    AnswerOutcome,
    QuestionSpec,
    ToolCall,
)
from premura.harness.answer_trial import (
    DishonestAnswerOperator,
    HonestAnswerOperator,
    run_answer_trial,
)
from premura.harness.scoreboard import read_scoreboard
from premura.session_log.dossier import build_dossier
from premura.session_log.store import connect

_KIND = "level_shift"
_TIER = "analyze_answer"


def _run(tmp_path: Path, operator, *, seed: int = 7):
    return run_answer_trial(
        seed=seed,
        question_kind=_KIND,
        operator=operator,
        warehouse_path=tmp_path / "warehouse.duckdb",
        session_log_path=tmp_path / "session_log.duckdb",
        scoreboard_path=tmp_path / "scoreboard.jsonl",
    )


# --------------------------------------------------------------------------- #
# FR-4 — honest pass end to end.
# --------------------------------------------------------------------------- #


def test_honest_operator_passes_end_to_end(tmp_path: Path) -> None:
    result = _run(tmp_path, HonestAnswerOperator())
    assert result.verdict.passed
    assert result.is_synthetic
    assert result.spec.kind == _KIND


def test_operator_receives_only_bounded_surface(tmp_path: Path) -> None:
    """The operator's ``answer`` is handed the spec + the bounded surface — never a
    connection, a path, or raw SQL. A recording operator proves the surface is a
    plain callable that returns serialized envelopes only."""

    seen: dict[str, object] = {}

    class _SpyOperator:
        model_id = "spy"

        def answer(self, spec: QuestionSpec, surface: AnalyticalSurface) -> AnswerOutcome:
            seen["surface_is_callable"] = callable(surface)
            payload = surface(spec.tool_name, spec.metric_id, **spec.parameters)
            seen["payload_keys"] = sorted(payload)
            # The surface exposes no path/connection attribute to reach the warehouse.
            seen["has_path_attr"] = hasattr(surface, "warehouse_path")
            truth = spec.compute_ground_truth(surface)
            return AnswerOutcome(
                answer_text="ok",
                claimed_estimates=dict(truth.estimates),
                tool_calls=(ToolCall(spec.tool_name, spec.metric_id),),
            )

    _run(tmp_path, _SpyOperator())
    assert seen["surface_is_callable"] is True
    assert seen["has_path_attr"] is False
    assert seen["payload_keys"] == ["message", "result", "status", "tool_name"]


# --------------------------------------------------------------------------- #
# FR-5 — session-log capture + scoreboard persistence.
# --------------------------------------------------------------------------- #


def test_session_log_holds_the_exchange(tmp_path: Path) -> None:
    result = _run(tmp_path, HonestAnswerOperator())
    dossier = build_dossier(result.session_log_path, session_id=result.session_id)
    assert dossier.has_transcript
    roles = [t.role for t in dossier.transcript]
    assert "user" in roles  # the rendered question
    assert "assistant" in roles  # the operator's answer
    # The question text names the analyzed metric.
    question = next(t for t in dossier.transcript if t.role == "user")
    assert result.spec.metric_id in question.content


def test_scoreboard_entry_under_open_tier_axis(tmp_path: Path) -> None:
    result = _run(tmp_path, HonestAnswerOperator())
    entries = read_scoreboard(path=tmp_path / "scoreboard.jsonl")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.tier == _TIER
    assert entry.final_pass is result.verdict.passed is True
    assert entry.operator_model == HonestAnswerOperator().model_id


def test_dossier_read_is_read_only_sole_writer(tmp_path: Path) -> None:
    # Reading the dossier must not need a writable handle; the harness stays the
    # sole writer. After the trial, a read-only connection opens the log fine.
    result = _run(tmp_path, HonestAnswerOperator())
    conn = connect(result.session_log_path, read_only=True)
    try:
        rows = conn.execute("SELECT count(*) FROM log_turn").fetchone()
    finally:
        conn.close()
    assert rows is not None and rows[0] >= 2


# --------------------------------------------------------------------------- #
# Spec-named edge cases through the seam.
# --------------------------------------------------------------------------- #


def test_edge1_dishonest_forbidden_claim_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, DishonestAnswerOperator(mode="forbidden_claim"))
    assert not result.verdict.passed
    assert not result.verdict.check("honesty").passed


def test_edge2_ungrounded_number_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, DishonestAnswerOperator(mode="ungrounded"))
    assert not result.verdict.passed
    assert not result.verdict.check("grounding").passed


def test_edge3_engine_refusal_honest_mirror_passes(tmp_path: Path) -> None:
    # An empty seed warehouse makes the engine refuse; the honest operator mirrors
    # it and the trial passes.
    result = run_answer_trial(
        seed=7,
        question_kind=_KIND,
        operator=HonestAnswerOperator(),
        warehouse_path=tmp_path / "w.duckdb",
        session_log_path=tmp_path / "s.duckdb",
        scoreboard_path=tmp_path / "sb.jsonl",
        seed_empty_warehouse=True,
    )
    assert result.verdict.passed
    assert result.verdict.ground_truth.is_refusal

    # A fabricated estimate over the same refusing data fails refusal-fidelity.
    bad = run_answer_trial(
        seed=7,
        question_kind=_KIND,
        operator=DishonestAnswerOperator(mode="ungrounded"),
        warehouse_path=tmp_path / "w2.duckdb",
        session_log_path=tmp_path / "s2.duckdb",
        scoreboard_path=tmp_path / "sb2.jsonl",
        seed_empty_warehouse=True,
    )
    assert not bad.verdict.passed
    assert not bad.verdict.check("refusal_fidelity").passed


def test_edge4_unwarranted_refusal_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, DishonestAnswerOperator(mode="unwarranted_refusal"))
    assert not result.verdict.passed
    assert not result.verdict.check("refusal_fidelity").passed


# --------------------------------------------------------------------------- #
# Determinism.
# --------------------------------------------------------------------------- #


def test_same_seed_same_verdict(tmp_path: Path) -> None:
    a = _run(tmp_path / "a", HonestAnswerOperator())
    b = _run(tmp_path / "b", HonestAnswerOperator())
    assert a.verdict.to_dict() == b.verdict.to_dict()
    assert a.spec == b.spec


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path: Path) -> None:
    # Each subdir used as a tmp root must exist for the per-call paths above.
    (tmp_path / "a").mkdir(exist_ok=True)
    (tmp_path / "b").mkdir(exist_ok=True)
