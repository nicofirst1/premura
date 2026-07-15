"""Onboarding arc gap #2: the ``interview_devices`` MCP tool + parser-backed resolver.

Locks the interview device branch over the device-track registry:

* the parser-backed resolver is actually installed - a track admits only a
  ``source_kind`` the parser registry knows; a made-up source is refused through
  the LIVE resolver, not the module's default-deny stub;
* ``device_inventory`` lists the seeded devices, each with a collection hint;
* ``device_route`` resolves a seeded device, and refuses a device with no parser
  behind it with the registry's dead-end message (never guide toward unreadable
  data);
* an ad-hoc device that names a real ``source_kind`` is admitted on the spot;
* the tool is registered on the live default MCP surface, dispatching
  list-vs-resolve on the optional argument.
"""

from __future__ import annotations

import asyncio

import pytest

from premura.mcp import server
from premura.mcp.entrypoint import build_server
from premura.parsers.registry import registered_source_kinds
from premura.ui import device_tracks as dt


@pytest.fixture(autouse=True)
def _isolate_registry():
    """The device-track registry is a mutable module global. Each test starts
    from import state (empty registry, reject-all resolver, unseeded) and
    restores it afterwards."""
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


def test_resolver_installed_admits_only_registered_parsers() -> None:
    server.install_device_track_resolver()
    assert dt._parser_resolver is not dt._reject_all
    assert dt._parser_resolver("garmin_gdpr") is True
    assert dt._parser_resolver("peloton_export") is False


def test_inventory_lists_seeded_devices_with_hints() -> None:
    server.install_device_track_resolver()
    inv = server.device_inventory()
    assert inv["status"] == "inventory"
    assert inv["devices"], "at least the seeded devices are present"
    known = registered_source_kinds()
    for entry in inv["devices"]:
        assert entry["collection_hint"].strip()  # the device branch guides collection
        assert entry["source_kind"] in known  # safety rail: nothing unreadable listed


def test_route_resolves_seeded_device() -> None:
    server.install_device_track_resolver()
    result = server.device_route("garmin")
    assert result["status"] == "routed"
    assert result["track_id"] == "garmin"
    assert result["source_kind"] == "garmin_gdpr"
    assert result["collection_hint"].strip()


def test_unregistered_device_refused_never_guides_unreadable_data() -> None:
    server.install_device_track_resolver()
    result = server.device_route("peloton")
    assert result["status"] == "refused"
    assert result["device"] == "peloton"
    assert "does not resolve" in result["reason"]
    assert "collection_hint" not in result
    assert dt.get_device_track("peloton") is None


def test_adhoc_device_named_as_real_source_kind_admitted() -> None:
    """A device named exactly as a registered parser source_kind is admitted on
    the spot (the documented add rule), same open-registry property as interview_route."""
    server.install_device_track_resolver()
    result = server.device_route("bmt")  # a real source_kind with no curated seed
    assert result["status"] == "routed"
    assert result["source_kind"] == "bmt"


def test_blank_device_refused() -> None:
    server.install_device_track_resolver()
    assert server.device_route("   ")["status"] == "refused"


def test_interview_devices_registered_and_dispatches_on_argument() -> None:
    srv = build_server()
    names = {tool.name for tool in asyncio.run(srv.list_tools())}
    assert "interview_devices" in names
    # No argument -> inventory; a device argument -> single route.
    assert server.device_inventory()["status"] == "inventory"
    assert server.device_route("garmin")["status"] == "routed"
