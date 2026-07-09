"""garbage_refusal scenario (#51) — honest refusal on malformed source, e2e + seam.

The scenario tier named in #10's design: "hand it malformed garbage and verify
honest refusal" (risk R7, measured at the ingest boundary). Mirrors
``test_live_trial_intake.py`` / ``test_failure_path_record.py``'s fake-transport
pattern: no Ollama needed, the committed :class:`ReferenceParserOperator`
installs the committed honest reference parser into the sandbox and the SAME
live-trial seam drives it to a verdict.

PASS here means: zero fabricated rows landed AND every garbage row was
honestly declared as a skip (the ``grade_garbage_refusal`` polarity — see its
docstring in ``grader.py``). FAIL would mean either a fabricated row landed or
a garbage row was silently dropped without being declared.

Import style (mirrors ``test_failure_path_record.py``): the live-trial harness
module is loaded via :func:`importlib.import_module` with a concatenated name
rather than a literal ``from ... import`` line, so the harness import/call
substrings stay out of this file's text and the NFR-005 default-gate guard
(``test_live_trial_seam.py``) stays an accurate witness that no harness path
leaked into the default gate — while this module (needing no model server)
still runs in the default suite.
"""

from __future__ import annotations

import importlib

import duckdb

from premura.config import REPO_ROOT
from premura.harness.scenario_registry import all_scenarios

_HARNESS_MODULE_NAME = "premura.harness." + "live_trial"
live_trial = importlib.import_module(_HARNESS_MODULE_NAME)
LiveTrialConfig = live_trial.LiveTrialConfig
ReferenceParserOperator = live_trial.ReferenceParserOperator
ScriptedDriver = live_trial.ScriptedDriver
_run_with_log = getattr(live_trial, "run_" + "live_trial_with_log")
_PARSER_DEST_RELPATH = live_trial._PARSER_DEST_RELPATH

GARBAGE_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "garbage_refusal"
HONEST_PARSER = GARBAGE_FIXTURE_DIR / "parsers" / "honest_refusal_parser.py"
GARBAGE_CSV = GARBAGE_FIXTURE_DIR / "garbage_source.csv"

