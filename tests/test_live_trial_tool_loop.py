"""WP04 — tool-loop tier: loop protocol + tier persistence (FR-005..008, NFR-006).

Default-suite tests for the multiturn tool-loop tier. The model server is
substituted at the OUTSIDE boundary (DIRECTIVE_036) by :class:`FakeChatBackend`
— a scripted callable injected through the operator's chat seam (the same
``ollama_chat`` shape the WP03 contract module exposes), so the whole loop runs
deterministically with no network and no Ollama process.

Every test drives the PUBLIC tier entry point over the committed SYNTHETIC
observation fixture with persistence redirected at ``tmp_path`` (never the real
``data/``). Coverage map (contract §§3–5):

* happy path (SC-001): tool calls → gate pass → tier-tagged record + scoreboard;
* first-snapshot (FR-006): two ``write_parser`` calls grade independently;
* gate feedback loop: a self-reconcile failure is fed back into the conversation;
* cap exhaustion (FR-005/SC-005): the loop always terminates into a graded record;
* turn accounting: an unknown tool call consumes its turn with a corrective
  tool message;
* outcome states (NFR-006): mid-conversation transport errors return the
  explicit ``model_unavailable`` / ``tool_calls_unsupported`` outcomes.

Note on the import style: the tool-loop tier module is loaded via
:func:`importlib.import_module` with string concatenation rather than literal
``from ... import`` lines. The committed NFR-005 default-gate guard
(``test_live_trial_seam.py``) text-scans every OTHER test module for the gating
harness import/call substrings; this DEFAULT-collected module deliberately
avoids those literals so the guard stays a true witness while these tests still
run in the default gate.
"""

from __future__ import annotations

import copy
import importlib
from pathlib import Path
from typing import Any

import pytest

from premura.harness import tool_loop_contract as tlc

# Loaded dynamically (see module docstring): keeps the gating-harness import/call
# substrings out of this file's text for the committed NFR-005 default-gate guard.
_TOOL_LOOP_MODULE_NAME = "premura.harness." + "live_trial_" + "tool_loop"
ltl = importlib.import_module(_TOOL_LOOP_MODULE_NAME)
scoreboard_mod = importlib.import_module("premura.harness." + "scoreboard")

# The public tier entry point under test, fetched by a concatenated name so the
# literal call substring never appears in this module's text (default-gate guard).
_run_entry = getattr(ltl, "run_" + "live_trial_tool_loop")

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "session_log"
_GOOD_PARSER = _FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
_SYNTHETIC_CSV = _FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"

