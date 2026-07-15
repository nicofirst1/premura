"""Offline, deterministic tests for the improvement scan (m4 WP2, FR-3/FR-4/FR-5).

The scan is PURE and deterministic: no model calls, no network, no randomness, no
clock reads beyond row timestamps (NFR-4/NFR-5). Each test seeds a recorded session
+ judgment(s) through the public store API, runs ``scan_session`` over the log, and
asserts on the persisted ``log_improvement`` rows read back through the FR-2 surface.

The playbook (``IMPROVEMENT_PLAYBOOK.md``) owns the area semantics; the judge rubric
(``JUDGE_RUBRIC.md``) owns criterion→category. The scan keys only on the closed store
vocabularies and the parsed docs — no ``if criterion_id == ...`` ladders (NFR-4). The
malformed-playbook tests inject a temporary doc to prove the parser fails loudly.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from premura.harness import improvement
from premura.harness.judge import load_rubric
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


# ---------------------------------------------------------------------------
# FR-3 — playbook parser
# ---------------------------------------------------------------------------


def test_load_playbook_exposes_version_and_required_areas() -> None:
    """FR-3: the playbook parses into a version + the six required area ids (four
    category areas + the two hook-owned ones)."""
    pb = improvement.load_playbook()
    assert pb.version  # a non-empty playbook_version header
    assert {
        "process_honesty",
        "goal_adherence",
        "tool_use_economy",
        "failure_recovery",
        "harness_reliability",
        "rubric_drift",
    } <= set(pb.areas)
    # Each category area maps from its rubric category; the hook-owned areas exist.
    assert pb.area_for_category("tool_use_economy") == "tool_use_economy"
    assert pb.harness_reliability_area == "harness_reliability"
    assert pb.rubric_drift_area == "rubric_drift"


def test_load_playbook_fails_loudly_on_missing_required_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-3: a playbook missing a required area fails loudly — code never silently
    proceeds with a malformed playbook."""
    text = improvement._read_playbook_text()
    # Drop the rubric_drift area heading + its body by truncating before it.
    mangled = text.split("### `rubric_drift`")[0]
    monkeypatch.setattr(improvement, "_read_playbook_text", lambda: mangled)
    with pytest.raises(ValueError, match="rubric_drift"):
        improvement.load_playbook()


def test_load_playbook_fails_loudly_on_missing_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-3: a playbook with no ``playbook_version`` header fails loudly."""
    text = improvement._read_playbook_text()
    mangled = text.replace("playbook_version:", "version-but-not-the-header:")
    monkeypatch.setattr(improvement, "_read_playbook_text", lambda: mangled)
    with pytest.raises(ValueError, match="playbook_version"):
        improvement.load_playbook()


# ---------------------------------------------------------------------------
# FR-4 — derivation rules
# ---------------------------------------------------------------------------


def _record_judgment(
    conn: duckdb.DuckDBPyConnection,
    sid: str,
    *,
    status: str = "complete",
    criteria: dict[str, dict[str, object]] | None = None,
    overall_band: str | None = "weak",
    rubric_version: str | None = None,
) -> str:
    rubric = load_rubric()
    return store.record_judgment(
        conn,
        session_id=sid,
        judge_model="m",
        rubric_version=rubric_version or rubric.version,
        status=status,
        criteria=criteria or {},
        overall_band=overall_band if status == "complete" else None,
    )


def test_weak_criterion_yields_one_proposal_in_mapped_area(tmp_path: Path) -> None:
    """FR-4: a criterion banded weak yields one proposal in the area mapped from
    that criterion's rubric category, carrying the criterion's rationale as
    evidence."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    rubric = load_rubric()
    # Pick the rubric criterion whose category is tool_use_economy.
    cid = "economical-tool-use"
    assert cid in rubric.criterion_ids
    _record_judgment(
        conn,
        sid,
        criteria={cid: {"band": "weak", "rationale": "thrashed the same read"}},
    )
    conn.close()

    results = improvement.scan_session(log_path, session_id=sid)
    assert len(results) == 1
    proposals = improvement_read.read_improvements(log_path, session_id=sid)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.area == "tool_use_economy"
    assert p.criterion_id == cid
    assert "thrashed the same read" in p.evidence
    assert p.status == "open"


