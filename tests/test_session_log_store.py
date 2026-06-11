"""Black-box tests for the session-log store (WP01).

These exercise the **public writer API** of ``premura.session_log.store`` and
assert on what a later reader sees in the session-log **file** (DuckDB rows,
raised exceptions), never on internal collaborators. The store is the substrate
WP03/WP05/WP06 consume; its observable shape is what those packages depend on.

Fidelity coverage map (reviewers check each):

* FR-070 / C-001 — the session log is its **own** local DuckDB file, applied by
  the package's own ``init_schema`` (idempotent), separate from the warehouse and
  from ``trace.*``: ``test_own_file_separate_from_warehouse_and_trace``,
  ``test_init_schema_idempotent``.
* FR-003 — fixed ``result_status`` vocabulary: ``test_result_status_vocab``.
* FR-032 — fixed ``run_kind`` vocabulary: ``test_run_kind_vocab``.
* ``kind`` vocabulary (data-model): ``test_step_kind_vocab``.
* FR-010..FR-013 — two-origin ingest provenance (loader-measured ints vs parser
  claims), declared vs emitted as separate captured sets, grader-only
  ``contract_pass``: ``test_ingest_provenance_two_origin_round_trip``,
  ``test_contract_pass_is_caller_supplied``.
* FR-031/FR-032 — session captures operator_model/driver_model/run_kind/
  premura_version/isolation_tag: ``test_session_captures_run_identity``.
* FR-021 / NFR-008 — single writer: ``test_single_writer``.
* FR-080 — steps + ingest outcome reachable from the log alone:
  ``test_session_and_steps_round_trip``.
* NFR-003 — zero new third-party deps: ``test_no_new_third_party_dependency``.
* FR-005 (config) — ``session_log_path`` sibling of ``warehouse_path``:
  ``test_config_session_log_path``.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from premura.config import settings
from premura.session_log import store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_initialized(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Open one writable session-log connection and apply the schema."""
    conn = store.connect(db_path)
    store.init_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# Schema / own-file fidelity (FR-070 / C-001)
# ---------------------------------------------------------------------------


def test_init_schema_idempotent(tmp_path: Path) -> None:
    conn = store.connect(tmp_path / "session_log.duckdb")
    store.init_schema(conn)
    # Re-applying must be a no-op (CREATE IF NOT EXISTS), not raise.
    store.init_schema(conn)
    tables = {
        row[0]
        for row in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
    }
    assert {
        "log_session",
        "log_step",
        "log_ingest_provenance",
        "log_live_trial_attempt",
        "log_turn",
    } <= tables
    conn.close()


def test_own_file_separate_from_warehouse_and_trace(tmp_path: Path) -> None:
    """The log lives in its own file and never creates trace.* / hp.* schemas."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = store.open_session(
        conn,
        operator_model="op-model",
        driver_model="drv-model",
        premura_version="0.3.0",
        isolation_tag="sandbox-xyz",
        run_kind="repeatable_check",
    )
    store.finish_session(conn, session_id=sid)
    conn.close()

    # The file exists on its own.
    assert log_path.exists()

    # Re-open read-only and confirm only the log tables exist; no trace/hp schema.
    ro = store.connect(log_path, read_only=True)
    schemas = {
        row[0]
        for row in ro.execute(
            "SELECT DISTINCT table_schema FROM information_schema.tables"
        ).fetchall()
    }
    assert "trace" not in schemas
    assert "hp" not in schemas
    ro.close()


# ---------------------------------------------------------------------------
# Session + step round-trip (FR-080)
# ---------------------------------------------------------------------------


def test_session_captures_run_identity(tmp_path: Path) -> None:
    """FR-031/FR-032: the five run-identity fields persist verbatim."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = store.open_session(
        conn,
        operator_model="claude:operator",
        driver_model="fake:scripted-driver",
        premura_version="0.3.0",
        isolation_tag="iso-001",
        run_kind="live_trial",
    )
    row = conn.execute(
        """
        SELECT operator_model, driver_model, premura_version, isolation_tag,
               run_kind, finished_at
        FROM log_session WHERE session_id = ?
        """,
        [sid],
    ).fetchone()
    assert row is not None
    assert row[0] == "claude:operator"
    assert row[1] == "fake:scripted-driver"
    assert row[2] == "0.3.0"
    assert row[3] == "iso-001"
    assert row[4] == "live_trial"
    assert row[5] is None  # not finished yet
    conn.close()


