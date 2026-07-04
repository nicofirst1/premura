"""Phase 5 slice 1: the interview-track registry + resolving-route safety rail.

Locks:

* ``track_id`` validated by the same rule as ``role_id`` / ``kind_id``;
* the registry is BOUNDED and OPEN — a new direction registers, duplicates are
  refused (mirroring ``register_kind``);
* the health safety rail — a track whose ``signal_route`` does not resolve is
  refused at registration, so no dead-end interview direction can be admitted;
* the default resolver rejects everything, so an un-wired registry admits
  nothing;
* the STAGES-8 seed once a real resolver is installed and list stable-sorted.
"""

from __future__ import annotations

import pytest

from premura.ui import interview_tracks as it


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Each test starts from module-import state (empty registry, reject-all
    resolver, unseeded) and restores it afterwards — the registry is a mutable
    module global."""
    saved_reg = dict(it._REGISTRY)
    saved_resolver = it._route_resolver
    saved_seeded = it._seeded
    it._REGISTRY.clear()
    it._route_resolver = it._reject_all
    it._seeded = False
    try:
        yield
    finally:
        it._REGISTRY.clear()
        it._REGISTRY.update(saved_reg)
        it._route_resolver = saved_resolver
        it._seeded = saved_seeded


def test_resolving_route_registers_and_duplicate_refused() -> None:
    it.set_route_resolver(lambda _route: True, seed=False)
    track = it.InterviewTrack(track_id="sleep", signal_route="signal_selector:sleep")
    assert it.register_track(track) is track
    assert it.get_track("sleep") is track
    assert it.get_track("nope") is None
    with pytest.raises(ValueError, match="already registered"):
        it.register_track(it.InterviewTrack(track_id="sleep", signal_route="signal_selector:sleep"))


def test_unresolvable_route_refused_at_registration() -> None:
    """e2e spec-named edge case: a 'hydration deep-dive' with nothing behind it
    is refused at registration, and the message names the unresolvable route."""
    it.set_route_resolver(lambda route: route == "signal_selector:sleep", seed=False)
    with pytest.raises(ValueError, match=r"signal_selector:hydration"):
        it.register_track(
            it.InterviewTrack(
                track_id="hydration_deep_dive",
                signal_route="signal_selector:hydration",
            )
        )
    assert it.get_track("hydration_deep_dive") is None


def test_default_resolver_admits_nothing() -> None:
    """An un-wired registry (no resolver installed) cannot silently admit a
    dead-end direction — even a well-formed track is refused."""
    with pytest.raises(ValueError, match="does not resolve"):
        it.register_track(it.InterviewTrack(track_id="sleep", signal_route="signal_selector:sleep"))


def test_track_id_validation_matches_rule() -> None:
    with pytest.raises(ValueError, match="non-empty track_id"):
        it.InterviewTrack(track_id=" ", signal_route="x").validate()
    with pytest.raises(ValueError, match="lowercase functional identifier"):
        it.InterviewTrack(track_id="Sleep Track", signal_route="x").validate()
    with pytest.raises(ValueError, match="non-empty signal_route"):
        it.InterviewTrack(track_id="sleep", signal_route="  ").validate()


def test_stages8_seed_once_real_resolver_installed_and_stable_sorted() -> None:
    it.set_route_resolver(lambda _route: True)  # seed=True by default
    assert it.known_track_ids() == {
        "sleep",
        "cardio",
        "metabolic",
        "stress",
        "mental",
        "gut",
        "lab",
        "overview",
    }
    ids = [t.track_id for t in it.list_tracks()]
    assert ids == sorted(ids)
    for track in it.list_tracks():
        assert track.signal_route.strip()


def test_seeding_is_one_shot() -> None:
    it.set_route_resolver(lambda _route: True)
    it.set_route_resolver(lambda _route: True)  # re-install must not re-seed / double-register
    assert len(it.known_track_ids()) == 8
