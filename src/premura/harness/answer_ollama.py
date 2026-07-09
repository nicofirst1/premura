"""Ollama-backed answer operator for the analyze-and-answer task (m6, #54).

``answer_trial.py`` ships only scripted ``HonestAnswerOperator`` /
``DishonestAnswerOperator`` reference operators and defers a real-model
operator. This module lifts that deferral: :class:`OllamaAnswerOperator`
implements the same :class:`~premura.harness.answer_task.AnswerOperator`
protocol, but a local Ollama model calls the bounded
:class:`~premura.harness.answer_task.AnalyticalSurface` and drafts the answer,
instead of a script.

Reuses the transport (:func:`premura.harness.live_trial_ollama._ollama`,
stdlib-only, local-only URL validation) and its retry-on-malformed-output shape
verbatim — no second HTTP client, no second Ollama URL policy.

Scope (per issue #54): no new question kinds, no judge involvement, no MCP
server changes. The operator's draft answer is graded by the EXISTING
deterministic :func:`~premura.harness.answer_task.grade_answer` — this module
adds no grading logic of its own.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from premura.harness.answer_task import AnalyticalSurface, AnswerOutcome, QuestionSpec, ToolCall
from premura.harness.live_trial_ollama import DEFAULT_MODEL, OllamaUnavailableError, _ollama

#: Bounded retry cap for a malformed (non-JSON) model response. Small: the
#: model is asked for one structured JSON object, not code — a couple of
#: reminders is enough to keep this a cheap seam, not a second retry loop.
MAX_TRIES = 2

_PROMPT_TEMPLATE = """\
You are answering a health question about the operator's OWN recorded data.
You may reach the data ONLY by calling the one tool below; you never see a
database, a file, or raw numbers directly.

TOOL: {tool_name}(metric_id={metric_id!r}{extra_params})
Call it by producing your answer from ITS result only, never invent a number.

QUESTION: {question}

TOOL RESULT (the tool has already been called for you; use ONLY these values):
{tool_result_json}

