"""Nutrition-intake resolver.

Resolves a declared ``nutrition_intake`` dependency against the dedicated
``hp.nutrition_intake_event`` / ``hp.nutrition_intake_item`` /
``hp.nutrition_quantity`` tables (migration ``004_profile_intake.sql``). Domain
meaning: a nutrition intake is an *eating/drinking occurrence* carrying one or
more nutrient/energy quantities — never a body observation. This resolver reads
the intake tables only; it never falls back to ``hp.fact_measurement`` even when
an observation metric happens to share the quantity key (NFR-003).

Like the observation and profile resolvers, this one stays **generic**: it
turns one declared quantity key + window into a domain-level payload (ordered
daily points + coverage + freshness basis). It does **not** compute trend
direction or impute missing days — that is the nutrition-trend signal's job
(WP04). Resolvers supply declared inputs; signals own the answer (the BMI
precedent).

Day basis (NFR-006): every event carries a naive-UTC ``start_utc`` and an
optional ``local_tz`` descriptor. When ``local_tz`` is present and parseable,
each event is bucketed by its **local calendar day** via the shared
:func:`premura.engine._localtime.local_calendar_day` converter; otherwise the
naive-UTC day is used. The basis is reported in the payload as ``day_basis`` so
computation and reported metadata never drift apart. Bases are never silently
mixed: if *any* event in the window falls back to the UTC day, the payload's
``day_basis`` is the fallback basis.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .._localtime import local_calendar_day
from .._registry import resolver
from .._resolution import ResolutionRequest, ResolvedInput
from .._results import FreshnessState

if TYPE_CHECKING:
    import duckdb


_DOMAIN = "nutrition_intake"

DEFAULT_WINDOW_DAYS: int = 30
"""Default look-back window (in days) when the caller declares no explicit one."""

DAY_BASIS_LOCAL: str = "local_calendar_day"
DAY_BASIS_UTC: str = "naive_utc_day"

# Pull every nutrition quantity (event-level OR item-level) matching the declared
# key, joined back to its owning event so we can read the event timestamp +
# local_tz. The CHECK constraint on hp.nutrition_quantity guarantees exactly one
# of nutrition_event_id / nutrition_item_id is set, so COALESCE through the item
# parent recovers the event id for item-level quantities without double-counting.
_QUERY = """
SELECT e.start_utc, e.local_tz, q.value_num
FROM hp.nutrition_quantity q
LEFT JOIN hp.nutrition_intake_item i
    ON q.nutrition_item_id = i.nutrition_item_id
JOIN hp.nutrition_intake_event e
    ON e.nutrition_event_id = COALESCE(q.nutrition_event_id, i.nutrition_event_id)
WHERE q.quantity_key = ?
  AND e.start_utc <= ?
  AND e.start_utc >= ?
ORDER BY e.start_utc ASC
"""


def _to_naive_utc(value: datetime) -> datetime:
    """Convert a (possibly tz-aware) datetime to naive UTC.

    Intake event timestamps are stored as DuckDB ``TIMESTAMP`` (naive UTC), so
    the anchor must be normalized before it can be compared. A naive datetime is
    assumed to already be UTC and passed through unchanged.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _resolve_window_days(request: ResolutionRequest) -> int:
    """Read a caller-declared window (parsed from ``failure_mode``) or default.

    The resolver protocol is fixed at ``(conn, request)``; callers thread an
    optional window through the declaration's ``failure_mode`` slot using the
    ``window_days=<int>`` convention. Anything unparseable falls back to the
    repo default rather than raising — window selection is a soft preference,
    not a programming error.
    """
    raw = request.dependency.failure_mode or ""
    for token in raw.replace(",", " ").split():
        if token.startswith("window_days="):
            try:
                parsed = int(token.split("=", 1)[1])
            except ValueError:
                return DEFAULT_WINDOW_DAYS
            return parsed if parsed > 0 else DEFAULT_WINDOW_DAYS
    return DEFAULT_WINDOW_DAYS


