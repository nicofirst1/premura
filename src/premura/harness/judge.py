"""The rubric-driven AI judge (judge-ai m3 WP2, FR-3/FR-4).

The judge is harness-side code that assesses one **recorded live-trial session**
against a versioned rubric and persists exactly one descriptive judgment back into
the session log. It is the consumer the improvement hook (next mission) will read;
this mission only *produces* the judgment.

The flow of :func:`judge_session`:

1. Assemble a read-only :class:`~premura.session_log.dossier.SessionDossier` for the
   session (the judge never reaches into the log tables ad hoc; the read surface opens
   the log strictly read-only).
2. Load the bounded rubric (:func:`load_rubric`) — its criterion *ids* are rubric-owned
   data, never enumerated in code (FR-3).
3. Build a prompt from dossier + rubric and call a **local** model through an injectable
   transport seam (same DIRECTIVE_036 pattern as the tool-loop ``Transport``). The
   default transport reuses the existing local-only Ollama guard verbatim (NFR-2): the
   PHI-bearing dossier may only reach a local model backend.
4. Parse and validate the model's structured verdict — bands against the store's
   ``CRITERION_BANDS``, criterion ids against the rubric. A malformed response is retried
   a bounded number of times.
5. Persist exactly one ``log_judgment`` row via :func:`store.record_judgment` with the
   honest ``status`` (``complete`` / ``unparseable`` / ``model_unavailable``). The judge
   **can never alter** ``contract_pass``, the scoreboard, or the trial verdict — they are
   out of its write reach by construction (it only opens the dossier read-only and only
   writes ``log_judgment``).

No code path here syncs or exports the dossier, the prompt, or the judgment (NFR-2).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from premura.harness.live_trial_ollama import (
    DEFAULT_MODEL,
    OllamaUnavailableError,
    _ollama,
)
from premura.session_log import dossier as dossier_mod
from premura.session_log import store

if TYPE_CHECKING:
    from pathlib import Path

    from premura.session_log.dossier import SessionDossier

# The rubric document packaged with the harness (FR-3). Single home for the
# criterion ids + the add-a-criterion rule; the judge reads it, never enumerates it.
_RUBRIC_FILE = "JUDGE_RUBRIC.md"
_PACKAGE = "premura.harness"

#: A judge transport is the OUTSIDE boundary (DIRECTIVE_036): it takes the assembled
#: judge prompt + the model id and returns the model's raw text output (or raises
#: :class:`OllamaUnavailableError`). The default goes through the local-only Ollama
#: ``/api/generate``; tests and the harness wiring substitute a scripted callable.
JudgeTransport = Callable[..., str]

#: Default bounded retry budget for a malformed model response (FR-4).
_DEFAULT_MAX_RETRIES = 2


class _MalformedVerdictError(ValueError):
    """The model's output could not be parsed/validated into a rubric verdict.

    Internal control-flow signal: it drives the bounded retry and, on exhaustion,
    the honest ``unparseable`` status. It never escapes :func:`judge_session`.
    """


@dataclass(frozen=True, slots=True)
class Rubric:
    """The loaded judge rubric (FR-3): its version + its criterion ids.

    ``criterion_ids`` is parsed from the rubric document's criterion headings —
    the rubric is the single source of the id set, so adding a criterion is a
    rubric edit (and a ``rubric_version`` bump), never a code change. The full
    ``text`` is what the judge serves the model so the model bands the right ids.
    ``criterion_categories`` maps each criterion id to its closed category, parsed
    from the same headings + their ``- **category:** `…``` line — the single place
    criterion→category is read (the improvement hook reuses this, not a second
    parser).
    """

    version: str
    criterion_ids: tuple[str, ...]
    text: str
    criterion_categories: dict[str, str] = field(default_factory=dict)

    def category_of(self, criterion_id: str) -> str | None:
        """The closed category of ``criterion_id``, or None if the rubric omits it."""
        return self.criterion_categories.get(criterion_id)


def load_rubric() -> Rubric:
    """Load the packaged judge rubric: version, criterion ids, categories (FR-3).

    Parses ``rubric_version``, the ``### `<id>``` criterion headings, and each
    criterion's ``- **category:** `<category>``` line out of the bundled
    ``JUDGE_RUBRIC.md``. Code never hardcodes the criterion ids or their
    categories; this read is the single place they enter the harness (the judge
    and, reusing this same parser, the improvement hook).
    """
    import importlib.resources as resources

    text = resources.files(_PACKAGE).joinpath(_RUBRIC_FILE).read_text(encoding="utf-8")
    version_match = re.search(r"rubric_version:\s*([^\s`]+)", text)
    if version_match is None:
        raise ValueError(f"{_RUBRIC_FILE} is missing a `rubric_version:` declaration")
    version = version_match.group(1)
    # Criterion headings are level-3 with a backtick-wrapped id: "### `the-id`".
    criterion_ids = tuple(re.findall(r"^###\s+`([a-z0-9-]+)`", text, re.MULTILINE))
    if not criterion_ids:
        raise ValueError(f"{_RUBRIC_FILE} defines no criteria")
    # Each criterion heading is followed by a "- **category:** `<category>`" line.
    # Parse them positionally: a heading binds to the first category line after it.
    categories: dict[str, str] = {}
    for match in re.finditer(
        r"^###\s+`([a-z0-9-]+)`(.*?)(?=^###\s+`|\Z)", text, re.MULTILINE | re.DOTALL
    ):
        cid, body = match.group(1), match.group(2)
        cat_match = re.search(r"\*\*category:\*\*\s*`([a-z0-9_]+)`", body)
        if cat_match:
            categories[cid] = cat_match.group(1)
    return Rubric(
        version=version,
        criterion_ids=criterion_ids,
        text=text,
        criterion_categories=categories,
    )


def _default_transport(prompt: str, *, model: str) -> str:
    """The default local-only transport: the existing Ollama generate path (NFR-2).

    Reuses ``live_trial_ollama._ollama`` verbatim, so the local-only URL guard
    carries over to the judge: the PHI-bearing dossier prompt can never be sent
    off-machine by configuration drift. Raises :class:`OllamaUnavailableError`
    when the backend is unreachable so the judge records ``model_unavailable``.
    """
    return _ollama(prompt, model=model)


def _render_transcript(doc: SessionDossier) -> str:
    if not doc.has_transcript:
        return "(no transcript was recorded for this session)"
    lines = []
    for turn in doc.transcript:
        tool = f" tool={turn.tool_name}" if turn.tool_name else ""
        lines.append(f"[{turn.turn_index}] {turn.role}{tool}: {turn.content}")
    return "\n".join(lines)


def _render_attempts(doc: SessionDossier) -> str:
    if not doc.attempts:
        return "(no per-attempt telemetry was recorded)"
    lines = []
    for att in doc.attempts:
        lines.append(
            f"attempt {att.attempt_index}: self_reconciliation_passed="
            f"{att.self_reconciliation_passed} unaccounted={att.unaccounted} "
            f"parser_error={att.parser_error!r}"
        )
    return "\n".join(lines)


def build_prompt(doc: SessionDossier, rubric: Rubric) -> str:
    """Assemble the judge prompt from the dossier + rubric (FR-4).

    The model is given the grader's recomputed facts (which it evaluates but never
    alters), the per-attempt telemetry, the full transcript, and the rubric text,
    then asked to band each rubric criterion id and return a strict JSON verdict.
    The criterion ids it must use come from the rubric, not from code.
    """
    facts = (
        f"contract_pass={doc.contract_pass}  rows_inserted={doc.rows_inserted}\n"
        f"operator_model={doc.operator_model}  driver_model={doc.driver_model}  "
        f"run_kind={doc.run_kind}"
    )
    criterion_list = "\n".join(f"  - {cid}" for cid in rubric.criterion_ids)
    bands = ", ".join(sorted(store.CRITERION_BANDS))
    return (
        "You are an evaluator assessing HOW an AI operator worked during a recorded "
        "Premura live-trial session. You judge the operator's PROCESS — not whether the "
        "ingest passed. A separate mechanical grader already decided pass/fail; you must "
        "NEVER restate, recompute, or override the grader's facts, the scoreboard, or the "
        "trial verdict.\n\n"
        "Assess each rubric criterion with exactly one descriptive BAND from this closed "
        f"set: {bands}. Use no numeric scores and no pass/fail language.\n\n"
        "=== GRADER FACTS (you evaluate these; you never change them) ===\n"
        f"{facts}\n\n"
        "=== PER-ATTEMPT TELEMETRY ===\n"
        f"{_render_attempts(doc)}\n\n"
        "=== TRANSCRIPT (in turn order) ===\n"
        f"{_render_transcript(doc)}\n\n"
        "=== RUBRIC ===\n"
        f"{rubric.text}\n\n"
        "=== YOUR TASK ===\n"
        "Band EACH of these criterion ids (use exactly these ids):\n"
        f"{criterion_list}\n\n"
        "Respond with ONLY a JSON object of this shape, no prose, no code fences:\n"
        '{"criteria": {"<criterion-id>": {"band": "<band>", "rationale": "<short reason>"}, '
        '...}, "overall_band": "<band or null>", "rationale": "<short overall reason>"}\n'
    )


def _parse_verdict(raw: str, rubric: Rubric) -> dict:
    """Parse + validate a model response into a rubric verdict (FR-4).

    Raises :class:`_MalformedVerdictError` if the output is not JSON, not the
    expected shape, names a criterion id the rubric does not define, or carries a
    band outside ``CRITERION_BANDS``. The criterion-id check enforces FR-3 from
    the judge side: an off-rubric id is malformed, never silently recorded.
    """
    text = raw.strip()
    # Tolerate an accidental ```json fence the prompt asked the model to omit.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _MalformedVerdictError(f"response is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise _MalformedVerdictError("response is not a JSON object")
    criteria = payload.get("criteria")
    if not isinstance(criteria, dict) or not criteria:
        raise _MalformedVerdictError("response has no non-empty 'criteria' object")

    rubric_ids = set(rubric.criterion_ids)
    validated: dict[str, dict[str, object]] = {}
    for cid, entry in criteria.items():
        if cid not in rubric_ids:
            raise _MalformedVerdictError(f"criterion id {cid!r} is not in the rubric")
        if not isinstance(entry, dict):
            raise _MalformedVerdictError(f"criterion {cid!r} is not an object")
        band = entry.get("band")
        if band not in store.CRITERION_BANDS:
            raise _MalformedVerdictError(f"criterion {cid!r} band {band!r} is out of vocabulary")
        validated[cid] = {"band": band, "rationale": str(entry.get("rationale", ""))}

    overall_band = payload.get("overall_band")
    if overall_band is not None and overall_band not in store.CRITERION_BANDS:
        raise _MalformedVerdictError(f"overall_band {overall_band!r} is out of vocabulary")
    rationale = payload.get("rationale")

    return {
        "criteria": validated,
        "overall_band": overall_band,
        "rationale": None if rationale is None else str(rationale),
    }


@dataclass(frozen=True, slots=True)
class JudgmentResult:
    """The outcome of one :func:`judge_session` invocation (the persisted row's shape).

    ``judgment_id`` is the id of the single ``log_judgment`` row written; ``status``
    is the honest status (``complete`` / ``unparseable`` / ``model_unavailable``).
    """

    judgment_id: str
    status: str
    criteria: dict[str, dict[str, object]] = field(default_factory=dict)
    overall_band: str | None = None


def judge_session(
    log_path: Path,
    *,
    session_id: str,
    model: str = DEFAULT_MODEL,
    transport: JudgeTransport | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> JudgmentResult:
    """Judge one recorded session against the rubric; persist one judgment (FR-4).

    Assembles the read-only dossier, loads the rubric, prompts the local model
    through ``transport`` (default: the local-only Ollama path), parses/validates
    the verdict with a bounded retry, and persists exactly one ``log_judgment``
    row via :func:`store.record_judgment` with the honest status. The judge writes
    nothing but that row — ``contract_pass``, the scoreboard, and the trial verdict
    are out of its reach.

    Args:
        log_path: the session-log file the recorded session lives in.
        session_id: the session to judge.
        model: the local model id to pass to the transport.
        transport: the injectable model backend (DIRECTIVE_036). Default is the
            local-only Ollama generate path; tests pass a scripted callable.
        max_retries: bounded retries for a malformed response (default 2).

    Returns:
        A :class:`JudgmentResult` carrying the persisted row's id + honest status.
    """
    send = transport if transport is not None else _default_transport
    rubric = load_rubric()
    doc = dossier_mod.build_dossier(log_path, session_id=session_id)
    prompt = build_prompt(doc, rubric)

    status = "unparseable"
    criteria: dict[str, dict[str, object]] = {}
    overall_band: str | None = None
    rationale: str | None = None
    raw_output: str | None = None

    # First attempt + up to ``max_retries`` retries on a malformed response.
    for _attempt in range(max_retries + 1):
        try:
            raw = send(prompt, model=model)
        except OllamaUnavailableError as exc:
            status = "model_unavailable"
            raw_output = str(exc)
            criteria = {}
            overall_band = None
            rationale = None
            break
        raw_output = raw
        try:
            verdict = _parse_verdict(raw, rubric)
        except _MalformedVerdictError:
            # Keep the latest raw output and retry within the budget.
            continue
        status = "complete"
        criteria = verdict["criteria"]
        overall_band = verdict["overall_band"]
        rationale = verdict["rationale"]
        break

    # An honest error status carries empty criteria + NULL overall_band (FR-1).
    if status != "complete":
        criteria = {}
        overall_band = None
        rationale = None

    conn = store.connect(log_path)
    try:
        judgment_id = store.record_judgment(
            conn,
            session_id=session_id,
            judge_model=model,
            rubric_version=rubric.version,
            status=status,
            criteria=criteria,
            overall_band=overall_band,
            rationale=rationale,
            raw_output=raw_output,
        )
    finally:
        conn.close()

    return JudgmentResult(
        judgment_id=judgment_id,
        status=status,
        criteria=criteria,
        overall_band=overall_band,
    )


__all__ = [
    "JudgeTransport",
    "JudgmentResult",
    "Rubric",
    "build_prompt",
    "judge_session",
    "load_rubric",
]
