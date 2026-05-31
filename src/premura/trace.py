"""The pure-Python session research trace service (``premura.trace``).

This module is the **stateful counterpart** that ADR-0009 pushed out of the
stateless analytical engine. It records every analytical tool call an agent
dispatches during a research session, derives a *measured* multiplicity
disclosure ("K user-facing findings among N unique hypotheses examined"), and
lets the agent mark which results it actually surfaced in a user-facing answer.

Design boundaries (ADR-0009, the mission spec, and the audit-consumer contract):

* **MCP-agnostic.** This module imports nothing from the MCP layer. It exposes a
  narrow, boring set of functions an MCP wrapper (WP03) calls; the service is
  fully testable on its own DuckDB connection without an MCP server.
* **Engine-agnostic and engine-pure.** Recording happens *around* dispatch and
  never reads ``hp.*`` health facts or computes a statistic. The analytical
  engine stays stateless/deterministic; its output is byte-identical whether or
  not a trace session is active.
* **Append-only.** Sessions, calls, results, and marks are inserted and never
  updated/deleted in normal operation. A call row is written before dispatch and
  *finalized* (its terminal status filled in) after — that finalize is the only
  in-place write, and it only fills the nullable terminal columns the WP01
  migration left open. Results and marks are separate immutable rows.
* **Measured, not self-reported.** N (unique hypotheses) and the raw call count
  are derived by a single bounded query over the recorded rows. A false count an
  agent passes in cannot change them, because the agent never reports a count.
* **Disclosure of search effort, never a corrected statistic.** No p-value, no
  "significant" label, no multiplicity correction. "Surfaced" (K) is an explicit
  agent presentation mark, never inferred from effect size or status. When a
  session has calls but no marks, K is reported *unavailable* with an explicit
  message rather than guessed.

The per-tool **normalized hypothesis identity** is a registry, not a switch
(ADR-0009 "guide, don't enumerate"): adding a future analytical tool means
declaring its identity normalizer in :data:`_IDENTITY_REGISTRY`, not editing the
counting/disclosure code. The denominator ``N`` is
``COUNT(DISTINCT hypothesis_identity)`` per session; exact retries collapse
because they normalize to the same canonical-JSON identity.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb

# The trace schema version this service writes/reads. Bump when the trace
# storage shape or the disclosure contract changes in a way a consumer must see.
TRACE_SCHEMA_VERSION = "1"

# The audit-consumer contract object version (see
# ``contracts/audit-consumer-contract.md``). Stable for downstream readers.
DISCLOSURE_CONTRACT_VERSION = "1"

# Default cap on the number of call records a disclosure inlines. A large
# session stays a single bounded query, never an unbounded row dump (NFR-005).
DEFAULT_CALL_LIMIT = 1000

# Terminal statuses a recorded call may finish in.
STATUS_AVAILABLE = "available"
STATUS_REFUSED = "refused"
STATUS_ERROR = "error"

# Closed-ish vocabulary of surfaced-mark roles (data-model). The service
# validates non-empty; the exact label set stays the agent's to extend, so this
# is documentation of the expected shapes, not an enforced enum.
KNOWN_MARK_ROLES = ("claim", "summary", "recommendation", "next_step", "caveat")


# ===========================================================================
# Public result shapes (T006)
#
# Every public function returns one of these frozen dataclasses. They carry a
# ``status`` string so an MCP wrapper can branch on a machine-readable outcome
# without exceptions, and a ``to_dict()`` that serializes to JSON-safe
# primitives for the MCP envelope / the audit-consumer contract.
# ===========================================================================


@dataclass(frozen=True)
class TraceError:
    """A non-success outcome from a trace operation.

    ``status`` is one of ``not_found``, ``invalid_reference``, or
    ``validation_error``. ``message`` is a human/agent-readable explanation;
    ``field`` names the offending input where applicable.
    """

    status: str
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status, "message": self.message}
        if self.field is not None:
            out["field"] = self.field
        return out


@dataclass(frozen=True)
class TraceSession:
    """Result of opening a research session (status ``opened``)."""

    session_id: str
    started_at_utc: str
    warehouse_fingerprint: str
    schema_version: str
    client_label: str | None = None
    status: str = "opened"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "session_id": self.session_id,
            "started_at_utc": self.started_at_utc,
            "warehouse_fingerprint": self.warehouse_fingerprint,
            "schema_version": self.schema_version,
            "client_label": self.client_label,
        }


@dataclass(frozen=True)
class ResultRef:
    """A stable reference to a recorded analytical result (audit contract)."""

    result_id: str
    result_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {"result_id": self.result_id, "result_hash": self.result_hash}


@dataclass(frozen=True)
class RecordedCall:
    """Result of recording (start + finish) one analytical call.

    Mirrors the audit-consumer "Call Record" object so a wrapper can return it
    directly. ``result_ref`` is present only for an ``available`` call.
    """

    call_id: str
    session_id: str
    tool_name: str
    hypothesis_identity: str
    request_hash: str
    terminal_status: str
    started_at_utc: str
    finished_at_utc: str | None = None
    refusal_reason: str | None = None
    error_kind: str | None = None
    result_ref: ResultRef | None = None
    status: str = "recorded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "call_id": self.call_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "hypothesis_identity": self.hypothesis_identity,
            "request_hash": self.request_hash,
            "terminal_status": self.terminal_status,
            "refusal_reason": self.refusal_reason,
            "error_kind": self.error_kind,
            "result_ref": self.result_ref.to_dict() if self.result_ref else None,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
        }


@dataclass(frozen=True)
class PendingCall:
    """Handle returned by :func:`start_recorded_call`, passed to
    :func:`finish_recorded_call`. Carries the minted ids/identity so the finalize
    write needs no second normalization pass."""

    call_id: str
    session_id: str
    tool_name: str
    hypothesis_identity: str
    request_hash: str
    started_at_utc: str
    status: str = "started"


@dataclass(frozen=True)
class SurfacedMark:
    """Result of marking a recorded call as surfaced (status ``marked``)."""

    mark_id: str
    session_id: str
    call_id: str
    role: str
    rationale: str
    marked_at_utc: str
    status: str = "marked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mark_id": self.mark_id,
            "call_id": self.call_id,
            "role": self.role,
            "rationale": self.rationale,
            "marked_at_utc": self.marked_at_utc,
        }


@dataclass(frozen=True)
class SurfacedSummary:
    """The surfaced (K) section of a disclosure (audit "Surfaced Summary").

    ``status`` is ``available`` (``count``/``marks`` populated) or
    ``unavailable`` (``count`` is ``None`` and ``message`` explains the absence).
    """

    status: str
    count: int | None
    message: str | None
    marks: tuple[SurfacedMark, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "count": self.count,
            "message": self.message,
            "marks": [m.to_dict() for m in self.marks],
        }


@dataclass(frozen=True)
class TraceDisclosure:
    """The derived multiplicity disclosure over one research session (T011).

    This is the audit-consumer "Session Disclosure" object. The counts are
    derived from recorded rows, never self-reported. ``status`` is ``available``
    for a real (possibly empty-but-valid) session.
    """

    session_id: str
    started_at_utc: str | None
    warehouse_fingerprint: str | None
    raw_analytical_call_count: int
    unique_hypothesis_count: int
    surfaced: SurfacedSummary
    refusal_breakdown: dict[str, int]
    calls: tuple[RecordedCall, ...]
    disclosure_text: str
    calls_truncated: bool = False
    schema_version: str = DISCLOSURE_CONTRACT_VERSION
    status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "started_at_utc": self.started_at_utc,
            "warehouse_fingerprint": self.warehouse_fingerprint,
            "raw_analytical_call_count": self.raw_analytical_call_count,
            "unique_hypothesis_count": self.unique_hypothesis_count,
            "surfaced": self.surfaced.to_dict(),
            "refusal_breakdown": dict(self.refusal_breakdown),
            "calls": [c.to_dict() for c in self.calls],
            "calls_truncated": self.calls_truncated,
            "disclosure_text": self.disclosure_text,
        }


# ===========================================================================
# Deterministic hashing + normalized hypothesis identity (T008)
# ===========================================================================


def canonical_json(obj: Any) -> str:
    """Serialize ``obj`` to canonical JSON text.

    Keys are sorted and separators are tight so two dicts that differ only by
    key order or whitespace produce byte-identical text — the property the
    request hash and the hypothesis identity both rely on for determinism.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_text(text: str) -> str:
    """Stable hex digest of ``text`` (sha256). Used for request/result hashes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_hash(tool_name: str, request: Mapping[str, Any]) -> str:
    """Deterministic hash of a normalized analytical request.

    Reordered request fields hash identically because the request is serialized
    through :func:`canonical_json`. The tool name is folded in so two different
    tools with coincidentally identical kwargs never collide.
    """
    payload = {"tool": tool_name, "request": _json_safe(request)}
    return _hash_text(canonical_json(payload))


def result_hash(result: Any) -> str:
    """Deterministic hash of a serialized result envelope.

    The result is normalized through :func:`canonical_json` so a reordered
    envelope hashes the same. No raw health rows are required here — the caller
    passes the engine's JSON-safe envelope, not the underlying series.
    """
    return _hash_text(canonical_json(_json_safe(result)))


def _json_safe(value: Any) -> Any:
    """Coerce a value into JSON-canonicalizable primitives.

    Tuples become lists; mappings are recursed (so nested order does not matter);
    anything already JSON-safe passes through. We do not attempt to serialize
    exotic objects — callers pass plain request kwargs / engine envelopes.
    """
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


# --- Per-tool hypothesis identity declarations (the registry, not a switch) ---
#
# Each declaration takes the *request kwargs as the MCP wrapper passes them*
# (the parameter names verified against ``src/premura/mcp/entrypoint.py`` and
# the engine defaults in ``premura.engine.analytical_tools``) and returns the
# canonical dict of fields that make two calls the "same" examined hypothesis.
# Defaults are applied here so an omitted parameter and its explicit default
# share an identity. Adding a future tool (e.g. ``paired_t_test``) is a new
# entry here — never a branch in the disclosure/counting code (ADR-0009).

# Engine defaults, duplicated as literals so this module stays engine-import-free
# (it must not pull engine code into the MCP-agnostic trace surface). They are
# pinned by tests so drift from the engine constants is caught.
_DEFAULT_MIN_SIDE_OBSERVATIONS = 2
_DEFAULT_SMOOTHING_WINDOW = 7
_DEFAULT_MIN_COVERAGE = 0.5


def _identity_change_point(req: Mapping[str, Any]) -> dict[str, Any]:
    """``change_point``: metric id + ``min_side_observations`` (post-default)."""
    mso = req.get("min_side_observations")
    if mso is None:
        mso = _DEFAULT_MIN_SIDE_OBSERVATIONS
    return {
        "metric_id": req.get("metric_id"),
        "min_side_observations": int(mso),
    }


def _identity_smoothed_average(req: Mapping[str, Any]) -> dict[str, Any]:
    """``smoothed_average``: metric id, window, min_coverage (post-default)."""
    window = req.get("window")
    if window is None:
        window = _DEFAULT_SMOOTHING_WINDOW
    min_coverage = req.get("min_coverage")
    if min_coverage is None:
        min_coverage = _DEFAULT_MIN_COVERAGE
    return {
        "metric_id": req.get("metric_id"),
        "window": int(window),
        "min_coverage": float(min_coverage),
    }


def _identity_correlate(req: Mapping[str, Any]) -> dict[str, Any]:
    """``correlate``: a pre-registered lagged association between two metrics.

    Identity fields (ADR-0008/0009 + the MCP request shape): left metric, right
    metric, integer lag, expected direction, the *presence/shape* of the lag
    justification, and the *shape* of the common-cause declaration. The free
    text of the justification and the specific candidate list are deliberately
    reduced to a shape (justification present? candidate set) so two pre-registrations
    of the same directional pair/lag with differently-worded prose are the same
    examined hypothesis, while a different lag/direction/pair is distinct.

    The pair is NOT reordered: ``correlate(a, b, lag)`` declares a directional
    lagged hypothesis (right responds to left), so ``(a, b)`` and ``(b, a)`` are
    distinct hypotheses (ADR-0008). The order-sensitivity rule is settled here.
    """
    candidates = req.get("common_cause_candidates")
    if candidates:
        # Order-insensitive, de-duplicated shape of the declared candidates: the
        # *set* of declared common causes is what bears on the hypothesis, not
        # the order they were listed in.
        candidate_shape: Any = sorted({str(c) for c in candidates})
    else:
        candidate_shape = []
    return {
        "left_metric_id": req.get("left_metric_id"),
        "right_metric_id": req.get("right_metric_id"),
        "lag_days": int(req["lag_days"]) if req.get("lag_days") is not None else None,
        "expected_direction": req.get("expected_direction"),
        "lag_justification_present": bool(req.get("lag_justification")),
        "common_cause_candidates": candidate_shape,
    }


# The declaration registry. Keyed by tool name; each value normalizes a request
# to its identity dict. This is the single seam a future analytical tool plugs
# into — disclosure/counting code never names a specific tool.
_IDENTITY_REGISTRY: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "change_point": _identity_change_point,
    "smoothed_average": _identity_smoothed_average,
    "correlate": _identity_correlate,
}


def register_hypothesis_identity(
    tool_name: str,
    normalizer: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> None:
    """Declare the normalized hypothesis identity for a new analytical tool.

    This is how a future tool (``paired_t_test``, ``rolling_mean``) joins the
    trace's N-counting without anyone editing the disclosure switch: it declares
    its identity once. ``normalizer`` maps the tool's request kwargs to the
    canonical dict of identity-bearing fields.
    """
    _IDENTITY_REGISTRY[tool_name] = normalizer


def hypothesis_identity(tool_name: str, request: Mapping[str, Any]) -> str:
    """Canonical-JSON normalized hypothesis identity for ``(tool, request)``.

    Falls back to a tool-tagged canonical dump of the whole request for a tool
    with no declared identity, so an unregistered tool still dedups exact
    retries deterministically (and is visibly its own hypothesis) rather than
    silently sharing identity with another tool.
    """
    normalizer = _IDENTITY_REGISTRY.get(tool_name)
    if normalizer is None:
        identity_obj: dict[str, Any] = {
            "tool": tool_name,
            "request": _json_safe(request),
        }
    else:
        identity_obj = {"tool": tool_name, "identity": normalizer(request)}
    return canonical_json(identity_obj)


# ===========================================================================
# Internal helpers
# ===========================================================================


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (boundary-owned clock)."""
    return datetime.now(UTC).isoformat()


