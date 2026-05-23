"""Stage 2 — Signal engine.

This package defines the **open boundary** of Premura's Stage 2 signal engine.
Importing it never imports any actual signal implementation: the registry is
empty until signal modules opt into registration via the ``@signal(...)``
decorator. This keeps the engine surface stable enough that a closed-source
``premura-engine-pro`` package (or other proprietary derivations) may
reimplement the boundary without breaking callers.

The engine operates in two modes:

* **On-demand** (default, called from MCP) — :func:`compute` looks up a
  :class:`SignalSpec` in :data:`REGISTRY`, invokes its ``fn`` with a DuckDB
  connection, and returns the result (optionally persisting a ``derived:*``
  row to ``hp.fact_measurement``).
* **Auto-run** (opt-in via ``auto_safe=True``) — the ingest loader may call
  :func:`list_auto_safe` after parsing a new batch, then for each spec check
  :func:`check_inputs_available` and call :func:`compute`.

This module re-exports :class:`SignalSpec`, :data:`REGISTRY`, and the
:func:`signal` decorator from :mod:`premura.engine._registry`.

The built-in implementation surface stays lazily loaded: importing
``premura.engine`` still leaves :data:`REGISTRY` empty until one of the query
or compute helpers below needs the built-in signals.

See STAGES.md for the four-stage architecture this slots into.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module, reload
from typing import TYPE_CHECKING

from ._registry import REGISTRY, SignalSpec, signal

if TYPE_CHECKING:
    import duckdb

__all__ = [
    "REGISTRY",
    "SignalSpec",
    "signal",
    "compute",
    "list_by_domain",
    "list_auto_safe",
    "check_inputs_available",
    "list_unavailable",
]


def compute(spec_name: str, conn: duckdb.DuckDBPyConnection) -> object:
    """Look up ``REGISTRY[spec_name]``, call its ``fn`` with ``conn``, return the result.

    In the full Stage 2 implementation this raises :class:`KeyError` if
    ``spec_name`` is not in :data:`REGISTRY`, raises :class:`RuntimeError` if
    the spec was registered without a function body, may read
    ``hp.fact_measurement``/``hp.fact_interval``/``hp.dim_metric`` via
    ``conn``, and may persist a ``derived:*`` row to ``hp.fact_measurement``
    when ``spec.output is not None``.
    """
    _ensure_builtin_signals_loaded()
    if spec_name not in REGISTRY:
        raise KeyError(spec_name)

    spec = REGISTRY[spec_name]
    if spec.fn is None:
        raise RuntimeError(f"signal {spec_name!r} is registered without an implementation")

    result = spec.fn(conn)
    if spec.output is not None:
        return _persist_derived_rows(conn, spec, result)
    return result


def list_by_domain(domain: str) -> list[SignalSpec]:
    """Return all :class:`SignalSpec`\\s in :data:`REGISTRY` whose ``domain`` contains ``domain``.

    Used by MCP's tool-exposure logic to discover relevant signals for a
    user-selected health direction. Does NOT filter by input-availability —
    that is :func:`check_inputs_available` / :func:`list_unavailable`.
    """
    _ensure_builtin_signals_loaded()
    return [spec for spec in REGISTRY.values() if domain in spec.domain]


def list_auto_safe() -> list[SignalSpec]:
    """Return all :class:`SignalSpec`\\s where ``auto_safe is True``.

    Used by the ingest loader's optional auto-precompute step
    (see ``docs/architecture/UPDATE_STRATEGY.md``).
    """
    _ensure_builtin_signals_loaded()
    return [spec for spec in REGISTRY.values() if spec.auto_safe]


def check_inputs_available(
    inputs: list[str], conn: duckdb.DuckDBPyConnection, within: object = None
) -> bool:
    """Return True iff every ``metric_id`` in ``inputs`` has at least one usable measurement.

    If ``within`` is provided, restrict the check to measurements within
    ``within`` of "now" (subject to each metric's ``validity_window`` from
    ``hp.dim_metric`` when tighter). Empty ``inputs`` returns True trivially.
    """
    if not inputs:
        return True

    requested_window = _coerce_within(within)
    now = datetime.now(tz=UTC)
    for metric_id in inputs:
        validity_window = _lookup_validity_window(conn, metric_id)
        effective_window = _effective_window(requested_window, validity_window)
        latest = _latest_metric_timestamp(conn, metric_id)
        if latest is None:
            return False
        if effective_window is not None and now - latest.replace(tzinfo=UTC) > effective_window:
            return False
    return True


def list_unavailable(domain: str, conn: duckdb.DuckDBPyConnection) -> list[SignalSpec]:
    """Return the subset of :func:`list_by_domain` whose inputs are not all available.

    MCP uses this to build the ``missing_inputs_report`` it returns to the UI
    layer for user-facing "go get this lab" suggestions.
    """
    return [
        spec
        for spec in list_by_domain(domain)
        if not check_inputs_available(spec.inputs, conn)
    ]


def _ensure_builtin_signals_loaded() -> None:
    if REGISTRY:
        return
    module = import_module("premura.engine.lab_ratios")
    if not REGISTRY:
        reload(module)


def _persist_derived_rows(
    conn: duckdb.DuckDBPyConnection,
    spec: SignalSpec,
    result: object,
) -> list[dict[str, object]]:
    rows = [row for row in result if isinstance(row, dict)] if isinstance(result, list) else []
    for row in rows:
        conn.execute(
            """
            INSERT INTO hp.fact_measurement (
                ts_utc, local_tz, metric_id, value_num, value_text, unit,
                source_id, source_uuid, dedupe_key, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (dedupe_key) DO UPDATE SET
                ts_utc = excluded.ts_utc,
                local_tz = excluded.local_tz,
                metric_id = excluded.metric_id,
                value_num = excluded.value_num,
                value_text = excluded.value_text,
                unit = excluded.unit,
                source_id = excluded.source_id,
                source_uuid = excluded.source_uuid,
                raw_payload = excluded.raw_payload
            """,
            [
                row["ts_utc"],
                row.get("local_tz"),
                spec.output,
                row.get("value_num"),
                row.get("value_text"),
                row["unit"],
                row["source_id"],
                row["source_uuid"],
                row["dedupe_key"],
                row["raw_payload"],
            ],
        )
    return rows


def _coerce_within(within: object) -> timedelta | None:
    if within is None:
        return None
    if isinstance(within, timedelta):
        return within
    raise TypeError("within must be a datetime.timedelta or None")


def _lookup_validity_window(conn: duckdb.DuckDBPyConnection, metric_id: str) -> timedelta | None:
    row = conn.execute(
        "SELECT validity_window FROM hp.dim_metric WHERE metric_id = ?",
        [metric_id],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return _parse_iso8601_duration(str(row[0]))


def _latest_metric_timestamp(conn: duckdb.DuckDBPyConnection, metric_id: str) -> datetime | None:
    row = conn.execute(
        """
        SELECT MAX(observed_at)
        FROM (
            SELECT ts_utc AS observed_at FROM hp.fact_measurement WHERE metric_id = ?
            UNION ALL
            SELECT end_utc AS observed_at FROM hp.fact_interval WHERE metric_id = ?
        )
        """,
        [metric_id, metric_id],
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def _effective_window(
    requested_window: timedelta | None,
    validity_window: timedelta | None,
) -> timedelta | None:
    if requested_window is None:
        return validity_window
    if validity_window is None:
        return requested_window
    return min(requested_window, validity_window)


def _parse_iso8601_duration(value: str) -> timedelta:
    normalized = value.removeprefix("P")
    if "T" in normalized:
        date_part, time_part = normalized.split("T", maxsplit=1)
    else:
        date_part, time_part = normalized, ""
    days = 0
    number = ""
    for char in date_part:
        if char.isdigit():
            number += char
            continue
        amount = int(number)
        number = ""
        if char == "Y":
            days += amount * 365
        elif char == "M":
            days += amount * 30
        elif char == "W":
            days += amount * 7
        elif char == "D":
            days += amount
        else:
            raise ValueError(f"unsupported ISO-8601 duration: {value}")

    seconds = 0
    number = ""
    for char in time_part:
        if char.isdigit():
            number += char
            continue
        amount = int(number)
        number = ""
        if char == "H":
            seconds += amount * 3600
        elif char == "M":
            seconds += amount * 60
        elif char == "S":
            seconds += amount
        else:
            raise ValueError(f"unsupported ISO-8601 duration: {value}")

    return timedelta(days=days, seconds=seconds)
