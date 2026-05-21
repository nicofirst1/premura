"""Stage 3 - MCP: the model-context-protocol surface for Premura.

This package is the importable home for the third stage of the four-stage
architecture (parsers → engine → MCP → UI). Stage 3 is the read-only
agent-facing query layer: it exposes signal results to MCP-aware tools by
delegating to the Stage 2 engine, not by touching the warehouse tables. In
particular, MCP code queries ``engine.list_by_domain`` (and the related
``engine.list_unavailable`` / ``engine.compute`` helpers) to discover which
signals are relevant for a user-selected health direction, and surfaces only
those signal results to MCP clients.

The hard layering rule for this stage is: MCP "never reads hp.fact_measurement directly".
Raw measurement access stays inside the Stage 2 engine; Stage 3 consumes
signal records and missing-input reports through the engine API and nothing
else. Future implementation missions wire this stub up to real MCP servers;
Phase 1 ships only the stage's importable name and a stub entry point.
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
