"""Read-only judgment + improvement-proposal surfaces (improvement-hook m4 FR-2).

The improvement hook (and any agent that wants to act on its output) must read
``log_judgment`` rows to derive proposals and read ``log_improvement`` rows to
list them — but they must NEVER reach into the session-log tables ad hoc and must
NEVER write the log: the harness is the sole writer (FR-021 / NFR-1). This module
is the agent-facing read surface that satisfies both, with the SAME discipline as
:func:`premura.session_log.dossier.build_dossier`: it opens the log STRICTLY
READ-ONLY (:func:`store.connect(..., read_only=True)`) and returns frozen
dataclass rows in a deterministic order.

* :func:`read_judgments` — the judgments for one session, the scan core's input.
* :func:`read_improvements` — the proposals, filterable by session and/or status;
  an agent lists open proposals through this, never via raw SQL.

No code path here syncs or exports any row or PHI (NFR-002): it is a local,
in-process read of the local session-log file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from premura.session_log import store

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class JudgmentRow:
    """One ``log_judgment`` row as a reader sees it (a read projection).

    ``criteria`` is decoded from the stored JSON into the mapping of rubric
    criterion id → ``{band, rationale}``. The criterion ids are rubric-owned data,
    never enumerated in code — this surface returns whatever the judge recorded.
    """

    judgment_id: str
    session_id: str
    judge_model: str
    rubric_version: str
    status: str
    criteria: dict[str, dict[str, object]]
    overall_band: str | None
    rationale: str | None
    raw_output: str | None


@dataclass(frozen=True, slots=True)
class ImprovementRow:
    """One ``log_improvement`` proposal as a reader sees it (a read projection)."""

    improvement_id: str
    session_id: str
    judgment_id: str
    criterion_id: str | None
    area: str
    summary: str
    evidence: str
    playbook_version: str
    status: str


def read_judgments(log_path: Path, *, session_id: str) -> list[JudgmentRow]:
    """Read one session's judgments, read-only, in deterministic order (FR-2).

    Opens ``log_path`` STRICTLY READ-ONLY and returns the session's
    ``log_judgment`` rows ordered by ``judged_at`` then ``judgment_id`` (so the
    order is stable even when two judgments share a wall-clock instant). A session
    with no judgments yields an empty list rather than raising — the scan core
    treats "no judgments" as "nothing to propose".
    """
    conn = store.connect(log_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT judgment_id, session_id, judge_model, rubric_version, status,
                   criteria_json, overall_band, rationale, raw_output
            FROM log_judgment
            WHERE session_id = ?
            ORDER BY judged_at, judgment_id
            """,
            [session_id],
        ).fetchall()
    finally:
        conn.close()
    return [
        JudgmentRow(
            judgment_id=str(r[0]),
            session_id=str(r[1]),
            judge_model=str(r[2]),
            rubric_version=str(r[3]),
            status=str(r[4]),
            criteria=json.loads(r[5]),
            overall_band=r[6],
            rationale=r[7],
            raw_output=r[8],
        )
        for r in rows
    ]


def read_improvements(
    log_path: Path, *, session_id: str | None = None, status: str | None = None
) -> list[ImprovementRow]:
    """Read improvement proposals, read-only, filterable + deterministic (FR-2).

    Opens ``log_path`` STRICTLY READ-ONLY and returns ``log_improvement`` rows,
    optionally filtered by ``session_id`` and/or ``status``, ordered by
    ``created_at`` then ``improvement_id``. A ``status`` outside
    :data:`store.PROPOSAL_STATUSES` raises :class:`ValueError` rather than silently
    returning nothing — a typo'd filter is a caller bug, not an empty result. This
    is the agent-facing list surface: an agent lists open proposals through it,
    never via raw SQL.
    """
    if status is not None and status not in store.PROPOSAL_STATUSES:
        raise ValueError(
            f"status filter must be one of {sorted(store.PROPOSAL_STATUSES)!r} or None, "
            f"got {status!r}."
        )
    clauses: list[str] = []
    params: list[object] = []
    if session_id is not None:
        clauses.append("session_id = ?")
        params.append(session_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = store.connect(log_path, read_only=True)
    try:
        rows = conn.execute(
            f"""
            SELECT improvement_id, session_id, judgment_id, criterion_id, area,
                   summary, evidence, playbook_version, status
            FROM log_improvement
            {where}
            ORDER BY created_at, improvement_id
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [
        ImprovementRow(
            improvement_id=str(r[0]),
            session_id=str(r[1]),
            judgment_id=str(r[2]),
            criterion_id=r[3],
            area=str(r[4]),
            summary=str(r[5]),
            evidence=str(r[6]),
            playbook_version=str(r[7]),
            status=str(r[8]),
        )
        for r in rows
    ]


__all__ = [
    "ImprovementRow",
    "JudgmentRow",
    "read_improvements",
    "read_judgments",
]
