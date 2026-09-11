"""FeelingsJournal parser tests."""

from __future__ import annotations

from pathlib import Path

from premura.parsers.feelings_journal import FeelingsJournalParser
from premura.parsers.lookup import metric_definition


def _write_feelings_journal_csv(tmp_path: Path) -> Path:
    csv = (
        "Date,Primary Feeling,Secondary Feeling,Tertiary Feeling,Comment,Tags\n"
        "2026-01-05T08:15:30.000000,Curious,Interested,Engaged,Trying out the new export,\n"
        "2026-01-04T21:40:05.500000,Calm,Content,,,\n"
    )
    path = tmp_path / "feelings_journal_export.csv"
    path.write_text(csv, encoding="utf-8")
    return path


def test_feelings_journal_rows_map_to_feeling_measurements(tmp_path):
    result = FeelingsJournalParser().parse(_write_feelings_journal_csv(tmp_path))

    feelings = [m for m in result.measurements if m.metric_id == "feeling"]
    assert len(feelings) == 2
    assert feelings[0].value_text == "Curious"
    assert feelings[0].value_num is None
    assert feelings[0].unit == "feeling_label"
    assert feelings[0].local_tz is None
    assert feelings[0].raw_payload == {
        "primary_feeling": "Curious",
        "secondary_feeling": "Interested",
        "tertiary_feeling": "Engaged",
        "tags": [],
    }
    assert feelings[1].value_text == "Calm"
    assert feelings[1].raw_payload == {
        "primary_feeling": "Calm",
        "secondary_feeling": "Content",
        "tertiary_feeling": None,
        "tags": [],
    }


def test_feelings_journal_comment_lands_in_clinical_notes(tmp_path):
    result = FeelingsJournalParser().parse(_write_feelings_journal_csv(tmp_path))

    assert len(result.clinical_notes) == 1
    assert result.clinical_notes[0].text == "Trying out the new export"
    assert result.clinical_notes[0].source_id == "feelings_journal:app"


def test_feelings_journal_declared_metric_registered_in_ontology():
    definition = metric_definition("feeling")
    assert definition is not None
    assert definition["canonical_unit"] == "enum"
    assert definition["category"] == "mental_health"


def test_feelings_journal_missing_primary_feeling_is_skipped(tmp_path):
    path = tmp_path / "feelings_journal_export.csv"
    path.write_text(
        "Date,Primary Feeling,Secondary Feeling,Tertiary Feeling,Comment,Tags\n"
        "2026-01-06T07:00:00.000000,,,,,\n",
        encoding="utf-8",
    )

    result = FeelingsJournalParser().parse(path)

    assert result.measurements == []
    assert len(result.skipped_rows) == 1
    assert result.skipped_rows[0].raw_field == "rows[0]:Primary Feeling"


def test_feelings_journal_dedupe_key_format(tmp_path):
    result = FeelingsJournalParser().parse(_write_feelings_journal_csv(tmp_path))

    assert all(m.dedupe_key.startswith("feelings_journal:") for m in result.measurements)
