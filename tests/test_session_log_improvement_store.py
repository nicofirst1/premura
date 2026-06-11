"""Black-box tests for the improvement-proposal store surface (m4 WP1, FR-1/FR-2).

These exercise the **public writer + read API** of ``premura.session_log.store``
and the read surface in ``premura.session_log.improvement_read`` for the
``log_improvement`` table the improvement hook fills. They assert on what a later
reader sees in the session-log **file** (DuckDB rows, raised exceptions), never on
internal collaborators — the same discipline as ``test_session_log_store.py``.

Fidelity coverage map (reviewers check each):

* FR-1 — ``log_improvement`` schema + ``PROPOSAL_STATUSES`` +
  ``record_improvement`` validation: ``test_record_improvement_round_trip``,
  ``test_proposal_status_vocab``, ``test_record_improvement_rejects_empty_fields``,
  ``test_record_improvement_requires_existing_session_and_judgment``.
* FR-2 — read surfaces (frozen dataclass rows, deterministic order):
  ``test_read_improvements_*``, ``test_read_judgments_*``.
* NFR-1 — read surfaces open read-only: ``test_read_surfaces_open_read_only``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from premura.session_log import improvement_read, store


def _open_initialized(db_path: Path) -> duckdb.DuckDBPyConnection:
    conn = store.connect(db_path)
    store.init_schema(conn)
    return conn


def _new_session(conn: duckdb.DuckDBPyConnection) -> str:
    return store.open_session(
        conn,
        operator_model="op",
        driver_model="drv",
        premura_version="0.3.0",
        isolation_tag="iso",
        run_kind="live_trial",
    )


def _new_judgment(conn: duckdb.DuckDBPyConnection, session_id: str) -> str:
    return store.record_judgment(
        conn,
        session_id=session_id,
        judge_model="m",
        rubric_version="2026-06-11.1",
        status="complete",
        criteria={"economical-tool-use": {"band": "weak", "rationale": "thrashed"}},
        overall_band="weak",
    )


# ---------------------------------------------------------------------------
# FR-1 — record_improvement
# ---------------------------------------------------------------------------


def test_record_improvement_round_trip(tmp_path: Path) -> None:
    """A recorded proposal replays from the log alone with every field intact."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    jid = _new_judgment(conn, sid)

    improvement_id = store.record_improvement(
        conn,
        session_id=sid,
        judgment_id=jid,
        criterion_id="economical-tool-use",
        area="tool_use_economy",
        summary="the operator keeps failing economical-tool-use",
        evidence="thrashed",
        playbook_version="2026-06-11.1",
        status="open",
    )
    assert improvement_id
    conn.close()

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        """
        SELECT improvement_id, session_id, judgment_id, criterion_id, area,
               summary, evidence, playbook_version, status
        FROM log_improvement WHERE session_id = ?
        """,
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == improvement_id
    assert row[1] == sid
    assert row[2] == jid
    assert row[3] == "economical-tool-use"
    assert row[4] == "tool_use_economy"
    assert row[5] == "the operator keeps failing economical-tool-use"
    assert row[6] == "thrashed"
    assert row[7] == "2026-06-11.1"
    assert row[8] == "open"


