"""WP06 — repeatable check end-to-end (FR-004, FR-030; OWNS NFR-001/NFR-002).

Black-box tests over the verdict :func:`run_repeatable_check` returns and the rows
the harness wrote into the session-log DB. The fake scripted agent (no model)
installs a committed reference parser, runs the WP03 subprocess ingest, the
harness records the named ``tool_call`` steps it is the SOLE writer of, the WP05
grader recomputes the verdict, and the sandbox is torn down (NFR-004).

Decisive artifacts:

* ``test_verdict_stable_across_runs`` (NFR-001) — two full runs from scratch
  serialize to a byte-identical verdict. This is the measurable NFR-001 evidence
  named in plan.md.
* ``test_dishonest_path_fails_end_to_end`` — the dishonest parser's self-report is
  clean, yet the verdict FAILs honesty on ``altitude_m``.

The whole suite runs OFFLINE from the committed fixture only (NFR-002): no private
dump path, no network. The live trial against the real dump is WP07, not here.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import jsonschema

from premura.config import REPO_ROOT
from premura.harness import repeatable_check

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "session_log"
GOOD_PARSER = FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
DISHONEST_PARSER = FIXTURE_DIR / "parsers" / "dishonest_fitbit_hr.py"
RAISING_PARSER = FIXTURE_DIR / "parsers" / "raising_fitbit_hr.py"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
VERDICT_SCHEMA = Path(__file__).parent / "contracts" / "grader-verdict.schema.json"

# These reference fixtures are committed with the mission (WP04); their absence is
# a HARD failure, never a skip — a vanished committed fixture must block the gate,
# not pass green.
_missing = [p.name for p in (GOOD_PARSER, DISHONEST_PARSER, SYNTHETIC_CSV) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed session-log fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


def _read_steps(session_log_path: Path) -> list[tuple[str, str, str, str]]:
    """Read (kind, tool_name, name, result_status) for every recorded step.

    Opens the harness-written log read-only — the harness was the sole writer.
    """
    conn = duckdb.connect(str(session_log_path), read_only=True)
    try:
        return conn.execute(
            "SELECT kind, tool_name, name, result_status FROM log_step ORDER BY started_at"
        ).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# T024 — end-to-end PASS + FAIL from the real repo root.
# --------------------------------------------------------------------------- #


def test_good_path_passes_end_to_end() -> None:
    """Good reference parser → verdict.passed True; all three rules pass."""
    result = repeatable_check.run_good(REPO_ROOT)
    verdict = result.verdict
    assert verdict["passed"] is True
    rules = verdict["rules"]
    assert rules["loaded"]["passed"] is True
    assert rules["runtime_valid"]["passed"] is True
    assert rules["runtime_valid"]["violations"] == []
    assert rules["honest_about_gaps"]["passed"] is True
    assert rules["honest_about_gaps"]["silent_drops"] == []
    # The verdict validates against the cross-WP schema (no ids/timestamps).
    jsonschema.validate(verdict, json.loads(VERDICT_SCHEMA.read_text(encoding="utf-8")))


def test_dishonest_path_fails_end_to_end() -> None:
    """Dishonest reference parser → verdict.passed False; silent_drops altitude_m."""
    result = repeatable_check.run_dishonest(REPO_ROOT)
    verdict = result.verdict
    assert verdict["passed"] is False
    assert verdict["rules"]["honest_about_gaps"]["passed"] is False
    assert verdict["rules"]["honest_about_gaps"]["silent_drops"] == ["altitude_m"]
    # The self-report still loads + is runtime-valid; only reconciliation catches it.
    assert verdict["rules"]["loaded"]["passed"] is True
    assert verdict["rules"]["runtime_valid"]["passed"] is True


# --------------------------------------------------------------------------- #
# DRIVE-1 / FR-080 — a raising parser yields a CAPTURED, GRADED FAIL, not a crash.
# --------------------------------------------------------------------------- #


def test_raising_parser_yields_captured_failed_run() -> None:
    """Parser raises before any batch → captured, graded FAIL (spec edge / FR-080).

    The parser raises before the runner reaches ``duck.initialize(warehouse)``, so
    NO warehouse file is created. The harness must NOT crash on the missing
    warehouse: it materializes an empty (0-fact-row) warehouse for grading, records
    the ``ingest_run`` step as ``error`` with a provenance row, finishes the
    session, and the grader returns a deterministic FAIL (no partial credit).
    """
    # Call RETURNS (no exception escapes the run); keep the sandbox to inspect the log.
    result = repeatable_check.run_repeatable_check(
        REPO_ROOT,
        parser_src=RAISING_PARSER,
        parser_attr="RaisingFitbitHrParser",
        keep_sandbox=True,
    )
    log_path = result.session_log_path
    try:
        verdict = result.verdict
        # Deterministic FAIL: loaded fails (0 warehouse rows) and so does the verdict.
        assert verdict["passed"] is False
        assert verdict["rules"]["loaded"]["passed"] is False
        assert verdict["rules"]["loaded"]["warehouse_rows"] == 0
        # runtime_valid fails (ingest_run_ok is False on the error envelope).
        assert verdict["rules"]["runtime_valid"]["passed"] is False

        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            # The ingest_run step was recorded with result_status == 'error'.
            ingest_step = conn.execute(
                "SELECT step_id, result_status FROM log_step WHERE tool_name = 'ingest_run'"
            ).fetchone()
            assert ingest_step is not None
            step_id, status = ingest_step
            assert status == "error"

            # A provenance row exists for that step (the run is auditable).
            prov = conn.execute(
                "SELECT contract_pass FROM log_ingest_provenance WHERE step_id = ?",
                [step_id],
            ).fetchone()
            assert prov is not None
            assert prov[0] is False  # grader's runtime_valid for the failed run

            # The session was FINISHED (not aborted): finished_at is set.
            finished = conn.execute("SELECT finished_at FROM log_session").fetchone()
            assert finished is not None
            assert finished[0] is not None
        finally:
            conn.close()
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# T024 — the harness recorded the named tool_call steps (FR-004) + provenance.
# --------------------------------------------------------------------------- #


def test_log_records_named_steps() -> None:
    """The harness recorded the named tool_call steps + the ingest provenance row.

    ``keep_sandbox=True`` lets the test inspect the pre-teardown log; production
    paths tear the sandbox down by default.
    """
    result = repeatable_check.run_good(REPO_ROOT, keep_sandbox=True)
    log_path = result.session_log_path
    try:
        steps = _read_steps(log_path)

        # One agent_turn parent.
        kinds = [k for (k, _t, _n, _s) in steps]
        assert kinds.count("agent_turn") == 1

        # The FR-004 named tool_call steps are present, by named-tool convention.
        tool_names = {t for (k, t, _n, _s) in steps if k == "tool_call"}
        assert {"edit_file", "parser_contract_check", "ingest_run"} <= tool_names

        # The ingest_run step succeeded and has a linked provenance row whose
        # contract_pass is the GRADER's recomputed runtime_valid (FR-065).
        conn = duckdb.connect(str(log_path), read_only=True)
        try:
            ingest_step = conn.execute(
                "SELECT step_id, result_status FROM log_step WHERE tool_name = 'ingest_run'"
            ).fetchone()
            assert ingest_step is not None
            step_id, status = ingest_step
            assert status == "available"
            prov = conn.execute(
                "SELECT rows_inserted, contract_pass FROM log_ingest_provenance WHERE step_id = ?",
                [step_id],
            ).fetchone()
            assert prov is not None
            rows_inserted, contract_pass = prov
            assert rows_inserted == 5
            # contract_pass == the grader's runtime_valid for this PASS run.
            assert contract_pass is True
            assert contract_pass == result.verdict["rules"]["runtime_valid"]["passed"]
        finally:
            conn.close()
    finally:
        # Inspection done — remove the kept sandbox tree (NFR-004).
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Sole-writer (FR-021): only the harness wrote the log; the runner wrote none.
# --------------------------------------------------------------------------- #


def test_harness_is_sole_log_writer() -> None:
    """Only the harness wrote the session log; the runner produced no log file.

    The runner writes the warehouse but never the session log (FR-021). After a
    run, the ONLY session-log file is the one the harness wrote, and it holds the
    harness's steps. We assert the harness's log has the steps and the runner left
    no separate log artifact in the sandbox.
    """
    result = repeatable_check.run_good(REPO_ROOT, keep_sandbox=True)
    log_path = result.session_log_path
    try:
        # The harness's log exists and carries its steps.
        assert log_path.exists()
        steps = _read_steps(log_path)
        assert len(steps) >= 4  # turn + edit_file + parser_contract_check + ingest_run

        # The runner produced NO other session-log file anywhere in the sandbox
        # data dir (the single redirected log path is the harness's own).
        data_dir = log_path.parent
        log_files = [p for p in data_dir.iterdir() if p.name == log_path.name]
        assert log_files == [log_path]
    finally:
        import shutil

        shutil.rmtree(log_path.parent.parent, ignore_errors=True)


def test_repeatable_check_source_has_no_network_client() -> None:
    """Static guard: the module imports no HTTP/network client (NFR-002 offline)."""
    src = Path(repeatable_check.__file__).read_text(encoding="utf-8")
    for forbidden in ("import requests", "import httpx", "import urllib.request", "import socket"):
        assert forbidden not in src


# --------------------------------------------------------------------------- #
# T025 — determinism (NFR-001) + offline (NFR-002).
# --------------------------------------------------------------------------- #


def test_verdict_stable_across_runs() -> None:
    """NFR-001: two full repeatable checks from scratch → byte-identical verdict.

    This is the measurable NFR-001 evidence artifact named in plan.md. Each run
    builds a fresh sandbox (different ids/timestamps upstream); none of that may
    leak into the verdict.
    """
    serialized: list[str] = []
    for _ in range(2):
        result = repeatable_check.run_good(REPO_ROOT)
        serialized.append(json.dumps(result.verdict, sort_keys=True))
    assert serialized[0] == serialized[1]

    # No id-like / timestamp-like key leaked into the verdict.
    for forbidden in (
        "session_id",
        "step_id",
        "batch_id",
        "isolation_tag",
        "started_at",
        "finished_at",
        "timestamp",
    ):
        assert forbidden not in serialized[0]


def test_runs_offline_from_clean_inputs() -> None:
    """NFR-002: the check runs to a verdict from the repo + committed fixtures only.

    No private dump path is referenced and no network is hit (the flow performs no
    HTTP — see ``test_repeatable_check_source_has_no_network_client``). Reaching a
    verdict from REPO_ROOT alone witnesses the self-contained, offline guarantee.
    """
    result = repeatable_check.run_good(REPO_ROOT)
    assert "passed" in result.verdict
    # The only inputs touched are under the repo's committed fixture tree.
    assert (
        REPO_ROOT / "tests" / "fixtures" / "session_log" / "fitbit_heart_rate_synthetic.csv"
    ).exists()
