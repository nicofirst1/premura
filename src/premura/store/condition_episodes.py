"""Store boundary for operator-declared condition episodes.

One home (``hp.condition_episode``, migration 007) for the agent-mediated
capture of "I was in <condition_label> from <start_day> through <end_day>"
declarations, so off/on analytical questions stop re-declaring episodes per
request. The honesty posture mirrors profile capture:

- a row is the operator's *assertion on a date*, never a verified condition;
  the label is operator vocabulary (any non-empty string, never an enum);
- corrections **append** a new row that links back via
  ``supersedes_episode_id`` (the superseded row's ``superseded_at`` is closed);
- withdrawals set ``retracted_at`` + a reason; nothing is deleted;
- the *current* declared set for a label is always non-overlapping: a new
  declaration that overlaps a current episode of the same label is rejected
  here at the store boundary (correct or retract the existing one first), so
  the stored set is always analyzable without a seam refusal surprise;
- ``end_day=None`` means *ongoing at declaration time*. Ongoing episodes are
  listable (record-keeping) but excluded from the analysis read path
  (:func:`closed_episodes_for_label`) — an episode without an end has no
  after-window to compare against.

Episodes are never auto-detected or suggested from the data (the locked
no-scanning guardrail); only explicit operator declarations land here. The
engine stays stateless: this module only feeds the same pre-registered
request shape the caller could have declared by hand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import duckdb

DEFAULT_CONDITION_SOURCE_KIND = "agent_condition_capture"


def _dumps(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, default=str)


_RECORD_COLUMNS = """
    episode_id, condition_label, start_day, end_day, declared_at,
    capture_session_id, source_kind, source_ref, supersedes_episode_id,
    superseded_at, retracted_at, retraction_reason, note