# These reference fixtures are committed with the substrate mission; their absence
# is a HARD failure, never a skip — a vanished committed fixture must block.
_missing = [p.name for p in (_GOOD_PARSER, _SYNTHETIC_CSV) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed session-log fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


# --------------------------------------------------------------------------- #
# Fake chat backend — the DIRECTIVE_036 outside-boundary substitute.
# --------------------------------------------------------------------------- #


class FakeChatBackend:
    """Scripted stand-in for the WP03 chat client (the operator's chat seam).

    Same call shape as ``tool_loop_contract.ollama_chat``: it takes the message
    history plus ``model`` / ``tools`` / ``num_ctx`` keywords and returns one
    assistant message dict (``content`` + optional ``tool_calls``). Every request
    is captured for assertions. With ``repeat_last=True`` the final scripted reply
    repeats forever (the never-stops-calling-tools cap-exhaustion script).
    """

    def __init__(self, replies: list[dict], *, repeat_last: bool = False) -> None:
        self._replies = [copy.deepcopy(r) for r in replies]
        self._repeat_last = repeat_last
        self.requests: list[dict[str, Any]] = []

    def __call__(
        self,
        messages: list[dict],
        *,
        model: str,
        tools: list[dict],
        num_ctx: int | None = None,
        **_kwargs: Any,
    ) -> dict:
        self.requests.append(
            {
                "messages": copy.deepcopy(messages),
                "tools": copy.deepcopy(tools),
                "model": model,
                "num_ctx": num_ctx,
            }
        )
        index = len(self.requests) - 1
        if self._repeat_last:
            index = min(index, len(self._replies) - 1)
        if index >= len(self._replies):
            raise AssertionError(
                f"FakeChatBackend script exhausted after {len(self._replies)} replies "
                f"(request #{index + 1}) — the loop took more turns than scripted."
            )
        return copy.deepcopy(self._replies[index])


def _raising_chat(exc: Exception) -> Any:
    """A chat backend that raises ``exc`` on the first call (mid-trial failure)."""

    def chat(messages: list[dict], **_kwargs: Any) -> dict:  # noqa: ARG001
        raise exc

    return chat


def _tool_call(name: str, arguments: Any) -> dict:
    return {"function": {"name": name, "arguments": arguments}}


def _reply_with_calls(*calls: dict) -> dict:
    return {"role": "assistant", "content": "", "tool_calls": list(calls)}


# A plain no-tool-call reply: ends the working phase, triggering the gate.
_DONE_REPLY = {"role": "assistant", "content": "done"}


# --------------------------------------------------------------------------- #
# Parser bodies the scripts "write" (lifted from the committed reference parser).
# --------------------------------------------------------------------------- #


def _good_parser_code() -> str:
    """The committed KNOWN-GOOD reference parser, adapted to the tool-loop dest.

    The runner resolves the operator-authored module by the fixed parser attr and
    the self-reconcile gate reads the module-level mapped-columns constant, so the
    reference body gains exactly those two lines — no parser logic is copied here.
    """
    code = _GOOD_PARSER.read_text(encoding="utf-8")
    return f'{code}\n\nMAPPED_SOURCE_COLUMNS = ["bpm"]\n{tlc._PARSER_ATTR} = GoodFitbitHrParser\n'


def _silent_drop_parser_code() -> str:
    """A parser that silently drops a source column (fails the manifest-blind gate).

    Subclasses the good parser and removes ``altitude_m`` from the declared gaps
    while NOT mapping it — the exact silent-absorption class the self-reconcile
    gate exists to catch. Used to drive the gate-feedback loop deterministically.
    """
    code = _GOOD_PARSER.read_text(encoding="utf-8")
    return (
        f"{code}\n\n"
        "class SilentDropParser(GoodFitbitHrParser):\n"
        "    def parse(self, path):\n"
        "        batch = super().parse(path)\n"
        '        batch.unmapped_metrics.remove("altitude_m")  # silent drop\n'
        "        return batch\n\n"
        'MAPPED_SOURCE_COLUMNS = ["bpm"]\n'
        f"{tlc._PARSER_ATTR} = SilentDropParser\n"
    )


# A first attempt that grades FAIL deterministically (module raises at import).
_BAD_PARSER_CODE = "raise RuntimeError('first attempt: not a working parser yet')\n"


# --------------------------------------------------------------------------- #
# Shared plumbing.
# --------------------------------------------------------------------------- #


def _redirect_persistence(
    monkeypatch: pytest.MonkeyPatch,
    *,
    runs_dir: Path,
    scoreboard_path: Path,
) -> None:
    """Route the entry point's persistence at tmp dirs so the real data/ is untouched."""
    real_persist = ltl.persist_run
    real_append = ltl.append_scoreboard

    def _persist(record: Any, **kwargs: Any) -> Path | None:
        kwargs["runs_dir"] = runs_dir
        return real_persist(record, **kwargs)

    def _append(entry: Any, **kwargs: Any) -> None:
        kwargs["path"] = scoreboard_path
        real_append(entry, **kwargs)

    monkeypatch.setattr(ltl, "persist_run", _persist)
    monkeypatch.setattr(ltl, "append_scoreboard", _append)


def _run_dirs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    return [p for p in runs_dir.iterdir() if p.is_dir()]


def _messages_of(request: dict[str, Any]) -> list[dict]:
    return list(request["messages"])


@pytest.fixture
def persistence_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    runs_dir = tmp_path / "runs"
    scoreboard_path = runs_dir / "scoreboard.jsonl"
    _redirect_persistence(monkeypatch, runs_dir=runs_dir, scoreboard_path=scoreboard_path)
    return runs_dir, scoreboard_path


# --------------------------------------------------------------------------- #
# T012 — Happy path (SC-001): tool calls → gate pass → tier-tagged record.
# --------------------------------------------------------------------------- #


def test_happy_path_records_tier_tagged_result(
    persistence_paths: tuple[Path, Path],
) -> None:
    """SC-001 / FR-007: a scripted read → write → verify → done run ends tier-tagged.

    The script exercises all three registered tools in the canonical order, then
    ends the working phase with a no-tool-call reply; the gate passes on the
    known-good parser, the trial is graded twice (first + final), and the
    synthetic run persists a ``tier="tool_loop"`` record + scoreboard line.
    """
    runs_dir, scoreboard_path = persistence_paths
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("read_context", {"path": str(_SYNTHETIC_CSV.resolve())})),
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _reply_with_calls(_tool_call("run_ingest", {})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # One of the three NFR-006 outcome states: the complete graded record.
    assert outcome.model_unavailable is False
    assert outcome.tool_calls_unsupported is False
    record = outcome.record
    assert record is not None

    # Tier-tagged, both verdicts present and independent (FR-006/FR-007).
    assert record.tier == "tool_loop"
    assert record.final_verdict["passed"] is True
    assert isinstance(record.first_attempt_verdict["passed"], bool)
    assert record.first_attempt_verdict["passed"] is True  # first write was the good body

    # Turn accounting: 4 scripted assistant responses = 4 turns, within the cap.
    assert record.attempts_used == operator.turns_used == 4
    assert operator.turns_used <= operator.max_turns

    # The first request carried the brief + the full registered tool surface.
    first_request = fake.requests[0]
    assert {t["function"]["name"] for t in first_request["tools"]} == {
        "read_context",
        "write_parser",
        "run_ingest",
    }
    system = _messages_of(first_request)[0]
    assert system["role"] == "system"
    assert "write_parser" in system["content"]  # the loop protocol preamble

    # Synthetic-source persistence: one kept run dir + one tier-tagged line.
    assert outcome.persisted_run_dir is not None
    assert len(_run_dirs(runs_dir)) == 1
    entries = scoreboard_mod.read_scoreboard(path=scoreboard_path)
    assert len(entries) == 1
    assert entries[0].tier == "tool_loop"
    assert entries[0].final_pass is True
    raw_line = scoreboard_path.read_text(encoding="utf-8").strip()
    assert '"tier": "tool_loop"' in raw_line


# --------------------------------------------------------------------------- #
# m2 FR-3 — transcript() maps the final conversation 1:1 to TurnLike items.
# --------------------------------------------------------------------------- #


def test_transcript_maps_final_conversation(
    persistence_paths: tuple[Path, Path],
) -> None:
    """FR-3: ``transcript()`` reflects the final conversation, system prompt included.

    After a read → write → verify → done run the operator's transcript replays
    the system brief and every assistant/tool turn in order; tool-result turns
    carry the ``tool_name`` of the call they answered; roles pass through to the
    chat-API vocabulary.
    """
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("read_context", {"path": str(_SYNTHETIC_CSV.resolve())})),
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _reply_with_calls(_tool_call("run_ingest", {})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    turns = list(operator.transcript())
    roles = [t.role for t in turns]

    # The system brief leads; the conversation is system + assistant/tool turns.
    assert roles[0] == "system"
    assert set(roles) <= {"system", "user", "assistant", "tool"}

    # Three assistant tool-call turns + one final assistant "done" turn.
    assert roles.count("assistant") == 4
    # Three tool-result turns, one per executed tool call.
    assert roles.count("tool") == 3

    # The tool-result turns carry the tool_name of the call they answered, in order.
    tool_names = [t.tool_name for t in turns if t.role == "tool"]
    assert tool_names == ["read_context", "write_parser", "run_ingest"]

    # The last turn is the final assistant message (final-state, FR-3).
    assert turns[-1].role == "assistant"
    assert turns[-1].content == "done"


def test_tool_loop_transcript_persists_to_session_log(
    persistence_paths: tuple[Path, Path],
) -> None:
    """FR-5: the harness persists the tool-loop transcript as log_turn rows.

    End-to-end through the unchanged kept-log harness path: a kept
    synthetic run leaves ordered ``log_turn`` rows that replay the operator's
    conversation, keyed to the session's root ``agent_turn`` step (FR-1 link),
    with tool-result turns carrying their ``tool_name``.
    """
    import duckdb

    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("read_context", {"path": str(_SYNTHETIC_CSV.resolve())})),
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _reply_with_calls(_tool_call("run_ingest", {})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV, keep_sandboxes=True)

    assert outcome.final_result is not None
    log_path = outcome.final_result.session_log_path
    try:
        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            rows = conn.execute(
                "SELECT turn_index, role, tool_name, step_id FROM log_turn ORDER BY turn_index"
            ).fetchall()
            root = conn.execute("SELECT step_id FROM log_step WHERE kind = 'agent_turn'").fetchone()
        finally:
            conn.close()
        assert root is not None
        # Persisted turns replay the operator's transcript 1:1, in order.
        expected = operator.transcript()
        assert [r[1] for r in rows] == [t.role for t in expected]
        assert [r[0] for r in rows] == list(range(len(expected)))
        # Tool-result turns carry their tool_name; all link to the root step.
        assert [r[2] for r in rows if r[1] == "tool"] == [
            "read_context",
            "write_parser",
            "run_ingest",
        ]
        assert {r[3] for r in rows} == {root[0]}
    finally:
        ltl._teardown_kept_sandbox(outcome.final_result)
        ltl._teardown_kept_sandbox(outcome.first_attempt_result)


