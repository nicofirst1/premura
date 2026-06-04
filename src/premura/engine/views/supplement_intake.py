"""Supplement-intake resolver.

Resolves a declared ``supplement_intake`` dependency against the dedicated
``hp.supplement_intake_event`` / ``hp.supplement_item`` tables (migration
``004_profile_intake.sql``). Domain meaning: a supplement intake is a
*supplement-taking occurrence* naming a product and/or ingredient — never a body
observation. This resolver reads the supplement intake tables only; it never
falls back to ``hp.fact_measurement`` or any other domain (NFR-003).

Like the nutrition resolver, this one stays **generic**: it turns a
caller-declared supplement *matcher* + window into a domain-level payload
(distinct logged days + coverage + freshness basis). It does **not** compute an
adherence verdict ("K of N days is good/bad") — that is the supplement-adherence
signal's job (WP04). Resolvers supply declared inputs; signals own the answer.

Matcher semantics — pinned here once (C-007 "guide, don't enumerate"). WP04,
WP05, and WP06 reference this single definition and never re-invent it:

* **No hardcoded supplement list.** The caller declares the matcher; the
  resolver never enumerates known supplements.
* **Case-insensitive substring.** A matcher token matches when it appears
  (case-folded) anywhere inside a label — exact match is the trivial case of a
  full-string substring.
* **Label precedence: product label, then ingredient label.** A token matches an
  item if it is a substring of ``product_label`` OR, when that does not match,
  of ``ingredient_label``. Product identity wins; the ingredient label is the
  fallback so a logged-by-ingredient row is still findable.
* **Multiple tokens combine as AND.** Whitespace splits the matcher into tokens;
  *every* token must match the item (under the product-then-ingredient rule) for
  the item to count. This lets a caller narrow ("vitamin d3") without enumerating
  brand names.

Day basis (NFR-006): every event carries a naive-UTC ``ts_utc`` and an optional
``local_tz``. When ``local_tz`` is present and parseable, each event is bucketed
by its **local calendar day** via the shared
:func:`premura.engine._localtime.local_calendar_day` converter; otherwise the
naive-UTC day is used. The basis is reported as ``day_basis`` so computation and
reported metadata never drift apart, and is never silently mixed: any UTC
fallback flips the whole payload's basis to the fallback.
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


_DOMAIN = "supplement_intake"

DEFAULT_WINDOW_DAYS: int = 30
"""Default look-back window (in days) when the caller declares no explicit one."""

DAY_BASIS_LOCAL: str = "local_calendar_day"
DAY_BASIS_UTC: str = "naive_utc_day"

# Pull every supplement event in the window together with its item labels so the
# matcher can be applied in Python (the matcher is a multi-token, product-then-
# ingredient, case-insensitive rule that does not map cleanly to a single SQL
# LIKE). One row per (event, item); an event with several items yields several
# rows, deduped to distinct days after matching.
_QUERY = """
SELECT e.ts_utc, e.local_tz, i.product_label, i.ingredient_label
FROM hp.supplement_intake_event e
JOIN hp.supplement_item i
    ON i.supplement_event_id = e.supplement_event_id
WHERE e.ts_utc <= ?
  AND e.ts_utc >= ?
