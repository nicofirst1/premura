"""Stage 4 — the improvement-item **kind** registry (OPERATING_ROLES.md).

The runtime improvement queue's item shape (`src/premura/ui/OPERATING_ROLES.md`
§"Improvement scan, queue, sharing") names six seeded
``kind`` values plus "the documented rule for
adding one" — never a closed enumeration (DOCTRINE.md rule 2: *design a level
above — guide, don't enumerate*). This module is that rule made concrete: a
bounded, OPEN registry, mirroring :mod:`premura.ui.roles` exactly (a
declaration dataclass + :func:`register_kind`, never a hardcoded switch or a
``frozenset`` baked into the store).

:func:`premura.mcp.server.improvement_queue_record` validates a ``kind``
against this registry's **live** contents, not a fixed vocabulary — so a new
kind is added by calling :func:`register_kind` (directly, or via that MCP
tool's ``kind_description`` auto-register path), with no central edit to this
module or to the store. The seeded six are examples of the contract, not a
closed persona-style list, exactly like the five reference roles in
:mod:`premura.ui.roles`.

Runtime-registered kinds are **process-local and ephemeral**: the registry is
an in-memory module global that resets to the seeded six on restart, while
recorded items keep their ``kind`` string in the session log. Re-describing a
kind next session is one ``kind_description`` away; persistent kind storage
is deliberately deferred until a consumer needs it.

Per the Stage 4 layering rule this module is pure data + registry rules: it
reads no ``hp.*`` rows and calls no engine code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImprovementKind:
    """One registered improvement-item ``kind`` — an id plus a short description.

    ``kind_id`` is a functional identifier (lowercase letters/digits/
    underscores, mirroring :class:`premura.ui.roles.RoleDeclaration`'s
    ``role_id`` rule). ``description`` is the short prose a new kind must
    carry (the draft's "a short description" requirement) so a future reader
    can tell what the kind means without reverse-engineering usage.
    """

    kind_id: str
    description: str

    def validate(self) -> None:
        if not self.kind_id or not self.kind_id.strip():
            raise ValueError("ImprovementKind requires a non-empty kind_id")
        if not self.kind_id.replace("_", "").isalnum() or self.kind_id != self.kind_id.lower():
            raise ValueError(
                "kind_id must be a lowercase functional identifier "
                f"(letters/digits/underscores), got {self.kind_id!r}"
            )
        if not self.description or not self.description.strip():
            raise ValueError(
                f"ImprovementKind {self.kind_id!r} requires a short, non-empty description"
            )


_REGISTRY: dict[str, ImprovementKind] = {}


def register_kind(kind: ImprovementKind) -> ImprovementKind:
    """Add one improvement kind to the registry (the rule for adding a kind).

    Validates the declaration and refuses a duplicate ``kind_id`` — replacing
    an existing kind's description is an explicit code change (or an explicit
    re-registration by a caller that first removes the old entry), never a
    silent overwrite.
    """
    kind.validate()
    if kind.kind_id in _REGISTRY:
        raise ValueError(f"improvement kind {kind.kind_id!r} is already registered")
    _REGISTRY[kind.kind_id] = kind
    return kind


def get_kind(kind_id: str) -> ImprovementKind | None:
    return _REGISTRY.get(kind_id)


def known_kind_ids() -> frozenset[str]:
    """The live set of registered kind ids — never a fixed vocabulary."""
    return frozenset(_REGISTRY)


def list_kinds() -> list[ImprovementKind]:
    """All registered kinds, stable by ``kind_id``."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


# --------------------------------------------------------------------------- #
# The six seeded kinds (draft doc "Seeded kinds") — examples of the contract,
# not a closed list. A new kind registers with a short description and needs
# no edit here.
# --------------------------------------------------------------------------- #

register_kind(
    ImprovementKind(
        "parser_gap",
        "An unsupported source, unmapped field, or parser limitation surfaced during ingest.",
    )
)
register_kind(
    ImprovementKind(
        "analysis_gap",
        "A question the analytical surface cannot answer yet (missing signal/tool/capability).",
    )
)
register_kind(
    ImprovementKind(
        "teaching_gap",
        "A point where the human needed clearer explanation than the agent could give.",
    )
)
register_kind(
    ImprovementKind(
        "workflow_gap",
        "Friction in how roles hand off or how the orchestrator sequences work.",
    )
)
register_kind(
    ImprovementKind(
        "docs_gap",
        "Missing, stale, or contradictory documentation discovered during operation.",
    )
)
register_kind(
    ImprovementKind(
        "other",
        "A recurring gap that does not fit the other seeded kinds.",
    )
)


__all__ = [
    "ImprovementKind",
    "get_kind",
    "known_kind_ids",
    "list_kinds",
    "register_kind",
]