def test_session_and_steps_round_trip(tmp_path: Path) -> None:
    """A parent agent_turn with a child ingest_run tool_call, read from the file."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = store.open_session(
        conn,
        operator_model="op",
        driver_model="drv",
        premura_version="0.3.0",
        isolation_tag="iso",
        run_kind="repeatable_check",
    )
    parent = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=None,
        kind="agent_turn",
        name="turn-1",
        tool_name=None,
        request_summary="operator turn",
        request_hash="rh-parent",
        result_status="available",
        result_summary="ok",
        result_hash="reh-parent",
    )
    child = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=parent,
        kind="tool_call",
        name="ingest",
        tool_name="ingest_run",
        request_summary="ingest fitbit",
        request_hash="rh-child",
        result_status="available",
        result_summary="loaded 3 rows",
        result_hash="reh-child",
    )
    store.finish_session(conn, session_id=sid)
    conn.close()

    # Reopen the FILE and reconstruct the verdict path from the log alone.
    ro = store.connect(log_path, read_only=True)
    finished = ro.execute(
        "SELECT finished_at FROM log_session WHERE session_id = ?", [sid]
    ).fetchone()
    assert finished is not None and finished[0] is not None

    steps = ro.execute(
        """
        SELECT step_id, parent_step_id, kind, name, tool_name, result_status
        FROM log_step WHERE session_id = ? ORDER BY started_at, step_id
        """,
        [sid],
    ).fetchall()
    by_id = {r[0]: r for r in steps}
    assert by_id[parent][1] is None  # parent has no parent
    assert by_id[parent][2] == "agent_turn"
    assert by_id[child][1] == parent  # child points at parent (the tree)
    assert by_id[child][2] == "tool_call"
    assert by_id[child][4] == "ingest_run"  # verdict-bearing step
    assert by_id[child][5] == "available"
    ro.close()


# ---------------------------------------------------------------------------
# Enum boundary validation
# ---------------------------------------------------------------------------


def _new_session(conn: duckdb.DuckDBPyConnection) -> str:
    return store.open_session(
        conn,
        operator_model="op",
        driver_model="drv",
        premura_version="0.3.0",
        isolation_tag="iso",
        run_kind="repeatable_check",
    )


def test_result_status_vocab(tmp_path: Path) -> None:
    """FR-003: result_status is the fixed six-value vocabulary; others raise."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    for status in ("available", "missing", "stale", "insufficient", "refused", "error"):
        sid_step = store.record_step(
            conn,
            session_id=sid,
            parent_step_id=None,
            kind="tool_call",
            name="s",
            tool_name="ingest_run",
            request_summary=None,
            request_hash=None,
            result_status=status,
            result_summary=None,
            result_hash=None,
        )
        assert sid_step  # accepted

    with pytest.raises(ValueError):
        store.record_step(
            conn,
            session_id=sid,
            parent_step_id=None,
            kind="tool_call",
            name="s",
            tool_name="ingest_run",
            request_summary=None,
            request_hash=None,
            result_status="success",  # not in the fixed vocabulary
            result_summary=None,
            result_hash=None,
        )
    conn.close()


def test_run_kind_vocab(tmp_path: Path) -> None:
    """FR-032: run_kind is {repeatable_check, live_trial}; others raise."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    for rk in ("repeatable_check", "live_trial"):
        assert store.open_session(
            conn,
            operator_model="op",
            driver_model="drv",
            premura_version="0.3.0",
            isolation_tag="iso",
            run_kind=rk,
        )
    with pytest.raises(ValueError):
        store.open_session(
            conn,
            operator_model="op",
            driver_model="drv",
            premura_version="0.3.0",
            isolation_tag="iso",
            run_kind="benchmark",  # not allowed
        )
    conn.close()


def test_step_kind_vocab(tmp_path: Path) -> None:
    """kind ∈ {agent_turn, model_call, tool_call}; others raise."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    for kind in ("agent_turn", "model_call", "tool_call"):
        assert store.record_step(
            conn,
            session_id=sid,
            parent_step_id=None,
            kind=kind,
            name="s",
            tool_name=None,
            request_summary=None,
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )
    with pytest.raises(ValueError):
        store.record_step(
            conn,
            session_id=sid,
            parent_step_id=None,
            kind="span",  # not allowed
            name="s",
            tool_name=None,
            request_summary=None,
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )
    conn.close()