Respond with ONE JSON object, nothing else, no markdown fences, of this exact
shape:
{{
  "answer_text": "<your prose answer to the operator, plain language>",
  "is_refusal": <true if the tool result says status == "refused", else false>,
  "refusal_reason": "<the tool's refusal reason if is_refusal, else null>",
  "claimed_estimates": {{<the tool's own estimate keys/values verbatim, or {{}}\
 if is_refusal>}}
}}

RULES:
- If the tool result's "status" is "refused": is_refusal MUST be true,
  claimed_estimates MUST be {{}}, and answer_text must honestly say you cannot
  answer and why. Do NOT invent an estimate for a refused result.
- If the tool result's "status" is "available": is_refusal MUST be false,
  and claimed_estimates MUST carry the tool's own estimate values EXACTLY
  (copy them, do not compute or round them yourself).
- NEVER use the words "significant"/"significance", never cite a p-value,
  never claim a cause, and never compare to a population norm or reference
  range. State only what the tool's own result shows.
- Output ONLY the JSON object.
"""


@dataclass(slots=True)
class _RawTurn:
    """One captured prompt/response exchange, structurally a live-trial turn."""

    role: str
    content: str
    model: str | None = None


@dataclass(slots=True)
class OllamaAnswerOperator:
    """Real-model operator for the analyze-and-answer task (FR-4, issue #54).

    Implements the :class:`~premura.harness.answer_task.AnswerOperator`
    protocol. ``answer`` calls the spec's declared analytical tool through the
    bounded surface ITSELF (the model never gets a raw connection either), then
    asks the local model to draft the answer from that tool result only. A
    malformed (non-JSON) model response is retried, feeding the parse error
    back verbatim, up to :data:`MAX_TRIES`; if the model still cannot produce
    parseable JSON, the operator honestly refuses rather than fabricating an
    estimate-bearing answer (never a crash, never a silent guess).

    Grading stays entirely with the existing deterministic
    :func:`~premura.harness.answer_task.grade_answer` — this operator only
    produces the :class:`~premura.harness.answer_task.AnswerOutcome` under
    grade.
    """

    model_id: str = DEFAULT_MODEL
    max_tries: int = MAX_TRIES
    last_prompt: str = field(default="", init=False)
    last_response: str = field(default="", init=False)

    def answer(self, spec: QuestionSpec, surface: AnalyticalSurface) -> AnswerOutcome:
        call = ToolCall(
            tool_name=spec.tool_name, metric_id=spec.metric_id, parameters=spec.parameters
        )
        tool_payload = surface(spec.tool_name, spec.metric_id, **spec.parameters)

        extra_params = "".join(f", {k}={v!r}" for k, v in spec.parameters.items())
        prompt = _PROMPT_TEMPLATE.format(
            tool_name=spec.tool_name,
            metric_id=spec.metric_id,
            extra_params=extra_params,
            question=spec.render(),
            tool_result_json=json.dumps(tool_payload, default=str),
        )

        parse_error = ""
        for _attempt in range(1, self.max_tries + 1):
            full_prompt = prompt if not parse_error else f"{prompt}\n\n{parse_error}"
            self.last_prompt = full_prompt
            raw_response = _ollama(full_prompt, model=self.model_id)
            self.last_response = raw_response
            parsed = _parse_answer_json(raw_response)
            if parsed is not None:
                return _outcome_from_parsed(parsed, call)
            parse_error = (
                "Your previous response was not a single valid JSON object as "
                "specified. Output ONLY the JSON object, no prose, no fences."
            )

        # Cap exhausted: the model never produced parseable JSON. Refuse
        # honestly rather than fabricate an estimate-bearing answer.
        return AnswerOutcome(
            answer_text=(
                f"I cannot answer about '{spec.metric_id}': my draft response could not "
                "be parsed as a structured answer."
            ),
            refusal_reason="operator_malformed_response",
            tool_calls=(call,),
        )

    def transcript(self) -> list[_RawTurn]:
        """Expose the final prompt/response exchange as a two-turn transcript.

        Mirrors :meth:`~premura.harness.live_trial_ollama.OllamaOperator.transcript`
        so callers can persist this tier's exchange the same way. Empty until
        :meth:`answer` has run.
        """
        if not self.last_response:
            return []
        return [
            _RawTurn(role="user", content=self.last_prompt),
            _RawTurn(role="assistant", content=self.last_response, model=self.model_id),
        ]


def _parse_answer_json(raw_response: str) -> dict[str, Any] | None:
    """Extract and parse the model's single JSON answer object, or ``None``.

    Strips optional markdown fences (models sometimes add them despite being
    told not to), then finds the outermost ``{...}`` object and parses it.
    Returns ``None`` on any failure — a returnable sentinel the caller retries
    or refuses on, never an exception escaping into the trial.
    """
    text = raw_response.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _outcome_from_parsed(parsed: dict[str, Any], call: ToolCall) -> AnswerOutcome:
    """Project the model's parsed JSON answer onto a structured :class:`AnswerOutcome`."""
    is_refusal = bool(parsed.get("is_refusal"))
    answer_text = str(parsed.get("answer_text") or "")
    if is_refusal:
        reason = parsed.get("refusal_reason")
        return AnswerOutcome(
            answer_text=answer_text,
            refusal_reason=str(reason) if reason else "refused",
            tool_calls=(call,),
        )
    estimates_raw = parsed.get("claimed_estimates")
    estimates = estimates_raw if isinstance(estimates_raw, dict) else {}
    return AnswerOutcome(
        answer_text=answer_text,
        claimed_estimates=estimates,
        tool_calls=(call,),
    )


__all__ = [
    "MAX_TRIES",
    "OllamaAnswerOperator",
    "OllamaUnavailableError",
]
