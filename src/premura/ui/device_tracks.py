"""Stage 4 — the device-interview registry + resolving-parser safety rail.

The device branch of first contact. Where :mod:`premura.ui.interview_tracks`
asks the human *what direction* they want to look at, this asks *what devices /
data they have* and guides collection ("Android? -> back up Health Connect ->
sleep data"; "Garmin? -> here is the data export"). It is the interview-track
pattern pointed at the **ingest** side: a bounded, OPEN registry
(:func:`register_device_track`, never a hardcoded switch) whose members each
name a collection hint and the parser ``source_kind`` their data lands in.

**The health safety rail:** guiding a human to gather data Premura has no parser
for is a dead end - they collect an export nothing can read. :func:`register_device_track`
refuses any track whose ``source_kind`` does not resolve to a registered parser.
Because Stage 4 imports no ingest code (the layering rule), the resolver is
**injected**: install one with :func:`set_parser_resolver`. The default resolver
rejects everything, so an un-wired registry cannot silently admit a dead end -
the seeds register only *after* a real resolver is in place.

Runtime-registered tracks are **process-local and ephemeral**: the registry is
an in-memory module global that resets on restart, exactly like the interview
track registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeviceTrack:
    """One device/data source the human may have - its id, the parser
    ``source_kind`` its export lands in, and how to collect it.

    ``track_id`` is a lowercase functional identifier (letters/digits/
    underscores), the same rule as :class:`premura.ui.interview_tracks.InterviewTrack`'s
    ``track_id``. ``source_kind`` is the parser this data resolves to; the safety
    rail (see :func:`register_device_track`) refuses a track whose source_kind is
    not a registered parser. ``collection_hint`` is the short, human-facing prose
    telling the person where/how to gather the export (the whole point of the
    device branch). ``required_slots`` names any profile/context slot keys the
    collection step depends on (usually empty).
    """

    track_id: str
    source_kind: str
    collection_hint: str
    required_slots: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.track_id or not self.track_id.strip():
            raise ValueError("DeviceTrack requires a non-empty track_id")
        if not self.track_id.replace("_", "").isalnum() or self.track_id != self.track_id.lower():
            raise ValueError(
                "track_id must be a lowercase functional identifier "
                f"(letters/digits/underscores), got {self.track_id!r}"
            )
        if not self.source_kind or not self.source_kind.strip():
            raise ValueError(f"DeviceTrack {self.track_id!r} requires a non-empty source_kind")
        if not self.collection_hint or not self.collection_hint.strip():
            raise ValueError(f"DeviceTrack {self.track_id!r} requires a non-empty collection_hint")


_REGISTRY: dict[str, DeviceTrack] = {}


def _reject_all(_source_kind: str) -> bool:
    """Default parser resolver - rejects everything so an un-wired registry
    cannot silently admit a dead-end device track."""
    return False


_parser_resolver: Callable[[str], bool] = _reject_all
_seeded = False


def set_parser_resolver(resolver: Callable[[str], bool], *, seed: bool = True) -> None:
    """Install the parser-registry resolver (Stage 4 imports no ingest code, so
    the resolver is injected). Seeds the device tracks lazily on first install,
    now that source kinds can resolve; re-installing a resolver never re-seeds.
    """
    global _parser_resolver, _seeded
    _parser_resolver = resolver
    if seed and not _seeded:
        _seed_devices()
        _seeded = True


def register_device_track(track: DeviceTrack) -> DeviceTrack:
    """Add one device track to the registry (the rule for adding a device).

    Validates the declaration, refuses a duplicate ``track_id``, then enforces
    the safety rail: the track's ``source_kind`` must resolve to a registered
    parser, or registration is refused with a message naming the unresolvable
    source_kind.
    """
    track.validate()
    if track.track_id in _REGISTRY:
        raise ValueError(f"device track {track.track_id!r} is already registered")
    if not _parser_resolver(track.source_kind):
        raise ValueError(
            f"device track {track.track_id!r} source_kind {track.source_kind!r} "
            "does not resolve to a registered parser (dead-end device refused)"
        )
    _REGISTRY[track.track_id] = track
    return track


def get_device_track(track_id: str) -> DeviceTrack | None:
    return _REGISTRY.get(track_id)


def known_device_track_ids() -> frozenset[str]:
    """The live set of registered device track ids - never a fixed vocabulary."""
    return frozenset(_REGISTRY)


def list_device_tracks() -> list[DeviceTrack]:
    """All registered device tracks, stable by ``track_id``."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


# --------------------------------------------------------------------------- #
# The seeded device tracks - instances of the contract, not a closed list.
# Seeded only once a resolver is installed, so an un-wired registry admits
# nothing; a track whose parser is not registered is skipped by the safety rail.
# Collection hints describe each parser's real export mechanism (see the parser
# module docstrings). A new device registers with no central edit.
# --------------------------------------------------------------------------- #

_SEED_DEVICES = (
    DeviceTrack(
        track_id="health_connect",
        source_kind="health_connect",
        collection_hint=(
            "On Android, open Health Connect and back up your data to a .db file - it "
            "aggregates what other apps (Samsung Health, Google Fit, sleep trackers) write to it."
        ),
    ),
    DeviceTrack(
        track_id="garmin",
        source_kind="garmin_gdpr",
        collection_hint=(
            "Request your Garmin data export from Garmin Account Management "
            "(Export Your Data); you receive a .zip by email."
        ),
    ),
    DeviceTrack(
        track_id="withings",
        source_kind="withings",
        collection_hint=(
            "In the Withings app or web account, use 'Download your data' to get a "
            ".zip of per-category CSVs (weight, blood pressure, sleep, steps)."
        ),
    ),
    DeviceTrack(
        track_id="fitbit",
        source_kind="fitbit_takeout",
        collection_hint=(
            "Export via Google Takeout (select Fitbit) or Fitbit's 'Export Your Account "
            "Archive'; you get a MyFitbitData folder or a .zip of it."
        ),
    ),
    DeviceTrack(
        track_id="sleep_as_android",
        source_kind="sleep_as_android",
        collection_hint=(
            "In Sleep as Android, back up your sleep records to a CSV export (Settings -> Backup)."
        ),
    ),
    DeviceTrack(
        track_id="myfitnesspal",
        source_kind="myfitnesspal",
        collection_hint=(
            "In MyFitnessPal, use 'File Export' to download your Nutrition-Summary CSV "
            "(or its zip) of logged meals."
        ),
    ),
    DeviceTrack(
        track_id="lab_report",
        source_kind="lab_pdf",
        collection_hint=(
            "Provide a lab-results PDF from your provider or patient portal; Premura "
            "extracts the values locally."
        ),
    ),
    DeviceTrack(
        track_id="ai_chat_recall",
        source_kind="ai_chat_recall",
        collection_hint=(
            "No device needed: recall the supplements and oral medications you take by "
            "pasting Premura's AI-chat recall prompt into any assistant and saving its JSON reply."
        ),
    ),
)


def _seed_devices() -> None:
    for track in _SEED_DEVICES:
        try:
            register_device_track(track)
        except ValueError:
            # Dead-end device (no parser registered for it) - the safety rail
            # refuses it; skip rather than crash. Lights up when its parser ships.
            continue


__all__ = [
    "DeviceTrack",
    "get_device_track",
    "known_device_track_ids",
    "list_device_tracks",
    "register_device_track",
    "set_parser_resolver",
]
