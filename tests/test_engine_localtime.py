"""Unit tests for the local-calendar-day helper (DRIFT-1).

``local_calendar_day`` converts a naive-UTC instant plus its heterogeneous
``local_tz`` descriptor into the local calendar day used for ``correlate``
pairing. It must handle every shape the parsers store (offset string, IANA zone
name, ``None``) and NEVER raise on a bad timezone — falling back to the UTC day
and flagging the fallback instead.
"""

from __future__ import annotations

from datetime import date, datetime

from premura.engine._localtime import local_calendar_day

# ---------------------------------------------------------------------------
# Offset strings (Health Connect / Garmin via _offset_str)
# ---------------------------------------------------------------------------


def test_positive_offset_crosses_midnight_forward() -> None:
    # 23:30 UTC + 02:00 = 01:30 next day local -> local day advances.
    ts = datetime(2026, 5, 29, 23, 30)
    day, fallback = local_calendar_day(ts, "+02:00")
    assert day == date(2026, 5, 30)
    assert fallback is False


def test_negative_offset_crosses_midnight_backward() -> None:
    # 02:00 UTC - 05:00 = 21:00 previous day local -> local day retreats.
    ts = datetime(2026, 5, 30, 2, 0)
    day, fallback = local_calendar_day(ts, "-05:00")
    assert day == date(2026, 5, 29)
    assert fallback is False


def test_offset_within_same_day_does_not_shift() -> None:
    ts = datetime(2026, 5, 29, 12, 0)
    day, fallback = local_calendar_day(ts, "+02:00")
    assert day == date(2026, 5, 29)
    assert fallback is False


def test_offset_with_seconds_component() -> None:
    ts = datetime(2026, 5, 29, 23, 59, 59)
    day, fallback = local_calendar_day(ts, "+00:00:30")
    assert day == date(2026, 5, 30)
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


def test_none_tz_falls_back_to_utc_day_flagged() -> None:
    ts = datetime(2026, 5, 29, 23, 30)
    day, fallback = local_calendar_day(ts, None)
    assert day == date(2026, 5, 29)
    assert fallback is True


def test_empty_tz_falls_back_to_utc_day_flagged() -> None:
    ts = datetime(2026, 5, 29, 23, 30)
    day, fallback = local_calendar_day(ts, "   ")
    assert day == date(2026, 5, 29)
    assert fallback is True


def test_garbage_tz_falls_back_without_raising() -> None:
    ts = datetime(2026, 5, 29, 23, 30)
    for garbage in ("not-a-zone", "Mars/Olympus", "+99:99x", "12:00"):
        day, fallback = local_calendar_day(ts, garbage)
        assert day == date(2026, 5, 29)
        assert fallback is True


def test_offset_out_of_range_falls_back_flagged() -> None:
    # Regex-shaped but implausible offsets must be flagged as fallback, never
    # treated as a real offset (e.g. "+99:99" used to shift by ~99h silently).
    ts = datetime(2026, 5, 29, 23, 30)
    for bad_offset in ("+99:99", "+25:00", "-30:00", "+12:75", "+10:00:99"):
        day, fallback = local_calendar_day(ts, bad_offset)
        assert day == date(2026, 5, 29), bad_offset
        assert fallback is True, bad_offset


def test_offset_at_generous_ceiling_still_valid() -> None:
    # ±18:00 is the accepted ceiling; +14:00 (real-world max, Kiribati) must work.
    ts = datetime(2026, 5, 29, 12, 0)
    day, fallback = local_calendar_day(ts, "+14:00")
    assert fallback is False
    assert day == date(2026, 5, 30)