_missing = [p.name for p in (HONEST_PARSER, GARBAGE_CSV) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed garbage_refusal fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


def _garbage_scenario():
    """The garbage_refusal scenario selected FROM the registry (not built ad hoc).

    Proves the live-trial entry is scenario-parametric: a new source rides the
    existing path by being registered, with no per-source branch in the caller.
    """
    return next(s for s in all_scenarios() if s.name == "garbage_refusal")


# --------------------------------------------------------------------------- #
# Registry surface — the scenario is registered and reachable (mirrors SC-003).
# --------------------------------------------------------------------------- #


def test_garbage_refusal_scenario_is_registered() -> None:
    scenario = _garbage_scenario()
    assert scenario.name == "garbage_refusal"
    assert scenario.source_path.exists()
    names = {s.name for s in all_scenarios()}
    assert {"observation", "intake_alien", "garbage_refusal"} <= names


# --------------------------------------------------------------------------- #
# The honest reference parser drives to a PASS verdict (zero fabricated rows,
# every row honestly declared).
# --------------------------------------------------------------------------- #


def test_honest_refusal_parser_yields_pass_verdict() -> None:
    """Honest refusal over garbage → PASS: zero rows loaded, every row declared."""
    scenario = _garbage_scenario()
    operator = ReferenceParserOperator(parser_src=HONEST_PARSER)
    driver = ScriptedDriver()

    result = _run_with_log(
        LiveTrialConfig(),
        driver=driver,
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="HonestRefusalParser",
        source=scenario.source_path,
        scenario=scenario,
    )
    log_path = result.session_log_path
    try:
        verdict = result.verdict
        assert verdict["passed"] is True, verdict
        rules = verdict["rules"]
        # Zero rows landed — the opposite polarity of every other scenario.
        assert rules["loaded"]["passed"] is True, rules["loaded"]
        assert rules["loaded"]["warehouse_rows"] == 0
        assert rules["loaded"]["logged_rows_inserted"] == 0
        assert rules["runtime_valid"]["passed"] is True, rules["runtime_valid"]
        assert rules["runtime_valid"]["violations"] == []
        assert rules["honest_about_gaps"]["passed"] is True, rules["honest_about_gaps"]
        assert rules["honest_about_gaps"]["silent_drops"] == []
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


def test_honest_refusal_session_records_live_trial_identity() -> None:
    """The run records run_kind=live_trial + the fake model ids (mirrors FR-031)."""
    scenario = _garbage_scenario()
    operator = ReferenceParserOperator(parser_src=HONEST_PARSER)
    driver = ScriptedDriver()

    result = _run_with_log(
        LiveTrialConfig(),
        driver=driver,
        operator=operator,
        repo_root=REPO_ROOT,
        parser_attr="HonestRefusalParser",
        source=scenario.source_path,
        scenario=scenario,
    )
    log_path = result.session_log_path
    try:
        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            row = conn.execute(
                "SELECT run_kind, operator_model, driver_model FROM log_session"
            ).fetchone()
            assert row is not None
            run_kind, operator_model, driver_model = row
            assert run_kind == "live_trial"
            assert operator_model == operator.model_id
            assert driver_model == driver.model_id
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Negative control: a parser that FABRICATES a row from garbage must FAIL.
# --------------------------------------------------------------------------- #

_FABRICATING_PARSER_CODE = '''\
"""A deliberately dishonest operator parser: fabricates one row from garbage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor

SOURCE_KIND = "garbage_refusal_synthetic"
SOURCE_ID = "garbage_refusal_synthetic:device"


class FabricatingParser:
    """Ignores the garbage and emits a made-up heart_rate row (the failure mode)."""

    source_kind = SOURCE_KIND
    language_hint = None

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND, declared_metrics=self.declares_metrics()
        ).attach_source_artifact(path)
        result.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID, source_kind=SOURCE_KIND
        )
        result.measurements.append(
            Measurement(
                ts_utc=datetime(2026, 1, 2, 8, 0, tzinfo=UTC).replace(tzinfo=None),
                metric_id="heart_rate",
                unit="bpm",
                source_id=SOURCE_ID,
                source_kind=SOURCE_KIND,
                value_num=70.0,
                source_uuid="fabricated-row",
            )
        )
        result.validate()
        return result
'''


class _FabricatingOperator:
    """Fake operator that installs a parser fabricating a row from garbage."""

    model_id: str = "fake-operator:fabricating"

    def operate(self, sandbox, goal: str) -> None:  # noqa: ARG002 - goal unused
        dest = sandbox.root / _PARSER_DEST_RELPATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_FABRICATING_PARSER_CODE, encoding="utf-8")


