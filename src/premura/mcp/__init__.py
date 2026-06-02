"""Stage 3 - MCP: the model-context-protocol surface for Premura.

This package is the importable home for the third stage of the four-stage
architecture (parsers → engine → MCP → UI). Stage 3 is the read-only
agent-facing query layer: it exposes signal results to MCP-aware tools by
delegating to the Stage 2 engine, not by touching the warehouse tables.

The hard layering rule for this stage is: MCP "never reads hp.fact_measurement directly".
Raw measurement access stays inside the Stage 2 engine; Stage 3 consumes
signal records and missing-input reports through the engine API and nothing
else.

Two entrypoints are provided:

* **Default surface** (``premura-mcp``) — the fully validity-gated agent-safe
  surface.  All eight tools (``list_metrics``, ``metric_summary``, and the six
  signal-backed tools) delegate entirely to the Stage 2 engine.  The
  ``query_warehouse`` escape hatch is intentionally absent; agents should use
  the signal-backed tools and catalog helpers.

* **Operator surface** (``premura-mcp-operator``) — lower-guarantee expert mode
  intended for operator/developer use only, **not** for autonomous agent
  consumption without explicit user approval.  Adds ``query_warehouse`` on top of
  the full default tool set.  No Stage 2 validity guarantees apply to results
  returned by ``query_warehouse``; callers own all result interpretation.

See ``docs/building/adr/0004-stage3-operator-entrypoint.md`` for the decision record.
"""

from __future__ import annotations

__all__ = ["register_tools"]


def register_tools(server: object, domains: list[str] | None = None) -> None:
    """Register Premura's read-only signal tools on an MCP ``server``.

    Phase 1 stub. The eventual implementation iterates over
    ``engine.list_by_domain(domain)`` for each entry in ``domains`` (or every
    known domain when ``domains is None``) and exposes each
    :class:`~premura.engine.SignalSpec` as an MCP tool that delegates back to
    ``engine.compute``. Raises :class:`NotImplementedError` until that
    mission lands.
    """
    raise NotImplementedError(
        "register_tools is a Phase 1 stub; the Stage 3 MCP wiring ships in "
        "a later implementation mission."
    )
