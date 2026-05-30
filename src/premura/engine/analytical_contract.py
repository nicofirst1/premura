"""Stage 3 — the analytical-tool contract (the bounded extension seam).

This module is the **open boundary** of Premura's first deterministic
analytical layer. It defines *the rule for adding an analytical tool* — a
declared tool descriptor, a registry, a shared dispatch path, a mandatory
result envelope, a first-class refusal outcome, and the closed confound /
question vocabularies — **not** a catalog of statistics. Adding a future tool
is registration against this contract, never a new branch in a dispatcher.

It is the structural twin of the Stage 2 signal and resolver registries in
:mod:`premura.engine._registry`: contributors learn one extension pattern.
Importing this module never imports any tool implementation; the registry is
empty until a tool opts in via :func:`analytical_tool`.

Design constraints (see ``docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md``):

* **MCP-agnostic and warehouse-agnostic.** This module imports nothing from the
  MCP layer and nothing from the warehouse/DuckDB layer. The result envelopes
  are plain frozen dataclasses that serialize to JSON-safe primitives through
  ``to_dict()``. No network access is reachable from here.
* **Closed, runtime-owned vocabularies.** The confound keys (D5) and analytical
  question types (D4) are closed sets owned and enforced by this contract.
  Values outside them are rejected by validation. Agents branch on these
  machine-readable keys instead of parsing prose.
* **Refusal is a first-class outcome.** Stale, inadmissible, insufficient, and
  out-of-bounds inputs return a distinct machine-readable reason and *no*
  estimate. A non-refusal outcome must carry estimate plus required validity
  metadata. The two are kept distinct so an agent never has to guess.

This module deliberately keeps its public surface small. Helpers used only to
build envelopes stay private; the exported names are the contract a tool author
and a reviewer need, nothing more.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Closed runtime vocabularies (research note D4 + D5)
# ---------------------------------------------------------------------------


class AnalyticalQuestionType(StrEnum):
    """The closed set of reviewed analytical question types (research note D4).

    These are runtime vocabulary entries, **not** prose suggestions and **not**
    user-facing labels. Each value mirrors a first-class analytical
    :class:`premura.engine.policies.QuestionType` member of the same name: the
    admissibility evaluator gates these questions on their *own* question type
    (with their own freshness/sufficiency), never by collapsing them onto a
    descriptive shape such as ``recent_trend`` — that collapse was the design
    research note D4 explicitly rejected because it hides the analytical
    sufficiency requirements. This enum is the contract-facing vocabulary tool
    authors declare against; the input-preparation layer converts it to the
    matching policy ``QuestionType`` before evaluation.

    Adding a value here is a reviewed change to the closed vocabulary, the same
    way confound keys are added.
    """

    LEVEL_SHIFT_DETECTION = "level_shift_detection"
    """For the ``change_point`` tool — a single-level-shift detector."""

    SMOOTHED_PATTERN = "smoothed_pattern"
    """For the smoothed-average tool — a trailing rolling mean."""


class ConfoundKey(StrEnum):
    """The closed, committed confound vocabulary (research note D5).

    Every non-refusal analytical result carries a confound checklist drawn from
    this set. Keys outside it are rejected by :func:`validate_confound_keys`.
    The research note may *propose* keys; this contract *owns* the committed set
    and enforces it. Agents cannot mint values like "probably fine" or collapse
    distinct risks into a generic quality label.
    """

    HIGH_IMPUTATION = "high_imputation"
    """Too much of the usable series was filled/imputed."""

    LOW_SAMPLE_SIZE = "low_sample_size"
    """Usable observations are near the minimum for the method."""

    SHORT_OVERLAP_WINDOW = "short_overlap_window"
    """The admissible window is short relative to what the question needs."""

    PARAMETER_AT_LIMIT = "parameter_at_limit"
    """A requested parameter sits at an allowed bound."""

    VENDOR_ESTIMATE_INPUT = "vendor_estimate_input"
    """An input value is a vendor-derived estimate, not a primary measurement."""

    TEMPORAL_AUTOCORRELATION = "temporal_autocorrelation"
    """Successive observations are correlated, so apparent stability or change
    may be overstated."""

    LIFE_EVENT_SENSITIVE = "life_event_sensitive"
    """The metric's level is easily shifted by ordinary life events (travel,
    illness, training change), so a detected shift is not evidence of cause."""

    METHOD_UNCERTAINTY_UNAVAILABLE = "method_uncertainty_unavailable"
    """The method cannot express a natural uncertainty interval (the
    smoothed-average case in research note D3)."""


CONFOUND_KEYS: frozenset[str] = frozenset(key.value for key in ConfoundKey)
"""The committed confound vocabulary as a flat frozenset of strings.

