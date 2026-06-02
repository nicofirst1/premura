"""Observation-history resolver.

Resolves declared observation dependencies against ``hp.dim_metric`` policy and
``hp.fact_measurement`` / ``hp.fact_interval`` data through the shared Stage 2
``_query`` helpers. Domain meaning: an observation is a measurement with a
timestamp and a source — never a profile declaration.

The resolver delegates freshness and policy logic to
:func:`premura.engine._query.latest_usable_value`, so there is exactly one
authoritative interpretation of ``validity_window`` and
``missing_data_policy`` in Stage 2. Every outcome (``current``, ``stale``,
``missing``, ``unknown_metric``) is explicit and returned as a
:class:`ResolvedInput`; the resolver never raises for ordinary missing-data
conditions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .._query import latest_usable_value, load_metric_policy
from .._registry import resolver
from .._resolution import ResolutionRequest, ResolvedInput
from .._results import FreshnessState

if TYPE_CHECKING:
    import duckdb


_DOMAIN = "observation_history"


def _to_naive_utc(value: datetime) -> datetime:
    """Convert a (possibly tz-aware) datetime to naive UTC.

    The Stage 2 warehouse stores DuckDB ``TIMESTAMP`` columns as naive UTC, and
    :mod:`premura.engine._query` reasons in naive UTC throughout. The resolver
    accepts whatever the caller passes for ``anchor_ts``: a tz-aware datetime
    (the seam's recommended shape) is normalized here; a naive datetime is
    assumed to already be UTC and passed through unchanged.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


@resolver(domain=_DOMAIN)
def resolve_observation(
    conn: duckdb.DuckDBPyConnection | None,
    request: ResolutionRequest,
) -> ResolvedInput:
    """Resolve one observation-history dependency as of ``request.anchor_ts``.

    ``request.dependency.required_key`` is interpreted as a ``metric_id``
    registered in ``hp.dim_metric`` (e.g. ``"weight"``, ``"resting_hr"``).

    Outcomes:

    * Unknown metric → ``usable=False, absence_reason="unknown_metric"``.
    * No observation rows → ``usable=False, absence_reason="missing"``.
    * Newest observation older than the metric's validity window →
      ``usable=False, absence_reason="stale"``; the observed value is still
      carried in the payload so callers can surface what was found and rejected.
    * Otherwise → ``usable=True`` with ``resolved_value``, ``observed_at``,
      ``freshness_state="current"`` and ``unit`` in the payload.

    Raises :class:`ValueError` only on programming errors (non-string key or
    missing connection), never on ordinary missing data.
    """
    metric_id = request.dependency.required_key
    if not isinstance(metric_id, str) or not metric_id:
        raise ValueError(
            f"observation_history required_key must be a non-empty metric_id; got {metric_id!r}"
        )
    if conn is None:
        raise ValueError("observation_history resolver requires a DuckDB connection; got None")

    anchor = request.anchor_ts
    anchor_naive = _to_naive_utc(anchor)

    policy = load_metric_policy(conn, metric_id)
    if policy is None:
        return ResolvedInput(
            domain=_DOMAIN,
            required_key=metric_id,
            anchor_ts=anchor,
            usable=False,
            absence_reason="unknown_metric",
            message=(
                f"metric {metric_id!r} is not registered in hp.dim_metric; "
                "declaration is structurally valid but no policy exists to "
                "judge freshness"
            ),
        )

    latest = latest_usable_value(conn, policy, now=anchor_naive)
    state = latest.freshness_state
    obs = latest.observation

    if state is FreshnessState.CURRENT and obs is not None:
        return ResolvedInput(
            domain=_DOMAIN,
            required_key=metric_id,
            anchor_ts=anchor,
            usable=True,
            payload={
                "resolved_value": obs.value,
                "observed_at": obs.ts,
                "freshness_state": FreshnessState.CURRENT.value,
                "unit": policy.unit,
            },
        )

    if state is FreshnessState.STALE and obs is not None:
        age = latest.age
        return ResolvedInput(
            domain=_DOMAIN,
            required_key=metric_id,
            anchor_ts=anchor,
            usable=False,
            absence_reason="stale",
            message=(
                f"latest {metric_id!r} observation is older than the validity "
                f"window (age={age}); honest refusal rather than silent reuse"
            ),
            payload={
                "resolved_value": obs.value,
                "observed_at": obs.ts,
                "freshness_state": FreshnessState.STALE.value,
                "unit": policy.unit,
            },
        )

    # UNAVAILABLE — no usable observation row.
    return ResolvedInput(
        domain=_DOMAIN,
        required_key=metric_id,
        anchor_ts=anchor,
        usable=False,
        absence_reason="missing",
        message=f"no {metric_id!r} observation has been recorded yet",
        payload={"freshness_state": FreshnessState.UNAVAILABLE.value},
    )


__all__ = ["resolve_observation"]
