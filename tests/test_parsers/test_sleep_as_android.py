"""SAA parser — synthetic CSV, no real PHI."""

from __future__ import annotations

from pathlib import Path

from premura.parsers.sleep_as_android import SleepAsAndroidParser


def _write_fixture(tmp_path: Path) -> Path:
    csv = (
        "Id,Tz,From,To,Sched,Hours,Rating,Comment,Framerate,Snore,Noise,Cycles,DeepSleep,LenAdjust,Geo,"
        "23:00,23:01,23:02,00:00,00:01\n"
        "1700000000000,Europe/Berlin,21. 03. 2024 23:00,22. 03. 2024 06:00,"
        ",7.0,3.5,sample,60.0,0,0,4,0.42,0,,"
        "1.2,0.9,0.4,0.1,0.0\n"
    )
    p = tmp_path / "saa.csv"
    p.write_text(csv, encoding="utf-8")
    return p


def test_emits_one_session_interval(tmp_path):
    p = _write_fixture(tmp_path)
    result = SleepAsAndroidParser().parse(p)
    sessions = [i for i in result.intervals if i.metric_id == "sleep_session"]
    assert len(sessions) == 1
    s = sessions[0]
    # 23:00 Europe/Berlin (CET = +01:00) = 22:00 UTC.
    assert s.start_utc.year == 2024
    assert s.start_utc.hour == 22
    assert s.local_tz == "Europe/Berlin"
    assert s.value_num == 7.0


def test_per_minute_actigraphy_count(tmp_path):
    p = _write_fixture(tmp_path)
    result = SleepAsAndroidParser().parse(p)
    actig = [m for m in result.measurements if m.metric_id == "sleep_actigraphy"]
    assert len(actig) == 5
    assert actig[0].unit == "index"
    times = [m.ts_utc for m in actig]
    assert times == sorted(times)


def test_rating_and_deep_pct_emitted(tmp_path):
    p = _write_fixture(tmp_path)
    result = SleepAsAndroidParser().parse(p)
    metrics = {m.metric_id for m in result.measurements}
    assert "sleep_rating" in metrics
    assert "sleep_deep_pct" in metrics
    deep = next(m for m in result.measurements if m.metric_id == "sleep_deep_pct")
    assert abs(deep.value_num - 42.0) < 1e-6


def test_dedupe_key_format(tmp_path):
    p = _write_fixture(tmp_path)
    result = SleepAsAndroidParser().parse(p)
    s = next(i for i in result.intervals if i.metric_id == "sleep_session")
    assert s.dedupe_key.startswith("sleep_as_android:saa:")