ORDER BY e.ts_utc ASC
"""


def _to_naive_utc(value: datetime) -> datetime:
    """Convert a (possibly tz-aware) datetime to naive UTC.

    Supplement event timestamps are stored as DuckDB ``TIMESTAMP`` (naive UTC),
    so the anchor must be normalized before it can be compared. A naive datetime
    is assumed to already be UTC and passed through unchanged.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _resolve_window_days(request: ResolutionRequest) -> int:
    """Read a caller-declared window (parsed from ``failure_mode``) or default.

    The resolver protocol is fixed at ``(conn, request)``; callers thread an
    optional window through the declaration's ``failure_mode`` slot using the
    ``window_days=<int>`` convention. Anything unparseable falls back to the
    repo default rather than raising.
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


def matches_supplement(
    matcher: str,
    product_label: str | None,
    ingredient_label: str | None,
) -> bool:
    """Return True iff ``matcher`` selects an item with these labels.

    The single authoritative implementation of the matcher semantics pinned in
    this module's docstring: case-insensitive substring, product label then
    ingredient label, multiple whitespace-separated tokens combined as AND.

    Exposed (not underscore-prefixed) so WP04/WP05/WP06 reuse this exact rule
    rather than re-deriving it.
    """
    tokens = matcher.casefold().split()
    if not tokens:
        return False
    product = (product_label or "").casefold()
    ingredient = (ingredient_label or "").casefold()
    return all(token in product or token in ingredient for token in tokens)


@resolver(domain=_DOMAIN)
def resolve_supplement_intake(
    conn: duckdb.DuckDBPyConnection | None,
    request: ResolutionRequest,
) -> ResolvedInput:
    """Resolve one supplement-intake dependency as of ``request.anchor_ts``.

    ``request.dependency.required_key`` is interpreted as the caller-declared
    **matcher** (see module docstring for the pinned matcher semantics).

    Outcomes:

    * No matching supplement event in the window → ``usable=False,
      absence_reason="missing"``. **No fallback** into any other domain is
      attempted (NFR-003).
    * Otherwise → ``usable=True`` with the generic logged-days payload
      (``matcher``, ``window_days``, ``logged_days``, ``logged_day_count``,
      ``window_day_count``, ``latest_logged_at``, ``freshness_state``,
      ``day_basis``). The payload is domain-level coverage; the resolver does
      not decide whether that coverage is "adherent".

    Raises :class:`ValueError` only on programming errors (non-string matcher or
    missing connection), never on ordinary missing data.
    """
    matcher = request.dependency.required_key
    if not isinstance(matcher, str) or not matcher.strip():
        raise ValueError(
            f"supplement_intake required_key must be a non-empty matcher; got {matcher!r}"
        )
    if conn is None:
        raise ValueError("supplement_intake resolver requires a DuckDB connection; got None")

    anchor = request.anchor_ts
    anchor_naive = _to_naive_utc(anchor)
    window_days = _resolve_window_days(request)
    window_start = anchor_naive - timedelta(days=window_days)

    rows = conn.execute(_QUERY, [anchor_naive, window_start]).fetchall()

    logged_days: set[Any] = set()
    any_utc_fallback = False
    latest_logged_at: datetime | None = None
    for ts_utc, local_tz, product_label, ingredient_label in rows:
        if not matches_supplement(matcher, product_label, ingredient_label):
            continue
        day, used_utc_fallback = local_calendar_day(ts_utc, local_tz)
        any_utc_fallback = any_utc_fallback or used_utc_fallback
        logged_days.add(day)
        if latest_logged_at is None or ts_utc > latest_logged_at:
            latest_logged_at = ts_utc

    if not logged_days:
        return ResolvedInput(
            domain=_DOMAIN,
            required_key=matcher,
            anchor_ts=anchor,
            usable=False,
            absence_reason="missing",
            message=(
                f"no supplement intake matching {matcher!r} logged in the {window_days}-day "
                f"window ending {anchor_naive.isoformat()} — honest refusal rather than "
                "substituting another domain's data"
            ),
            payload={
                "matcher": matcher,
                "window_days": window_days,
                "freshness_state": FreshnessState.UNAVAILABLE.value,
            },
        )

    day_basis = DAY_BASIS_UTC if any_utc_fallback else DAY_BASIS_LOCAL
    ordered_days = sorted(logged_days)

    return ResolvedInput(
        domain=_DOMAIN,
        required_key=matcher,
        anchor_ts=anchor,
        usable=True,
        payload={
            "matcher": matcher,
            "window_days": window_days,
            "logged_days": [day.isoformat() for day in ordered_days],
            "logged_day_count": len(ordered_days),
            "window_day_count": window_days,
            "latest_logged_at": latest_logged_at,
            "freshness_state": FreshnessState.CURRENT.value,
            "day_basis": day_basis,
        },
    )


__all__ = ["matches_supplement", "resolve_supplement_intake"]
