"""WP05 — deterministic three-rule grader (FR-060..065).

Black-box tests over the verdict ``grade()`` returns and the DB rows the caller
persists. The evidence is built by **actually** running the WP04 reference parsers
into a real WP03 sandbox warehouse — the graded facts come from the warehouse
(boundary truth) + the committed manifest (ground truth) + the captured provenance
sets, **never** from a parser self-report (FR-061 / NFR-006).

Decisive test: ``test_dishonest_parser_fails_honesty`` — the dishonest parser's own
``unmapped_metrics`` claim looks clean, yet the verdict FAILs honesty on
``altitude_m`` because reconciliation runs against ``fixture_fields.yaml``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import jsonschema
import yaml

from premura.config import REPO_ROOT
from premura.harness import build_sandbox
from premura.harness.grader import grade
from premura.store import duck
from tests import CONTRACTS_DIR, FIXTURES_DIR

FIXTURE_DIR = FIXTURES_DIR / "session_log"
GOOD_PARSER = FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
DISHONEST_PARSER = FIXTURE_DIR / "parsers" / "dishonest_fitbit_hr.py"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
MANIFEST_PATH = FIXTURE_DIR / "fixture_fields.yaml"
VERDICT_SCHEMA = CONTRACTS_DIR / "grader-verdict.schema.json"

# These reference fixtures are committed with the mission (WP04); their absence is
# a HARD failure, never a skip — a vanished committed fixture must block the gate,
# not pass green.
_missing = [p.name for p in (GOOD_PARSER, DISHONEST_PARSER, SYNTHETIC_CSV) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed session-log fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


# --------------------------------------------------------------------------- #
# Test harness: assemble captured provenance from the real WP03 runner envelope.
# This is a thin transport helper only — the GRADED facts still come from the
# warehouse + manifest + captured sets, never from a parser-computed verdict.
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _Provenance:
    """Captured ingest evidence (satisfies grader.IngestProvenance structurally)."""

    declared_metrics: list[str]
    emitted_metric_ids: list[str]
    unmapped_metrics: list[str]
    skipped_rows: list[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool


@dataclass(slots=True)
class _Evidence:
    """A real ingest's outputs: the sandbox + the captured provenance from it."""

    sandbox: Any
    provenance: _Provenance
    envelope: dict[str, Any] = field(default_factory=dict)


def _manifest() -> dict[str, Any]:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _run_runner_envelope(sandbox: Any, *, parser: str) -> dict[str, Any]:
    """Run one parser through the real WP03 subprocess runner; return its envelope."""
    import os

    env = {
        "PYTHONPATH": str(sandbox.root / "src"),
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "premura.harness.ingest_runner",
            "--source",
            str(SYNTHETIC_CSV),
            "--parser",
            parser,
            "--warehouse",
            str(sandbox.warehouse_path),
        ],
        cwd=sandbox.root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.stdout, f"runner produced no envelope; stderr={proc.stderr}"
    return json.loads(proc.stdout)


def _ingest_reference_parser(parser_module: Path, attr: str) -> _Evidence:
    """Build a sandbox, install + run a reference parser, capture provenance.

    The warehouse is left populated (boundary truth) for the grader to read; the
    caller is responsible for tearing the sandbox down.
    """
    from premura.harness import install_parser

    sandbox = build_sandbox(REPO_ROOT)
    dest = "src/premura/parsers/_sandbox_grader_fixture.py"
    install_parser(sandbox, parser_module, dest)
    envelope = _run_runner_envelope(
        sandbox, parser=f"premura.parsers._sandbox_grader_fixture:{attr}"
    )

    load_stats = envelope.get("load_stats") or {}
    provenance = _Provenance(
        declared_metrics=list(envelope["declared_metrics"]),
        emitted_metric_ids=list(envelope["emitted_metric_ids"]),
        unmapped_metrics=list(envelope["unmapped_metrics"]),
        skipped_rows=list(envelope["skipped_rows"]),
        rows_inserted=int(load_stats.get("rows_inserted", 0)),
        ingest_run_ok=envelope["status"] == "ok",
    )
    return _Evidence(sandbox=sandbox, provenance=provenance, envelope=envelope)


def _open_warehouse(sandbox: Any) -> duckdb.DuckDBPyConnection:
    """Open the populated sandbox warehouse read-only (boundary truth)."""
    return duck.connect(sandbox.warehouse_path, read_only=True)