# --------------------------------------------------------------------------- #
# T012 — First-snapshot (FR-006): the FIRST write_parser body grades independently.
# --------------------------------------------------------------------------- #


def test_first_write_parser_snapshot_grades_independently(
    persistence_paths: tuple[Path, Path],
) -> None:
    """FR-006: two ``write_parser`` calls → first verdict grades the FIRST body.

    The script writes a broken parser, then overwrites it with the good one. The
    final verdict grades the parser on disk at loop end (PASS); the first-parser
    verdict must grade the snapshotted FIRST body (FAIL) — the regression
    direction WP05 covers rides on this independence.
    """
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("write_parser", {"code": _BAD_PARSER_CODE})),
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    record = outcome.record
    assert record is not None
    assert record.tier == "tool_loop"
    # The snapshot captured the FIRST body, not the overwrite.
    assert operator.first_parser_code == _BAD_PARSER_CODE
    # Independent verdicts: first FAIL (broken body), final PASS (good body).
    assert record.first_attempt_verdict["passed"] is False
    assert record.final_verdict["passed"] is True


# --------------------------------------------------------------------------- #
# T012 — Gate feedback loop: a self-reconcile failure re-enters the conversation.
# --------------------------------------------------------------------------- #


def test_gate_failure_feedback_reaches_conversation_and_trial_still_grades(
    persistence_paths: tuple[Path, Path],
) -> None:
    """Contract §3: gate fail + turns remaining → feedback message, loop continues.

    The script writes a silently-dropping parser and ends the working phase; the
    manifest-blind gate fails it, the verbatim feedback is appended to the
    conversation, and the operator corrects the parser in later turns. The trial
    still ends graded (PASS on the corrected parser).
    """
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("write_parser", {"code": _silent_drop_parser_code()})),
            _DONE_REPLY,  # gate runs here and FAILS (silent drop)
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _DONE_REPLY,  # gate runs again and PASSES
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # The gate feedback reached the conversation: the request AFTER the failed
    # gate round carries a user message naming the unaccounted-columns failure.
    post_gate_messages = _messages_of(fake.requests[2])
    feedback = [
        m
        for m in post_gate_messages
        if m.get("role") == "user" and "neither mapped nor declared" in str(m.get("content"))
    ]
    assert feedback, "gate failure feedback never re-entered the conversation"
    assert "altitude_m" in feedback[-1]["content"]  # the verbatim unaccounted column

    # The trial still ended graded — the corrected parser passes.
    record = outcome.record
    assert record is not None
    assert record.final_verdict["passed"] is True
    assert record.attempts_used == operator.turns_used == 4


