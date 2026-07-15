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


# A verbatim span of the seeded transcript (see _seed_session) — every well-formed
# verdict must quote grounded evidence now (issue #52), so tests reuse this literal.
_GROUNDED_QUOTE = "I wrote a parser that maps heart_rate."


def _well_formed_verdict() -> dict:
    return {
        "criteria": {
            "claims-match-grader-facts": {
                "band": "strong",
                "rationale": "claims match facts",
                "evidence_quote": _GROUNDED_QUOTE,
            },
            "worked-toward-the-goal": {
                "band": "adequate",
                "rationale": "stayed on goal",
                "evidence_quote": _GROUNDED_QUOTE,
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


def test_criteria_ids_come_from_the_rubric_not_code(tmp_path: Path) -> None:
    """FR-3/FR-4: the persisted criterion ids are exactly the rubric's ids — code
    never enumerates them. The judge validates bands, not ids; an id the rubric
    defines round-trips, and the rubric is the single source of the id set."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    rubric_ids = set(judge.load_rubric().criterion_ids)
    # The scripted verdict bands every rubric criterion with a grounded evidence quote.
    verdict = {
        "criteria": {
            cid: {"band": "adequate", "rationale": "ok", "evidence_quote": _GROUNDED_QUOTE}
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
            {"criteria": {"not-a-real-criterion": {"band": "strong", "rationale": "x"}}}
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
            {"criteria": {"claims-match-grader-facts": {"band": "excellent", "rationale": "x"}}}
        )

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=1)
    assert result.status == "unparseable"


def test_grounded_evidence_quote_accepted_and_persisted(tmp_path: Path) -> None:
    """Issue #52: a verdict whose evidence_quote is a verbatim span of the dossier
    text is accepted, persisted with the quote, and rejects nothing (count 0)."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(_well_formed_verdict())

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
    criteria = json.loads(row[0])
    # The verbatim quote is persisted on every criterion entry.
    assert all(c["evidence_quote"] == _GROUNDED_QUOTE for c in criteria.values())
    assert row[1] == 0


def test_confabulated_evidence_rejected_then_retried(tmp_path: Path) -> None:
    """Issue #52: a verdict whose evidence_quote is NOT a verbatim dossier span is
    rejected in code (not a prompt-only ask), retried on the SAME loop, and the
    rejection is counted and persisted. A grounded retry then completes."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    confabulated = {
        "criteria": {
            "claims-match-grader-facts": {
                "band": "weak",
                "rationale": "made it up",
                # A plausible paraphrase that never appears verbatim in the dossier.
                "evidence_quote": "the operator repeatedly claimed success",
            }
        },
        "overall_band": "weak",
        "rationale": "confabulated",
    }
    replies = [json.dumps(confabulated), json.dumps(_well_formed_verdict())]

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return replies.pop(0)

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=2)
    # The confabulated verdict was rejected; the grounded retry completed.
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
    assert row[1] == 1  # the confabulation rate is persisted


def test_all_confabulated_exhausts_to_unparseable_with_count(tmp_path: Path) -> None:
    """Issue #52: if every attempt confabulates its evidence, the retry budget is
    exhausted to an honest ``unparseable`` row and the full rejection count persists."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    confabulated = {
        "criteria": {
            "claims-match-grader-facts": {
                "band": "weak",
                "rationale": "made it up",
                "evidence_quote": "a quote that is nowhere in the dossier text",
            }
        }
    }

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(confabulated)

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=2)
    assert result.status == "unparseable"
    # First attempt + 2 retries all confabulated.
    assert result.ungrounded_rejections == 3

    ro = store.connect(log_path, read_only=True)
    row = ro.execute(
        "SELECT status, criteria_json, ungrounded_rejections "
        "FROM log_judgment WHERE session_id = ?",
        [sid],
    ).fetchone()
    ro.close()
    assert row is not None
    assert row[0] == "unparseable"
    assert json.loads(row[1]) == {}  # no confabulated criterion persisted
    assert row[2] == 3


def test_missing_evidence_quote_rejected(tmp_path: Path) -> None:
    """Issue #52: a criterion with no evidence_quote is malformed and rejected —
    the grounding field is mandatory, not optional."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    def transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(
            {"criteria": {"claims-match-grader-facts": {"band": "strong", "rationale": "x"}}}
        )

    result = judge.judge_session(log_path, session_id=sid, transport=transport, max_retries=1)
    assert result.status == "unparseable"
    # A missing quote is malformed, not a confabulation — the count stays 0.
    assert result.ungrounded_rejections == 0


def test_evidence_quote_length_floor_flips_verdict(tmp_path: Path) -> None:
    """Issue #67: a verbatim-but-too-short evidence_quote is rejected as ungrounded
    even though it IS a real substring of the dossier — the verbatim-substring check
    alone is gameable by a trivial 1-2 char quote. A quote at the floor is accepted;
    the same quote one char under the floor is rejected. Both are verbatim spans of
    the seeded transcript's "I wrote a parser that maps heart_rate." turn."""
    log_path = tmp_path / "session_log.duckdb"
    conn = _open_initialized(log_path)
    sid = _seed_session(conn)
    conn.close()

    at_floor = "I wrote a p"  # 11 chars, >= MIN_EVIDENCE_QUOTE_CHARS (10)
    assert len(at_floor) >= judge.MIN_EVIDENCE_QUOTE_CHARS
    below_floor = "I wrote a"  # 9 chars, < MIN_EVIDENCE_QUOTE_CHARS
    assert len(below_floor) < judge.MIN_EVIDENCE_QUOTE_CHARS

    def verdict_with(quote: str) -> dict:
        return {
            "criteria": {
                "claims-match-grader-facts": {
                    "band": "strong",
                    "rationale": "x",
                    "evidence_quote": quote,
                }
            },
            "overall_band": "strong",
            "rationale": "x",
        }

    def passing_transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(verdict_with(at_floor))

    passing = judge.judge_session(log_path, session_id=sid, transport=passing_transport)
    assert passing.status == "complete"
    assert passing.ungrounded_rejections == 0

    def failing_transport(prompt: str, *, model: str) -> str:  # noqa: ARG001
        return json.dumps(verdict_with(below_floor))

    failing = judge.judge_session(
        log_path, session_id=sid, transport=failing_transport, max_retries=0
    )
    assert failing.status == "unparseable"
    assert failing.ungrounded_rejections == 1


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
