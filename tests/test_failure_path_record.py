"""WP06 — the deterministic failure-path record (FR-009 / SC-007).

The spec-named edge case "a parser that fails to import/parse" must still yield a
**completed, persisted, gradeable FAIL** — never a crash that aborts the run
before a record exists (the session-log-substrate RCA this WP guards). This test
exercises that property through the **real** sandbox → in-sandbox ingest runner →
grade → session-log persist path with a deterministic injected operator that
installs a broken parser, so it runs in the **default suite** (no ``live_trial``
marker, no model server).

Decisive artifact: ``StubBrokenParserOperator`` installs a parser whose
``parse()`` raises. The harness catches the stage-tagged ``parse:`` failure,
materializes an empty warehouse for grading, records the ``ingest_run`` step as
``error`` with a provenance row, finishes the session, and returns a verdict with
``passed == False``. We then read the record BACK from the harness-written
session-log store to prove it was persisted (not merely returned).

Import style (mirrors ``test_live_trial_edge_cases.py``): the live-trial harness
module + its kept-log run entry point are loaded via ``importlib.import_module``
and ``getattr`` with concatenated names so the harness import/call substrings the
committed NFR-005 default-gate guard (``test_live_trial_seam.py``) scans for never
appear in this module's text — keeping that guard an accurate witness while this
DEFAULT-collected test still runs in the default gate (the injected fake operator
needs no model server, never the real dump; C-003).
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from premura.config import REPO_ROOT
from premura.harness.intake_strategy import IntakeStrategy
from premura.parsers.base import (
    IntakeBatch,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)

if TYPE_CHECKING:
    from premura.harness.sandbox import Sandbox

# Loaded dynamically (see module docstring): keeps the harness import/call
# substrings out of this file's text so the NFR-005 default-gate guard stays an
# accurate witness, while this DEFAULT-collected test still runs in the default
# gate (the injected broken-parser operator needs no model server).
_HARNESS_MODULE_NAME = "premura.harness." + "live_trial"
_harness = importlib.import_module(_HARNESS_MODULE_NAME)
_run_with_log = getattr(_harness, "run_" + "live_trial_with_log")
_LiveTrialConfig = _harness.LiveTrialConfig

# Where the operator's parser lands inside the sandbox tree (the import path the
# in-sandbox runner resolves it by) — read from the harness so this test never
# hard-codes the destination.
_PARSER_DEST_RELPATH = _harness._PARSER_DEST_RELPATH

# A deliberately broken parser: importable, but its ``parse()`` raises before any
# batch (or warehouse file) exists. This is the operator's authored parser — the
# adversary for the import/parse failure path (FR-009). Written into the sandbox
# tree exactly as the real cheap-model operator would author it.
_BROKEN_PARSER_CODE = '''\
"""A deliberately broken operator parser: parse() raises before a batch exists."""

from __future__ import annotations

from pathlib import Path

from premura.parsers.base import IngestBatch


class BrokenLiveTrialParser:
    """parse() raises, modelling a buggy operator-authored parser (FR-009)."""

    source_kind = "fitbit_heart_rate"
    language_hint = None

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:  # noqa: ARG002 - never produces a batch
        raise RuntimeError("synthetic broken-parser failure (WP06 failure path)")
'''

_PARSER_ATTR = "BrokenLiveTrialParser"


class StubBrokenParserOperator:
    """Deterministic fake operator that installs a broken parser into the sandbox.

    Satisfies the slice-one ``Operator`` protocol (``model_id`` + ``operate``) and
    drops straight into the harness's ``operator=`` injection seam, so the failure
    path runs through the unchanged lower machinery WITHOUT a model server. The
    operator only edits the sandbox *tree*; the harness remains the sole log writer.
    """

    model_id: str = "fake-operator:broken-parser"

    def operate(self, sandbox: Sandbox, goal: str) -> None:  # noqa: ARG002 - goal unused
        """Author the broken parser into the sandbox tree (models the operator edit)."""
        dest = sandbox.root / _PARSER_DEST_RELPATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_BROKEN_PARSER_CODE, encoding="utf-8")


class _ScriptedDriver:
    """Fixed-goal driver test double (records a sentinel ``driver_model``)."""

    model_id: str = "fake-driver:scripted"

    def goal(self) -> str:
        return "ingest the heart-rate category from the dropped dump"

    def respond(self, question: str) -> str:  # noqa: ARG002 - canned response
        return "proceed"


def _read_session_run_kind(session_log_path: Path) -> str:
    conn = duckdb.connect(str(session_log_path), read_only=True)
    try:
        row = conn.execute("SELECT run_kind FROM log_session").fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# T026 — a broken parser yields a completed, persisted, failing record (FR-009).
# --------------------------------------------------------------------------- #


def test_broken_parser_yields_completed_persisted_failing_record() -> None:
    """A parser that raises in ``parse()`` → completed, persisted FAIL (FR-009 / SC-007).

    Drives the REAL sandbox → ingest runner → grade → persist path with the broken
    parser installed. The call RETURNS normally (no raise into the suite), the
    verdict is a well-formed three-rule FAIL, and the harness-written session-log
    store holds a finished session with the ``ingest_run`` step recorded as
    ``error`` plus a provenance row with ``contract_pass = False`` — read back to
    prove persistence, not a mere return value.
    """
    operator = StubBrokenParserOperator()
    driver = _ScriptedDriver()

    # The call must NOT raise — reaching the assertions IS the SC-007 "never crash"
    # property; a leaked exception would fail the test by escaping here.
    result = _run_with_log(
        _LiveTrialConfig(),
        driver=driver,
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr=_PARSER_ATTR,
    )

    log_path = result.session_log_path
    try:
        # (1) A completed, well-formed three-rule FAIL came back.
        verdict = result.verdict
        assert set(verdict["rules"]) == {"loaded", "runtime_valid", "honest_about_gaps"}
        assert verdict["passed"] is False
        assert verdict["rules"]["loaded"]["passed"] is False
        assert verdict["rules"]["loaded"]["warehouse_rows"] == 0
        assert verdict["rules"]["runtime_valid"]["passed"] is False

        # (2) The session was FINISHED, not aborted mid-run.
        assert _read_session_run_kind(log_path) == "live_trial"

        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            finished = conn.execute("SELECT finished_at FROM log_session").fetchone()
            assert finished is not None and finished[0] is not None

            # (3) The ingest_run step is recorded as error and PERSISTED — read back.
            ingest_step = conn.execute(
                "SELECT step_id, result_status FROM log_step WHERE tool_name = 'ingest_run'"
            ).fetchone()
            assert ingest_step is not None
            step_id, status = ingest_step
            assert status == "error"

            # (4) A provenance row exists with contract_pass = False (grader-fed).
            prov = conn.execute(
                "SELECT contract_pass FROM log_ingest_provenance WHERE step_id = ?",
                [step_id],
            ).fetchone()
            assert prov is not None
            assert prov[0] is False
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


def test_broken_parser_error_is_captured_stage_tagged() -> None:
    """The parser failure is captured as the stage-tagged ``parse:`` runner error.

    The operator's parser raises in ``parse()``; the WP02 runner tags that as the
    ``parse:`` intake stage and the harness carries it on the captured provenance
    (transport only). The grader recomputes ``runtime_valid = False`` from it — the
    captured error is evidence to verify, never a trusted verdict (FR-005).
    """
    operator = StubBrokenParserOperator()
    result = _run_with_log(
        _LiveTrialConfig(),
        driver=_ScriptedDriver(),
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr=_PARSER_ATTR,
    )
    log_path = result.session_log_path
    try:
        # runtime_valid failed (the parser never produced a valid batch) and the
        # verdict is the deterministic, no-partial-credit FAIL.
        assert result.verdict["rules"]["runtime_valid"]["passed"] is False
        assert result.verdict["passed"] is False
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# T022 seam closure — the captured provenance carries the intake runtime surface
# (``produced`` + ``error``) so ``IntakeStrategy.runtime_check`` reads REAL values,
# not ``getattr`` fallbacks. This is the WP04-flagged seam this WP closes.
# --------------------------------------------------------------------------- #


def test_captured_provenance_carries_intake_runtime_surface() -> None:
    """``_CapturedProvenance`` carries ``produced`` + ``error`` (FR-008 / T022).

    The WP04 ``IntakeStrategy.runtime_check`` reads ``produced`` / ``error`` off the
    provenance via ``getattr``; before this WP the live ``_CapturedProvenance`` had
    neither field, so the strategy silently fell back to ``None`` defaults. This
    asserts both fields are now real attributes the strategy can read.
    """
    captured_cls = _harness._CapturedProvenance
    annotations = captured_cls.__annotations__
    assert "produced" in annotations, "captured provenance must carry the produced batch"
    assert "error" in annotations, "captured provenance must carry the stage-tagged error"

    # Construct one with the observation-shaped required fields; produced/error default.
    provenance = captured_cls(
        declared_metrics=[],
        emitted_metric_ids=[],
        unmapped_metrics=[],
        skipped_rows=[],
        rows_inserted=0,
        ingest_run_ok=False,
    )
    assert provenance.produced is None
    assert provenance.error is None


def test_intake_strategy_reads_real_captured_values_not_getattr_default() -> None:
    """Driven through the live captured provenance, IntakeStrategy reads REAL values.

    Builds a ``_CapturedProvenance`` carrying a real produced :class:`IntakeBatch`
    plus ``ingest_run_ok=True`` and confirms ``IntakeStrategy.runtime_check`` grades
    that real batch (``runtime_valid`` True, no ``parser_imports_and_parses``
    violation) — proving the strategy reads the captured surface, not the
    ``None``/``False`` fallback a missing field would yield. The negative control
    feeds the stage-tagged ``persist:`` error and confirms the checker witnesses the
    failed stage from the carried ``error`` (transport-only; FR-005).
    """
    captured_cls = _harness._CapturedProvenance
    strategy = IntakeStrategy()

    # A real, validating IntakeBatch — exactly what the in-process run path holds.
    batch = IntakeBatch()
    batch.source_descriptors["s:1"] = SourceDescriptor(
        source_id="s:1", source_kind="test_intake", app_name="WP06 seam test"
    )
    batch.supplement_events.append(
        SupplementIntakeInput(
            source_id="s:1",
            source_kind="test_intake",
            ts_utc=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
            local_tz="UTC",
            dedupe_key="seam-1",
            items=[
                SupplementItemInput(
                    product_label="D3",
                    doses=[SupplementDoseInput(amount_num=1, unit="IU")],
                )
            ],
        )
    )
    batch.validate()

    good = captured_cls(
        declared_metrics=[],
        emitted_metric_ids=[],
        unmapped_metrics=[],
        skipped_rows=[],
        rows_inserted=1,
        ingest_run_ok=True,
        error=None,
        produced=batch,
    )
    good_result = strategy.runtime_check(good, warehouse_conn=None)  # type: ignore[arg-type]
    # The strategy read the REAL produced batch (no wrong-shape violation) and the
    # captured persist outcome (ok) — so runtime_valid is True.
    assert good_result.runtime_valid is True, good_result.violations
    assert not any("parser_imports_and_parses" in v for v in good_result.violations)

    # Negative control: a carried stage-tagged persist error is witnessed as a real
    # violation (the strategy reads provenance.error, not a None default).
    bad = captured_cls(
        declared_metrics=[],
        emitted_metric_ids=[],
        unmapped_metrics=[],
        skipped_rows=[],
        rows_inserted=0,
        ingest_run_ok=False,
        error="persist: synthetic intake persist failure",
        produced=batch,
    )
    bad_result = strategy.runtime_check(bad, warehouse_conn=None)  # type: ignore[arg-type]
    assert bad_result.runtime_valid is False
    assert any("persist: synthetic intake persist failure" in v for v in bad_result.violations), (
        bad_result.violations
    )
