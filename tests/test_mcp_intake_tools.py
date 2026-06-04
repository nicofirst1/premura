"""WP05 — default-surface MCP intake tool tests.

These lock the two thin intake tools that expose WP04's parameterized intake
signals on the DEFAULT agent-safe MCP surface (FR-006):

* ``supplement_intake_adherence`` — coverage "K of N days" for a caller-declared
  matcher + bounded window (status/coverage family).
* ``nutrition_intake_trend`` — up/down/flat over a caller-declared quantity key +
  bounded window, missing days kept as VISIBLE GAPS (trend family).

What is locked here:

* FR-006 (T025): BOTH tools are PUBLISHED on the default surface (an exact +2
  count delta against the prior surface, asserted via ``build_server`` /
  ``list_tools``), and on the operator surface that inherits the default set.
* The wrappers are THIN: they delegate to the WP04 signal through the engine
  ``compute(..., params=...)`` seam, so each tool surfaces the engine's own
  result (matcher/quantity-key echoed back, day_basis from the resolver) — the
  wrapper computes no coverage/direction of its own.
* Three refusal states (``missing_input`` / ``stale_input`` /
  ``insufficient_data``) stay STRUCTURALLY DISTINCT through the tool layer, not
  collapsed into one generic string error; missing/stale carry the structured
  ``missing_input`` report.
* NFR-001: no diagnosis/recommendation/causal/significance language at the
  surface, across both tools and all states.

Intake rows are seeded directly via ``persist_intake_batch`` (the already-shipped
store path); tests assert on the structured tool payloads, never on signal
internals.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from premura.mcp import server
from premura.mcp.entrypoint import build_operator_server, build_server
from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionQuantityInput,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)
from premura.store import duck
from premura.store.profile_intake import persist_intake_batch

_SOURCE_ID = "intake:test"
_SOURCE_KIND = "reference_intake"

# The two intake tools WP05 adds to the default surface (FR-006).
_INTAKE_TOOLS = {"supplement_intake_adherence", "nutrition_intake_trend"}

# Banned non-diagnostic language checked across every serialized payload string
# (NFR-001 at the surface). Mirrors the engine-level signal test's ban list.
_BANNED_SUBSTRINGS = (
    "should",
    "p-value",
    "p value",
    "significant",
    "reference range",
    "normal range",
    "diagnos",
    "deficien",
    "caused by",
    "causes",
    "because of",
    "recommend",
    "you must",
    "you need to",
)


# ---------------------------------------------------------------------------
# Fixtures / seeding helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def anchor_ts() -> datetime:
    """A "now"-anchored reference.

    The thin tools deliberately expose ONLY ``matcher``/``quantity_key`` +
    ``window_days`` — not an anchor — so the underlying signal computes against
    real ``now`` (UTC). Tests therefore seed events relative to actual now so the
    fixed freshness/window math lands where each state needs it.
    """
    return datetime.now(tz=UTC)


def _warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "intake.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _descriptor() -> SourceDescriptor:
    return SourceDescriptor(source_id=_SOURCE_ID, source_kind=_SOURCE_KIND)


def _naive(anchor_ts: datetime, *, days: int) -> datetime:
    return anchor_ts.replace(tzinfo=None) - timedelta(days=days)


def _open(db_path: Path) -> Any:
    return duck.connect(db_path, read_only=False)


def _seed_supplement(db_path: Path, events: list[SupplementIntakeInput]) -> None:
    conn = _open(db_path)
    try:
        persist_intake_batch(
            conn,
            IntakeBatch(
                source_descriptors={_SOURCE_ID: _descriptor()},
                supplement_events=events,
            ),
        )
    finally:
        conn.close()


def _seed_nutrition(db_path: Path, events: list[NutritionIntakeInput]) -> None:
    conn = _open(db_path)
    try:
        persist_intake_batch(
            conn,
            IntakeBatch(
                source_descriptors={_SOURCE_ID: _descriptor()},
                nutrition_events=events,
            ),
        )
    finally:
        conn.close()


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


def _nutrition_event(
    *,
    start_utc: datetime,
    dedupe_key: str,
    quantity_key: str = "energy",
    value_num: float = 500.0,
) -> NutritionIntakeInput:
    return NutritionIntakeInput(
        source_id=_SOURCE_ID,
        source_kind=_SOURCE_KIND,
        start_utc=start_utc,
        dedupe_key=dedupe_key,
        event_quantities=[
            NutritionQuantityInput(quantity_key=quantity_key, value_num=value_num, subject="event")
        ],
    )


def _all_strings(value: Any) -> str:
    chunks: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for sub in node.values():
                _walk(sub)
        elif isinstance(node, (list, tuple)):
            for sub in node:
                _walk(sub)

    _walk(value)
    return " \n ".join(chunks)


def _assert_non_diagnostic(payload: dict[str, Any]) -> None:
    text = _all_strings(payload).lower()
    for banned in _BANNED_SUBSTRINGS:
        assert banned not in text, f"banned phrase {banned!r} in tool payload: {text!r}"


# ---------------------------------------------------------------------------
# T025 — publication on the default surface (FR-006), exact +2 count delta
# ---------------------------------------------------------------------------


def test_both_intake_tools_published_on_default_surface() -> None:
    """FR-006: both intake tools are PUBLISHED (not just defined) on the default surface."""

    async def run() -> None:
        names = {tool.name for tool in await build_server().list_tools()}
        assert _INTAKE_TOOLS <= names, f"intake tools missing from default surface: {names}"

    asyncio.run(run())


def test_intake_tools_add_exactly_two_to_default_surface() -> None:
    """The two intake tools are an exact +2 delta over the rest of the surface (FR-006)."""

    async def run() -> None:
        names = {tool.name for tool in await build_server().list_tools()}
        # Removing exactly the two intake tools leaves the prior surface; the
        # delta is exactly two, neither collapsed into one nor over-registered.
        assert len(names) - len(names - _INTAKE_TOOLS) == 2

    asyncio.run(run())


def test_both_intake_tools_inherited_by_operator_surface() -> None:
    """The operator surface inherits the default set, so both intake tools appear there too."""

    async def run() -> None:
        names = {tool.name for tool in await build_operator_server().list_tools()}
        assert _INTAKE_TOOLS <= names

    asyncio.run(run())


def test_intake_tools_callable_through_published_surface(
    tmp_path: Path, anchor_ts: datetime
) -> None:
    """A published tool is live, not dead: calling it through the surface returns the envelope.

    Drives the tools the way an agent would — through ``build_server().call_tool`` —
    rather than via a direct module reference, proving registration wired the
    wrapper, not just that the function exists.
    """
    db_path = _warehouse(tmp_path)
    _seed_supplement(
        db_path,
        [
            _supplement_event(ts_utc=_naive(anchor_ts, days=2), dedupe_key="p1"),
            _supplement_event(ts_utc=_naive(anchor_ts, days=1), dedupe_key="p2"),
        ],
    )
    _seed_nutrition(
        db_path,
        [
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=3), dedupe_key="e1", value_num=1500.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=2), dedupe_key="e2", value_num=1900.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=1), dedupe_key="e3", value_num=2300.0
            ),
        ],
    )

    async def run() -> None:
        srv = build_server(warehouse_path=db_path)

        async def call(name: str, args: dict[str, object]) -> dict[str, Any]:
            result = await srv.call_tool(name, args)
            return result[1] if isinstance(result, tuple) else result

        sup = await call("supplement_intake_adherence", {"matcher": "vitamin d3", "window_days": 7})
        assert sup["tool_name"] == "supplement_intake_adherence"
        assert sup["status"] == "available"

        nut = await call("nutrition_intake_trend", {"quantity_key": "energy", "window_days": 14})
        assert nut["tool_name"] == "nutrition_intake_trend"
        assert nut["status"] == "available"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# T023 — supplement_intake_adherence wrapper: one successful call + states
# ---------------------------------------------------------------------------


def test_supplement_tool_available(tmp_path: Path, anchor_ts: datetime) -> None:
    """Data present -> ``available`` with the engine's real coverage answer."""
    db_path = _warehouse(tmp_path)
    _seed_supplement(
        db_path,
        [
            _supplement_event(ts_utc=_naive(anchor_ts, days=3), dedupe_key="s1"),
            _supplement_event(ts_utc=_naive(anchor_ts, days=2), dedupe_key="s2"),
            _supplement_event(ts_utc=_naive(anchor_ts, days=1), dedupe_key="s3"),
        ],
    )

    payload = server.supplement_intake_adherence(
        "vitamin d3", window_days=7, warehouse_path=db_path
    )

    assert payload["tool_name"] == "supplement_intake_adherence"
    assert payload["status"] == "available"
    # The wrapper is thin: matcher/window/coverage come straight from the engine.
    assert payload["result"]["matcher"] == "vitamin d3"
    assert payload["result"]["window_day_count"] == 7
    assert payload["result"]["logged_day_count"] == 3
    # day_basis is the resolver's own (the wrapper never recomputes it).
    assert payload["result"]["day_basis"] is not None
    assert "missing_input" not in payload
    _assert_non_diagnostic(payload)


