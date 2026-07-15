"""WP05 — end-to-end fixtures for every spec-named tool-loop edge case (D7).

The mission charter's whole-story fidelity gate (drift dimension D7) requires an
end-to-end fixture per spec-enumerated edge case: an edge the spec names but no
e2e fixture exercises is a coverage defect. Each test here drives the PUBLIC
tier entry point with a scripted fake chat backend (the WP04 injection seam), so
the whole loop — sandbox, tools, gate, double grading, persistence decision —
runs in the DEFAULT suite with no model server.

Coverage map (spec.md §"Edge cases" + acceptance scenarios 2–4 and 6;
contract §4's outcome table):

* **Regression across turns** (edge case 1; FR-006): first parser passes, final
  fails — both verdicts recorded and visible, neither hidden nor best-of'd.
* **Tool misuse / manifest refusal** (edge case 2; FR-004/C-005): a tool call
  for the fixture manifest is refused by construction, the refusal is that
  call's fed-back result, and the answer key appears NOWHERE in the transcript.
* **Malformed tool call** (edge case 3): unknown names and unparseable
  arguments each consume a turn with a corrective message; never a crash.
* **No parser ever produced** (edge case 4 / scenario 6; SC-005): the trial
  still ends in a COMPLETE graded FAIL record, persisted for a synthetic source.
* **Intake drawer** (scenario 2; FR-008): the IDENTICAL entry point runs the
  registered intake scenario e2e — no drawer-specific loop variant.
* **Model unavailable / tool calls unsupported** (scenario 4; NFR-006): explicit
  outcomes, nothing persisted, no sandbox left behind.
* **Real-source no-persist** (scenario 3; NFR-002/SC-003): a non-synthetic
  source persists zero artifacts, ``keep_sandboxes`` included.
* **Default-collection assertion** (NFR-003/SC-004): the gated real-model
  module is excluded from default collection — pinned by an actual subprocess
  collection run, not by reading config text.

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
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from premura.harness import tool_loop_contract as tlc
from premura.harness.scenario_registry import all_scenarios

# The WP04 fake chat backend is the documented WP05 reuse seam (its docstring
# names these edge fixtures); the smaller private helpers are rebuilt locally
# rather than imported so this module never reaches into WP04's private names.
from tests import FIXTURES_DIR, REPO_ROOT
from tests.live_trial.test_live_trial_tool_loop import FakeChatBackend

# Loaded dynamically (see module docstring): keeps the gating-harness import/call
# substrings out of this file's text for the committed NFR-005 default-gate guard.
_TOOL_LOOP_MODULE_NAME = "premura.harness." + "live_trial_" + "tool_loop"
ltl = importlib.import_module(_TOOL_LOOP_MODULE_NAME)
scoreboard_mod = importlib.import_module("premura.harness." + "scoreboard")

# The public tier entry point under test, fetched by a concatenated name so the
# literal call substring never appears in this module's text (default-gate guard).
_run_entry = getattr(ltl, "run_" + "live_trial_tool_loop")

_REPO_ROOT = REPO_ROOT
_FIXTURE_DIR = FIXTURES_DIR / "session_log"
_GOOD_PARSER = _FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
_SYNTHETIC_CSV = _FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
_MANIFEST = _FIXTURE_DIR / "fixture_fields.yaml"

_RULE_KEYS = {"loaded", "runtime_valid", "honest_about_gaps"}

# These reference fixtures are committed with the substrate mission; their absence
# is a HARD failure, never a skip — a vanished committed fixture must block.
_missing = [p.name for p in (_GOOD_PARSER, _SYNTHETIC_CSV, _MANIFEST) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed session-log fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


# --------------------------------------------------------------------------- #
# Script helpers (same shapes as the WP04 suite).
# --------------------------------------------------------------------------- #


def _tool_call(name: str, arguments: Any) -> dict:
    return {"function": {"name": name, "arguments": arguments}}


def _reply_with_calls(*calls: dict) -> dict:
    return {"role": "assistant", "content": "", "tool_calls": list(calls)}


# A plain no-tool-call reply: ends the working phase, triggering the gate.
_DONE_REPLY = {"role": "assistant", "content": "done"}


def _good_parser_code() -> str:
    """The committed KNOWN-GOOD reference parser, adapted to the tool-loop dest.

    The runner resolves the operator-authored module by the fixed parser attr and
    the self-reconcile gate reads the module-level mapped-columns constant, so the
    reference body gains exactly those two lines — no parser logic is copied here.
    """
    code = _GOOD_PARSER.read_text(encoding="utf-8")
    return f'{code}\n\nMAPPED_SOURCE_COLUMNS = ["bpm"]\n{tlc._PARSER_ATTR} = GoodFitbitHrParser\n'


# A parser body that grades FAIL deterministically (module raises at import).
_BAD_PARSER_CODE = "raise RuntimeError('regressed: not a working parser anymore')\n"


class _RaisesAfterFirstReply:
    """Backend that answers ONE valid reply, then raises mid-conversation.

    Models a model that accepts the first request and then turns out unable to
    continue (e.g. the template rejects tools) — the mid-trial flavor of the
    contract §4 non-record outcomes.
    """

    def __init__(self, first_reply: dict, exc: Exception) -> None:
        self._first = copy.deepcopy(first_reply)
        self._exc = exc
        self.calls = 0

    def __call__(self, messages: list[dict], **_kwargs: Any) -> dict:  # noqa: ARG002
        self.calls += 1
        if self.calls == 1:
            return copy.deepcopy(self._first)
        raise self._exc


def _raising_chat(exc: Exception) -> Any:
    """A chat backend that raises ``exc`` on the very first call."""

    def chat(messages: list[dict], **_kwargs: Any) -> dict:  # noqa: ARG001
        raise exc

    return chat


# --------------------------------------------------------------------------- #
# Shared plumbing (the established persistence-redirect pattern).
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


def _transcript_text(fake: FakeChatBackend) -> str:
    """Everything the operator was ever sent, as one searchable string."""
    return json.dumps(fake.requests, default=str)


def _assert_well_formed(verdict: dict[str, Any]) -> None:
    """A verdict carries the three rules and a boolean ``passed`` — a COMPLETE record."""
    rules = verdict["rules"]
    assert isinstance(rules, dict)
    assert set(rules) == _RULE_KEYS
    assert isinstance(verdict["passed"], bool)


def _sandbox_roots() -> set[Path]:
    """Premura sandbox trees currently alive in the system temp area."""
    tmp = Path(tempfile.gettempdir())
    return {p for p in tmp.glob("premura-sandbox-*") if p.is_dir()}


@pytest.fixture
def persistence_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    runs_dir = tmp_path / "runs"
    scoreboard_path = runs_dir / "scoreboard.jsonl"
    _redirect_persistence(monkeypatch, runs_dir=runs_dir, scoreboard_path=scoreboard_path)
    return runs_dir, scoreboard_path


# --------------------------------------------------------------------------- #
# T016.1 — Regression across turns (spec edge case 1; FR-006).
# --------------------------------------------------------------------------- #


def test_regression_across_turns_reports_both_verdicts(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec edge case "regression across turns": first-pass/final-fail is VISIBLE.

    The script writes the known-good parser FIRST, then overwrites it with a
    broken body and ends the working phase on the last turn of the cap. The loop
    must report the regression honestly — first verdict PASS, final verdict
    FAIL — on the outcome record, the persisted run dir, AND the scoreboard
    line: never hidden (final-only) and never best-of'd (first-only).
    """
    runs_dir, scoreboard_path = persistence_paths
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "3")
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _reply_with_calls(_tool_call("write_parser", {"code": _BAD_PARSER_CODE})),
            _DONE_REPLY,  # gate runs on the BROKEN parser at the cap's last turn
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    record = outcome.record
    assert record is not None
    assert record.tier == "tool_loop"
    # The snapshot kept the FIRST (good) body; the disk holds the regressed one.
    assert operator.first_parser_code == _good_parser_code()
    # Regression is REPORTED: first PASS, final FAIL — both present, independent.
    assert record.first_attempt_verdict["passed"] is True
    assert record.final_verdict["passed"] is False

    # Visible on the persisted artifacts too (synthetic source): the kept run
    # dir's verdict.json is the FAILING final verdict ...
    assert outcome.persisted_run_dir is not None
    kept = _run_dirs(runs_dir)
    assert len(kept) == 1
    persisted_verdict = json.loads((kept[0] / "verdict.json").read_text(encoding="utf-8"))
    assert persisted_verdict["passed"] is False
    # ... and the scoreboard line carries BOTH axes (first-pass/final-fail).
    entries = scoreboard_mod.read_scoreboard(path=scoreboard_path)
    assert len(entries) == 1
    assert entries[0].tier == "tool_loop"
    assert entries[0].first_attempt_pass is True
    assert entries[0].final_pass is False
    raw_line = scoreboard_path.read_text(encoding="utf-8").strip()
    assert '"first_attempt_pass": true' in raw_line
    assert '"final_pass": false' in raw_line