def test_record_improvement_allows_null_criterion(tmp_path: Path) -> None:
    """criterion_id is nullable: a judgment-level proposal carries no criterion."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    jid = _new_judgment(conn, sid)
    iid = store.record_improvement(
        conn,
        session_id=sid,
        judgment_id=jid,
        criterion_id=None,
        area="harness_reliability",
        summary="the judgment did not complete",
        evidence="status=unparseable",
        playbook_version="2026-06-11.1",
        status="open",
    )
    assert iid
    row = conn.execute(
        "SELECT criterion_id FROM log_improvement WHERE improvement_id = ?", [iid]
    ).fetchone()
    assert row is not None and row[0] is None
    conn.close()


def test_proposal_status_vocab(tmp_path: Path) -> None:
    """FR-1: status is the fixed PROPOSAL_STATUSES vocabulary; others raise.

    Mirrors the existing store boundary checks (``result_status`` / ``run_kind`` /
    ``status``). The other two statuses exist now so a later lifecycle mission
    needs no schema migration; this mission only ever writes ``open``.
    """
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    jid = _new_judgment(conn, sid)
    assert store.PROPOSAL_STATUSES == frozenset({"open", "dismissed", "addressed"})
    for status in sorted(store.PROPOSAL_STATUSES):
        iid = store.record_improvement(
            conn,
            session_id=sid,
            judgment_id=jid,
            criterion_id=None,
            area="harness_reliability",
            summary="s",
            evidence="e",
            playbook_version="v1",
            status=status,
        )
        assert iid
    with pytest.raises(ValueError, match="status"):
        store.record_improvement(
            conn,
            session_id=sid,
            judgment_id=jid,
            criterion_id=None,
            area="harness_reliability",
            summary="s",
            evidence="e",
            playbook_version="v1",
            status="acted",  # not in the vocabulary
        )
    conn.close()


@pytest.mark.parametrize("blank_field", ["summary", "evidence", "area"])
def test_record_improvement_rejects_empty_fields(tmp_path: Path, blank_field: str) -> None:
    """FR-1: summary / evidence / area must be non-empty; a blank raises."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    jid = _new_judgment(conn, sid)
    kwargs = {
        "session_id": sid,
        "judgment_id": jid,
        "criterion_id": None,
        "area": "harness_reliability",
        "summary": "s",
        "evidence": "e",
        "playbook_version": "v1",
        "status": "open",
    }
    kwargs[blank_field] = "   "  # whitespace-only is empty
    with pytest.raises(ValueError, match=blank_field):
        store.record_improvement(conn, **kwargs)  # type: ignore[arg-type]
    conn.close()


def test_record_improvement_requires_existing_session(tmp_path: Path) -> None:
    """FR-1: an unknown session id is rejected (referenced session must exist)."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    jid = _new_judgment(conn, sid)
    with pytest.raises(ValueError, match="session"):
        store.record_improvement(
            conn,
            session_id="no-such-session",
            judgment_id=jid,
            criterion_id=None,
            area="harness_reliability",
            summary="s",
            evidence="e",
            playbook_version="v1",
            status="open",
        )
    conn.close()


def test_record_improvement_requires_existing_judgment(tmp_path: Path) -> None:
    """FR-1: an unknown judgment id is rejected (referenced judgment must exist)."""
    conn = _open_initialized(tmp_path / "session_log.duckdb")
    sid = _new_session(conn)
    with pytest.raises(ValueError, match="judgment"):
        store.record_improvement(
            conn,
            session_id=sid,
            judgment_id="no-such-judgment",
            criterion_id=None,
            area="harness_reliability",
            summary="s",
            evidence="e",
            playbook_version="v1",
            status="open",
        )
    conn.close()


# ---------------------------------------------------------------------------
# FR-2 — read surfaces
# ---------------------------------------------------------------------------


def test_read_judgments_returns_frozen_rows_in_order(tmp_path: Path) -> None:
    """FR-2: read_judgments returns frozen dataclass rows for a session, ordered
    deterministically by judged_at then judgment_id."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    jid1 = _new_judgment(conn, sid)
    jid2 = store.record_judgment(
        conn,
        session_id=sid,
        judge_model="m",
        rubric_version="v1",
        status="unparseable",
        criteria={},
        overall_band=None,
        raw_output="garbled",
    )
    conn.close()

    rows = improvement_read.read_judgments(log_path, session_id=sid)
    assert [r.judgment_id for r in rows] == sorted([jid1, jid2], key=lambda j: j)  # deterministic
    by_id = {r.judgment_id: r for r in rows}
    assert by_id[jid1].status == "complete"
    assert by_id[jid1].criteria["economical-tool-use"]["band"] == "weak"
    assert by_id[jid2].status == "unparseable"
    assert by_id[jid2].criteria == {}
    # Rows are frozen.
    with pytest.raises((AttributeError, TypeError)):
        rows[0].status = "x"  # type: ignore[misc]