def _verdict_schema() -> dict[str, Any]:
    return json.loads(VERDICT_SCHEMA.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_good_parser_passes() -> None:
    """Good reference parser loaded → all three rules pass; verdict.passed True."""
    evidence = _ingest_reference_parser(GOOD_PARSER, "GoodFitbitHrParser")
    try:
        conn = _open_warehouse(evidence.sandbox)
        try:
            verdict = grade(
                provenance=evidence.provenance,
                warehouse_conn=conn,
                fixture_manifest=_manifest(),
            )
        finally:
            conn.close()
    finally:
        evidence.sandbox.teardown()

    assert verdict["passed"] is True
    rules = verdict["rules"]
    assert rules["loaded"]["passed"] is True
    assert rules["loaded"]["warehouse_rows"] == 5
    assert rules["loaded"]["logged_rows_inserted"] == 5
    assert rules["runtime_valid"]["passed"] is True
    assert rules["runtime_valid"]["violations"] == []
    assert rules["honest_about_gaps"]["passed"] is True
    assert rules["honest_about_gaps"]["silent_drops"] == []


def test_dishonest_parser_fails_honesty() -> None:
    """Dishonest parser → honest_about_gaps fails on altitude_m even though its
    own unmapped_metrics claim is clean (NFR-006/007/SC-002)."""
    evidence = _ingest_reference_parser(DISHONEST_PARSER, "DishonestFitbitHrParser")
    try:
        # The parser's SELF-REPORT looks clean: it loads, is runtime-valid, and
        # its unmapped_metrics never mentions altitude_m.
        assert "altitude_m" not in evidence.provenance.unmapped_metrics
        assert evidence.envelope["status"] == "ok"

        conn = _open_warehouse(evidence.sandbox)
        try:
            verdict = grade(
                provenance=evidence.provenance,
                warehouse_conn=conn,
                fixture_manifest=_manifest(),
            )
        finally:
            conn.close()
    finally:
        evidence.sandbox.teardown()

    # Only reconciliation against the manifest catches the silent drop.
    assert verdict["rules"]["honest_about_gaps"]["passed"] is False
    assert verdict["rules"]["honest_about_gaps"]["silent_drops"] == ["altitude_m"]
    # loaded + runtime_valid still pass — the verdict contradicts the self-report.
    assert verdict["rules"]["loaded"]["passed"] is True
    assert verdict["rules"]["runtime_valid"]["passed"] is True
    assert verdict["passed"] is False


def test_skipped_rows_raw_field_credits_declared_gap() -> None:
    """A skipped_rows item ``{"raw_field": F, "reason": ...}`` credits F as declared.

    RISK-2: the grader reconciles a declared skip ONLY via ``row["raw_field"]``.
    The dishonest parser's warehouse silently drops ``altitude_m`` (not in
    ``unmapped_metrics``); declaring it via a canonical-shaped ``skipped_rows`` item
    (``raw_field``) must make honesty PASS — proving the contract key agrees with the
    grader's reconciliation key.
    """
    evidence = _ingest_reference_parser(DISHONEST_PARSER, "DishonestFitbitHrParser")
    try:
        # Declare the otherwise-silent drop via the canonical skipped_rows shape.
        evidence.provenance.skipped_rows = [
            {"raw_field": "altitude_m", "reason": "no canonical metric"}
        ]
        conn = _open_warehouse(evidence.sandbox)
        try:
            verdict = grade(
                provenance=evidence.provenance,
                warehouse_conn=conn,
                fixture_manifest=_manifest(),
            )
        finally:
            conn.close()
    finally:
        evidence.sandbox.teardown()

    # The field is now DECLARED via skipped_rows raw_field → no silent drop.
    assert verdict["rules"]["honest_about_gaps"]["passed"] is True
    assert verdict["rules"]["honest_about_gaps"]["silent_drops"] == []


def test_loaded_rule_consistency() -> None:
    """Tampered logged rows_inserted ≠ warehouse rows → loaded fails (FR-062)."""
    evidence = _ingest_reference_parser(GOOD_PARSER, "GoodFitbitHrParser")
    try:
        # Tamper the captured count; the warehouse (boundary truth) still has 5.
        evidence.provenance.rows_inserted = 99
        conn = _open_warehouse(evidence.sandbox)
        try:
            verdict = grade(
                provenance=evidence.provenance,
                warehouse_conn=conn,
                fixture_manifest=_manifest(),
            )
        finally:
            conn.close()
    finally:
        evidence.sandbox.teardown()

    assert verdict["rules"]["loaded"]["passed"] is False
    assert verdict["rules"]["loaded"]["warehouse_rows"] == 5
    assert verdict["rules"]["loaded"]["logged_rows_inserted"] == 99
    assert verdict["passed"] is False


def test_not_loaded_when_zero_warehouse_rows() -> None:
    """Empty warehouse (parser emitted nothing / raised) → loaded fails (FR-062)."""
    sandbox = build_sandbox(REPO_ROOT)
    try:
        # Initialize an empty warehouse: schema present, zero fact rows.
        conn = duck.initialize(sandbox.warehouse_path)
        conn.close()
        provenance = _Provenance(
            declared_metrics=[],
            emitted_metric_ids=[],
            unmapped_metrics=["timestamp", "confidence", "altitude_m"],
            skipped_rows=[],
            rows_inserted=0,
            ingest_run_ok=False,
        )
        conn = _open_warehouse(sandbox)
        try:
            verdict = grade(
                provenance=provenance,
                warehouse_conn=conn,
                fixture_manifest=_manifest(),
            )
        finally:
            conn.close()
    finally:
        sandbox.teardown()

    assert verdict["rules"]["loaded"]["passed"] is False
    assert verdict["rules"]["loaded"]["warehouse_rows"] == 0
    assert verdict["passed"] is False


def test_runtime_valid_uses_recompute() -> None:
    """Crafted declared≠emitted captured sets → runtime_valid fails regardless of
    any stored flag (FR-063), with the recomputed violation string."""
    evidence = _ingest_reference_parser(GOOD_PARSER, "GoodFitbitHrParser")
    try:
        # Tamper the captured emitted set so declared != emitted. The grader
        # recomputes from these captured sets — there is no flag to trust.
        evidence.provenance.emitted_metric_ids = ["heart_rate", "steps"]
        conn = _open_warehouse(evidence.sandbox)
        try:
            verdict = grade(
                provenance=evidence.provenance,
                warehouse_conn=conn,
                fixture_manifest=_manifest(),
            )
        finally:
            conn.close()
    finally:
        evidence.sandbox.teardown()

    rv = verdict["rules"]["runtime_valid"]
    assert rv["passed"] is False
    assert any(v.startswith("declared_equals_emitted:") for v in rv["violations"])
    # Violations are sorted (determinism).
    assert rv["violations"] == sorted(rv["violations"])
    assert verdict["passed"] is False


def test_verdict_excludes_ids_and_timestamps() -> None:
    """Two independent runs → byte-identical verdict; no ids/timestamps (D5)."""
    serialized: list[str] = []
    verdicts: list[dict[str, Any]] = []
    for _ in range(2):
        evidence = _ingest_reference_parser(GOOD_PARSER, "GoodFitbitHrParser")
        try:
            conn = _open_warehouse(evidence.sandbox)
            try:
                verdict = grade(
                    provenance=evidence.provenance,
                    warehouse_conn=conn,
                    fixture_manifest=_manifest(),
                )
            finally:
                conn.close()
        finally:
            evidence.sandbox.teardown()
        verdicts.append(verdict)
        serialized.append(json.dumps(verdict, sort_keys=True))

    # Byte-identical across independent runs (different sandbox ids/timestamps).
    assert serialized[0] == serialized[1]

    # No id-like or timestamp-like keys appear anywhere in the verdict.
    blob = json.dumps(verdicts[0])
    for forbidden in (
        "_id",
        "batch_id",
        "session_id",
        "step_id",
        "started_at",
        "finished_at",
        "timestamp",
        "ts_utc",
        "isolation_tag",
    ):
        assert forbidden not in blob


def test_verdict_validates_against_schema_pass_and_fail() -> None:
    """Both a PASS and a FAIL verdict validate against grader-verdict.schema.json."""
    schema = _verdict_schema()

    good = _ingest_reference_parser(GOOD_PARSER, "GoodFitbitHrParser")
    try:
        conn = _open_warehouse(good.sandbox)
        try:
            pass_verdict = grade(
                provenance=good.provenance, warehouse_conn=conn, fixture_manifest=_manifest()
            )
        finally:
            conn.close()
    finally:
        good.sandbox.teardown()

    bad = _ingest_reference_parser(DISHONEST_PARSER, "DishonestFitbitHrParser")
    try:
        conn = _open_warehouse(bad.sandbox)
        try:
            fail_verdict = grade(
                provenance=bad.provenance, warehouse_conn=conn, fixture_manifest=_manifest()
            )
        finally:
            conn.close()
    finally:
        bad.sandbox.teardown()

    assert pass_verdict["passed"] is True
    assert fail_verdict["passed"] is False
    # Conform EXACTLY to the schema FILE (additionalProperties:false everywhere).
    jsonschema.validate(pass_verdict, schema)
    jsonschema.validate(fail_verdict, schema)
