"""Withings CSV export parser — synthetic fixtures only (no real export rows).

Covers every spec-named edge case in the parser's design (CONTRACT.md's
decision tree end to end): happy-path rows for each of the five recognized
export members, a blank cell (unknown, not fabricated as zero), a malformed
cell (declared via ``skipped_rows``, never dropped silently), the
vendor-fallback metric (``vendor:withings:pulse_wave_velocity``), the bare
English canonical addition (``fat_mass``), and the structural
``weight.Category`` field that has no metric home (``unmapped_metrics``).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from premura.parsers.withings import SOURCE_ID, SOURCE_KIND, WithingsParser
from tests.fixtures.parsers.withings.csv_content import MEMBERS, write_zip


@pytest.fixture
def export_zip(tmp_path: Path) -> Path:
    path = tmp_path / "withings_export.zip"
    write_zip(path)
    return path


def test_declares_metrics_matches_ontology_reuse_and_new_rows() -> None:
    declared = set(WithingsParser().declares_metrics())
    # Step-1 existing-alias reuse (no new dim_metric.yaml rows needed for these).
    assert {
        "weight",
        "body_fat_pct",
        "lean_body_mass",
        "muscle_mass",
        "bone_mass",
        "body_water_mass",
        "bp_systolic",
        "bp_diastolic",
        "heart_rate",
        "steps",
        "sleep_session",
        "sleep_deep_pct",
    } <= declared
    # Step 4 (bare English canonical) and step 5 (vendor fallback) additions.
    assert "fat_mass" in declared
    assert "vendor:withings:pulse_wave_velocity" in declared


def test_happy_path_weight_row_emits_all_body_composition_metrics(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    batch.validate()
    jun05 = {
        m.metric_id: m
        for m in batch.measurements
        if m.ts_utc.isoformat().startswith("2026-06-05T07:15")
    }
    assert jun05["weight"].value_num == 82.4
    assert jun05["weight"].unit == "kg"
    assert jun05["fat_mass"].value_num == 18.9
    assert jun05["lean_body_mass"].value_num == 63.5
    assert jun05["body_fat_pct"].value_num == 22.9
    assert jun05["bone_mass"].value_num == 3.1
    assert jun05["muscle_mass"].value_num == 55.2
    assert jun05["body_water_mass"].value_num == 45.8
    pwv = next(
        m for m in batch.measurements if m.metric_id == "vendor:withings:pulse_wave_velocity"
    )
    assert pwv.value_num == 7.4
    assert pwv.unit == "m/s"


def test_blank_cell_is_unknown_not_zero(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    # 2026-06-12 07:10 weight row has every body-composition cell blank except weight.
    weight_jun12 = [
        m for m in batch.measurements if m.ts_utc.isoformat().startswith("2026-06-12T07:10")
    ]
    assert {m.metric_id for m in weight_jun12} == {"weight"}
    assert weight_jun12[0].value_num == 81.9
    # bp.csv 2026-06-12 07:18 row: heart rate + pulse wave velocity blank, not zero.
    bp_jun12 = [
        m for m in batch.measurements if m.ts_utc.isoformat().startswith("2026-06-12T07:18")
    ]
    assert {m.metric_id for m in bp_jun12} == {"bp_systolic", "bp_diastolic"}


def test_malformed_cell_is_skipped_row_not_dropped(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    reasons = " | ".join(s.reason for s in batch.skipped_rows)
    fields = {s.raw_field for s in batch.skipped_rows}
    assert "weight.Weight (kg)" in fields
    assert "non-numeric value" in reasons
    assert "bp.Systolic (mmHg)" in fields
    assert "raw_tracker_hr.Heart rate (bpm)" in fields
    assert "aggregates_steps.Steps" in fields
    assert "sleep.from/to" in fields


def test_comments_land_on_weight_measurement_category_is_unmapped(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    jun26 = next(
        m
        for m in batch.measurements
        if m.metric_id == "weight" and m.ts_utc.isoformat().startswith("2026-06-26")
    )
    assert jun26.value_text == "felt good today"
    assert "vendor:withings:weight.Category" in batch.unmapped_metrics


def test_steps_becomes_interval_not_measurement(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    steps = [i for i in batch.intervals if i.metric_id == "steps"]
    assert len(steps) == 1
    assert steps[0].value_num == 8342
    assert (steps[0].end_utc - steps[0].start_utc).total_seconds() == 86400


def test_sleep_session_and_deep_pct(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    sessions = [i for i in batch.intervals if i.metric_id == "sleep_session"]
    # Happy-path row + blank-stage row both produce a session interval; the
    # unparseable-`to` row is skipped wholesale (no interval, no measurement).
    assert len(sessions) == 2
    deep_pct = [m for m in batch.measurements if m.metric_id == "sleep_deep_pct"]
    assert len(deep_pct) == 1
    total = 5400 + 14400 + 7200 + 900
    assert abs(deep_pct[0].value_num - 100.0 * 5400 / total) < 1e-6


def test_source_descriptor_and_dedupe_keys(export_zip: Path) -> None:
    batch = WithingsParser().parse(export_zip)
    assert SOURCE_ID in batch.source_descriptors
    assert batch.source_descriptors[SOURCE_ID].source_kind == SOURCE_KIND
    keys = [m.dedupe_key for m in batch.measurements] + [i.dedupe_key for i in batch.intervals]
    assert len(keys) == len(set(keys))


def test_reingest_is_idempotent_shape(export_zip: Path) -> None:
    a = WithingsParser().parse(export_zip)
    b = WithingsParser().parse(export_zip)
    a_keys = sorted(m.dedupe_key for m in a.measurements) + sorted(
        i.dedupe_key for i in a.intervals
    )
    b_keys = sorted(m.dedupe_key for m in b.measurements) + sorted(
        i.dedupe_key for i in b.intervals
    )
    assert a_keys == b_keys


def test_preview_routing_matches_ingest_dispatch(export_zip: Path) -> None:
    parser = WithingsParser()
    with zipfile.ZipFile(export_zip) as zf:
        members = [info.filename for info in zf.infolist()]
    preview = parser.preview_routing(members)
    assert preview.routed_count == len(members)
    assert preview.unhandled_count == 0
    assert {name for name, handler in preview.entries} == set(MEMBERS)


def test_unrecognized_zip_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-withings.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("something-else.csv", "a,b\n1,2\n")
    with pytest.raises(ValueError, match="no recognized Withings export member"):
        WithingsParser().parse(path)


def test_non_zip_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-a-zip.csv"
    path.write_text("Date,Weight (kg)\n2026-06-05,82.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a Withings export zip"):
        WithingsParser().parse(path)


def test_build_fixture_helper_matches_this_suite(tmp_path: Path) -> None:
    """``build_fixture.py``'s ``write_zip`` (used for local CLI acceptance runs,
    never committed -- see module docstring) parses identically to the
    in-memory fixture every other test in this file uses."""
    generated = tmp_path / "withings_export_synthetic.zip"
    write_zip(generated)
    batch = WithingsParser().parse(generated)
    batch.validate()
    assert len(batch) > 0
