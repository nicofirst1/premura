"""The session log's own file + its **sole** writer surface.

This module is the substrate the rest of the session-log mission stands on. It
records what an *operating* agent did during a run — the session, the step tree
(turn -> model/tool call), and the Premura-internal facts of each ingest — into
the session log's **own** local DuckDB file, so the deterministic grader can
later recompute a verdict from the log alone (FR-080).

Design boundaries (data-model.md, ``contracts/session-log-writer.md``, ADR 0011,
spec C-001/C-002):

* **Its own file, its own schema bootstrap.** This module owns ``connect()`` for
  the log file and applies its **own** :data:`schema.sql` via :func:`init_schema`
  (idempotent ``CREATE IF NOT EXISTS``). It does **not** route through
  ``premura.store.duck.run_migrations`` and does **not** fold into the warehouse
  ``hp.*`` / research-trace ``trace.*`` tables (FR-070 / C-001). Keeping it a
  separate file is what removes the single-file write contention; the harness is
  the sole writer (FR-021 / NFR-008) and the subprocess runner never opens it.
* **Connection-agnostic writers.** Like ``premura.trace``, every writer function
  takes an already-open ``duckdb.DuckDBPyConnection`` and never opens/closes it.
  The caller (the harness) owns the single writable connection.
* **Boundary input validation.** ``result_status``, ``run_kind``, and ``kind``
  are validated against fixed vocabularies at this seam (FR-003 / FR-032);
  arbitrary strings raise :class:`ValueError` rather than being silently stored.
* **Two-origin provenance, claims preserved.** :func:`record_ingest_provenance`
  persists loader-MEASURED ints as authoritative columns and the parser's
  DECLARED claims (unmapped / skipped) as JSON, clearly distinguished, alongside
  the separately-captured declared/emitted metric sets — claims are persisted for
  the grader to reconcile, never discarded (FR-010..FR-013).
* **Grader-only ``contract_pass``.** :func:`record_ingest_provenance` persists
  ``contract_pass`` exactly as the caller (the grader) supplies it. This WP has
  no other source for it — it is the grader's recomputed runtime-subset result,
  never a parser/runner self-report (FR-061 / FR-065).

No code path in this module syncs or exports the file (NFR-004); summaries are
PHI-safe envelopes supplied by the caller.
"""

from __future__ import annotations

import importlib.resources as resources
import json
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Protocol

import duckdb
from ulid import ULID

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

# The package this module lives in, used to load the bundled schema.sql.
_PACKAGE = "premura.session_log"
_SCHEMA_FILE = "schema.sql"

# ---------------------------------------------------------------------------
# Fixed vocabularies (validated at this boundary seam).
# ---------------------------------------------------------------------------

# FR-003 — the fixed step-result vocabulary. Pinned here; arbitrary strings are
# rejected so a result_status can never be a silently-accepted free string.
RESULT_STATUSES: frozenset[str] = frozenset(
    {"available", "missing", "stale", "insufficient", "refused", "error"}
)

# FR-032 — the fixed run kinds.
RUN_KINDS: frozenset[str] = frozenset({"repeatable_check", "live_trial"})

# data-model — the fixed step kinds (OTel GenAI tree shape, by hand).
STEP_KINDS: frozenset[str] = frozenset({"agent_turn", "model_call", "tool_call"})

# FR-1 — the fixed conversation-turn roles, mirroring the chat-API role standard.
# Validated at this boundary seam (same style as RESULT_STATUSES): an out-of-
# vocabulary role raises ValueError rather than being silently stored. The rule
# for extending it is the same as the other vocabularies — add the value here and
# extend the vocab test, in this module only; do not enumerate per-tier roles.
TURN_ROLES: frozenset[str] = frozenset({"system", "user", "assistant", "tool"})

# judge-ai m3 FR-1 — the two closed judgment vocabularies, validated at this
# boundary seam (same style as the vocabularies above). They are DESCRIPTIVE only:
# no numeric scores and no pass/fail language confusable with the mechanical
# grader verdict (NFR-6). The rule for extending either is the existing one — add
# the value here and extend the vocab test, in this module only.
#
# JUDGMENT_STATUSES is the honesty axis: a judgment attempt is always recorded,
# and ``unparseable`` / ``model_unavailable`` say so plainly rather than being
# dropped or faked.
JUDGMENT_STATUSES: frozenset[str] = frozenset({"complete", "unparseable", "model_unavailable"})

