"""Stage 3 — the public analytical *facade* (WP05).

This module is the stable, MCP-facing entry point onto the Stage 3 analytical
layer. It exposes exactly three narrow capabilities over the WP02 contract:

* :func:`load_builtin_analytical_tools` — statically import the in-tree
  built-in analytical tool module(s) so their
  :func:`~premura.engine.analytical_contract.analytical_tool` decorators
  populate the shared ``REGISTRY``.
* :func:`list_analytical_tools` — list the registered tool specs (for MCP
  tool-exposure and tests), loading the built-ins first.
* :func:`invoke_analytical_tool` — invoke a tool **by name** through the single
  shared dispatch path, loading the built-ins first.

It deliberately has **no per-tool branch** of its own:
:func:`invoke_analytical_tool` always defers to
:func:`premura.engine.analytical_contract.dispatch`, which itself looks up the
spec and calls its ``fn`` with no ``if tool == ...`` ladder. Adding a future
tool is two reviewed edits — register it against the contract (the
``@analytical_tool`` decorator) and, if it lives in a new module, append that
module's dotted name to :data:`_BUILTIN_ANALYTICAL_MODULES`. It is **never** an
edit to a dispatch branch here.

Static loading, not scanning. The built-ins are loaded by importing a small,
explicit, in-tree list of module names — exactly the posture the Stage 2 engine
uses for its built-in signal and resolver modules
(:data:`premura.engine._BUILTIN_SIGNAL_MODULES`). There is **no filesystem
scan, no plugin entry point, and no dynamic discovery**: a reviewer can read the
full set of built-in tools from one tuple.

MCP-agnostic and warehouse-agnostic. Like the contract it fronts, this module
imports nothing from the MCP layer and nothing from the warehouse/DuckDB layer.
The objects it returns (:class:`AnalyticalResultEnvelope`,
:class:`AnalyticalToolSpec`, :class:`RefusalOutcome`) serialize to JSON-safe
primitives through their ``to_dict()`` methods; no network access is reachable
from here.
"""

from __future__ import annotations

from importlib import import_module

from premura.engine.analytical_contract import (
    REGISTRY,
    AnalyticalOutcome,
    AnalyticalToolSpec,
    dispatch,
)

__all__ = [
    "load_builtin_analytical_tools",
    "list_analytical_tools",
    "invoke_analytical_tool",
]

# Static list of built-in analytical tool modules, in load order. Each module
# registers its tools as a side effect of import via the ``@analytical_tool``
# decorator from :mod:`premura.engine.analytical_contract`. Importing this
# facade module does NOT import any of these — they are loaded lazily by
# :func:`load_builtin_analytical_tools` the first time the public surface needs
# the built-in tools.
#
# This mirrors :data:`premura.engine._BUILTIN_SIGNAL_MODULES` and
# :data:`premura.engine._BUILTIN_RESOLVER_MODULES`: adding a future built-in
# analytical tool that lives in a new module means appending its dotted name
# here — no filesystem scanning, no plugin entry points, no dispatch branch.
_BUILTIN_ANALYTICAL_MODULES: tuple[str, ...] = ("premura.engine.analytical_tools",)

# The names the built-in modules are expected to register. Used to decide
# whether a reload is needed and is intentionally decoupled from ``REGISTRY``
# truthiness: a test may register a custom tool before the first load, and that
# must NOT be mistaken for "built-ins already loaded".
_BUILTIN_ANALYTICAL_NAMES: frozenset[str] = frozenset(
    {
        "change_point",
        "smoothed_average",
    }
)

# Tracks whether the built-in analytical modules have been imported and
# registered. Flipped to ``True`` only after every module in
# :data:`_BUILTIN_ANALYTICAL_MODULES` imports without error, so a failed import
# does not leave the flag wrongly true.
_BUILTINS_LOADED: bool = False


def load_builtin_analytical_tools() -> None:
    """Statically import the built-in analytical tool module(s).

    Importing each module in :data:`_BUILTIN_ANALYTICAL_MODULES` runs its
    ``@analytical_tool`` decorators, which populate the shared
    :data:`~premura.engine.analytical_contract.REGISTRY`. This is a **static
    import of an explicit, in-tree module list**, not a filesystem scan or
    plugin-discovery step.

    Idempotent: the ``_BUILTINS_LOADED`` flag short-circuits subsequent calls.
    The flag is decoupled from ``REGISTRY`` truthiness, so a custom tool
    registered before the first load is never mistaken for the built-ins, and a
    cleared registry (e.g. a test that mutated it) triggers a reload.
    """
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED and _BUILTIN_ANALYTICAL_NAMES <= set(REGISTRY):
        return
    for module_name in _BUILTIN_ANALYTICAL_MODULES:
        import_module(module_name)
    # Only mark loaded after every module imported without error.
    _BUILTINS_LOADED = True


def list_analytical_tools() -> list[AnalyticalToolSpec]:
    """Return every registered analytical tool spec (built-ins loaded first).

    The MCP layer and tests use this to discover which analytical tools exist
    and read their declared surface (name, parameters, question type, confound
    keys) without poking the registry dict directly. The order follows
    insertion order of :data:`~premura.engine.analytical_contract.REGISTRY`.
    """
    load_builtin_analytical_tools()
    return list(REGISTRY.values())


def invoke_analytical_tool(tool_name: str, *args: object, **kwargs: object) -> AnalyticalOutcome:
    """Invoke a registered analytical tool by name through shared dispatch.

    This is the single public invocation entry point MCP/WP06 depends on. It
    loads the built-in tools, then defers to
    :func:`premura.engine.analytical_contract.dispatch` — the one shared
    dispatch path, which has **no per-tool branch**. This facade adds none
    either: it neither special-cases any tool name nor inspects the outcome.

    Raises :class:`KeyError` if ``tool_name`` is not registered, and
    :class:`RuntimeError` if the spec was registered without an implementation —
    the same clear public errors :func:`dispatch` raises. (An *admissibility*
    or *parameter* problem is not an error: a tool returns a refusal envelope
    for that, distinct from an unknown-name ``KeyError``.)
    """
    load_builtin_analytical_tools()
    return dispatch(tool_name, *args, **kwargs)
