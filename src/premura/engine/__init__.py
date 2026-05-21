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
:func:`signal` decorator from :mod:`premura.engine._registry`, and declares
five stub API functions that future implementation missions will fill in.
All five currently raise :class:`NotImplementedError`.

See STAGES.md for the four-stage architecture this slots into.
"""
from __future__ import annotations

from ._registry import REGISTRY, SignalSpec, signal

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


def compute(spec_name: str, conn: object) -> object:
    """Look up ``REGISTRY[spec_name]``, call its ``fn`` with ``conn``, return the result.

    In the full Stage 2 implementation this raises :class:`KeyError` if
    ``spec_name`` is not in :data:`REGISTRY`, raises :class:`RuntimeError` if
    the spec was registered without a function body, may read
    ``hp.fact_measurement``/``hp.fact_interval``/``hp.dim_metric`` via
    ``conn``, and may persist a ``derived:*`` row to ``hp.fact_measurement``
    when ``spec.output is not None``.
    """
    raise NotImplementedError("Stage 2 — see STAGES.md")


def list_by_domain(domain: str) -> list[SignalSpec]:
    """Return all :class:`SignalSpec`\\s in :data:`REGISTRY` whose ``domain`` contains ``domain``.

    Used by MCP's tool-exposure logic to discover relevant signals for a
    user-selected health direction. Does NOT filter by input-availability —
    that is :func:`check_inputs_available` / :func:`list_unavailable`.
    """
    raise NotImplementedError("Stage 2 — see STAGES.md")


def list_auto_safe() -> list[SignalSpec]:
    """Return all :class:`SignalSpec`\\s where ``auto_safe is True``.

    Used by the ingest loader's optional auto-precompute step
    (see ``docs/UPDATE_STRATEGY.md``).
    """
    raise NotImplementedError("Stage 2 — see STAGES.md")


def check_inputs_available(
    inputs: list[str], conn: object, within: object = None
) -> bool:
    """Return True iff every ``metric_id`` in ``inputs`` has at least one usable measurement.

    If ``within`` is provided, restrict the check to measurements within
    ``within`` of "now" (subject to each metric's ``validity_window`` from
    ``hp.dim_metric`` when tighter). Empty ``inputs`` returns True trivially.
    """
    raise NotImplementedError("Stage 2 — see STAGES.md")


def list_unavailable(domain: str, conn: object) -> list[SignalSpec]:
    """Return the subset of :func:`list_by_domain` whose inputs are not all available.

    MCP uses this to build the ``missing_inputs_report`` it returns to the UI
    layer for user-facing "go get this lab" suggestions.
    """
    raise NotImplementedError("Stage 2 — see STAGES.md")
