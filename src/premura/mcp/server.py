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

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import engine
from ..config import settings
from ..engine import (
    AnalyticalInputSeries,
    AnalyticalQuestionType,
    AnalyticalResultEnvelope,
    BeforeAfterDirection,
    BeforeAfterPairedRequest,
    EvidenceCandidate,
    ExpectedDirection,
    MissingInputReport,
    PreparedPoint,
    PreRegisteredAssociationHypothesis,
    comparative_signals,
)
from ..engine import _query as engine_query
from ..engine.policies._defaults import builtin_policies
from ..profile_fields import (
    SUPPORTED_PROFILE_FIELDS,
    UnsupportedProfileFieldError,
    get_profile_field,
)
from ..store import duck, profile_intake
from . import pubmed

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


# --------------------------------------------------------------------------- #
# Agent-mediated bounded profile capture (WP03).
#
# These two helpers are the runtime write surface for stable baseline profile
# facts. They are the only profile-capture path the MCP/CLI layers touch, and
# they delegate ALL validation and persistence to the store boundary
# (``premura.store.profile_intake`` + ``premura.profile_fields``). There is no
# generic attribute writer here: the bounded allowlist is enforced once, at the
# store, and every unsupported/derived key (e.g. ``age``) is rejected there.
# --------------------------------------------------------------------------- #

#: Provenance recorded for facts written through this agent-mediated surface.
PROFILE_CAPTURE_SOURCE_KIND = profile_intake.DEFAULT_PROFILE_SOURCE_KIND


@contextmanager
def _open_warehouse_writable(
    warehouse_path: Path | None,
) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the warehouse read-write for profile capture and always close it.

    Profile capture mutates ``hp.profile_context_assertion``, so unlike the
    read-only analytical tools this opens a writable connection. Migrations are
    re-run (idempotent ``CREATE ... IF NOT EXISTS``) so the profile tables exist
    even if this is the first write against a freshly created warehouse.
    """
    conn = duck.connect(warehouse_path or settings.warehouse_path, read_only=False)
    try:
        duck.run_migrations(conn)
        yield conn
    finally:
        conn.close()


def supported_profile_fields() -> dict[str, Any]:
    """Return the bounded baseline-profile allowlist as a self-describing schema.

    This is the discovery half of the capture surface: it tells a caller exactly
    which attribute keys are storable, what value shape each expects, and (for
    enums) the closed set of allowed values — so the caller never has to guess or
    probe with a failing write. It delegates to ``premura.profile_fields`` rather
    than re-listing keys, keeping the allowlist single-sourced.
    """
    fields = [
        {
            "attribute_key": field.attribute_key,
            "value_kind": str(field.value_kind),
            "description": field.description,
            "unit": field.unit,
            "allowed_values": (
                list(field.allowed_values) if field.allowed_values is not None else None
            ),
        }
        for field in SUPPORTED_PROFILE_FIELDS.values()
    ]
    return {
        "fields": fields,
        "supported_keys": [f["attribute_key"] for f in fields],
        "source_kind": PROFILE_CAPTURE_SOURCE_KIND,
    }


def record_profile_context(
    attribute_key: str,
    value: Any,
    *,
    effective_start_utc: str | datetime | None = None,
    source_ref: str | None = None,
    actor_ref: str | None = None,
    notes: str | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Record one bounded baseline profile fact through the agent-mediated path.

    Validation and persistence are delegated to the store boundary
    (:func:`premura.store.profile_intake.record_profile_context`), which enforces
    the bounded allowlist. An unsupported or derived key (e.g. ``age``) is NOT
    silently dropped: it is surfaced as a structured ``rejected`` response with an
    explicit reason, distinct from the ``recorded`` happy path.

    Each call opens a bounded capture session so provenance is attributable, and
    records the new assertion as ``agent_profile_capture``. When the write
    supersedes a prior open assertion for the same attribute, the superseded id is
    surfaced so the caller can see the append/supersede effect rather than a vague
    success.
    """
    try:
        field = get_profile_field(attribute_key)
    except UnsupportedProfileFieldError as exc:
        return {
            "status": "rejected",
            "attribute_key": attribute_key,
            "reason": str(exc),
            "supported_keys": list(SUPPORTED_PROFILE_FIELDS),
        }

    start = _parse_effective_start(effective_start_utc)

    with _open_warehouse_writable(warehouse_path) as conn:
        capture_session_id = profile_intake.start_profile_capture_session(
            conn, actor_kind="agent", actor_ref=actor_ref, notes=notes
        )
        superseded_id = profile_intake.current_assertion_id(conn, attribute_key)
        try:
            assertion_id = profile_intake.record_profile_context(
                conn,
                attribute_key=attribute_key,
                value=value,
                effective_start_utc=start,
                capture_session_id=capture_session_id,
                source_kind=PROFILE_CAPTURE_SOURCE_KIND,
                source_ref=source_ref,
                supersede=True,
            )
        except (UnsupportedProfileFieldError, ValueError) as exc:
            # A value that does not fit the field's typed slot (or a late-detected
            # unsupported key) is a visible rejection, not a silent success.
            return {
                "status": "rejected",
                "attribute_key": attribute_key,
                "reason": str(exc),
                "supported_keys": list(SUPPORTED_PROFILE_FIELDS),
            }
        stored = profile_intake.get_current_profile(conn, attribute_key)

    return {
        "status": "recorded",
        "attribute_key": attribute_key,
        "value_kind": str(field.value_kind),
        "assertion_id": assertion_id,
        "capture_session_id": capture_session_id,
        "source_kind": PROFILE_CAPTURE_SOURCE_KIND,
        "superseded_assertion_id": superseded_id,
        "current": _serialize_assertion(stored),
    }