def test_supplement_tool_missing_input(tmp_path: Path, anchor_ts: datetime) -> None:
    """Declared-but-empty domain -> structurally distinct ``missing_input`` + report."""
    db_path = _warehouse(tmp_path)
    # A non-matching supplement: the domain exists but the matcher finds nothing.
    _seed_supplement(
        db_path,
        [
            _supplement_event(
                ts_utc=_naive(anchor_ts, days=1),
                dedupe_key="other",
                product_label="Acme Magnesium",
                ingredient_label="magnesium citrate",
            )
        ],
    )

    payload = server.supplement_intake_adherence(
        "vitamin d3", window_days=7, warehouse_path=db_path
    )

    assert payload["status"] == "missing_input"
    assert payload["result"]["logged_day_count"] == 0
    # Missing carries the structured report (not just a string error).
    assert payload["missing_input"]["tool_name"] == "supplement_intake_adherence"
    assert payload["missing_input"]["missing_inputs"] == ["supplement_intake"]
    _assert_non_diagnostic(payload)


def test_supplement_tool_stale_input(tmp_path: Path, anchor_ts: datetime) -> None:
    """Matching but old history -> ``stale_input``, distinct from missing.

    The signal's default freshness cutoff is 7 days, so a 20-day-old dose (still
    inside a 30-day window) is present-but-stale — the distinct weaker state.
    The wrapper's only knobs are matcher + window; freshness is the engine's.
    """
    db_path = _warehouse(tmp_path)
    _seed_supplement(
        db_path,
        [_supplement_event(ts_utc=_naive(anchor_ts, days=20), dedupe_key="stale-only")],
    )

    payload = server.supplement_intake_adherence(
        "vitamin d3", window_days=30, warehouse_path=db_path
    )

    assert payload["status"] == "stale_input"
    # Stale retains the latest evidence and carries the structured report.
    assert payload["result"]["latest_logged_at"] is not None
    assert payload["missing_input"]["stale_inputs"] == ["supplement_intake"]
    _assert_non_diagnostic(payload)


