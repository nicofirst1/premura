"""Fitbit Google Takeout parser -- synthetic fixtures only (no real export rows).

Covers the parser's design end to end against CONTRACT.md's decision tree:
happy-path rows for every recognized daily/summary member, the deliberate skip
of intraday streams and non-signal categories (surfaced in ``notes``), the
blank-cell / malformed-cell / vendor-sentinel edge cases, and the ontology-reuse
vs new-row vs vendor-fallback metric mappings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from premura.parsers.fitbit_takeout import SOURCE_ID, SOURCE_KIND, FitbitTakeoutParser
from tests.fixtures.parsers.fitbit_takeout.content import member_names, write_tree, write_zip


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    return write_tree(tmp_path)


def _parse(path: Path):
    batch = FitbitTakeoutParser().parse(path)
    batch.validate()
    return batch


def test_declares_metrics_covers_reuse_new_and_vendor() -> None:
    declared = set(FitbitTakeoutParser().declares_metrics())
    # Rung 1: existing ontology reuse.
    assert {
        "hrv_rmssd_overnight",
        "respiratory_rate_sleep",
        "spo2",
        "skin_temperature",
        "resting_hr",
        "sleep_session",
        "sleep_rating",
        "sleep_efficiency",
        "stress",
        "mindfulness_session",
    } <= declared
    # Rung 4: bare English canonical additions.
    assert {
        "active_minutes_very",
        "active_minutes_moderate",
        "active_minutes_light",
        "sedentary_minutes",
    } <= declared
    # Rung 5: vendor fallback.
    assert "vendor:fitbit:menstrual_period" in declared


def test_emitted_metrics_are_declared(export_dir: Path) -> None:
    batch = _parse(export_dir)
    assert batch.emitted_metrics <= set(batch.declared_metrics)


def test_daily_hrv_spo2_resp_temp(export_dir: Path) -> None:
    batch = _parse(export_dir)
    by_metric = {m.metric_id: m for m in batch.measurements}
    hrv = [m for m in batch.measurements if m.metric_id == "hrv_rmssd_overnight"]
    assert len(hrv) == 1  # blank + malformed rows dropped/skipped
    assert hrv[0].value_num == 47.5 and hrv[0].unit == "ms"
    assert by_metric["respiratory_rate_sleep"].unit == "breaths_per_min"
    spo2 = next(m for m in batch.measurements if m.metric_id == "spo2")
    assert spo2.value_num == 96.5 and spo2.unit == "pct"
    temp = next(m for m in batch.measurements if m.metric_id == "skin_temperature")
    assert temp.value_num == 31.42 and temp.unit == "celsius"


def test_blank_cell_is_unknown_and_malformed_is_skipped(export_dir: Path) -> None:
    batch = _parse(export_dir)
    fields = {s.raw_field for s in batch.skipped_rows}
    reasons = " | ".join(s.reason for s in batch.skipped_rows)
    assert "daily_hrv.rmssd" in fields
    assert "non-numeric value" in reasons
    assert "stress_score.STRESS_SCORE" in fields


def test_active_and_sedentary_daily_minutes(export_dir: Path) -> None:
    batch = _parse(export_dir)

    def values(metric_id: str) -> list[float]:
        return [m.value_num for m in batch.measurements if m.metric_id == metric_id]

    very = [m for m in batch.measurements if m.metric_id == "active_minutes_very"]
    assert sorted(m.value_num for m in very) == [72, 94]  # both daily rows kept
    assert all(m.unit == "min" for m in very)
    assert values("active_minutes_moderate") == [42]
    assert values("active_minutes_light") == [214]
    assert values("sedentary_minutes") == [560]


def test_resting_hr_sentinel_day_dropped(export_dir: Path) -> None:
    batch = _parse(export_dir)
    rhr = [m for m in batch.measurements if m.metric_id == "resting_hr"]
    # The date:null 0.0 sentinel day is dropped; the sleep_score RHR + one JSON
    # daily RHR remain (both real, non-zero).
    assert all(m.value_num > 0 for m in rhr)
    assert any(abs(m.value_num - 58.4) < 1e-6 for m in rhr)


def test_stress_sentinel_dropped_and_ready_kept(export_dir: Path) -> None:
    batch = _parse(export_dir)
    stress = [m for m in batch.measurements if m.metric_id == "stress"]
    assert len(stress) == 1  # NO_DATA and malformed dropped/skipped
    assert stress[0].value_num == 79 and stress[0].unit == "score_0_100"


def test_sleep_session_interval_and_efficiency(export_dir: Path) -> None:
    batch = _parse(export_dir)
    sessions = [i for i in batch.intervals if i.metric_id == "sleep_session"]
    assert len(sessions) == 1  # the inverted-time second log is skipped wholesale
    assert (sessions[0].end_utc - sessions[0].start_utc).total_seconds() > 0
    eff = [m for m in batch.measurements if m.metric_id == "sleep_efficiency"]
    assert eff and eff[0].value_num == 94 and eff[0].unit == "pct"
    rating = [m for m in batch.measurements if m.metric_id == "sleep_rating"]
    assert len(rating) == 1 and rating[0].value_num == 78


def test_mindfulness_interval_and_inverted_skipped(export_dir: Path) -> None:
    batch = _parse(export_dir)
    sessions = [i for i in batch.intervals if i.metric_id == "mindfulness_session"]
    assert len(sessions) == 1
    assert sessions[0].value_text == "Quick scan"
    assert "mindfulness.start/end" in {s.raw_field for s in batch.skipped_rows}


def test_menstrual_period_interval(export_dir: Path) -> None:
    batch = _parse(export_dir)
    periods = [i for i in batch.intervals if i.metric_id == "vendor:fitbit:menstrual_period"]
    assert len(periods) == 1
    assert (periods[0].end_utc - periods[0].start_utc).days == 5  # 5 days inclusive-ish


def test_intraday_and_non_signal_are_noted_not_parsed(export_dir: Path) -> None:
    batch = _parse(export_dir)
    assert batch.notes is not None
    # Per-minute steps stream and the Social/ file are unhandled, not emitted.
    assert "steps" in batch.notes
    assert "some_export.csv" in batch.notes
    assert not any(m.metric_id == "steps" for m in batch.measurements)


def test_unmapped_vendor_details_declared(export_dir: Path) -> None:
    batch = _parse(export_dir)
    assert "vendor:fitbit:daily_hrv.nremhr" in batch.unmapped_metrics
    assert "vendor:fitbit:sleep_score.subscores" in batch.unmapped_metrics
    assert "vendor:fitbit:daily_spo2.lower_bound" in batch.unmapped_metrics


def test_source_descriptor_and_unique_dedupe_keys(export_dir: Path) -> None:
    batch = _parse(export_dir)
    assert SOURCE_ID in batch.source_descriptors
    assert batch.source_descriptors[SOURCE_ID].source_kind == SOURCE_KIND
    keys = [m.dedupe_key for m in batch.measurements] + [i.dedupe_key for i in batch.intervals]
    assert len(keys) == len(set(keys))


def test_reingest_is_idempotent_shape(export_dir: Path) -> None:
    a = _parse(export_dir)
    b = _parse(export_dir)
    a_keys = sorted(m.dedupe_key for m in a.measurements) + sorted(
        i.dedupe_key for i in a.intervals
    )
    b_keys = sorted(m.dedupe_key for m in b.measurements) + sorted(
        i.dedupe_key for i in b.intervals
    )
    assert a_keys == b_keys


def test_zip_input_matches_directory_input(tmp_path: Path, export_dir: Path) -> None:
    zip_path = tmp_path / "fitbit_takeout.zip"
    write_zip(zip_path)
    dir_batch = _parse(export_dir)
    zip_batch = _parse(zip_path)
    assert dir_batch.emitted_metrics == zip_batch.emitted_metrics
    assert len(dir_batch) == len(zip_batch)


def test_preview_routing_matches_ingest_dispatch(export_dir: Path) -> None:
    parser = FitbitTakeoutParser()
    members = member_names()
    preview = parser.preview_routing(members)
    # Two members are intentionally unrouted (intraday steps + non-signal file).
    assert preview.unhandled_count == 2
    assert preview.routed_count == len(members) - 2


def test_empty_or_unrecognized_input_is_rejected(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no recognized Fitbit Takeout"):
        FitbitTakeoutParser().parse(empty)
    bad = tmp_path / "not-an-export.txt"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a Fitbit Takeout"):
        FitbitTakeoutParser().parse(bad)
