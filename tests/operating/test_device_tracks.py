"""Onboarding arc gap #2: the device-track registry + resolving-parser rail.

Locks, mirroring ``test_interview_tracks.py`` on the ingest side:

* ``track_id`` validated by the same rule; ``collection_hint`` required (the
  device branch exists to guide collection, so an empty hint is refused);
* the registry is BOUNDED and OPEN - a new device registers, duplicates refused;
* the health safety rail - a track whose ``source_kind`` has no registered
  parser is refused, so the interview never guides toward data nothing can read;
* the default resolver rejects everything (an un-wired registry admits nothing);
* the seeds register once a real resolver is installed and list stable-sorted,
  and seeding is one-shot.
"""

from __future__ import annotations

import pytest

from premura.ui import device_tracks as dt


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Each test starts from module-import state (empty registry, reject-all
    resolver, unseeded) and restores it afterwards - the registry is a mutable
    module global."""
    saved_reg = dict(dt._REGISTRY)
    saved_resolver = dt._parser_resolver
    saved_seeded = dt._seeded
    dt._REGISTRY.clear()
    dt._parser_resolver = dt._reject_all
    dt._seeded = False
    try:
        yield
    finally:
        dt._REGISTRY.clear()
        dt._REGISTRY.update(saved_reg)
        dt._parser_resolver = saved_resolver
        dt._seeded = saved_seeded


def _track(track_id: str = "garmin", source_kind: str = "garmin_gdpr") -> dt.DeviceTrack:
    return dt.DeviceTrack(track_id=track_id, source_kind=source_kind, collection_hint="do X")


def test_resolving_source_kind_registers_and_duplicate_refused() -> None:
    dt.set_parser_resolver(lambda _sk: True, seed=False)
    track = _track()
    assert dt.register_device_track(track) is track
    assert dt.get_device_track("garmin") is track
    assert dt.get_device_track("nope") is None
    with pytest.raises(ValueError, match="already registered"):
        dt.register_device_track(_track())


def test_unregistered_parser_refused_at_registration() -> None:
    """Safety rail: guiding a human to gather data no parser can read is a dead
    end, refused at registration with a message naming the source_kind."""
    dt.set_parser_resolver(lambda sk: sk == "garmin_gdpr", seed=False)
    with pytest.raises(ValueError, match=r"peloton_export"):
        dt.register_device_track(_track(track_id="peloton", source_kind="peloton_export"))
    assert dt.get_device_track("peloton") is None


def test_default_resolver_admits_nothing() -> None:
    with pytest.raises(ValueError, match="does not resolve"):
        dt.register_device_track(_track())


def test_validation_matches_rule() -> None:
    with pytest.raises(ValueError, match="non-empty track_id"):
        dt.DeviceTrack(track_id=" ", source_kind="x", collection_hint="h").validate()
    with pytest.raises(ValueError, match="lowercase functional identifier"):
        dt.DeviceTrack(track_id="Garmin X", source_kind="x", collection_hint="h").validate()
    with pytest.raises(ValueError, match="non-empty source_kind"):
        dt.DeviceTrack(track_id="garmin", source_kind=" ", collection_hint="h").validate()
    with pytest.raises(ValueError, match="non-empty collection_hint"):
        dt.DeviceTrack(track_id="garmin", source_kind="x", collection_hint="  ").validate()


def test_seeds_register_once_real_resolver_installed_and_stable_sorted() -> None:
    dt.set_parser_resolver(lambda _sk: True)  # seed=True by default
    ids = [t.track_id for t in dt.list_device_tracks()]
    assert ids == sorted(ids)
    assert "garmin" in dt.known_device_track_ids()
    for track in dt.list_device_tracks():
        assert track.source_kind.strip() and track.collection_hint.strip()


def test_seeder_skips_dead_end_devices() -> None:
    """A seed whose parser is not registered is skipped, not fatal - so seeding
    with a partial resolver still admits the resolvable devices."""
    dt.set_parser_resolver(lambda sk: sk == "garmin_gdpr")
    assert dt.known_device_track_ids() == {"garmin"}


def test_seeding_is_one_shot() -> None:
    dt.set_parser_resolver(lambda _sk: True)
    count = len(dt.known_device_track_ids())
    dt.set_parser_resolver(lambda _sk: True)  # re-install must not re-seed
    assert len(dt.known_device_track_ids()) == count
