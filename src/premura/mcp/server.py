"""Stage 3 analytical helpers over the local warehouse.

This module is the executable slice of M2. It provides small, read-only
helpers that the MCP entrypoint (:mod:`premura.mcp.entrypoint`) publishes as
FastMCP tools.

Two families of helpers live here:

* **Default catalog/summary tools** (``list_metrics`` / ``metric_summary``) —
  validity-gated catalog and summary helpers that delegate entirely to the
  Stage 2 engine (``premura.engine.list_metric_catalog`` /
  ``premura.engine.metric_summary``). They return structured validity/imputation
  envelopes with machine-branchable fields — no raw row counts, no all-time
  extrema.
* **Raw warehouse tool** (``query_warehouse``) — exploratory escape hatch that
  runs arbitrary read-only SQL against the warehouse.
* **Signal-backed tools** (``resting_hr_status`` and friends) — the supported
  path for the six approved Stage 2 answers. Each one opens the warehouse
  through the same safe read-only connection, delegates to the Stage 2 signal
  engine (``premura.engine``) rather than re-implementing any SQL, and returns
  the engine's structured result serialized into a plain, JSON-safe payload.
  None of these wrappers touch ``hp.fact_measurement`` / ``hp.fact_interval``
  directly — the engine owns that.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import engine
from ..config import settings
from ..engine import MissingInputReport, comparative_signals
from ..store import duck

if TYPE_CHECKING:
    from collections.abc import Iterator

    import duckdb

_READ_ONLY_PREFIXES = ("select", "with", "describe", "show")
_DEFAULT_QUERY_MAX_ROWS = 200
_MAX_QUERY_MAX_ROWS = 1000


def query_warehouse(
    sql: str,
    params: Sequence[object] | None = None,
    *,
    warehouse_path: Path | None = None,
    max_rows: int = _DEFAULT_QUERY_MAX_ROWS,
) -> dict[str, Any]:
    """Execute one read-only query against the warehouse and return JSON-safe rows."""
    _ensure_read_only_sql(sql)
    _ensure_bounded_positive_int("max_rows", max_rows, maximum=_MAX_QUERY_MAX_ROWS)
    with _open_warehouse(warehouse_path) as conn:
        result = conn.execute(sql, params or [])
        columns = [col[0] for col in (result.description or [])]
        fetched_rows = result.fetchmany(max_rows + 1)
        truncated = len(fetched_rows) > max_rows
        rows = [_row_to_dict(columns, row) for row in fetched_rows[:max_rows]]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "max_rows": max_rows,
            "truncated": truncated,
        }


@contextmanager
def _open_warehouse(warehouse_path: Path | None) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the warehouse through the single safe read-only path and always close it.

    This is the one place that resolves the warehouse location and opens a
    read-only DuckDB connection. Both the raw SQL tools and the signal-backed
    wrappers route through here so they share identical, read-only access.
    """
    conn = duck.connect(warehouse_path or settings.warehouse_path, read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def list_metrics(
    *, warehouse_path: Path | None = None, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List canonical metrics as validity-gated catalog entries.

    Delegates entirely to the Stage 2 engine helper
    (:func:`premura.engine.list_metric_catalog`).  Returns explicit
    ``validity_status`` / ``validity_window`` / ``missing_data_policy`` fields
    per metric so downstream callers can branch on availability without parsing
    prose.  No raw row counts or all-time extrema are exposed.
    """
    _ensure_non_negative_int("limit", limit)
    _ensure_non_negative_int("offset", offset)
    # Resolve the paged metric IDs from dim_metric via the read-only connection,
    # then delegate all freshness/coverage logic to the Stage 2 catalog helper.
    id_result = query_warehouse(
        "SELECT metric_id FROM hp.dim_metric ORDER BY metric_id LIMIT ? OFFSET ?",
        [limit, offset],
        warehouse_path=warehouse_path,
    )
    metric_ids = [row["metric_id"] for row in id_result["rows"]]
    if not metric_ids:
        return []
    with _open_warehouse(warehouse_path) as conn:
        entries = engine.list_metric_catalog(metric_ids, conn)
    return [entry.to_dict() for entry in entries]


def metric_summary(metric_id: str, *, warehouse_path: Path | None = None) -> dict[str, Any]:
    """Return a validity summary for one canonical metric over a fixed 30-day window.

    Delegates entirely to the Stage 2 engine helper
    (:func:`premura.engine.metric_summary`).  Returns explicit
    ``validity_status``, ``sample_size``, ``imputed_proportion``, and
    ``gap_count`` fields so downstream callers can branch on availability and
    coverage without parsing prose.  No all-time extrema (min/max/avg) or raw
    row counts are exposed.

    Unknown metrics return an ``unavailable`` entry (not ``None``) — the
    structured envelope distinguishes unknown from known-but-empty.
    """
    if not metric_id.strip():
        raise ValueError("metric_id must not be empty")
    with _open_warehouse(warehouse_path) as conn:
        entry = engine.metric_summary(metric_id, conn)
    return entry.to_dict()


# --------------------------------------------------------------------------- #
# Signal-backed Stage 3 tools (WP04)
#
# Each wrapper opens the warehouse through the same safe read-only path the raw
# tools use, then delegates entirely to the Stage 2 signal engine. There is NO
# raw SQL against the fact tables in any of these — the engine owns the math and
# the freshness/sufficiency verdicts; the wrapper only serializes the result.
# --------------------------------------------------------------------------- #

# The five spans below are advisory: the Stage 2 signals compute over their own
# fixed windows. We accept these arguments for a stable, self-describing tool
# surface and add a transparent caveat when a caller asks for a window the
# engine does not currently honor, rather than silently pretend it was applied.
_REQUESTED_WINDOW_CAVEAT = (
    "A custom window of {requested} day(s) was requested, but this signal "
    "computes over its own fixed window; the requested value was not applied."
)


def resting_hr_status(*, warehouse_path: Path | None = None) -> dict[str, Any]:
    """Latest resting heart rate with an explicit freshness verdict (status family)."""
    return _run_signal("resting_hr_status", warehouse_path=warehouse_path)


def resting_hr_trend(
    *, lookback_days: int | None = None, warehouse_path: Path | None = None
) -> dict[str, Any]:
    """Recent resting-heart-rate trend with gap and imputation visibility (trend family)."""
    _ensure_optional_window("lookback_days", lookback_days, minimum=7, maximum=90)
    return _run_signal(
        "resting_hr_trend", warehouse_path=warehouse_path, requested_window=lookback_days
    )


def steps_trend(
    *, lookback_days: int | None = None, warehouse_path: Path | None = None
) -> dict[str, Any]:
    """Recent daily-steps trend without imputing missing days (trend family)."""
    _ensure_optional_window("lookback_days", lookback_days, minimum=7, maximum=90)
    return _run_signal(
        "steps_trend", warehouse_path=warehouse_path, requested_window=lookback_days
    )


def weight_trend(
    *, lookback_days: int | None = None, warehouse_path: Path | None = None
) -> dict[str, Any]:
    """Recent body-weight trend with freshness and carried-forward caveats (trend family)."""
    _ensure_optional_window("lookback_days", lookback_days, minimum=7, maximum=120)
    return _run_signal(
        "weight_trend", warehouse_path=warehouse_path, requested_window=lookback_days
    )


def sleep_deep_pct_baseline(
    *, baseline_days: int | None = None, warehouse_path: Path | None = None
) -> dict[str, Any]:
    """Compare the latest deep-sleep percentage to the user's own baseline (baseline family)."""
    _ensure_optional_window("baseline_days", baseline_days, minimum=7, maximum=60)
    return _run_signal(
        "sleep_deep_pct_baseline",
        warehouse_path=warehouse_path,
        requested_window=baseline_days,
    )


def hrv_change_around_date(
    anchor_date: str,
    *,
    window_days: int | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Compare overnight HRV before/after a user-supplied anchor date (change family).

    The user-supplied ``anchor_date`` flows straight through to the engine's
    explicit-anchor path (:func:`premura.engine.comparative_signals.hrv_change_around_date`),
    NOT the midpoint default that ``engine.compute`` would use. No significance
    or causation is ever claimed.
    """
    parsed_anchor = _parse_anchor_date(anchor_date)
    _ensure_optional_window("window_days", window_days, minimum=3, maximum=30)
    with _open_warehouse(warehouse_path) as conn:
        result = comparative_signals.hrv_change_around_date(conn, parsed_anchor)
    return _serialize_signal_result(
        "hrv_change_around_date", result, requested_window=window_days
    )


def _run_signal(
    spec_name: str,
    *,
    warehouse_path: Path | None,
    requested_window: int | None = None,
) -> dict[str, Any]:
    """Open the warehouse, run one registered engine signal, serialize the result."""
    with _open_warehouse(warehouse_path) as conn:
        result = engine.compute(spec_name, conn)
    return _serialize_signal_result(spec_name, result, requested_window=requested_window)


def _serialize_signal_result(
    tool_name: str,
    result: object,
    *,
    requested_window: int | None = None,
) -> dict[str, Any]:
    """Turn a Stage 2 result envelope into a plain, tool-friendly MCP payload.

    Every payload carries:

    * ``status`` — one of ``available`` / ``missing_input`` / ``stale_input`` /
      ``insufficient_data``. Non-success reasons stay structurally distinct so a
      caller can branch on them instead of parsing a generic error string.
    * ``message`` — a user-facing sentence (the lead caveat or the missing-input
      message) so the caller always has something to show.
    * ``result`` — the full structured envelope via the engine's ``to_dict()``.

    A requested-but-unhonored window is appended as a transparent caveat.
    """
    payload = result.to_dict()  # type: ignore[attr-defined]
    if requested_window is not None:
        payload["caveats"] = [
            *payload.get("caveats", []),
            _REQUESTED_WINDOW_CAVEAT.format(requested=requested_window),
        ]
    status = _classify_result_status(payload)
    hint = _signal_missing_input_hint(tool_name)
    response: dict[str, Any] = {
        "tool_name": tool_name,
        "status": status,
        "message": _result_message(payload, status, hint),
        "result": payload,
    }
    if status in ("missing_input", "stale_input"):
        report = _build_missing_input_report(tool_name, status, hint, payload)
        response["missing_input"] = report.to_dict()
    return response


def _build_missing_input_report(
    tool_name: str,
    status: str,
    hint: str | None,
    payload: dict[str, Any],
) -> MissingInputReport:
    """Build a structured required/missing/stale-input report from boundary data.

    ``required_inputs`` is the signal's full declared input list (so this stays
    correct if a signal ever declares more than one input). For today's
    single-input signals every declared input maps to ``missing_inputs`` when the
    answer is ``missing_input`` and to ``stale_inputs`` when it is ``stale_input``.
    """
    required_inputs = _signal_required_inputs(tool_name)
    message = hint if hint else _result_message(payload, status, hint)
    if status == "missing_input":
        return MissingInputReport(
            tool_name=tool_name,
            required_inputs=required_inputs,
            message=message,
            missing_inputs=list(required_inputs),
        )
    return MissingInputReport(
        tool_name=tool_name,
        required_inputs=required_inputs,
        message=message,
        stale_inputs=list(required_inputs),
    )


def _signal_spec(tool_name: str) -> object | None:
    """Look up the engine SignalSpec for a tool, ensuring built-ins are loaded.

    The signal-backed tools share their name with the engine spec name. The
    registry is populated lazily, so trigger a load (the hrv tool bypasses
    ``engine.compute``) before reading the spec.
    """
    if tool_name not in engine.REGISTRY:
        # Idempotently load built-in signals via a public engine query.
        engine.list_by_domain("")
    return engine.REGISTRY.get(tool_name)


def _signal_required_inputs(tool_name: str) -> list[str]:
    spec = _signal_spec(tool_name)
    inputs = getattr(spec, "inputs", None)
    return list(inputs) if inputs else []


def _signal_missing_input_hint(tool_name: str) -> str | None:
    spec = _signal_spec(tool_name)
    return getattr(spec, "missing_input_hint", None)


def _classify_result_status(payload: dict[str, Any]) -> str:
    """Map a serialized envelope to a structurally-distinct availability status.

    Each unavailable reason gets its own label rather than collapsing into a
    single error: missing input, stale-but-present input, and insufficient data
    are different facts the caller may want to act on differently.
    """
    family = payload.get("family")
    if family == "missing_input":
        return "missing_input"
    if family == "change":
        return "available" if payload.get("sufficient_data") else "insufficient_data"

    freshness = payload.get("freshness_state") or payload.get("current_freshness_state")
    if freshness == "unavailable":
        # No usable value at all behind a "latest value" answer.
        return "missing_input"

    if family == "trend":
        # A trend describes a window; a stale final point is a caveat, not an
        # unavailable answer. Only genuine sparsity (unknown direction) makes the
        # trend itself unanswerable.
        if payload.get("trend_direction") == "unknown":
            return "insufficient_data"
        return "available"

    # Status / baseline are single "latest value" answers: a present-but-old
    # value is a distinct, weaker state than a fresh one.
    if freshness == "stale":
        return "stale_input"
    if family == "baseline" and payload.get("comparison_state") == "unknown":
        # Present and fresh, but too few prior nights to name a baseline.
        return "insufficient_data"
    return "available"


def _result_message(payload: dict[str, Any], status: str, hint: str | None = None) -> str:
    """Pick a single user-facing sentence to accompany the structured result.

    For an unavailable answer (``missing_input`` / ``stale_input``) prefer the
    signal's actionable ``missing_input_hint`` so the caller sees how to fix the
    gap, falling back to the prior generic message when no hint is authored.
    ``available`` and fresh-but-sparse ``insufficient_data`` messages are
    unchanged.
    """
    if payload.get("family") == "missing_input":
        return str(payload.get("message", ""))
    if status in ("missing_input", "stale_input") and hint:
        return hint
    caveats = payload.get("caveats") or []
    if caveats:
        return str(caveats[0])
    if status == "available":
        return "Answer available."
    return "This answer is not available right now."


def _parse_anchor_date(anchor_date: str) -> date:
    if not isinstance(anchor_date, str) or not anchor_date.strip():
        raise ValueError("anchor_date must be a non-empty ISO-8601 date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(anchor_date.strip())
    except ValueError as exc:
        raise ValueError(
            f"anchor_date must be an ISO-8601 date (YYYY-MM-DD); got {anchor_date!r}"
        ) from exc


def _ensure_optional_window(
    name: str, value: int | None, *, minimum: int, maximum: int
) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


def _ensure_read_only_sql(sql: str) -> None:
    normalized = sql.strip()
    if not normalized:
        raise ValueError("query must not be empty")
    body = normalized[:-1].strip() if normalized.endswith(";") else normalized
    if ";" in body:
        raise ValueError("query_warehouse accepts exactly one read-only statement")
    if not body.lower().startswith(_READ_ONLY_PREFIXES):
        raise ValueError("query_warehouse only allows read-only SQL")


def _ensure_non_negative_int(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0")


def _ensure_bounded_positive_int(name: str, value: int, *, maximum: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    if value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")


def _row_to_dict(columns: list[str], row: Sequence[object]) -> dict[str, Any]:
    return {name: _json_safe(value) for name, value in zip(columns, row, strict=False)}


def _json_safe(value: object) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


__all__ = [
    "hrv_change_around_date",
    "list_metrics",
    "metric_summary",
    "query_warehouse",
    "resting_hr_status",
    "resting_hr_trend",
    "sleep_deep_pct_baseline",
    "steps_trend",
    "weight_trend",
]
