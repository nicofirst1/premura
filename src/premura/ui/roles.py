"""Stage 4 — the operating-role declaration registry (OPERATING_ROLES.md).

Roles are **declarations in a bounded registry**, never a hardcoded router
switch: the router is this registry plus :func:`register_role` (the rule for
adding an entry). The orchestrator (the operating agent plus the thin
deterministic gate/trace layer, decision note 0013) reads these declarations
to know each role's job, allowed surfaces, handoff outputs, and boundaries.

The five reference roles ship as instances of the contract, not a closed
persona list — a new role registers a declaration with no central edit. The
orchestrator itself is not a role. This module is pure data + registry rules:
per the Stage 4 layering rule it reads no ``hp.*`` rows and calls no engine
code.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoleDeclaration:
    """One bounded runtime responsibility the orchestrator may dispatch.

    ``role_id`` is a functional id (never a persona name). ``surfaces`` names
    the governance surfaces / tool scopes the role may touch;``boundaries``
    states what it must not do (the assertion boundary). Both are prose
    contracts read by the operating agent — the deterministic layer enforces
    only the audit gate and the trace, not these scopes.
    """

    role_id: str
    job: str
    surfaces: tuple[str, ...] = field(default_factory=tuple)
    handoff_outputs: tuple[str, ...] = field(default_factory=tuple)
    boundaries: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.role_id or not self.role_id.strip():
            raise ValueError("RoleDeclaration requires a non-empty role_id")
        if not self.role_id.replace("_", "").isalnum() or self.role_id != self.role_id.lower():
            raise ValueError(
                "role_id must be a lowercase functional identifier "
                f"(letters/digits/underscores), got {self.role_id!r}"
            )
        if not self.job or not self.job.strip():
            raise ValueError(f"RoleDeclaration {self.role_id!r} requires a one-sentence job")

    def to_dict(self) -> dict[str, object]:
        return {
            "role_id": self.role_id,
            "job": self.job,
            "surfaces": list(self.surfaces),
            "handoff_outputs": list(self.handoff_outputs),
            "boundaries": list(self.boundaries),
        }


_REGISTRY: dict[str, RoleDeclaration] = {}


def register_role(declaration: RoleDeclaration) -> RoleDeclaration:
    """Add one role declaration to the registry (the rule for adding a role).

    Validates the declaration and refuses a duplicate ``role_id`` — replacing
    an existing role is an explicit code change, not a silent re-register.
    """
    declaration.validate()
    if declaration.role_id in _REGISTRY:
        raise ValueError(f"role {declaration.role_id!r} is already registered")
    _REGISTRY[declaration.role_id] = declaration
    return declaration


def get_role(role_id: str) -> RoleDeclaration | None:
    return _REGISTRY.get(role_id)


def list_roles() -> list[RoleDeclaration]:
    """All registered declarations, stable by role_id."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


# --------------------------------------------------------------------------- #
# The five reference roles (instances of the contract, not a closed list).
# Jobs and boundaries are the ones the promoted spec adopts from the draft.
# --------------------------------------------------------------------------- #

register_role(
    RoleDeclaration(
        role_id="ingest",
        job="Load source artifacts and surface unsupported or unmapped source data.",
        surfaces=("ingest seams (parsers -> loader / persist_intake_batch)",),
        handoff_outputs=("load report", "unmapped_metrics", "skipped_rows", "parser gaps"),
        boundaries=(
            "writes warehouse data only through ingest seams",
            "never invents a metric_id outside the decision tree",
        ),
    )
)

register_role(
    RoleDeclaration(
        role_id="analysis",
        job="Read warehouse signals and produce bounded descriptive/comparative results.",
        surfaces=("default MCP analytical/signal tools (read-only)",),
        handoff_outputs=("result envelopes", "refusals", "research-trace session refs"),
        boundaries=(
            "read-only warehouse access",
            "no diagnosis, causation, or unsupported statistical claims",
        ),
    )
)

register_role(
    RoleDeclaration(
        role_id="human_facing",
        job=(
            "Ask minimal/optional clarifying questions, explain results, and present "
            "blessed answers and share packets."
        ),
        surfaces=("conversation", "present_answer gate", "capture tools with consent"),
        handoff_outputs=("draft answers", "user decisions", "clarified goals"),
        boundaries=(
            "must not silently store lifestyle context",
            "final health-interpreting answers go through present_answer",
        ),
    )
)

register_role(
    RoleDeclaration(
        role_id="answer_audit",
        job="Inspect a draft answer against trace and evidence before presentation.",
        surfaces=("answer_audit tool (read-only over trace + draft)",),
        handoff_outputs=("verdict", "required revisions"),
        boundaries=(
            "creates no new evidence",
            "does not rerun analysis or PubMed searches by default",
        ),
    )
)

register_role(
    RoleDeclaration(
        role_id="improvement_scan",
        job="Turn runtime friction into private, sanitized improvement candidates.",
        surfaces=("local improvement queue (later slice)",),
        handoff_outputs=("improvement candidates",),
        boundaries=(
            "writes sanitized candidates only",
            "no public GitHub content without a reviewed share packet",
        ),
    )
)
