"""Structural routing-preview capability (m7 WP1).

`premura inspect` consumes a *structural* parser capability — a parser that can
preview routing exposes ``preview_routing(member_names) -> RoutingPreview`` — and
never special-cases any vendor. These tests pin the capability shape and the
Garmin implementation that delegates to its existing dispatcher (FR-1.1, FR-1.4).

The preview is name-based dry-run only: routing a member must not read file
contents, open a warehouse connection, or mutate anything.
"""

from __future__ import annotations

from premura.parsers.base import RoutingPreview
from premura.parsers.garmin_gdpr import GarminGDPRParser


def test_routing_preview_holds_ordered_member_handler_pairs() -> None:
    preview = RoutingPreview(entries=[("a.json", "_handle_x"), ("b.json", None)])
    assert preview.entries[0] == ("a.json", "_handle_x")
    assert preview.routed_count == 1
    assert preview.unhandled_count == 1


def test_garmin_previews_routing_via_its_dispatcher() -> None:
    """FR-1.4 — Garmin delegates to its _dispatch/_HANDLERS table; a known member
    routes to a named handler, an unknown member is reported unhandled."""
    parser = GarminGDPRParser()
    members = [
        "DI_CONNECT/sleepData.json",
        "DI_CONNECT/UDSFile_20240101.json",
        "DI_CONNECT/totally_unknown_export.json",
    ]
    preview = parser.preview_routing(members)

    by_member = dict(preview.entries)
    assert by_member["DI_CONNECT/sleepData.json"] == "_handle_sleep_data"
    assert by_member["DI_CONNECT/UDSFile_20240101.json"] == "_handle_daily_wellness"
    assert by_member["DI_CONNECT/totally_unknown_export.json"] is None
    assert preview.routed_count == 2
    assert preview.unhandled_count == 1


def test_garmin_preview_preserves_member_order() -> None:
    parser = GarminGDPRParser()
    members = ["z_unknown.json", "sleepData.json", "BloodPressureFile.json"]
    preview = parser.preview_routing(members)
    assert [m for m, _ in preview.entries] == members