"""


class ConditionEpisodeError(ValueError):
    """A condition-episode write the store boundary refuses, with the reason."""


@dataclass(frozen=True)
class ConditionEpisodeRecord:
    """Read-back shape for one stored condition-episode declaration."""

    episode_id: int
    condition_label: str
    start_day: date
    end_day: date | None
    declared_at: datetime
    capture_session_id: int | None
    source_kind: str
    source_ref: str | None
    supersedes_episode_id: int | None
    superseded_at: datetime | None
    retracted_at: datetime | None
    retraction_reason: str | None
    note: str | None

    @property
    def is_current(self) -> bool:
        return self.superseded_at is None and self.retracted_at is None

    @property
    def is_ongoing(self) -> bool:
        return self.end_day is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "condition_label": self.condition_label,
            "start_day": self.start_day.isoformat(),
            "end_day": self.end_day.isoformat() if self.end_day else None,
            "ongoing": self.is_ongoing,
            "declared_at": self.declared_at.isoformat(sep=" "),
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "supersedes_episode_id": self.supersedes_episode_id,
            "superseded_at": (
                self.superseded_at.isoformat(sep=" ") if self.superseded_at else None
            ),
            "retracted_at": self.retracted_at.isoformat(sep=" ") if self.retracted_at else None,
            "retraction_reason": self.retraction_reason,
            "note": self.note,
        }


def record_condition_episode(
    conn: duckdb.DuckDBPyConnection,
    *,
    condition_label: str,
    start_day: date,
    end_day: date | None = None,
    capture_session_id: int | None = None,
    source_kind: str = DEFAULT_CONDITION_SOURCE_KIND,
    source_ref: str | None = None,
    supersedes_episode_id: int | None = None,
    note: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> int:
    """Record one operator-declared condition episode; return its episode_id.

    Pass ``supersedes_episode_id`` to correct an existing declaration: the old
    row's ``superseded_at`` is closed and the new row links back — history is
    appended, never overwritten. A new declaration that overlaps a *current*
    episode of the same label (treating an ongoing episode as open-ended) is
    refused with :class:`ConditionEpisodeError`: correct (supersede) or retract
    the conflicting episode instead, so the stored current set stays
    non-overlapping and analyzable.
    """
    label = condition_label.strip() if isinstance(condition_label, str) else ""
    if not label:
        raise ConditionEpisodeError("condition_label must be a non-empty operator-declared string")
    if not isinstance(start_day, date) or isinstance(start_day, datetime):
        raise ConditionEpisodeError("start_day must be a local calendar date")
    if end_day is not None and (not isinstance(end_day, date) or isinstance(end_day, datetime)):
        raise ConditionEpisodeError("end_day must be a local calendar date or omitted (ongoing)")
    if end_day is not None and end_day < start_day:
        raise ConditionEpisodeError("end_day must not be before start_day")

    conn.execute("BEGIN")
    try:
        if supersedes_episode_id is not None:
            target = get_condition_episode(conn, supersedes_episode_id)
            if target is None:
                raise ConditionEpisodeError(
                    f"supersedes_episode_id {supersedes_episode_id} does not exist"
                )
            if not target.is_current:
                raise ConditionEpisodeError(
                    f"episode {supersedes_episode_id} is already "
                    f"{'superseded' if target.superseded_at else 'retracted'}; "
                    "supersede the current row instead"
                )
            conn.execute(
                "UPDATE hp.condition_episode SET superseded_at = now() WHERE episode_id = ?",
                [supersedes_episode_id],
            )

        conflict = _overlapping_current_episode(conn, label, start_day, end_day)
        if conflict is not None:
            raise ConditionEpisodeError(
                f"declaration overlaps current episode {conflict.episode_id} "
                f"({conflict.start_day.isoformat()}"
                f"–{conflict.end_day.isoformat() if conflict.end_day else 'ongoing'}) "
                f"for label {label!r}; supersede or retract it instead of "
                "stacking overlapping declarations"
            )

        row = conn.execute(
            """
            INSERT INTO hp.condition_episode
                (condition_label, start_day, end_day, capture_session_id,
                 source_kind, source_ref, supersedes_episode_id, note, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING episode_id
            """,
            [
                label,
                start_day,
                end_day,
                capture_session_id,
                source_kind,
                source_ref,
                supersedes_episode_id,
                note,
                _dumps(raw_payload),
            ],
        ).fetchone()
        conn.execute("COMMIT")
        assert row is not None
        return int(row[0])
    except Exception:
        conn.execute("ROLLBACK")
        raise


def retract_condition_episode(
    conn: duckdb.DuckDBPyConnection,
    episode_id: int,
    *,
    reason: str,
) -> ConditionEpisodeRecord:
    """Withdraw one current episode declaration; return the retracted record.

    The row stays in history with ``retracted_at`` + the operator's reason. A
    missing, already-retracted, or superseded episode is refused with
    :class:`ConditionEpisodeError` so a stale id never looks like a success.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ConditionEpisodeError("a retraction requires a non-empty reason")
    target = get_condition_episode(conn, episode_id)
    if target is None:
        raise ConditionEpisodeError(f"episode {episode_id} does not exist")
    if not target.is_current:
        raise ConditionEpisodeError(
            f"episode {episode_id} is already "
            f"{'superseded' if target.superseded_at else 'retracted'}"
        )
    conn.execute(
        """
        UPDATE hp.condition_episode
        SET retracted_at = now(), retraction_reason = ?
        WHERE episode_id = ?
        """,
        [reason.strip(), episode_id],
    )
    record = get_condition_episode(conn, episode_id)
    assert record is not None
    return record


def list_condition_episodes(
    conn: duckdb.DuckDBPyConnection,
    *,
    condition_label: str | None = None,
    include_history: bool = False,
) -> list[ConditionEpisodeRecord]:
    """List stored episode declarations, newest start first.

    By default only *current* declarations (not superseded, not retracted) are
    returned — what an analysis would use plus any ongoing episodes. Pass
    ``include_history=True`` to see the full append-only trail.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if condition_label is not None:
        clauses.append("condition_label = ?")
        params.append(condition_label.strip())
    if not include_history:
        clauses.append("superseded_at IS NULL AND retracted_at IS NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_RECORD_COLUMNS} FROM hp.condition_episode {where} "
        "ORDER BY start_day DESC, episode_id DESC",
        params,
    ).fetchall()
    return [_to_record(row) for row in rows]


def closed_episodes_for_label(
    conn: duckdb.DuckDBPyConnection,
    condition_label: str,
) -> list[ConditionEpisodeRecord]:
    """The analysis read path: current, *closed* episodes for one label.

    Ongoing episodes (no end_day) are excluded — they have no after-window to
    compare against — and superseded/retracted rows never appear. Ordered by
    start_day ascending, the order an analytical request declares them in.
    """
    rows = conn.execute(
        f"""
        SELECT {_RECORD_COLUMNS} FROM hp.condition_episode
        WHERE condition_label = ?
          AND superseded_at IS NULL AND retracted_at IS NULL
          AND end_day IS NOT NULL
        ORDER BY start_day ASC, episode_id ASC
        """,
        [condition_label.strip()],
    ).fetchall()
    return [_to_record(row) for row in rows]


def get_condition_episode(
    conn: duckdb.DuckDBPyConnection, episode_id: int
) -> ConditionEpisodeRecord | None:
    """Return one stored declaration by id (any state), or None."""
    row = conn.execute(
        f"SELECT {_RECORD_COLUMNS} FROM hp.condition_episode WHERE episode_id = ?",
        [episode_id],
    ).fetchone()
    return _to_record(row) if row is not None else None


# --------------------------------------------------------------------------- #
# Internal helpers.
# --------------------------------------------------------------------------- #


def _overlapping_current_episode(
    conn: duckdb.DuckDBPyConnection,
    label: str,
    start_day: date,
    end_day: date | None,
) -> ConditionEpisodeRecord | None:
    """Find a current same-label episode whose day range intersects the new one.

    Ranges are inclusive; a NULL end (ongoing) is open-ended on the right, on
    both sides of the comparison.
    """
    row = conn.execute(
        f"""
        SELECT {_RECORD_COLUMNS} FROM hp.condition_episode
        WHERE condition_label = ?
          AND superseded_at IS NULL AND retracted_at IS NULL
          AND start_day <= COALESCE(?, DATE '9999-12-31')
          AND COALESCE(end_day, DATE '9999-12-31') >= ?
        LIMIT 1
        """,
        [label, end_day, start_day],
    ).fetchone()
    return _to_record(row) if row is not None else None


def _to_record(row: Any) -> ConditionEpisodeRecord:
    return ConditionEpisodeRecord(
        episode_id=int(row[0]),
        condition_label=row[1],
        start_day=row[2],
        end_day=row[3],
        declared_at=row[4],
        capture_session_id=int(row[5]) if row[5] is not None else None,
        source_kind=row[6],
        source_ref=row[7],
        supersedes_episode_id=int(row[8]) if row[8] is not None else None,
        superseded_at=row[9],
        retracted_at=row[10],
        retraction_reason=row[11],
        note=row[12],
    )