def _mint_id(prefix: str) -> str:
    """Mint a stable, unique VARCHAR id at the Python boundary (not a DB sequence).

    A call can be addressed before insert and across processes, matching the
    WP01 schema's VARCHAR primary keys.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


def _ts_to_iso(value: Any) -> str | None:
    """Render a DuckDB timestamp cell as an ISO string (or ``None``)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _session_exists(conn: duckdb.DuckDBPyConnection, session_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM trace.research_session WHERE session_id = ? LIMIT 1",
        [session_id],
    ).fetchone()
    return row is not None


# ===========================================================================
# Session opening (T007)
# ===========================================================================


def open_research_session(
    conn: duckdb.DuckDBPyConnection,
    *,
    client_label: str | None = None,
    created_by: str | None = None,
) -> TraceSession:
    """Open an explicit research session and persist it (FR-001).

    Captures a pragmatic-but-stable warehouse fingerprint and the trace schema
    version so a disclosure can carry the context it was computed against. The
    fingerprint reuses DuckDB's own state rather than building a cryptographic
    inventory of the warehouse — pragmatic per the WP scope.

    Returns a :class:`TraceSession` with ``status="opened"``.
    """
    session_id = _mint_id("sess")
    started_at = _now_iso()
    fingerprint = _warehouse_fingerprint(conn)
    conn.execute(
        """
        INSERT INTO trace.research_session
            (session_id, started_at_utc, client_label, warehouse_fingerprint,
             schema_version, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            started_at,
            client_label,
            fingerprint,
            TRACE_SCHEMA_VERSION,
            created_by,
        ],
    )
    return TraceSession(
        session_id=session_id,
        started_at_utc=started_at,
        warehouse_fingerprint=fingerprint,
        schema_version=TRACE_SCHEMA_VERSION,
        client_label=client_label,
    )


def _warehouse_fingerprint(conn: duckdb.DuckDBPyConnection) -> str:
    """A stable, pragmatic fingerprint of the warehouse for reproduction context.

    Combines DuckDB's library version with a digest of the live schema/table
    inventory (catalog/schema/table names). This is stable across reads of the
    same warehouse shape and changes when the schema changes, which is the
    reproduction signal a disclosure needs — without reading any ``hp.*`` health
    rows (NFR-002 / provenance boundary). If the catalog query is unavailable for
    any reason, fall back to the library version alone rather than failing the
    session open.
    """
    try:
        version_row = conn.execute("PRAGMA version").fetchone()
        lib_version = str(version_row[0]) if version_row else "unknown"
    except Exception:  # pragma: no cover - defensive, version pragma is stable
        lib_version = "unknown"
    try:
        rows = conn.execute(
            """
            SELECT table_catalog, table_schema, table_name
            FROM information_schema.tables
            ORDER BY table_catalog, table_schema, table_name
            """
        ).fetchall()
        inventory = canonical_json([list(map(str, r)) for r in rows])
        digest = _hash_text(inventory)[:16]
    except Exception:  # pragma: no cover - defensive
        digest = "noinv"
    return f"duckdb-{lib_version}-schema-{digest}"


# ===========================================================================
# Call/result recording (T009)
# ===========================================================================


def start_recorded_call(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    tool_name: str,
    request: Mapping[str, Any],
) -> PendingCall | TraceError:
    """Record an analytical call *before* dispatch (FR-002, FR-003).

    Mints a stable ``call_id``, computes the deterministic request hash and the
    normalized hypothesis identity, and inserts a call row with no terminal
    status yet. Returns a :class:`PendingCall` to hand to
    :func:`finish_recorded_call`, or a :class:`TraceError` (``not_found``) for an
    unknown session.

    This does not read ``hp.*`` and computes no statistic — it only records the
    request shape the boundary observed.
    """
    if not _session_exists(conn, session_id):
        return TraceError(
            status="not_found",
            message=f"No such research session: {session_id!r}.",
            field="session_id",
        )
    call_id = _mint_id("call")
    started_at = _now_iso()
    rhash = request_hash(tool_name, request)
    identity = hypothesis_identity(tool_name, request)
    conn.execute(
        """
        INSERT INTO trace.tool_call
            (call_id, session_id, tool_name, request_hash, hypothesis_identity,
             started_at_utc)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [call_id, session_id, tool_name, rhash, identity, started_at],
    )
    return PendingCall(
        call_id=call_id,
        session_id=session_id,
        tool_name=tool_name,
        hypothesis_identity=identity,
        request_hash=rhash,
        started_at_utc=started_at,
    )