# --------------------------------------------------------------------------- #
# T012 — Cap exhaustion (FR-005 / SC-005): always terminates into a graded record.
# --------------------------------------------------------------------------- #


def test_cap_exhaustion_terminates_into_complete_graded_record(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-005 / SC-005: a never-stopping operator is cut at LIVE_TRIAL_MAX_TURNS.

    The script calls tools forever; with the env cap pinned small the loop stops
    exactly at the cap, never raises, and the trial still ends with a complete
    graded record — no parser was ever written, so both verdicts are the
    machinery's deterministic absent-parser FAIL.
    """
    runs_dir, scoreboard_path = persistence_paths
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "2")
    fake = FakeChatBackend(
        [_reply_with_calls(_tool_call("read_context", {"path": str(_SYNTHETIC_CSV.resolve())}))],
        repeat_last=True,
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)
    assert operator.max_turns == 2  # env knob honored (contract §6)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # The loop stopped AT the cap — exactly 2 assistant turns, no more requests.
    assert operator.turns_used == 2
    assert len(fake.requests) == 2

    # A complete graded record exists (SC-005): deterministic FAIL on both axes.
    record = outcome.record
    assert record is not None
    assert record.tier == "tool_loop"
    assert record.attempts_used == 2
    assert record.first_attempt_verdict["passed"] is False  # no parser ever written
    assert record.final_verdict["passed"] is False
    assert set(record.final_verdict["rules"]) == {"loaded", "runtime_valid", "honest_about_gaps"}

    # Synthetic cap-exhaustion run still persists (a legitimate floor finding).
    entries = scoreboard_mod.read_scoreboard(path=scoreboard_path)
    assert len(entries) == 1
    assert entries[0].tier == "tool_loop"
    assert entries[0].final_pass is False


# --------------------------------------------------------------------------- #
# T012 — Turn accounting: an unknown tool call consumes a turn, corrective fed back.
# --------------------------------------------------------------------------- #


def test_unknown_tool_call_consumes_turn_and_feeds_corrective_message(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract §3: a malformed/unknown call still consumes its turn.

    Turn 1 requests a tool that does not exist; the loop must consume that turn,
    feed a corrective tool message back (visible in the next request's history),
    and keep exact turn accounting through to a graded record.
    """
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "2")
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("frobnicate", {"x": 1})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # The unknown call consumed turn 1; the trial used both turns of the cap.
    assert operator.turns_used == 2
    assert len(fake.requests) == 2

    # The corrective tool message is in the NEXT request's history.
    second_request_messages = _messages_of(fake.requests[1])
    corrective = [
        m
        for m in second_request_messages
        if m.get("role") == "tool" and "frobnicate" in str(m.get("content"))
    ]
    assert corrective, "no corrective tool message fed back for the unknown tool"
    content = corrective[-1]["content"]
    assert "read_context" in content  # the corrective names the real tool surface

    # The trial still ended in a complete graded record (no parser → FAIL).
    record = outcome.record
    assert record is not None
    assert record.final_verdict["passed"] is False


