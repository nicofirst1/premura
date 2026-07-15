"""Behavioral tests for the WP04 intake descriptive signals.

Two parameterized, non-diagnostic signals consume the WP03 intake resolvers
through the public ``compute(name, conn, params=...)`` seam (T031):

* ``supplement_intake_adherence`` — coverage "K of N days" for a caller-declared
  matcher + bounded window (status/coverage family).
* ``nutrition_intake_trend`` — up/down/flat over a caller-declared quantity key +
  bounded window, missing days kept as VISIBLE GAPS (trend family).

Every test drives behavior through the *public* engine seam
(``from premura.engine import compute``) — there are no direct imports of the
signal functions or the resolver view modules. The signals reach their resolvers
through ``premura.engine.descriptive_signals.resolve_dependency`` (the same
monkeypatchable module attribute the BMI consumer uses), and the engine's lazy
loader binds both intake resolvers via the ``@resolver(domain=...)`` registry, so
these tests prove the wiring end-to-end (registration-as-discovery, not dead
code).

Intake rows are seeded directly via ``persist_intake_batch`` (the already-shipped
store path); this WP does not depend on WP01/WP02. Tests assert on the signal
envelopes (black-box), never on signal internals.

What is locked here:

* FR-003/FR-004 (T019): positive-path — data present surfaces a real answer, a
  fixture STRUCTURALLY DISTINCT from the refusal suite (D5: a missingness-only
  suite would let an always-empty path masquerade as compliant).
* FR-005 (T020): the three refusal states (missing / stale / insufficient) are
  STRUCTURALLY DISTINCT envelope states, not one catch-all.
* FR-004 (T018): the nutrition trend NEVER imputes missing days — gaps stay
  visible (no carry-forward).
* NFR-006 / D4 (T021): a local-midnight-crossing event reports day/window
  metadata on the SAME local-day basis the resolver computed on.
* NFR-001 (T022): no envelope/caveat carries a reference range, "should", a
  p-value, "significant", or causal language.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionQuantityInput,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)
from premura.store.profile_intake import persist_intake_batch

# NOTE: ``premura.engine`` is intentionally NOT imported at module top — sibling
# tests purge ``premura.engine*`` from ``sys.modules`` and re-import to simulate a
# fresh process; a module-level binding would capture a pre-purge ``compute`` /
# ``REGISTRY``. Reach the engine surface through :func:`_engine` every time so we
# always resolve against the currently-active module (mirrors test_intake_resolvers).


def _engine() -> Any:
    """Return the current ``premura.engine`` module (purge-safe)."""
    import premura.engine as engine_pkg

    return engine_pkg


def compute(spec_name: str, conn: Any, **kwargs: Any) -> Any:
    return _engine().compute(spec_name, conn, **kwargs)


# ---------------------------------------------------------------------------
# Fixtures and seeding helpers
# ---------------------------------------------------------------------------

_SOURCE_ID = "intake:test"
_SOURCE_KIND = "reference_intake"


@pytest.fixture
def anchor_ts() -> datetime:
    """A fixed timezone-aware anchor used across the signal tests."""
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


def _descriptor() -> SourceDescriptor:
    return SourceDescriptor(source_id=_SOURCE_ID, source_kind=_SOURCE_KIND)


def _seed_nutrition(conn: Any, *, events: list[NutritionIntakeInput]) -> None:
    persist_intake_batch(
        conn,
        IntakeBatch(
            source_descriptors={_SOURCE_ID: _descriptor()},
            nutrition_events=events,
        ),
    )


def _seed_supplement(conn: Any, *, events: list[SupplementIntakeInput]) -> None:
    persist_intake_batch(
        conn,
        IntakeBatch(
            source_descriptors={_SOURCE_ID: _descriptor()},
            supplement_events=events,
        ),
    )


def _nutrition_event(
    *,
    start_utc: datetime,
    dedupe_key: str,
    quantity_key: str = "energy",
    value_num: float = 500.0,
    local_tz: str | None = None,
) -> NutritionIntakeInput:
    return NutritionIntakeInput(
        source_id=_SOURCE_ID,
        source_kind=_SOURCE_KIND,
        start_utc=start_utc,
        dedupe_key=dedupe_key,
        local_tz=local_tz,
        event_quantities=[
            NutritionQuantityInput(quantity_key=quantity_key, value_num=value_num, subject="event")
        ],
    )


def _supplement_event(
    *,
    ts_utc: datetime,
    dedupe_key: str,
    product_label: str | None = "Acme Vitamin D3",
    ingredient_label: str | None = "cholecalciferol",
    local_tz: str | None = None,
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
                doses=[SupplementDoseInput(amount_text="1 capsule")],
            )
        ],
    )


def _naive(anchor_ts: datetime, *, days: int) -> datetime:
    return anchor_ts.replace(tzinfo=None) - timedelta(days=days)


def _supplement_params(
    *, matcher: str, anchor_ts: datetime, window_days: int | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"matcher": matcher, "anchor_ts": anchor_ts}
    if window_days is not None:
        params["window_days"] = window_days
    return params


def _nutrition_params(
    *, quantity_key: str, anchor_ts: datetime, window_days: int | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"quantity_key": quantity_key, "anchor_ts": anchor_ts}
    if window_days is not None:
        params["window_days"] = window_days
    return params


def _all_text(result: Any) -> str:
    """Flatten an envelope's serialized text (every string field + caveats)."""
    payload = result.to_dict()
    chunks: list[str] = []

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, dict):
            for sub in value.values():
                _walk(sub)
        elif isinstance(value, (list, tuple)):
            for sub in value:
                _walk(sub)

    _walk(payload)
    return " \n ".join(chunks)


