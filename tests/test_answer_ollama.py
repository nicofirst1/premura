"""Ollama-backed answer operator tests (issue #54).

Default-suite (no model, no network): the transport (:func:`_ollama`) is
substituted at its boundary with a fake, deterministic transport, and the rest
of the seam (bounded surface, grader) runs for real through
:func:`run_answer_trial`. Pins three paths named in the issue:

* honest-pass — a model response grounded in the tool's own result passes;
* fabricated-fail — a model response with an invented estimate fails grounding;
* refusal — a model response mirroring an engine refusal passes.

No new question kinds, no judge involvement, no MCP server changes. Grading
stays the existing deterministic ``grade_answer`` — these tests exercise it
via the seam, not a duplicate check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from premura.harness import answer_ollama
from premura.harness.answer_trial import run_answer_trial

_KIND = "level_shift"


def _run(tmp_path: Path, operator, *, seed: int = 7, seed_empty_warehouse: bool = False):
    return run_answer_trial(
        seed=seed,
        question_kind=_KIND,
        operator=operator,
        warehouse_path=tmp_path / "warehouse.duckdb",
        session_log_path=tmp_path / "session_log.duckdb",
        scoreboard_path=tmp_path / "scoreboard.jsonl",
        seed_empty_warehouse=seed_empty_warehouse,
    )


def test_honest_grounded_response_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A model response that copies the tool's own estimate verbatim passes."""

    def _fake_ollama(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001
        # Read the tool result the operator embedded in the prompt and echo its
        # estimate back verbatim, like a well-behaved model would.
        marker = "TOOL RESULT (the tool has already been called for you"
        after = prompt[prompt.index(marker) :]
        json_text = after[after.index("{") : after.index("\n\nRespond")].rsplit("}", 1)[0] + "}"
        payload = json.loads(json_text)
        estimate = payload["result"]["estimate"]
        response = {
            "answer_text": f"The level shifted {estimate['direction']}.",
            "is_refusal": False,
            "refusal_reason": None,
            "claimed_estimates": estimate,
        }
        return json.dumps(response)

    monkeypatch.setattr(answer_ollama, "_ollama", _fake_ollama)
    operator = answer_ollama.OllamaAnswerOperator(model_id="fake:test")
    result = _run(tmp_path, operator)

    assert result.verdict.passed
    assert result.verdict.check("honesty").passed
    assert result.verdict.check("grounding").passed
    assert not result.outcome.is_refusal
    assert operator.transcript()[-1].role == "assistant"


def test_fabricated_estimate_fails_grounding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model response with an invented estimate fails the grounding check."""

    def _fake_ollama(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001, ARG005
        response = {
            "answer_text": "The level rose by about 999 over the window.",
            "is_refusal": False,
            "refusal_reason": None,
            "claimed_estimates": {"direction": "increase", "level_difference": 999.0},
        }
        return json.dumps(response)

    monkeypatch.setattr(answer_ollama, "_ollama", _fake_ollama)
    operator = answer_ollama.OllamaAnswerOperator(model_id="fake:test")
    result = _run(tmp_path, operator)

    assert not result.verdict.passed
    assert not result.verdict.check("grounding").passed


def test_refusal_mirrors_engine_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty warehouse makes the engine refuse; the model mirrors it honestly."""

    def _fake_ollama(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001, ARG005
        response = {
            "answer_text": "I cannot answer: there is not enough usable data.",
            "is_refusal": True,
            "refusal_reason": "insufficient_data",
            "claimed_estimates": {},
        }
        return json.dumps(response)

    monkeypatch.setattr(answer_ollama, "_ollama", _fake_ollama)
    operator = answer_ollama.OllamaAnswerOperator(model_id="fake:test")
    result = _run(tmp_path, operator, seed_empty_warehouse=True)

    assert result.verdict.passed
    assert result.verdict.ground_truth.is_refusal
    assert result.outcome.is_refusal


def test_malformed_response_retries_then_honestly_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-JSON responses are retried within the cap, then the operator refuses."""

    calls = {"n": 0}

    def _fake_ollama(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001, ARG005
        calls["n"] += 1
        return "not json at all"

    monkeypatch.setattr(answer_ollama, "_ollama", _fake_ollama)
    operator = answer_ollama.OllamaAnswerOperator(model_id="fake:test", max_tries=2)
    result = _run(tmp_path, operator)

    assert calls["n"] == 2
    assert result.outcome.is_refusal
    assert result.outcome.refusal_reason == "operator_malformed_response"
    # Ground truth here is available (non-empty warehouse), so refusing when the
    # engine computed a result fails refusal_fidelity — an honest, non-fabricating
    # failure, not a crash.
    assert not result.verdict.passed
    assert not result.verdict.check("refusal_fidelity").passed


def test_parse_answer_json_strips_markdown_fences() -> None:
    raw = '```json\n{"answer_text": "x", "is_refusal": false, "claimed_estimates": {}}\n```'
    parsed = answer_ollama._parse_answer_json(raw)
    assert parsed is not None
    assert parsed["answer_text"] == "x"


def test_parse_answer_json_returns_none_on_garbage() -> None:
    assert answer_ollama._parse_answer_json("not json") is None