def finish_recorded_call(
    conn: duckdb.DuckDBPyConnection,
    pending: PendingCall,
    *,
    terminal_status: str,
    result: Any | None = None,
    refusal_reason: str | None = None,
    error_kind: str | None = None,
) -> RecordedCall | TraceError:
    """Finalize a recorded call *after* dispatch (FR-002, FR-004).

    ``terminal_status`` must be ``available``, ``refused``, or ``error``:

    * ``available`` — attaches a stable result reference (``result_hash`` plus an
      optional compact ``result_summary``); pass the engine's JSON-safe envelope
      as ``result``. No raw health rows are stored.
    * ``refused`` — records the machine-readable ``refusal_reason`` on the call.
    * ``error`` — records ``error_kind`` for a dispatch failure, keeping the
      disclosure internally consistent (the attempt is still one recorded call).

    Returns a :class:`RecordedCall`, or a :class:`TraceError` for an invalid
    terminal status / a missing reason on a refusal.
    """
    if terminal_status not in (STATUS_AVAILABLE, STATUS_REFUSED, STATUS_ERROR):
        return TraceError(
            status="validation_error",
            message=(
                "terminal_status must be one of "
                f"{STATUS_AVAILABLE!r}, {STATUS_REFUSED!r}, {STATUS_ERROR!r}."
            ),
            field="terminal_status",
        )
    if terminal_status == STATUS_REFUSED and not (refusal_reason and refusal_reason.strip()):
        return TraceError(
            status="validation_error",
            message="A refused call requires a machine-readable refusal_reason.",
            field="refusal_reason",
        )
    finished_at = _now_iso()
    conn.execute(
        """
        UPDATE trace.tool_call
        SET finished_at_utc = ?, terminal_status = ?, refusal_reason = ?, error_kind = ?
        WHERE call_id = ?
        """,
        [
            finished_at,
            terminal_status,
            refusal_reason if terminal_status == STATUS_REFUSED else None,
            error_kind if terminal_status == STATUS_ERROR else None,
            pending.call_id,
        ],
    )
    result_ref: ResultRef | None = None
    if terminal_status == STATUS_AVAILABLE and result is not None:
        result_ref = _record_result(conn, pending.call_id, result)
    return RecordedCall(
        call_id=pending.call_id,
        session_id=pending.session_id,
        tool_name=pending.tool_name,
        hypothesis_identity=pending.hypothesis_identity,
        request_hash=pending.request_hash,
        terminal_status=terminal_status,
        started_at_utc=pending.started_at_utc,
        finished_at_utc=finished_at,
        refusal_reason=refusal_reason if terminal_status == STATUS_REFUSED else None,
        error_kind=error_kind if terminal_status == STATUS_ERROR else None,
        result_ref=result_ref,
    )


