"""Behavioral tests for the WP03 intake resolvers + parameterized compute seam.

Every resolver test drives behavior through the *public* engine seam
(``from premura.engine import resolve_dependency``) — there are no imports of
``premura.engine.views.nutrition_intake`` / ``...supplement_intake``. The lazy
loader inside :func:`premura.engine.resolve_dependency` is what binds the two
intake resolvers to those modules via the ``@resolver(domain=...)`` registry, so
these tests prove the binding works end-to-end (T013, registration-as-discovery).

Intake rows are seeded directly via ``persist_intake_batch`` (the already-shipped
store path); this WP does not depend on WP01/WP02. Tests assert on the resolved
payload + honest-refusal envelope, never on resolver internals.

What is locked here:

* FR-001/FR-002: both domains resolve usable rows to the generic payload and
  refuse honestly (``usable=False`` + explicit ``absence_reason``) when none.
* NFR-003 (T014): a same-named *observation* row never satisfies an intake
  dependency — the resolvers read intake tables only, no hidden fallback.
* NFR-005 (T015): the shared ``resolve_dependency`` path has no per-domain branch
  for the two intake domains; both reach their resolver purely via the registry.
* NFR-006 (T016): a row whose ``local_tz`` puts it on a different local day than
  its UTC date resolves with ``day_basis == "local_calendar_day"`` and the local
  day in its day set.
* T031: a parameterized in-test signal receives params through ``compute(...)``;
  an existing zero-arg signal still computes unchanged.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)
from premura.store.profile_intake import persist_intake_batch

# NOTE: ``premura.engine`` is intentionally NOT imported at module top. Sibling
# tests (``test_engine_contract.py``) purge ``premura.engine*`` from
# ``sys.modules`` and re-import to simulate a fresh process; a module-level
# binding here would capture the pre-purge ``compute`` / ``REGISTRY`` and then
# diverge from the freshly-imported engine module the public seam rebuilds.
# Every test reaches the engine surface through :func:`_engine` so it always
# resolves against the currently-active module (mirrors test_engine_resolvers).


def _engine() -> Any:
    """Return the current ``premura.engine`` module (purge-safe)."""
    import premura.engine as engine_pkg

    return engine_pkg


def resolve_dependency(conn: Any, request: Any) -> Any:
    return _engine().resolve_dependency(conn, request)


def compute(spec_name: str, conn: Any, **kwargs: Any) -> Any:
    return _engine().compute(spec_name, conn, **kwargs)


def _dependency_declaration(**kwargs: Any) -> Any:
    return _engine().DependencyDeclaration(**kwargs)


def _resolution_request(**kwargs: Any) -> Any:
    return _engine().ResolutionRequest(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures and seeding helpers
# ---------------------------------------------------------------------------

_SOURCE_ID = "intake:test"
_SOURCE_KIND = "reference_intake"


@pytest.fixture
def anchor_ts() -> datetime:
    """A fixed timezone-aware anchor used across the resolver tests."""
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


def _descriptor() -> SourceDescriptor:
    return SourceDescriptor(source_id=_SOURCE_ID, source_kind=_SOURCE_KIND)


def _seed_nutrition(
    conn: Any,
    *,
    events: list[NutritionIntakeInput],
) -> None:
    batch = IntakeBatch(
        source_descriptors={_SOURCE_ID: _descriptor()},
        nutrition_events=events,
    )
    persist_intake_batch(conn, batch)


def _seed_supplement(
    conn: Any,
    *,
    events: list[SupplementIntakeInput],
) -> None:
    batch = IntakeBatch(
        source_descriptors={_SOURCE_ID: _descriptor()},
        supplement_events=events,
    )
    persist_intake_batch(conn, batch)


def _nutrition_event(
    *,
    start_utc: datetime,
    dedupe_key: str,
    quantity_key: str = "energy",
    value_num: float = 500.0,
    local_tz: str | None = None,
    subject: str = "event",
) -> NutritionIntakeInput:
    """Build one nutrition event carrying a single quantity.

    ``subject="event"`` attaches the quantity to the whole event; ``"item"``
    nests it under a single item so item-level quantities are exercised too.
    """
    if subject == "event":
        return NutritionIntakeInput(
            source_id=_SOURCE_ID,
            source_kind=_SOURCE_KIND,
            start_utc=start_utc,
            dedupe_key=dedupe_key,
            local_tz=local_tz,
            event_quantities=[
                NutritionQuantityInput(
                    quantity_key=quantity_key, value_num=value_num, subject="event"
                )
            ],
        )
    return NutritionIntakeInput(
        source_id=_SOURCE_ID,
        source_kind=_SOURCE_KIND,
        start_utc=start_utc,
        dedupe_key=dedupe_key,
        local_tz=local_tz,
        items=[
            NutritionItemInput(
                item_label="oats",
                quantities=[
                    NutritionQuantityInput(
                        quantity_key=quantity_key, value_num=value_num, subject="item"
                    )
                ],
            )
        ],
    )


def _supplement_event(
    *,
    ts_utc: datetime,
    dedupe_key: str,
    product_label: str | None = "Acme Vitamin D3",
    ingredient_label: str | None = "cholecalciferol",
    local_tz: str | None = None,
    amount_text: str | None = "1 capsule",
    amount_num: float | None = None,
) -> SupplementIntakeInput:
    return SupplementIntakeInput(
        source_id=_SOURCE_ID,
        source_kind=_SOURCE_KIND,
        ts_utc=ts_utc,
        dedupe_key=dedupe_key,
        local_tz=local_tz,
        items=[
            SupplementItemInput(
                product_label=product_label,
                ingredient_label=ingredient_label,
                doses=[SupplementDoseInput(amount_num=amount_num, amount_text=amount_text)],
            )
        ],
    )


def _seed_same_named_observation(
    conn: Any,
    *,
    metric_id: str,
    value_num: float,
    ts: datetime,
    unit: str = "kcal",
) -> None:
    """Register a metric + insert one observation row sharing an intake key.

    This is the trap NFR-003 guards against: an observation in
    ``hp.fact_measurement`` whose ``metric_id`` collides with an intake key. The
    intake resolvers must read intake tables only and never satisfy a declared
    intake dependency from this row.
    """
    conn.execute(
        """
        INSERT INTO hp.dim_metric (metric_id, display_name, canonical_unit, value_kind)
        VALUES (?, ?, ?, 'instantaneous')
        ON CONFLICT (metric_id) DO NOTHING
        """,
        [metric_id, metric_id, unit],
    )
    conn.execute(
        """
        INSERT INTO hp.dim_source (source_id, source_kind, first_seen, last_seen)
        VALUES (?, 'wearable', now(), now())
        ON CONFLICT (source_id) DO NOTHING
        """,
        ["wearable:obs"],
    )
    conn.execute(
        """
        INSERT INTO hp.fact_measurement
            (ts_utc, metric_id, value_num, unit, source_id, source_uuid, dedupe_key)
        VALUES (?, ?, ?, ?, 'wearable:obs', 'u1', ?)
        """,
        [ts, metric_id, value_num, unit, f"obs-{metric_id}-1"],
    )


def _nutrition_request(
    *,
    quantity_key: str,
    anchor_ts: datetime,
    window_days: int | None = None,
) -> Any:
    failure_mode = "" if window_days is None else f"window_days={window_days}"
    return _resolution_request(
        anchor_ts=anchor_ts,
        dependency=_dependency_declaration(
            consumer_name="nutrition_intake_trend",
            depends_on_domain="nutrition_intake",
            required_key=quantity_key,
            failure_mode=failure_mode,
        ),
    )


def _supplement_request(
    *,
    matcher: str,
    anchor_ts: datetime,
    window_days: int | None = None,
) -> Any:
    failure_mode = "" if window_days is None else f"window_days={window_days}"
    return _resolution_request(
        anchor_ts=anchor_ts,
        dependency=_dependency_declaration(
            consumer_name="supplement_intake_adherence",
            depends_on_domain="supplement_intake",
            required_key=matcher,
            failure_mode=failure_mode,
        ),
    )


# ---------------------------------------------------------------------------
# FR-001: usable resolution to the generic payload
# ---------------------------------------------------------------------------


def test_nutrition_intake_resolves_usable_payload(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A logged nutrition quantity resolves to the generic daily-points payload."""
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=anchor_ts.replace(tzinfo=None) - timedelta(days=2),
                dedupe_key="n1",
                value_num=500.0,
            ),
            _nutrition_event(
                start_utc=anchor_ts.replace(tzinfo=None) - timedelta(days=1),
                dedupe_key="n2",
                value_num=700.0,
            ),
        ],
    )

    resolved = resolve_dependency(
        empty_warehouse, _nutrition_request(quantity_key="energy", anchor_ts=anchor_ts)
    )

    assert resolved.usable is True
    assert resolved.domain == "nutrition_intake"
    payload = resolved.payload
    assert payload is not None
    assert payload["matched_key"] == "energy"
    assert payload["days_with_data"] == 2
    assert payload["latest_logged_at"] is not None
    # Generic payload only — the resolver must not pre-compute a verdict.
    assert "trend_direction" not in payload
    assert "day_basis" in payload
    # Ordered daily points, never imputed: exactly two visible days.
    assert len(payload["points"]) == 2