def _parse_effective_start(value: str | datetime | None) -> datetime:
    """Resolve the assertion's effective-start instant.

    Defaults to "now" (naive UTC, matching the warehouse's timezone-naive
    storage) when the caller does not pin a start, so the common "this is true as
    of now" capture needs no argument.
    """
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("effective_start_utc must be a non-empty ISO-8601 timestamp")
        return datetime.fromisoformat(value.strip())
    raise ValueError("effective_start_utc must be an ISO-8601 string or datetime")


def _serialize_assertion(
    record: profile_intake.ProfileAssertionRecord | None,
) -> dict[str, Any] | None:
    """Serialize a stored profile assertion into a JSON-safe read-back view."""
    if record is None:
        return None
    return {
        "assertion_id": record.assertion_id,
        "attribute_key": record.attribute_key,
        "value_text": record.value_text,
        "value_num": record.value_num,
        "value_date": _json_safe(record.value_date),
        "unit": record.unit,
        "effective_start_utc": _json_safe(record.effective_start_utc),
        "effective_end_utc": _json_safe(record.effective_end_utc),
        "source_kind": record.source_kind,
        "supersedes_assertion_id": record.supersedes_assertion_id,
    }


def list_metrics(
    *,
    metric_ids: list[str] | None = None,
    warehouse_path: Path | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List canonical metrics as validity-gated catalog entries.

    Delegates **entirely** to the Stage 2 engine: metric-id enumeration goes
    through :func:`premura.engine.list_metric_ids` and per-metric freshness
    through :func:`premura.engine.list_metric_catalog`.  This tool issues no raw
    warehouse SQL of its own — the engine owns all ``hp.*`` access.

    When ``metric_ids`` is provided the catalog is built for exactly those IDs
    (``limit`` / ``offset`` are ignored) and an unknown ID yields an explicit
    ``unavailable`` entry rather than being silently dropped (FR-004).  When
    ``metric_ids`` is ``None`` the registered metrics are enumerated and paged.

    Returns explicit ``validity_status`` / ``validity_window`` /
    ``missing_data_policy`` fields per metric so downstream callers can branch
    on availability without parsing prose.  No raw row counts or all-time
    extrema are exposed.
    """
    if metric_ids is None:
        _ensure_non_negative_int("limit", limit)
        _ensure_non_negative_int("offset", offset)
    with _open_warehouse(warehouse_path) as conn:
        ids = (
            engine.list_metric_ids(conn, limit=limit, offset=offset)
            if metric_ids is None
            else metric_ids
        )
        entries = engine.list_metric_catalog(ids, conn)
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
    return _run_signal("steps_trend", warehouse_path=warehouse_path, requested_window=lookback_days)


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
    return _serialize_signal_result("hrv_change_around_date", result, requested_window=window_days)


def _run_signal(
    spec_name: str,
    *,
    warehouse_path: Path | None,
    requested_window: int | None = None,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Open the warehouse, run one registered engine signal, serialize the result.

    ``params`` threads a parameterized signal's caller arguments (an intake
    matcher / quantity key + window) through the WP03-extended ``compute()`` seam
    (T031). When ``params is None`` the zero-arg signals are invoked exactly as
    before; when supplied, the engine forwards them to a signal whose ``fn``
    declared a ``params`` keyword. The wrapper performs NO warehouse reads or
    intake math of its own — the engine owns the resolver, the coverage/direction
    computation, and the freshness/sufficiency verdict.
    """
    with _open_warehouse(warehouse_path) as conn:
        result = engine.compute(spec_name, conn, params=params)
    return _serialize_signal_result(spec_name, result, requested_window=requested_window)


# --------------------------------------------------------------------------- #
# Intake signal-backed Stage 3 tools (WP05)
#
# These two wrappers expose WP04's parameterized intake signals on the default
# MCP surface. They are deliberately THIN: each validates only the caller-facing
# parameter shape, then delegates ENTIRELY to the WP04 signal through the same
# ``_run_signal`` path the zero-arg signals use, passing the caller's matcher /
# quantity-key + window through the WP03-extended ``compute(..., params=...)``
# seam (T031). There is NO raw fact-table SQL, NO re-read of the intake tables,
# and NO re-derivation of coverage/trend semantics here — the engine owns the
# resolver, the math, and the freshness/sufficiency verdict; the wrapper only
# assembles the params dict and serializes the engine envelope. The four
# structurally-distinct states (available / missing_input / stale_input /
# insufficient_data) flow straight through from the engine's own ``status``.
# --------------------------------------------------------------------------- #


def supplement_intake_adherence(
    matcher: str,
    *,
    window_days: int | None = None,
    min_logged_days: int | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Coverage "K of N days" for a caller-declared supplement matcher (delegates to engine).

    The caller declares the supplement ``matcher`` (interpreted by the WP03
    resolver's pinned matcher semantics), an optional bounded ``window_days``, and
    an optional ``min_logged_days`` — the minimum distinct logged days the caller
    needs before a coverage answer is meaningful (default ``1``). All three pass
    straight through to the WP04 ``supplement_intake_adherence`` signal via
    ``compute(..., params=...)``. This wrapper validates only the caller-facing
    parameter shape — it re-reads no intake rows and re-derives no coverage. The
    engine returns one of four structurally-distinct states (``available`` /
    ``missing_input`` / ``stale_input`` / ``insufficient_data``); an empty,
    stale, or too-thin domain comes back as an honest refusal with its own state,
    never substituted from another source and never a diagnosis or recommendation.
    Raising ``min_logged_days`` above ``1`` is how a caller makes the
    ``insufficient_data`` state reachable (a single fresh logged day satisfies the
    default floor and reports ``available``).
    """
    clean_matcher = _require_matcher("matcher", matcher)
    _ensure_optional_window("window_days", window_days, minimum=1, maximum=365)
    _ensure_optional_window("min_logged_days", min_logged_days, minimum=1, maximum=365)
    params: dict[str, Any] = {"matcher": clean_matcher}
    if window_days is not None:
        params["window_days"] = window_days
    if min_logged_days is not None:
        params["min_logged_days"] = min_logged_days
    return _run_signal(
        "supplement_intake_adherence",
        warehouse_path=warehouse_path,
        params=params,
    )


def nutrition_intake_trend(
    quantity_key: str,
    *,
    window_days: int | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Plain up/down/flat direction of a caller-declared nutrient/energy key (delegates to engine).

    The caller declares the nutrition ``quantity_key`` (e.g. ``"energy"`` /
    ``"protein"``, interpreted by the WP03 resolver) and an optional bounded
    ``window_days``; both pass straight through to the WP04
    ``nutrition_intake_trend`` signal via ``compute(..., params=...)``. This
    wrapper validates only the caller-facing parameter shape — it re-reads no
    intake rows and re-derives no direction, and it never imputes a missing day
    (the engine keeps gaps visible). The engine returns one of four
    structurally-distinct states (``available`` / ``missing_input`` /
    ``stale_input`` / ``insufficient_data``); a plain trend direction only, never
    a reference range, significance, or causal claim.
    """
    clean_key = _require_matcher("quantity_key", quantity_key)
    _ensure_optional_window("window_days", window_days, minimum=1, maximum=365)
    params: dict[str, Any] = {"quantity_key": clean_key}
    if window_days is not None:
        params["window_days"] = window_days
    return _run_signal(
        "nutrition_intake_trend",
        warehouse_path=warehouse_path,
        params=params,
    )


def _require_matcher(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


# --------------------------------------------------------------------------- #
# Stage 3 analytical tools (WP06) — change_point and smoothed_average
#
# These two wrappers expose the WP04 proof tools on the default MCP surface.
# They are deliberately THIN: each validates only the caller-facing parameter
# shape, reads warehouse evidence through the SAME engine-owned Stage 2 query
# layer the descriptive signals use (``premura.engine._query`` — the wrapper
# itself issues NO raw fact-table SQL), hands that evidence to the engine's
# public input-preparation + dispatch surface
# (``premura.engine.prepare_input_series`` / ``invoke_analytical_tool``), and
# serializes the returned envelope. There is NO statistical computation and NO
# caveat/estimate invention here — the engine owns all of that.
# --------------------------------------------------------------------------- #

# The window of history the analytical tools read, mirroring the descriptive
# trend span. The engine layer owns admissibility and method bounds; this is
# only how much recent history the warehouse glue offers as candidate evidence.
_ANALYTICAL_WINDOW_SPAN = timedelta(days=90)


def change_point(
    metric_id: str,
    *,
    min_side_observations: int | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Detect a single level shift in one metric's recent series (delegates to engine).

    Validates the caller-facing parameter shape only, then delegates entirely to
    the engine: warehouse evidence is read through the Stage 2 query layer, fed to
    ``prepare_input_series`` (admissibility gate), and dispatched through
    ``invoke_analytical_tool``. The wrapper performs no statistical computation and
    never names a cause; refusals (stale / inadmissible / insufficient /
    out-of-bounds) flow straight through from the engine with a distinct reason and
    no estimate.
    """
    params: dict[str, object] = {}
    if min_side_observations is not None:
        _ensure_positive_int("min_side_observations", min_side_observations)
        params["min_side_observations"] = min_side_observations
    return _run_analytical_tool(
        "change_point",
        metric_id,
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        params=params,
        warehouse_path=warehouse_path,
    )


def smoothed_average(
    metric_id: str,
    *,
    window: int | None = None,
    min_coverage: float | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Return a conservative trailing smoothed pattern for one metric (delegates to engine).

    Validates the caller-facing parameter shape only, then delegates entirely to
    the engine (Stage 2 evidence read → ``prepare_input_series`` →
    ``invoke_analytical_tool``). The wrapper computes nothing and implies no
    prediction or statistical significance; smoothing/window metadata and any
    refusal come from the engine envelope unchanged.
    """
    params: dict[str, object] = {}
    if window is not None:
        _ensure_positive_int("window", window)
        params["window"] = window
    if min_coverage is not None:
        _ensure_unit_fraction("min_coverage", min_coverage)
        params["min_coverage"] = min_coverage
    return _run_analytical_tool(
        "smoothed_average",
        metric_id,
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
        params=params,
        warehouse_path=warehouse_path,
    )


def rolling_mean(
    metric_id: str,
    *,
    window: int | None = None,
    min_coverage: float | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Return a declared moving-window summary for one metric (delegates to engine).

    Validates the caller-facing parameter shape only, then delegates entirely to
    the engine: warehouse evidence is read through the Stage 2 query layer under
    the reviewed ``MOVING_WINDOW_PATTERN`` question type, fed to
    ``prepare_input_series`` (admissibility gate), and dispatched through
    ``invoke_analytical_tool``. The wrapper computes no rolling means, invents no
    caveats, and implies no prediction or significance; under-covered windows,
    coverage/window metadata, and any refusal come from the engine envelope
    unchanged. Stale, inadmissible, insufficient, or out-of-bounds requests return
    a structured refusal with a distinct reason and no estimate.
    """
    params: dict[str, object] = {}
    if window is not None:
        _ensure_positive_int("window", window)
        params["window"] = window
    if min_coverage is not None:
        _ensure_unit_fraction("min_coverage", min_coverage)
        params["min_coverage"] = min_coverage
    return _run_analytical_tool(
        "rolling_mean",
        metric_id,
        question_type=AnalyticalQuestionType.MOVING_WINDOW_PATTERN,
        params=params,
        warehouse_path=warehouse_path,
    )


# --------------------------------------------------------------------------- #
# Stage 3 simple anchor-date before/after paired difference (WP04) — paired_t_test
#
# ``paired_t_test`` is the single-series paired sibling of ``correlate``. It is
# just as THIN: it validates only the caller-facing parameter shape, reads ONE
# admitted series' evidence through the SAME engine-owned Stage 2 query layer the
# single-series tools use (``_prepare_analytical_series`` — no raw fact-table SQL),
# builds the pre-registered before/after request the engine requires, then hands
# the prepared series + request to the engine: ``prepare_before_after_paired_input``
# applies the anchor-date pairing + admissibility, and ``invoke_analytical_tool``
# runs the deterministic paired-difference estimate. The wrapper computes NO
# statistics, does NO pairing, names NO confounds/caveats, and emits NO p-value or
# significance verdict: the returned envelope (available or refusal) is the
# engine's, serialized unchanged.
# --------------------------------------------------------------------------- #


def paired_t_test(
    metric_id: str,
    *,
    anchor_date: str,
    before_days: int,
    after_days: int,
    expected_direction: str,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Report a simple before/after paired difference for one metric (delegates to engine).

    The caller pre-registers the metric, the anchor date, the before/after window
    sizes, and the ``expected_direction`` ("increase"/"decrease") BEFORE seeing the
    result — the anti-p-hacking discipline of FR-005. The anchor only splits the
    before/after windows; it is never shown to be the cause of any change.

    This wrapper validates only the caller-facing parameter shape and assembles the
    declared request. The single series read goes through the engine's Stage 2
    query layer; all pairing, admissibility, computation (mean paired difference and
    its dispersion), confounds, caveats, and refusals belong to the engine. The
    wrapper performs no statistics and emits no p-value or significance verdict; an
    inadmissible / stale / no-valid-pairs / too-few-pairs / constant-difference
    request flows back as a structured refusal with a distinct reason and no
    estimate.
    """
    metric = _require_metric_id("metric_id", metric_id)
    parsed_anchor = _parse_anchor_date(anchor_date)
    _ensure_positive_int("before_days", before_days)
    _ensure_positive_int("after_days", after_days)
    direction = _parse_before_after_direction(expected_direction)

    request = BeforeAfterPairedRequest(
        metric_id=metric,
        anchor_date=parsed_anchor,
        before_days=before_days,
        after_days=after_days,
        expected_direction=direction,
    )

    with _open_warehouse(warehouse_path) as conn:
        series = _prepare_analytical_series(conn, metric, AnalyticalQuestionType.PAIRED_DIFFERENCE)
        paired = engine.prepare_before_after_paired_input(series, request)
        envelope = engine.invoke_analytical_tool("paired_t_test", paired)
    return _serialize_analytical_result(envelope)


def _parse_before_after_direction(value: str) -> BeforeAfterDirection:
    """Map the caller-facing direction string onto the closed engine vocabulary.

    The closed set (``increase`` / ``decrease``) is the engine's; the wrapper does
    not invent a third value, so an agent cannot smuggle a free-form expectation.
    """
    try:
        return BeforeAfterDirection(value)
    except ValueError as exc:
        allowed = ", ".join(d.value for d in BeforeAfterDirection)
        raise ValueError(f"expected_direction must be one of: {allowed}; got {value!r}") from exc


# --------------------------------------------------------------------------- #
# Stage 3 pre-registered lagged association (WP04) — correlate
#
# ``correlate`` is the paired sibling of the single-series analytical tools.
# It is just as THIN: it validates only the caller-facing parameter shape, builds
# the pre-registered hypothesis the engine requires, reads each series' evidence
# through the SAME engine-owned Stage 2 query layer the single-series tools use
# (``_prepare_analytical_series`` — no raw fact-table SQL of its own), then hands
# the two prepared series + hypothesis to the engine: ``prepare_paired_input``
# applies the lag/pairing and admissibility, and ``invoke_analytical_tool`` runs
# the deterministic Spearman + N_eff estimate. The wrapper computes NO statistics,
# does NO pairing, names NO confounds/caveats, and touches NO network/PubMed: the
# returned envelope (available or refusal) is the engine's, serialized unchanged.
# --------------------------------------------------------------------------- #


def correlate(
    left_metric_id: str,
    right_metric_id: str,
    *,
    lag_days: int,
    expected_direction: str,
    lag_justification: str | None = None,
    common_cause_candidates: Sequence[str] | None = None,
    warehouse_path: Path | None = None,
) -> dict[str, Any]:
    """Report a pre-registered lagged association between two metrics (delegates to engine).

    The caller pre-registers the metric pair, integer-day ``lag_days``, and
    ``expected_direction`` ("positive"/"negative") BEFORE seeing the result — the
    anti-p-hacking discipline of ADR-0008. A 4..14 day lag requires
    ``lag_justification``; lags beyond 14 days are refused by the engine. Optional
    ``common_cause_candidates`` (open, caller-supplied — never an enumerated
    catalog) are passed through so the engine can flag the ``common_cause_plausible``
    confound.

    This wrapper validates only the caller-facing parameter shape and assembles the
    hypothesis. Every series read goes through the engine's Stage 2 query layer; all
    pairing, admissibility, computation (Spearman rho, effective sample size,
    association band), confounds, caveats, and refusals belong to the engine. The
    wrapper performs no statistics and never claims significance or causation; an
    inadmissible / no-overlap / weak-support / unsupported-lag request flows back as
    a structured refusal with a distinct reason and no estimate.
    """
    left = _require_metric_id("left_metric_id", left_metric_id)
    right = _require_metric_id("right_metric_id", right_metric_id)
    direction = _parse_expected_direction(expected_direction)
    if isinstance(lag_days, bool) or not isinstance(lag_days, int):
        raise ValueError("lag_days must be a whole-day integer")
    candidates = tuple(common_cause_candidates) if common_cause_candidates else ()

    hypothesis = PreRegisteredAssociationHypothesis(
        left_metric_id=left,
        right_metric_id=right,
        lag_days=lag_days,
        expected_direction=direction,
        lag_justification=lag_justification,
        common_cause_candidates=candidates,
    )

    with _open_warehouse(warehouse_path) as conn:
        left_series = _prepare_analytical_series(
            conn, left, AnalyticalQuestionType.LAGGED_ASSOCIATION
        )
        right_series = _prepare_analytical_series(
            conn, right, AnalyticalQuestionType.LAGGED_ASSOCIATION
        )
        paired = engine.prepare_paired_input(left_series, right_series, hypothesis)
        envelope = engine.invoke_analytical_tool("correlate", paired, hypothesis)
    return _serialize_analytical_result(envelope)


def _require_metric_id(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def _parse_expected_direction(value: str) -> ExpectedDirection:
    """Map the caller-facing direction string onto the closed engine vocabulary.

    The closed set (``positive`` / ``negative``) is the engine's; the wrapper does
    not invent a third value, so an agent cannot smuggle a free-form expectation.
    """
    try:
        return ExpectedDirection(value)
    except ValueError as exc:
        allowed = ", ".join(d.value for d in ExpectedDirection)
        raise ValueError(f"expected_direction must be one of: {allowed}; got {value!r}") from exc


def _run_analytical_tool(
    tool_name: str,
    metric_id: str,
    *,
    question_type: AnalyticalQuestionType,
    params: dict[str, object],
    warehouse_path: Path | None,
) -> dict[str, Any]:
    """Read evidence, prepare the input series, dispatch the tool, serialize.

    All warehouse access is through the engine's Stage 2 query layer; all
    admissibility, computation, and refusal logic is the engine's. The wrapper
    only assembles the prepared-input call and serializes the engine's envelope.
    """
    if not metric_id or not metric_id.strip():
        raise ValueError("metric_id must not be empty")
    metric_id = metric_id.strip()
    with _open_warehouse(warehouse_path) as conn:
        series = _prepare_analytical_series(conn, metric_id, question_type)
        envelope = engine.invoke_analytical_tool(tool_name, series, **params)
    return _serialize_analytical_result(envelope)


def _prepare_analytical_series(
    conn: duckdb.DuckDBPyConnection,
    metric_id: str,
    question_type: AnalyticalQuestionType,
) -> AnalyticalInputSeries:
    """Turn engine-read warehouse evidence into a prepared analytical input series.

    Evidence is read through the engine's Stage 2 query helpers
    (:func:`premura.engine._query.load_metric_policy` /
    :func:`~premura.engine._query.ordered_window`) — the same layer the
    descriptive signals use — so this wrapper never issues raw fact-table SQL of
    its own. The admissibility gate, refusal construction, and all downstream
    computation belong to :func:`premura.engine.prepare_input_series` and the
    invoked tool; this function only assembles the candidate and points.
    """
    reference_time = engine_query._naive_utc_now()
    policy = engine_query.load_metric_policy(conn, metric_id)
    if policy is None:
        # Unknown metric: hand the engine an empty-evidence call so it produces a
        # first-class refusal (no points -> evidence_missing) rather than the
        # wrapper inventing a reason of its own.
        return engine.prepare_input_series(
            metric_id,
            question_type,
            candidate=EvidenceCandidate(
                metric_id=metric_id,
                metric_family=metric_id,
                value_kind="unknown",
                observed_at=None,
                point_count=0,
            ),
            policies=builtin_policies(),
            points=[],
            reference_time=reference_time,
        )

    window = engine_query.ordered_window(
        conn, policy, span=_ANALYTICAL_WINDOW_SPAN, now=reference_time
    )
    points = [
        PreparedPoint(ts=p.ts, value=p.value, is_imputed=p.is_imputed, local_tz=p.local_tz)
        for p in window.points
    ]
    observed_at = points[-1].ts if points else None
    candidate = EvidenceCandidate(
        metric_id=metric_id,
        metric_family=_metric_family_for(metric_id),
        value_kind="interval" if policy.is_interval else "aggregate",
        observed_at=observed_at,
        point_count=len(points),
    )
    return engine.prepare_input_series(
        metric_id,
        question_type,
        candidate=candidate,
        policies=builtin_policies(),
        points=points,
        reference_time=reference_time,
        window_start=window.window_start,
        window_end=window.window_end,
        freshness_status=window.latest_freshness.value,
    )


def _metric_family_for(metric_id: str) -> str:
    """Resolve the admissibility family that owns ``metric_id``.

    The built-in family policies declare which metrics they cover via
    ``applies_to_metrics``; this looks the metric up there rather than hard-coding
    a per-metric family. An unmapped metric falls back to its own id, which the
    evaluator will treat as having no covering policy and refuse accordingly.
    """
    for policy in builtin_policies():
        if metric_id in policy.applies_to_metrics:
            return policy.metric_family
    return metric_id


def _serialize_analytical_result(envelope: AnalyticalResultEnvelope) -> dict[str, Any]:
    """Serialize one engine analytical envelope into the MCP tool payload.

    The payload always carries ``tool_name``, ``status``, ``message``, and
    ``result`` (the full engine envelope via ``to_dict()``). The status is the
    engine's own ``available`` / ``refused`` verdict; the message is the engine's
    refusal message for a refusal, or the engine's lead caveat for a non-refusal —
    the wrapper authors no new prose, estimate, or caveat.
    """
    payload = envelope.to_dict()
    refusal = payload.get("refusal")
    if refusal is not None:
        message = str(refusal.get("message", ""))
    else:
        caveats = payload.get("caveats") or []
        message = str(caveats[0]) if caveats else "Analytical result available."
    return {
        "tool_name": payload["tool_name"],
        "status": payload["status"],
        "message": message,
        "result": payload,
    }


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

    Parameterized intake signals (WP04/WP05) already compute their own
    structurally-distinct ``status`` on the engine side (available / missing_input
    / stale_input / insufficient_data). When the envelope carries that field we
    trust it verbatim rather than re-deriving the verdict in the wrapper — the
    classification stays single-sourced in the engine. The zero-arg Stage 2
    signals do not set a top-level ``status``, so they fall through to the
    family/freshness-based derivation below unchanged.
    """
    declared_status = payload.get("status")
    if isinstance(declared_status, str) and declared_status:
        return declared_status

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


# --------------------------------------------------------------------------- #
# PubMed grounding wrappers (WP03)
#
# These two wrappers expose WP02's Premura-owned PubMed provider
# (``premura.mcp.pubmed``) on the Stage 3 server helper surface. They are
# deliberately THIN: each validates only the trivial caller-facing input shape
# (mirroring the other server helpers) and delegates entirely to the provider's
# public surface. There is NO health-warehouse access, NO analytical
# computation, NO diagnosis/causal language, and NO raw SQL here — this module's
# PubMed path reads no ``hp.*`` rows. Ordinary no-results / invalid / unavailable
# / provider-error outcomes flow straight back as the provider's structured,
# JSON-safe dictionaries; only an empty query / empty PMID is a caller error.
# --------------------------------------------------------------------------- #


def pubmed_search(
    query: str,
    *,
    limit: int = pubmed.DEFAULT_SEARCH_LIMIT,
    sort: str | None = None,
) -> dict[str, Any]:
    """Search PubMed for candidate records (delegates to the WP02 provider).

    Candidates are discovery hints only and are never citeable; the returned
    payload carries the provider's ``citation_rule`` and each candidate's
    ``citation_status = candidate_only``. This wrapper computes nothing and reads
    no warehouse data — it forwards to :func:`premura.mcp.pubmed.pubmed_search`
    and returns its JSON-safe outcome dict (``available`` / ``no_results`` /
    ``provider_error``) unchanged.
    """
    return pubmed.pubmed_search(query, limit=limit, sort=sort)


def pubmed_fetch(pmid: str) -> dict[str, Any]:
    """Fetch one PubMed record by exact PMID (delegates to the WP02 provider).

    Only a fetched record is citeable (``citation_status =
    citeable_fetched_record``) and carries the ``pubmed_url`` provenance an honest
    citation needs. This wrapper computes nothing and reads no warehouse data — it
    forwards to :func:`premura.mcp.pubmed.pubmed_fetch` and returns its JSON-safe
    outcome dict (``available`` / ``invalid_pmid`` / ``unavailable`` /
    ``provider_error``) unchanged.
    """
    return pubmed.pubmed_fetch(pmid)


def _parse_anchor_date(anchor_date: str) -> date:
    if not isinstance(anchor_date, str) or not anchor_date.strip():
        raise ValueError("anchor_date must be a non-empty ISO-8601 date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(anchor_date.strip())
    except ValueError as exc:
        raise ValueError(
            f"anchor_date must be an ISO-8601 date (YYYY-MM-DD); got {anchor_date!r}"
        ) from exc


def _ensure_optional_window(name: str, value: int | None, *, minimum: int, maximum: int) -> None:
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


def _ensure_positive_int(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")


def _ensure_unit_fraction(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not (0.0 < value <= 1.0):
        raise ValueError(f"{name} must be in the interval (0.0, 1.0]")


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
    "PROFILE_CAPTURE_SOURCE_KIND",
    "change_point",
    "correlate",
    "hrv_change_around_date",
    "list_metrics",
    "metric_summary",
    "nutrition_intake_trend",
    "paired_t_test",
    "pubmed_fetch",
    "pubmed_search",
    "query_warehouse",
    "record_profile_context",
    "resting_hr_status",
    "resting_hr_trend",
    "rolling_mean",
    "sleep_deep_pct_baseline",
    "smoothed_average",
    "steps_trend",
    "supplement_intake_adherence",
    "supported_profile_fields",
    "weight_trend",
]