@resolver(domain=_DOMAIN)
def resolve_nutrition_intake(
    conn: duckdb.DuckDBPyConnection | None,
    request: ResolutionRequest,
) -> ResolvedInput:
    """Resolve one nutrition-intake dependency as of ``request.anchor_ts``.

    ``request.dependency.required_key`` is interpreted as a
    ``nutrition_quantity.quantity_key`` (e.g. ``"energy"``, ``"protein"``).

    Outcomes:

    * No matching quantity in the window → ``usable=False,
      absence_reason="missing"``. **No fallback** into observation history is
      attempted — that is the central no-hidden-fallback guarantee (NFR-003).
    * Otherwise → ``usable=True`` with the generic daily-points payload
      (``matched_key``, ``window_days``, ordered ``points``, ``days_with_data``,
      ``window_day_count``, ``latest_logged_at``, ``freshness_state``,
      ``day_basis``). The payload is domain-level: it carries coverage and a
      freshness basis, but no trend verdict.

    ``freshness_state`` is the *basis* the signal layer interprets: ``current``
    when at least one matching event exists in the window, ``unavailable`` when
    none do. The resolver does not itself enforce a freshness cutoff — that
    policy lives in the signal (FR-005).

    Raises :class:`ValueError` only on programming errors (non-string key or
    missing connection), never on ordinary missing data.
    """
    quantity_key = request.dependency.required_key
    if not isinstance(quantity_key, str) or not quantity_key:
        raise ValueError(
            f"nutrition_intake required_key must be a non-empty quantity_key; got {quantity_key!r}"
        )
    if conn is None:
        raise ValueError("nutrition_intake resolver requires a DuckDB connection; got None")

    anchor = request.anchor_ts
    anchor_naive = _to_naive_utc(anchor)
    window_days = _resolve_window_days(request)
    window_start = anchor_naive - timedelta(days=window_days)

    rows = conn.execute(_QUERY, [quantity_key, anchor_naive, window_start]).fetchall()

    if not rows:
        return ResolvedInput(
            domain=_DOMAIN,
            required_key=quantity_key,
            anchor_ts=anchor,
            usable=False,
            absence_reason="missing",
            message=(
                f"no nutrition intake with quantity key {quantity_key!r} logged in the "
                f"{window_days}-day window ending {anchor_naive.isoformat()} — honest refusal "
                "rather than substituting a same-named observation"
            ),
            payload={
                "matched_key": quantity_key,
                "window_days": window_days,
                "freshness_state": FreshnessState.UNAVAILABLE.value,
            },
        )

    # Bucket every matching quantity by its (local) calendar day. If any event
    # lacks a usable local_tz we fall back to the UTC day for the whole payload,
    # so the reported basis can never mix local and UTC days silently.
    daily_totals: dict[Any, float] = {}
    any_utc_fallback = False
    latest_logged_at: datetime | None = None
    for start_utc, local_tz, value_num in rows:
        day, used_utc_fallback = local_calendar_day(start_utc, local_tz)
        any_utc_fallback = any_utc_fallback or used_utc_fallback
        daily_totals[day] = daily_totals.get(day, 0.0) + float(value_num)
        if latest_logged_at is None or start_utc > latest_logged_at:
            latest_logged_at = start_utc

    day_basis = DAY_BASIS_UTC if any_utc_fallback else DAY_BASIS_LOCAL
    points = [{"day": day.isoformat(), "value": daily_totals[day]} for day in sorted(daily_totals)]

    return ResolvedInput(
        domain=_DOMAIN,
        required_key=quantity_key,
        anchor_ts=anchor,
        usable=True,
        payload={
            "matched_key": quantity_key,
            "window_days": window_days,
            "points": points,
            "days_with_data": len(daily_totals),
            "window_day_count": window_days,
            "latest_logged_at": latest_logged_at,
            "freshness_state": FreshnessState.CURRENT.value,
            "day_basis": day_basis,
        },
    )


__all__ = ["resolve_nutrition_intake"]