# Keys safe to keep in a compact result summary envelope. These are method /
# validity metadata from the analytical result envelope — never the raw series,
# paired observations, or any ``hp.*`` health row. Anything outside this set is
# dropped so a result summary can never become a raw health-fact dump.
_SAFE_SUMMARY_KEYS = frozenset(
    {
        "tool_name",
        "status",
        "result_kind",
        "confound_keys",
        "refusal",
        "inputs",
        "effective_window",
        "usable_count",
        "coverage",
        "raw_paired_sample_size",
        "effective_sample_size",
        "lag_days",
        "expected_direction",
    }
)


def _compact_summary(result: Any) -> str | None:
    """Extract a safe, compact JSON-text envelope subset from a result.

    Only whitelisted method/validity keys survive; raw series and health rows are
    excluded by construction (the data-model "must avoid storing raw health fact
    dumps" rule). Returns ``None`` when the result is not a mapping.
    """
    if not isinstance(result, Mapping):
        return None
    subset = {k: _json_safe(v) for k, v in result.items() if k in _SAFE_SUMMARY_KEYS}
    if not subset:
        return None
    return canonical_json(subset)


def _record_result(
    conn: duckdb.DuckDBPyConnection,
    call_id: str,
    result: Any,
) -> ResultRef:
    """Append an immutable result reference row for an available call."""
    result_id = _mint_id("res")
    rhash = result_hash(result)
    summary = _compact_summary(result)
    conn.execute(
        """
        INSERT INTO trace.tool_result
            (result_id, call_id, result_hash, result_summary, created_at_utc)
        VALUES (?, ?, ?, ?, ?)
        """,
        [result_id, call_id, rhash, summary, _now_iso()],
    )
    return ResultRef(result_id=result_id, result_hash=rhash)