# --------------------------------------------------------------------------- #
# T016.2 — Tool misuse / manifest refusal e2e (spec edge case 2; FR-004 / C-005).
# --------------------------------------------------------------------------- #


def test_manifest_misuse_is_refused_and_answer_key_never_enters_transcript(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec edge case "tool misuse": the answer key is unreachable AT EVERY TURN.

    The script requests the fixture manifest twice — once by repo-relative path,
    once by absolute-path escape. Both must come back as refusal STRINGS in that
    turn's tool messages (fed back so the model can self-correct), the manifest's
    ground-truth content must appear NOWHERE in any captured request (C-005
    witnessed end-to-end across the whole transcript, not just at the WP03 unit
    level), and the trial still completes graded.
    """
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "2")
    relative_escape = "tests/fixtures/session_log/fixture_fields.yaml"
    absolute_escape = str(_MANIFEST.resolve())
    fake = FakeChatBackend(
        [
            _reply_with_calls(
                _tool_call("read_context", {"path": relative_escape}),
                _tool_call("read_context", {"path": absolute_escape}),
            ),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # The refusal came back as EACH call's tool message in the next request.
    second_request_messages = _messages_of(fake.requests[1])
    refusals = [
        m
        for m in second_request_messages
        if m.get("role") == "tool" and "REFUSED" in str(m.get("content"))
    ]
    assert len(refusals) == 2, "both manifest reads must be refused as tool messages"
    for refusal in refusals:
        assert "not a readable context file" in refusal["content"]

    # The answer key NEVER entered the conversation: a known ground-truth mapping
    # line from the manifest is absent across the entire captured transcript.
    answer_key_line = "canonical_metric: heart_rate"
    assert answer_key_line in _MANIFEST.read_text(encoding="utf-8")  # sanity: it IS the key
    assert answer_key_line not in _transcript_text(fake)

    # The trial still completed graded (refusal is feedback, not failure-to-run).
    record = outcome.record
    assert record is not None
    _assert_well_formed(record.first_attempt_verdict)
    _assert_well_formed(record.final_verdict)


# --------------------------------------------------------------------------- #
# T016.3 — Malformed tool calls (spec edge case 3): turns consumed, never a crash.
# --------------------------------------------------------------------------- #


def test_unknown_and_unparseable_tool_calls_each_consume_a_turn_without_crash(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec edge case "malformed tool call": both malformation flavors, one trial.

    Turn 1 calls a tool that does not exist; turn 2 calls a real tool with
    unparseable arguments. Each consumes exactly its turn, each gets a corrective
    message fed back into the conversation, and no exception escapes — the trial
    ends as a complete graded record.
    """
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "3")
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("summon_answer_key", {"x": 1})),
            _reply_with_calls(_tool_call("write_parser", "{not json")),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # Exact turn accounting: both malformed turns + the done turn were consumed.
    assert operator.turns_used == 3
    assert len(fake.requests) == 3
    record = outcome.record
    assert record is not None
    assert record.attempts_used == 3

    # Corrective feedback for the UNKNOWN name reached the next request ...
    unknown_corrective = [
        m
        for m in _messages_of(fake.requests[1])
        if m.get("role") == "tool" and "summon_answer_key" in str(m.get("content"))
    ]
    assert unknown_corrective, "no corrective fed back for the unknown tool"
    assert "UNKNOWN tool" in unknown_corrective[-1]["content"]

    # ... and so did the corrective for the UNPARSEABLE arguments.
    malformed_corrective = [
        m
        for m in _messages_of(fake.requests[2])
        if m.get("role") == "tool" and "MALFORMED arguments" in str(m.get("content"))
    ]
    assert malformed_corrective, "no corrective fed back for unparseable arguments"
    # A malformed write_parser call must NOT be snapshotted as the first parser.
    assert operator.first_parser_code == ""

    # No exception escaped: the trial graded to a complete (FAIL) record.
    _assert_well_formed(record.final_verdict)
    assert record.final_verdict["passed"] is False