# ---------------------------------------------------------------------------
# Ingest provenance: two-origin split (FR-010..FR-013, FR-061/FR-065)
# ---------------------------------------------------------------------------


class _FakeLoadStats:
    """A LoadStatsLike: the three loader-measured ints the writer reads."""

    def __init__(self, inserted: int, dup: int, priority: int) -> None:
        self.rows_inserted = inserted
        self.rows_skipped_dup = dup
        self.rows_skipped_priority = priority


def test_ingest_provenance_two_origin_round_trip(tmp_path: Path) -> None:
    """Loader-measured ints land as columns; parser claims + declared/emitted
    land as distinct JSON sets; all decode back to the inputs (FR-010..FR-013)."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    step = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=None,
        kind="tool_call",
        name="ingest",
        tool_name="ingest_run",
        request_summary=None,
        request_hash=None,
        result_status="available",
        result_summary=None,
        result_hash=None,
    )

    declared = ["heart_rate"]
    emitted = ["heart_rate"]
    unmapped = ["confidence", "altitude_m"]
    skipped = [{"raw_field": "bpm", "reason": "bad row"}]

    store.record_ingest_provenance(
        conn,
        step_id=step,
        batch_id="batch-001",
        parser_kind="good_fitbit_hr",
        load_stats=_FakeLoadStats(3, 1, 2),
        declared_metrics=declared,
        emitted_metric_ids=emitted,
        unmapped_metrics=unmapped,
        skipped_rows=skipped,
        contract_pass=True,
    )
    conn.close()

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        """
        SELECT step_id, batch_id, parser_kind,
               rows_inserted, rows_skipped_dup, rows_skipped_priority,
               declared_metrics_json, emitted_metric_ids_json,
               unmapped_metrics_json, skipped_rows_json, contract_pass
        FROM log_ingest_provenance WHERE step_id = ?
        """,
        [step],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == step
    assert row[1] == "batch-001"
    assert row[2] == "good_fitbit_hr"
    # Loader-measured ints are authoritative columns.
    assert (row[3], row[4], row[5]) == (3, 1, 2)
    # The four list fields decode from JSON to the exact inputs.
    assert json.loads(row[6]) == declared
    assert json.loads(row[7]) == emitted
    assert json.loads(row[8]) == unmapped
    assert json.loads(row[9]) == skipped
    # declared and emitted are SEPARATE captured sets (distinct columns).
    assert row[6] != row[8]  # declared distinct from unmapped-claim
    assert bool(row[10]) is True


def test_contract_pass_is_caller_supplied(tmp_path: Path) -> None:
    """contract_pass is persisted exactly as the caller (the grader) supplies it;
    this WP has no other source for it (FR-061/FR-065)."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    step = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=None,
        kind="tool_call",
        name="ingest",
        tool_name="ingest_run",
        request_summary=None,
        request_hash=None,
        result_status="error",
        result_summary=None,
        result_hash=None,
    )
    store.record_ingest_provenance(
        conn,
        step_id=step,
        batch_id="b",
        parser_kind="p",
        load_stats=_FakeLoadStats(0, 0, 0),
        declared_metrics=[],
        emitted_metric_ids=[],
        unmapped_metrics=[],
        skipped_rows=[],
        contract_pass=False,
    )
    conn.close()

    ro = store.connect(log_path, read_only=True)
    val = ro.execute(
        "SELECT contract_pass FROM log_ingest_provenance WHERE step_id = ?", [step]
    ).fetchone()
    ro.close()
    assert val is not None and bool(val[0]) is False


