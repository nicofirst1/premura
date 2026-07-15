"""Tests for the pure trace service (``premura.trace``, WP02).

These drive the service *directly* on an initialized warehouse connection (the
``empty_warehouse`` fixture), never through MCP — the point of WP02 is that the
trace is independently testable. They prove the disclosure is *measured* from
recorded rows (deterministic hashing, normalized hypothesis identity, the
conservative surfaced fallback, the consistency invariant), not self-reported.
"""

from __future__ import annotations

import time

from premura import trace


# --------------------------------------------------------------------------- #
# Small helpers to keep the recording dance compact in each test.
# --------------------------------------------------------------------------- #
def _record(
    conn,
    session_id,
    tool,
    request,
    *,
    status="available",
    result=None,
    refusal_reason=None,
    error_kind=None,
):
    """Start + finish one recorded call, returning the RecordedCall."""
    pending = trace.start_recorded_call(conn, session_id, tool, request)
    assert isinstance(pending, trace.PendingCall), pending
    finished = trace.finish_recorded_call(
        conn,
        pending,
        terminal_status=status,
        result=result,
        refusal_reason=refusal_reason,
        error_kind=error_kind,
    )
    assert isinstance(finished, trace.RecordedCall), finished
    return finished


# --------------------------------------------------------------------------- #
# T012 — open session returns stable required fields.
# --------------------------------------------------------------------------- #
def test_open_session_returns_required_fields(empty_warehouse) -> None:
    conn = empty_warehouse
    session = trace.open_research_session(conn, client_label="agent-x")
    assert isinstance(session, trace.TraceSession)
    assert session.status == "opened"
    assert session.session_id  # non-empty stable id
    assert session.started_at_utc
    assert session.warehouse_fingerprint
    assert session.schema_version == trace.TRACE_SCHEMA_VERSION
    assert session.client_label == "agent-x"
    # The row is actually persisted.
    row = conn.execute(
        "SELECT session_id FROM trace.research_session WHERE session_id = ?",
        [session.session_id],
    ).fetchone()
    assert row is not None


def test_each_open_session_gets_a_distinct_id(empty_warehouse) -> None:
    conn = empty_warehouse
    a = trace.open_research_session(conn)
    b = trace.open_research_session(conn)
    assert a.session_id != b.session_id


# --------------------------------------------------------------------------- #
# Determinism: reordered request fields hash identically; identity dedups.
# --------------------------------------------------------------------------- #
def test_reordered_request_hashes_identically() -> None:
    a = trace.request_hash(
        "correlate",
        {
            "left_metric_id": "hr",
            "right_metric_id": "steps",
            "lag_days": 1,
            "expected_direction": "positive",
        },
    )
    b = trace.request_hash(
        "correlate",
        {
            "expected_direction": "positive",
            "lag_days": 1,
            "right_metric_id": "steps",
            "left_metric_id": "hr",
        },
    )
    assert a == b


def test_hypothesis_identity_normalizes_defaults() -> None:
    # An omitted change_point min_side_observations equals its explicit default.
    omitted = trace.hypothesis_identity("change_point", {"metric_id": "hr"})
    explicit = trace.hypothesis_identity(
        "change_point", {"metric_id": "hr", "min_side_observations": 2}
    )
    assert omitted == explicit
    # A different parameter is a different hypothesis.
    other = trace.hypothesis_identity(
        "change_point", {"metric_id": "hr", "min_side_observations": 5}
    )
    assert other != omitted


def test_correlate_identity_is_direction_and_lag_sensitive() -> None:
    base = {
        "left_metric_id": "a",
        "right_metric_id": "b",
        "lag_days": 1,
        "expected_direction": "positive",
    }
    swapped_pair = {**base, "left_metric_id": "b", "right_metric_id": "a"}
    other_lag = {**base, "lag_days": 2}
    other_dir = {**base, "expected_direction": "negative"}
    idents = {
        trace.hypothesis_identity("correlate", base),
        trace.hypothesis_identity("correlate", swapped_pair),
        trace.hypothesis_identity("correlate", other_lag),
        trace.hypothesis_identity("correlate", other_dir),
    }
    assert len(idents) == 4  # all distinct hypotheses


