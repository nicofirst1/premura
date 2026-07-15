"""Synthetic Withings export CSV content — single source of truth.

Plain text on purpose: this repo's ``.gitignore`` excludes ``*.zip`` and
``ops/check_no_tracked_data.sh`` documents the convention explicitly
("synthetic test fixtures are text formats ... and never match these
patterns"). So the zip built from this content (``build_fixture.py`` ->
``withings_export_synthetic.zip``) is a local-only, gitignored artifact,
never committed -- only these CSV strings are. All values are made up; no
real Withings export was used or copied (AGENTS.md "never copy real operator
data").

Shared by ``tests/test_parsers/test_withings.py`` (builds an equivalent zip in
``tmp_path`` for every assertion) and ``build_fixture.py`` (materializes the
same zip on disk for the issue #33 CLI acceptance commands:
``premura ingest --source withings`` / ``premura inspect`` -- run the builder
once locally, then point those commands at its output).

Each CSV below intentionally carries a happy-path row, a blank-cell row
(unknown, never fabricated as zero), and a malformed row (declared via
``skipped_rows``, never dropped silently) — the parser's spec-named edge
cases per CONTRACT.md.
"""

from __future__ import annotations

WEIGHT_HEADER = (
    "Date,Weight (kg),Fat mass (kg),Fat free mass (kg),Fat Ratio (%),"
    "Bone mass (kg),Muscle mass (kg),Hydration (kg),Comments,Category"
)
WEIGHT_CSV = (
    WEIGHT_HEADER + "\n"
    "2026-06-05 07:15:00,82.4,18.9,63.5,22.9,3.1,55.2,45.8,,smart_body_analyzer\n"
    "2026-06-12 07:10:00,81.9,,,,,,,,smart_body_analyzer\n"
    "2026-06-19 07:05:00,not-a-number,18.5,63.0,22.5,3.1,55.0,45.6,,smart_body_analyzer\n"
    "2026-06-26 07:20:00,81.2,18.2,63.0,22.4,3.0,55.1,45.7,felt good today,body_cardio\n"
)

BP_HEADER = "Date,Systolic (mmHg),Diastolic (mmHg),Heart rate (bpm),Pulse wave velocity (m/s)"
BP_CSV = (
    BP_HEADER + "\n"
    "2026-06-05 07:20:00,118,76,58,7.4\n"
    "2026-06-12 07:18:00,121,79,,\n"
    "2026-06-19 07:22:00,bad,80,60,7.6\n"
)

HR_HEADER = "Date,Heart rate (bpm)"
HR_CSV = (
    HR_HEADER + "\n"
    "2026-06-05 08:00:00,72\n"
    "2026-06-05 12:30:00,88\n"
    "2026-06-06 09:15:00,not-a-number\n"
)

STEPS_HEADER = "Date,Steps"
STEPS_CSV = STEPS_HEADER + "\n2026-06-05,8342\n2026-06-06,\n2026-06-07,lots\n"

SLEEP_HEADER = "from,to,deep (s),light (s),rem (s),wakeup (s)"
SLEEP_CSV = (
    SLEEP_HEADER + "\n"
    "2026-06-04 23:10:00,2026-06-05 06:50:00,5400,14400,7200,900\n"
    "2026-06-05 23:05:00,2026-06-06 06:40:00,,,,\n"
    "2026-06-06 23:00:00,not-a-time,5000,14000,7000,800\n"
    "2026-06-07 23:00:00,2026-06-08 06:30:00,bad,14000,7000,800\n"
)

MEMBERS = {
    "weight.csv": WEIGHT_CSV,
    "bp.csv": BP_CSV,
    "raw_tracker_hr.csv": HR_CSV,
    "aggregates_steps.csv": STEPS_CSV,
    "sleep.csv": SLEEP_CSV,
}


def write_zip(path) -> None:
    """Write the full synthetic Withings export zip to ``path``."""
    import zipfile

    with zipfile.ZipFile(path, "w") as zf:
        for name, content in MEMBERS.items():
            zf.writestr(name, content)


__all__ = [
    "BP_CSV",
    "HR_CSV",
    "MEMBERS",
    "SLEEP_CSV",
    "STEPS_CSV",
    "WEIGHT_CSV",
    "write_zip",
]
