"""Stage 4 — the interview-track registry + resolving-route safety rail.

The track registry locked by ``src/premura/ui/HUMAN_FACING.md``
§"The track registry" (ADR 0015 decision 3). First contact asks the user *what
direction* to look at — sleep, cardio, metabolic, stress, mental, gut, lab,
overview (STAGES.md §Interview) — and the answer is a routing decision that
calls the signal selector, never an "analyse everything at once" default. This
module is that set of directions as a **bounded, OPEN registry**, mirroring
:mod:`premura.ui.improvement_kinds` exactly (a frozen declaration +
:func:`register_track`, never a hardcoded switch or a closed enumeration —
DOCTRINE.md rule 2). The STAGES-8 ship as instances of the contract; a new
direction registers with no central edit.

**The health safety rail:** an interview direction that routes nowhere is a
dead end — the user is asked about a topic Premura cannot then analyse.
:func:`register_track` refuses any track whose ``signal_route`` does not
resolve to a registered signal selector. Because Stage 4 imports no engine code
(the layering rule: no ``hp.*`` reads, no direct engine/warehouse calls), the
resolver is **injected**: install one with :func:`set_route_resolver`. The
default resolver rejects everything, so an un-wired registry cannot silently
admit a dead end — the seeds register only *after* a real resolver is in place.

Runtime-registered tracks are **process-local and ephemeral**: the registry is
an in-memory module global that resets on restart, exactly like the improvement
kind registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InterviewTrack:
    """One interview direction — a functional id, its signal route, and the
    profile/context slots phase 2 must fill before it can run.

    ``track_id`` is a lowercase functional identifier (letters/digits/
    underscores), the same rule as :class:`premura.ui.roles.RoleDeclaration`'s
    ``role_id`` and :class:`premura.ui.improvement_kinds.ImprovementKind`'s
    ``kind_id``. ``signal_route`` is the signal-selector routing direction this
    track resolves to; the safety rail (see :func:`register_track`) refuses a
    track whose route does not resolve. ``required_slots`` names the profile/
    context slot keys the phase-2 interview flow must fill for this direction
    (empty when the direction needs no specific input).
    """

    track_id: str
    signal_route: str
    required_slots: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.track_id or not self.track_id.strip():
            raise ValueError("InterviewTrack requires a non-empty track_id")
        if not self.track_id.replace("_", "").isalnum() or self.track_id != self.track_id.lower():
            raise ValueError(
                "track_id must be a lowercase functional identifier "
                f"(letters/digits/underscores), got {self.track_id!r}"
            )
        if not self.signal_route or not self.signal_route.strip():
            raise ValueError(f"InterviewTrack {self.track_id!r} requires a non-empty signal_route")


_REGISTRY: dict[str, InterviewTrack] = {}


def _reject_all(_route: str) -> bool:
    """Default route resolver — rejects everything so an un-wired registry
    cannot silently admit a dead-end direction."""
    return False


_route_resolver: Callable[[str], bool] = _reject_all
_seeded = False


def set_route_resolver(resolver: Callable[[str], bool], *, seed: bool = True) -> None:
    """Install the signal-selector route resolver (Stage 4 imports no engine, so
    the resolver is injected). Seeds the STAGES-8 lazily on first install, now
    that routes can resolve; re-installing a resolver never re-seeds.
    """
    global _route_resolver, _seeded
    _route_resolver = resolver
    if seed and not _seeded:
        _seed_stages8()
        _seeded = True


def register_track(track: InterviewTrack) -> InterviewTrack:
    """Add one interview track to the registry (the rule for adding a direction).

    Validates the declaration, refuses a duplicate ``track_id`` (mirroring
    :func:`premura.ui.improvement_kinds.register_kind`), then enforces the
    safety rail: the track's ``signal_route`` must resolve to a registered
    signal selector, or registration is refused with a message naming the
    unresolvable route.
    """
    track.validate()
    if track.track_id in _REGISTRY:
        raise ValueError(f"interview track {track.track_id!r} is already registered")
    if not _route_resolver(track.signal_route):
        raise ValueError(
            f"interview track {track.track_id!r} signal_route {track.signal_route!r} "
            "does not resolve to a registered signal selector (dead-end direction refused)"
        )
    _REGISTRY[track.track_id] = track
    return track


def get_track(track_id: str) -> InterviewTrack | None:
    return _REGISTRY.get(track_id)


def known_track_ids() -> frozenset[str]:
    """The live set of registered track ids — never a fixed vocabulary."""
    return frozenset(_REGISTRY)


def list_tracks() -> list[InterviewTrack]:
    """All registered tracks, stable by ``track_id``."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


# --------------------------------------------------------------------------- #
# The STAGES-8 interview directions (STAGES.md §Interview) — instances of the
# contract, not a closed list. Seeded only once a resolver is installed, so an
# un-wired registry admits nothing. ``required_slots`` is left for the phase-2
# interview flow to fill per direction.
# --------------------------------------------------------------------------- #

_STAGES8 = (
    "sleep",
    "cardio",
    "metabolic",
    "stress",
    "mental",
    "gut",
    "lab",
    "overview",
)


# track_id is interview vocabulary (STAGES.md); the route targets engine-domain
# vocabulary. They diverge only for cardio (signals register "cardiovascular").
_STAGES8_ROUTE = {"cardio": "cardiovascular"}


def signal_route_for(direction: str) -> str:
    """The ``signal_selector:`` route for a STAGES-8 direction, bridging interview
    vocabulary to the engine signal domain (they diverge only for ``cardio``).
    Shared by both seeders so they cannot drift."""
    return f"signal_selector:{_STAGES8_ROUTE.get(direction, direction)}"


def _seed_stages8() -> None:
    for direction in _STAGES8:
        register_track(
            InterviewTrack(track_id=direction, signal_route=signal_route_for(direction))
        )


__all__ = [
    "InterviewTrack",
    "get_track",
    "known_track_ids",
    "list_tracks",
    "register_track",
    "set_route_resolver",
    "signal_route_for",
]