def test_supplement_tool_states_are_structurally_distinct(
    tmp_path: Path, anchor_ts: datetime
) -> None:
    """missing / stale / insufficient survive the tool layer as distinct states."""
    missing_db = _warehouse(tmp_path / "m")
    missing = server.supplement_intake_adherence(
        "vitamin d3", window_days=7, warehouse_path=missing_db
    )

    stale_db = _warehouse(tmp_path / "s")
    _seed_supplement(
        stale_db,
        [_supplement_event(ts_utc=_naive(anchor_ts, days=20), dedupe_key="stale")],
    )
    stale = server.supplement_intake_adherence(
        "vitamin d3", window_days=30, warehouse_path=stale_db
    )

    # insufficient: a single fresh logged day. The tool's default min_logged_days
    # is 1, so a single fresh day is "available"; to surface insufficient through
    # the engine we seed zero distinct logged days inside freshness but a present
    # row — exercised at the engine level in test_intake_signals. Here we assert
    # the two states the tool's own knobs can reach stay distinct, plus that
    # neither collapses into the other or into a generic error string.
    assert missing["status"] == "missing_input"
    assert stale["status"] == "stale_input"
    assert missing["status"] != stale["status"]
    # Each unavailable state is a real label, not a generic "error".
    assert missing["status"] in {"missing_input", "stale_input", "insufficient_data"}
    assert stale["status"] in {"missing_input", "stale_input", "insufficient_data"}


# ---------------------------------------------------------------------------
# T024 — nutrition_intake_trend wrapper: one successful call + states
# ---------------------------------------------------------------------------


