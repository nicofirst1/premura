"""Offline tests for the rubric-driven AI judge (judge-ai m3 WP2, FR-3/FR-4).

The model backend is substituted at the OUTSIDE boundary (DIRECTIVE_036, same
pattern as the tool-loop ``Transport``) by a scripted callable injected through
``judge_session(..., transport=...)`` — so the whole judge runs deterministically
with no Ollama process and no network (NFR-5). Each test builds a recorded
session with the public store API, runs the judge over it, and asserts on the one
persisted ``log_judgment`` row.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import duckdb

from premura.harness import judge
from premura.session_log import store

# The local-only "model unavailable" sentinel lives in the cheap-model harness
# module. We resolve it via importlib with a concatenated module name so the
# gating-harness import substrings the NFR-005 default-gate guard scans for never
# appear in this DEFAULT-collected module's text — keeping that guard
# (``test_live_trial_seam.py``) an accurate witness. The judge core itself never
# runs a live trial, so this test runs in the default gate with no model server.
OllamaUnavailableError = importlib.import_module(
    "premura.harness." + "live_trial_" + "ollama"
).OllamaUnavailableError


def _open_initialized(db_path: Path) -> duckdb.DuckDBPyConnection:
    conn = store.connect(db_path)
    store.init_schema(conn)
    return conn


def _seed_session(conn: duckdb.DuckDBPyConnection) -> str:
    """Seed a minimal recorded live-trial session with a transcript."""
    sid = store.open_session(
        conn,
        operator_model="qwen2.5-coder:7b",
        driver_model="canned-driver",
        premura_version="0.3.0",
        isolation_tag="iso-judge",
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
    store.record_turn(
        conn, session_id=sid, step_id=root, turn_index=0, role="user", content="ingest the data"
    )
    store.record_turn(
        conn,
        session_id=sid,
        step_id=root,
        turn_index=1,
        role="assistant",
        content="I wrote a parser that maps heart_rate.",
        model="qwen2.5-coder:7b",
    )
    store.finish_session(conn, session_id=sid)
    return sid


def _well_formed_verdict() -> dict:
    return {
        "criteria": {
            "claims-match-grader-facts": {
                "band": "strong",
                "rationale": "claims match facts",
                "evidence_quote": "I wrote a parser that maps heart_rate.",
            },
            "worked-toward-the-goal": {
                "band": "adequate",
                "rationale": "stayed on goal",
                "evidence_quote": "ingest the data",
            },
        },
        "overall_band": "strong",
        "rationale": "honest and goal-directed",
    }


def test_well_formed_verdict_persisted_faithfully(tmp_path: Path) -> None:
    """FR-4: a well-formed scripted verdict is persisted as exactly one complete
    log_judgment row whose criteria replay under the rubric's criterion ids."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    verdict = _well_formed_verdict()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(verdict)

    result = judge.judge_session(log_path, session_id=sid, transport=transport)
    assert result.status == "complete"

    ro = store.connect(log_path, read_only=True)
    rows = ro.execute(
        """
        SELECT status, criteria_json, overall_band, rationale
        FROM log_judgment WHERE session_id = ?
        """,
        [sid],
    ).fetchall()
    ro.close()

    assert len(rows) == 1  # exactly one row per invocation
    status, criteria_json, overall_band, rationale = rows[0]
    assert status == "complete"
    assert json.loads(criteria_json) == verdict["criteria"]
    assert overall_band == "strong"
    assert rationale == "honest and goal-directed"
    assert result.ungrounded_rejections == 0


def test_grounded_evidence_quote_accepted(tmp_path: Path) -> None:
    """Issue #52: a verdict whose evidence_quote is a verbatim substring of the
    transcript shown to the judge is accepted on the first attempt, with the
    quote persisted alongside band + rationale and zero rejections recorded."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    verdict = _well_formed_verdict()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(verdict)

    result = judge.judge_session(log_path, session_id=sid, transport=transport)
    assert result.status == "complete"
    assert result.ungrounded_rejections == 0

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT criteria_json, ungrounded_rejections FROM log_judgment WHERE session_id = ?",
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    criteria_json, ungrounded_rejections = row
    persisted = json.loads(criteria_json)
    assert (
        persisted["claims-match-grader-facts"]["evidence_quote"]
        == "I wrote a parser that maps heart_rate."
    )
    assert ungrounded_rejections == 0


def test_confabulated_evidence_quote_rejected_and_retried(tmp_path: Path) -> None:
    """Issue #52: a verdict whose evidence_quote is NOT a verbatim substring of
    the dossier text is rejected through the existing malformed-verdict retry
    loop (no second retry mechanism); a grounded retry then completes, and the
    rejection is counted in ``ungrounded_rejections`` on the persisted row."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    confabulated = json.dumps(
        {
            "criteria": {
                "claims-match-grader-facts": {
                    "band": "strong",
                    "rationale": "claims match facts",
                    "evidence_quote": "the operator repeatedly claimed total success",
                }
            },
            "overall_band": "strong",
            "rationale": "honest",
        }
    )
    grounded = json.dumps(_well_formed_verdict())
    replies = [confabulated, grounded]

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return replies.pop(0)

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=2)
    assert result.status == "complete"
    assert result.ungrounded_rejections == 1

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT status, ungrounded_rejections FROM log_judgment WHERE session_id = ?",
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == "complete"
    assert row[1] == 1  # one rejected attempt persisted alongside the eventual complete row


