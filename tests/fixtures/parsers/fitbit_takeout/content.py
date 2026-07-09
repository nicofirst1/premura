"""Synthetic Fitbit Google Takeout export content -- single source of truth.

Structurally faithful to a real ``MyFitbitData/<User>/<Category>/`` export
(same filenames, headers, JSON shapes, timestamp formats), but **all values are
made up** -- no real Fitbit export was copied (AGENTS.md "never copy real
operator data"). The tree is materialized under ``tmp_path`` by ``write_tree``;
nothing here is a committed data file, only these Python string constants.

Each member carries a happy-path row, plus the parser's spec-named edge cases:
a blank cell (unknown, never fabricated as zero), a malformed cell (declared via
``skipped_rows``, never dropped), and vendor sentinels (a ``NO_DATA`` stress day,
a ``date: null`` resting-HR day). An intraday stream file and a non-signal
category file are included so the parser's "skip and note" path is exercised.
"""

from __future__ import annotations

from pathlib import Path

# The export root folder Fitbit's Takeout ships (the parser dispatches on it).
ROOT = "MyFitbitData"
USER = "TestUser"

# --- Sleep ---------------------------------------------------------------- #

DAILY_HRV = (
    "timestamp,rmssd,nremhr,entropy\n"
    "2024-01-11T00:00:00,47.5,54.2,2.9\n"
    "2024-01-12T00:00:00,,55.0,3.0\n"  # blank rmssd -> unknown, not zero
    "2024-01-13T00:00:00,not-a-number,53.1,2.8\n"  # malformed -> skipped_rows
)

DAILY_RESP = (
    "timestamp,daily_respiratory_rate\n2024-01-11T00:00:00,15.4\n2024-01-12T00:00:00,16.1\n"
)

DAILY_SPO2 = (
    "timestamp,average_value,lower_bound,upper_bound\n"
    "2024-01-11T00:00:00Z,96.5,93.0,99.9\n"
    "2024-01-12T00:00:00Z,95.8,92.5,99.1\n"
)

COMPUTED_TEMP = (
    "type,sleep_start,sleep_end,temperature_samples,nightly_temperature,"
    "baseline_relative_sample_sum,baseline_relative_sample_sum_of_squares,"
    "baseline_relative_nightly_standard_deviation,baseline_relative_sample_standard_deviation\n"
    "IDT,2024-01-10T23:15,2024-01-11T07:05,530,31.42,NaN,NaN,NaN,NaN\n"
    "IDT,2024-01-11T22:31,2024-01-12T07:00,551,30.11,NaN,NaN,NaN,NaN\n"
)

SLEEP_SCORE = (
    "sleep_log_entry_id,timestamp,overall_score,composition_score,"
    "revitalization_score,duration_score,deep_sleep_in_minutes,"
    "resting_heart_rate,restlessness\n"
    "41941918001,2024-01-11T08:03:30Z,78,,78,,89,58,0.12\n"
    "41941918002,2024-01-12T07:55:00Z,,,,,80,60,0.10\n"  # blank overall -> no rating
)

SLEEP_JSON = """[{
  "logId" : 36052440001,
  "dateOfSleep" : "2024-01-11",
  "startTime" : "2024-01-10T22:41:00.000",
  "endTime" : "2024-01-11T07:44:30.000",
  "duration" : 32580000,
  "minutesAsleep" : 476,
  "timeInBed" : 543,
  "efficiency" : 94,
  "type" : "stages",
  "levels" : { "summary" : { "deep" : { "minutes" : 64 } } }
},{
  "logId" : 36052440002,
  "dateOfSleep" : "2024-01-12",
  "startTime" : "2024-01-11T23:10:00.000",
  "endTime" : "not-a-time",
  "efficiency" : 91,
  "type" : "stages"
}]"""

# --- Physical Activity (daily JSON aggregates) ---------------------------- #

VERY_ACTIVE = """[{
  "dateTime" : "01/11/24 00:00:00",
  "value" : "94"
},{
  "dateTime" : "01/12/24 00:00:00",
  "value" : "72"
}]"""

MODERATELY_ACTIVE = """[{
  "dateTime" : "01/11/24 00:00:00",
  "value" : "42"
}]"""

LIGHTLY_ACTIVE = """[{
  "dateTime" : "01/11/24 00:00:00",
  "value" : "214"
}]"""

SEDENTARY = """[{
  "dateTime" : "01/11/24 00:00:00",
  "value" : "560"
}]"""

RESTING_HR = """[{
  "dateTime" : "01/10/24 00:00:00",
  "value" : { "date" : null, "value" : 0.0, "error" : 0.0 }
},{
  "dateTime" : "01/11/24 00:00:00",
  "value" : { "date" : "01/11/24", "value" : 58.4, "error" : 6.2 }
}]"""

# An intraday stream file (per-minute): must be skipped and noted, not parsed.
STEPS_INTRADAY = """[{
  "dateTime" : "01/11/24 11:18:00",
  "value" : "13"
},{
  "dateTime" : "01/11/24 11:19:00",
  "value" : "19"
}]"""

