"""Profile-as-of resolver.

Resolves declared profile dependencies against ``hp.profile_context_assertion``
with latest-valid-as-of-anchor semantics. The contract: meaning and time decide
which row wins, never opportunistic substitution from another domain.

Key guarantees encoded here:

* Resolution is **as-of** ``request.anchor_ts``, not "latest open row." An
  assertion that closed before the anchor or that opens after the anchor is
  invisible to the resolver.
* There is **no hidden fallback** into observation history. A declared profile
  dependency whose attribute key has no matching assertion returns ``missing``,
  even when a same-name observation row happens to exist.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .._registry import resolver
from .._resolution import ResolutionRequest, ResolvedInput

if TYPE_CHECKING:
    import duckdb


_DOMAIN = "profile_context"

# Resolve the latest assertion that was *valid* at the anchor time. The
# ``effective_end_utc IS NULL OR ? < effective_end_utc`` clause keeps an
# assertion alive only until (but not including) the moment it was closed; the
# DESC ordering then picks the most-recent start (with ``assertion_id`` as a
# deterministic tiebreaker for the rare same-start case).
_AS_OF_QUERY = """
SELECT assertion_id, value_text, value_num, value_date, unit,
       effective_start_utc, effective_end_utc, source_kind
FROM hp.profile_context_assertion
WHERE attribute_key = ?
  AND effective_start_utc <= ?
  AND (effective_end_utc IS NULL OR ? < effective_end_utc)
ORDER BY effective_start_utc DESC, assertion_id DESC
LIMIT 1
"""


def _to_naive_utc(value: datetime) -> datetime:
    """Convert a (possibly tz-aware) datetime to naive UTC.

    ``hp.profile_context_assertion`` timestamps are DuckDB ``TIMESTAMP`` (naive
    UTC), so the anchor must be normalized before it can be compared. A naive
    datetime is assumed to already be UTC and passed through unchanged.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _pick_resolved_value(
    value_num: float | None,
    value_text: str | None,
    value_date: object,
) -> object:
    """Return whichever typed slot the assertion populated.

    The store boundary enforces that exactly one slot is non-null per assertion
    (see :func:`premura.store.profile_intake._typed_slots`). Iterating numeric →
    text → date matches that mapping and yields the original declared value.
    """
    if value_num is not None:
        return value_num
    if value_text is not None:
        return value_text
    return value_date


@resolver(domain=_DOMAIN)
def resolve_profile(
    conn: duckdb.DuckDBPyConnection | None,
    request: ResolutionRequest,
) -> ResolvedInput:
    """Resolve one profile-context dependency as of ``request.anchor_ts``.

    ``request.dependency.required_key`` is interpreted as a profile
    ``attribute_key`` (e.g. ``"standing_height_cm"``).

    Outcomes:

    * No assertion valid at the anchor → ``usable=False,
      absence_reason="missing"``. **No fallback** into observation history is
      attempted — that is the central no-hidden-fallback guarantee.
    * Otherwise → ``usable=True`` with payload fields ``resolved_value``,
      ``unit``, ``effective_start_utc``, ``effective_end_utc`` (may be ``None``
      for an open assertion), and ``source_kind``.

    Raises :class:`ValueError` only on programming errors (non-string key or
    missing connection), never on ordinary missing data.
    """
    attribute_key = request.dependency.required_key
    if not isinstance(attribute_key, str) or not attribute_key:
        raise ValueError(
            f"profile_context required_key must be a non-empty attribute_key; "
            f"got {attribute_key!r}"
        )
    if conn is None:
        raise ValueError(
            "profile_context resolver requires a DuckDB connection; got None"
        )

    anchor = request.anchor_ts
    anchor_naive = _to_naive_utc(anchor)

    row = conn.execute(
        _AS_OF_QUERY,
        [attribute_key, anchor_naive, anchor_naive],
    ).fetchone()

    if row is None:
        return ResolvedInput(
            domain=_DOMAIN,
            required_key=attribute_key,
            anchor_ts=anchor,
            usable=False,
            absence_reason="missing",
            message=(
                f"no profile assertion for {attribute_key!r} as of "
                f"{anchor_naive.isoformat()} — honest refusal rather than "
                "substituting a same-named observation"
            ),
        )

    (
        _assertion_id,
        value_text,
        value_num,
        value_date,
        unit,
        effective_start_utc,
        effective_end_utc,
        source_kind,
    ) = row

    resolved_value = _pick_resolved_value(value_num, value_text, value_date)

    return ResolvedInput(
        domain=_DOMAIN,
        required_key=attribute_key,
        anchor_ts=anchor,
        usable=True,
        payload={
            "resolved_value": resolved_value,
            "unit": unit,
            "effective_start_utc": effective_start_utc,
            "effective_end_utc": effective_end_utc,
            "source_kind": source_kind,
        },
    )


__all__ = ["resolve_profile"]