def test_supplement_intake_resolves_usable_payload(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A logged supplement resolves to the generic logged-days payload."""
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(
                ts_utc=anchor_ts.replace(tzinfo=None) - timedelta(days=3), dedupe_key="s1"
            ),
            _supplement_event(
                ts_utc=anchor_ts.replace(tzinfo=None) - timedelta(days=1), dedupe_key="s2"
            ),
        ],
    )

    resolved = resolve_dependency(
        empty_warehouse, _supplement_request(matcher="vitamin d3", anchor_ts=anchor_ts)
    )

    assert resolved.usable is True
    assert resolved.domain == "supplement_intake"
    payload = resolved.payload
    assert payload is not None
    assert payload["matcher"] == "vitamin d3"
    assert payload["logged_day_count"] == 2
    assert "adherence" not in payload  # resolver computes no verdict
    assert "day_basis" in payload


def test_supplement_matcher_is_case_insensitive_substring_and(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """The pinned matcher: case-insensitive substring, product-then-ingredient, AND."""
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(
                ts_utc=anchor_ts.replace(tzinfo=None) - timedelta(days=1),
                dedupe_key="s1",
                product_label="Acme Vitamin D3",
                ingredient_label="cholecalciferol",
            )
        ],
    )

    # Mixed case + partial tokens, AND across tokens, matches the product label.
    hit = resolve_dependency(
        empty_warehouse, _supplement_request(matcher="ACME d3", anchor_ts=anchor_ts)
    )
    assert hit.usable is True

    # Falls back to ingredient label when the token is not in the product label.
    by_ingredient = resolve_dependency(
        empty_warehouse, _supplement_request(matcher="cholecalciferol", anchor_ts=anchor_ts)
    )
    assert by_ingredient.usable is True

    # AND semantics: a token that matches nothing makes the whole matcher miss.
    miss = resolve_dependency(
        empty_warehouse, _supplement_request(matcher="acme magnesium", anchor_ts=anchor_ts)
    )
    assert miss.usable is False
    assert miss.absence_reason == "missing"


# ---------------------------------------------------------------------------
# FR-002: honest refusal when no matching row
# ---------------------------------------------------------------------------


def test_nutrition_intake_refuses_when_empty(empty_warehouse: Any, anchor_ts: datetime) -> None:
    resolved = resolve_dependency(
        empty_warehouse, _nutrition_request(quantity_key="energy", anchor_ts=anchor_ts)
    )
    assert resolved.usable is False
    assert resolved.absence_reason == "missing"
    assert resolved.message


def test_supplement_intake_refuses_when_empty(empty_warehouse: Any, anchor_ts: datetime) -> None:
    resolved = resolve_dependency(
        empty_warehouse, _supplement_request(matcher="vitamin d3", anchor_ts=anchor_ts)
    )
    assert resolved.usable is False
    assert resolved.absence_reason == "missing"
    assert resolved.message


# ---------------------------------------------------------------------------
# T014 / NFR-003: no hidden fallback — an observation row never satisfies intake
# ---------------------------------------------------------------------------


def test_observation_row_never_satisfies_nutrition_intake(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A same-named observation must not back-fill an intake dependency (NFR-003).

    Seed an ``energy`` observation in ``hp.fact_measurement`` but no nutrition
    intake row. The nutrition resolver reads intake tables only, so the declared
    intake dependency must still refuse honestly.
    """
    conn = empty_warehouse
    _seed_same_named_observation(
        conn,
        metric_id="energy",
        value_num=2000.0,
        ts=anchor_ts.replace(tzinfo=None) - timedelta(days=1),
    )

    resolved = resolve_dependency(
        conn, _nutrition_request(quantity_key="energy", anchor_ts=anchor_ts)
    )

    assert resolved.usable is False
    assert resolved.absence_reason == "missing"


def test_observation_row_never_satisfies_supplement_intake(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """The supplement resolver must not read any observation row (NFR-003)."""
    conn = empty_warehouse
    _seed_same_named_observation(
        conn,
        metric_id="vitamin_d3",
        value_num=1.0,
        ts=anchor_ts.replace(tzinfo=None) - timedelta(days=1),
        unit="count",
    )

    resolved = resolve_dependency(
        conn, _supplement_request(matcher="vitamin_d3", anchor_ts=anchor_ts)
    )

    assert resolved.usable is False
    assert resolved.absence_reason == "missing"


# ---------------------------------------------------------------------------
# T015 / NFR-005: structural generalization — no per-domain branch in the seam
# ---------------------------------------------------------------------------


def _dispatcher_code_without_docstring(fn: Any) -> str:
    """Return the source of ``fn`` with its docstring node removed.

    The structural-generalization invariant is about *code* (no per-domain
    branch), not prose: the dispatcher's docstring legitimately names the intake
    domains when explaining the unsupported-domain fall-through. Parse the AST,
    drop the leading string-literal expression, and unparse the rest.
    """
    source = textwrap.dedent(inspect.getsource(fn))
    module = ast.parse(source)
    func = module.body[0]
    assert isinstance(func, ast.FunctionDef)
    body = func.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        func.body = body[1:]
    return ast.unparse(module)


def test_shared_seam_has_no_per_domain_branch() -> None:
    """The shared ``resolve_dependency`` path names no intake domain (NFR-005).

    Both intake domains must be reached purely through the ``@resolver`` registry
    — exactly like ``observation_history`` / ``profile_context`` — not through an
    ``if domain == "nutrition_intake"`` branch inside the dispatcher. We read the
    actual dispatcher source, strip its docstring (which names the domains only as
    prose), and assert the remaining *code* contains no domain-literal branch.
    """
    from premura.engine import _resolution

    code = _dispatcher_code_without_docstring(_resolution.resolve_dependency)
    assert "nutrition_intake" not in code
    assert "supplement_intake" not in code
    # The dispatcher routes via the registry, not a hardcoded chain.
    assert "RESOLVERS" in code


def test_intake_domains_reached_purely_via_registry(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """Both intake domains are registered through the same decorator-driven seam."""
    from premura.engine import RESOLVERS

    # Touch the public seam so the lazy loader imports the resolver modules.
    resolve_dependency(
        empty_warehouse, _nutrition_request(quantity_key="energy", anchor_ts=anchor_ts)
    )
    resolve_dependency(empty_warehouse, _supplement_request(matcher="x", anchor_ts=anchor_ts))

    assert "nutrition_intake" in RESOLVERS
    assert "supplement_intake" in RESOLVERS
    # The observation/profile resolvers register through the identical seam.
    assert "observation_history" in RESOLVERS
    assert "profile_context" in RESOLVERS


# ---------------------------------------------------------------------------
# T016 / NFR-006: local-calendar-day basis crosses local midnight
# ---------------------------------------------------------------------------


def test_nutrition_uses_local_calendar_day(empty_warehouse: Any) -> None:
    """A near-midnight event resolves on its LOCAL day, not its UTC date (NFR-006).

    ``2026-05-20T11:30:00`` UTC in ``Pacific/Auckland`` (+12) is local
    ``2026-05-20 23:30`` — same calendar date as UTC would be wrong to assume in
    general, so use an instant that crosses: ``2026-05-20T13:00:00`` UTC is local
    ``2026-05-21 01:00`` in Auckland. The resolved day set must use the local
    (21st) day and ``day_basis == "local_calendar_day"``.
    """
    utc_instant = datetime(2026, 5, 20, 13, 0, 0)  # naive UTC
    anchor = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=utc_instant,
                dedupe_key="ntz",
                local_tz="Pacific/Auckland",
            )
        ],
    )

    resolved = resolve_dependency(
        empty_warehouse, _nutrition_request(quantity_key="energy", anchor_ts=anchor)
    )

    assert resolved.usable is True
    payload = resolved.payload
    assert payload is not None
    assert payload["day_basis"] == "local_calendar_day"
    # UTC date is the 20th; the local Auckland day is the 21st.
    assert payload["points"][0]["day"] == "2026-05-21"