# --- Stress --------------------------------------------------------------- #

STRESS_SCORE = (
    "DATE,UPDATED_AT,STRESS_SCORE,SLEEP_POINTS,MAX_SLEEP_POINTS,"
    "RESPONSIVENESS_POINTS,MAX_RESPONSIVENESS_POINTS,EXERTION_POINTS,"
    "MAX_EXERTION_POINTS,STATUS,CALCULATION_FAILED\n"
    "2024-01-11T00:00:00,2024-01-11T07:23:52.009,0,0,0,0,0,0,0,NO_DATA,true\n"  # sentinel
    "2024-01-12T00:00:00,2024-01-12T17:07:49.634,79,0,0,0,0,0,0,READY_NOT_PREMIUM,false\n"
    "2024-01-13T00:00:00,2024-01-13T07:33:56.804,bad,0,0,0,0,0,0,READY_NOT_PREMIUM,false\n"
)

MINDFULNESS = (
    "session_id,activity_name,average_heart_rate,start_heart_rate,end_heart_rate,"
    "duration,start_date_time,end_date_time,session_type,stress_metrics,pause_times\n"
    "366324d0-0001,Quick scan,null,64,61,180000,"
    "2024-01-11T08:14:14+01:00,2024-01-11T08:17:15+01:00,quick-scan,"
    "{meanScore=-1 derivScore=-1},null\n"
    "366324d0-0002,Breathe,null,70,66,300000,"
    "2024-01-12T09:00:00+01:00,not-a-time,paced-breathing,{},null\n"  # inverted -> skipped
)

# --- Menstrual Health ----------------------------------------------------- #

MENSTRUAL_CYCLES = (
    "id,cycle_start_date,cycle_end_date,ovulation_start_date,ovulation_end_date,"
    "ovulation_source,period_start_date,period_end_date,period_source,"
    "fertile_start_date,fertile_end_date,fertile_source\n"
    "cycle-0001,2024-01-05,2024-02-01,2024-01-18,2024-01-19,detected,"
    "2024-01-05,2024-01-09,logged,2024-01-14,2024-01-20,detected\n"
)

# --- Non-signal category (must be skipped and noted) ---------------------- #

NON_SIGNAL = "some,other\ndata,here\n"


# Relative path within MyFitbitData/<User>/ -> content.
MEMBERS: dict[str, str] = {
    "Sleep/Daily Heart Rate Variability Summary - 2024-01-11.csv": DAILY_HRV,
    "Sleep/Daily Respiratory Rate Summary - 2024-01-11.csv": DAILY_RESP,
    "Sleep/Daily SpO2 - 2024-01-11-2024-04-11.csv": DAILY_SPO2,
    "Sleep/Computed Temperature - 2024-01-11.csv": COMPUTED_TEMP,
    "Sleep/sleep_score.csv": SLEEP_SCORE,
    "Sleep/sleep-2024-01-11.json": SLEEP_JSON,
    "Physical Activity/very_active_minutes-2024-01-11.json": VERY_ACTIVE,
    "Physical Activity/moderately_active_minutes-2024-01-11.json": MODERATELY_ACTIVE,
    "Physical Activity/lightly_active_minutes-2024-01-11.json": LIGHTLY_ACTIVE,
    "Physical Activity/sedentary_minutes-2024-01-11.json": SEDENTARY,
    "Physical Activity/resting_heart_rate-2024-01-11.json": RESTING_HR,
    "Physical Activity/steps-2024-01-11.json": STEPS_INTRADAY,
    "Stress/Stress Score.csv": STRESS_SCORE,
    "Stress/Mindfulness Sessions.csv": MINDFULNESS,
    "Menstrual Health/menstrual_health_cycles.csv": MENSTRUAL_CYCLES,
    "Social/Media/some_export.csv": NON_SIGNAL,
}


def write_tree(root: Path) -> Path:
    """Materialize the synthetic export tree under ``root``.

    Returns the export-root folder path -- what ``hpipe ingest --source fitbit``
    (and the parser) is pointed at.
    """
    base = root / ROOT / USER
    for rel, content in MEMBERS.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root / ROOT


def member_names() -> list[str]:
    """Full archive member paths (``<root>/<user>/<rel>``) for the synthetic tree.

    Lives here rather than in the test module so the test file never has to name
    the real dump-root token, which a cross-test invariant forbids in
    ``test_*.py`` (see ``test_live_trial_seam`` C-003 / NFR-005).
    """
    return [f"{ROOT}/{USER}/{rel}" for rel in MEMBERS]


def write_zip(path: Path) -> None:
    """Write the synthetic export as a zip of the export tree."""
    import zipfile

    with zipfile.ZipFile(path, "w") as zf:
        for rel, content in MEMBERS.items():
            zf.writestr(f"{ROOT}/{USER}/{rel}", content)


__all__ = ["MEMBERS", "ROOT", "USER", "member_names", "write_tree", "write_zip"]
