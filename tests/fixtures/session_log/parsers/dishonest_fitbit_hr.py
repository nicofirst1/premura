"""Reference parser: the DISHONEST Fitbit-HR parser (must be graded FAIL).

This is a test fixture, NOT a shipped production parser. It is the adversary the
honesty rail must catch (NFR-006 / NFR-007): a parser whose own metadata "looks
clean" yet silently drops a source field.

It is identical to ``good_fitbit_hr`` (same ``bpm -> heart_rate`` mapping; loads
fine; runtime-valid) EXCEPT that it silently drops EXACTLY ONE field,
``altitude_m``: it neither loads ``altitude_m`` as a canonical metric NOR lists
it in ``unmapped_metrics`` / ``skipped_rows``. It DOES declare ``timestamp`` and
``confidence``, so ``altitude_m`` is the single, unambiguous silent drop.

The point of the fixture: the grader reconciles against
``fixture_fields.yaml`` (ground truth), so it catches ``altitude_m`` as a
``silent_drop`` even though this parser's self-report claims nothing is wrong.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor

SOURCE_KIND = "fitbit_heart_rate"
SOURCE_ID = "fitbit_heart_rate:device"

# Note the silent drop: ``altitude_m`` is a real CSV field, but it is declared
# NOWHERE here. The parser's metadata therefore looks complete while hiding one
# field from the honesty reconciliation.
UNMAPPED_FIELDS = ["timestamp", "confidence"]


def _parse_ts(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt.astimezone(UTC).replace(tzinfo=None)


class DishonestFitbitHrParser:
    """Dishonest reference parser: silently drops ``altitude_m``."""

    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
            unmapped_metrics=list(UNMAPPED_FIELDS),
        ).attach_source_artifact(path)
        result.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID,
            source_kind=SOURCE_KIND,
            device_manufacturer="Fitbit",
        )
        with path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                bpm = row.get("bpm")
                if not bpm:
                    continue
                ts = _parse_ts(row["timestamp"])
                result.measurements.append(
                    Measurement(
                        ts_utc=ts,
                        metric_id="heart_rate",
                        unit="bpm",
                        source_id=SOURCE_ID,
                        source_kind=SOURCE_KIND,
                        value_num=float(bpm),
                        source_uuid=f"{SOURCE_KIND}:{row['timestamp']}",
                    )
                )
        result.validate()
        return result


__all__ = ["DishonestFitbitHrParser", "SOURCE_KIND"]
