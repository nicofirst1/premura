"""Public-surface tests for the Stage 2 input-resolution seam.

These tests lock the resolver surface and registry shape through public
engine imports only. They cover (a) the closed set of declared semantic
domains, (b) honest refusal for declared-but-unregistered domains, and
(c) registry-driven dispatch.

The tests do NOT import :mod:`premura.engine._resolution`,
:mod:`premura.engine._registry`, or any ``premura.engine.views.*`` private
module directly — that is the whole point of the seam.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anchor_ts() -> datetime:
    """A fixed timezone-aware anchor used across the seam tests."""
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def clean_resolvers() -> Iterator[None]:
    """Snapshot and restore ``RESOLVERS`` around tests that register a fake.

    The resolver registry is process-global by design (it mirrors the signal
    registry). Tests that mutate it must clean up so they do not leak state
    into sibling tests. Snapshotting the dict contents preserves any
    legitimately-loaded built-in resolvers (currently none in WP01, but
    forward-compatible).
    """
    from premura.engine import RESOLVERS

    snapshot = dict(RESOLVERS)
    try:
        yield
    finally:
        RESOLVERS.clear()
        RESOLVERS.update(snapshot)


# ---------------------------------------------------------------------------
# 1. SEMANTIC_DOMAINS shape
# ---------------------------------------------------------------------------


def test_semantic_domains_is_the_closed_mission_set() -> None:
    """The four declared semantic domains match the contract YAML exactly."""
    from premura.engine import SEMANTIC_DOMAINS

    assert SEMANTIC_DOMAINS == frozenset(
        {
            "observation_history",
            "profile_context",
            "nutrition_intake",
            "supplement_intake",
        }
    )


def test_semantic_domains_is_immutable() -> None:
    """``SEMANTIC_DOMAINS`` is a frozenset so callers cannot mutate the set."""
    from premura.engine import SEMANTIC_DOMAINS

    assert isinstance(SEMANTIC_DOMAINS, frozenset)


# ---------------------------------------------------------------------------
# 2. DependencyDeclaration / ResolutionRequest / ResolvedInput shape
# ---------------------------------------------------------------------------


def test_dependency_declaration_constructs_with_required_fields(
    anchor_ts: datetime,
) -> None:
    from premura.engine import DependencyDeclaration, ResolutionRequest

    dep = DependencyDeclaration(
        consumer_name="bmi",
        depends_on_domain="profile_context",
        required_key="profile:standing_height_cm",
        failure_mode="explicit_missing_input",
    )
    request = ResolutionRequest(anchor_ts=anchor_ts, dependency=dep)

    assert request.anchor_ts == anchor_ts
    assert request.dependency.consumer_name == "bmi"
    assert request.dependency.depends_on_domain == "profile_context"
    assert request.dependency.required_key == "profile:standing_height_cm"
    assert request.dependency.failure_mode == "explicit_missing_input"


def test_resolved_input_carries_optional_payload(anchor_ts: datetime) -> None:
    """``ResolvedInput.payload`` lets resolvers carry domain-specific fields.

    The contract promises one declaration surface and one resolution protocol,
    not one universal payload shape. Locking ``payload`` as ``None`` by
    default keeps the unsupported-domain outcome small while leaving room for
    observation- or profile-specific fields when WP02 lands.
    """
    from premura.engine import ResolvedInput

    out = ResolvedInput(
        domain="observation_history",
        required_key="vital:body_weight",
        anchor_ts=anchor_ts,
        usable=True,
        payload={"resolved_value": 72.0, "freshness_state": "current"},
    )
    assert out.payload is not None
    assert out.payload["resolved_value"] == 72.0


# ---------------------------------------------------------------------------
# 3. Unsupported-domain fall-through for every declared semantic domain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain",
    [
        "nutrition_intake",
        "supplement_intake",
    ],
)
def test_undeclared_resolver_domains_fall_through_to_unsupported(
    domain: str,
    anchor_ts: datetime,
) -> None:
    """Domains that are declared in ``SEMANTIC_DOMAINS`` but have no registered
    resolver yet must resolve to the explicit ``unsupported_domain`` outcome.

    This is FR-007 — honest refusal for declared-but-not-yet-resolvable
    domains. It locks the no-silent-coercion guarantee that WP02's new
    resolvers cannot weaken.
    """
    from premura.engine import (
        DependencyDeclaration,
        ResolutionRequest,
        resolve_dependency,
    )

    dep = DependencyDeclaration(
        consumer_name="proof_consumer",
        depends_on_domain=domain,
        required_key=f"{domain}:probe",
        failure_mode="explicit_missing_input",
    )
    request = ResolutionRequest(anchor_ts=anchor_ts, dependency=dep)

    out = resolve_dependency(conn=None, request=request)

    assert out.usable is False
    assert out.absence_reason == "unsupported_domain"
    assert out.domain == domain
    assert out.required_key == f"{domain}:probe"
    assert out.anchor_ts == anchor_ts
    assert out.message is not None and domain in out.message


def test_registered_resolver_domains_dispatch_through_registry() -> None:
    """The mission's two shipped resolvers register themselves at lazy-load.

    This is the structural complement to the unsupported-domain test above:
    observation_history and profile_context must show up in RESOLVERS once
    the lazy loader has run. Behavioral verification lives in
    ``tests/test_engine_resolvers.py``.
    """
    from premura.engine import (
        RESOLVERS,
        DependencyDeclaration,
        ResolutionRequest,
        resolve_dependency,
    )

    # Trigger the lazy loader by issuing a request against a declared-but-
    # unresolved domain. The loader fires before dispatch, so this registers
    # observation_history and profile_context without needing a DB connection
    # — nutrition_intake has no resolver and returns ``unsupported_domain``.
    resolve_dependency(
        conn=None,
        request=ResolutionRequest(
            anchor_ts=datetime(2026, 1, 1, tzinfo=UTC),
            dependency=DependencyDeclaration(
                consumer_name="probe",
                depends_on_domain="nutrition_intake",
                required_key="probe",
                failure_mode="explicit_missing_input",
            ),
        ),
    )

    assert "observation_history" in RESOLVERS
    assert "profile_context" in RESOLVERS


# ---------------------------------------------------------------------------
# 4. Registry-driven dispatch (the structural correction)
# ---------------------------------------------------------------------------


def test_registered_resolver_handles_dispatch_for_its_domain(
    anchor_ts: datetime,
    clean_resolvers: None,
) -> None:
    """Registering a resolver via the public decorator routes dispatch to it.

    The point of this test is to prove the registry is the dispatch source —
    not an ``if``/``elif`` chain inside ``resolve_dependency``. The fake
    resolver returns a sentinel payload; if dispatch were hardcoded, the
    sentinel would never appear.
    """
    from premura.engine import (
        DependencyDeclaration,
        ResolutionRequest,
        ResolvedInput,
        resolve_dependency,
        resolver,
    )

    sentinel_payload: dict[str, Any] = {"sentinel": "from-fake-resolver"}

    @resolver(domain="observation_history")
    def _fake_observation_resolver(
        conn: Any,
        request: ResolutionRequest,
    ) -> ResolvedInput:
        return ResolvedInput(
            domain="observation_history",
            required_key=request.dependency.required_key,
            anchor_ts=request.anchor_ts,
            usable=True,
            payload=sentinel_payload,
        )

    dep = DependencyDeclaration(
        consumer_name="proof_consumer",
        depends_on_domain="observation_history",
        required_key="vital:body_weight",
        failure_mode="explicit_missing_input",
    )
    request = ResolutionRequest(anchor_ts=anchor_ts, dependency=dep)

    out = resolve_dependency(conn=None, request=request)

    assert out.usable is True
    assert out.domain == "observation_history"
    assert out.required_key == "vital:body_weight"
    assert out.payload is sentinel_payload


def test_resolver_removal_restores_unsupported_domain_outcome(
    anchor_ts: datetime,
    clean_resolvers: None,
) -> None:
    """Removing the resolver brings back the ``unsupported_domain`` outcome.

    This is the proof that dispatch is registry-driven both ways: present
    entries route to the resolver, absent entries fall through honestly.
    """
    from premura.engine import (
        RESOLVERS,
        DependencyDeclaration,
        ResolutionRequest,
        ResolvedInput,
        resolve_dependency,
        resolver,
    )

    @resolver(domain="profile_context")
    def _fake_profile_resolver(
        conn: Any,
        request: ResolutionRequest,
    ) -> ResolvedInput:
        return ResolvedInput(
            domain="profile_context",
            required_key=request.dependency.required_key,
            anchor_ts=request.anchor_ts,
            usable=True,
        )

    dep = DependencyDeclaration(
        consumer_name="proof_consumer",
        depends_on_domain="profile_context",
        required_key="profile:standing_height_cm",
        failure_mode="explicit_missing_input",
    )
    request = ResolutionRequest(anchor_ts=anchor_ts, dependency=dep)

    # While registered: the fake resolver wins.
    out_registered = resolve_dependency(conn=None, request=request)
    assert out_registered.usable is True

    # Remove the entry and confirm the fall-through outcome returns.
    del RESOLVERS["profile_context"]
    out_removed = resolve_dependency(conn=None, request=request)
    assert out_removed.usable is False
    assert out_removed.absence_reason == "unsupported_domain"


# ---------------------------------------------------------------------------
# 5. Unknown semantic-domain strings raise ValueError
# ---------------------------------------------------------------------------


def test_unknown_semantic_domain_raises_value_error(anchor_ts: datetime) -> None:
    """A typo'd or speculative domain string is a programming error.

    The seam refuses to treat it as a missing-data condition because doing so
    would hide consumer-side mistakes (e.g. a future BMI implementation typo'd
    the domain). Raising forces the caller to fix the declaration.
    """
    from premura.engine import (
        DependencyDeclaration,
        ResolutionRequest,
        resolve_dependency,
    )

    dep = DependencyDeclaration(
        consumer_name="proof_consumer",
        depends_on_domain="made_up_domain",
        required_key="anything",
        failure_mode="explicit_missing_input",
    )
    request = ResolutionRequest(anchor_ts=anchor_ts, dependency=dep)

    with pytest.raises(ValueError, match="made_up_domain"):
        resolve_dependency(conn=None, request=request)


def test_resolver_decorator_rejects_unknown_domain() -> None:
    """The public ``@resolver`` decorator validates its ``domain`` argument.

    Registering against an unknown domain at decoration time is a
    programming error and must fail loudly, not silently grow the registry
    surface.
    """
    from premura.engine import ResolutionRequest, ResolvedInput, resolver

    with pytest.raises(ValueError, match="made_up_domain"):

        @resolver(domain="made_up_domain")
        def _bad(
            conn: Any,
            request: ResolutionRequest,
        ) -> ResolvedInput:  # pragma: no cover - never registered
            raise AssertionError("decorator must reject before this body runs")


# ---------------------------------------------------------------------------
# 6. Determinism and identity of the public surface
# ---------------------------------------------------------------------------


def test_resolvers_dict_identity_is_stable_across_imports() -> None:
    """Re-importing ``premura.engine`` returns the same ``RESOLVERS`` object.

    The signal registry is process-global by convention; the resolver
    registry must follow suit so a resolver registered in one place is
    visible everywhere else.
    """
    import premura.engine as engine_first
    import premura.engine as engine_second

    assert engine_first.RESOLVERS is engine_second.RESOLVERS


def test_repeated_resolution_yields_equal_results(anchor_ts: datetime) -> None:
    """Two identical requests produce equal :class:`ResolvedInput` instances.

    Locks the deterministic-public-surface promise (NFR-002 in the spec):
    repeated runs with unchanged inputs produce the same outcome.
    """
    from premura.engine import (
        DependencyDeclaration,
        ResolutionRequest,
        resolve_dependency,
    )

    dep = DependencyDeclaration(
        consumer_name="proof_consumer",
        depends_on_domain="nutrition_intake",
        required_key="nutrition:calories",
        failure_mode="explicit_missing_input",
    )
    request = ResolutionRequest(anchor_ts=anchor_ts, dependency=dep)

    first = resolve_dependency(conn=None, request=request)
    second = resolve_dependency(conn=None, request=request)
    assert first == second
