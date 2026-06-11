"""MyFitnessPal intake parser — synthetic fixtures only (no real export rows)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from premura.parsers.base import normalize_parse_output
from premura.parsers.myfitnesspal import SOURCE_ID, SOURCE_KIND, MyFitnessPalParser

NUTRITION_HEADER = (
    "Date,Meal,Calories,Fat (g),Saturated Fat,Polyunsaturated Fat,Monounsaturated Fat,"
    "Trans Fat,Cholesterol,Sodium (mg),Potassium,Carbohydrates (g),Fiber,Sugar,"
    "Protein (g),Vitamin A,Vitamin C,Calcium,Iron,Note"
)

# Three synthetic meals: a full row, a row with an empty cell (unknown, not
# zero), and a note-carrying row. Values are made up.
NUTRITION_CSV = (
    NUTRITION_HEADER + "\n"
    "2026-01-05,Breakfast,400.0,10.0,3.0,1.0,4.0,0.0,50.0,300.0,400.0,"
    "55.0,6.0,12.0,20.0,10.0,40.0,15.0,8.0,\n"
    "2026-01-05,Lunch,650.5,22.0,,2.0,8.0,0.0,80.0,900.0,600.0,"
    "70.0,9.0,10.0,35.0,5.0,20.0,10.0,12.0,\n"
    "2026-01-06,Dinner,500.0,15.0,5.0,1.5,6.0,0.0,60.0,700.0,500.0,"
    "60.0,7.0,9.0,30.0,8.0,25.0,12.0,10.0,post-run meal\n"
)

EXERCISE_CSV = (
    "Date,Exercise,Type,Exercise Calories,Exercise Minutes,Sets,Reps Per Set,"
    "Kilograms,Steps,Note\n"
    "2026-01-05,Synthetic run,Cardio,300.0,30,,,,4000,\n"
)

MEASUREMENT_CSV = """Date
"""

BAD_ROW_CSV = f"""{NUTRITION_HEADER}
2026-01-07,Lunch,not-a-number,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,
not-a-date,Dinner,100.0,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,
2026-01-07,,100.0,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,
"""


@pytest.fixture
def export_zip(tmp_path: Path) -> Path:
    path = tmp_path / "File-Export-2026-01-01-to-2026-01-31.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Nutrition-Summary-2026-01-01-to-2026-01-31.csv", NUTRITION_CSV)
        zf.writestr("Exercise-Summary-2026-01-01-to-2026-01-31.csv", EXERCISE_CSV)
        zf.writestr("Measurement-Summary-2026-01-01-to-2026-01-31.csv", MEASUREMENT_CSV)
    return path


def _parse(path: Path):
    observation, intake = normalize_parse_output(MyFitnessPalParser().parse(path))
    assert observation is None, "intake-only parser must emit no observation batch"
    assert intake is not None
    return intake


def test_zip_parses_nutrition_events(export_zip: Path) -> None:
    batch = _parse(export_zip)
    assert len(batch.nutrition_events) == 3
    batch.validate()

    by_meal = {(e.start_utc.date().isoformat(), e.meal_label): e for e in batch.nutrition_events}
    breakfast = by_meal[("2026-01-05", "Breakfast")]
    keys = {q.quantity_key: q for q in breakfast.event_quantities}
    assert len(keys) == 17
    assert keys["energy"].value_num == 400.0
    assert keys["energy"].unit == "kcal"
    assert keys["sodium"].unit == "mg"
    assert keys["vitamin_a"].unit is None  # MFP labels no unit; none is invented
    assert all(q.subject == "event" for q in breakfast.event_quantities)
    assert breakfast.items == []  # summary export carries no per-food items
    assert breakfast.local_tz is None  # bare diary date; no timezone invented
    assert breakfast.source_id == SOURCE_ID
    assert SOURCE_ID in batch.source_descriptors


def test_empty_cell_is_unknown_not_zero(export_zip: Path) -> None:
    batch = _parse(export_zip)
    lunch = next(e for e in batch.nutrition_events if e.meal_label == "Lunch")
    keys = {q.quantity_key for q in lunch.event_quantities}
    assert "fat_saturated" not in keys  # empty cell skipped, not fabricated as 0
    assert len(keys) == 16


def test_note_lands_in_raw_payload(export_zip: Path) -> None:
    batch = _parse(export_zip)
    dinner = next(e for e in batch.nutrition_events if e.meal_label == "Dinner")
    assert dinner.raw_payload == {"note": "post-run meal"}


def test_skipped_files_are_declared_not_silent(export_zip: Path) -> None:
    batch = _parse(export_zip)
    # 'Steps' resolves to a canonical metric -> a skipped row with the seam reason.
    skipped_fields = {s.raw_field for s in batch.skipped_rows}
    assert "exercise_summary.Steps" in skipped_fields
    # Ladder-homeless exercise columns -> declared unmapped, never dropped.
    assert f"vendor:{SOURCE_KIND}:exercise_summary.Exercise Calories" in batch.unmapped_metrics
    assert f"vendor:{SOURCE_KIND}:exercise_summary.Kilograms" in batch.unmapped_metrics


def test_bare_nutrition_csv_parses(tmp_path: Path) -> None:
    csv_path = tmp_path / "Nutrition-Summary-2026-01-01-to-2026-01-31.csv"
    csv_path.write_text(NUTRITION_CSV, encoding="utf-8")
    batch = _parse(csv_path)
    assert len(batch.nutrition_events) == 3


def test_malformed_rows_surface_as_skipped(tmp_path: Path) -> None:
    csv_path = tmp_path / "Nutrition-Summary-bad.csv"
    csv_path.write_text(BAD_ROW_CSV, encoding="utf-8")
    batch = _parse(csv_path)
    assert batch.nutrition_events == []
    reasons = " | ".join(s.reason for s in batch.skipped_rows)
    assert "non-numeric quantity" in reasons
    assert "unparseable Date" in reasons
    assert "missing Date or Meal" in reasons


def test_dedupe_key_stable_per_date_meal(export_zip: Path) -> None:
    a = _parse(export_zip)
    b = _parse(export_zip)
    assert [e.dedupe_key for e in a.nutrition_events] == [e.dedupe_key for e in b.nutrition_events]
    assert len({e.dedupe_key for e in a.nutrition_events}) == 3


def test_zip_without_nutrition_member_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-mfp.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("something-else.csv", "a,b\n1,2\n")
    with pytest.raises(ValueError, match="no Nutrition-Summary"):
        MyFitnessPalParser().parse(path)


def test_declares_no_observation_metrics() -> None:
    assert MyFitnessPalParser().declares_metrics() == []
