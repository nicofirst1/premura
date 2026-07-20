"""Garmin GDPR parser — synthetic fixtures only (no real export rows).

Covers the summarizedActivities bug fix: the single-element-list wrapper
around ``summarizedActivitiesExport``, epoch-millisecond timestamps
(``beginTimestamp``), and millisecond ``duration`` (not
``durationInSeconds``).
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from premura.parsers.garmin_gdpr import GarminGDPRParser

# Three synthetic activities. Timestamps and duration are epoch milliseconds,
# matching the real Garmin summarizedActivitiesExport shape.
_ACTIVITIES = [
    {
        "activityId": 111,
        "name": "Morning Run",
        "activityType": "road_biking",
        "sportType": "cycling",
        "beginTimestamp": 1784452425000,  # 2026-07-19T09:13:45Z
        "startTimeGmt": 1784452425000,
        "duration": 2827553.95,  # ~47.126 min
        "distance": 15234.5,
        "avgHr": 142.0,
        "maxHr": 168.0,
        "steps": 0,
        "calories": 512.0,
    },
    {
        "activityId": 112,
        "name": "Strength",
        "activityType": "strength_training",
        "sportType": "fitness_equipment",
        "beginTimestamp": 1784500000000,
        "duration": 1800000.0,  # exactly 30 min
        "avgHr": 110.0,
        "calories": 220.0,
    },
    {
        "activityId": 113,
        "name": "Evening Walk",
        "activityType": "walking",
        "sportType": "walking",
        "beginTimestamp": 1784520000000,
        "duration": 900000.0,  # 15 min
        "distance": 1200.0,
        "steps": 1500,
        "avgHr": 95.0,
        "calories": 80.0,
    },
]


@pytest.fixture
def export_zip(tmp_path: Path) -> Path:
    path = tmp_path / "garmin_export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        # Real-world shape: single-element list wrapping the export dict.
        payload = [{"summarizedActivitiesExport": _ACTIVITIES}]
        zf.writestr(
            "DI_CONNECT/DI-Connect-Fitness/1234_0_summarizedActivities.json",
            json.dumps(payload),
        )
    return path


def test_declares_metrics_includes_all_emitted_ids() -> None:
    declared = set(GarminGDPRParser().declares_metrics())
    assert {"exercise_session", "heart_rate", "distance", "steps", "active_kcal"} <= declared


def test_activities_unwrap_and_parse_with_correct_timestamps(export_zip: Path) -> None:
    batch = GarminGDPRParser().parse(export_zip)
    batch.validate()

    sessions = [iv for iv in batch.intervals if iv.metric_id == "exercise_session"]
    assert len(sessions) == 3

    run = next(iv for iv in sessions if iv.value_text == "road_biking")
    assert run.start_utc.isoformat() == "2026-07-19T09:13:45"
    # duration is milliseconds: 2827553.95 ms = 2827.55395 s
    assert (run.end_utc - run.start_utc).total_seconds() == pytest.approx(2827.55395, abs=1e-3)

    strength = next(iv for iv in sessions if iv.value_text == "strength_training")
    assert (strength.end_utc - strength.start_utc).total_seconds() == pytest.approx(1800.0)

    # Per-activity metrics emitted alongside the session interval.
    walk_uuid_prefix = "garmin:activity_summary:113"
    calories = next(
        iv
        for iv in batch.intervals
        if iv.metric_id == "active_kcal" and (iv.source_uuid or "").startswith(walk_uuid_prefix)
    )
    assert calories.value_num == 80.0

    distance = next(
        iv
        for iv in batch.intervals
        if iv.metric_id == "distance" and (iv.source_uuid or "").startswith(walk_uuid_prefix)
    )
    assert distance.value_num == 1200.0

    steps = next(
        iv
        for iv in batch.intervals
        if iv.metric_id == "steps" and (iv.source_uuid or "").startswith(walk_uuid_prefix)
    )
    assert steps.value_num == 1500.0

    hr = next(
        m
        for m in batch.measurements
        if m.metric_id == "heart_rate" and (m.source_uuid or "").startswith(walk_uuid_prefix)
    )
    assert hr.value_num == 95.0