def test_strong_adequate_not_applicable_yield_nothing(tmp_path: Path) -> None:
    """FR-4: strong / adequate / not_applicable bands produce no proposal."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    _record_judgment(
        conn,
        sid,
        criteria={
            "claims-match-grader-facts": {"band": "strong", "rationale": "honest"},
            "worked-toward-the-goal": {"band": "adequate", "rationale": "ok"},
            "economical-tool-use": {"band": "not_applicable", "rationale": "no transcript"},
        },
        overall_band="strong",
    )
    conn.close()

    results = improvement.scan_session(log_path, session_id=sid)
    assert results == []
    assert improvement_read.read_improvements(log_path, session_id=sid) == []


def test_non_complete_status_yields_harness_reliability(tmp_path: Path) -> None:
    """FR-4: a judgment whose status is not ``complete`` yields exactly one
    ``harness_reliability`` proposal (criterion-level NULL)."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    _record_judgment(conn, sid, status="unparseable", criteria={}, overall_band=None)
    conn.close()

    results = improvement.scan_session(log_path, session_id=sid)
    assert len(results) == 1
    proposals = improvement_read.read_improvements(log_path, session_id=sid)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.area == "harness_reliability"
    assert p.criterion_id is None
    assert "unparseable" in p.evidence


def test_off_rubric_criterion_yields_rubric_drift(tmp_path: Path) -> None:
    """FR-4: a judged criterion id the current rubric does not define yields one
    ``rubric_drift`` proposal — even if its band is weak, it is drift, not a
    category proposal (the category cannot be looked up)."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    _record_judgment(
        conn,
        sid,
        criteria={"a-retired-criterion": {"band": "weak", "rationale": "old"}},
    )
    conn.close()

    improvement.scan_session(log_path, session_id=sid)
    proposals = improvement_read.read_improvements(log_path, session_id=sid)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.area == "rubric_drift"
    assert p.criterion_id == "a-retired-criterion"


def test_multiple_weak_criteria_each_yield_a_proposal(tmp_path: Path) -> None:
    """FR-4: two weak criteria in different categories yield two proposals in their
    respective areas."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    _record_judgment(
        conn,
        sid,
        criteria={
            "economical-tool-use": {"band": "weak", "rationale": "thrash"},
            "claims-match-grader-facts": {"band": "weak", "rationale": "overclaimed"},
        },
    )
    conn.close()

    improvement.scan_session(log_path, session_id=sid)
    proposals = improvement_read.read_improvements(log_path, session_id=sid)
    assert {p.area for p in proposals} == {"tool_use_economy", "process_honesty"}


def test_scan_carries_playbook_version_on_each_proposal(tmp_path: Path) -> None:
    """FR-4: each proposal records the playbook_version that produced it."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    _record_judgment(
        conn, sid, criteria={"economical-tool-use": {"band": "weak", "rationale": "x"}}
    )
    conn.close()

    improvement.scan_session(log_path, session_id=sid)
    pb = improvement.load_playbook()
    proposals = improvement_read.read_improvements(log_path, session_id=sid)
    assert all(p.playbook_version == pb.version for p in proposals)


# ---------------------------------------------------------------------------
# FR-5 — idempotent persistence
# ---------------------------------------------------------------------------


def test_rescan_is_idempotent(tmp_path: Path) -> None:
    """FR-5: re-running the scan over the same judgments writes nothing new and
    reports each proposal as pre-existing the second time."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    _record_judgment(
        conn,
        sid,
        criteria={
            "economical-tool-use": {"band": "weak", "rationale": "thrash"},
            "claims-match-grader-facts": {"band": "weak", "rationale": "overclaim"},
        },
    )
    conn.close()

    first = improvement.scan_session(log_path, session_id=sid)
    assert len(first) == 2
    assert all(not r.pre_existing for r in first)  # all newly written

    second = improvement.scan_session(log_path, session_id=sid)
    assert len(second) == 2
    assert all(r.pre_existing for r in second)  # all already present

    # Still exactly two rows in the table — no duplicates.
    assert len(improvement_read.read_improvements(log_path, session_id=sid)) == 2


def test_scan_no_judgments_writes_nothing(tmp_path: Path) -> None:
    """FR-4/FR-5: a session with no judgments yields no proposals (nothing to
    consume), not an error."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _new_session(conn)
    conn.close()
    assert improvement.scan_session(log_path, session_id=sid) == []
    assert improvement_read.read_improvements(log_path, session_id=sid) == []