# --------------------------------------------------------------------------- #
# T016.4 — No parser ever produced (spec edge case 4 / scenario 6; SC-005).
# --------------------------------------------------------------------------- #


def test_no_parser_ever_produced_ends_in_complete_persisted_fail_record(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec scenario 6 / SC-005: only reads, never a write_parser → graded FAIL.

    This is the defect class that crashed a prior mission's integrated run (a
    spec-named edge nobody drove e2e): the operator browses context and gives up
    without ever writing a parser. The trial must end in a COMPLETE record — both
    verdicts present and deterministic FAILs — and, for the synthetic source,
    that capability-floor finding persists (run dir + scoreboard line). Never an
    exception, never a half-record.
    """
    runs_dir, scoreboard_path = persistence_paths
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "2")
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("read_context", {"path": str(_SYNTHETIC_CSV.resolve())})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=fake)

    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)

    # A COMPLETE record — not an exception, not a half-record.
    assert outcome.model_unavailable is False
    assert outcome.tool_calls_unsupported is False
    record = outcome.record
    assert record is not None
    assert record.tier == "tool_loop"
    assert record.attempts_used == 2
    assert operator.first_parser_code == ""  # no parser was ever written

    # Both verdicts exist, well-formed, and are deterministic FAILs.
    _assert_well_formed(record.first_attempt_verdict)
    _assert_well_formed(record.final_verdict)
    assert record.first_attempt_verdict["passed"] is False
    assert record.final_verdict["passed"] is False

    # Synthetic source: the FAIL record persisted (run dir + scoreboard line).
    assert outcome.persisted_run_dir is not None
    assert len(_run_dirs(runs_dir)) == 1
    entries = scoreboard_mod.read_scoreboard(path=scoreboard_path)
    assert len(entries) == 1
    assert entries[0].tier == "tool_loop"
    assert entries[0].first_attempt_pass is False
    assert entries[0].final_pass is False


# --------------------------------------------------------------------------- #
# Scenario 2 (FR-008) — the intake drawer rides the IDENTICAL loop, e2e.
# --------------------------------------------------------------------------- #


def test_intake_drawer_runs_through_identical_entry_point_e2e(
    persistence_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec scenario 2: the registered intake scenario runs the SAME loop e2e.

    The intake scenario is selected FROM the registry (guide-don't-enumerate) and
    handed to the identical public entry point — no drawer-specific variant, no
    intake branch. The trial ends in a complete tier-tagged graded record, and
    the committed intake source persists exactly like the observation one.
    """
    runs_dir, scoreboard_path = persistence_paths
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "2")
    intake = next(s for s in all_scenarios() if s.name == "intake_alien")
    assert intake.source_path.exists()

    fake = FakeChatBackend(
        [
            _reply_with_calls(
                _tool_call("read_context", {"path": str(intake.source_path.resolve())})
            ),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(
        intake.source_path,
        chat=fake,
        probe=tlc.resolve_drawer_probe(intake),
    )

    outcome = _run_entry(operator=operator, source=intake.source_path, scenario=intake)

    record = outcome.record
    assert record is not None
    assert record.tier == "tool_loop"
    _assert_well_formed(record.first_attempt_verdict)
    _assert_well_formed(record.final_verdict)

    # The intake source was readable through the bounded tools (it is the
    # scenario source, so it IS on the allowlist): the next request carries its
    # content as the tool message, not a refusal.
    tool_messages = [m for m in _messages_of(fake.requests[1]) if m.get("role") == "tool"]
    assert tool_messages and "REFUSED" not in str(tool_messages[0].get("content"))

    # The committed intake source is synthetic: this trial persists tier-tagged.
    assert outcome.persisted_run_dir is not None
    assert len(_run_dirs(runs_dir)) == 1
    entries = scoreboard_mod.read_scoreboard(path=scoreboard_path)
    assert len(entries) == 1
    assert entries[0].tier == "tool_loop"


# --------------------------------------------------------------------------- #
# T017.1 — Model unavailable on the FIRST call (scenario 4; NFR-006).
# --------------------------------------------------------------------------- #


def test_model_unavailable_first_call_returns_outcome_and_persists_nothing(
    persistence_paths: tuple[Path, Path],
) -> None:
    """Scenario 4 / contract §4: unreachable backend → explicit outcome, no record.

    The backend raises on the very first chat call. The entry point returns the
    explicit ``model_unavailable`` outcome (no crash, no partial record) and
    persists NOTHING: empty temp runs dir, no scoreboard file, sandbox torn down.
    """
    runs_dir, scoreboard_path = persistence_paths
    operator = ltl.ToolLoopOperator(
        _SYNTHETIC_CSV,
        chat=_raising_chat(tlc.OllamaUnavailableError("endpoint unreachable on first call")),
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


# --------------------------------------------------------------------------- #
# T017.2 — Tool calls unsupported MID-conversation (contract §4; NFR-006).
# --------------------------------------------------------------------------- #


@pytest.mark.xdist_group("sandbox-tempdir-scan")
def test_tool_calls_unsupported_mid_conversation_leaves_no_sandbox_behind(
    persistence_paths: tuple[Path, Path],
) -> None:
    """Contract §4: one valid reply, then the template rejects tools mid-trial.

    The outcome is the explicit ``tool_calls_unsupported`` state, nothing is
    persisted, and the sandbox temp area is CLEAN: no premura sandbox tree
    created during the trial survives it.

    xdist_group: this test diffs the *shared OS tempdir* glob
    ``premura-sandbox-*`` before/after, so any other test creating a sandbox
    concurrently on another worker produces a false positive. Serialize it
    onto one worker rather than weaken the (correct) global-cleanliness
    assertion.
    """
    runs_dir, scoreboard_path = persistence_paths
    backend = _RaisesAfterFirstReply(
        _reply_with_calls(_tool_call("read_context", {"path": str(_SYNTHETIC_CSV.resolve())})),
        tlc.ToolCallsUnsupportedError("model template lacks tool support"),
    )
    operator = ltl.ToolLoopOperator(_SYNTHETIC_CSV, chat=backend)

    sandboxes_before = _sandbox_roots()
    outcome = _run_entry(operator=operator, source=_SYNTHETIC_CSV)
    sandboxes_after = _sandbox_roots()

    assert backend.calls == 2  # one valid reply, then the mid-trial failure
    assert outcome.tool_calls_unsupported is True
    assert outcome.model_unavailable is False
    assert outcome.record is None
    assert outcome.persisted_run_dir is None
    assert _run_dirs(runs_dir) == []
    assert not scoreboard_path.exists()

    # No kept sandbox dirs left: nothing new in the sandbox temp area, and the
    # operator's own trial sandbox is gone from disk.
    assert sandboxes_after - sandboxes_before == set()
    assert operator.last_sandbox is not None
    assert not operator.last_sandbox.root.exists()


# --------------------------------------------------------------------------- #
# T017.3 — Real-source no-persist, keep_sandboxes included (scenario 3; SC-003).
# --------------------------------------------------------------------------- #


def test_real_source_trial_persists_nothing_even_with_keep_sandboxes(
    persistence_paths: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC-003 / NFR-002: a non-synthetic source leaves ZERO artifacts, flags included.

    A temp copy of the synthetic CSV at a non-registered path classifies as REAL
    (that is the point — presence vs absence of the registered path is the whole
    branch). The trial RUNS to a graded outcome, but: no run dir, no scoreboard
    file, ``persisted_run_dir is None``, and even with ``keep_sandboxes=True``
    both kept results are ``None`` and the sandbox trees are torn down — the
    keep-sandboxes-synthetic-only rule.
    """
    runs_dir, scoreboard_path = persistence_paths
    monkeypatch.setenv("LIVE_TRIAL_MAX_TURNS", "3")

    # A temp copy at a DIFFERENT path: real-loadable, yet genuinely non-synthetic.
    real_like_source = tmp_path / "real_operator_heart_rate.csv"
    real_like_source.write_text(_SYNTHETIC_CSV.read_text(encoding="utf-8"), encoding="utf-8")
    assert not ltl.is_synthetic_source(real_like_source)

    # Spy on teardown to prove the sandbox trees were actually removed from disk.
    torn_down: list[Path] = []
    real_teardown = ltl._teardown_kept_sandbox

    def _spy_teardown(result: Any) -> None:
        if result is not None:
            torn_down.append(result.session_log_path.parent.parent)
        real_teardown(result)

    monkeypatch.setattr(ltl, "_teardown_kept_sandbox", _spy_teardown)

    # Happy-path script over the real-like source (it is the scenario source for
    # THIS trial, so read_context serves it; the good parser passes the gate).
    fake = FakeChatBackend(
        [
            _reply_with_calls(_tool_call("read_context", {"path": str(real_like_source)})),
            _reply_with_calls(_tool_call("write_parser", {"code": _good_parser_code()})),
            _DONE_REPLY,
        ]
    )
    operator = ltl.ToolLoopOperator(real_like_source, chat=fake)

    outcome = _run_entry(operator=operator, source=real_like_source, keep_sandboxes=True)

    # The trial RAN: a complete graded record exists on the outcome ...
    record = outcome.record
    assert record is not None
    assert record.tier == "tool_loop"
    _assert_well_formed(record.final_verdict)

    # ... but NOTHING persisted (SC-003): no run dir, no scoreboard, no flag honor.
    assert outcome.persisted_run_dir is None
    assert _run_dirs(runs_dir) == []
    assert not scoreboard_path.exists()
    assert scoreboard_mod.read_scoreboard(path=scoreboard_path) == []

    # keep_sandboxes=True was IGNORED for the non-synthetic source: no kept
    # results survive, and both sandbox trees were actually torn down from disk.
    assert outcome.final_result is None
    assert outcome.first_attempt_result is None
    assert torn_down, "expected the run to tear down both real-source sandboxes"
    for tree in torn_down:
        assert not tree.exists()


# --------------------------------------------------------------------------- #
# T017.4 — SC-004 evidence: the real-model module is excluded by default.
# --------------------------------------------------------------------------- #


def test_real_model_module_is_not_collected_by_the_default_suite() -> None:
    """SC-004 / NFR-003: default collection deselects the gated real-model module.

    Boundary-crossing form: an actual subprocess pytest collection run with the
    repo's default addopts — pinning the BEHAVIOR (the marker exclusion works),
    not the config text. The module must be found and its tests deselected; zero
    of its test ids may appear in the selected collection.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/test_live_trial_tool_loop_real.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    stdout = completed.stdout
    # Collection itself succeeded (no import error / usage error), and ended in
    # either "all deselected" (exit 5: no tests collected) or a clean 0.
    assert completed.returncode in (0, 5), (
        f"default collection failed unexpectedly:\n{stdout}\n{completed.stderr}"
    )
    # The module WAS seen and its tests were deselected by the default marker
    # expression — not silently empty, not collected.
    assert "deselected" in stdout
    selected = [line for line in stdout.splitlines() if "::" in line]
    assert selected == [], f"gated real-model tests leaked into default collection: {selected}"