# CRITERION_BANDS is the assessment axis: every criterion's band AND the optional
# overall band are validated against this set. The criterion IDS themselves are
# rubric-owned data (FR-3) and are deliberately NOT enumerated here — code
# validates bands and records whatever criterion ids the rubric defined.
CRITERION_BANDS: frozenset[str] = frozenset({"strong", "adequate", "weak", "not_applicable"})

# improvement-hook m4 FR-1 — the closed improvement-proposal lifecycle vocabulary,
# validated at this boundary seam (same style as the vocabularies above). The
# improvement hook only ever writes ``open``; ``dismissed`` / ``addressed`` exist
# now so a later lifecycle mission can transition a proposal with NO schema
# migration. The rule for extending it is the existing one — add the value here
# and extend the vocab test, in this module only. The proposal *area* ids are
# playbook-owned data (FR-3) and are deliberately NOT enumerated here, exactly as
# the criterion ids are rubric-owned: code validates the closed status vocabulary
# and records whatever area the playbook defined.
PROPOSAL_STATUSES: frozenset[str] = frozenset({"open", "dismissed", "addressed"})


class LoadStatsLike(Protocol):
    """The three loader-MEASURED ints :func:`record_ingest_provenance` reads.

    Structural so a real ``LoadStats`` (from the warehouse loader) or any object
    exposing these attributes satisfies it without this module importing the
    loader. These three are the authoritative, loader-measured facts.
    """

    rows_inserted: int
    rows_skipped_dup: int
    rows_skipped_priority: int


class SelfReconciliationLike(Protocol):
    """Structured self-reconciliation telemetry for one live-trial attempt."""

    @property
    def passed(self) -> bool: ...

    @property
    def source_columns(self) -> object: ...

    @property
    def accounted(self) -> object: ...

    @property
    def unaccounted(self) -> object: ...


# ---------------------------------------------------------------------------
# Connection + schema bootstrap (this WP owns the log file).
# ---------------------------------------------------------------------------


