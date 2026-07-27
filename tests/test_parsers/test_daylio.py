"""Daylio parser tests."""

from __future__ import annotations

from pathlib import Path

from premura.parsers.daylio import DaylioParser
from premura.parsers.lookup import metric_definition


def _write_daylio_csv(tmp_path: Path) -> Path:
    csv = (
        "full_date,date,weekday,time,mood,activities,scales,note_title,note\n"
        "2026-07-27,July 27,Monday,13:48,meh,work | walk,,Mood note,Private note text\n"
        "2026-07-26,July 26,Sunday,18:20,rad,run,,,\n"
    )
    path = tmp_path / "daylio_export.csv"
    path.write_text(csv, encoding="utf-8")
    return path


def test_daylio_mood_rows_map_to_numeric_scores(tmp_path):
    result = DaylioParser().parse(_write_daylio_csv(tmp_path))

    moods = [m for m in result.measurements if m.metric_id == "mood_score"]
    assert len(moods) == 2
    assert moods[0].value_num == 3.0
    assert moods[0].value_text == "meh"
    assert moods[0].unit == "score_1_5"
    assert moods[0].raw_payload == {
        "mood": "meh",
        "activities": ["work", "walk"],
        "activity_count": 2,
        "weekday": "Monday",
        "scales_present": False,
    }
    assert moods[1].value_num == 5.0
    assert moods[1].value_text == "rad"


def test_daylio_notes_land_in_clinical_notes(tmp_path):
    result = DaylioParser().parse(_write_daylio_csv(tmp_path))

    assert len(result.clinical_notes) == 1
    assert result.clinical_notes[0].text == "Mood note\n\nPrivate note text"
    assert result.clinical_notes[0].source_id == "daylio:app"


def test_daylio_declared_metric_registered_in_ontology():
    definition = metric_definition("mood_score")
    assert definition is not None
    assert definition["canonical_unit"] == "score_1_5"
    assert definition["category"] == "mental_health"


def test_daylio_unknown_mood_is_skipped(tmp_path):
    path = tmp_path / "daylio_export.csv"
    path.write_text(
        "full_date,date,weekday,time,mood,activities,scales,note_title,note\n"
        "2026-07-27,July 27,Monday,13:48,confused,work,,,\n",
        encoding="utf-8",
    )

    result = DaylioParser().parse(path)

    assert result.measurements == []
    assert len(result.skipped_rows) == 1
    assert result.skipped_rows[0].raw_field == "rows[0]:mood"


def test_daylio_dedupe_key_format(tmp_path):
    result = DaylioParser().parse(_write_daylio_csv(tmp_path))

    assert all(m.dedupe_key.startswith("daylio:") for m in result.measurements)
