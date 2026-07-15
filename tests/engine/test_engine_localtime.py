"""Unit tests for the local-calendar-day helper (DRIFT-1).

``local_calendar_day`` converts a naive-UTC instant plus its heterogeneous
``local_tz`` descriptor into the local calendar day used for ``correlate``
pairing. It must handle every shape the parsers store (offset string, IANA zone
name, ``None``) and NEVER raise on a bad timezone — falling back to the UTC day
and flagging the fallback instead.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from premura.engine._localtime import local_calendar_day

# ---------------------------------------------------------------------------
# Offset strings (Health Connect / Garmin via _offset_str)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ts", "offset", "expected_day"),
    [
        # 23:30 UTC + 02:00 = 01:30 next day local -> local day advances.
        (datetime(2026, 5, 29, 23, 30), "+02:00", date(2026, 5, 30)),
        # 02:00 UTC - 05:00 = 21:00 previous day local -> local day retreats.
        (datetime(2026, 5, 30, 2, 0), "-05:00", date(2026, 5, 29)),
        # Offset within the same day does not shift.
        (datetime(2026, 5, 29, 12, 0), "+02:00", date(2026, 5, 29)),
        # Seconds component tips 23:59:59 forward across midnight.
        (datetime(2026, 5, 29, 23, 59, 59), "+00:00:30", date(2026, 5, 30)),
    ],
)
def test_offset_string_shifts_local_day(ts: datetime, offset: str, expected_day: date) -> None:
    day, fallback = local_calendar_day(ts, offset)
    assert day == expected_day
    assert fallback is False


# ---------------------------------------------------------------------------
# IANA zone names (Sleep as Android via tz_name) — dateutil.tz.gettz, offline
# ---------------------------------------------------------------------------


def test_iana_zone_shifts_local_day() -> None:
    # Europe/Rome is +02:00 in late May (DST). 23:30 UTC -> 01:30 next day local.
    ts = datetime(2026, 5, 29, 23, 30)
    day, fallback = local_calendar_day(ts, "Europe/Rome")
    assert day == date(2026, 5, 30)
    assert fallback is False


def test_iana_negative_zone_retreats_local_day() -> None:
    # America/New_York is -04:00 in late May (EDT). 02:00 UTC -> 22:00 prev day.
    ts = datetime(2026, 5, 30, 2, 0)
    day, fallback = local_calendar_day(ts, "America/New_York")
    assert day == date(2026, 5, 29)
    assert fallback is False


def test_iana_utc_zone_is_identity() -> None:
    ts = datetime(2026, 5, 29, 23, 30)
    day, fallback = local_calendar_day(ts, "UTC")
    assert day == date(2026, 5, 29)
    assert fallback is False


# ---------------------------------------------------------------------------
# Fallback cases — never raise, always flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_tz",
    [
        # None / empty -> no zone at all.
        None,
        "   ",
        # Garbage strings that never parse to a zone or offset.
        "not-a-zone",
        "Mars/Olympus",
        "+99:99x",
        "12:00",
        # Regex-shaped but implausible offsets must be flagged as fallback, never
        # treated as a real offset (e.g. "+99:99" used to shift ~99h silently).
        "+99:99",
        "+25:00",
        "-30:00",
        "+12:75",
        "+10:00:99",
    ],
)
def test_bad_tz_falls_back_to_utc_day_flagged(bad_tz: str | None) -> None:
    # Never raise: a bad/absent timezone falls back to the UTC day and flags it.
    ts = datetime(2026, 5, 29, 23, 30)
    day, fallback = local_calendar_day(ts, bad_tz)
    assert day == date(2026, 5, 29), bad_tz
    assert fallback is True, bad_tz


def test_offset_at_generous_ceiling_still_valid() -> None:
    # ±18:00 is the accepted ceiling; +14:00 (real-world max, Kiribati) must work.
    ts = datetime(2026, 5, 29, 12, 0)
    day, fallback = local_calendar_day(ts, "+14:00")
    assert fallback is False
    assert day == date(2026, 5, 30)