def test_correlate_identity_ignores_justification_text_but_keeps_presence() -> None:
    no_just = {
        "left_metric_id": "a",
        "right_metric_id": "b",
        "lag_days": 5,
        "expected_direction": "positive",
    }
    just_one = {**no_just, "lag_justification": "circadian"}
    just_two = {**no_just, "lag_justification": "different wording entirely"}
    # Different prose, same hypothesis (justification present).
    assert trace.hypothesis_identity("correlate", just_one) == trace.hypothesis_identity(
        "correlate", just_two
    )
    # Presence vs absence is a different pre-registration.
    assert trace.hypothesis_identity("correlate", just_one) != trace.hypothesis_identity(
        "correlate", no_just
    )


def test_register_hypothesis_identity_adds_a_tool_without_editing_a_switch() -> None:
    trace.register_hypothesis_identity(
        "paired_t_test_probe",
        lambda req: {"outcome": req.get("outcome"), "contrast": req.get("contrast")},
    )
    one = trace.hypothesis_identity("paired_t_test_probe", {"outcome": "x", "contrast": "g"})
    two = trace.hypothesis_identity("paired_t_test_probe", {"contrast": "g", "outcome": "x"})
    diff = trace.hypothesis_identity("paired_t_test_probe", {"outcome": "y", "contrast": "g"})
    assert one == two
    assert one != diff


# --------------------------------------------------------------------------- #
# T012 — exact retry: raw count increases, N does not.
# --------------------------------------------------------------------------- #
def test_exact_retry_increases_raw_not_n(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    req = {"metric_id": "hr", "min_side_observations": 3}
    _record(conn, s.session_id, "change_point", req, result={"tool_name": "change_point"})
    _record(conn, s.session_id, "change_point", req, result={"tool_name": "change_point"})

    disc = trace.get_research_disclosure(conn, s.session_id)
    assert isinstance(disc, trace.TraceDisclosure)
    assert disc.raw_analytical_call_count == 2
    assert disc.unique_hypothesis_count == 1


# --------------------------------------------------------------------------- #
# T012 — distinct identities: N increases.
# --------------------------------------------------------------------------- #
def test_distinct_identities_increase_n(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )
    _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hrv"},
        result={"tool_name": "change_point"},
    )
    _record(
        conn,
        s.session_id,
        "smoothed_average",
        {"metric_id": "hr", "window": 7},
        result={"tool_name": "smoothed_average"},
    )
    disc = trace.get_research_disclosure(conn, s.session_id)
    assert disc.raw_analytical_call_count == 3
    assert disc.unique_hypothesis_count == 3


# --------------------------------------------------------------------------- #
# T012 — refused call counts toward raw AND N, appears in refusal breakdown.
# --------------------------------------------------------------------------- #
def test_refused_call_counts_and_breaks_down(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )
    _record(
        conn,
        s.session_id,
        "correlate",
        {
            "left_metric_id": "a",
            "right_metric_id": "b",
            "lag_days": 2,
            "expected_direction": "positive",
        },
        status="refused",
        refusal_reason="insufficient_overlap",
    )
    _record(
        conn,
        s.session_id,
        "correlate",
        {
            "left_metric_id": "c",
            "right_metric_id": "d",
            "lag_days": 1,
            "expected_direction": "negative",
        },
        status="refused",
        refusal_reason="insufficient_overlap",
    )

    disc = trace.get_research_disclosure(conn, s.session_id)
    assert disc.raw_analytical_call_count == 3
    assert disc.unique_hypothesis_count == 3  # the two refusals are distinct hypotheses
    assert disc.refusal_breakdown == {"insufficient_overlap": 2}