def test_supplement_uses_local_calendar_day(empty_warehouse: Any) -> None:
    """Supplement coverage uses the local calendar day too (NFR-006)."""
    utc_instant = datetime(2026, 5, 20, 13, 0, 0)
    anchor = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(
                ts_utc=utc_instant,
                dedupe_key="stz",
                local_tz="Pacific/Auckland",
            )
        ],
    )

    resolved = resolve_dependency(
        empty_warehouse, _supplement_request(matcher="vitamin d3", anchor_ts=anchor)
    )

    assert resolved.usable is True
    payload = resolved.payload
    assert payload is not None
    assert payload["day_basis"] == "local_calendar_day"
    assert payload["logged_days"] == ["2026-05-21"]


def test_utc_fallback_basis_when_no_local_tz(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Without ``local_tz`` the basis is the explicit naive-UTC fallback."""
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=anchor_ts.replace(tzinfo=None) - timedelta(days=1),
                dedupe_key="nutc",
                local_tz=None,
            )
        ],
    )
    resolved = resolve_dependency(
        empty_warehouse, _nutrition_request(quantity_key="energy", anchor_ts=anchor_ts)
    )
    assert resolved.usable is True
    assert resolved.payload is not None
    assert resolved.payload["day_basis"] == "naive_utc_day"


# ---------------------------------------------------------------------------
# T031: parameterized-signal invocation seam (backward compatible)
# ---------------------------------------------------------------------------


@pytest.fixture
def _restore_registry() -> Iterator[None]:
    """Snapshot + restore the signal REGISTRY around in-test registration."""
    from premura.engine import REGISTRY

    snapshot = dict(REGISTRY)
    try:
        yield
    finally:
        REGISTRY.clear()
        REGISTRY.update(snapshot)


def test_compute_threads_params_to_parameterized_signal(
    empty_warehouse: Any, _restore_registry: None
) -> None:
    """A signal that declares ``params`` receives caller params through compute()."""
    from premura.engine import signal

    seen: dict[str, Any] = {}

    @signal(name="intake_param_probe", domain=["intake"], inputs=[])
    def _probe(conn: Any, *, params: Any) -> dict[str, Any]:
        seen.update(params)
        return {"echo": dict(params)}

    result = compute(
        "intake_param_probe", empty_warehouse, params={"matcher": "vitamin d3", "window_days": 14}
    )

    assert seen == {"matcher": "vitamin d3", "window_days": 14}
    assert result == {"echo": {"matcher": "vitamin d3", "window_days": 14}}


def test_compute_zero_arg_signal_unchanged(empty_warehouse: Any, _restore_registry: None) -> None:
    """An existing zero-arg signal is still invoked as ``fn(conn)`` (no params)."""
    from premura.engine import signal

    calls: list[int] = []

    @signal(name="intake_zero_arg_probe", domain=["intake"], inputs=[])
    def _zero(conn: Any) -> str:
        calls.append(1)
        return "ok"

    # Default call path — no params — must work exactly as before.
    assert compute("intake_zero_arg_probe", empty_warehouse) == "ok"
    assert calls == [1]


def test_compute_rejects_params_for_zero_arg_signal(
    empty_warehouse: Any, _restore_registry: None
) -> None:
    """Passing params to a signal that does not accept them is a programming error."""
    from premura.engine import signal

    @signal(name="intake_zero_arg_probe2", domain=["intake"], inputs=[])
    def _zero(conn: Any) -> str:
        return "ok"

    with pytest.raises(TypeError, match="does not accept caller params"):
        compute("intake_zero_arg_probe2", empty_warehouse, params={"matcher": "x"})