# ---------------------------------------------------------------------------
# T019 — Positive path (data present -> real answer surfaced) — BOTH signals
# ---------------------------------------------------------------------------


def test_supplement_adherence_positive_path(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Coverage answer is surfaced: K logged days of an N-day window (FR-003)."""
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(ts_utc=_naive(anchor_ts, days=3), dedupe_key="s1"),
            _supplement_event(ts_utc=_naive(anchor_ts, days=2), dedupe_key="s2"),
            _supplement_event(ts_utc=_naive(anchor_ts, days=1), dedupe_key="s3"),
        ],
    )

    result = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params=_supplement_params(matcher="vitamin d3", anchor_ts=anchor_ts, window_days=7),
    )

    assert result.status == "available"
    assert result.logged_day_count == 3  # K
    assert result.window_day_count == 7  # N
    assert result.coverage_fraction == pytest.approx(3 / 7)
    assert result.latest_logged_at is not None
    assert result.matcher == "vitamin d3"


def test_nutrition_trend_positive_path(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """A rising series surfaces an ``up`` direction with visible points (FR-004)."""
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=4), dedupe_key="n1", value_num=1500.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=3), dedupe_key="n2", value_num=1800.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=2), dedupe_key="n3", value_num=2200.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=1), dedupe_key="n4", value_num=2600.0
            ),
        ],
    )

    result = compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params=_nutrition_params(quantity_key="energy", anchor_ts=anchor_ts, window_days=14),
    )

    assert result.status == "available"
    assert result.trend_direction == "up"
    assert result.days_with_data == 4
    assert len(result.points) == 4
    assert result.latest_logged_at is not None


# ---------------------------------------------------------------------------
# T020 — Refusal path: three STRUCTURALLY DISTINCT states — BOTH signals
# ---------------------------------------------------------------------------


def test_supplement_adherence_missing_declared_but_empty(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """Declared-but-empty domain (no matching rows) -> ``missing_input`` (D7)."""
    # Seed a NON-matching supplement so the domain is exercised but the matcher
    # finds nothing — this is "declared but empty", distinct from an unsupported
    # domain.
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(
                ts_utc=_naive(anchor_ts, days=1),
                dedupe_key="other",
                product_label="Acme Magnesium",
                ingredient_label="magnesium citrate",
            )
        ],
    )

    result = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params=_supplement_params(matcher="vitamin d3", anchor_ts=anchor_ts, window_days=7),
    )

    assert result.status == "missing_input"
    assert result.logged_day_count == 0
    assert result.coverage_fraction is None
    assert result.latest_logged_at is None


def test_supplement_adherence_stale(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Matching history exists but the latest usable day is outside freshness."""
    # One match logged 6 days ago; with a 2-day freshness rule the latest usable
    # day is older than the rule allows -> ``stale_input`` (distinct from missing).
    _seed_supplement(
        empty_warehouse,
        events=[_supplement_event(ts_utc=_naive(anchor_ts, days=6), dedupe_key="old")],
    )

    result = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params={
            "matcher": "vitamin d3",
            "anchor_ts": anchor_ts,
            "window_days": 30,
            "freshness_days": 2,
        },
    )

    assert result.status == "stale_input"
    # Stale retains the latest evidence so the caller sees WHY it is stale.
    assert result.latest_logged_at is not None