def test_refused_call_requires_a_reason(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    pending = trace.start_recorded_call(conn, s.session_id, "change_point", {"metric_id": "hr"})
    assert isinstance(pending, trace.PendingCall)
    err = trace.finish_recorded_call(conn, pending, terminal_status="refused")
    assert isinstance(err, trace.TraceError)
    assert err.status == "validation_error"
    assert err.field == "refusal_reason"


def test_error_terminal_status_is_recorded_consistently(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    pending = trace.start_recorded_call(conn, s.session_id, "change_point", {"metric_id": "hr"})
    rec = trace.finish_recorded_call(conn, pending, terminal_status="error", error_kind="KeyError")
    assert isinstance(rec, trace.RecordedCall)
    assert rec.terminal_status == "error"
    assert rec.error_kind == "KeyError"
    disc = trace.get_research_disclosure(conn, s.session_id)
    # The errored attempt is still one recorded call and one hypothesis.
    assert disc.raw_analytical_call_count == 1
    assert disc.unique_hypothesis_count == 1


# --------------------------------------------------------------------------- #
# T012 — no surfaced marks: surfaced status unavailable with message.
# --------------------------------------------------------------------------- #
def test_no_marks_surfaced_unavailable(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )
    disc = trace.get_research_disclosure(conn, s.session_id)
    assert disc.surfaced.status == "unavailable"
    assert disc.surfaced.count is None
    assert disc.surfaced.message
    # The disclosure text never says "significant" or "tests".
    assert "significant" not in disc.disclosure_text.lower()
    assert "tests" not in disc.disclosure_text.lower()
    assert "unique hypotheses examined" in disc.disclosure_text


# --------------------------------------------------------------------------- #
# T012 — surfaced marks: K == mark count, includes roles/rationales.
# --------------------------------------------------------------------------- #
def test_surfaced_marks_set_k_and_carry_roles(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    c1 = _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )
    c2 = _record(
        conn,
        s.session_id,
        "smoothed_average",
        {"metric_id": "hrv", "window": 7},
        result={"tool_name": "smoothed_average"},
    )
    m1 = trace.mark_surfaced(conn, s.session_id, c1.call_id, "claim", "main finding")
    m2 = trace.mark_surfaced(conn, s.session_id, c2.call_id, "summary", "supporting trend")
    assert isinstance(m1, trace.SurfacedMark)
    assert isinstance(m2, trace.SurfacedMark)

    disc = trace.get_research_disclosure(conn, s.session_id)
    assert disc.surfaced.status == "available"
    assert disc.surfaced.count == 2
    roles = {m.role for m in disc.surfaced.marks}
    rationales = {m.rationale for m in disc.surfaced.marks}
    assert roles == {"claim", "summary"}
    assert rationales == {"main finding", "supporting trend"}
    assert "2 user-facing findings among 2 unique hypotheses examined" in disc.disclosure_text


def test_mark_validation_paths(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    other = trace.open_research_session(conn)
    call = _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )

    # Unknown session.
    e1 = trace.mark_surfaced(conn, "sess_missing", call.call_id, "claim", "x")
    assert isinstance(e1, trace.TraceError) and e1.status == "not_found"
    assert e1.field == "session_id"

    # Unknown call.
    e2 = trace.mark_surfaced(conn, s.session_id, "call_missing", "claim", "x")
    assert isinstance(e2, trace.TraceError) and e2.status == "not_found"
    assert e2.field == "call_id"

    # Call in a different session.
    e3 = trace.mark_surfaced(conn, other.session_id, call.call_id, "claim", "x")
    assert isinstance(e3, trace.TraceError) and e3.status == "invalid_reference"

    # Empty role / rationale.
    e4 = trace.mark_surfaced(conn, s.session_id, call.call_id, "  ", "x")
    assert isinstance(e4, trace.TraceError) and e4.status == "validation_error"
    assert e4.field == "role"
    e5 = trace.mark_surfaced(conn, s.session_id, call.call_id, "claim", "")
    assert isinstance(e5, trace.TraceError) and e5.status == "validation_error"
    assert e5.field == "rationale"


# --------------------------------------------------------------------------- #
# DRIFT-2 regression — duplicate surfaced marks cannot make K exceed N.
# A call marked surfaced twice must not inflate K (NFR-006: raw >= N >= K).
# --------------------------------------------------------------------------- #
def test_duplicate_surfaced_mark_rejected_and_k_counts_distinct_calls(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    call = _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )

    first = trace.mark_surfaced(conn, s.session_id, call.call_id, "claim", "main finding")
    assert isinstance(first, trace.SurfacedMark)

    # Re-marking the SAME call (even with a different role/rationale) is rejected.
    dup = trace.mark_surfaced(conn, s.session_id, call.call_id, "recommendation", "also this")
    assert isinstance(dup, trace.TraceError)
    assert dup.status == "already_marked"
    assert dup.field == "call_id"

    # The disclosure invariant holds: one unique hypothesis, one surfaced call.
    disc = trace.get_research_disclosure(conn, s.session_id)
    assert disc.unique_hypothesis_count == 1
    assert disc.surfaced.status == "available"
    assert disc.surfaced.count == 1
    assert disc.raw_analytical_call_count >= disc.unique_hypothesis_count >= disc.surfaced.count


# --------------------------------------------------------------------------- #
# DRIFT-3 regression — a finalized call is immutable through the public surface.
# A second finish_recorded_call must be rejected, not silently overwrite the row
# (NFR-003 append-only).
# --------------------------------------------------------------------------- #
def test_double_finalize_is_rejected_and_row_is_immutable(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    pending = trace.start_recorded_call(conn, s.session_id, "change_point", {"metric_id": "hr"})
    assert isinstance(pending, trace.PendingCall)

    first = trace.finish_recorded_call(
        conn, pending, terminal_status="refused", refusal_reason="weak_support"
    )
    assert isinstance(first, trace.RecordedCall)
    assert first.terminal_status == "refused"

    # A second finalize (e.g. trying to flip it to available) must be rejected.
    second = trace.finish_recorded_call(
        conn, pending, terminal_status="available", result={"tool_name": "change_point"}
    )
    assert isinstance(second, trace.TraceError)
    assert second.status == "already_finalized"
    assert second.field == "call_id"

    # The persisted row is unchanged: still refused, no result row appended.
    row = conn.execute(
        "SELECT terminal_status, refusal_reason FROM trace.tool_call WHERE call_id = ?",
        [pending.call_id],
    ).fetchone()
    assert row[0] == "refused"
    assert row[1] == "weak_support"
    n_results = conn.execute(
        "SELECT COUNT(*) FROM trace.tool_result WHERE call_id = ?",
        [pending.call_id],
    ).fetchone()[0]
    assert n_results == 0


# --------------------------------------------------------------------------- #
# T012 — unknown session disclosure returns not_found (FR-015).
# --------------------------------------------------------------------------- #
def test_unknown_session_disclosure_not_found(empty_warehouse) -> None:
    conn = empty_warehouse
    err = trace.get_research_disclosure(conn, "sess_never_opened")
    assert isinstance(err, trace.TraceError)
    assert err.status == "not_found"


def test_empty_valid_session_is_distinct_from_not_found(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    disc = trace.get_research_disclosure(conn, s.session_id)
    assert isinstance(disc, trace.TraceDisclosure)
    assert disc.raw_analytical_call_count == 0
    assert disc.unique_hypothesis_count == 0
    assert disc.surfaced.status == "unavailable"


def test_start_recorded_call_unknown_session(empty_warehouse) -> None:
    conn = empty_warehouse
    err = trace.start_recorded_call(conn, "sess_missing", "change_point", {"metric_id": "hr"})
    assert isinstance(err, trace.TraceError)
    assert err.status == "not_found"


# --------------------------------------------------------------------------- #
# T012 — consistency invariant: raw >= N >= K when K available (NFR-006).
# --------------------------------------------------------------------------- #
def test_consistency_invariant(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    # 4 calls, 3 unique hypotheses (one exact retry), 2 surfaced.
    req = {"metric_id": "hr"}
    c1 = _record(conn, s.session_id, "change_point", req, result={"tool_name": "cp"})
    _record(conn, s.session_id, "change_point", req, result={"tool_name": "cp"})  # retry
    c3 = _record(
        conn, s.session_id, "change_point", {"metric_id": "hrv"}, result={"tool_name": "cp"}
    )
    _record(
        conn,
        s.session_id,
        "smoothed_average",
        {"metric_id": "hr", "window": 14},
        result={"tool_name": "sa"},
    )
    trace.mark_surfaced(conn, s.session_id, c1.call_id, "claim", "a")
    trace.mark_surfaced(conn, s.session_id, c3.call_id, "summary", "b")

    disc = trace.get_research_disclosure(conn, s.session_id)
    raw = disc.raw_analytical_call_count
    n = disc.unique_hypothesis_count
    assert disc.surfaced.status == "available"
    k = disc.surfaced.count
    assert raw == 4
    assert n == 3
    assert k == 2
    assert raw >= n >= k


# --------------------------------------------------------------------------- #
# Audit-consumer contract: call references are stable and structured.
# --------------------------------------------------------------------------- #
def test_disclosure_call_references_satisfy_audit_contract(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    rec = _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point", "status": "available"},
    )
    disc = trace.get_research_disclosure(conn, s.session_id)
    payload = disc.to_dict()
    # Required Session Disclosure fields.
    for key in (
        "schema_version",
        "session_id",
        "started_at_utc",
        "warehouse_fingerprint",
        "raw_analytical_call_count",
        "unique_hypothesis_count",
        "surfaced",
        "refusal_breakdown",
        "calls",
    ):
        assert key in payload, key
    call = payload["calls"][0]
    for key in (
        "call_id",
        "tool_name",
        "hypothesis_identity",
        "request_hash",
        "terminal_status",
        "refusal_reason",
        "result_ref",
        "started_at_utc",
        "finished_at_utc",
    ):
        assert key in call, key
    assert call["call_id"] == rec.call_id
    assert call["result_ref"]["result_id"]
    assert call["result_ref"]["result_hash"]


def test_result_summary_never_stores_raw_health_series(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    # An envelope carrying a raw series + a safe method key.
    result = {
        "tool_name": "smoothed_average",
        "status": "available",
        "series": [{"date": "2026-01-01", "value": 60.0}],  # raw health-ish payload
        "effective_window": 7,
    }
    rec = _record(
        conn, s.session_id, "smoothed_average", {"metric_id": "hr", "window": 7}, result=result
    )
    assert rec.result_ref is not None
    row = conn.execute(
        "SELECT result_summary FROM trace.tool_result WHERE call_id = ?",
        [rec.call_id],
    ).fetchone()
    summary = row[0]
    assert summary is not None
    assert "series" not in summary  # raw series dropped
    assert "effective_window" in summary  # safe method key kept


# --------------------------------------------------------------------------- #
# Exports are generated from the structured trace, not canonical (FR-014).
# --------------------------------------------------------------------------- #
def test_json_and_markdown_exports(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    c = _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )
    trace.mark_surfaced(conn, s.session_id, c.call_id, "claim", "main")
    disc = trace.get_research_disclosure(conn, s.session_id)

    js = trace.disclosure_to_json(disc)
    assert s.session_id in js
    md = trace.disclosure_to_markdown(disc)
    assert "user-facing findings among" in md
    assert "significant" not in md.lower()


# --------------------------------------------------------------------------- #
# T012 — a 500-call session disclosure returns under the spec bound (NFR-005).
# Sanity bound, not a brittle benchmark.
# --------------------------------------------------------------------------- #
def test_500_call_session_disclosure_is_bounded_and_fast(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    for i in range(500):
        # Vary the metric so identities spread out; a handful repeat.
        _record(
            conn,
            s.session_id,
            "change_point",
            {"metric_id": f"m{i % 120}"},
            result={"tool_name": "change_point"},
        )

    start = time.perf_counter()
    disc = trace.get_research_disclosure(conn, s.session_id, call_limit=trace.DEFAULT_CALL_LIMIT)
    elapsed = time.perf_counter() - start

    assert isinstance(disc, trace.TraceDisclosure)
    assert disc.raw_analytical_call_count == 500
    assert disc.unique_hypothesis_count == 120
    # Single bounded query: well under the 1s spec bound. Generous CI margin.
    assert elapsed < 1.0


def test_disclosure_call_list_is_bounded_by_call_limit(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    for i in range(10):
        _record(
            conn,
            s.session_id,
            "change_point",
            {"metric_id": f"m{i}"},
            result={"tool_name": "change_point"},
        )
    disc = trace.get_research_disclosure(conn, s.session_id, call_limit=5)
    assert len(disc.calls) == 5
    assert disc.calls_truncated is True
    # Counts are still over the full session, not the truncated call list.
    assert disc.raw_analytical_call_count == 10
    assert disc.unique_hypothesis_count == 10


def test_include_calls_false_omits_call_list(empty_warehouse) -> None:
    conn = empty_warehouse
    s = trace.open_research_session(conn)
    _record(
        conn,
        s.session_id,
        "change_point",
        {"metric_id": "hr"},
        result={"tool_name": "change_point"},
    )
    disc = trace.get_research_disclosure(conn, s.session_id, include_calls=False)
    assert disc.calls == ()
    assert disc.raw_analytical_call_count == 1


# --------------------------------------------------------------------------- #
# NFR-004 — counts measured at the boundary, not self-reported. There is no API
# to set a count, so a "false claim" simply cannot reach the disclosure.
# --------------------------------------------------------------------------- #
def test_no_self_reported_count_surface_exists() -> None:
    # The disclosure is derived; the public surface exposes no count setter.
    public = set(dir(trace))
    for forbidden in ("set_count", "report_count", "override_n", "set_n", "set_k"):
        assert forbidden not in public


def test_engine_defaults_match_pinned_identity_constants() -> None:
    # Guard against drift: the identity normalizers duplicate the engine defaults
    # to stay engine-import-free; pin them to the real engine constants here so a
    # change in the engine surfaces as a failing test rather than silent wrong N.
    from premura.engine import analytical_tools as at

    assert trace._DEFAULT_MIN_SIDE_OBSERVATIONS == at.DEFAULT_MIN_SIDE_OBSERVATIONS
    assert trace._DEFAULT_SMOOTHING_WINDOW == at.DEFAULT_SMOOTHING_WINDOW
    assert trace._DEFAULT_MIN_COVERAGE == at.DEFAULT_MIN_COVERAGE