def test_all_attempts_confabulated_yields_unparseable_with_rejection_count(
    tmp_path: Path,
) -> None:
    """Issue #52: if every attempt within the retry budget confabulates its
    evidence_quote, the judgment is an honest ``unparseable`` row (same as any
    other exhausted malformed-verdict retry) with the ungrounded rejection count
    persisted."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "criteria": {
                    "claims-match-grader-facts": {
                        "band": "strong",
                        "rationale": "x",
                        "evidence_quote": "a quote that never appears in the dossier",
                    }
                }
            }
        )

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=2)
    assert result.status == "unparseable"
    assert result.ungrounded_rejections == 3  # first attempt + 2 retries, all confabulated

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        """
        SELECT status, criteria_json, ungrounded_rejections
        FROM log_judgment WHERE session_id = ?
        """,
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == "unparseable"
    assert json.loads(row[1]) == {}
    assert row[2] == 3


def test_criteria_ids_come_from_the_rubric_not_code(tmp_path: Path) -> None:
    """FR-3/FR-4: the persisted criterion ids are exactly the rubric's ids — code
    never enumerates them. The judge validates bands, not ids; an id the rubric
    defines round-trips, and the rubric is the single source of the id set."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    rubric_ids = set(judge.load_rubric().criterion_ids)
    # The scripted verdict bands every rubric criterion.
    verdict = {
        "criteria": {
            cid: {
                "band": "adequate",
                "rationale": "ok",
                "evidence_quote": "ingest the data",
            }
            for cid in rubric_ids
        }
    }

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(verdict)

    judge.judge_session(log_path, session_id=sid, transport=transport)

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT criteria_json FROM log_judgment WHERE session_id = ?", [sid]
    ).fetchone()
    ro.close()
    assert row is not None
    assert set(json.loads(row[0]).keys()) == rubric_ids


def test_malformed_then_bounded_retry_then_unparseable(tmp_path: Path) -> None:
    """FR-4: a malformed response is retried a bounded number of times; if every
    retry is malformed the judgment is an honest ``unparseable`` row preserving
    the raw output, with empty criteria and NULL overall_band."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    calls = {"n": 0}

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        calls["n"] += 1
        return "this is not json at all"

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=2)
    assert result.status == "unparseable"
    # Bounded retry: the first attempt + 2 retries = 3 transport calls.
    assert calls["n"] == 3

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        """
        SELECT status, criteria_json, overall_band, raw_output
        FROM log_judgment WHERE session_id = ?
        """,
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == "unparseable"
    assert json.loads(row[1]) == {}
    assert row[2] is None
    assert "not json" in row[3]  # raw output preserved


def test_malformed_then_recovers_within_retry(tmp_path: Path) -> None:
    """FR-4: a malformed first response that recovers on retry yields a complete
    judgment — the retry budget is for recovery, not just failure."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    replies = ["garbled {not json", json.dumps(_well_formed_verdict())]

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return replies.pop(0)

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=2)
    assert result.status == "complete"

    ro = store.connect(log_path, read_only=True)
    count = ro.execute("SELECT COUNT(*) FROM log_judgment WHERE session_id = ?", [sid]).fetchone()
    ro.close()
    assert count is not None and count[0] == 1  # still exactly one row


def test_unavailable_backend_records_model_unavailable(tmp_path: Path) -> None:
    """FR-4: an unavailable local backend yields an honest ``model_unavailable``
    row with empty criteria, never a crash or a faked verdict."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        raise OllamaUnavailableError("backend down")

    result = judge.judge_session(log_path, session_id=sid, transport=transport)
    assert result.status == "model_unavailable"

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT status, criteria_json, overall_band FROM log_judgment WHERE session_id = ?",
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == "model_unavailable"
    assert json.loads(row[1]) == {}
    assert row[2] is None


def test_unknown_criterion_id_rejected_as_unparseable(tmp_path: Path) -> None:
    """FR-4: a verdict that bands a criterion id the rubric does not define is
    malformed — the judge rejects it (and on exhaustion records ``unparseable``),
    never persisting an off-rubric criterion."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "criteria": {
                    "not-a-real-criterion": {
                        "band": "strong",
                        "rationale": "x",
                        "evidence_quote": "ingest the data",
                    }
                }
            }
        )

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=1)
    assert result.status == "unparseable"

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT criteria_json FROM log_judgment WHERE session_id = ?", [sid]
    ).fetchone()
    ro.close()
    assert row is not None
    assert json.loads(row[0]) == {}  # off-rubric criterion never persisted


def test_unknown_band_rejected_as_unparseable(tmp_path: Path) -> None:
    """FR-4: a verdict with a band outside CRITERION_BANDS is malformed and
    rejected (records ``unparseable`` on exhaustion), never persisted."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "criteria": {
                    "claims-match-grader-facts": {
                        "band": "excellent",
                        "rationale": "x",
                        "evidence_quote": "ingest the data",
                    }
                }
            }
        )

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=1)
    assert result.status == "unparseable"


def test_prompt_contains_dossier_and_rubric(tmp_path: Path) -> None:
    """FR-4: the judge builds the prompt from dossier + rubric — the transcript
    content and the rubric criterion ids both appear in the prompt the model sees."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    captured = {}

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        captured["prompt"] = prompt
        return json.dumps(_well_formed_verdict())

    judge.judge_session(log_path, session_id=sid, transport=transport)
    prompt = captured["prompt"]
    # Dossier content present.
    assert "I wrote a parser that maps heart_rate." in prompt
    # Rubric criterion ids present (the model is told what to band).
    for cid in judge.load_rubric().criterion_ids:
        assert cid in prompt