# ===========================================================================
# Surfaced marks (T010)
# ===========================================================================


def mark_surfaced(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    call_id: str,
    role: str,
    rationale: str,
) -> SurfacedMark | TraceError:
    """Mark a recorded call as surfaced in the user-facing answer (FR-009).

    "Surfaced" = selected for presentation (a claim/summary/recommendation/
    next-step/caveat in the answer). It is *never* a statistical-significance
    judgment, and the service never infers a mark from effect size or status —
    the agent declares it explicitly.

    Validation:

    * unknown session -> ``not_found``
    * unknown call -> ``not_found``
    * call belongs to a different session -> ``invalid_reference``
    * empty role / rationale -> ``validation_error``
    """
    if not role or not role.strip():
        return TraceError(
            status="validation_error",
            message="A surfaced mark requires a non-empty role.",
            field="role",
        )
    if not rationale or not rationale.strip():
        return TraceError(
            status="validation_error",
            message="A surfaced mark requires a non-empty rationale.",
            field="rationale",
        )
    if not _session_exists(conn, session_id):
        return TraceError(
            status="not_found",
            message=f"No such research session: {session_id!r}.",
            field="session_id",
        )
    row = conn.execute(
        "SELECT session_id FROM trace.tool_call WHERE call_id = ? LIMIT 1",
        [call_id],
    ).fetchone()
    if row is None:
        return TraceError(
            status="not_found",
            message=f"No such recorded call: {call_id!r}.",
            field="call_id",
        )
    if row[0] != session_id:
        return TraceError(
            status="invalid_reference",
            message=(f"Call {call_id!r} belongs to session {row[0]!r}, not {session_id!r}."),
            field="call_id",
        )
    mark_id = _mint_id("mark")
    marked_at = _now_iso()
    conn.execute(
        """
        INSERT INTO trace.surfaced_mark
            (mark_id, session_id, call_id, role, rationale, marked_at_utc)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [mark_id, session_id, call_id, role.strip(), rationale.strip(), marked_at],
    )
    return SurfacedMark(
        mark_id=mark_id,
        session_id=session_id,
        call_id=call_id,
        role=role.strip(),
        rationale=rationale.strip(),
        marked_at_utc=marked_at,
    )


# ===========================================================================
# Disclosure computation + exports (T011)
# ===========================================================================

# The exact framing required by FR-010 / the data-model: search effort, never
# "significant results"/"tests".
_SURFACED_UNAVAILABLE_MESSAGE = (
    "Surfaced count unavailable: the agent did not mark any included results for this session."
)


def get_research_disclosure(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    *,
    include_calls: bool = True,
    call_limit: int = DEFAULT_CALL_LIMIT,
) -> TraceDisclosure | TraceError:
    """Derive the measured multiplicity disclosure for a session (FR-006..FR-012).

    Returns a :class:`TraceDisclosure` whose counts are computed by bounded
    queries over the recorded rows — never self-reported. For an unknown /
    never-opened session returns a :class:`TraceError` (``not_found``, FR-015),
    which is distinct from a valid-but-empty session (raw=N=0, surfaced
    unavailable).

    * **raw_analytical_call_count** — every recorded call in the session.
    * **unique_hypothesis_count (N)** — ``COUNT(DISTINCT hypothesis_identity)``,
      so exact retries collapse but refusals still count.
    * **surfaced (K)** — count of surfaced marks; reported *unavailable* with an
      explicit message when calls exist but no marks do (FR-011), never guessed.
    * **refusal_breakdown** — counts by ``refusal_reason``.
    * **calls** — bounded list of stable call/result references for audit
      consumers (omitted when ``include_calls`` is false; truncated at
      ``call_limit`` with ``calls_truncated`` set).
    """
    session_row = conn.execute(
        """
        SELECT started_at_utc, warehouse_fingerprint
        FROM trace.research_session WHERE session_id = ? LIMIT 1
        """,
        [session_id],
    ).fetchone()
    if session_row is None:
        return TraceError(
            status="not_found",
            message=f"No such research session: {session_id!r}.",
            field="session_id",
        )
    started_at = _ts_to_iso(session_row[0])
    fingerprint = session_row[1]

    # Aggregate counts in one bounded query (raw + N). Bounded by definition: one
    # grouped scan over this session's calls, never a per-row Python loop.
    agg = conn.execute(
        """
        SELECT
            COUNT(*) AS raw_calls,
            COUNT(DISTINCT hypothesis_identity) AS n_unique
        FROM trace.tool_call
        WHERE session_id = ?
        """,
        [session_id],
    ).fetchone()
    raw_calls = int(agg[0]) if agg else 0
    n_unique = int(agg[1]) if agg else 0

    # Refusal breakdown by reason — a second bounded grouped scan.
    refusal_rows = conn.execute(
        """
        SELECT refusal_reason, COUNT(*)
        FROM trace.tool_call
        WHERE session_id = ? AND terminal_status = ? AND refusal_reason IS NOT NULL
        GROUP BY refusal_reason
        ORDER BY refusal_reason
        """,
        [session_id, STATUS_REFUSED],
    ).fetchall()
    refusal_breakdown = {str(r[0]): int(r[1]) for r in refusal_rows}

    surfaced = _surfaced_summary(conn, session_id, raw_calls)

    calls: tuple[RecordedCall, ...] = ()
    truncated = False
    if include_calls:
        calls, truncated = _call_records(conn, session_id, call_limit)

    text = _disclosure_text(raw_calls, n_unique, surfaced, refusal_breakdown)

    return TraceDisclosure(
        session_id=session_id,
        started_at_utc=started_at,
        warehouse_fingerprint=fingerprint,
        raw_analytical_call_count=raw_calls,
        unique_hypothesis_count=n_unique,
        surfaced=surfaced,
        refusal_breakdown=refusal_breakdown,
        calls=calls,
        calls_truncated=truncated,
        disclosure_text=text,
    )


def _surfaced_summary(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    raw_calls: int,
) -> SurfacedSummary:
    """Compute the surfaced (K) section with the conservative fallback (FR-011)."""
    mark_rows = conn.execute(
        """
        SELECT mark_id, session_id, call_id, role, rationale, marked_at_utc
        FROM trace.surfaced_mark
        WHERE session_id = ?
        ORDER BY marked_at_utc, mark_id
        """,
        [session_id],
    ).fetchall()
    if not mark_rows:
        # No marks at all. If there were analytical calls, K is *unavailable*
        # with an explicit message (never a guessed 0/inferred number). For a
        # genuinely empty session this is the same honest "no marks" state.
        return SurfacedSummary(
            status="unavailable",
            count=None,
            message=_SURFACED_UNAVAILABLE_MESSAGE,
            marks=(),
        )
    marks = tuple(
        SurfacedMark(
            mark_id=str(r[0]),
            session_id=str(r[1]),
            call_id=str(r[2]),
            role=str(r[3]),
            rationale=str(r[4]),
            marked_at_utc=_ts_to_iso(r[5]) or "",
        )
        for r in mark_rows
    )
    return SurfacedSummary(
        status="available",
        count=len(marks),
        message=None,
        marks=marks,
    )


def _call_records(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    call_limit: int,
) -> tuple[tuple[RecordedCall, ...], bool]:
    """Bounded list of stable call/result references for audit consumers.

    A single LEFT JOIN scan capped at ``call_limit + 1`` so a large session never
    returns an unbounded dump; the extra row (if present) only flips the
    ``truncated`` flag.
    """
    limit = max(0, call_limit)
    rows = conn.execute(
        """
        SELECT
            c.call_id, c.session_id, c.tool_name, c.hypothesis_identity,
            c.request_hash, c.terminal_status, c.started_at_utc, c.finished_at_utc,
            c.refusal_reason, c.error_kind, r.result_id, r.result_hash
        FROM trace.tool_call c
        LEFT JOIN trace.tool_result r ON r.call_id = c.call_id
        WHERE c.session_id = ?
        ORDER BY c.started_at_utc, c.call_id
        LIMIT ?
        """,
        [session_id, limit + 1],
    ).fetchall()
    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]
    records = tuple(
        RecordedCall(
            call_id=str(row[0]),
            session_id=str(row[1]),
            tool_name=str(row[2]),
            hypothesis_identity=str(row[3]) if row[3] is not None else "",
            request_hash=str(row[4]) if row[4] is not None else "",
            terminal_status=str(row[5]) if row[5] is not None else "",
            started_at_utc=_ts_to_iso(row[6]) or "",
            finished_at_utc=_ts_to_iso(row[7]),
            refusal_reason=row[8],
            error_kind=row[9],
            result_ref=(
                ResultRef(result_id=str(row[10]), result_hash=str(row[11]))
                if row[10] is not None
                else None
            ),
        )
        for row in rows
    )
    return records, truncated


def _disclosure_text(
    raw_calls: int,
    n_unique: int,
    surfaced: SurfacedSummary,
    refusal_breakdown: dict[str, int],
) -> str:
    """Render the honest disclosure sentence (FR-010).

    Uses the required framing "user-facing findings among unique hypotheses
    examined" and shows the raw call count separately. It never says
    "significant results" or "tests".
    """
    if surfaced.status == "available":
        k = surfaced.count
        head = f"{k} user-facing findings among {n_unique} unique hypotheses examined"
    else:
        head = (
            f"Surfaced findings unavailable among {n_unique} unique hypotheses "
            "examined (the agent did not mark any included results)"
        )
    parts = [head, f"raw analytical calls: {raw_calls}"]
    if refusal_breakdown:
        total_refused = sum(refusal_breakdown.values())
        by_reason = ", ".join(
            f"{reason}: {count}" for reason, count in sorted(refusal_breakdown.items())
        )
        parts.append(f"refusals: {total_refused} ({by_reason})")
    return "; ".join(parts) + "."


# ===========================================================================
# Human-readable exports (T011, FR-014) — generated from the structured trace,
# never the canonical record.
# ===========================================================================


def disclosure_to_json(disclosure: TraceDisclosure) -> str:
    """Serialize a disclosure to JSON text (an on-demand export, not canonical)."""
    return json.dumps(disclosure.to_dict(), indent=2, ensure_ascii=False)


def disclosure_to_markdown(disclosure: TraceDisclosure) -> str:
    """Render a disclosure as Markdown (an on-demand export, not canonical).

    Generated from the structured disclosure so it can never drift from the
    canonical counts. Mirrors the audit-consumer fields in a human-readable
    shape without becoming a source of truth (FR-014).
    """
    d = disclosure
    lines: list[str] = []
    lines.append(f"# Research disclosure — session `{d.session_id}`")
    lines.append("")
    lines.append(d.disclosure_text)
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Raw analytical calls: {d.raw_analytical_call_count}")
    lines.append(f"- Unique hypotheses examined (N): {d.unique_hypothesis_count}")
    if d.surfaced.status == "available":
        lines.append(f"- User-facing findings surfaced (K): {d.surfaced.count}")
    else:
        lines.append(f"- User-facing findings surfaced (K): unavailable — {d.surfaced.message}")
    lines.append("")
    if d.refusal_breakdown:
        lines.append("## Refusals by reason")
        lines.append("")
        for reason, count in sorted(d.refusal_breakdown.items()):
            lines.append(f"- {reason}: {count}")
        lines.append("")
    if d.surfaced.status == "available" and d.surfaced.marks:
        lines.append("## Surfaced marks")
        lines.append("")
        for m in d.surfaced.marks:
            lines.append(f"- `{m.call_id}` [{m.role}]: {m.rationale}")
        lines.append("")
    if d.calls:
        lines.append("## Recorded calls")
        lines.append("")
        for c in d.calls:
            ref = c.result_ref.result_hash[:12] if c.result_ref else "—"
            lines.append(
                f"- `{c.call_id}` {c.tool_name} → {c.terminal_status}"
                + (f" ({c.refusal_reason})" if c.refusal_reason else "")
                + f" [result: {ref}]"
            )
        if d.calls_truncated:
            lines.append("- … (call list truncated)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
