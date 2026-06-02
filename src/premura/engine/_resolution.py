"""Stage 2 input-resolution seam.

This module is the **structural correction** for the Stage 2 abstraction unit.
It is NOT a universal prepared-series layer; it is a domain-aware seam that
resolves a *declared dependency* against a *semantic domain* as of an anchor
time.

Public callers should always reach this surface through ``premura.engine``::

    from premura.engine import (
        SEMANTIC_DOMAINS,
        DependencyDeclaration,
        ResolutionRequest,
        ResolvedInput,
        resolve_dependency,
    )

The seam ships four valid semantic domains. Two now have concrete resolvers:
``observation_history`` and ``profile_context``. The other two
(``nutrition_intake`` and ``supplement_intake``) remain valid declaration
targets and intentionally return ``unsupported_domain`` until later parser
missions ship real rows.

Key design rules (do not relax without a new mission):

* No silent coercion across domains. A declaration against ``profile_context``
  must never be satisfied by reading an observation-history row.
* No filesystem scanning, no entry points, no plugin loader. The registry
  surface is static in-tree.
* The protocol is ``(conn, request) -> ResolvedInput``. Resolvers may carry
  domain-specific fields in ``ResolvedInput.payload`` (e.g. ``resolved_value``,
  ``observed_at``, ``freshness_state``, ``effective_start_utc``); the contract
  promises one declaration surface and one resolution protocol, not one
  universal resolved payload shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from ._registry import RESOLVERS

if TYPE_CHECKING:
    import duckdb


SEMANTIC_DOMAINS: frozenset[str] = frozenset(
    {
        "observation_history",
        "profile_context",
        "nutrition_intake",
        "supplement_intake",
    }
)
"""The four valid semantic domains a :class:`DependencyDeclaration` may target.

Two are supported by concrete resolvers (after WP02 lands):
``observation_history`` and ``profile_context``. The other two
(``nutrition_intake``, ``supplement_intake``) are valid declaration targets but
resolve to an explicit unresolved outcome until later missions ship real
parser-produced rows. The set is intentionally closed in this mission;
expanding it requires a new mission per the spec's domain-vs-shape rubric.
"""


UNSUPPORTED_DOMAIN_REASON: str = "unsupported_domain"
"""``absence_reason`` value returned when a declared dependency targets a
valid semantic domain that has no registered resolver yet."""


@dataclass(frozen=True)
class DependencyDeclaration:
    """One declared dependency from a Stage 2 consumer.

    Fields mirror ``contracts/input-resolution-surface.yaml``:

    * ``consumer_name`` — the Stage 2 answer / tool that owns the dependency
      (e.g. ``"bmi"``).
    * ``depends_on_domain`` — must be one of :data:`SEMANTIC_DOMAINS`.
    * ``required_key`` — the exact metric or attribute key required
      (e.g. ``"vital:body_weight"`` or ``"profile:standing_height_cm"``).
    * ``failure_mode`` — how the consumer behaves when the dependency is
      missing, stale, partial, or unsupported. Kept as a free-form string so
      the consumer side (WP03 BMI) can define its own honest-refusal vocabulary
      without churning this contract.
    """

    consumer_name: str
    depends_on_domain: str
    required_key: str
    failure_mode: str


@dataclass(frozen=True)
class ResolutionRequest:
    """One resolution request: an anchor time plus the declared dependency.

    ``anchor_ts`` is the time reference the resolver uses to pick the
    appropriate slice of data. The seam itself never assumes "now"; the caller
    must provide an explicit timezone-aware datetime.
    """

    anchor_ts: datetime
    dependency: DependencyDeclaration


@dataclass(frozen=True)
class ResolvedInput:
    """One resolution outcome.

    Carries a small, fixed core (``domain`` / ``required_key`` / ``anchor_ts``
    / ``usable``) and an optional ``payload`` mapping for domain-specific
    fields. This shape deliberately does NOT promise a universal resolved
    payload: ``payload`` is the seam where a future observation resolver can
    return ``resolved_value`` + ``observed_at`` + ``freshness_state``, a
    profile resolver can return ``resolved_value`` + ``effective_start_utc`` +
    ``effective_end_utc`` + ``source_kind``, and an unsupported-domain outcome
    can return nothing.

    ``absence_reason`` and ``message`` are populated whenever ``usable`` is
    False so callers can surface honest refusal context. ``usable=False`` with
    ``absence_reason=None`` is allowed (resolvers may choose to omit it), but
    discouraged — prefer an explicit reason.
    """

    domain: str
    required_key: str
    anchor_ts: datetime
    usable: bool
    absence_reason: str | None = None
    message: str | None = None
    payload: Mapping[str, Any] | None = field(default=None)


class Resolver(Protocol):
    """Callable contract every registered resolver must satisfy.

    A resolver receives the live DuckDB connection (shipped data lives in the
    warehouse) and a :class:`ResolutionRequest`. It must return a
    :class:`ResolvedInput` whose ``domain`` matches the requested domain.
    Resolvers must not raise for ordinary missing-data conditions; they must
    return a ``usable=False`` ``ResolvedInput`` with an explicit
    ``absence_reason`` instead. Raising is reserved for programming errors
    (e.g. the resolver was wired against the wrong domain).
    """

    def __call__(
        self,
        conn: duckdb.DuckDBPyConnection | None,
        request: ResolutionRequest,
    ) -> ResolvedInput: ...


def resolve_dependency(
    conn: duckdb.DuckDBPyConnection | None,
    request: ResolutionRequest,
) -> ResolvedInput:
    """Resolve one declared dependency through the static resolver registry.

    Dispatch is registry-driven, not an ``if``/``elif`` chain:

    1. Validate ``request.dependency.depends_on_domain`` is in
       :data:`SEMANTIC_DOMAINS`. Unknown domains raise :class:`ValueError`
       because they indicate a programming error in the consumer, not a
       missing-data condition.
    2. Look up the resolver in :data:`premura.engine._registry.RESOLVERS`.
       Absence here is the **expected** state for valid-but-not-yet-supported
       domains (``nutrition_intake``, ``supplement_intake`` in this mission,
       and ``observation_history`` / ``profile_context`` until WP02 lands):
       return a ``usable=False`` :class:`ResolvedInput` with
       ``absence_reason="unsupported_domain"``.
    3. Otherwise delegate to the registered resolver and return its result.

    Note: the public engine surface wraps this entrypoint with a lazy
    built-in-resolver loader so callers always import from
    :mod:`premura.engine`, not from this private module.
    """
    domain = request.dependency.depends_on_domain
    if domain not in SEMANTIC_DOMAINS:
        raise ValueError(
            f"unknown semantic domain {domain!r}; must be one of {sorted(SEMANTIC_DOMAINS)}"
        )

    fn = RESOLVERS.get(domain)
    if fn is None:
        return ResolvedInput(
            domain=domain,
            required_key=request.dependency.required_key,
            anchor_ts=request.anchor_ts,
            usable=False,
            absence_reason=UNSUPPORTED_DOMAIN_REASON,
            message=(
                f"no resolver registered for semantic domain {domain!r}; "
                "declaration is valid but not yet resolvable in this mission"
            ),
        )

    return fn(conn, request)
