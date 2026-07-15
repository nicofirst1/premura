"""WP01 — the observation golden-verdict regression (C-004 / SC-006).

Proves the scenario refactor changed **nothing** about observation grading: the
refactored ``grade()`` driven through the observation scenario over the committed
synthetic fixture reproduces the pre-refactor verdict **byte-for-byte**.

The golden (:data:`GOLDEN_OBSERVATION_VERDICT`) was captured from ``master``'s
grader — *before* the scenario/strategy refactor — by running the known-good
reference parser through the real WP03 sandbox runner, then grading. It is the
frozen baseline, not a hand-authored expectation.

Test method (mirrors ``tests/test_grader.py``): build a real sandbox, install +
run the good reference parser through the subprocess runner so the warehouse
holds genuine boundary truth, capture provenance from the runner envelope, then
grade via :func:`premura.harness.scenario.observation_scenario`'s strategy and
assert the serialized verdict equals the golden exactly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import yaml

from premura.config import REPO_ROOT
from premura.harness import build_sandbox, install_parser
from premura.harness.grader import grade
from premura.harness.scenario import observation_scenario
from premura.store import duck
from tests import FIXTURES_DIR

FIXTURE_DIR = FIXTURES_DIR / "session_log"
GOOD_PARSER = FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
MANIFEST_PATH = FIXTURE_DIR / "fixture_fields.yaml"

# Committed fixtures ship with the mission; their absence is a HARD failure.
_missing = [p.name for p in (GOOD_PARSER, SYNTHETIC_CSV, MANIFEST_PATH) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed observation fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


# --------------------------------------------------------------------------- #
# T001 — the GOLDEN, captured from master's grader BEFORE the refactor.
# Captured by running the good reference parser through the real sandbox runner
# and grading with the pre-refactor grade(). Frozen here; do not hand-edit.
# --------------------------------------------------------------------------- #
GOLDEN_OBSERVATION_VERDICT: dict[str, Any] = {
    "passed": True,
    "rules": {
        "loaded": {
            "passed": True,
            "warehouse_rows": 5,
            "logged_rows_inserted": 5,
        },
        "runtime_valid": {
            "passed": True,
            "violations": [],
        },
        "honest_about_gaps": {
            "passed": True,
            "silent_drops": [],
        },
    },
}


@dataclass(slots=True)
class _Provenance:
    """Captured ingest evidence (satisfies grader.IngestProvenance structurally)."""

    declared_metrics: list[str]
    emitted_metric_ids: list[str]
    unmapped_metrics: list[str]
    skipped_rows: list[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool


def _run_runner_envelope(sandbox: Any, *, parser: str) -> dict[str, Any]:
    """Run the parser through the real WP03 subprocess runner; return its envelope."""
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


def _grade_observation_via_scenario() -> dict[str, Any]:
    """Run the good parser into a real sandbox and grade via the observation scenario."""
    sandbox = build_sandbox(REPO_ROOT)
    try:
        install_parser(sandbox, GOOD_PARSER, "src/premura/parsers/_sandbox_obs_golden.py")
        envelope = _run_runner_envelope(
            sandbox, parser="premura.parsers._sandbox_obs_golden:GoodFitbitHrParser"
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
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        conn = duck.connect(sandbox.warehouse_path, read_only=True)
        try:
            return grade(
                provenance=provenance,
                warehouse_conn=conn,
                fixture_manifest=manifest,
                strategy=observation_scenario().strategy,
            )
        finally:
            conn.close()
    finally:
        sandbox.teardown()


def test_observation_verdict_matches_golden_value() -> None:
    """The refactored grader reproduces the golden verdict as a dict (C-004)."""
    verdict = _grade_observation_via_scenario()
    assert verdict == GOLDEN_OBSERVATION_VERDICT


def test_observation_verdict_byte_identical_to_golden() -> None:
    """Serialized (sorted-key) verdict is BYTE-for-byte the golden (SC-006).

    Determinism rail: arrays sorted, no ids, no timestamps — so the canonical JSON
    serialization is reproducible across runs (D5 / NFR-001).
    """
    verdict = _grade_observation_via_scenario()
    assert json.dumps(verdict, sort_keys=True) == json.dumps(
        GOLDEN_OBSERVATION_VERDICT, sort_keys=True
    )


def test_default_strategy_reproduces_golden() -> None:
    """Omitting ``strategy`` defaults to observation → same golden (C-004).

    The default-keeps-call-sites-working seam: ``live_trial.py`` / ``repeatable_check.py``
    still call ``grade()`` with no ``strategy`` and must get observation behavior.
    """
    sandbox = build_sandbox(REPO_ROOT)
    try:
        install_parser(sandbox, GOOD_PARSER, "src/premura/parsers/_sandbox_obs_default.py")
        envelope = _run_runner_envelope(
            sandbox, parser="premura.parsers._sandbox_obs_default:GoodFitbitHrParser"
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
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        conn = duck.connect(sandbox.warehouse_path, read_only=True)
        try:
            verdict = grade(
                provenance=provenance,
                warehouse_conn=conn,
                fixture_manifest=manifest,
            )
        finally:
            conn.close()
    finally:
        sandbox.teardown()
    assert verdict == GOLDEN_OBSERVATION_VERDICT
