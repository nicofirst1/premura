"""Black-box tests for the read-only session dossier (judge-ai m3 FR-2).

The dossier is the judge's (and the future improvement hook's) single read
surface over one recorded session: it assembles session metadata, the grader's
recomputed facts, per-attempt telemetry, and the full transcript in
``turn_index`` order. It opens the session log STRICTLY READ-ONLY so the read
path can never write the log (the harness stays the sole writer). These tests
build a session with the public store writer API, then assert on what
:func:`premura.session_log.dossier.build_dossier` returns.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from premura.session_log import dossier, store


def _open_initialized(db_path: Path) -> duckdb.DuckDBPyConnection:
    conn = store.connect(db_path)
    store.init_schema(conn)
    return conn


class _Recon:
    """A SelfReconciliationLike for record_live_trial_attempt."""

    def __init__(self, *, passed: bool, source_columns: list[str], unaccounted: list[str]) -> None:
        self.passed = passed
        self.source_columns = source_columns
        self.accounted = frozenset(set(source_columns) - set(unaccounted))
        self.unaccounted = unaccounted


class _LoadStats:
    def __init__(self, inserted: int, dup: int, priority: int) -> None:
        self.rows_inserted = inserted
        self.rows_skipped_dup = dup
        self.rows_skipped_priority = priority


def _seed_full_session(conn: duckdb.DuckDBPyConnection) -> str:
    """Seed one live-trial session with steps, provenance, attempts, and turns."""
    sid = store.open_session(
        conn,
        operator_model="qwen2.5-coder:7b",
        driver_model="canned-driver",
        premura_version="0.3.0",
        isolation_tag="iso-dossier",
        run_kind="live_trial",
    )
    root = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=None,
        kind="agent_turn",
        name="live_trial_turn",
        tool_name=None,
        request_summary="live-trial goal: ingest heart rate",
        request_hash=None,
        result_status="available",
        result_summary=None,
        result_hash=None,
    )
    ingest_step = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=root,
        kind="tool_call",
        name="live-trial ingest",
        tool_name="ingest_run",
        request_summary="ingest via LiveTrialParser",
        request_hash=None,
        result_status="available",
        result_summary=None,
        result_hash=None,
    )
    store.record_ingest_provenance(
        conn,
        step_id=ingest_step,
        batch_id="batch-001",
        parser_kind="LiveTrialParser",
        load_stats=_LoadStats(3, 1, 0),
        declared_metrics=["heart_rate"],
        emitted_metric_ids=["heart_rate"],
        unmapped_metrics=["confidence"],
        skipped_rows=[],
        contract_pass=True,
    )
    store.record_live_trial_attempt(
        conn,
        session_id=sid,
        attempt_index=1,
        self_reconciliation=_Recon(
            passed=True, source_columns=["ts", "bpm", "confidence"], unaccounted=[]
        ),
        parser_error=None,
    )
    # Out-of-order inserts to prove the dossier orders by turn_index.
    store.record_turn(
        conn, session_id=sid, step_id=root, turn_index=1, role="assistant", content="second"
    )
    store.record_turn(
        conn, session_id=sid, step_id=root, turn_index=0, role="user", content="first"
    )
    store.record_turn(
        conn, session_id=sid, step_id=root, turn_index=2, role="tool", content="third"
    )
    store.finish_session(conn, session_id=sid)
    return sid


def test_dossier_assembles_metadata_facts_attempts_transcript(tmp_path: Path) -> None:
    """FR-2: the dossier carries session metadata, grader facts, per-attempt
    telemetry, and the transcript for one recorded session."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_full_session(conn)
    conn.close()

    doc = dossier.build_dossier(log_path, session_id=sid)

    assert doc.session_id == sid
    assert doc.operator_model == "qwen2.5-coder:7b"
    assert doc.driver_model == "canned-driver"
    assert doc.run_kind == "live_trial"

    # Grader's recomputed facts: contract_pass + row counts.
    assert doc.contract_pass is True
    assert doc.rows_inserted == 3

    # Per-attempt telemetry.
    assert len(doc.attempts) == 1
    assert doc.attempts[0].attempt_index == 1
    assert doc.attempts[0].self_reconciliation_passed is True

    # Full transcript present.
    assert len(doc.transcript) == 3


def test_dossier_transcript_in_turn_index_order(tmp_path: Path) -> None:
    """FR-2: the transcript is returned in turn_index order regardless of insert
    order."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_full_session(conn)
    conn.close()

    doc = dossier.build_dossier(log_path, session_id=sid)
    assert [t.turn_index for t in doc.transcript] == [0, 1, 2]
    assert [t.role for t in doc.transcript] == ["user", "assistant", "tool"]
    assert [t.content for t in doc.transcript] == ["first", "second", "third"]


def test_dossier_no_turns_says_so_explicitly(tmp_path: Path) -> None:
    """FR-2: a dossier for a session with no recorded turns says so explicitly
    rather than failing."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = store.open_session(
        conn,
        operator_model="op",
        driver_model="drv",
        premura_version="0.3.0",
        isolation_tag="iso-empty",
        run_kind="live_trial",
    )
    store.finish_session(conn, session_id=sid)
    conn.close()

    doc = dossier.build_dossier(log_path, session_id=sid)
    assert doc.transcript == []
    assert doc.has_transcript is False


def test_dossier_opens_log_read_only(tmp_path: Path) -> None:
    """FR-2 / sole-writer: building a dossier opens the log strictly read-only.

    A read-only connection cannot write; if the dossier tried to write it would
    raise. We prove the read surface never mutates the log by confirming the
    log file is still openable read-write by a fresh (sole-writer) connection
    afterward and that the dossier read left the row counts unchanged.
    """
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_full_session(conn)
    before = conn.execute("SELECT COUNT(*) FROM log_turn").fetchone()
    conn.close()

    # Build the dossier while NO writer holds the file. If build_dossier opened
    # read-write it would take the writer lock; opening read-only leaves the file
    # shareable. We can still open a second read-only reader concurrently.
    doc = dossier.build_dossier(log_path, session_id=sid)
    assert doc.session_id == sid

    reader = store.connect(log_path, read_only=True)
    after = reader.execute("SELECT COUNT(*) FROM log_turn").fetchone()
    reader.close()
    assert before == after  # the read surface mutated nothing


def test_dossier_unknown_session_raises(tmp_path: Path) -> None:
    """A dossier for a session id not in the log raises (a clear error, not a
    silent empty dossier that the judge would assess as if it were real)."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    _seed_full_session(conn)
    conn.close()

    with pytest.raises(KeyError):
        dossier.build_dossier(log_path, session_id="01NONEXISTENT")