def test_live_trial_attempt_round_trip(tmp_path: Path) -> None:
    """FR-008: per-attempt self-reconciliation telemetry persists in the session log."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = store.open_session(
        conn,
        operator_model="cheap-op",
        driver_model="cheap-driver",
        premura_version="0.3.0",
        isolation_tag="iso-attempt",
        run_kind="live_trial",
    )

    class _Recon:
        passed = False
        source_columns = ["logged_at_us", "note"]
        accounted = frozenset({"logged_at_us"})
        unaccounted = ["note"]

    attempt_id = store.record_live_trial_attempt(
        conn,
        session_id=sid,
        attempt_index=1,
        self_reconciliation=_Recon(),
        parser_error="parse: synthetic parser failure",
    )
    conn.close()

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        """
        SELECT attempt_id, attempt_index, self_reconciliation_passed,
               source_columns_json, accounted_json, unaccounted_json, parser_error
        FROM log_live_trial_attempt
        WHERE session_id = ?
        ORDER BY attempt_index
        """,
        [sid],
    ).fetchone()
    ro.close()

    assert row is not None
    assert row[0] == attempt_id
    assert row[1] == 1
    assert bool(row[2]) is False
    assert json.loads(row[3]) == ["logged_at_us", "note"]
    assert json.loads(row[4]) == ["logged_at_us"]
    assert json.loads(row[5]) == ["note"]
    assert row[6] == "parse: synthetic parser failure"


# ---------------------------------------------------------------------------
# Conversation-turn capture (m2 FR-1)
# ---------------------------------------------------------------------------


def test_record_turn_round_trip(tmp_path: Path) -> None:
    """FR-1: a recorded turn replays from the log alone with all its fields.

    The transcript is what the judge-AI follow-on reads; a round-trip through
    the file is the contract. The optional per-turn telemetry (``tool_name`` /
    ``model`` / ``token_count``) is persisted exactly as supplied.
    """
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    step_id = store.record_step(
        conn,
        session_id=sid,
        parent_step_id=None,
        kind="agent_turn",
        name="turn",
        tool_name=None,
        request_summary=None,
        request_hash=None,
        result_status="available",
        result_summary=None,
        result_hash=None,
    )

    turn_id = store.record_turn(
        conn,
        session_id=sid,
        step_id=step_id,
        turn_index=0,
        role="assistant",
        content="here is the parser I wrote",
        tool_name="write_parser",
        model="qwen2.5-coder:7b",
        token_count=42,
    )
    conn.close()

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        """
        SELECT turn_id, session_id, step_id, turn_index, role, content,
               tool_name, model, token_count
        FROM log_turn
        WHERE session_id = ?
        ORDER BY turn_index
        """,
        [sid],
    ).fetchone()
    ro.close()

    assert row is not None
    assert row[0] == turn_id
    assert row[1] == sid
    assert row[2] == step_id
    assert row[3] == 0
    assert row[4] == "assistant"
    assert row[5] == "here is the parser I wrote"
    assert row[6] == "write_parser"
    assert row[7] == "qwen2.5-coder:7b"
    assert row[8] == 42


def test_turn_role_vocab(tmp_path: Path) -> None:
    """FR-1: role is the fixed four-value vocabulary; others raise ValueError.

    Mirrors the ``result_status`` / ``run_kind`` / ``kind`` boundary checks: an
    out-of-vocabulary role is rejected at the store seam, never silently stored.
    """
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    for index, role in enumerate(sorted(store.TURN_ROLES)):
        tid = store.record_turn(
            conn,
            session_id=sid,
            step_id=None,
            turn_index=index,
            role=role,
            content="ok",
        )
        assert tid  # accepted
    assert store.TURN_ROLES == frozenset({"system", "user", "assistant", "tool"})
    with pytest.raises(ValueError, match="role"):
        store.record_turn(
            conn,
            session_id=sid,
            step_id=None,
            turn_index=99,
            role="developer",  # chat-API role NOT in the vocabulary
            content="should be rejected",
        )
    conn.close()


def test_turn_index_unique_per_session(tmp_path: Path) -> None:
    """FR-1: (session_id, turn_index) is unique — a slot cannot be reused.

    The ordered transcript cannot hold a duplicate position; a second write at
    the same index for the same session is rejected by the DB constraint.
    """
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    store.record_turn(
        conn, session_id=sid, step_id=None, turn_index=0, role="user", content="first"
    )
    with pytest.raises(duckdb.ConstraintException):
        store.record_turn(
            conn, session_id=sid, step_id=None, turn_index=0, role="assistant", content="dup slot"
        )
    conn.close()


def test_turn_index_independent_across_sessions(tmp_path: Path) -> None:
    """FR-1: the same turn_index in a DIFFERENT session is allowed.

    Uniqueness is per-session, so two sessions can each hold their own index 0.
    """
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid_a = _new_session(conn)
    sid_b = _new_session(conn)
    store.record_turn(conn, session_id=sid_a, step_id=None, turn_index=0, role="user", content="a")
    # Same index, other session — must NOT collide.
    tid_b = store.record_turn(
        conn, session_id=sid_b, step_id=None, turn_index=0, role="user", content="b"
    )
    assert tid_b
    conn.close()


def test_record_turn_nullable_step_and_optionals(tmp_path: Path) -> None:
    """FR-1: step_id and the optional telemetry are nullable.

    A turn need not be linked to a step, and the per-turn telemetry fields default
    to NULL when omitted — the transcript stays minimal for tiers that have none.
    """
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    store.record_turn(
        conn, session_id=sid, step_id=None, turn_index=0, role="system", content="system prompt"
    )
    conn.close()

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT step_id, tool_name, model, token_count FROM log_turn WHERE session_id = ?",
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row == (None, None, None, None)


# ---------------------------------------------------------------------------
# Single writer (FR-021 / NFR-008)
# ---------------------------------------------------------------------------


def test_single_writer(tmp_path: Path) -> None:
    """No second OS process can open the file for writing while the harness holds it.

    The single-writer invariant (FR-021 / NFR-008) is across *processes*: the
    parent harness is the sole writer, and the subprocess runner never opens this
    file. DuckDB enforces this at the file lock level — a *separate* process that
    tries to open the same file read-write while the harness holds a writable
    connection is rejected. (Within one process DuckDB shares the instance, so the
    meaningful guarantee — and the one this WP's design depends on — is the
    cross-process lock proven here.) Black-box: we open one writable conn through
    the public ``connect``, then prove a fresh interpreter cannot also open it
    writable, while a read-only reader still works.
    """
    log_path = tmp_path / "session_log.duckdb"
    writer = _open_initialized(log_path)
    sid = _new_session(writer)
    assert sid
    # The transcript table is written only through this sole writable connection
    # (NFR-1): record a turn so the cross-process lock below also guards log_turn.
    writer_turn = store.record_turn(
        writer,
        session_id=sid,
        step_id=None,
        turn_index=0,
        role="user",
        content="synthetic single-writer probe turn",
    )
    assert writer_turn

    # A second OS process opening the same file read-write must be rejected while
    # the harness holds the writable connection (the subprocess runner is denied a
    # writer handle by construction).
    probe = (
        "import sys, duckdb\n"
        "try:\n"
        f"    duckdb.connect({str(log_path)!r}, read_only=False)\n"
        "    sys.exit(0)\n"  # opened -> single-writer NOT enforced
        "except duckdb.Error:\n"
        "    sys.exit(7)\n"  # rejected -> single-writer enforced
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 7, (
        "a second process acquired a writer handle while the harness held one: "
        f"rc={result.returncode} stderr={result.stderr!r}"
    )

    # After the sole writer releases the file, a read-only reader sees the
    # committed row — confirming the write was durable and the file is shareable
    # once the single writer is done.
    writer.close()
    reader = store.connect(log_path, read_only=True)
    count = reader.execute("SELECT COUNT(*) FROM log_session").fetchone()
    assert count is not None and count[0] == 1
    # The turn written through the sole writer is durable too (NFR-1).
    turn_count = reader.execute(
        "SELECT COUNT(*) FROM log_turn WHERE session_id = ?", [sid]
    ).fetchone()
    assert turn_count is not None and turn_count[0] == 1
    reader.close()


# ---------------------------------------------------------------------------
# Zero new dependencies (NFR-003)
# ---------------------------------------------------------------------------


def test_no_new_third_party_dependency() -> None:
    """The store imports only stdlib + already-declared deps (duckdb, ulid).

    Static import audit over store.py so a new runtime dependency cannot slip in
    unnoticed (NFR-003). Allowed third-party top-level modules are the ones the
    project already declares.
    """
    src = Path(store.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    allowed_third_party = {"duckdb", "ulid"}
    stdlib_seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in allowed_third_party:
                    stdlib_seen.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top in {"premura", "__future__"}:
                    continue
                if top not in allowed_third_party:
                    stdlib_seen.add(top)
    # Anything not in allowed_third_party must be importable from stdlib.
    import importlib.util

    for mod in stdlib_seen:
        spec = importlib.util.find_spec(mod)
        assert spec is not None, f"unexpected non-stdlib import: {mod}"
        origin = spec.origin or ""
        assert "site-packages" not in origin, f"third-party import not allowed: {mod}"


# ---------------------------------------------------------------------------
# Config path (FR-005)
# ---------------------------------------------------------------------------


def test_config_session_log_path() -> None:
    """session_log_path is a sibling of warehouse_path under duck_dir (additive)."""
    assert settings.session_log_path == settings.duck_dir / "session_log.duckdb"
    assert settings.session_log_path.parent == settings.warehouse_path.parent
    assert settings.session_log_path != settings.warehouse_path
