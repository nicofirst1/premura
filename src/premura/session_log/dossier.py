"""Read-only session dossier — the judge's single read surface (judge-ai m3 FR-2).

The judge AI (and the future improvement hook) must read a recorded session to
assess it, but they must NEVER reach into the session-log tables ad hoc and must
NEVER write the log — the harness is the sole writer (FR-021 / NFR-1). This
module is the one read surface that satisfies both: it opens the log STRICTLY
READ-ONLY (:func:`store.connect(..., read_only=True)`) and assembles one session
into a judge-readable :class:`SessionDossier`.

What a dossier carries (FR-2):

* **session metadata** — the models (operator / driver) and the run kind;
* **the grader's recomputed facts** — ``contract_pass`` and the loader-measured
  row counts from ``log_ingest_provenance`` (the verdict-bearing ingest step).
  The judge *evaluates* these facts; it can never alter them — this surface is
  read-only by construction;
* **per-attempt telemetry** — the durable ``log_live_trial_attempt`` rows;
* **the full transcript** — every ``log_turn`` row in ``turn_index`` order.

A session with no recorded turns is reported explicitly (``has_transcript`` is
False, ``transcript`` is empty) rather than failing — some tiers record no
conversation. An unknown session id raises :class:`KeyError` so the judge never
silently assesses an empty dossier as if it were a real run.

No code path here syncs or exports the dossier, the transcript, or any PHI
(NFR-002): it is a local, in-process read of the local session-log file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from premura.session_log import store

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb


@dataclass(frozen=True, slots=True)
class DossierTurn:
    """One transcript turn as the judge reads it (a read projection of log_turn)."""

    turn_index: int
    role: str
    content: str
    tool_name: str | None = None
    model: str | None = None
    token_count: int | None = None


@dataclass(frozen=True, slots=True)
class DossierAttempt:
    """One per-attempt telemetry row as the judge reads it (read projection)."""

    attempt_index: int
    self_reconciliation_passed: bool
    source_columns: list[str]
    accounted: list[str]
    unaccounted: list[str]
    parser_error: str | None


@dataclass(frozen=True, slots=True)
class SessionDossier:
    """One recorded session assembled for the judge (FR-2).

    Carries the four parts the rubric judges against: session metadata, the
    grader's recomputed facts (``contract_pass`` + row counts), per-attempt
    telemetry, and the full ordered transcript. ``has_transcript`` makes the
    no-turns case explicit so a tier that records no conversation is read as
    "no transcript", not mistaken for an error.
    """

    session_id: str
    operator_model: str
    driver_model: str
    run_kind: str
    contract_pass: bool | None
    rows_inserted: int | None
    attempts: list[DossierAttempt] = field(default_factory=list)
    transcript: list[DossierTurn] = field(default_factory=list)

    @property
    def has_transcript(self) -> bool:
        """True iff the session recorded at least one conversation turn."""
        return bool(self.transcript)


def _read_session_meta(conn: duckdb.DuckDBPyConnection, session_id: str) -> tuple[str, str, str]:
    row = conn.execute(
        "SELECT operator_model, driver_model, run_kind FROM log_session WHERE session_id = ?",
        [session_id],
    ).fetchone()
    if row is None:
        raise KeyError(f"no session {session_id!r} in this session log")
    return str(row[0]), str(row[1]), str(row[2])


def _read_grader_facts(
    conn: duckdb.DuckDBPyConnection, session_id: str
) -> tuple[bool | None, int | None]:
    """Read the verdict-bearing ingest step's grader-recomputed facts.

    Joins ``log_ingest_provenance`` to its ``log_step`` so the dossier reads the
    grader's ``contract_pass`` and the loader-measured ``rows_inserted`` for THIS
    session. Returns ``(None, None)`` when the session has no ingest provenance
    (e.g. a session that never reached the ingest step), so the judge sees the
    absence honestly rather than a fabricated pass.
    """
    row = conn.execute(
        """
        SELECT p.contract_pass, p.rows_inserted
        FROM log_ingest_provenance AS p
        JOIN log_step AS s ON s.step_id = p.step_id
        WHERE s.session_id = ?
        ORDER BY s.started_at, s.step_id
        LIMIT 1
        """,
        [session_id],
    ).fetchone()
    if row is None:
        return None, None
    contract_pass = None if row[0] is None else bool(row[0])
    rows_inserted = None if row[1] is None else int(row[1])
    return contract_pass, rows_inserted


def _read_attempts(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[DossierAttempt]:
    rows = conn.execute(
        """
        SELECT attempt_index, self_reconciliation_passed,
               source_columns_json, accounted_json, unaccounted_json, parser_error
        FROM log_live_trial_attempt
        WHERE session_id = ?
        ORDER BY attempt_index
        """,
        [session_id],
    ).fetchall()
    return [
        DossierAttempt(
            attempt_index=int(r[0]),
            self_reconciliation_passed=bool(r[1]),
            source_columns=list(json.loads(r[2])),
            accounted=list(json.loads(r[3])),
            unaccounted=list(json.loads(r[4])),
            parser_error=r[5],
        )
        for r in rows
    ]


def _read_transcript(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[DossierTurn]:
    rows = conn.execute(
        """
        SELECT turn_index, role, content, tool_name, model, token_count
        FROM log_turn
        WHERE session_id = ?
        ORDER BY turn_index
        """,
        [session_id],
    ).fetchall()
    return [
        DossierTurn(
            turn_index=int(r[0]),
            role=str(r[1]),
            content=str(r[2]),
            tool_name=r[3],
            model=r[4],
            token_count=None if r[5] is None else int(r[5]),
        )
        for r in rows
    ]


def build_dossier(log_path: Path, *, session_id: str) -> SessionDossier:
    """Assemble one recorded session into a judge-readable dossier (FR-2).

    Opens ``log_path`` STRICTLY READ-ONLY, reads the four parts, and returns a
    :class:`SessionDossier`. The read surface never writes the log — the harness
    stays the sole writer (NFR-1). An unknown ``session_id`` raises
    :class:`KeyError`; a session with no recorded turns yields an empty
    transcript with ``has_transcript`` False (FR-2 no-turns case).
    """
    conn = store.connect(log_path, read_only=True)
    try:
        operator_model, driver_model, run_kind = _read_session_meta(conn, session_id)
        contract_pass, rows_inserted = _read_grader_facts(conn, session_id)
        attempts = _read_attempts(conn, session_id)
        transcript = _read_transcript(conn, session_id)
    finally:
        conn.close()

    return SessionDossier(
        session_id=session_id,
        operator_model=operator_model,
        driver_model=driver_model,
        run_kind=run_kind,
        contract_pass=contract_pass,
        rows_inserted=rows_inserted,
        attempts=attempts,
        transcript=transcript,
    )


__all__ = [
    "DossierAttempt",
    "DossierTurn",
    "SessionDossier",
    "build_dossier",
]