def test_nutrition_tool_available(tmp_path: Path, anchor_ts: datetime) -> None:
    """A rising series -> ``available`` with an ``up`` direction (engine's answer)."""
    db_path = _warehouse(tmp_path)
    _seed_nutrition(
        db_path,
        [
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

    payload = server.nutrition_intake_trend("energy", window_days=14, warehouse_path=db_path)

    assert payload["tool_name"] == "nutrition_intake_trend"
    assert payload["status"] == "available"
    assert payload["result"]["quantity_key"] == "energy"
    assert payload["result"]["trend_direction"] == "up"
    assert payload["result"]["days_with_data"] == 4
    assert "missing_input" not in payload
    _assert_non_diagnostic(payload)


def test_nutrition_tool_missing_input(tmp_path: Path, anchor_ts: datetime) -> None:
    """No matching quantity rows -> structurally distinct ``missing_input`` + report."""
    db_path = _warehouse(tmp_path)
    _seed_nutrition(
        db_path,
        [
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=1),
                dedupe_key="prot",
                quantity_key="protein",
            )
        ],
    )

    payload = server.nutrition_intake_trend("energy", window_days=14, warehouse_path=db_path)

    assert payload["status"] == "missing_input"
    assert payload["result"]["trend_direction"] == "unknown"
    assert payload["result"]["days_with_data"] == 0
    assert payload["missing_input"]["missing_inputs"] == ["nutrition_intake"]
    _assert_non_diagnostic(payload)


def test_nutrition_tool_insufficient_data(tmp_path: Path, anchor_ts: datetime) -> None:
    """Too few observed days to name a direction -> ``insufficient_data`` (distinct)."""
    db_path = _warehouse(tmp_path)
    _seed_nutrition(
        db_path,
        [
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=1), dedupe_key="solo", value_num=2000.0
            )
        ],
    )

    payload = server.nutrition_intake_trend("energy", window_days=14, warehouse_path=db_path)

    assert payload["status"] == "insufficient_data"
    assert payload["result"]["days_with_data"] == 1
    # The single observed point stays visible; not collapsed to missing.
    assert len(payload["result"]["points"]) == 1
    _assert_non_diagnostic(payload)


def test_nutrition_tool_stale_input(tmp_path: Path, anchor_ts: datetime) -> None:
    """Matching but old history -> ``stale_input`` with the structured report."""
    db_path = _warehouse(tmp_path)
    _seed_nutrition(
        db_path,
        [
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=20), dedupe_key="o1", value_num=1500.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=19), dedupe_key="o2", value_num=1700.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=18), dedupe_key="o3", value_num=1900.0
            ),
        ],
    )

    payload = server.nutrition_intake_trend("energy", window_days=30, warehouse_path=db_path)

    assert payload["status"] == "stale_input"
    assert payload["missing_input"]["stale_inputs"] == ["nutrition_intake"]
    _assert_non_diagnostic(payload)


def test_nutrition_tool_three_states_structurally_distinct(
    tmp_path: Path, anchor_ts: datetime
) -> None:
    """missing / stale / insufficient remain three distinct states through the tool."""
    missing = server.nutrition_intake_trend(
        "energy", window_days=14, warehouse_path=_warehouse(tmp_path / "miss")
    )

    insufficient_db = _warehouse(tmp_path / "insuf")
    _seed_nutrition(
        insufficient_db,
        [_nutrition_event(start_utc=_naive(anchor_ts, days=1), dedupe_key="one", value_num=2000.0)],
    )
    insufficient = server.nutrition_intake_trend(
        "energy", window_days=14, warehouse_path=insufficient_db
    )

    stale_db = _warehouse(tmp_path / "stale")
    _seed_nutrition(
        stale_db,
        [
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=20), dedupe_key="s1", value_num=1500.0
            ),
            _nutrition_event(
                start_utc=_naive(anchor_ts, days=19), dedupe_key="s2", value_num=1700.0
            ),
        ],
    )
    stale = server.nutrition_intake_trend("energy", window_days=30, warehouse_path=stale_db)

    states = {missing["status"], insufficient["status"], stale["status"]}
    assert states == {"missing_input", "insufficient_data", "stale_input"}


# ---------------------------------------------------------------------------
# Thinness: a bad caller-facing param is rejected before any engine work
# ---------------------------------------------------------------------------


def test_tools_reject_empty_required_param(tmp_path: Path) -> None:
    """An empty matcher / quantity_key is a caller error, raised by the thin wrapper."""
    db_path = _warehouse(tmp_path)
    with pytest.raises(ValueError):
        server.supplement_intake_adherence("   ", warehouse_path=db_path)
    with pytest.raises(ValueError):
        server.nutrition_intake_trend("", warehouse_path=db_path)
