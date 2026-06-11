"""MyFitnessPal "File Export" parser — nutrition intake seam.

Reads the official MyFitnessPal data export (a zip of per-date-range summary
CSVs, or the bare ``Nutrition-Summary-*.csv``) and emits an **intake-only**
:class:`~premura.parsers.base.ParseOutput`. One CSV row is one per-meal
aggregate (date + meal + nutrient totals), which maps onto one
:class:`NutritionIntakeInput` whose amounts are event-level quantities
(``subject="event"``) — the export carries no per-food items.

Seam and scope decisions (CONTRACT.md "Two seams"):

- **Nutrition-Summary** rows are eating occurrences → ``IntakeBatch``. A meal's
  kcal is *consumed* energy; it never becomes an observation row.
- **Exercise-Summary** rows are *expended*-energy observations — a different
  seam this parser deliberately does not emit (MyFitnessPal exercise is
  typically synced *from* the wearable source already ingested, so emitting it
  would double-count). Columns that resolve to a canonical metric are surfaced
  as ``skipped_rows`` (had a home, produced no loadable row, with the reason);
  columns the decision tree cannot place are declared in ``unmapped_metrics``.
- **Measurement-Summary** columns beyond ``Date`` are declared the same way.

Timestamps: MyFitnessPal exports a bare local diary **date** with no timezone.
The event is stored at that date's midnight as a naive timestamp with
``local_tz=None``; the nutrition resolver then buckets it on the UTC-day
fallback, which equals the MyFitnessPal diary date verbatim — no timezone is
invented. (Same posture as wide-format BMT rows without a ``Time`` column.)

Unit notes: columns whose MyFitnessPal header names a unit get that unit
(``Fat (g)``, ``Sodium (mg)``). ``Vitamin A`` / ``Vitamin C`` / ``Calcium`` /
``Iron`` are exported without a unit label (the app shows them as percent of
daily value), so their quantities carry ``unit=None`` rather than a fabricated
unit; trends over them remain meaningful within this source.

Idempotency: ``dedupe_key = sha256("myfitnesspal|<date>|<meal>")`` — one event
per diary date + meal. Re-ingesting an overlapping export range is a no-op for
already-loaded meals; the store is append-only, so an edit made in the app to
an already-ingested day is not retroactively updated (first write wins).
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path

from .base import (
    IntakeBatch,
    NutritionIntakeInput,
    NutritionQuantityInput,
    ParseOutput,
    SkippedRow,
    SourceDescriptor,
)
from .lookup import suggest_metric

SOURCE_KIND = "myfitnesspal"
SOURCE_ID = "myfitnesspal:file_export"

NUTRITION_MEMBER_PREFIX = "Nutrition-Summary"
EXERCISE_MEMBER_PREFIX = "Exercise-Summary"
MEASUREMENT_MEMBER_PREFIX = "Measurement-Summary"

# Source column -> (quantity_key, unit). Quantity keys are intake-seam
# vocabulary (CONTRACT.md: they do not travel the suggest_metric ladder and are
# not observation metric_ids). Units come from the export header where it names
# one; the four unit-unlabeled columns carry None (see module docstring).
NUTRITION_COLUMNS: dict[str, tuple[str, str | None]] = {
    "Calories": ("energy", "kcal"),
    "Fat (g)": ("fat_total", "g"),
    "Saturated Fat": ("fat_saturated", "g"),
    "Polyunsaturated Fat": ("fat_polyunsaturated", "g"),
    "Monounsaturated Fat": ("fat_monounsaturated", "g"),
    "Trans Fat": ("fat_trans", "g"),
    "Cholesterol": ("cholesterol", "mg"),
    "Sodium (mg)": ("sodium", "mg"),
    "Potassium": ("potassium", "mg"),
    "Carbohydrates (g)": ("carbohydrate", "g"),
    "Fiber": ("fiber", "g"),
    "Sugar": ("sugar", "g"),
    "Protein (g)": ("protein", "g"),
    "Vitamin A": ("vitamin_a", None),
    "Vitamin C": ("vitamin_c", None),
    "Calcium": ("calcium", None),
    "Iron": ("iron", None),
}

# Columns consumed by the event shape itself rather than mapped to a quantity.
NUTRITION_STRUCTURAL = {"Date", "Meal", "Note"}

_SKIP_FILE_REASON = (
    "observation-seam data deliberately not emitted by the intake parser: "
    "MyFitnessPal exercise/measurement summaries are typically synced from a "
    "wearable source already ingested (double-count risk); ingest the wearable "
    "export instead"
)


def _dedupe_key(date_str: str, meal: str) -> str:
    payload = f"{SOURCE_KIND}|{date_str}|{meal}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_date(value: str):
    from datetime import datetime

    return datetime.strptime(value.strip(), "%Y-%m-%d")


class MyFitnessPalParser:
    """Parses a MyFitnessPal file export into an intake-only batch."""

    source_kind = SOURCE_KIND
    language_hint: str | None = "en"

    def declares_metrics(self) -> list[str]:
        # Intake-only: emits no observation metric_ids, so no dim_metric rows.
        return []

    def parse(self, path: Path) -> ParseOutput:
        batch = IntakeBatch()
        batch.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID,
            source_kind=SOURCE_KIND,
            app_package="com.myfitnesspal.android",
            app_name="MyFitnessPal",
        )
        unmapped: set[str] = set()

        if zipfile.is_zipfile(path):
            self._parse_zip(path, batch, unmapped)
        else:
            self._parse_nutrition_text(
                path.read_text(encoding="utf-8-sig", errors="replace"), batch, unmapped
            )

        batch.unmapped_metrics = sorted(unmapped)
        return ParseOutput(intake=batch)

    # ----- zip routing ------------------------------------------------------ #
    def _parse_zip(self, path: Path, batch: IntakeBatch, unmapped: set[str]) -> None:
        with zipfile.ZipFile(path) as zf:
            saw_nutrition = False
            for member in zf.namelist():
                stem = Path(member).name
                if stem.startswith(NUTRITION_MEMBER_PREFIX) and stem.endswith(".csv"):
                    saw_nutrition = True
                    text = zf.read(member).decode("utf-8-sig", errors="replace")
                    self._parse_nutrition_text(text, batch, unmapped)
                elif stem.startswith((EXERCISE_MEMBER_PREFIX, MEASUREMENT_MEMBER_PREFIX)):
                    file_key = (
                        "exercise_summary"
                        if stem.startswith(EXERCISE_MEMBER_PREFIX)
                        else "measurement_summary"
                    )
                    header = (
                        zf.read(member).decode("utf-8-sig", errors="replace").splitlines() or [""]
                    )[0]
                    self._declare_skipped_file(file_key, header, batch, unmapped)
            if not saw_nutrition:
                raise ValueError(
                    f"{path.name}: no {NUTRITION_MEMBER_PREFIX}*.csv member found; "
                    "not a MyFitnessPal file export?"
                )

    def _declare_skipped_file(
        self, file_key: str, header_line: str, batch: IntakeBatch, unmapped: set[str]
    ) -> None:
        """Surface every column of a deliberately skipped member file.

        A column that resolves to a canonical metric had a home but produced no
        loadable row here -> ``skipped_rows`` with the seam reason. A column the
        ladder cannot place -> ``unmapped_metrics`` (vendor label).
        """
        columns = next(csv.reader(io.StringIO(header_line)), []) if header_line else []
        for col in columns:
            col = col.strip()
            if not col or col == "Date":
                continue
            if suggest_metric(col) is not None:
                batch.skipped_rows.append(
                    SkippedRow(raw_field=f"{file_key}.{col}", reason=_SKIP_FILE_REASON)
                )
            else:
                unmapped.add(f"vendor:{SOURCE_KIND}:{file_key}.{col}")

    # ----- nutrition -------------------------------------------------------- #
    def _parse_nutrition_text(self, text: str, batch: IntakeBatch, unmapped: set[str]) -> None:
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = [c for c in (reader.fieldnames or []) if c and c.strip()]

        # Decision-tree pass over the header: any column that is neither
        # structural nor a known quantity is declared, never silently dropped.
        for col in fieldnames:
            if col in NUTRITION_STRUCTURAL or col in NUTRITION_COLUMNS:
                continue
            if suggest_metric(col) is not None:  # pragma: no cover - defensive
                continue
            unmapped.add(f"vendor:{SOURCE_KIND}:nutrition_summary.{col}")

        for row in reader:
            date_str = (row.get("Date") or "").strip()
            meal = (row.get("Meal") or "").strip()
            if not date_str or not meal:
                batch.skipped_rows.append(
                    SkippedRow(
                        raw_field=f"nutrition_summary:{date_str or '?'}|{meal or '?'}",
                        reason="row missing Date or Meal; cannot anchor an intake event",
                    )
                )
                continue
            try:
                start = _parse_date(date_str)
            except ValueError:
                batch.skipped_rows.append(
                    SkippedRow(
                        raw_field=f"nutrition_summary:{date_str}|{meal}",
                        reason=f"unparseable Date {date_str!r} (expected YYYY-MM-DD)",
                    )
                )
                continue

            quantities: list[NutritionQuantityInput] = []
            bad_value = False
            for col, (key, unit) in NUTRITION_COLUMNS.items():
                raw = (row.get(col) or "").strip()
                if raw == "":
                    continue  # unknown, not zero — never fabricate
                try:
                    value = float(raw)
                except ValueError:
                    batch.skipped_rows.append(
                        SkippedRow(
                            raw_field=f"nutrition_summary:{date_str}|{meal}|{col}",
                            reason=f"non-numeric quantity {raw!r}",
                        )
                    )
                    bad_value = True
                    break
                quantities.append(
                    NutritionQuantityInput(
                        quantity_key=key, value_num=value, unit=unit, subject="event"
                    )
                )
            if bad_value:
                continue

            note = (row.get("Note") or "").strip()
            batch.nutrition_events.append(
                NutritionIntakeInput(
                    source_id=SOURCE_ID,
                    source_kind=SOURCE_KIND,
                    start_utc=start,
                    dedupe_key=_dedupe_key(date_str, meal),
                    local_tz=None,
                    meal_label=meal,
                    source_uuid=f"{date_str}|{meal}",
                    event_quantities=quantities,
                    raw_payload={"note": note} if note else None,
                )
            )
