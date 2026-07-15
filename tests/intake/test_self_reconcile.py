"""WP01 — manifest-blind self-reconciliation gate (FR-003 / C-005).

Default-collected (no model server). Proves the gate:

* reads the ground set from the FILE header, not the parser's behaviour;
* closes the "lazy parser skips a column" loophole (a column the parser ignored
  AND never declared still fails);
* is equivalent to the grader's ``honest_about_gaps`` rule on the committed
  fixture — the gate never imports the manifest, but the test may, to assert the
  two compute the same silent-drop check (header vs manifest).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import yaml

from premura.harness.grader import _grade_honest_about_gaps
from premura.harness.self_reconcile import SelfReconciliationResult, self_reconcile
from premura.parsers.base import IngestBatch, SkippedRow
from tests import FIXTURES_DIR

FIXTURE_DIR = FIXTURES_DIR / "session_log"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
MANIFEST_PATH = FIXTURE_DIR / "fixture_fields.yaml"

# The fixture is committed with the mission; its absence is a HARD failure, never
# a skip — a vanished committed fixture must block the gate, not pass green.
for _required in (SYNTHETIC_CSV, MANIFEST_PATH):
    if not _required.exists():
        raise FileNotFoundError(
            f"Committed session-log fixture missing: {_required.name}. "
            "It ships with the mission; its absence must fail the suite, not skip it."
        )


def _batch(*, unmapped: list[str], skipped: list[str] | None = None) -> IngestBatch:
    """An IngestBatch carrying only the declared-gap fields the gate consults."""
    return IngestBatch(
        source_kind="fitbit_heart_rate",
        declared_metrics=["heart_rate"],
        unmapped_metrics=list(unmapped),
        skipped_rows=[
            SkippedRow(raw_field=field, reason="declared gap") for field in (skipped or [])
        ],
    )


# --------------------------------------------------------------------------- #
# T003.1 — honest parser passes; ground set comes from the file header.
# --------------------------------------------------------------------------- #


def test_honest_parser_passes() -> None:
    batch = _batch(unmapped=["timestamp", "confidence", "altitude_m"])

    result = self_reconcile(SYNTHETIC_CSV, batch, mapped_columns={"bpm"})

    assert isinstance(result, SelfReconciliationResult)
    assert result.passed is True
    assert result.unaccounted == []
    # Ground set is read from the file header verbatim (sorted for determinism).
    assert result.source_columns == ["altitude_m", "bpm", "confidence", "timestamp"]
    assert result.passed == (result.unaccounted == [])


# --------------------------------------------------------------------------- #
# T003.2 — silent drop fails: a column neither mapped nor declared is caught.
# --------------------------------------------------------------------------- #


def test_silent_drop_fails() -> None:
    # altitude_m is omitted from unmapped: a silent drop.
    batch = _batch(unmapped=["timestamp", "confidence"])

    result = self_reconcile(SYNTHETIC_CSV, batch, mapped_columns={"bpm"})

    assert result.passed is False
    assert result.unaccounted == ["altitude_m"]


# --------------------------------------------------------------------------- #
# T003.3 — loophole closed: the ground set is the FILE header, not the columns
# the parser read. A parser that simply ignores `confidence` (never maps it,
# never declares it) must fail even though its own batch looks clean.
# --------------------------------------------------------------------------- #


def test_lazy_parser_loophole_closed() -> None:
    # Parser mapped only bpm and declared only timestamp/altitude_m; it silently
    # ignored `confidence` entirely. The batch alone would never reveal this.
    batch = _batch(unmapped=["timestamp", "altitude_m"])

    result = self_reconcile(SYNTHETIC_CSV, batch, mapped_columns={"bpm"})

    assert result.passed is False
    assert "confidence" in result.unaccounted
    assert result.unaccounted == ["confidence"]


def test_mapped_and_declared_column_not_double_penalized() -> None:
    # A column both mapped AND listed as unmapped is still simply accounted.
    batch = _batch(unmapped=["timestamp", "confidence", "altitude_m", "bpm"])

    result = self_reconcile(SYNTHETIC_CSV, batch, mapped_columns={"bpm"})

    assert result.passed is True
    assert result.unaccounted == []


def test_empty_or_headerless_file_is_not_a_silent_pass(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    batch = _batch(unmapped=[])

    result = self_reconcile(empty, batch, mapped_columns=set())

    # No ground set means honesty cannot be proven -> hard fail, never silent pass.
    assert result.passed is False
    assert result.source_columns == []


# --------------------------------------------------------------------------- #
# T003.4 — grader equivalence on the committed fixture.
#
# The gate reads the header; the grader reads the manifest + warehouse. For the
# honest batch both must agree. We build the minimal warehouse view the grader's
# honesty rule consults (DISTINCT metric_id over the fact tables) directly, so
# the test stays default-collected and fast while exercising the REAL grader
# function. The gate never imports the manifest; this test may.
# --------------------------------------------------------------------------- #


class _Provenance:
    """Captured evidence satisfying grader.IngestProvenance structurally."""

    def __init__(self, *, unmapped: list[str], skipped: list[str]) -> None:
        self.declared_metrics: list[str] = ["heart_rate"]
        self.emitted_metric_ids: list[str] = ["heart_rate"]
        self.unmapped_metrics: list[str] = unmapped
        self.skipped_rows: list[dict[str, Any]] = [
            {"raw_field": field, "reason": "declared gap"} for field in skipped
        ]
        self.rows_inserted: int = 1
        self.ingest_run_ok: bool = True


def _warehouse_with_metric(metric_id: str) -> duckdb.DuckDBPyConnection:
    """Minimal in-memory warehouse exposing one loaded metric to the grader.

    The grader's honesty rule only runs ``COUNT(*)`` / ``SELECT DISTINCT
    metric_id`` over ``hp.fact_measurement`` / ``hp.fact_interval``; a bare table
    with a ``metric_id`` column is sufficient ground truth.
    """
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA hp")
    conn.execute("CREATE TABLE hp.fact_measurement (metric_id VARCHAR)")
    conn.execute("CREATE TABLE hp.fact_interval (metric_id VARCHAR)")
    conn.execute("INSERT INTO hp.fact_measurement VALUES (?)", [metric_id])
    return conn


def test_grader_equivalence_on_fixture() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    unmapped = ["timestamp", "confidence", "altitude_m"]

    gate = self_reconcile(SYNTHETIC_CSV, _batch(unmapped=unmapped), mapped_columns={"bpm"})

    conn = _warehouse_with_metric("heart_rate")
    try:
        grader = _grade_honest_about_gaps(
            _Provenance(unmapped=unmapped, skipped=[]),
            conn,
            manifest,
        )
    finally:
        conn.close()

    # Both honest views agree the parser is honest about its gaps.
    assert gate.passed is True
    assert grader["passed"] is True
    assert gate.passed == grader["passed"]


def test_grader_equivalence_on_fixture_silent_drop() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    # Drop altitude_m from declarations: both gate and grader must flag it.
    unmapped = ["timestamp", "confidence"]

    gate = self_reconcile(SYNTHETIC_CSV, _batch(unmapped=unmapped), mapped_columns={"bpm"})

    conn = _warehouse_with_metric("heart_rate")
    try:
        grader = _grade_honest_about_gaps(
            _Provenance(unmapped=unmapped, skipped=[]),
            conn,
            manifest,
        )
    finally:
        conn.close()

    assert gate.passed is False
    assert grader["passed"] is False
    assert gate.passed == grader["passed"]
    assert "altitude_m" in gate.unaccounted
    assert "altitude_m" in grader["silent_drops"]