def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the session-log file, creating its parent dir if missing.

    Mirrors ``premura.store.duck.connect`` (same idiom), but opens the session
    log's **own** file — never the warehouse. The caller is responsible for
    calling :func:`init_schema` once after creation. The harness opens exactly
    **one** writable connection per run and is the sole writer (FR-021); the
    subprocess runner never opens this file, and DuckDB's file lock rejects any
    *other* process that tries to open it read-write while the harness holds it.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply the session log's own ``schema.sql`` (idempotent).

    Reads the bundled DDL via :mod:`importlib.resources` and executes it. Every
    statement is ``CREATE ... IF NOT EXISTS`` so re-running on an already-
    initialized connection is a no-op. This is the session-log package's **own**
    bootstrap — not the warehouse migration runner (FR-070 / C-001).
    """
    schema_sql = resources.files(_PACKAGE).joinpath(_SCHEMA_FILE).read_text(encoding="utf-8")
    conn.execute(schema_sql)


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------


def _mint_id() -> str:
    """Mint a stable VARCHAR id at the Python boundary (python-ulid, as elsewhere)."""
    return str(ULID())


# ---------------------------------------------------------------------------
# Writer functions (the recording API the harness — the sole writer — calls).
# ---------------------------------------------------------------------------


def open_session(
    conn: duckdb.DuckDBPyConnection,
    *,
    operator_model: str,
    driver_model: str,
    premura_version: str,
    isolation_tag: str,
    run_kind: str,
) -> str:
    """Insert one ``log_session`` row and return its ``session_id`` (FR-031/FR-032).

    Captures the run identity a maintainer/grader needs to situate the run:
    ``operator_model`` / ``driver_model`` (sentinels for the fake scripted agent /
    operator in a repeatable check), ``premura_version``, ``isolation_tag``, and
    ``run_kind``. ``run_kind`` is validated against :data:`RUN_KINDS`; an
    out-of-vocabulary value raises :class:`ValueError`. ``started_at`` is a
    wall-clock ``now()`` (nondeterministic, not consumed by the grader).
    """
    if run_kind not in RUN_KINDS:
        raise ValueError(f"run_kind must be one of {sorted(RUN_KINDS)!r}, got {run_kind!r}.")
    session_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_session
            (session_id, started_at, finished_at, operator_model, driver_model,
             premura_version, isolation_tag, run_kind)
        VALUES (?, now(), NULL, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            operator_model,
            driver_model,
            premura_version,
            isolation_tag,
            run_kind,
        ],
    )
    return session_id


def record_step(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_id: str,
    parent_step_id: str | None,
    kind: str,
    name: str | None,
    tool_name: str | None,
    request_summary: str | None,
    request_hash: str | None,
    result_status: str,
    result_summary: str | None,
    result_hash: str | None,
) -> str:
    """Insert one ``log_step`` row and return its ``step_id``.

    A step is a node in the turn -> call tree: pass ``parent_step_id=None`` for a
    root (e.g. an ``agent_turn``) and the parent's id for a child (e.g. a
    ``tool_call`` whose ``tool_name='ingest_run'`` is the verdict-bearing step).
    ``kind`` is validated against :data:`STEP_KINDS` and ``result_status`` against
    the fixed :data:`RESULT_STATUSES` vocabulary (FR-003); an out-of-vocabulary
    value raises :class:`ValueError` rather than being silently stored.
    Summaries must be PHI-safe envelopes supplied by the caller.
    """
    if kind not in STEP_KINDS:
        raise ValueError(f"kind must be one of {sorted(STEP_KINDS)!r}, got {kind!r}.")
    if result_status not in RESULT_STATUSES:
        raise ValueError(
            f"result_status must be one of {sorted(RESULT_STATUSES)!r}, got {result_status!r}."
        )
    step_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_step
            (step_id, session_id, parent_step_id, kind, name, tool_name,
             request_summary, request_hash, result_status, result_summary,
             result_hash, started_at, finished_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now(), now())
        """,
        [
            step_id,
            session_id,
            parent_step_id,
            kind,
            name,
            tool_name,
            request_summary,
            request_hash,
            result_status,
            result_summary,
            result_hash,
        ],
    )
    return step_id


