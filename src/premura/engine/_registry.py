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
    command can identify stale outputs. See docs/architecture/UPDATE_STRATEGY.md."""

    fn: Callable | None = None
    """The actual function. Set by the @signal(...) decorator. None at definition
    time means the spec was declared without a function body (test-only)."""

    # --- Additive Stage 2 contributor metadata (all OPTIONAL) ---------------
    # These fields exist so future grounded Stage 2 functions can declare what
    # they answer and how Stage 3 should surface caveats, WITHOUT changing the
    # core registration contract above. Existing built-in lab-ratio
    # registrations leave them at their defaults and do not churn.
    # See CONTRACT.md (this package) for what each field is for.

    question: str | None = None
    """Plain-English question the signal answers, for Stage 3 surfacing and
    review. Example: "What is my resting heart rate right now?". Optional;
    leave None for derivation-only signals like the lab ratios."""

    family: str | None = None
    """Shared result family this signal produces, or None for signals that do
    not use a result envelope (the lab ratios persist derived rows instead).
    One of :data:`RESULT_FAMILIES` when set: "status" / "trend" / "baseline" /
    "change". See premura.engine._results for the matching envelopes."""

    missing_input_hint: str | None = None
    """User-facing guidance Stage 3 can show when a required input is absent.
    Plain language, no diagnosis or external reference data. Example:
    "Connect a wearable that records resting heart rate to answer this." """

    caveat_summary: tuple[str, ...] = ()
    """Short, standing caveats Stage 3 may surface without inventing health
    claims. These are signal-level disclaimers (e.g. "vendor sleep stages are
    estimates"), distinct from the per-result ``caveats`` lists in
    premura.engine._results. Defaults to an empty tuple so existing
    registrations stay unchanged."""


RESULT_FAMILIES: frozenset[str] = frozenset({"status", "trend", "baseline", "change"})
"""The four logical result families this mission supports. A signal's
``family`` metadata, when set, must be one of these. Mirrors the result
envelopes in :mod:`premura.engine._results` and ``data-model.md``."""


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
    question: str | None = None,
    family: str | None = None,
    missing_input_hint: str | None = None,
    caveat_summary: tuple[str, ...] | list[str] = (),
) -> Callable:
    """Register a signal function into REGISTRY.

    Usage:

        from premura.engine import signal

        @signal(name="ast_alt_ratio", domain=["liver", "metabolic"],
                inputs=["lab:ast", "lab:alt"], output="derived:ast_alt_ratio",
                priority="high", auto_safe=True, revision="1")
        def compute_ast_alt_ratio(conn):
            ...

    The optional ``question``, ``family``, ``missing_input_hint`` and
    ``caveat_summary`` arguments are the additive Stage 2 contributor metadata
    described in CONTRACT.md. They default to "unset" so existing derivation
    signals (the lab ratios) need no churn. When ``family`` is provided it must
    be one of :data:`RESULT_FAMILIES`.

    Re-registering the same `name` overwrites the previous entry. Stage 2
    implementation missions must not register two signals with the same `name`;
    reviewers catch collisions at PR time.
    """
    if family is not None and family not in RESULT_FAMILIES:
        raise ValueError(
            f"signal {name!r} family {family!r} must be one of {sorted(RESULT_FAMILIES)}"
        )

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
            question=question,
            family=family,
            missing_input_hint=missing_input_hint,
            caveat_summary=tuple(caveat_summary),
        )
        return fn

    return deco