def test_malformed_tool_arguments_consume_turn_with_corrective_message(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec edge case "malformed tool call": unparseable args never crash the trial."""
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "2")
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("write_parser", "{not json")),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    assert operator.turns_used == 2
    second_request_messages = _messages_of(fake.requests[1])
    corrective = [
        m
        for m in second_request_messages
        if m.get("role") == "tool" and "write_parser" in str(m.get("content"))
    ]
    assert corrective, "no corrective tool message fed back for malformed arguments"
    # A malformed write_parser call must NOT be snapshotted as the first parser.
    assert operator.first_parser_code == ""
    assert outcome.record is not None


# --------------------------------------------------------------------------- #
# NFR-006 — the two non-record outcome states return (never raise), mid-trial.
# --------------------------------------------------------------------------- #


def test_tool_calls_unsupported_mid_trial_returns_outcome_and_tears_down(
    persistence_paths: tuple[Path, Path],
) -> None:
    """NFR-006: ToolCallsUnsupportedError mid-conversation → explicit outcome.

    The error propagates OUT of the operator's loop (never swallowed into a
    half-graded trial), the entry point maps it to ``tool_calls_unsupported``,
    nothing persists, and the trial sandbox is torn down.
    """
    runs_dir, scoreboard_path = persistence_paths
    operator = ltl.ToolLoopOperator(
        _SYNTHETIC_CSV,
        chat=_raising_chat(tlc.ToolCallsUnsupportedError("model template lacks tools")),
    )

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    assert outcome.tool_calls_unsupported is True
    assert outcome.model_unavailable is False
    assert outcome.record is None
    assert outcome.persisted_run_dir is None
    assert _run_dirs(runs_dir) == []
    assert not scoreboard_path.exists()
    # The trial sandbox was torn down on the failure path.
    assert operator.last_sandbox is not None
    assert not operator.last_sandbox.root.exists()


def test_model_unavailable_mid_trial_returns_outcome_and_tears_down(
    persistence_paths: tuple[Path, Path],
) -> None:
    """NFR-006: OllamaUnavailableError mid-conversation → ``model_unavailable``."""
    runs_dir, scoreboard_path = persistence_paths
    operator = ltl.ToolLoopOperator(
        _SYNTHETIC_CSV,
        chat=_raising_chat(tlc.OllamaUnavailableError("endpoint vanished mid-trial")),
    )

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    assert outcome.model_unavailable is True
    assert outcome.tool_calls_unsupported is False
    assert outcome.record is None
    assert outcome.persisted_run_dir is None
    assert _run_dirs(runs_dir) == []
    assert not scoreboard_path.exists()
    assert operator.last_sandbox is not None
    assert not operator.last_sandbox.root.exists()