def test_supplement_adherence_insufficient(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Some rows but not enough distinct days to answer honestly."""
    # Window is fresh, but only one logged day with a min-days threshold of 2.
    _seed_supplement(
        empty_warehouse,
        events=[_supplement_event(ts_utc=_naive(anchor_ts, days=1), dedupe_key="one")],
    )

    result = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params={
            "matcher": "vitamin d3",
            "anchor_ts": anchor_ts,
            "window_days": 7,
            "min_logged_days": 2,
        },
    )

    assert result.status == "insufficient_data"
    assert result.logged_day_count == 1


def test_nutrition_trend_missing_declared_but_empty(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """No matching quantity rows -> ``missing_input`` (D7)."""
    # Seed a different quantity key so the nutrition domain has rows but the
    # requested key finds none.
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=1), dedupe_key="prot", quantity_key="protein"
            )
        ],
    )

    result = compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params=_nutrition_params(quantity_key="energy", anchor_ts=anchor_ts, window_days=14),
    )

    assert result.status == "missing_input"
    assert result.trend_direction == "unknown"
    assert result.days_with_data == 0
    assert result.points == []


def test_nutrition_trend_stale(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Matching history exists but the latest day is outside freshness."""
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(start_utc=_naive(anchor_ts, days=20), dedupe_key="o1", value_num=1500),
            _nutrition_event(start_utc=_naive(anchor_ts, days=19), dedupe_key="o2", value_num=1700),
            _nutrition_event(start_utc=_naive(anchor_ts, days=18), dedupe_key="o3", value_num=1900),
        ],
    )

    result = compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params={
            "quantity_key": "energy",
            "anchor_ts": anchor_ts,
            "window_days": 30,
            "freshness_days": 3,
        },
    )

    assert result.status == "stale_input"
    assert result.latest_logged_at is not None