def record_ingest_provenance(
    conn: duckdb.DuckDBPyConnection,
    *,
    step_id: str,
    batch_id: str,
    parser_kind: str,
    load_stats: LoadStatsLike,
    declared_metrics: Sequence[str],
    emitted_metric_ids: Sequence[str],
    unmapped_metrics: Sequence[str],
    skipped_rows: Sequence[dict],
    contract_pass: bool,
) -> None:
    """Insert one ``log_ingest_provenance`` row for an ``ingest_run`` step.

    Persists the MIXED source-of-truth with the split kept intact:

    * **loader-measured (authoritative)** — ``rows_inserted`` /
      ``rows_skipped_dup`` / ``rows_skipped_priority`` from ``load_stats`` are
      stored as integer columns.
    * **captured sets** — ``declared_metrics`` and ``emitted_metric_ids`` are
      stored as SEPARATE JSON columns so the grader can recompute
      "declared == emitted".
    * **parser claims (NOT authoritative)** — ``unmapped_metrics`` and
      ``skipped_rows`` are persisted as JSON precisely so they survive for the
      grader to reconcile; they are the parser's claim, never discarded.

    ``contract_pass`` is the **grader's** recomputed runtime-subset result,
    supplied by the caller and persisted verbatim. This WP has **no other source**
    for it — it is never a parser/runner self-report (FR-061 / FR-065).
    """
    conn.execute(
        """
        INSERT INTO log_ingest_provenance
            (step_id, batch_id, parser_kind, rows_inserted, rows_skipped_dup,
             rows_skipped_priority, declared_metrics_json, emitted_metric_ids_json,
             unmapped_metrics_json, skipped_rows_json, contract_pass)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            step_id,
            batch_id,
            parser_kind,
            int(load_stats.rows_inserted),
            int(load_stats.rows_skipped_dup),
            int(load_stats.rows_skipped_priority),
            json.dumps(list(declared_metrics)),
            json.dumps(list(emitted_metric_ids)),
            json.dumps(list(unmapped_metrics)),
            json.dumps(list(skipped_rows)),
            bool(contract_pass),
        ],
    )


def _json_ready_sequence(value: object) -> list[object]:
    """Normalize list/tuple/set/frozenset payloads to a JSON-serializable list."""
    if isinstance(value, (list, tuple)):
        seq = list(value)
    elif isinstance(value, (set, frozenset)):
        seq = sorted(value)
    else:
        seq = [value]

    normalized: list[object] = []
    for item in seq:
        if is_dataclass(item) and not isinstance(item, type):
            normalized.append(asdict(item))
        else:
            normalized.append(item)
    return normalized


def record_live_trial_attempt(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_id: str,
    attempt_index: int,
    self_reconciliation: SelfReconciliationLike,
    parser_error: str | None,
) -> str:
    """Insert one durable cheap-model attempt telemetry row (FR-008)."""
    attempt_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_live_trial_attempt
            (attempt_id, session_id, attempt_index, self_reconciliation_passed,
             source_columns_json, accounted_json, unaccounted_json, parser_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            attempt_id,
            session_id,
            int(attempt_index),
            bool(self_reconciliation.passed),
            json.dumps(_json_ready_sequence(self_reconciliation.source_columns)),
            json.dumps(_json_ready_sequence(self_reconciliation.accounted)),
            json.dumps(_json_ready_sequence(self_reconciliation.unaccounted)),
            parser_error,
        ],
    )
    return attempt_id


def record_turn(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_id: str,
    step_id: str | None,
    turn_index: int,
    role: str,
    content: str,
    tool_name: str | None = None,
    model: str | None = None,
    token_count: int | None = None,
) -> str:
    """Insert one ``log_turn`` row and return its ``turn_id`` (FR-1).

    Records a single conversation turn of a live-trial run's transcript. ``role``
    is validated against the fixed :data:`TURN_ROLES` vocabulary at this boundary
    (same style as ``result_status``); an out-of-vocabulary value raises
    :class:`ValueError` rather than being silently stored. ``turn_index`` is the
    0-based position within the session's transcript and ``(session_id,
    turn_index)`` is unique — re-using a slot for a session is rejected by the DB
    constraint. ``step_id`` is nullable and, when set, links the turn to the
    ``log_step`` node it occurred under (typically the run's root ``agent_turn``).
    ``content`` carries the full turn content (PHI-bearing, local-only per NFR-002 /
    ADR 0011); ``tool_name`` / ``model`` / ``token_count`` are optional per-turn
    telemetry. The harness is the sole writer (FR-021 / NFR-1).
    """
    if role not in TURN_ROLES:
        raise ValueError(f"role must be one of {sorted(TURN_ROLES)!r}, got {role!r}.")
    turn_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_turn
            (turn_id, session_id, step_id, turn_index, role, content,
             tool_name, model, token_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            turn_id,
            session_id,
            step_id,
            int(turn_index),
            role,
            content,
            tool_name,
            model,
            None if token_count is None else int(token_count),
        ],
    )
    return turn_id


def record_judgment(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_id: str,
    judge_model: str,
    rubric_version: str,
    status: str,
    criteria: dict[str, dict[str, object]],
    overall_band: str | None = None,
    rationale: str | None = None,
    raw_output: str | None = None,
    ungrounded_rejections: int = 0,
) -> str:
    """Insert one ``log_judgment`` row and return its ``judgment_id`` (FR-1).

    Records exactly one AI-judge verdict over a recorded session. ``status`` is
    validated against :data:`JUDGMENT_STATUSES` and every band — each criterion's
    ``band`` and the optional ``overall_band`` — against :data:`CRITERION_BANDS`,
    at this boundary (same style as ``result_status`` / ``role``); an
    out-of-vocabulary value raises :class:`ValueError` rather than being silently
    stored. The criterion *ids* are NOT enumerated here — they belong to the
    rubric (FR-3); ``criteria`` is stored verbatim as a JSON object mapping
    criterion id -> ``{band, rationale, evidence_quote}``.

    The judge can never alter ``contract_pass``, the scoreboard, or the trial
    verdict: this writes a separate, additive ``log_judgment`` row only. A
    judgment attempt is always recorded honestly — on ``unparseable`` /
    ``model_unavailable`` the caller passes an empty ``criteria`` and
    ``overall_band=None`` while ``raw_output`` preserves what the model actually
    said (if anything). The harness is the sole writer (FR-021 / NFR-1).

    ``ungrounded_rejections`` (issue #52) counts how many attempts this judge
    invocation rejected because a criterion's ``evidence_quote`` was not a
    verbatim substring of the dossier text shown to the judge - the judge's own
    confabulation rate, made a standing, queryable number rather than a one-off
    audit observation.

    The bands are DESCRIPTIVE only (NFR-6): no numeric scores, no language
    confusable with the mechanical grader verdict.
    """
    if status not in JUDGMENT_STATUSES:
        raise ValueError(f"status must be one of {sorted(JUDGMENT_STATUSES)!r}, got {status!r}.")
    for criterion_id, entry in criteria.items():
        band = entry.get("band")
        if band not in CRITERION_BANDS:
            raise ValueError(
                f"criterion {criterion_id!r} band must be one of "
                f"{sorted(CRITERION_BANDS)!r}, got {band!r}."
            )
    if overall_band is not None and overall_band not in CRITERION_BANDS:
        raise ValueError(
            f"overall_band must be one of {sorted(CRITERION_BANDS)!r} or None, "
            f"got {overall_band!r}."
        )
    judgment_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_judgment
            (judgment_id, session_id, judged_at, judge_model, rubric_version,
             status, criteria_json, overall_band, rationale, raw_output,
             ungrounded_rejections)
        VALUES (?, ?, now(), ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            judgment_id,
            session_id,
            judge_model,
            rubric_version,
            status,
            json.dumps(criteria),
            overall_band,
            rationale,
            raw_output,
            int(ungrounded_rejections),
        ],
    )
    return judgment_id


def _require_non_empty(value: str, *, field: str) -> str:
    """Reject a blank/whitespace-only field at the store seam (FR-1)."""
    if not value or not value.strip():
        raise ValueError(f"{field} must be a non-empty string, got {value!r}.")
    return value


def record_improvement(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_id: str,
    judgment_id: str,
    criterion_id: str | None,
    area: str,
    summary: str,
    evidence: str,
    playbook_version: str,
    status: str,
) -> str:
    """Insert one ``log_improvement`` row and return its ``improvement_id`` (FR-1).

    Records exactly one durable improvement PROPOSAL the improvement hook derived
    from a judgment. ``status`` is validated against :data:`PROPOSAL_STATUSES` and
    ``summary`` / ``evidence`` / ``area`` must be non-empty, at this boundary (same
    style as ``result_status`` / ``role`` / judgment ``status``); an out-of-
    vocabulary or blank value raises :class:`ValueError` rather than being silently
    stored. The referenced ``session_id`` and ``judgment_id`` must already exist —
    a dangling reference is rejected here (and also by the table's FKs) so a
    proposal can never point at a session or judgment the log does not carry.

    ``criterion_id`` is NULLABLE and opaque (rubric-owned data, never enumerated in
    code): NULL for a judgment-level proposal, the rubric criterion id otherwise.
    ``area`` is a playbook-owned id — code never hardcodes area semantics; it
    records whatever area the playbook mapped the evidence to. This mission only
    ever writes ``"open"``; the other statuses exist so a later lifecycle mission
    needs no schema migration. The harness is the sole writer (FR-021 / NFR-1).
    """
    if status not in PROPOSAL_STATUSES:
        raise ValueError(f"status must be one of {sorted(PROPOSAL_STATUSES)!r}, got {status!r}.")
    _require_non_empty(area, field="area")
    _require_non_empty(summary, field="summary")
    _require_non_empty(evidence, field="evidence")

    session_row = conn.execute(
        "SELECT 1 FROM log_session WHERE session_id = ?", [session_id]
    ).fetchone()
    if session_row is None:
        raise ValueError(f"no session {session_id!r} in this session log")
    judgment_row = conn.execute(
        "SELECT 1 FROM log_judgment WHERE judgment_id = ?", [judgment_id]
    ).fetchone()
    if judgment_row is None:
        raise ValueError(f"no judgment {judgment_id!r} in this session log")

    improvement_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_improvement
            (improvement_id, session_id, judgment_id, created_at, criterion_id,
             area, summary, evidence, playbook_version, status)
        VALUES (?, ?, ?, now(), ?, ?, ?, ?, ?, ?)
        """,
        [
            improvement_id,
            session_id,
            judgment_id,
            criterion_id,
            area,
            summary,
            evidence,
            playbook_version,
            status,
        ],
    )
    return improvement_id


def finish_session(conn: duckdb.DuckDBPyConnection, *, session_id: str) -> None:
    """Set ``finished_at`` on a session at teardown (wall-clock ``now()``).

    The only in-place write in this module: it fills the nullable ``finished_at``
    the open left open. Timestamps are not consumed by the grader.
    """
    conn.execute(
        "UPDATE log_session SET finished_at = now() WHERE session_id = ?",
        [session_id],
    )


# ---------------------------------------------------------------------------
# Runtime orchestrator records (OPERATING_ROLES.md slice 1).
#
# The handoff trace and the answer-audit verdicts are the two deterministic
# pieces of the hybrid orchestrator (decision note 0013). They live HERE — the
# session log's own file — and never in the warehouse research trace, so
# research multiplicity counts stay uncontaminated by orchestrator events.
# Rows are append-only; a revised draft is a new hash, never an edit.
# ---------------------------------------------------------------------------

HANDOFF_STATUSES: frozenset[str] = frozenset({"dispatched", "returned", "refused", "failed"})


def record_handoff(
    conn: duckdb.DuckDBPyConnection,
    *,
    runtime_session_id: str,
    from_id: str,
    to_id: str,
    task_summary: str,
    status: str,
    inputs_ref: str | None = None,
    outputs_ref: str | None = None,
    surface_touched: str | None = None,
    reason: str | None = None,
) -> str:
    """Insert one ``log_handoff`` row and return its ``handoff_id``.

    ``task_summary`` and the ``*_ref`` fields are compact PHI-safe references —
    never raw health data. ``status`` is validated against
    :data:`HANDOFF_STATUSES`; an out-of-vocabulary value raises ``ValueError``.
    """
    _require_non_empty(runtime_session_id, field="runtime_session_id")
    _require_non_empty(from_id, field="from_id")
    _require_non_empty(to_id, field="to_id")
    _require_non_empty(task_summary, field="task_summary")
    if status not in HANDOFF_STATUSES:
        raise ValueError(f"status must be one of {sorted(HANDOFF_STATUSES)!r}, got {status!r}.")
    handoff_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_handoff
            (handoff_id, runtime_session_id, from_id, to_id, task_summary,
             inputs_ref, outputs_ref, surface_touched, status, reason, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
        """,
        [
            handoff_id,
            runtime_session_id,
            from_id,
            to_id,
            task_summary,
            inputs_ref,
            outputs_ref,
            surface_touched,
            status,
            reason,
        ],
    )
    return handoff_id


def list_handoffs(
    conn: duckdb.DuckDBPyConnection,
    *,
    runtime_session_id: str,
) -> list[dict[str, object]]:
    """Return one runtime session's handoffs in recording order (JSON-safe)."""
    rows = conn.execute(
        """
        SELECT handoff_id, runtime_session_id, from_id, to_id, task_summary,
               inputs_ref, outputs_ref, surface_touched, status, reason,
               CAST(recorded_at AS VARCHAR)
        FROM log_handoff WHERE runtime_session_id = ?
        ORDER BY recorded_at ASC, handoff_id ASC
        """,
        [runtime_session_id],
    ).fetchall()
    cols = [
        "handoff_id",
        "runtime_session_id",
        "from_id",
        "to_id",
        "task_summary",
        "inputs_ref",
        "outputs_ref",
        "surface_touched",
        "status",
        "reason",
        "recorded_at",
    ]
    return [dict(zip(cols, row, strict=True)) for row in rows]


def record_answer_audit(
    conn: duckdb.DuckDBPyConnection,
    *,
    draft_sha256: str,
    passed: bool,
    trace_verified: bool,
    runtime_session_id: str | None = None,
    disclosure: str | None = None,
    refusal_count: int | None = None,
    failures: list[str] | None = None,
) -> str:
    """Insert one ``log_answer_audit`` verdict row and return its ``audit_id``."""
    _require_non_empty(draft_sha256, field="draft_sha256")
    audit_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_answer_audit
            (audit_id, runtime_session_id, draft_sha256, passed, trace_verified,
             disclosure, refusal_count, failures, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
        """,
        [
            audit_id,
            runtime_session_id,
            draft_sha256,
            passed,
            trace_verified,
            disclosure,
            refusal_count,
            json.dumps(failures) if failures is not None else None,
        ],
    )
    return audit_id


def latest_answer_audit(
    conn: duckdb.DuckDBPyConnection,
    *,
    draft_sha256: str,
) -> dict[str, object] | None:
    """Return the newest verdict for a draft hash, or None (gate read path)."""
    row = conn.execute(
        """
        SELECT audit_id, runtime_session_id, draft_sha256, passed, trace_verified,
               disclosure, refusal_count, failures, CAST(recorded_at AS VARCHAR)
        FROM log_answer_audit WHERE draft_sha256 = ?
        ORDER BY recorded_at DESC, audit_id DESC LIMIT 1
        """,
        [draft_sha256],
    ).fetchone()
    if row is None:
        return None
    cols = [
        "audit_id",
        "runtime_session_id",
        "draft_sha256",
        "passed",
        "trace_verified",
        "disclosure",
        "refusal_count",
        "failures",
        "recorded_at",
    ]
    record = dict(zip(cols, row, strict=True))
    if record["failures"] is not None:
        record["failures"] = json.loads(str(record["failures"]))
    return record


# ---------------------------------------------------------------------------
# Runtime improvement queue (OPERATING_ROLES.md slice 3, "Improvement scan,
# queue, sharing").
#
# The `improvement_scan` role's private, local write path. Deliberately
# decoupled from `premura.ui.improvement_kinds`, mirroring `record_handoff`
# above: this module stays a generic session-log substrate shared by the
# harness and the runtime layer, so it does NOT import Stage 4's `premura.ui`
# package. `kind` is validated here only as a non-empty string — checking it
# against the OPEN kind registry (and auto-registering a new kind with a
# description) is the MCP-layer wrapper's job
# (`premura.mcp.server.improvement_queue_record`), exactly like
# `orchestrator_handoff`'s role-registry check lives at that same layer, not
# here. `status` and `privacy_level` ARE fixed, closed vocabularies (the
# draft's seven lifecycle statuses and three sharing levels) and so ARE
# validated at this boundary, the same style as every other status field in
# this module.
# ---------------------------------------------------------------------------

# The draft's seven-value improvement-item lifecycle. The rule for extending
# it is the existing one — add the value here (this module only); it is NOT
# a Rule-2 open registry like `kind`, because the lifecycle states are a
# small closed vocabulary the spec names outright, not an open categorization.
IMPROVEMENT_ITEM_STATUSES: frozenset[str] = frozenset(
    {
        "open",
        "issue_proposed",
        "issue_created",
        "pr_proposed",
        "pr_created",
        "done",
        "dismissed",
    }
)

# The draft's three sharing levels ("Supported sharing levels"). `privacy_level`
# names which level THIS candidate would need if it were ever shared; sharing
# itself (share packets, GitHub writes) is later-slice work (slice 4) and no
# code path in this slice reads this field to make a network call.
IMPROVEMENT_PRIVACY_LEVELS: frozenset[str] = frozenset(
    {"minimal", "structural", "synthetic_example"}
)


def record_improvement_item(
    conn: duckdb.DuckDBPyConnection,
    *,
    kind: str,
    summary: str,
    privacy_level: str,
    suggested_action: str | None = None,
    trace_refs: Sequence[str] | None = None,
    github_refs: Sequence[str] | None = None,
    status: str = "open",
) -> str:
    """Insert one ``log_improvement_item`` row and return its ``item_id``.

    ``status`` is validated against :data:`IMPROVEMENT_ITEM_STATUSES` and
    ``privacy_level`` against :data:`IMPROVEMENT_PRIVACY_LEVELS`; an
    out-of-vocabulary value raises :class:`ValueError`. ``kind`` and
    ``summary`` must be non-empty strings; ``kind`` is NOT checked against
    the open kind registry here (see module note above — that check, and the
    add-a-kind path, live at the MCP wrapper). ``trace_refs`` /
    ``github_refs`` are compact PHI-safe references, stored as JSON lists
    (empty list when omitted); ``github_refs`` is inert in this slice — no
    code path here ever reaches GitHub.
    """
    if status not in IMPROVEMENT_ITEM_STATUSES:
        raise ValueError(
            f"status must be one of {sorted(IMPROVEMENT_ITEM_STATUSES)!r}, got {status!r}."
        )
    if privacy_level not in IMPROVEMENT_PRIVACY_LEVELS:
        raise ValueError(
            f"privacy_level must be one of {sorted(IMPROVEMENT_PRIVACY_LEVELS)!r}, "
            f"got {privacy_level!r}."
        )
    _require_non_empty(kind, field="kind")
    _require_non_empty(summary, field="summary")

    item_id = _mint_id()
    conn.execute(
        """
        INSERT INTO log_improvement_item
            (item_id, created_at, status, kind, summary, suggested_action,
             privacy_level, trace_refs_json, github_refs_json)
        VALUES (?, now(), ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            item_id,
            status,
            kind,
            summary,
            suggested_action,
            privacy_level,
            json.dumps(list(trace_refs) if trace_refs else []),
            json.dumps(list(github_refs) if github_refs else []),
        ],
    )
    return item_id


_IMPROVEMENT_ITEM_COLUMNS = (
    "item_id",
    "created_at",
    "status",
    "kind",
    "summary",
    "suggested_action",
    "privacy_level",
    "trace_refs_json",
    "github_refs_json",
)


def _improvement_item_row(row: tuple[object, ...]) -> dict[str, object]:
    record = dict(zip(_IMPROVEMENT_ITEM_COLUMNS, row, strict=True))
    record["trace_refs"] = json.loads(str(record.pop("trace_refs_json")))
    record["github_refs"] = json.loads(str(record.pop("github_refs_json")))
    return record


def list_improvement_items(
    conn: duckdb.DuckDBPyConnection,
    *,
    status: str | None = None,
    kind: str | None = None,
) -> list[dict[str, object]]:
    """Read the improvement queue, oldest first, optionally filtered (JSON-safe).

    A ``status`` outside :data:`IMPROVEMENT_ITEM_STATUSES` raises
    :class:`ValueError` — a typo'd filter is a caller bug, not an empty
    result (same discipline as
    :func:`premura.session_log.improvement_read.read_improvements`).
    ``kind`` is unrestricted (the open registry lives elsewhere); an unknown
    kind simply matches nothing.
    """
    if status is not None and status not in IMPROVEMENT_ITEM_STATUSES:
        raise ValueError(
            f"status must be one of {sorted(IMPROVEMENT_ITEM_STATUSES)!r} or None, got {status!r}."
        )
    clauses: list[str] = []
    params: list[object] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    rows = conn.execute(
        f"""
        SELECT item_id, CAST(created_at AS VARCHAR), status, kind, summary,
               suggested_action, privacy_level, trace_refs_json, github_refs_json
        FROM log_improvement_item
        {where}
        ORDER BY created_at ASC, item_id ASC
        """,
        params,
    ).fetchall()
    return [_improvement_item_row(row) for row in rows]


def get_improvement_item(
    conn: duckdb.DuckDBPyConnection,
    *,
    item_id: str,
) -> dict[str, object] | None:
    """Read back exactly one improvement-queue item by id, or ``None``."""
    row = conn.execute(
        """
        SELECT item_id, CAST(created_at AS VARCHAR), status, kind, summary,
               suggested_action, privacy_level, trace_refs_json, github_refs_json
        FROM log_improvement_item WHERE item_id = ?
        """,
        [item_id],
    ).fetchone()
    if row is None:
        return None
    return _improvement_item_row(row)
