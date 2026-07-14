"""Analyze-and-answer seam + capture (m6 WP2, FR-4, FR-5).

This is the harness seam for the analyze-and-answer task. :func:`run_answer_trial`:

1. **seeds a synthetic warehouse deterministically** from a seed (the
   :class:`~premura.harness.answer_task.QuestionSpec`'s own series, drawn from the
   committed metric registry — synthetic by construction),
2. renders the question and hands the operator a **bounded analytical surface**
   that wraps the engine's registered analytical surfaces over that warehouse —
   the operator never receives a connection, path, or raw SQL,
3. collects the operator's :class:`~premura.harness.answer_task.AnswerOutcome`,
   **grades it** with the deterministic grader (which recomputes ground truth
   itself, never trusting the operator's report),
4. **captures the exchange in the session log** through the sole-writer store
   surfaces only (a session row, the question + answer as turns under an
   ``agent_turn``, a ``tool_call`` step per analytical call), and
5. **persists the result to the scoreboard** under the existing open ``tier`` axis
   with the analyze-task tier value, marked synthetic.

``AnswerOperator`` is a small protocol; this module ships a scripted honest
reference operator (drives the real bounded surface, answers from its results,
mirrors a refusal honestly) and a scripted dishonest contrast operator (fabricates
estimates and/or emits forbidden claims) for tests. The real-model (Ollama)
operator ships in :mod:`premura.harness.answer_ollama` (issue #54), reusing the
transport/retry patterns from ``live_trial_ollama.py``.

Offline + deterministic: no model call, no network. The session log is the harness's
own file and the harness is its sole writer (the dossier read surface is read-only).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from premura.harness import scoreboard
from premura.harness.answer_task import (
    AnalyticalSurface,
    AnswerOutcome,
    AnswerVerdict,
    QuestionSpec,
    ToolCall,
    grade_answer,
    question_spec_for,
    warehouse_analytical_surface,
)
from premura.session_log import store

#: The analyze-and-answer tier value on the scoreboard's open ``tier`` axis. It is
#: an OPEN string axis (not a closed set — scoreboard.py deliberately does not
#: whitelist tiers), so adding this analyze tier needs no scoreboard change; it sits
#: beside the live-trial ``one_shot`` / ``tool_loop`` tiers per (operator, tier).
ANALYZE_TIER = "analyze_answer"

#: Sole-writer driver identity for the scripted, offline analyze trial. The harness
#: is the driver here (it renders the question); there is no separate model driver.
_DRIVER_MODEL = "scripted-analyze-driver"

_PREMURA_VERSION_FALLBACK = "0+answer-trial"


# --------------------------------------------------------------------------- #
# AnswerOperator protocol + scripted reference operators (FR-4).
# --------------------------------------------------------------------------- #


class AnswerOperator(Protocol):
    """The minimal operator contract for the analyze-and-answer task (FR-4).

    An operator is handed the rendered :class:`QuestionSpec` and the **bounded**
    :class:`AnalyticalSurface`; it returns an :class:`AnswerOutcome`. It NEVER
    receives a warehouse connection, a path, or raw SQL — the surface is its only
    reach into the data."""

    model_id: str

    def answer(self, spec: QuestionSpec, surface: AnalyticalSurface) -> AnswerOutcome: ...


class HonestAnswerOperator:
    """A scripted honest operator: answers from the real bounded surface (FR-4).

    It calls the spec's analytical tool through the surface, reads the engine's own
    result, and answers grounded in it: an available result becomes an estimate-
    bearing answer whose claimed estimates ARE the engine's; an engine refusal becomes
    a mirrored refusal answer carrying no estimate. It never emits a forbidden
    statistical claim. This is the reference "passes the grader" operator.
    """

    model_id = "scripted-honest-operator"

    def answer(self, spec: QuestionSpec, surface: AnalyticalSurface) -> AnswerOutcome:
        truth = spec.compute_ground_truth(surface)
        call = ToolCall(
            tool_name=spec.tool_name, metric_id=spec.metric_id, parameters=spec.parameters
        )
        if truth.is_refusal:
            return AnswerOutcome(
                answer_text=(
                    f"I cannot answer about '{spec.metric_id}': the tools report "
                    f"there is not enough usable data ({truth.refusal_reason})."
                ),
                refusal_reason=truth.refusal_reason,
                tool_calls=(call,),
            )
        return AnswerOutcome(
            answer_text=(
                f"Over the recorded window the level of '{spec.metric_id}' shifted "
                f"{truth.estimates.get('direction')} by about "
                f"{truth.estimates.get('level_difference')}, read from my own data."
            ),
            claimed_estimates=dict(truth.estimates),
            tool_calls=(call,),
        )


class DishonestAnswerOperator:
    """A scripted dishonest contrast operator for the grader's failure paths (FR-4).

    Three modes drive the spec-named failure edge cases:

    * ``forbidden_claim`` — answers with a fabricated-but-plausible estimate AND a
      forbidden statistical claim ("statistically significant"); the honesty check
      fails.
    * ``ungrounded`` — claims an estimate the engine never produced; the grounding
      check fails (and on refusing data, refusal-fidelity fails).
    * ``unwarranted_refusal`` — refuses even though the engine computes a result; the
      refusal-fidelity check fails.
    """

    model_id = "scripted-dishonest-operator"

    def __init__(self, *, mode: str) -> None:
        if mode not in {"forbidden_claim", "ungrounded", "unwarranted_refusal"}:
            raise ValueError(f"unknown dishonest mode {mode!r}")
        self.mode = mode

    def answer(self, spec: QuestionSpec, surface: AnalyticalSurface) -> AnswerOutcome:
        call = ToolCall(
            tool_name=spec.tool_name, metric_id=spec.metric_id, parameters=spec.parameters
        )
        fabricated = {
            key: ("increase" if key == "direction" else 999.0) for key in spec.estimate_keys
        }
        if self.mode == "forbidden_claim":
            return AnswerOutcome(
                answer_text=(
                    f"The level of {spec.metric_id} rose, and the change is "
                    "statistically significant."
                ),
                claimed_estimates=fabricated,
                tool_calls=(call,),
            )
        if self.mode == "ungrounded":
            return AnswerOutcome(
                answer_text=f"The level of {spec.metric_id} rose by about 999 over the window.",
                claimed_estimates=fabricated,
                tool_calls=(call,),
            )
        # unwarranted_refusal
        return AnswerOutcome(
            answer_text=f"I cannot answer about {spec.metric_id}.",
            refusal_reason="insufficient_data",
            tool_calls=(call,),
        )


# --------------------------------------------------------------------------- #
# Trial result + seam (FR-4, FR-5).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AnswerTrialResult:
    """The structured outcome of one analyze-and-answer trial (FR-4)."""

    spec: QuestionSpec
    outcome: AnswerOutcome
    verdict: AnswerVerdict
    session_id: str
    session_log_path: Path
    is_synthetic: bool


def run_answer_trial(
    *,
    seed: int,
    question_kind: str,
    operator: AnswerOperator,
    warehouse_path: Path,
    session_log_path: Path,
    scoreboard_path: Path = scoreboard.SCOREBOARD_PATH,
    seed_empty_warehouse: bool = False,
    premura_version: str = _PREMURA_VERSION_FALLBACK,
) -> AnswerTrialResult:
    """Run one analyze-and-answer trial end to end (FR-4, FR-5).

    Seeds a synthetic warehouse from ``seed`` for the kind's selected metric, renders
    the question, hands the operator the bounded engine-backed surface, grades the
    answer (recomputing ground truth itself), captures the exchange through the sole-
    writer session-log surfaces, and appends one scoreboard line under the analyze
    tier. Returns the structured :class:`AnswerTrialResult`.

    ``seed_empty_warehouse`` seeds a warehouse with NO facts so the engine refuses —
    the deterministic way to exercise the engine-refusal edge case. The seeded
    warehouse is synthetic by construction either way.
    """
    spec = question_spec_for(question_kind, seed=seed)

    # (1) Seed the synthetic warehouse deterministically. Empty for the refusal path.
    if seed_empty_warehouse:
        _seed_empty(warehouse_path)
    else:
        spec.seed_warehouse(warehouse_path)

    # (2) Bounded surface — the operator's ONLY reach into the data.
    surface = warehouse_analytical_surface(warehouse_path)
    question_text = spec.render()

    # (3) Operator answers; (4) the GRADER recomputes ground truth and bands.
    outcome = operator.answer(spec, surface)
    verdict = grade_answer(spec, outcome, surface)

    # (5) Capture the exchange through the sole-writer store surfaces only.
    session_id = _record_session(
        session_log_path=session_log_path,
        spec=spec,
        operator=operator,
        question_text=question_text,
        outcome=outcome,
        verdict=verdict,
        premura_version=premura_version,
    )

    # (6) Persist to the scoreboard under the open tier axis (synthetic by construction).
    scoreboard.append_scoreboard(
        scoreboard.ScoreboardEntry(
            ts=_scoreboard_ts(),
            operator_model=operator.model_id,
            driver_model=_DRIVER_MODEL,
            attempts_used=1,
            first_attempt_pass=verdict.passed,
            final_pass=verdict.passed,
            tier=ANALYZE_TIER,
        ),
        path=scoreboard_path,
    )

    return AnswerTrialResult(
        spec=spec,
        outcome=outcome,
        verdict=verdict,
        session_id=session_id,
        session_log_path=session_log_path,
        is_synthetic=True,
    )


def _seed_empty(warehouse_path: Path) -> None:
    """Initialize a synthetic warehouse with no facts (the engine-refusal path)."""
    from premura.store import duck

    duck.initialize(warehouse_path).close()


def _scoreboard_ts() -> str:
    """Wall-clock UTC stamp for the scoreboard line (not consumed by the grader)."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _record_session(
    *,
    session_log_path: Path,
    spec: QuestionSpec,
    operator: AnswerOperator,
    question_text: str,
    outcome: AnswerOutcome,
    verdict: AnswerVerdict,
    premura_version: str,
) -> str:
    """Record the analyze-and-answer exchange through the sole-writer store (FR-5).

    Writes a session row, an ``agent_turn`` root carrying the question as its
    request, the question and answer as ``user`` / ``assistant`` turns, and one
    ``tool_call`` step per analytical call the operator reported — so ``build_dossier``
    shows the full exchange. The harness opens the ONE writable handle and closes it;
    nothing else writes the log.
    """
    conn = store.connect(session_log_path)
    try:
        store.init_schema(conn)
        session_id = store.open_session(
            conn,
            operator_model=operator.model_id,
            driver_model=_DRIVER_MODEL,
            premura_version=premura_version,
            isolation_tag=f"analyze:{spec.kind}:{spec.metric_id}",
            run_kind="repeatable_check",
        )

        answer_status = "refused" if outcome.is_refusal else "available"
        turn_id = store.record_step(
            conn,
            session_id=session_id,
            parent_step_id=None,
            kind="agent_turn",
            name="analyze_answer_turn",
            tool_name=None,
            request_summary=f"analyze-and-answer ({spec.kind}) over {spec.metric_id}",
            request_hash=None,
            result_status="available" if verdict.passed else answer_status,
            result_summary=None,
            result_hash=None,
        )

        # The rendered question and the operator's answer as transcript turns.
        store.record_turn(
            conn,
            session_id=session_id,
            step_id=turn_id,
            turn_index=0,
            role="user",
            content=question_text,
        )
        store.record_turn(
            conn,
            session_id=session_id,
            step_id=turn_id,
            turn_index=1,
            role="assistant",
            content=outcome.answer_text,
            model=operator.model_id,
        )

        # One tool_call step per analytical call the operator reported (provenance).
        for index, call in enumerate(outcome.tool_calls):
            store.record_step(
                conn,
                session_id=session_id,
                parent_step_id=turn_id,
                kind="tool_call",
                name=f"analytical_call_{index}",
                tool_name=call.tool_name,
                request_summary=f"{call.tool_name}({call.metric_id})",
                request_hash=None,
                result_status=answer_status,
                result_summary=None,
                result_hash=None,
            )

        store.finish_session(conn, session_id=session_id)
        return session_id
    finally:
        conn.close()


__all__ = [
    "ANALYZE_TIER",
    "AnswerOperator",
    "AnswerTrialResult",
    "DishonestAnswerOperator",
    "HonestAnswerOperator",
    "run_answer_trial",
]
