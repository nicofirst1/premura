"""Source refresh (re-ingest) idempotency guarantee (issue #101).

`premura ingest <source> [path] [--force]` is the one-command refresh path. This
pins the operator-visible guarantee behind it, asserted through the warehouse's
most-recent reading (the same MAX(ts_utc) an operator sees via `premura status`)
rather than through bookkeeping internals:

- an *unchanged* export re-ingested is a no-op (sha256 skip; reading unchanged),
- an *updated* export re-ingested advances the latest reading,
- `--force` reloads despite an unchanged hash (fresh run row; same reading).

The mechanism already exists; these tests document and verify it as a refresh
workflow. Synthetic Daylio export only (no real operator data), mirroring
tests/test_parsers/test_daylio.py.
"""

from __future__ import annotations

from pathlib import Path

from premura.cli import _ingest_one

_HEADER = "full_date,date,weekday,time,mood,activities,scales,note_title,note\n"
_ROWS_V1 = (
    "2026-07-26,July 26,Sunday,18:20,rad,run,,,\n2026-07-27,July 27,Monday,13:48,meh,work,,,\n"
)
# A newer-dated entry: a different sha256 and a later ts_utc than V1's latest.
_LATER_ROW = "2026-07-28,July 28,Tuesday,09:00,good,walk,,,\n"


def _write_daylio(path: Path, *, extra: str = "") -> None:
    path.write_text(_HEADER + _ROWS_V1 + extra, encoding="utf-8")


def _latest_mood_reading(conn):
    row = conn.execute(
        "SELECT MAX(ts_utc) FROM hp.fact_measurement WHERE metric_id = 'mood_score'"
    ).fetchone()
    return row[0] if row else None


def _run_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM hp.ingest_run").fetchone()[0]


def test_reingesting_updated_export_advances_latest_reading(
    empty_warehouse, tmp_path: Path
) -> None:
    export = tmp_path / "daylio_export.csv"
    _write_daylio(export)
    _ingest_one(empty_warehouse, "daylio", export)
    before = _latest_mood_reading(empty_warehouse)

    # Operator drops an updated export under the same name, then refreshes.
    _write_daylio(export, extra=_LATER_ROW)
    _ingest_one(empty_warehouse, "daylio", export)
    after = _latest_mood_reading(empty_warehouse)

    assert before is not None
    assert after is not None
    assert after > before, "a changed export must advance the warehouse's latest reading"


def test_reingesting_unchanged_export_is_a_noop(empty_warehouse, tmp_path: Path) -> None:
    export = tmp_path / "daylio_export.csv"
    _write_daylio(export)
    _ingest_one(empty_warehouse, "daylio", export)
    reading_before = _latest_mood_reading(empty_warehouse)
    runs_before = _run_count(empty_warehouse)

    # Same bytes → same sha256 → skipped: no new run, reading unmoved.
    _ingest_one(empty_warehouse, "daylio", export)

    assert _latest_mood_reading(empty_warehouse) == reading_before
    assert _run_count(empty_warehouse) == runs_before


def test_force_reingest_reloads_despite_unchanged_hash(empty_warehouse, tmp_path: Path) -> None:
    export = tmp_path / "daylio_export.csv"
    _write_daylio(export)
    _ingest_one(empty_warehouse, "daylio", export)
    reading_before = _latest_mood_reading(empty_warehouse)
    runs_before = _run_count(empty_warehouse)

    # --force bypasses the sha256 skip and reloads the same bytes: a fresh run
    # row is written, and the (unchanged) data leaves the latest reading put.
    _ingest_one(empty_warehouse, "daylio", export, force=True)

    assert _latest_mood_reading(empty_warehouse) == reading_before
    assert _run_count(empty_warehouse) == runs_before + 1
