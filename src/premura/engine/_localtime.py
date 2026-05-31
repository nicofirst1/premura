"""Local-calendar-day resolution for analytical pairing (DRIFT-1).

The warehouse stores every fact with a naive-UTC ``ts_utc`` *and* a ``local_tz``
descriptor (see ``001_init.sql`` — ``hp.fact_measurement.local_tz`` /
``hp.fact_interval.local_tz``). Stage 2 carries both downstream; this module is
the single, pure converter that turns one naive-UTC instant + its ``local_tz``
into the *local* calendar day a near-midnight observation actually belongs to.

Why this matters: ``correlate`` pairs two daily series by calendar day. Keying
on the UTC day puts sleep / overnight-HRV observations on the wrong day for any
operator not at UTC, shifting the declared lag by a day. Pairing on the *local*
calendar day fixes that (spec §40, ADR-0008).

``local_tz`` is heterogeneous across parsers, and this helper handles all three
shapes it can take, never raising on a bad value (it falls back to UTC and flags
the fallback so the caller can surface it honestly):

* an **offset string** ``±HH:MM`` or ``±HH:MM:SS`` — Health Connect / Garmin
  (``_offset_str`` in those parsers);
* an **IANA zone name** like ``"Europe/Rome"`` or ``"UTC"`` — Sleep as Android
  (``tz_name``), resolved with ``dateutil.tz.gettz`` (already a dependency; the
  sleep parser uses it; it is offline);
* ``None`` / empty / unparseable — BMT stores ``None``; here we fall back to the
  UTC day and flag it.

This module reads no warehouse, makes no network call, holds no clock, and is
fully deterministic.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from dateutil import tz as _dateutil_tz

__all__ = ["local_calendar_day"]


# ``±HH:MM`` or ``±HH:MM:SS`` — the fixed-offset shape Health Connect / Garmin
# store via ``_offset_str``. Seconds are accepted for completeness though current
# parsers only emit whole minutes.
_OFFSET_RE = re.compile(r"^(?P<sign>[+-])(?P<hh>\d{2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?$")

# Real-world UTC offsets span ≈ [-12:00, +14:00]; ±18:00 is a generous ceiling
# that still rejects nonsense like "+99:99". Magnitude is compared before sign.
_MAX_OFFSET = timedelta(hours=18)


def local_calendar_day(ts_utc: datetime, local_tz: str | None) -> tuple[date, bool]:
    """Return the local calendar day for a naive-UTC instant + its ``local_tz``.

    Parameters
    ----------
    ts_utc:
        A timezone-naive datetime whose wall-clock represents UTC (exactly how
        the warehouse stores ``ts_utc`` / ``end_utc``).
    local_tz:
        The stored local-timezone descriptor: an offset string ``±HH:MM`` /
        ``±HH:MM:SS``, an IANA zone name (``"Europe/Rome"``, ``"UTC"``), or
        ``None``/empty/unparseable.

    Returns
    -------
    ``(local_date, used_utc_fallback)`` where ``local_date`` is the calendar day
    the observation falls on in its local zone, and ``used_utc_fallback`` is
    ``True`` only when ``local_tz`` was missing or could not be interpreted and
    the UTC day was used instead. This function never raises on a bad ``local_tz``.
    """
    if local_tz is None:
        return (ts_utc.date(), True)
    stripped = local_tz.strip()
    if not stripped:
        return (ts_utc.date(), True)

    # 1. Fixed-offset string (Health Connect / Garmin). local = utc + offset.
    match = _OFFSET_RE.match(stripped)
    if match is not None:
        hh = int(match.group("hh"))
        mm = int(match.group("mm"))
        ss = int(match.group("ss") or 0)
        delta = timedelta(hours=hh, minutes=mm, seconds=ss)
        # Reject implausible offsets (e.g. "+99:99"): minutes/seconds must be a
        # real sexagesimal component, and the magnitude must fall inside the real
        # UTC range (≈ [-12:00, +14:00]; we allow up to ±18:00 to stay generous
        # without admitting garbage). Anything outside → UTC fallback, flagged —
        # the same honest treatment as an unparseable zone, never a fake offset.
        if mm >= 60 or ss >= 60 or delta > _MAX_OFFSET:
            return (ts_utc.date(), True)
        if match.group("sign") == "-":
            delta = -delta
        return ((ts_utc + delta).date(), False)

    # 2. IANA zone name (Sleep as Android). Interpret ts_utc as UTC, convert.
    zone = _dateutil_tz.gettz(stripped)
    if zone is None:
        # Unknown / unparseable zone: deterministic UTC fallback, flagged.
        return (ts_utc.date(), True)
    local = ts_utc.replace(tzinfo=_dateutil_tz.UTC).astimezone(zone)
    return (local.date(), False)
