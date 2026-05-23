"""Stage 2 — Signal engine.

This package defines the **open boundary** of Premura's Stage 2 signal engine.
Importing it never imports any actual signal implementation: the registry is
empty until signal modules opt into registration. This keeps the engine surface
stable enough that a closed-source ``premura-engine-pro`` package (or other
proprietary derivations) may reimplement the boundary without breaking callers.

The engine operates primarily in on-demand mode:

* **On-demand** (default, called from MCP) — :func:`compute` looks up a
  :class:`SignalSpec` in :data:`REGISTRY`, invokes its ``fn`` with a DuckDB
  connection, and returns the result (optionally persisting a ``derived:*``
  row to ``hp.fact_measurement``).

Signals may also mark themselves ``auto_safe=True`` so future explicit
recompute flows can identify low-risk derived outputs without re-litigating
which registry entries are safe to materialize automatically.

This module re-exports :class:`SignalSpec`, :data:`REGISTRY`, and the
:func:`signal` decorator from :mod:`premura.engine._registry`.

The built-in implementation surface stays lazily loaded: importing
``premura.engine`` still leaves :data:`REGISTRY` empty until one of the query
or compute helpers below needs the built-in signals.

See STAGES.md for the four-stage architecture this slots into.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import TYPE_CHECKING, Any

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
    """Return all :class:`SignalSpec` entries whose ``domain`` contains ``domain``.

    Used by MCP's tool-exposure logic to discover relevant signals for a
    user-selected health direction. Does NOT filter by input-availability -
    that is :func:`check_inputs_available` / :func:`list_unavailable`.
    """
    _ensure_builtin_signals_loaded()
    return [spec for spec in REGISTRY.values() if domain in spec.domain]


def list_auto_safe() -> list[SignalSpec]:
    """Return all :class:`SignalSpec` entries where ``auto_safe is True``.

    This is metadata only. It identifies derivations that are conservative
    enough for future explicit recompute flows.
    """
    _ensure_builtin_signals_loaded()
    return [spec for spec in REGISTRY.values() if spec.auto_safe]


def check_inputs_available(
    inputs: list[str],
    conn: duckdb.DuckDBPyConnection,
    within: object = None,
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


def list_unavailable(
    domain: str,
    conn: duckdb.DuckDBPyConnection,
) -> list[SignalSpec]:
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
    module.register_builtin_signals()


def _persist_derived_rows(
    conn: duckdb.DuckDBPyConnection,
    spec: SignalSpec,
    result: object,
) -> list[dict[str, Any]]:
    rows = _coerce_derived_rows(spec.name, result)
    for row in rows:
        payload = dict(row.get("raw_payload") or {})
        payload["revision"] = spec.revision
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
                json.dumps(payload),
            ],
        )
    return rows


def _coerce_derived_rows(spec_name: str, result: object) -> list[dict[str, Any]]:
    if not isinstance(result, list):
        raise TypeError(f"signal {spec_name!r} must return list[dict[str, object]]")

    required = {"ts_utc", "unit", "source_id", "source_uuid", "dedupe_key"}
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(result):
        if not isinstance(row, Mapping):
            raise TypeError(f"signal {spec_name!r} row {index} must be a mapping")
        missing = required - set(row)
        if missing:
            raise ValueError(f"signal {spec_name!r} row {index} missing fields: {sorted(missing)}")
        raw_payload = row.get("raw_payload")
        if raw_payload is not None and not isinstance(raw_payload, Mapping):
            raise TypeError(
                f"signal {spec_name!r} row {index} raw_payload must be a mapping or None"
            )
        rows.append(dict(row))
    return rows


def _coerce_within(within: object) -> timedelta | None:
    if within is None:
        return None
    if isinstance(within, timedelta):
        return within
    raise TypeError("within must be a datetime.timedelta or None")


def _lookup_validity_window(
    conn: duckdb.DuckDBPyConnection,
    metric_id: str,
) -> timedelta | None:
    row = conn.execute(
        "SELECT validity_window FROM hp.dim_metric WHERE metric_id = ?",
        [metric_id],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return _parse_iso8601_duration(str(row[0]))


def _latest_metric_timestamp(
    conn: duckdb.DuckDBPyConnection,
    metric_id: str,
) -> datetime | None:
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
    match = re.fullmatch(
        r"P(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value,
    )
    if match is None or not any(match.groupdict().values()):
        raise ValueError(f"unsupported ISO-8601 duration: {value}")

    parts = {name: int(raw) if raw is not None else 0 for name, raw in match.groupdict().items()}
    return timedelta(
        days=(parts["years"] * 365) + (parts["months"] * 30) + (parts["weeks"] * 7) + parts["days"],
        seconds=(parts["hours"] * 3600) + (parts["minutes"] * 60) + parts["seconds"],
    )