def test_read_judgments_unknown_session_is_empty(tmp_path: Path) -> None:
    """FR-2: a session with no judgments reads as an empty list, not an error."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    _new_session(conn)
    conn.close()
    assert improvement_read.read_judgments(log_path, session_id="nope") == []


def test_read_improvements_filters_by_session_and_status(tmp_path: Path) -> None:
    """FR-2: read_improvements lists proposals, filterable by session_id/status,
    frozen rows in deterministic order."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid_a = _new_session(conn)
    sid_b = _new_session(conn)
    jid_a = _new_judgment(conn, sid_a)
    jid_b = _new_judgment(conn, sid_b)
    store.record_improvement(
        conn,
        session_id=sid_a,
        judgment_id=jid_a,
        criterion_id="economical-tool-use",
        area="tool_use_economy",
        summary="a-open",
        evidence="e",
        playbook_version="v1",
        status="open",
    )
    store.record_improvement(
        conn,
        session_id=sid_a,
        judgment_id=jid_a,
        criterion_id=None,
        area="harness_reliability",
        summary="a-dismissed",
        evidence="e",
        playbook_version="v1",
        status="dismissed",
    )
    store.record_improvement(
        conn,
        session_id=sid_b,
        judgment_id=jid_b,
        criterion_id=None,
        area="harness_reliability",
        summary="b-open",
        evidence="e",
        playbook_version="v1",
        status="open",
    )
    conn.close()

    # Filter by session.
    a_rows = improvement_read.read_improvements(log_path, session_id=sid_a)
    assert {r.summary for r in a_rows} == {"a-open", "a-dismissed"}
    # Filter by session + status.
    a_open = improvement_read.read_improvements(log_path, session_id=sid_a, status="open")
    assert {r.summary for r in a_open} == {"a-open"}
    # Filter by status only (all sessions).
    all_open = improvement_read.read_improvements(log_path, status="open")
    assert {r.summary for r in all_open} == {"a-open", "b-open"}
    # No filter: everything.
    everything = improvement_read.read_improvements(log_path)
    assert len(everything) == 3
    # Rows are frozen dataclasses with the fields a caller reads.
    one = a_open[0]
    assert one.area == "tool_use_economy"
    assert one.criterion_id == "economical-tool-use"
    assert one.status == "open"
    with pytest.raises((AttributeError, TypeError)):
        one.status = "x"  # type: ignore[misc]


def test_read_improvements_rejects_bad_status_filter(tmp_path: Path) -> None:
    """FR-2: a status filter outside PROPOSAL_STATUSES raises rather than silently
    returning nothing."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    conn.close()
    with pytest.raises(ValueError, match="status"):
        improvement_read.read_improvements(log_path, status="bogus")


# ---------------------------------------------------------------------------
# NFR-1 — read surfaces open read-only
# ---------------------------------------------------------------------------


def test_read_surfaces_open_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-1: both read surfaces open the log STRICTLY read-only — they never
    acquire a writable handle (same discipline as ``dossier.build_dossier``).

    We spy on ``store.connect`` and assert every connection the read surfaces open
    passes ``read_only=True``. This is the structural guarantee that keeps the
    harness the sole writer: a read path can never write the log, by construction.
    """
    log_path = tmp_path / "session_log.duckdb"
    writer = _open_initialized(log_path)
    sid = _new_session(writer)
    jid = _new_judgment(writer, sid)
    store.record_improvement(
        writer,
        session_id=sid,
        judgment_id=jid,
        criterion_id=None,
        area="harness_reliability",
        summary="s",
        evidence="e",
        playbook_version="v1",
        status="open",
    )
    writer.close()

    real_connect = store.connect
    opened_read_only: list[bool] = []

    def _spy_connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        opened_read_only.append(read_only)
        return real_connect(db_path, read_only=read_only)

    monkeypatch.setattr(store, "connect", _spy_connect)

    assert len(improvement_read.read_judgments(log_path, session_id=sid)) == 1
    assert len(improvement_read.read_improvements(log_path, session_id=sid)) == 1
    # Every connection the read surfaces opened was read-only.
    assert opened_read_only and all(opened_read_only)