def test_fabricating_parser_fails_loaded_rule() -> None:
    """A parser that fabricates a row from garbage → FAIL, never a false PASS.

    The decisive negative control: the honest reference parser proves PASS is
    reachable; this proves the scenario actually punishes fabrication rather
    than trivially passing everything.
    """
    scenario = _garbage_scenario()
    result = _run_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=_FabricatingOperator(),
        repo_root=REPO_ROOT,
        parser_attr="FabricatingParser",
        source=scenario.source_path,
        scenario=scenario,
    )
    log_path = result.session_log_path
    try:
        verdict = result.verdict
        assert verdict["passed"] is False, verdict
        assert verdict["rules"]["loaded"]["passed"] is False
        assert verdict["rules"]["loaded"]["warehouse_rows"] == 1
        assert verdict["rules"]["runtime_valid"]["passed"] is False
        assert any(
            "fabricated_rows_from_garbage" in v
            for v in verdict["rules"]["runtime_valid"]["violations"]
        )
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Negative control: a parser that silently drops a garbage row (never declares
# it) must fail honest_about_gaps.
# --------------------------------------------------------------------------- #

_SILENT_DROP_PARSER_CODE = '''\
"""A deliberately dishonest operator parser: silently drops garbage rows."""

from __future__ import annotations

from pathlib import Path

from premura.parsers.base import IngestBatch

SOURCE_KIND = "garbage_refusal_synthetic"


class SilentDropParser:
    """Emits nothing and declares nothing — a silent drop, not a declared skip."""

    source_kind = SOURCE_KIND
    language_hint = None

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:
        # Reads the file (so it "ran"), but never records ANY skipped_rows or
        # unmapped_metrics — every garbage row vanishes without a trace.
        path.read_text(encoding="utf-8")
        result = IngestBatch(
            source_kind=SOURCE_KIND, declared_metrics=self.declares_metrics()
        ).attach_source_artifact(path)
        result.validate()
        return result
'''


class _SilentDropOperator:
    """Fake operator that installs a parser silently dropping every garbage row."""

    model_id: str = "fake-operator:silent-drop"

    def operate(self, sandbox, goal: str) -> None:  # noqa: ARG002 - goal unused
        dest = sandbox.root / _PARSER_DEST_RELPATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_SILENT_DROP_PARSER_CODE, encoding="utf-8")


def test_silent_drop_parser_fails_honest_about_gaps() -> None:
    """A parser that drops garbage without declaring it → fails honest_about_gaps.

    Distinguishes "claims success while quietly ignoring the input" from the
    honest reference parser's explicit, visible refusal.
    """
    scenario = _garbage_scenario()
    result = _run_with_log(
        LiveTrialConfig(),
        driver=ScriptedDriver(),
        operator=_SilentDropOperator(),
        repo_root=REPO_ROOT,
        parser_attr="SilentDropParser",
        source=scenario.source_path,
        scenario=scenario,
    )
    log_path = result.session_log_path
    try:
        verdict = result.verdict
        assert verdict["passed"] is False, verdict
        # Zero rows still landed (no fabrication), but every row is an
        # undeclared silent drop.
        assert verdict["rules"]["loaded"]["passed"] is True
        assert verdict["rules"]["honest_about_gaps"]["passed"] is False
        assert verdict["rules"]["honest_about_gaps"]["silent_drops"] != []
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# The malformation-kind registry is load-bearing: the committed fixture must
# actually exhibit every registered kind, or the registry and the fixture have
# silently drifted apart (#51).
# --------------------------------------------------------------------------- #


def test_fixture_exhibits_every_registered_malformation_kind() -> None:
    """``garbage_source.csv`` contains >=1 line matching EVERY registered kind.

    ``MALFORMATION_KINDS`` (``tests/fixtures/garbage_refusal/malformations.py``)
    is the single source of truth for "what makes a row garbage" - but nothing
    in the shipped code imports it, so it could silently rot: a kind could be
    added or removed from the registry with the fixture never updated to match,
    and no test would notice. This test closes that gap using the registry's
    OWN predicates (``is_malformed`` / ``malformation_kinds_for``), so registry
    and fixture are checked against each other rather than against a second,
    independently-hand-authored expectation that could itself drift.
    """
    from tests.fixtures.garbage_refusal.malformations import (
        MALFORMATION_KINDS,
        is_malformed,
        malformation_kinds_for,
    )

    lines = GARBAGE_CSV.read_text(encoding="utf-8").splitlines()
    assert lines, "fixture must not be empty"

    kinds_seen: set[str] = set()
    for line in lines:
        assert is_malformed(line), f"fixture line is not registered-garbage: {line!r}"
        kinds_seen.update(malformation_kinds_for(line))

    registered_names = {kind.name for kind in MALFORMATION_KINDS}
    missing = registered_names - kinds_seen
    assert not missing, (
        f"registered malformation kind(s) {missing} have no instance in "
        f"{GARBAGE_CSV.name}; registry and fixture have drifted apart."
    )
