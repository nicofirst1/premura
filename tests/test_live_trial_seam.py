"""WP07 — live-trial seam (FR-030, FR-031; OWNS NFR-005).

Black-box tests over the live-trial seam. A FAKE operator
(:class:`~premura.harness.live_trial.ReferenceParserOperator`) edits the sandbox
to install a committed reference parser — exactly the edit the deferred real
cheap-model operator would make — over the SYNTHETIC fixture (never the real
dump, C-003). The harness reuses the SAME lower machinery as the repeatable check
(WP03 sandbox + runner, WP01 store as the sole log writer, WP05 grader) and is
still the sole log writer; the only difference is the operator edit.

Decisive artifacts:

* ``test_seam_drives_to_verdict_with_fake_operator`` (FR-030/FR-031) — the seam
  drives end-to-end to a grader verdict; the harness-written session records
  ``run_kind="live_trial"`` with the fake ``operator_model`` / ``driver_model``,
  and the harness wrote the named ``tool_call`` steps.
* ``test_live_trial_not_in_default_gate`` (NFR-005) — the live trial is in NO
  default gate: ``run_live_trial`` is referenced ONLY by this seam test, no
  committed test reads the real ``source_dir``, and with the default dump absent
  the default suite is unaffected (no live trial runs at import/collection).

The whole suite runs OFFLINE from the committed fixture only; the real-dump
live trial is the local follow-up, never part of the default suite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import jsonschema

from premura.config import REPO_ROOT
from premura.harness import live_trial
from premura.harness.live_trial import (
    LiveTrialConfig,
    ReferenceParserOperator,
    ScriptedDriver,
)
from premura.harness.sandbox import install_parser

if TYPE_CHECKING:
    from premura.harness.sandbox import Sandbox

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "session_log"
GOOD_PARSER = FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
RAISING_PARSER = FIXTURE_DIR / "parsers" / "raising_fitbit_hr.py"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
VERDICT_SCHEMA = (
    REPO_ROOT
    / "kitty-specs"
    / "session-log-substrate-01KT45S1"
    / "contracts"
    / "grader-verdict.schema.json"
)

# These reference fixtures are committed with the mission (WP04); their absence is
# a HARD failure, never a skip — a vanished committed fixture must block the gate,
# not pass green.
_missing = [p.name for p in (GOOD_PARSER, SYNTHETIC_CSV) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed session-log fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


def _read_session(session_log_path: Path) -> tuple[str, str, str]:
    """Read (run_kind, operator_model, driver_model) for the single logged session.

    Opens the harness-written log read-only — the harness was the sole writer.
    """
    conn = duckdb.connect(str(session_log_path), read_only=True)
    try:
        row = conn.execute(
            "SELECT run_kind, operator_model, driver_model FROM log_session"
        ).fetchone()
        assert row is not None
        return row[0], row[1], row[2]
    finally:
        conn.close()


def _read_steps(session_log_path: Path) -> list[tuple[str, str | None, str]]:
    conn = duckdb.connect(str(session_log_path), read_only=True)
    try:
        return conn.execute(
            "SELECT kind, tool_name, result_status FROM log_step ORDER BY started_at"
        ).fetchall()
    finally:
        conn.close()


def _read_live_trial_attempts(session_log_path: Path) -> list[tuple[int, bool, str | None]]:
    conn = duckdb.connect(str(session_log_path), read_only=True)
    try:
        return conn.execute(
            """
            SELECT attempt_index, self_reconciliation_passed, parser_error
            FROM log_live_trial_attempt
            ORDER BY attempt_index
            """
        ).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# T027 — the fake-operator seam drives end-to-end to a verdict (FR-030/FR-031).
# --------------------------------------------------------------------------- #


def test_seam_drives_to_verdict_with_fake_operator() -> None:
    """Fake operator edits the sandbox → seam reaches a PASS verdict (FR-030).

    Uses the synthetic fixture (NOT the real dump). The returned verdict is the
    SAME grader artifact the repeatable check produces, validated against the
    cross-WP schema (no ids/timestamps).
    """
    operator = ReferenceParserOperator(parser_src=GOOD_PARSER)
    driver = ScriptedDriver()
    config = LiveTrialConfig()  # default source_dir is never read here

    verdict = live_trial.run_live_trial(
        config,
        driver=driver,
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )

    assert verdict["passed"] is True
    rules = verdict["rules"]
    assert rules["loaded"]["passed"] is True
    assert rules["runtime_valid"]["passed"] is True
    assert rules["honest_about_gaps"]["passed"] is True
    jsonschema.validate(verdict, json.loads(VERDICT_SCHEMA.read_text(encoding="utf-8")))


def test_session_records_live_trial_identity() -> None:
    """FR-031: the harness records run_kind=live_trial + the fake model ids.

    ``run_live_trial_with_log`` keeps the sandbox so we can read the
    harness-written session row, then tears it down (NFR-004).
    """
    operator = ReferenceParserOperator(parser_src=GOOD_PARSER)
    driver = ScriptedDriver()

    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=driver,
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        run_kind, operator_model, driver_model = _read_session(log_path)
        # run_kind is the DISTINCT live_trial kind, not repeatable_check.
        assert run_kind == "live_trial"
        # The session-identity fields carry the fake model ids (capability tiers).
        assert operator_model == operator.model_id == "fake-operator:reference-parser"
        assert driver_model == driver.model_id == "fake-driver:scripted"
        assert run_kind != "repeatable_check"

        # The grader verdict came back through the same machinery.
        assert result.verdict["passed"] is True
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


def test_seam_reuses_harness_machinery_operator_edits_sandbox() -> None:
    """The seam reuses WP06's machinery: operator edits, harness is sole log writer.

    The operator EDITS the sandbox tree (installs a parser); the HARNESS wrote the
    named ``agent_turn`` + ``tool_call`` steps (the operator never touched the log).
    The ``edit_file`` step witnesses the operator-edit seam; ``ingest_run`` is the
    same verdict-bearing runner step the repeatable check uses.
    """
    operator = ReferenceParserOperator(parser_src=GOOD_PARSER)
    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        steps = _read_steps(log_path)
        kinds = [k for (k, _t, _s) in steps]
        assert kinds.count("agent_turn") == 1

        tool_names = {t for (k, t, _s) in steps if k == "tool_call"}
        # The operator-edit seam (edit_file) + the shared runner step (ingest_run).
        assert {"edit_file", "ingest_run"} <= tool_names

        # The harness is the sole writer: there is exactly ONE session-log file and
        # it carries the harness's steps (the operator/runner wrote no log).
        data_dir = log_path.parent
        log_files = [p for p in data_dir.iterdir() if p.name == log_path.name]
        assert log_files == [log_path]

        # The ingest_run step has the grader-fed provenance row (FR-065): contract_pass
        # equals the verdict's runtime_valid — proving the same grader machinery.
        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            ingest_step = conn.execute(
                "SELECT step_id FROM log_step WHERE tool_name = 'ingest_run'"
            ).fetchone()
            assert ingest_step is not None
            prov = conn.execute(
                "SELECT contract_pass FROM log_ingest_provenance WHERE step_id = ?",
                [ingest_step[0]],
            ).fetchone()
            assert prov is not None
            assert prov[0] == result.verdict["rules"]["runtime_valid"]["passed"]
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# DRIVE-1 / FR-080 — a raising operator parser yields a CAPTURED, GRADED FAIL.
# --------------------------------------------------------------------------- #


def test_raising_operator_yields_captured_failed_run() -> None:
    """Operator installs a parser that raises → captured, graded FAIL (FR-080).

    Same edge case as the repeatable check, exercised through the live-trial seam
    (run_kind=live_trial): the operator's parser raises before any warehouse file is
    created, yet the seam RETURNS a deterministic FAIL with the ``ingest_run`` step
    recorded as ``error``, a provenance row, and a finished session — never a crash.
    """
    operator = ReferenceParserOperator(parser_src=RAISING_PARSER)
    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="RaisingFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        verdict = result.verdict
        assert verdict["passed"] is False
        assert verdict["rules"]["loaded"]["passed"] is False
        assert verdict["rules"]["loaded"]["warehouse_rows"] == 0
        assert verdict["rules"]["runtime_valid"]["passed"] is False

        # The session is the DISTINCT live_trial kind and was finished, not aborted.
        run_kind, _operator_model, _driver_model = _read_session(log_path)
        assert run_kind == "live_trial"

        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            ingest_step = conn.execute(
                "SELECT step_id, result_status FROM log_step WHERE tool_name = 'ingest_run'"
            ).fetchone()
            assert ingest_step is not None
            step_id, status = ingest_step
            assert status == "error"

            prov = conn.execute(
                "SELECT contract_pass FROM log_ingest_provenance WHERE step_id = ?",
                [step_id],
            ).fetchone()
            assert prov is not None
            assert prov[0] is False

            finished = conn.execute("SELECT finished_at FROM log_session").fetchone()
            assert finished is not None
            assert finished[0] is not None
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# T028 — NFR-005: the live trial is wired into NO default gate / never blocks.
# --------------------------------------------------------------------------- #


def test_live_trial_not_in_default_gate() -> None:
    """NFR-005: the live trial is in NO default gate and can never block a change.

    Made checkable three ways:

    1. The default-collected test suite references ``run_live_trial`` ONLY from this
       seam test module — no other default test invokes it (so the only exercise is
       over the synthetic fixture, never as a gating step elsewhere).
    2. NO committed test reads the real ``source_dir`` (default
       ``~/Downloads/MyFitbitData``) — the real dump is local-only (C-003).
    3. With the configured real dump absent, importing/collecting the default suite
       is unaffected: nothing runs a live trial at import/collection time, so a
       missing dump cannot fail the gate.
    """
    tests_dir = Path(__file__).parent
    this_module = Path(__file__).name

    # (1) The live-trial HARNESS (the run_live_trial function / the live_trial module)
    #     is referenced by NO default test module except this seam test. We match the
    #     harness call/import, NOT the bare "live_trial" run_kind string literal — that
    #     vocabulary value legitimately appears in the WP01 store tests and is not the
    #     gating harness path.
    harness_markers = ("run_live_trial", "harness.live_trial", "harness import live_trial")
    offenders: list[str] = []
    for test_file in tests_dir.rglob("test_*.py"):
        if test_file.name == this_module:
            continue
        text = test_file.read_text(encoding="utf-8")
        if any(marker in text for marker in harness_markers):
            offenders.append(str(test_file.relative_to(tests_dir)))
    assert offenders == [], f"live trial harness leaked into default gate tests: {offenders}"

    # (2) NO committed test reads the real source_dir / the real Fitbit dump path.
    #     This seam module mentions the path only in explanatory prose (the path it
    #     REFUSES to read), so it is excluded; every other test must not name it.
    real_dump_markers = ("MyFitbitData", "~/Downloads")
    for test_file in tests_dir.rglob("test_*.py"):
        if test_file.name == this_module:
            continue
        text = test_file.read_text(encoding="utf-8")
        for marker in real_dump_markers:
            assert marker not in text, (
                f"{test_file.name} references the real dump path {marker!r} (C-003 / NFR-005)"
            )

    # (3) With the configured real dump absent, the default suite is unaffected: the
    #     module imported and collected without running any live trial, and the
    #     default config points at a path we never read in any committed test.
    default_source = LiveTrialConfig().source_dir
    assert default_source.name == "MyFitbitData"
    # We never assert the real dump exists, and reaching here proves collection did
    # not depend on it: importing this module ran no live trial.


def test_real_model_wiring_is_closed_followup() -> None:
    """FR-013: the named follow-up is closed; the seam exports working factories.

    Bare calls no longer behave like placeholder probes. They return real operator /
    driver objects without reaching a model server during construction.
    """
    operator = live_trial.real_model_operator()
    driver = live_trial.real_model_driver()

    assert isinstance(operator, live_trial.Operator)
    assert isinstance(driver, live_trial.Driver)
    assert isinstance(operator.model_id, str) and operator.model_id
    assert isinstance(driver.model_id, str) and driver.model_id

    # The module docstring documents the follow-up as closed, not deferred.
    doc = live_trial.__doc__ or ""
    assert "closed" in doc.lower()

    # No frontier/cloud model client is imported by the seam itself.
    src = Path(live_trial.__file__).read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert forbidden not in src


def test_live_trial_attempt_log_starts_empty_for_fake_operator() -> None:
    """Non-Ollama seam runs do not invent per-attempt rows the operator never produced."""
    operator = ReferenceParserOperator(parser_src=GOOD_PARSER)
    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        assert _read_live_trial_attempts(log_path) == []
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Conversation-turn capture (m2 FR-2 / FR-5) — the transcript seam + harness
# persistence. An operator that exposes ``transcript()`` after ``operate()`` gets
# its conversation persisted as ordered ``log_turn`` rows by the harness (the SOLE
# log writer, FR-021 / NFR-1); the capability is detected STRUCTURALLY (no registry
# of tiers). Operators without it behave exactly as before. Capture failure on an
# otherwise-successful run surfaces as an ``error``-status step, never an exception
# that flips the verdict. Synthetic fixtures only (C-003).
# --------------------------------------------------------------------------- #

_PARSER_DEST_RELPATH = "src/premura/parsers/_live_trial_parser.py"


@dataclass
class _Turn:
    """A minimal structural :class:`~premura.harness.live_trial.TurnLike` value."""

    role: str
    content: str
    tool_name: str | None = None
    model: str | None = None
    token_count: int | None = None


@dataclass
class _TranscriptOperator:
    """A fake operator that installs the reference parser AND exposes a transcript.

    Models a tier that converses: ``operate`` does the sandbox edit (like
    :class:`ReferenceParserOperator`) and records a canned conversation that
    ``transcript()`` returns afterward, so the harness has turns to persist.
    """

    parser_src: Path
    model_id: str = "fake-operator:transcript"
    _turns: list[_Turn] = field(default_factory=list)

    def operate(self, sandbox: Sandbox, goal: str) -> None:
        install_parser(sandbox, self.parser_src, _PARSER_DEST_RELPATH)
        self._turns = [
            _Turn(role="system", content=f"You are an operator. goal: {goal}"),
            _Turn(role="assistant", content="here is the parser", tool_name="write_parser"),
            _Turn(role="tool", content="parser written", tool_name="write_parser"),
            _Turn(role="assistant", content="done", model=self.model_id, token_count=7),
        ]

    def transcript(self) -> list[_Turn]:
        return list(self._turns)


@dataclass
class _RaisingTranscriptOperator:
    """A fake operator whose ``transcript()`` raises — capture must not flip verdict."""

    parser_src: Path
    model_id: str = "fake-operator:bad-transcript"

    def operate(self, sandbox: Sandbox, goal: str) -> None:  # noqa: ARG002 - goal unused
        install_parser(sandbox, self.parser_src, _PARSER_DEST_RELPATH)

    def transcript(self) -> list[_Turn]:
        raise RuntimeError("synthetic transcript-capture failure")


def _read_turns(session_log_path: Path) -> list[tuple[str | None, int, str, str, str | None]]:
    conn = duckdb.connect(str(session_log_path), read_only=True)
    try:
        return conn.execute(
            """
            SELECT step_id, turn_index, role, content, tool_name
            FROM log_turn ORDER BY turn_index
            """
        ).fetchall()
    finally:
        conn.close()


def test_transcript_operator_persists_turns_in_order() -> None:
    """FR-5: the harness persists the operator's transcript as ordered log_turn rows.

    The turns replay in conversation order, carry the operator's optional
    telemetry, and link to the run's root ``agent_turn`` step (FR-1's step_id link).
    """
    operator = _TranscriptOperator(parser_src=GOOD_PARSER)
    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        # The run still reached its normal verdict.
        assert result.verdict["passed"] is True

        turns = _read_turns(log_path)
        assert [(r[2], r[3]) for r in turns] == [
            (
                "system",
                "You are an operator. goal: ingest the heart-rate category from the dropped dump",
            ),
            ("assistant", "here is the parser"),
            ("tool", "parser written"),
            ("assistant", "done"),
        ]
        assert [r[1] for r in turns] == [0, 1, 2, 3]
        # tool_name carried through on the tool-bearing turns.
        assert turns[1][4] == "write_parser"
        assert turns[2][4] == "write_parser"

        # Every turn links to the single root agent_turn step (FR-1 step_id link).
        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            root = conn.execute("SELECT step_id FROM log_step WHERE kind = 'agent_turn'").fetchone()
            assert root is not None
        finally:
            conn.close()
        assert {r[0] for r in turns} == {root[0]}
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


def test_no_capability_operator_leaves_zero_turns() -> None:
    """FR-2: a transcript-less operator behaves exactly as before (no log_turn rows)."""
    operator = ReferenceParserOperator(parser_src=GOOD_PARSER)
    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        assert result.verdict["passed"] is True
        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            count = conn.execute("SELECT COUNT(*) FROM log_turn").fetchone()
            assert count is not None and count[0] == 0
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


def test_capture_failure_does_not_flip_verdict() -> None:
    """FR-5: a raising transcript() yields a recorded error step, not an exception.

    The run still returns its PASS verdict and a finished session; the capture
    failure surfaces as an ``error``-status step, never an aborted run.
    """
    operator = _RaisingTranscriptOperator(parser_src=GOOD_PARSER)
    result = live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="GoodFitbitHrParser",
    )
    log_path = result.session_log_path
    try:
        # The verdict is unchanged — capture failure cannot flip the run.
        assert result.verdict["passed"] is True

        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            # No turns landed (capture failed before any write).
            turns = conn.execute("SELECT COUNT(*) FROM log_turn").fetchone()
            assert turns is not None and turns[0] == 0
            # The failure is recorded as an error-status step.
            err = conn.execute(
                "SELECT COUNT(*) FROM log_step WHERE result_status = 'error'"
            ).fetchone()
            assert err is not None and err[0] >= 1
            # The session was still finished, not aborted.
            finished = conn.execute("SELECT finished_at FROM log_session").fetchone()
            assert finished is not None and finished[0] is not None
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)