def test_nutrition_trend_insufficient(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Too few observed days to name a direction honestly -> ``insufficient_data``."""
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=1), dedupe_key="single", value_num=2000
            )
        ],
    )

    result = compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params=_nutrition_params(quantity_key="energy", anchor_ts=anchor_ts, window_days=14),
    )

    assert result.status == "insufficient_data"
    assert result.days_with_data == 1
    # The single observed point stays visible; it is not silently dropped.
    assert len(result.points) == 1


def test_refusal_states_are_structurally_distinct(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """The three refusal states are distinct envelope states, not one catch-all."""
    # missing: empty domain
    missing = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params=_supplement_params(matcher="vitamin d3", anchor_ts=anchor_ts, window_days=7),
    )
    # stale: a single old match
    _seed_supplement(
        empty_warehouse,
        events=[_supplement_event(ts_utc=_naive(anchor_ts, days=6), dedupe_key="stale1")],
    )
    stale = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params={
            "matcher": "vitamin d3",
            "anchor_ts": anchor_ts,
            "window_days": 30,
            "freshness_days": 2,
            "min_logged_days": 1,
        },
    )
    # insufficient: a single fresh match with a higher min-days threshold
    insufficient = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params={
            "matcher": "vitamin d3",
            "anchor_ts": anchor_ts,
            "window_days": 30,
            "freshness_days": 30,
            "min_logged_days": 5,
        },
    )

    states = {missing.status, stale.status, insufficient.status}
    assert states == {"missing_input", "stale_input", "insufficient_data"}


# ---------------------------------------------------------------------------
# T018 — No imputation: missing days stay VISIBLE GAPS
# ---------------------------------------------------------------------------


def test_nutrition_trend_never_imputes_missing_days(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """A series with calendar gaps keeps gaps visible — no carry-forward fill."""
    # Three logged days spread across a window with deliberate gaps between them.
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(start_utc=_naive(anchor_ts, days=10), dedupe_key="g1", value_num=1500),
            _nutrition_event(start_utc=_naive(anchor_ts, days=5), dedupe_key="g2", value_num=1800),
            _nutrition_event(start_utc=_naive(anchor_ts, days=1), dedupe_key="g3", value_num=2100),
        ],
    )

    result = compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params=_nutrition_params(quantity_key="energy", anchor_ts=anchor_ts, window_days=14),
    )

    # Exactly the observed days appear; the gaps between them are NOT filled.
    assert result.days_with_data == 3
    assert len(result.points) == 3
    # No point is flagged imputed/carried-forward — the resolver never invents one.
    assert all(not p.get("is_imputed", False) for p in result.points)
    # A caveat names the gaps so trust is not overstated.
    assert any("gap" in c.lower() for c in result.caveats)


# ---------------------------------------------------------------------------
# T021 — Local-midnight divergence: reported basis == computed basis (NFR-006/D4)
# ---------------------------------------------------------------------------


def test_supplement_adherence_reports_local_day_basis(empty_warehouse: Any) -> None:
    """A local-midnight-crossing event is reported on the LOCAL day basis (NFR-006).

    ``2026-05-20T13:00:00`` UTC in ``Pacific/Auckland`` (+12) is local
    ``2026-05-21 01:00`` — a different calendar day than its UTC date. The signal
    must report the same local-day basis the resolver computed on; it must NOT
    recompute day/window metadata from raw UTC.
    """
    anchor = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(
                ts_utc=datetime(2026, 5, 20, 13, 0, 0),
                dedupe_key="stz",
                local_tz="Pacific/Auckland",
            )
        ],
    )

    result = compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params={
            "matcher": "vitamin d3",
            "anchor_ts": anchor,
            "window_days": 30,
            "min_logged_days": 1,
            "freshness_days": 30,
        },
    )

    assert result.status == "available"
    assert result.day_basis == "local_calendar_day"
    # The reported coverage day is the LOCAL (21st) day, not the UTC (20th) date.
    assert result.logged_days == ["2026-05-21"]


def test_nutrition_trend_reports_local_day_basis(empty_warehouse: Any) -> None:
    """The nutrition trend reports the same local-day basis its points use."""
    anchor = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(
                start_utc=datetime(2026, 5, 20, 13, 0, 0),
                dedupe_key="ntz1",
                local_tz="Pacific/Auckland",
                value_num=1500.0,
            ),
            _nutrition_event(
                start_utc=datetime(2026, 5, 22, 13, 0, 0),
                dedupe_key="ntz2",
                local_tz="Pacific/Auckland",
                value_num=1700.0,
            ),
        ],
    )

    result = compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params={"quantity_key": "energy", "anchor_ts": anchor, "window_days": 30},
    )

    assert result.day_basis == "local_calendar_day"
    # Points carry the LOCAL day, not the UTC date (21st/23rd, not 20th/22nd).
    days = [p["day"] for p in result.points]
    assert days == ["2026-05-21", "2026-05-23"]


# ---------------------------------------------------------------------------
# T022 — Non-diagnostic assertion (NFR-001), across BOTH signals + all states
# ---------------------------------------------------------------------------

# Banned language: reference ranges, normative "should", p-values, "significant",
# and causal/diagnostic verbs. Checked case-insensitively over every serialized
# string field (envelope text + caveats) of both signals across states.
_BANNED_SUBSTRINGS = (
    "should",
    "p-value",
    "p value",
    "significant",
    "reference range",
    "normal range",
    "diagnos",  # diagnose / diagnosis / diagnostic
    "deficien",  # deficient / deficiency
    "caused by",
    "causes",
    "because of",
    "recommend",
    "you must",
    "you need to",
)


def _assert_non_diagnostic(result: Any) -> None:
    text = _all_text(result).lower()
    for banned in _BANNED_SUBSTRINGS:
        assert banned not in text, f"banned non-diagnostic phrase {banned!r} in: {text!r}"


def test_signals_are_non_diagnostic_across_states(
    empty_warehouse: Any, anchor_ts: datetime
) -> None:
    """No envelope/caveat carries reference-range, normative, p-value, or causal language."""
    # Positive supplement path.
    _seed_supplement(
        empty_warehouse,
        events=[
            _supplement_event(ts_utc=_naive(anchor_ts, days=2), dedupe_key="d1"),
            _supplement_event(ts_utc=_naive(anchor_ts, days=1), dedupe_key="d2"),
        ],
    )
    _assert_non_diagnostic(
        compute(
            "supplement_intake_adherence",
            empty_warehouse,
            params=_supplement_params(matcher="vitamin d3", anchor_ts=anchor_ts, window_days=7),
        )
    )

    # Positive nutrition path (rising) + a gap caveat.
    _seed_nutrition(
        empty_warehouse,
        events=[
            _nutrition_event(start_utc=_naive(anchor_ts, days=6), dedupe_key="t1", value_num=1500),
            _nutrition_event(start_utc=_naive(anchor_ts, days=3), dedupe_key="t2", value_num=1900),
            _nutrition_event(start_utc=_naive(anchor_ts, days=1), dedupe_key="t3", value_num=2300),
        ],
    )
    _assert_non_diagnostic(
        compute(
            "nutrition_intake_trend",
            empty_warehouse,
            params=_nutrition_params(quantity_key="energy", anchor_ts=anchor_ts, window_days=14),
        )
    )

    # Refusal envelopes too (missing on a fresh empty warehouse domain).
    _assert_non_diagnostic(
        compute(
            "supplement_intake_adherence",
            empty_warehouse,
            params=_supplement_params(matcher="zzz-nothing", anchor_ts=anchor_ts, window_days=7),
        )
    )
    _assert_non_diagnostic(
        compute(
            "nutrition_intake_trend",
            empty_warehouse,
            params=_nutrition_params(
                quantity_key="zzz-nothing", anchor_ts=anchor_ts, window_days=14
            ),
        )
    )


# ---------------------------------------------------------------------------
# Integration: signals are discovered through the built-in loader (not dead code)
# ---------------------------------------------------------------------------


@pytest.fixture
def _registry_snapshot() -> Iterator[None]:
    from premura.engine import REGISTRY

    snapshot = dict(REGISTRY)
    try:
        yield
    finally:
        REGISTRY.clear()
        REGISTRY.update(snapshot)


def test_signals_registered_via_builtin_loader(empty_warehouse: Any, anchor_ts: datetime) -> None:
    """Both signals are reachable through ``compute`` purely via built-in discovery.

    Computing through the public seam triggers the lazy built-in loader; if the
    signals were not registered via ``register_builtin_signals()`` this would
    ``KeyError`` rather than return an envelope. This proves they are live
    registry entries, not dead module-level functions.
    """
    from premura.engine import REGISTRY
    from premura.engine import compute as engine_compute

    # Force a fresh load by clearing then computing through the public seam.
    engine_compute(
        "supplement_intake_adherence",
        empty_warehouse,
        params=_supplement_params(matcher="x", anchor_ts=anchor_ts),
    )
    engine_compute(
        "nutrition_intake_trend",
        empty_warehouse,
        params=_nutrition_params(quantity_key="x", anchor_ts=anchor_ts),
    )

    assert "supplement_intake_adherence" in REGISTRY
    assert "nutrition_intake_trend" in REGISTRY
    # The registered fn must accept caller params (the parameterized seam).
    assert REGISTRY["supplement_intake_adherence"].family == "status"
    assert REGISTRY["nutrition_intake_trend"].family == "trend"
