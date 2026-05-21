"""Engine signal registry — the open boundary of Stage 2.

This module defines the data shape that signal functions register against.
Importing this module never imports any actual signal implementation.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SignalSpec:
    """One signal function's registration record.

    See parsers/CONTRACT.md for the parsers-side companion contract.
    See STAGES.md for the four-stage architecture this slots into.
    """

    name: str
    """Unique short identifier within the registry. Snake_case. Example: "ast_alt_ratio"."""

    domain: list[str]
    """One or more domain tags the signal serves. Used by MCP's list_by_domain
    discovery. Example: ["liver", "metabolic"]."""

    inputs: list[str]
    """Canonical metric_ids this signal needs as input. Example: ["lab:ast", "lab:alt"]."""

    output: str | None = None
    """Canonical metric_id this signal produces, or None for transient outputs.
    If set, MUST start with "derived:" per C-011. Example: "derived:ast_alt_ratio"."""

    priority: str = "normal"
    """One of "high" / "normal" / "low". MCP surfaces missing-input gaps to the
    user only for high-priority signals (per Scenario D in spec.md §6)."""

    auto_safe: bool = False
    """If True, the ingest loader may auto-precompute this signal after parsing
    when its inputs land in the new batch. Conservative default False — only
    derivations with super-low noise-introduction probability should opt in."""

    revision: str = "1"
    """Bump when the function's derivation logic materially changes. Stored in
    raw_payload of any persisted derived:* row, so a future `hpipe revalidate`
    command can identify stale outputs. See docs/UPDATE_STRATEGY.md."""

    fn: Callable | None = None
    """The actual function. Set by the @signal(...) decorator. None at definition
    time means the spec was declared without a function body (test-only)."""


REGISTRY: dict[str, SignalSpec] = {}
"""Module-level registry. Empty at import time; populated by @signal(...) decorators
when signal implementation modules are imported. Stage 2 implementation missions
will define those modules; this skeleton mission ships an empty registry."""


def signal(
    *,
    name: str,
    domain: list[str],
    inputs: list[str],
    output: str | None = None,
    priority: str = "normal",
    auto_safe: bool = False,
    revision: str = "1",
) -> Callable:
    """Register a signal function into REGISTRY.

    Usage:

        from premura.engine import signal

        @signal(name="ast_alt_ratio", domain=["liver", "metabolic"],
                inputs=["lab:ast", "lab:alt"], output="derived:ast_alt_ratio",
                priority="high", auto_safe=True, revision="1")
        def compute_ast_alt_ratio(conn):
            ...

    Re-registering the same `name` overwrites the previous entry. Stage 2
    implementation missions must not register two signals with the same `name`;
    reviewers catch collisions at PR time.
    """

    def deco(fn: Callable) -> Callable:
        REGISTRY[name] = SignalSpec(
            name=name,
            domain=domain,
            inputs=inputs,
            output=output,
            priority=priority,
            auto_safe=auto_safe,
            revision=revision,
            fn=fn,
        )
        return fn

    return deco