This is the authoritative closed set validation enforces. It mirrors
:class:`ConfoundKey`; both are kept in sync because the frozenset is derived
from the enum.
"""

ANALYTICAL_QUESTION_TYPES: frozenset[str] = frozenset(qt.value for qt in AnalyticalQuestionType)
"""The committed analytical question-type vocabulary as a flat frozenset."""


class AnalyticalStatus(StrEnum):
    """The outcome status of an analytical run.

    ``available`` carries an estimate and required validity metadata.
    ``refused`` carries a :class:`RefusalOutcome` and **no** estimate.
    """

    AVAILABLE = "available"
    REFUSED = "refused"


# ---------------------------------------------------------------------------
# Tool descriptor + registry (T005) — the bounded extension point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalyticalToolSpec:
    """One analytical tool's registration record (the ``AnalyticalToolSpec``).

    Declaring this and registering it is the *entire* extension contract:
    dispatch goes through :func:`dispatch`, which never grows a per-tool branch.

    Validation (:meth:`validate`) enforces the closed vocabularies at
    registration time so a malformed descriptor is rejected before it can be
    invoked.
    """

    name: str
    """Unique snake_case tool name within the analytical registry. Example:
    ``"change_point"``."""

    description: str
    """Plain-language description for agents and reviewers."""

    input_shape: str
    """Declared input-series requirement, e.g. the engine-owned single ordered
    series shape passed after admissibility evaluation. A short identifier the
    contract documents, not a free-form sentence the dispatcher parses."""

    parameters: tuple[str, ...]
    """Supported parameter names. Bounds, defaults, and refusal behavior live in
    the tool implementation; the descriptor declares which names are accepted so
    reviewers can see the surface."""

    result_kind: str
    """Declared result shape produced by the tool, e.g.
    ``"change_point_estimate"``. Documentation/discovery metadata only."""

    confound_keys: tuple[str, ...]
    """Closed-vocabulary confound keys this tool may emit. Each MUST be a member
    of :data:`CONFOUND_KEYS`; validated at registration."""

    question_type: AnalyticalQuestionType
    """The reviewed analytical question type this tool answers. ``change_point``
    uses :attr:`AnalyticalQuestionType.LEVEL_SHIFT_DETECTION`; the smoothed
    average uses :attr:`AnalyticalQuestionType.SMOOTHED_PATTERN`."""

    revision: str = "1"
    """Version string for reviewable method changes. Bump when the method's
    computation materially changes."""

    fn: Callable[..., AnalyticalOutcome] | None = None
    """The actual tool function. Set by the :func:`analytical_tool` decorator.
    ``None`` at definition time means the spec was declared without a function
    body (test-only). A tool with no ``fn`` cannot be dispatched."""

    def validate(self) -> AnalyticalToolSpec:
        """Reject a malformed descriptor (T007).

        Raises :class:`ValueError` on: empty name, non-snake_case-ish name,
        confound keys outside the committed vocabulary, or duplicate confound
        keys. Returns ``self`` for fluent use.
        """
        if not self.name or not self.name.strip():
            raise ValueError("AnalyticalToolSpec.name must be a non-empty string")
        if self.name != self.name.strip() or " " in self.name:
            raise ValueError(
                f"AnalyticalToolSpec.name {self.name!r} must be a bare snake_case token"
            )
        if not self.description or not self.description.strip():
            raise ValueError(f"AnalyticalToolSpec.description for {self.name!r} must be non-empty")
        # Closed-vocabulary enforcement: a descriptor may only promise to emit
        # confound keys the contract owns.
        validate_confound_keys(self.confound_keys, context=f"tool {self.name!r}")
        if len(set(self.confound_keys)) != len(self.confound_keys):
            raise ValueError(f"AnalyticalToolSpec {self.name!r} has duplicate confound_keys")
        return self


REGISTRY: dict[str, AnalyticalToolSpec] = {}
"""Module-level analytical registry. Empty at import time; populated by
:func:`analytical_tool` decorators when tool implementation modules are
imported. This contract mission ships an empty registry; the proof tools
(``change_point`` and the smoothed average) register here in later work."""


def analytical_tool(
    *,
    name: str,
    description: str,
    input_shape: str,
    parameters: tuple[str, ...] | list[str],
    result_kind: str,
    confound_keys: tuple[str, ...] | list[str],
    question_type: AnalyticalQuestionType,
    revision: str = "1",
) -> Callable[[Callable[..., AnalyticalOutcome]], Callable[..., AnalyticalOutcome]]:
    """Register an analytical tool function into :data:`REGISTRY`.

    The structural twin of :func:`premura.engine.signal` and
    :func:`premura.engine.resolver`. Usage::

        from premura.engine.analytical_contract import (
            analytical_tool, AnalyticalQuestionType,
        )

        @analytical_tool(
            name="change_point",
            description="Single-level-shift detector over one ordered series.",
            input_shape="single_ordered_series",
            parameters=("min_side_observations",),
            result_kind="change_point_estimate",
            confound_keys=("low_sample_size", "life_event_sensitive"),
            question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        )
        def run_change_point(series, **params):
            ...

    The descriptor is validated at registration, so a malformed tool is
    rejected immediately. Re-registering the same ``name`` overwrites the prior
    entry ("last write wins", matching the signal/resolver convention);
    reviewers catch accidental collisions at PR time. The function is returned
    unchanged so it can still be unit-tested directly.
    """

    def deco(
        fn: Callable[..., AnalyticalOutcome],
    ) -> Callable[..., AnalyticalOutcome]:
        spec = AnalyticalToolSpec(
            name=name,
            description=description,
            input_shape=input_shape,
            parameters=tuple(parameters),
            result_kind=result_kind,
            confound_keys=tuple(confound_keys),
            question_type=question_type,
            revision=revision,
            fn=fn,
        ).validate()
        REGISTRY[spec.name] = spec
        return fn

    return deco


def dispatch(tool_name: str, *args: Any, **kwargs: Any) -> AnalyticalOutcome:
    """Invoke a registered tool through the single shared dispatch path.

    This is the only invocation entrypoint, and it deliberately has **no
    per-tool branch**: it looks up the spec, calls its ``fn``, and returns the
    outcome. Adding a tool is registration against this contract, never an edit
    here.

    Raises :class:`KeyError` if ``tool_name`` is not registered, and
    :class:`RuntimeError` if the spec was registered without a function body.
    """
    if tool_name not in REGISTRY:
        raise KeyError(tool_name)
    spec = REGISTRY[tool_name]
    if spec.fn is None:
        raise RuntimeError(f"analytical tool {tool_name!r} is registered without an implementation")
    return spec.fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# Result / refusal / confound model types (T006)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfoundEntry:
    """One entry in a result's confound checklist (closed-vocabulary key + note).

    ``key`` MUST be a member of :data:`CONFOUND_KEYS`; this is enforced when the
    surrounding envelope is validated. ``detail`` is an optional concise
    plain-language note for the agent to surface — never a free-form caveat that
    replaces the machine-readable key.
    """

    key: ConfoundKey
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key.value, "detail": self.detail}


@dataclass(frozen=True)
class Uncertainty:
    """The method-defined uncertainty payload, or an explicit unavailable marker.

    Some methods (the trailing smoothed average, research note D3) have no
    natural confidence interval. Rather than fabricating a band, such a method
    sets ``available=False`` and pairs it with the
    ``method_uncertainty_unavailable`` confound key. When ``available`` is True,
    ``payload`` carries the method-specific, JSON-safe support description (for
    ``change_point``, the support around the selected split — never a p-value).
    """

    available: bool
    payload: Mapping[str, Any] | None = None

    @classmethod
    def unavailable(cls) -> Uncertainty:
        """The explicit "uncertainty is not defined for this method" marker."""
        return cls(available=False, payload=None)

    def validate(self) -> Uncertainty:
        if self.available and self.payload is None:
            raise ValueError("Uncertainty.payload must be present when available is True")
        if not self.available and self.payload is not None:
            raise ValueError("Uncertainty.payload must be None when available is False")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "payload": dict(self.payload) if self.payload is not None else None,
        }


@dataclass(frozen=True)
class RefusalOutcome:
    """Explains why an analytical request cannot honestly run (a first-class outcome).

    A refusal carries a distinct machine-readable ``reason`` so an agent can
    branch without parsing prose, a concise plain-language ``message``, and the
    relevant input/parameter identifiers when applicable. A refusal NEVER
    carries an estimate — that invariant is enforced at the envelope level by
    :meth:`AnalyticalResultEnvelope.validate`.
    """

    reason: str
    message: str
    missing_or_bad_inputs: tuple[str, ...] = ()
    parameter_name: str | None = None

    def validate(self) -> RefusalOutcome:
        if not self.reason or not self.reason.strip():
            raise ValueError("RefusalOutcome.reason must be a non-empty string")
        if not self.message or not self.message.strip():
            raise ValueError("RefusalOutcome.message must be a non-empty string")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "message": self.message,
            "missing_or_bad_inputs": list(self.missing_or_bad_inputs),
            "parameter_name": self.parameter_name,
        }


@dataclass(frozen=True)
class AnalyticalResultEnvelope:
    """The mandatory result envelope every analytical tool returns (T006).

    Exactly one of two shapes, distinguished by ``status``:

    * ``available`` — carries an ``estimate`` payload plus the required validity
      metadata (``validity_status``, ``is_imputed_pct``, ``sample_size``), an
      ``uncertainty`` behavior, and a closed-vocabulary ``confound_checklist``.
    * ``refused`` — carries a :class:`RefusalOutcome` and **no** estimate.

    The envelope is MCP-agnostic and warehouse-agnostic: ``estimate`` is any
    JSON-safe mapping the tool produces (e.g. a ``ChangePointEstimate`` rendered
    to primitives). :meth:`to_dict` returns only JSON-safe primitives, and
    repeated calls over the same constructed envelope are byte-stable.
    """

    tool_name: str
    status: AnalyticalStatus
    inputs: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)
    estimate: Mapping[str, Any] | None = None
    uncertainty: Uncertainty | None = None
    validity_status: str | None = None
    is_imputed_pct: float | None = None
    sample_size: int | None = None
    confound_checklist: tuple[ConfoundEntry, ...] = ()
    caveats: tuple[str, ...] = ()
    refusal: RefusalOutcome | None = None

    def validate(self) -> AnalyticalResultEnvelope:
        """Enforce the contract invariants (T007). Returns ``self``.

        Rejects:

        * a refusal envelope that carries an estimate (or lacks a refusal);
        * a non-refusal envelope missing required metadata or its uncertainty
          behavior;
        * any confound key outside the committed vocabulary;
        * an out-of-range ``is_imputed_pct``.
        """
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("AnalyticalResultEnvelope.tool_name must be non-empty")

        if self.status is AnalyticalStatus.REFUSED:
            if self.estimate is not None:
                raise ValueError("a refusal result must not include an estimate")
            if self.refusal is None:
                raise ValueError("a refusal result must include a RefusalOutcome")
            self.refusal.validate()
            # A refusal carries no validity metadata to validate, but any
            # confound entries present must still use the closed vocabulary.
            validate_confound_keys(
                tuple(entry.key.value for entry in self.confound_checklist),
                context=f"tool {self.tool_name!r}",
            )
            return self

        # status is AVAILABLE — a non-refusal result.
        if self.refusal is not None:
            raise ValueError("a non-refusal result must not carry a RefusalOutcome")
        if self.estimate is None:
            raise ValueError("a non-refusal result must include an estimate")
        missing = [
            field_name
            for field_name, value in (
                ("uncertainty", self.uncertainty),
                ("validity_status", self.validity_status),
                ("is_imputed_pct", self.is_imputed_pct),
                ("sample_size", self.sample_size),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                f"a non-refusal result is missing required metadata: {sorted(missing)}"
            )
        if self.is_imputed_pct is not None and not (0.0 <= self.is_imputed_pct <= 100.0):
            raise ValueError("AnalyticalResultEnvelope.is_imputed_pct must be in [0.0, 100.0]")
        if self.uncertainty is not None:
            self.uncertainty.validate()
        validate_confound_keys(
            tuple(entry.key.value for entry in self.confound_checklist),
            context=f"tool {self.tool_name!r}",
        )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "inputs": list(self.inputs),
            "parameters": dict(self.parameters),
            "estimate": dict(self.estimate) if self.estimate is not None else None,
            "uncertainty": (self.uncertainty.to_dict() if self.uncertainty is not None else None),
            "validity_status": self.validity_status,
            "is_imputed_pct": self.is_imputed_pct,
            "sample_size": self.sample_size,
            "confound_checklist": [entry.to_dict() for entry in self.confound_checklist],
            "caveats": list(self.caveats),
            "refusal": self.refusal.to_dict() if self.refusal is not None else None,
        }


# An analytical tool returns the mandatory envelope (available *or* refused).
AnalyticalOutcome = AnalyticalResultEnvelope


# ---------------------------------------------------------------------------
# Validation helpers (T007)
# ---------------------------------------------------------------------------


def validate_confound_keys(
    keys: tuple[str, ...] | list[str],
    *,
    context: str = "result",
) -> None:
    """Reject any confound key outside the committed vocabulary (T007).

    Raises :class:`ValueError` naming the unknown key(s) and ``context`` so the
    agent and reviewer can locate the offending tool or result. An empty
    checklist is valid.
    """
    unknown = [key for key in keys if key not in CONFOUND_KEYS]
    if unknown:
        raise ValueError(
            f"unknown confound key(s) {sorted(set(unknown))} in {context}; "
            f"committed vocabulary is {sorted(CONFOUND_KEYS)}"
        )


__all__ = [
    # Vocabularies
    "AnalyticalQuestionType",
    "ANALYTICAL_QUESTION_TYPES",
    "ConfoundKey",
    "CONFOUND_KEYS",
    "AnalyticalStatus",
    # Registry / dispatch (the extension seam)
    "AnalyticalToolSpec",
    "REGISTRY",
    "analytical_tool",
    "dispatch",
    # Result model
    "AnalyticalResultEnvelope",
    "AnalyticalOutcome",
    "RefusalOutcome",
    "ConfoundEntry",
    "Uncertainty",
    # Validation
    "validate_confound_keys",
]
