"""Thin MCP server entrypoint over Premura's warehouse helpers.

Two entrypoints are provided:

* **Default surface** (``premura-mcp``, :func:`build_server`) — the agent-safe
  surface.  Enumerated per-instance tools are collapsed into parameterized ones
  (guide, don't enumerate): the eight approved Stage 2 signal answers behind one
  ``signal`` tool (``signal()`` with no name self-describes the catalog); the
  three descriptive single-metric methods behind one ``analyze`` tool
  (``change_point`` / ``smoothed_average`` / ``rolling_mean``); the two
  pre-registered paired differences behind one ``paired_test`` tool (kinds
  ``before_after`` / ``condition_label``); record/list/retract behind one
  ``condition_episode`` tool; and metric lookup + manual single-row load
  behind one ``ingest_row`` tool (ops ``suggest_metric`` / ``load`` — the only
  sanctioned path for manually-transcribed data, delegating entirely to
  ``store.manual_load`` / ``store.loader.load``).  Alongside these it exposes
  the catalog/summary helpers (``list_metrics`` / ``metric_summary``), the
  two-metric association ``correlate``, the bounded agent-mediated profile
  capture tools (``profile_context_supported_fields`` /
  ``profile_context_record``), the two interview routing tools
  (``interview_route`` / ``interview_devices``), the three session
  research-trace tools (``research_trace_open`` / ``research_trace_mark_surfaced``
  / ``research_trace_disclosure``), the two PubMed grounding tools
  (``pubmed_search`` / ``pubmed_fetch``), and the runtime-orchestrator tools
  (``operating_roles`` / ``orchestrator_handoff`` / ``answer_audit`` /
  ``present_answer`` / ``improvement_queue_record`` / ``improvement_queue_list``
  / ``share_packet_render``) — 24 tools in total.
  ``query_warehouse`` is intentionally absent; agents should use the ``signal`` /
  ``analyze`` / ``paired_test`` / ``correlate`` tools, the trace tools, the PubMed
  tools, and the catalog helpers instead.  The authoritative tool list is asserted
  in ``tests/mcp/test_mcp_server.py`` (``_DEFAULT_TOOLS``).

* **Operator surface** (``premura-mcp-operator``, :func:`build_operator_server``)
  — lower-guarantee expert mode intended for operator/developer use only,
  **not** for autonomous agent consumption.  Adds :func:`query_warehouse` on top
  of the full default tool set.  No Stage 2 validity guarantees apply to results
  returned by ``query_warehouse``.

The explicit-approval rule is enforced two ways, not by prose alone: (1) surface
separation — ``query_warehouse`` is simply absent from the default
``premura-mcp`` surface, so an agent connected there cannot reach it; and (2) an
explicit launch acknowledgment — the ``premura-mcp-operator`` console entry
(:func:`main_operator`) refuses to start unless the launcher passes ``--ack`` or
sets ``PREMURA_OPERATOR_ACK``.  The lower-guarantee disclosure to the end user
remains a client/agent-layer responsibility the server cannot enforce.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import trace
from . import server as warehouse_server

JsonScalar = str | int | float | bool | None

#: Environment variable an operator may set (to a truthy value) to acknowledge
#: lower-guarantee operator mode instead of passing ``--ack`` on the CLI.
_OPERATOR_ACK_ENV = "PREMURA_OPERATOR_ACK"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _refusal_reason_of(payload: dict[str, Any]) -> str:
    """Pull the engine's machine-readable refusal reason out of an analytical payload.

    The analytical wrappers return ``{"status": ..., "result": <engine envelope>}``;
    a refusal carries ``result.refusal.reason``. Falls back to a generic marker so a
    refused call is always recorded with *some* reason (a refused trace row must
    carry a reason — see :func:`premura.trace.finish_recorded_call`).
    """
    result = payload.get("result")
    if isinstance(result, dict):
        refusal = result.get("refusal")
        if isinstance(refusal, dict):
            reason = refusal.get("reason")
            if isinstance(reason, str) and reason.strip():
                return reason
    return "refused"


def _trace_meta_of(value: object) -> dict[str, Any] | None:
    """Render a trace start/finish outcome into a JSON-safe wrapper ``trace`` object.

    Returns the wrapper-layer trace metadata (``session_id``/``call_id``/
    ``result_id`` on success, or a structured error) — NEVER injected into the
    engine envelope. ``None`` means "no metadata to attach" (no session supplied).
    """
    if value is None:
        return None
    if isinstance(value, trace.TraceError):
        return {
            "status": value.status,
            "message": value.message,
            **({"field": value.field} if value.field else {}),
        }
    if isinstance(value, trace.PendingCall):
        return {"session_id": value.session_id, "call_id": value.call_id}
    if isinstance(value, trace.RecordedCall):
        meta: dict[str, Any] = {
            "session_id": value.session_id,
            "call_id": value.call_id,
            "terminal_status": value.terminal_status,
        }
        if value.result_ref is not None:
            meta["result_id"] = value.result_ref.result_id
        return meta
    return None


def _trace_session_error_envelope(tool_name: str, err: trace.TraceError) -> dict[str, Any]:
    """Refusal envelope for an analytical call naming a non-recordable session.

    When an analytical tool is given an explicit ``session_id`` that cannot be
    recorded against (unknown / typo'd session), the wrapper refuses instead of
    dispatching, so the agent never receives an unmeasured-but-trusted result.
    The engine is NOT invoked; there is no result and no recorded row. The trace
    problem is carried both at the top level and under the ``trace`` key.
    """
    envelope: dict[str, Any] = {
        "tool_name": tool_name,
        "status": err.status,  # e.g. "not_found"
        "message": err.message,
        "result": None,
        "trace": _trace_meta_of(err),
    }
    if err.field:
        envelope["field"] = err.field
    return envelope


def _dispatch_analytical_with_trace(
    *,
    warehouse_path: Path | None,
    tool_name: str,
    session_id: str | None,
    request: dict[str, Any],
    dispatch: Any,
    call_kind: str = trace.CALL_KIND_ANALYTICAL,
) -> dict[str, Any]:
    """Dispatch an analytical wrapper, mechanically recording it iff a session is given.

    Opt-in by explicit session association:

    * **No ``session_id``** — behavior is exactly as today: call ``dispatch()`` and
      return the engine envelope verbatim. No trace row is written and the response
      shape is byte-identical to the untraced path.
    * **With ``session_id``** — record the call BEFORE dispatch
      (:func:`premura.trace.start_recorded_call`), dispatch UNCHANGED, then finalize
      AFTER dispatch with the engine's own ``available``/``refused`` verdict (an
      uncaught dispatch error finalizes as ``error`` and re-raises). The engine
      envelope is returned untouched; the recorded-call references are attached only
      at the WRAPPER layer under a top-level ``trace`` key, so the envelope stays
      byte-identical with tracing on vs off.

    ``request`` is the analytical request kwargs as the wrapper received them; the
    per-tool identity registry in ``premura.trace`` normalizes them, so the wrapper
    passes them straight through (exact retries collapse to one hypothesis there).

    ``call_kind`` routes evidence-source tools (the PubMed lookups) through the
    exact same record → dispatch → finalize seam; their rows are excluded from
    the multiplicity disclosure by ``premura.trace`` and consumed by citation
    binding instead.
    """
    if not session_id:
        # Untraced fast path — no trace key added.
        return dispatch()

    # Record BEFORE dispatch, but do NOT hold the trace's writable connection open
    # across the dispatch: the analytical wrapper opens its OWN read-only DuckDB
    # connection to the same warehouse file, and DuckDB refuses concurrent
    # read-only + read-write handles to one file in a single process. So the two
    # short-lived writable trace connections (start, then finish) bracket the
    # dispatch without ever overlapping its read-only handle. The logical order
    # (record → dispatch → finalize) is preserved.
    with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
        pending = trace.start_recorded_call(
            conn, session_id, tool_name, request, call_kind=call_kind
        )
    if isinstance(pending, trace.TraceError):
        # An explicit session_id was supplied but the call cannot be recorded
        # against it (e.g. an unknown / typo'd / expired session). REFUSE rather
        # than dispatch: returning an unmeasured result that the agent would trust
        # as part of a measured session silently defeats the "measured, not
        # self-reported" guarantee. The analytical engine is never invoked.
        return _trace_session_error_envelope(tool_name, pending)

    try:
        payload = dispatch()
    except ValueError:
        # Pre-question parameter validation failure (empty metric id, invalid
        # enum, unsupported lag — the warehouse server raises ValueError BEFORE
        # the request becomes an analytical question). Such calls
        # MUST NOT be recorded or counted, so discard the eagerly-started row.
        with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
            trace.discard_recorded_call(conn, pending)
        raise
    except Exception:
        # A genuine fault AFTER a valid analytical question (the spec's
        # recorded-before-dispatch / engine-raises-mid-dispatch edge case):
        # finalize the attempt's terminal status so the disclosure stays
        # internally consistent (the look at the data still happened).
        with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
            trace.finish_recorded_call(
                conn, pending, terminal_status=trace.STATUS_ERROR, error_kind="dispatch_error"
            )
        raise

    with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
        if call_kind == trace.CALL_KIND_EVIDENCE_SOURCE:
            recorded = _finish_evidence_call(conn, pending, payload)
        elif payload.get("status") == "refused":
            recorded = trace.finish_recorded_call(
                conn,
                pending,
                terminal_status=trace.STATUS_REFUSED,
                refusal_reason=_refusal_reason_of(payload),
            )
        else:
            recorded = trace.finish_recorded_call(
                conn,
                pending,
                terminal_status=trace.STATUS_AVAILABLE,
                result=payload.get("result"),
            )
    payload["trace"] = _trace_meta_of(recorded)
    return payload


def _finish_evidence_call(
    conn: Any, pending: trace.PendingCall, payload: dict[str, Any]
) -> trace.RecordedCall | trace.TraceError:
    """Finalize an evidence-source lookup with an honest terminal status.

    Citation binding treats ONLY a terminal-``available`` ``pubmed_fetch`` row
    as citeable, so the mapping must never record a failed lookup as available:

    * provider outcome ``available`` → ``available`` (the lookup produced the
      record / candidates; the compact result reference is attached);
    * ``provider_error`` → ``error`` (transport/parse fault — the look-up never
      completed);
    * anything else (``no_results`` / ``invalid_pmid`` / ``unavailable``) →
      ``refused`` with the provider outcome as the machine-readable reason: the
      lookup completed but yielded nothing citeable. Evidence refusals never
      reach the analytical refusal breakdown (filtered by kind in the trace).
    """
    outcome = payload.get("status")
    if outcome == "available":
        return trace.finish_recorded_call(
            conn,
            pending,
            terminal_status=trace.STATUS_AVAILABLE,
            result=payload,
        )
    if outcome == "provider_error":
        return trace.finish_recorded_call(
            conn,
            pending,
            terminal_status=trace.STATUS_ERROR,
            error_kind="provider_error",
        )
    return trace.finish_recorded_call(
        conn,
        pending,
        terminal_status=trace.STATUS_REFUSED,
        refusal_reason=str(outcome) if outcome else "unknown_outcome",
    )


#: The signal name-space exposed by the single ``signal`` tool. Each entry
#: declares its agent-facing params (so ``signal()`` with no name self-describes)
#: and the plain-English question lifted from the former per-signal tool
#: docstrings. Dispatch (built per-server in :func:`_register_default_tools`)
#: routes each name to the matching thin server wrapper, which keeps every
#: per-signal window bound and the HRV explicit-anchor path exactly as before.
#: Adding a signal is one entry here plus its engine registration — the agent
#: still sees exactly one tool, never a growing menu (guide, don't enumerate).
#: ponytail: internal routing table, not an agent-facing enumeration.
_SIGNAL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "name": "resting_hr_status",
        "question": "Latest resting heart rate with an explicit freshness verdict.",
        "params": (),
    },
    {
        "name": "resting_hr_trend",
        "question": "Recent resting-heart-rate trend with gap and imputation visibility.",
        "params": (
            {
                "name": "lookback_days",
                "type": "int",
                "required": False,
                "hint": "trend span, 7..90 days",
            },
        ),
    },
    {
        "name": "steps_trend",
        "question": "Recent daily-steps trend; missing days stay gaps and are never imputed.",
        "params": (
            {
                "name": "lookback_days",
                "type": "int",
                "required": False,
                "hint": "trend span, 7..90 days",
            },
        ),
    },
    {
        "name": "weight_trend",
        "question": "Recent body-weight trend with freshness and carried-forward caveats.",
        "params": (
            {
                "name": "lookback_days",
                "type": "int",
                "required": False,
                "hint": "trend span, 7..120 days",
            },
        ),
    },
    {
        "name": "sleep_deep_pct_baseline",
        "question": "Compare the latest deep-sleep percentage to the user's own recent baseline.",
        "params": (
            {
                "name": "baseline_days",
                "type": "int",
                "required": False,
                "hint": "baseline span, 7..60 days",
            },
        ),
    },
    {
        "name": "hrv_change_around_date",
        "question": "Overnight HRV before/after a user-supplied anchor date; no causation claimed.",
        "params": (
            {
                "name": "anchor_date",
                "type": "str",
                "required": True,
                "hint": "YYYY-MM-DD change date the comparison is centered on",
            },
            {
                "name": "window_days",
                "type": "int",
                "required": False,
                "hint": "before/after span, 3..30 days",
            },
        ),
    },
    {
        "name": "supplement_intake_adherence",
        "question": "Logged-day coverage (K of N days) for a supplement you name.",
        "params": (
            {
                "name": "matcher",
                "type": "str",
                "required": True,
                "hint": "supplement product/ingredient your filter selects",
            },
            {
                "name": "window_days",
                "type": "int",
                "required": False,
                "hint": "coverage window, 1..365 days",
            },
            {
                "name": "min_logged_days",
                "type": "int",
                "required": False,
                "hint": "fewest distinct logged days before coverage is reported (default 1)",
            },
        ),
    },
    {
        "name": "nutrition_intake_trend",
        "question": "Plain up/down/flat direction for a nutrient/energy key you name.",
        "params": (
            {
                "name": "quantity_key",
                "type": "str",
                "required": True,
                "hint": "nutrient/energy key, e.g. energy or protein",
            },
            {
                "name": "window_days",
                "type": "int",
                "required": False,
                "hint": "trend window, 1..365 days",
            },
        ),
    },
)

#: name -> declared params, derived from :data:`_SIGNAL_CATALOG` (single source).
_SIGNAL_PARAMS: dict[str, tuple[dict[str, Any], ...]] = {
    entry["name"]: entry["params"] for entry in _SIGNAL_CATALOG
}


def _signal_catalog() -> dict[str, Any]:
    """Return the self-describing signal catalog (``signal()`` with no name)."""
    return {"signals": [dict(entry) for entry in _SIGNAL_CATALOG], "count": len(_SIGNAL_CATALOG)}


def _register_default_tools(
    mcp: FastMCP, *, warehouse_path: Path | None, session_log_path: Path | None
) -> None:
    """Register the full agent-safe default tool set on *mcp*.

    This is the shared core.  It does NOT include ``query_warehouse`` — that
    raw SQL escape hatch lives exclusively on the operator surface.
    """
    # Inject the engine-backed interview route resolver + seed the STAGES-8 (#41
    # leaves this to MCP startup; Stage 4 imports no engine). Idempotent.
    warehouse_server.install_interview_route_resolver()
    # Inject the parser-backed device-track resolver + seed the device branch
    # (onboarding arc gap #2; Stage 4 imports no ingest code). Idempotent.
    warehouse_server.install_device_track_resolver()

    @mcp.tool()
    def list_metrics(
        metric_ids: list[str] | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List canonical metrics as validity-gated catalog entries.

        With no arguments, enumerates registered metrics (paged by
        ``limit`` / ``offset``).  Pass ``metric_ids`` to fetch catalog entries
        for specific metrics; an unknown id returns an explicit ``unavailable``
        entry rather than being omitted.  Each entry reports a validity status
        and declared policy — never raw fact-table row counts.
        """
        metrics = warehouse_server.list_metrics(
            metric_ids=metric_ids,
            warehouse_path=warehouse_path,
            limit=limit,
            offset=offset,
        )
        return {
            "metrics": metrics,
            "count": len(metrics),
            "limit": limit,
            "offset": offset,
        }

    @mcp.tool()
    def metric_summary(metric_id: str) -> dict[str, Any]:
        """Return a validity/imputation envelope for one canonical metric.

        Reports validity status, latest value, declared policy, and recent-window
        coverage (sample size / imputed proportion / gap count).  An unknown
        metric returns an explicit ``unavailable`` summary, never raw extrema.
        """
        return {
            "summary": warehouse_server.metric_summary(
                metric_id,
                warehouse_path=warehouse_path,
            )
        }

    # --- Signal-backed Stage 2 tools (one parameterized tool) -------------- #
    # The eight approved Stage 2 signal answers are exposed as ONE ``signal``
    # tool, not eight. ``signal()`` with no name returns a self-describing
    # catalog (:data:`_SIGNAL_CATALOG`); ``signal(name, params)`` dispatches to
    # the matching thin server wrapper below, which owns the resolver, the
    # coverage/trend/freshness verdict, each per-signal window bound, and the HRV
    # explicit-anchor path. This layer computes nothing and issues no raw SQL;
    # the engine's four structurally-distinct states (available / missing_input /
    # stale_input / insufficient_data) flow straight through, never a diagnosis
    # or recommendation.
    _signal_dispatch: dict[str, Any] = {
        "resting_hr_status": lambda p: warehouse_server.resting_hr_status(
            warehouse_path=warehouse_path
        ),
        "resting_hr_trend": lambda p: warehouse_server.resting_hr_trend(
            lookback_days=p.get("lookback_days"), warehouse_path=warehouse_path
        ),
        "steps_trend": lambda p: warehouse_server.steps_trend(
            lookback_days=p.get("lookback_days"), warehouse_path=warehouse_path
        ),
        "weight_trend": lambda p: warehouse_server.weight_trend(
            lookback_days=p.get("lookback_days"), warehouse_path=warehouse_path
        ),
        "sleep_deep_pct_baseline": lambda p: warehouse_server.sleep_deep_pct_baseline(
            baseline_days=p.get("baseline_days"), warehouse_path=warehouse_path
        ),
        "hrv_change_around_date": lambda p: warehouse_server.hrv_change_around_date(
            p.get("anchor_date"),
            window_days=p.get("window_days"),
            warehouse_path=warehouse_path,
        ),
        "supplement_intake_adherence": lambda p: warehouse_server.supplement_intake_adherence(
            p.get("matcher"),
            window_days=p.get("window_days"),
            min_logged_days=p.get("min_logged_days"),
            warehouse_path=warehouse_path,
        ),
        "nutrition_intake_trend": lambda p: warehouse_server.nutrition_intake_trend(
            p.get("quantity_key"),
            window_days=p.get("window_days"),
            warehouse_path=warehouse_path,
        ),
    }
    # Catalog and dispatch must cover the same signal names — cheap drift guard.
    assert set(_signal_dispatch) == set(_SIGNAL_PARAMS)

    @mcp.tool()
    def signal(name: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Answer one approved Stage 2 signal, or list the available signals.

        Call ``signal()`` with no ``name`` to get the catalog: each signal's
        ``name``, the plain-English ``question`` it answers, and its declared
        ``params`` (which are required, and their bounds). Then call
        ``signal(name, params)`` to run one — for example
        ``signal("resting_hr_status")`` or
        ``signal("supplement_intake_adherence", {"matcher": "vitamin d",
        "window_days": 30})``.

        Each answer delegates to the grounded signal engine and returns a
        structured payload whose ``status`` distinguishes available /
        missing_input / stale_input / insufficient_data without collapsing into a
        generic error. It is descriptive only: no diagnosis, recommendation, or
        causal claim. An unknown ``name`` or a missing required param is rejected
        with an explicit error rather than a fabricated answer.
        """
        if name is None:
            return _signal_catalog()
        if name not in _signal_dispatch:
            raise ValueError(
                f"unknown signal {name!r}; call signal() with no name to list available signals"
            )
        supplied = params or {}
        for pspec in _SIGNAL_PARAMS[name]:
            if pspec["required"] and not supplied.get(pspec["name"]):
                raise ValueError(f"signal {name!r} requires param {pspec['name']!r}")
        return _signal_dispatch[name](supplied)

    # --- Stage 3 analytical tools ------------------------------------------ #
    # change_point / smoothed_average / rolling_mean — the three descriptive
    # single-metric pattern tools — are exposed as ONE ``analyze`` tool selected
    # by ``method``. Each method routes to the SAME thin server wrapper and the
    # SAME ``_dispatch_analytical_with_trace`` call as before, preserving the
    # per-method trace ``tool_name`` and request identity, so the multiplicity
    # trace stays byte-identical to the pre-collapse surface. Pre-registered
    # hypothesis tests (``paired_test``) and the two-metric association
    # (``correlate``) stay separate tools: a descriptive pattern is a different
    # epistemic kind from a hypothesis test and must not share one menu slot.
    analyze_methods = ("change_point", "smoothed_average", "rolling_mean")

    @mcp.tool()
    def analyze(
        method: str,
        metric_id: str,
        window: int | None = None,
        min_coverage: float | None = None,
        min_side_observations: int | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Describe one metric's recent pattern with a chosen descriptive method.

        ``method`` selects the descriptive tool:

        * ``"change_point"`` — detect the single most prominent level shift (when,
          before/after levels, direction). Uses ``min_side_observations``.
        * ``"smoothed_average"`` — a conservative trailing average over the
          recent admissible series. Uses ``window`` and ``min_coverage``.
        * ``"rolling_mean"`` — a trailing moving-window mean across the series.
          Uses ``window`` and ``min_coverage``.

        All three are descriptive only: they name no cause and carry no p-value or
        significance claim, and under-covered windows are left blank so missing
        data stays visible. Stale, inadmissible, insufficient, or out-of-bounds
        requests return a structured refusal with a distinct reason and no
        estimate. Params that do not belong to the chosen ``method`` must be left
        unset. For a before/after or condition difference use ``paired_test``; for
        a two-metric lagged association use ``correlate``.

        Pass the optional ``session_id`` from ``research_trace_open`` to record
        this call in a research session's multiplicity trace; without it the tool
        behaves exactly as before and writes no trace row.
        """
        if method not in analyze_methods:
            raise ValueError(
                f"unknown analyze method {method!r}; expected one of {', '.join(analyze_methods)}"
            )
        if method == "change_point":
            if window is not None or min_coverage is not None:
                raise ValueError("analyze method 'change_point' takes only min_side_observations")
            return _dispatch_analytical_with_trace(
                warehouse_path=warehouse_path,
                tool_name="change_point",
                session_id=session_id,
                request={"metric_id": metric_id, "min_side_observations": min_side_observations},
                dispatch=lambda: warehouse_server.change_point(
                    metric_id,
                    min_side_observations=min_side_observations,
                    warehouse_path=warehouse_path,
                ),
            )
        if min_side_observations is not None:
            raise ValueError(f"analyze method {method!r} takes only window and min_coverage")
        server_fn = (
            warehouse_server.smoothed_average
            if method == "smoothed_average"
            else warehouse_server.rolling_mean
        )
        return _dispatch_analytical_with_trace(
            warehouse_path=warehouse_path,
            tool_name=method,
            session_id=session_id,
            request={"metric_id": metric_id, "window": window, "min_coverage": min_coverage},
            dispatch=lambda: server_fn(
                metric_id,
                window=window,
                min_coverage=min_coverage,
                warehouse_path=warehouse_path,
            ),
        )

    # --- Stage 3 pre-registered lagged association ------------------------ #
    # correlate reports a pre-registered association between two metrics at a
    # caller-declared integer-day lag. It is a thin wrapper that delegates to the
    # engine analytical path (prepare_paired_input -> invoke_analytical_tool):
    # it computes no statistics, does no pairing, and issues no raw SQL. The agent
    # MUST pre-register the hypothesis (pair, lag, expected direction) before
    # seeing the result; an unsupported lag, missing justification, inadmissible
    # input, no overlap, or weak support returns a structured refusal with a
    # distinct reason and no estimate.

    @mcp.tool()
    def correlate(
        left_metric_id: str,
        right_metric_id: str,
        lag_days: int,
        expected_direction: str,
        lag_justification: str | None = None,
        common_cause_candidates: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Report a pre-registered lagged association between two daily metrics.

        Answers one pre-registered question: are ``left_metric_id`` and
        ``right_metric_id`` associated at ``lag_days`` (whole days; the right
        series responds ``lag_days`` after the left), in the
        ``expected_direction`` ("positive" or "negative") you declare up front?
        A 4..14 day lag requires ``lag_justification``; lags beyond 14 days are
        refused. Supply any plausible ``common_cause_candidates`` BEFORE
        computation so the common-cause confound is flagged.

        Returns Spearman's rho with observed/expected direction, a direction
        match, an association band, raw and effective sample sizes, lag and
        overlap metadata, imputation percentage, validity status, and a
        closed-vocabulary confound checklist. It is descriptive association only:
        it never asks for or reports a p-value, significance, the best lag, the
        best pair, or a cause. Inadmissible, no-overlap, weak-support, or
        unsupported-lag requests return a structured refusal with a distinct
        reason and no estimate.

        Pass the optional ``session_id`` from ``research_trace_open`` to record
        this pre-registered hypothesis in a research session's multiplicity trace;
        without it the tool behaves exactly as before and writes no trace row.
        """
        return _dispatch_analytical_with_trace(
            warehouse_path=warehouse_path,
            tool_name="correlate",
            session_id=session_id,
            request={
                "left_metric_id": left_metric_id,
                "right_metric_id": right_metric_id,
                "lag_days": lag_days,
                "expected_direction": expected_direction,
                "lag_justification": lag_justification,
                "common_cause_candidates": common_cause_candidates,
            },
            dispatch=lambda: warehouse_server.correlate(
                left_metric_id,
                right_metric_id,
                lag_days=lag_days,
                expected_direction=expected_direction,
                lag_justification=lag_justification,
                common_cause_candidates=common_cause_candidates,
                warehouse_path=warehouse_path,
            ),
        )

    # --- Stage 3 pre-registered paired difference (before/after or condition) #
    # paired_t_test and condition_paired_t_test are exposed as ONE ``paired_test``
    # tool selected by ``kind``. Each kind routes to the SAME thin server wrapper
    # and the SAME ``_dispatch_analytical_with_trace`` call as before, preserving
    # the per-kind trace ``tool_name`` (``paired_t_test`` /
    # ``condition_paired_t_test``) and request identity, so the multiplicity trace
    # stays byte-identical to the pre-collapse surface. Both are pre-registered:
    # the agent MUST declare the split (anchor OR condition episodes), windows, and
    # expected direction before seeing the result. Descriptive only — never a
    # p-value or significance verdict, never a causal/diagnostic/population claim.
    paired_kinds = ("before_after", "condition_label")

    @mcp.tool()
    def paired_test(
        kind: str,
        metric_id: str,
        before_days: int,
        after_days: int,
        expected_direction: str,
        anchor_date: str | None = None,
        condition_label: str | None = None,
        episodes: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Report a pre-registered before/after paired difference for one metric.

        ``kind`` selects how the before/after split is defined:

        * ``"before_after"`` — split around a single ``anchor_date`` (YYYY-MM-DD):
          the ``before_days`` before vs the ``after_days`` after, in the
          ``expected_direction`` ("increase"/"decrease") declared up front.
          ``condition_label`` / ``episodes`` must be left unset.
        * ``"condition_label"`` — split by the operator's declared on-condition
          ``episodes`` for one ``condition_label`` (a single non-empty string,
          never a list): ``before_days`` off-label before each episode vs
          ``after_days`` on-label into it. Omit ``episodes`` to use the stored
          declaration recorded via ``condition_episode`` (label matching is exact,
          case-sensitive); the response then carries an ``episodes_source``
          disclosure naming the episode ids used. ``anchor_date`` must be unset.

        Observations are matched into pairs and the paired differences summarized
        as a mean and its dispersion (standard deviation, standard error, and a
        descriptive difference interval), plus whether the observed direction
        matches your expectation. It is descriptive only: never a p-value or
        "significant" verdict; the anchor/label only splits the windows and is not
        shown to cause any change; no causal/diagnostic/treatment/population-norm
        claim. Inadmissible, stale, no-valid-pairs, too-few-pairs/episodes,
        overlapping-episode, or constant-difference requests return a structured
        refusal with a distinct reason and no estimate.

        Pass the optional ``session_id`` from ``research_trace_open`` to record
        this pre-registered hypothesis in a research session's multiplicity trace;
        without it the tool behaves exactly as before and writes no trace row.
        """
        if kind not in paired_kinds:
            raise ValueError(
                f"unknown paired_test kind {kind!r}; expected one of {', '.join(paired_kinds)}"
            )
        if kind == "before_after":
            if condition_label is not None or episodes is not None:
                raise ValueError(
                    "paired_test kind 'before_after' takes anchor_date, not "
                    "condition_label/episodes"
                )
            if not anchor_date:
                raise ValueError("paired_test kind 'before_after' requires anchor_date")
            return _dispatch_analytical_with_trace(
                warehouse_path=warehouse_path,
                tool_name="paired_t_test",
                session_id=session_id,
                request={
                    "metric_id": metric_id,
                    "anchor_date": anchor_date,
                    "before_days": before_days,
                    "after_days": after_days,
                    "expected_direction": expected_direction,
                },
                dispatch=lambda: warehouse_server.paired_t_test(
                    metric_id,
                    anchor_date=anchor_date,
                    before_days=before_days,
                    after_days=after_days,
                    expected_direction=expected_direction,
                    warehouse_path=warehouse_path,
                ),
            )
        # kind == "condition_label"
        if anchor_date is not None:
            raise ValueError(
                "paired_test kind 'condition_label' takes condition_label/episodes, not anchor_date"
            )
        if not condition_label:
            raise ValueError("paired_test kind 'condition_label' requires condition_label")
        # Resolve the stored declaration BEFORE building the trace request, so the
        # recorded hypothesis identity carries the actual episode set used (two
        # calls under different stored states are different hypotheses;
        # stored-vs-hand-declared of the same set is the same hypothesis).
        episodes_source: dict[str, Any] | None = None
        declared = episodes
        if declared is None:
            stored = warehouse_server.stored_condition_episodes(
                condition_label, warehouse_path=warehouse_path
            )
            declared = [{"start_day": ep["start_day"], "end_day": ep["end_day"]} for ep in stored]
            episodes_source = {
                "kind": "stored_declaration",
                "condition_label": condition_label,
                "episode_ids": [ep["episode_id"] for ep in stored],
                "episodes": declared,
            }
        resolved = declared
        payload = _dispatch_analytical_with_trace(
            warehouse_path=warehouse_path,
            tool_name="condition_paired_t_test",
            session_id=session_id,
            request={
                "metric_id": metric_id,
                "condition_label": condition_label,
                "episodes": resolved,
                "before_days": before_days,
                "after_days": after_days,
                "expected_direction": expected_direction,
            },
            dispatch=lambda: warehouse_server.condition_paired_t_test(
                metric_id,
                condition_label=condition_label,
                episodes=resolved,
                before_days=before_days,
                after_days=after_days,
                expected_direction=expected_direction,
                warehouse_path=warehouse_path,
            ),
        )
        if episodes_source is not None:
            # Wrapper-layer disclosure only — the engine envelope itself stays
            # byte-identical with explicit declaration of the same set.
            payload["episodes_source"] = episodes_source
        return payload

    # --- Agent-mediated profile capture ------------------------------------ #
    # The bounded write path for stable baseline profile facts. These live on
    # the DEFAULT agent-safe surface (not the operator-only surface) because
    # bounded capture is the supported agent workflow. Both delegate straight to
    # the store boundary, which enforces the allowlist; unsupported/derived keys
    # (e.g. ``age``) come back as a structured ``rejected`` response.

    @mcp.tool()
    def profile_context_supported_fields() -> dict[str, Any]:
        """List the bounded baseline-profile attributes that can be captured.

        Returns each supported ``attribute_key`` with its value shape (and, for
        enums, the allowed values) so the agent can discover the surface before
        writing. Keys outside this set — including derived ones like ``age`` —
        are not storable.
        """
        return warehouse_server.supported_profile_fields()

    @mcp.tool()
    def profile_context_record(
        attribute_key: str,
        value: str | int | float,
        effective_start_utc: str | None = None,
        source_ref: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Record one bounded baseline profile fact (agent-mediated capture).

        ``attribute_key`` must be in the supported allowlist (see
        ``profile_context_supported_fields``). A supported fact is stored as a new
        ``agent_profile_capture`` assertion (superseding any prior open one) and
        returned with ``status='recorded'``; an unsupported or derived key, or a
        value that does not fit the field, is returned with ``status='rejected'``
        and an explicit reason rather than silently accepted.
        """
        return warehouse_server.record_profile_context(
            attribute_key,
            value,
            effective_start_utc=effective_start_utc,
            source_ref=source_ref,
            notes=notes,
            warehouse_path=warehouse_path,
        )

    # --- Interview routing (Phase 5 slice 2, HUMAN_FACING.md Part B) ------- #
    # Interview phase 1 (Direction): resolve the human's chosen health direction
    # to a track — its signal route + the profile slots grounding must fill —
    # never an "analyse everything" default. The bounded-open track registry and
    # the resolving-route safety rail live in ``premura.ui.interview_tracks``
    # (#41); the engine-backed resolver is injected at server build. This tool is
    # a pure proposal: it writes NO profile fact (capture stays with
    # ``profile_context_record``) and refuses a dead-end direction rather than
    # fabricating a route.

    @mcp.tool()
    def interview_route(direction: str) -> dict[str, Any]:
        """Resolve a chosen health direction to its interview track (phase 1).

        Give the direction the human picked (e.g. ``sleep``). Returns the track's
        ``signal_route`` and ``required_slots`` plus ``missing_slots`` — the
        allowlisted baseline-profile facts still unset that phase-2 grounding
        should propose to capture, one at a time, via ``profile_context_record``.
        This tool writes NO profile fact of its own. A direction with no analysis
        behind it is refused with a dead-end reason (``status='refused'``) rather
        than fabricating a route — interview before metrics, never a dead end.
        """
        return warehouse_server.interview_route(direction, warehouse_path=warehouse_path)

    # --- Interview device branch (onboarding arc gap #2) ------------------- #
    # Interview phase 1b (Devices): after learning what the human wants to know,
    # inventory what data/devices they HAVE and guide collection. Mirrors
    # interview_route but pointed at the ingest side - the bounded-open device
    # registry + resolving-parser safety rail live in ``premura.ui.device_tracks``;
    # the parser-backed resolver is injected at server build. Pure proposal: it
    # writes nothing and only guides toward data a registered parser can read.

    @mcp.tool()
    def interview_devices(device: str | None = None) -> dict[str, Any]:
        """Inventory collectable data sources, or resolve one to collection guidance.

        Call with no argument to get the full inventory of data sources Premura
        can ingest - each with a ``source_kind`` and a ``collection_hint`` telling
        the human where/how to gather it ("Garmin -> request your data export").
        Pass a ``device`` (e.g. ``garmin``) to resolve just that one. A device
        with no parser behind it is refused (``status='refused'``) rather than
        guiding the human to collect data nothing can read. Writes NOTHING.
        """
        if device is None:
            return warehouse_server.device_inventory()
        return warehouse_server.device_route(device)

    # --- Agent-mediated condition-episode capture (one parameterized tool) - #
    # record / list / retract are exposed as ONE ``condition_episode`` tool
    # selected by ``op``. Each op routes to the SAME store-boundary server method
    # as before (the allowlist, supersede-with-history, and retract-with-reason
    # rules live there, unchanged). Declarations are recorded, never verified;
    # episodes are NEVER auto-detected or suggested from the data. This is the
    # bounded agent-mediated write path behind off/on questions (``paired_test``
    # with kind ``condition_label``).

    @mcp.tool()
    def condition_episode(
        op: str,
        condition_label: str | None = None,
        start_day: str | None = None,
        end_day: str | None = None,
        supersedes_episode_id: int | None = None,
        note: str | None = None,
        source_ref: str | None = None,
        include_history: bool = False,
        episode_id: int | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Record, list, or retract operator-declared condition episodes.

        ``op`` selects the operation:

        * ``"record"`` — record one episode. Requires ``condition_label`` (the
          operator's own word for the condition — any non-empty string, recorded
          never verified; matching is exact after trimming and case-sensitive) and
          ``start_day`` (``YYYY-MM-DD``). Omit ``end_day`` while ongoing (ongoing
          episodes are record-keeping only; analyses use closed episodes). Pass
          ``supersedes_episode_id`` to correct an earlier declaration (the old row
          stays in history). A declaration overlapping a current episode of the
          same label returns ``status='rejected'`` with the reason.
        * ``"list"`` — list stored declarations (current by default). Filter by
          ``condition_label``; pass ``include_history=True`` to also see superseded
          and retracted declarations (the append-only trail). Use this before
          running ``paired_test`` (kind ``condition_label``) without explicit
          episodes.
        * ``"retract"`` — withdraw one current declaration. Requires ``episode_id``
          and ``reason``; the row stays in history marked retracted (nothing is
          deleted). A missing, already-retracted, or superseded id returns
          ``status='rejected'`` with the reason.
        """
        if op == "record":
            if not condition_label:
                raise ValueError("condition_episode op 'record' requires condition_label")
            if not start_day:
                raise ValueError("condition_episode op 'record' requires start_day")
            return warehouse_server.record_condition_episode(
                condition_label,
                start_day,
                end_day,
                supersedes_episode_id=supersedes_episode_id,
                note=note,
                source_ref=source_ref,
                warehouse_path=warehouse_path,
            )
        if op == "list":
            return warehouse_server.list_condition_episodes(
                condition_label,
                include_history=include_history,
                warehouse_path=warehouse_path,
            )
        if op == "retract":
            if episode_id is None:
                raise ValueError("condition_episode op 'retract' requires episode_id")
            if not reason:
                raise ValueError("condition_episode op 'retract' requires reason")
            return warehouse_server.retract_condition_episode(
                episode_id,
                reason,
                warehouse_path=warehouse_path,
            )
        raise ValueError(
            f"unknown condition_episode op {op!r}; expected one of record, list, retract"
        )

    # --- Manual single-row load (the paved road, m8 WP05) - one parameterized #
    # tool selected by ``op``. ``suggest_metric`` and ``load`` each delegate
    # entirely to ``warehouse_server`` / ``store.manual_load`` / ``store.loader``
    # — zero conversion or validation logic lives in this MCP layer. This is the
    # only sanctioned path for manually-transcribed data; a batch importer is a
    # parser (see ``src/premura/parsers/PARSER_CONTRIBUTING.md``), not this tool.

    @mcp.tool()
    def ingest_row(
        op: str,
        field_name: str | None = None,
        metric_id: str | None = None,
        ts_utc: str | None = None,
        unit: str | None = None,
        source_ref: str | None = None,
        value_num: float | None = None,
        value_text: str | None = None,
    ) -> dict[str, Any]:
        """Look up a metric id, or manually load one transcribed observation.

        ``op`` selects the operation:

        * ``"suggest_metric"`` — requires ``field_name`` (a raw column/test
          label). Resolves it to a canonical ``metric_id`` exactly as
          ``parsers.lookup.suggest_metric`` would for a parser author; a null
          result means follow the standards-first ladder or stop.
        * ``"load"`` — requires ``metric_id``, ``ts_utc`` (ISO 8601),
          ``unit`` (as observed — what the source states, never pre-converted),
          ``source_ref`` (mandatory plain-text provenance, e.g. "operator
          spreadsheet row 14"), and one of ``value_num`` / ``value_text``.
          Builds a single-row batch and loads it through the exact same
          boundary every parser uses (``store.loader.load``): unit
          convert-or-refuse and ``hp.ingest_skip`` persistence apply with zero
          special-casing. Missing/empty ``source_ref`` is refused before the
          loader is even opened — provenance is never fabricated. Returns
          ``status='loaded'`` with the stored canonical unit, or
          ``status='refused'`` with the reason (also queryable in
          ``hp.ingest_skip`` for unit refusals).

        Not a bulk importer: one row per call, by design. Batches of real
        source artifacts deserve a parser.
        """
        if op == "suggest_metric":
            if not field_name:
                raise ValueError("ingest_row op 'suggest_metric' requires field_name")
            return warehouse_server.ingest_row_suggest_metric(field_name)
        if op == "load":
            if not metric_id:
                raise ValueError("ingest_row op 'load' requires metric_id")
            if not ts_utc:
                raise ValueError("ingest_row op 'load' requires ts_utc")
            if not unit:
                raise ValueError("ingest_row op 'load' requires unit")
            return warehouse_server.ingest_row_load(
                metric_id,
                ts_utc,
                unit,
                source_ref,
                value_num=value_num,
                value_text=value_text,
                warehouse_path=warehouse_path,
            )
        raise ValueError(f"unknown ingest_row op {op!r}; expected one of suggest_metric, load")

    # --- Runtime orchestrator: roles, handoff trace, blocking answer gate -- #
    # Slice 1 of src/premura/ui/OPERATING_ROLES.md (decision note
    # 0013). The operating agent is the intelligence; these tools are the thin
    # deterministic layer: the role registry (discovery), the handoff trace
    # (session-log file, never the research trace), and the audit gate whose
    # verified envelope structurally cannot be obtained without an audit.

    @mcp.tool()
    def operating_roles() -> dict[str, Any]:
        """List the registered operating-role declarations.

        Each declaration carries the role's job, allowed surfaces, handoff
        outputs, and boundaries. The registry is bounded but open: new roles
        register declarations; this is never a closed persona list.
        """
        return warehouse_server.operating_roles()

    @mcp.tool()
    def orchestrator_handoff(
        runtime_session_id: str,
        from_id: str,
        to_id: str,
        task_summary: str,
        status: str,
        inputs_ref: str | None = None,
        outputs_ref: str | None = None,
        surface_touched: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Record one cross-role handoff in the orchestrator trace.

        ``status`` is one of dispatched/returned/refused/failed. All fields are
        compact PHI-safe references — never raw health data. Handoffs land in
        the session-log store, not the research trace, so multiplicity counts
        stay uncontaminated.
        """
        return warehouse_server.orchestrator_handoff(
            runtime_session_id,
            from_id,
            to_id,
            task_summary,
            status,
            inputs_ref=inputs_ref,
            outputs_ref=outputs_ref,
            surface_touched=surface_touched,
            reason=reason,
            session_log_path=session_log_path,
        )

    @mcp.tool()
    def answer_audit(draft: str, session_id: str | None = None) -> dict[str, Any]:
        """Audit a draft health answer against its research-trace session.

        Deterministic v1 checks: the named session must exist and have recorded
        analytical calls; the measured search-effort disclosure and refusal
        counts are computed from trace rows, never trusted from prose. The
        verdict is recorded keyed by the draft's sha256 — ``present_answer``
        requires a passing verdict for exactly that draft. The audit creates no
        new evidence and reruns nothing.
        """
        return warehouse_server.answer_audit(
            draft,
            session_id=session_id,
            warehouse_path=warehouse_path,
            session_log_path=session_log_path,
        )

    @mcp.tool()
    def present_answer(
        draft: str,
        interprets_health: bool,
        acknowledge_unverified: bool = False,
    ) -> dict[str, Any]:
        """Bless a final answer for presentation (the blocking gate).

        A health-interpreting draft is blessed only with a passing
        ``answer_audit`` verdict for exactly this draft; the blessed envelope
        carries the measured disclosure and mandatory caveats. Without one the
        gate refuses (``acknowledge_unverified=True`` after a failed audit
        returns the draft with a prominent NOT TRACE-VERIFIED warning instead).
        Non-interpreting drafts pass through marked as such.
        """
        return warehouse_server.present_answer(
            draft,
            interprets_health=interprets_health,
            acknowledge_unverified=acknowledge_unverified,
            session_log_path=session_log_path,
        )

    # --- Runtime improvement queue (OPERATING_ROLES.md slice 3) ------------ #
    # The `improvement_scan` role's write/read path: a PRIVATE, LOCAL queue in
    # the session-log store (never the warehouse, never GitHub). Sharing
    # (share packets, public writes) is later-slice work (slice 4).

    @mcp.tool()
    def improvement_queue_record(
        kind: str,
        summary: str,
        privacy_level: str,
        suggested_action: str | None = None,
        trace_refs: list[str] | None = None,
        github_refs: list[str] | None = None,
        status: str = "open",
        kind_description: str | None = None,
    ) -> dict[str, Any]:
        """Record one improvement candidate in the private local queue.

        ``kind`` must be a REGISTERED id in the bounded, open kind registry
        (seeded: ``parser_gap`` / ``analysis_gap`` / ``teaching_gap`` /
        ``workflow_gap`` / ``docs_gap`` / ``other``). Pass ``kind_description``
        to register a new kind on the spot — the documented rule for adding a
        kind, with no central edit. ``status`` defaults to ``"open"`` and
        ``privacy_level`` must be one of ``minimal`` / ``structural`` /
        ``synthetic_example`` (which sharing level this item would need IF it
        were ever shared — sharing itself is not implemented yet). This is a
        LOCAL, PRIVATE write: nothing here reaches GitHub. An out-of-vocabulary
        value or an unregistered kind without a description comes back as a
        structured ``rejected`` response.
        """
        return warehouse_server.improvement_queue_record(
            kind,
            summary,
            privacy_level,
            suggested_action=suggested_action,
            trace_refs=trace_refs,
            github_refs=github_refs,
            status=status,
            kind_description=kind_description,
            session_log_path=session_log_path,
        )

    @mcp.tool()
    def improvement_queue_list(
        status: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        """Read back the private local improvement queue, optionally filtered.

        A pure, strictly read-only lookup; a session log with no recorded
        items returns an empty list rather than an error. Filter by the fixed
        ``status`` vocabulary and/or an exact ``kind`` id.
        """
        return warehouse_server.improvement_queue_list(
            status=status,
            kind=kind,
            session_log_path=session_log_path,
        )

    # --- Share packets (OPERATING_ROLES.md slice 4) ------------------------- #
    # Renders a privacy-graded VIEW over one stored improvement-queue item —
    # production only. No code path here writes to GitHub or off this machine;
    # posting a packet is a separate, explicitly human-approved act (see
    # ``premura.share_packet.NOT_POSTED_NOTICE`` and RUNTIME_AGENT.md
    # "Privacy and share-packet boundary").

    @mcp.tool()
    def share_packet_render(
        item_id: str,
        level: str,
        format: str = "json",
    ) -> dict[str, Any]:
        """Render one improvement-queue item as a reviewable public share packet.

        ``level`` selects one of the three draft sharing levels: ``minimal``
        (say only that a gap of this kind was encountered), ``structural``
        (adds bookkeeping counts plus a couple of fabricated illustrative
        field examples), or ``synthetic_example`` (adds one fully fabricated
        record shaped like a generic source export). All three are generated
        views over the stored item and NEVER echo its free-text ``summary``/
        ``suggested_action`` — see the module docstring for why. This tool
        PRODUCES a packet only; it writes nothing to GitHub or off this
        machine. Posting is a separate, explicitly human-approved act.
        ``format="markdown"`` adds a generated human-readable export beside
        the structured fields.
        """
        return warehouse_server.share_packet_render(
            item_id,
            level,
            format=format,
            session_log_path=session_log_path,
        )

    # --- Session research trace --------------------------------------------- #
    # These three tools expose the multiplicity-disclosure trace as the SUPPORTED
    # agent workflow, so they live on the DEFAULT agent-safe surface (the operator
    # surface inherits them by registering this same default set). They orchestrate
    # the pure ``premura.trace`` service over a writable warehouse connection; they
    # compute no statistics and read no raw ``hp.*`` health rows. The disclosure
    # tool returns derived counts only — it never reaches for ``query_warehouse``.

    @mcp.tool()
    def research_trace_open(client_label: str | None = None) -> dict[str, Any]:
        """Open an explicit research session and return a stable ``session_id``.

        Pass the returned ``session_id`` to ``change_point`` / ``smoothed_average``
        / ``correlate`` to record each analytical call, then to
        ``research_trace_mark_surfaced`` and ``research_trace_disclosure``. The
        optional ``client_label`` is a short label for the operating agent/client.
        Returns the session id plus the warehouse fingerprint and schema version the
        disclosure will be computed against.
        """
        with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
            session = trace.open_research_session(conn, client_label=client_label)
            return session.to_dict()

    @mcp.tool()
    def research_trace_mark_surfaced(
        session_id: str,
        call_id: str,
        role: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Mark a recorded analytical call as used in the user-facing answer.

        ``role`` describes how the result was used (e.g. ``claim``, ``summary``,
        ``recommendation``, ``next_step``, ``caveat``) and ``rationale`` is a short
        explanation. "Surfaced" is an explicit agent presentation mark — never a
        significance judgment. An unknown session/call returns ``not_found``; a
        ``call_id`` from a different session returns ``invalid_reference``; an empty
        ``role``/``rationale`` returns a validation error.
        """
        with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
            outcome = trace.mark_surfaced(conn, session_id, call_id, role, rationale)
            if isinstance(outcome, trace.TraceError):
                return outcome.to_dict()
            return {**outcome.to_dict(), "status": outcome.status, "session_id": session_id}

    @mcp.tool()
    def research_trace_disclosure(
        session_id: str,
        format: str = "json",
        include_calls: bool = True,
    ) -> dict[str, Any]:
        """Read/export a research session's measured multiplicity disclosure.

        Reports the raw analytical-call count and the unique-hypothesis count (N)
        derived from the recorded rows (exact retries collapse; refusals still
        count toward N), the surfaced (K) summary, the refusal breakdown, and a
        bounded list of stable call/result references — framed as "K user-facing
        findings among N unique hypotheses examined", never "significant results".
        ``format="markdown"`` returns a generated human-readable export beside the
        structured counts. An unknown session returns an explicit ``not_found``,
        not an empty successful disclosure.
        """
        with warehouse_server._open_warehouse_writable(warehouse_path) as conn:
            disclosure = trace.get_research_disclosure(
                conn, session_id, include_calls=include_calls
            )
            if isinstance(disclosure, trace.TraceError):
                return disclosure.to_dict()
            payload = disclosure.to_dict()
            if format == "markdown":
                payload["disclosure_markdown"] = trace.disclosure_to_markdown(disclosure)
            return payload

    # --- PubMed grounding ---------------------------------------------------- #
    # Exactly two tools expose Premura's own PubMed grounding behavior on the
    # default agent-safe surface: search finds candidates, fetch-by-PMID creates
    # citeable records. They delegate to the PubMed provider wrappers in
    # ``premura.mcp.server`` and add NO broad third-party PubMed surface (no
    # full-text, deep analysis, MeSH, Europe PMC, Unpaywall, or related-article
    # tools). PubMed context is literature only: it reads no ``hp.*`` rows, runs
    # no SQL, and never computes a claim about the user's own warehouse data.

    @mcp.tool()
    def pubmed_search(
        query: str,
        limit: int = 20,
        sort: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Search PubMed for CANDIDATE literature records (candidates only).

        Returns discovery hints, NOT citeable evidence: every candidate carries
        ``citation_status = candidate_only`` and the payload restates the citation
        rule. To cite a record in a final answer you MUST first retrieve it with
        ``pubmed_fetch`` by its exact ``pmid`` — a search candidate (even with a
        title or snippet) is never citeable on its own.

        Pass the research-trace ``session_id`` when literature work belongs to a
        recorded session: the lookup is then recorded as an EVIDENCE-SOURCE call
        (record → dispatch → finalize, same seam as the analytical tools).
        Evidence rows never count toward "N unique hypotheses examined"; they
        exist so the answer-audit gate can verify citations. Without
        ``session_id`` the behavior is exactly the untraced behavior.

        This is literature grounding only. It does not read the user's health
        warehouse and does not compute, confirm, or quantify any claim about the
        user's own data; it never produces diagnosis, treatment, or causal claims.
        Ordinary outcomes (``available`` / ``no_results`` / ``provider_error``)
        come back as a structured dict.
        """
        return _dispatch_analytical_with_trace(
            warehouse_path=warehouse_path,
            tool_name="pubmed_search",
            session_id=session_id,
            request={"query": query, "limit": limit, "sort": sort},
            dispatch=lambda: warehouse_server.pubmed_search(query, limit=limit, sort=sort),
            call_kind=trace.CALL_KIND_EVIDENCE_SOURCE,
        )

    @mcp.tool()
    def pubmed_fetch(pmid: str, session_id: str | None = None) -> dict[str, Any]:
        """Fetch one CITEABLE PubMed record by its exact PMID.

        A successful fetch returns a record with
        ``citation_status = citeable_fetched_record`` plus the ``pubmed_url``
        provenance an honest citation needs. Final user-facing answers may cite
        ONLY records obtained this way; ``pubmed_search`` candidates are discovery
        hints and are never citeable until fetched here by exact PMID.

        Pass the research-trace ``session_id`` whenever the fetched record may be
        cited in a final answer: the fetch is then recorded as an EVIDENCE-SOURCE
        call, and the answer-audit gate's citation binding accepts a cited PMID
        ONLY when this session recorded a successful fetch for it. A fetch made
        without ``session_id`` is untraced and cannot back a citation in an
        audited answer. Evidence rows never count toward "N unique hypotheses
        examined".

        This is literature grounding only. It does not read the user's health
        warehouse and does not compute, confirm, or quantify any claim about the
        user's own data; it never produces diagnosis, treatment, or causal claims.
        Ordinary outcomes (``available`` / ``invalid_pmid`` / ``unavailable`` /
        ``provider_error``) come back as a structured dict; missing optional
        metadata stays explicitly absent and is never fabricated.
        """
        return _dispatch_analytical_with_trace(
            warehouse_path=warehouse_path,
            tool_name=trace.PUBMED_FETCH_TOOL_NAME,
            session_id=session_id,
            request={"pmid": pmid},
            dispatch=lambda: warehouse_server.pubmed_fetch(pmid),
            call_kind=trace.CALL_KIND_EVIDENCE_SOURCE,
        )


def build_server(
    *, warehouse_path: Path | None = None, session_log_path: Path | None = None
) -> FastMCP:
    """Build the default agent-safe MCP server surface.

    Exposes catalog, summary, and the six approved Stage 2 signal tools (all
    read-only), plus the bounded agent-mediated profile-capture tools
    ``profile_context_supported_fields`` and ``profile_context_record``. The
    record tool is the only write path on this surface and is constrained to the
    profile allowlist (unsupported/derived keys are rejected, not stored).
    ``query_warehouse`` is intentionally excluded — use :func:`build_operator_server`
    to obtain a surface that includes the raw SQL escape hatch.

    ``session_log_path`` redirects the runtime-orchestrator tools' session-log
    file alongside ``warehouse_path`` so a sandboxed/live-trial server never
    writes handoffs or audit verdicts into the operator's real session log.
    """
    mcp = FastMCP(
        "premura",
        instructions=(
            "Local-first Premura warehouse. Read-only Stage 2 analysis (catalog, "
            "summary, signal tools) plus a bounded agent-mediated profile-capture "
            "write path (profile_context_record, constrained to the profile "
            "allowlist). No raw SQL on this surface."
        ),
    )
    _register_default_tools(mcp, warehouse_path=warehouse_path, session_log_path=session_log_path)
    return mcp


def build_operator_server(
    *, warehouse_path: Path | None = None, session_log_path: Path | None = None
) -> FastMCP:
    """Build the operator MCP server surface — lower-guarantee expert mode.

    Registers the full default tool set PLUS ``query_warehouse``, the raw SQL
    escape hatch.  This surface is intended for operator/developer use only and
    MUST NOT be used by an autonomous agent without explicit user approval.

    No Stage 2 validity or freshness guarantees apply to results returned by
    ``query_warehouse``; callers own all result interpretation.  The signal-backed
    and catalog tools on this surface retain their normal Stage 2 guarantees.
    """
    mcp = FastMCP(
        "premura-operator",
        instructions=(
            "OPERATOR MODE — lower-guarantee expert surface. "
            "Includes query_warehouse (raw SQL escape hatch). "
            "No Stage 2 validity guarantees apply to query_warehouse results. "
            "This surface must only be used after explicit user approval; "
            "it is not safe for autonomous agent consumption."
        ),
    )
    _register_default_tools(mcp, warehouse_path=warehouse_path, session_log_path=session_log_path)

    @mcp.tool()
    def query_warehouse(
        sql: str, params: list[JsonScalar] | None = None, max_rows: int = 200
    ) -> dict[str, Any]:
        """Run one read-only SQL query against the local Premura warehouse.

        OPERATOR-ONLY ESCAPE HATCH.  This tool runs arbitrary read-only SQL and
        returns raw rows without any Stage 2 validity, freshness, or imputation
        guarantees.  Results must be interpreted by the caller without assuming
        coverage or correctness.  Requires explicit user approval before use;
        autonomous agents must not invoke this tool unsupervised.
        """
        return warehouse_server.query_warehouse(
            sql,
            params,
            warehouse_path=warehouse_path,
            max_rows=max_rows,
        )

    return mcp


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv, prog="premura-mcp", operator_mode=False)
    build_server(warehouse_path=args.warehouse_path, session_log_path=args.session_log_path).run(
        transport="stdio"
    )


def main_operator(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv, prog="premura-mcp-operator", operator_mode=True)
    if not _operator_ack_granted(args):
        raise SystemExit(
            "Refusing to start premura-mcp-operator without explicit operator "
            "acknowledgment.\n"
            "This surface registers query_warehouse — arbitrary read-only SQL with "
            "NO Stage 2 validity, freshness, or imputation guarantees. It is not "
            "safe for autonomous agent use without explicit user approval.\n"
            f"To proceed, re-run with --ack, or set {_OPERATOR_ACK_ENV}=1."
        )
    build_operator_server(
        warehouse_path=args.warehouse_path, session_log_path=args.session_log_path
    ).run(transport="stdio")


def _operator_ack_granted(args: argparse.Namespace) -> bool:
    """True iff the operator explicitly acknowledged lower-guarantee mode.

    The acknowledgment is the system-enforced realization of the operator
    contract's ``explicit_user_approval_required_for_agent_use`` rule: the
    ``premura-mcp-operator`` console entry will not expose ``query_warehouse``
    unless the launcher opts in via ``--ack`` or the ``PREMURA_OPERATOR_ACK``
    environment variable.  The in-process :func:`build_operator_server` builder
    stays ungated so tests and embedders can construct the surface directly.
    """
    if getattr(args, "ack", False):
        return True
    return (os.environ.get(_OPERATOR_ACK_ENV) or "").strip().lower() in _TRUTHY


def _parse_args(
    argv: Sequence[str] | None = None,
    *,
    prog: str,
    operator_mode: bool,
) -> argparse.Namespace:
    description = (
        "Run Premura's operator MCP server over one DuckDB warehouse. "
        "Includes query_warehouse (raw SQL escape hatch). "
        "Lower-guarantee expert mode — requires explicit user approval."
        if operator_mode
        else (
            "Run Premura's local MCP server over one DuckDB warehouse: "
            "read-only Stage 2 analysis plus a bounded profile-capture write path."
        )
    )
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "--warehouse-path",
        type=Path,
        help=(
            "Explicit path to the DuckDB warehouse file. Defaults to "
            "PREMURA_DATA_DIR/duck/health.duckdb."
        ),
    )
    parser.add_argument(
        "--session-log-path",
        type=Path,
        help=(
            "Explicit path to the session log's own DuckDB file (orchestrator "
            "handoffs and answer-audit verdicts; never the warehouse). Created "
            "on first record. Defaults to the warehouse's sibling "
            "session_log.duckdb."
        ),
    )
    if operator_mode:
        parser.add_argument(
            "--ack",
            action="store_true",
            help=(
                "Acknowledge lower-guarantee operator mode. Required to launch "
                "(exposing query_warehouse, the raw read-only SQL escape hatch with "
                "no Stage 2 validity guarantees) unless PREMURA_OPERATOR_ACK is set "
                "to a truthy value."
            ),
        )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.warehouse_path is not None and not args.warehouse_path.exists():
        parser.error(f"warehouse does not exist: {args.warehouse_path}")
    return args


__all__ = ["build_operator_server", "build_server", "main", "main_operator"]


if __name__ == "__main__":
    main()
