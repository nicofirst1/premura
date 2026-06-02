"""Reference parser: the HONEST Fitbit-HR parser (passes all three grader rules).

This is a test fixture, NOT a shipped production parser. It is installed into a
sandbox by later WPs so the always-on check has a known-good baseline; Fitbit
itself stays a genuinely unsupported target for the live trial.

It conforms to the real ``PluginParser`` protocol (``src/premura/parsers/base.py``)
so it runs through the REAL ingest/load seam — the boundary-crossing fixture for
the fidelity gate (D1). The three grader rules it satisfies:

* "it loaded"      — emits real ``Measurement`` rows whose only ``metric_id`` is
  ``heart_rate``, a metric that ACTUALLY EXISTS in ``dim_metric.yaml``.
* "runtime-valid"  — ``declared_metrics == emitted metric_ids``; no ``derived:``
  metric; ``parse()`` produces a batch that ``validate()``s without raising.
* "honest about gaps" — every CSV source field is either the mapped canonical
  metric (``bpm -> heart_rate``) or declared in ``unmapped_metrics``
  (``timestamp``, ``confidence``, ``altitude_m``). Nothing is silently dropped.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor

SOURCE_KIND = "fitbit_heart_rate"
SOURCE_ID = "fitbit_heart_rate:device"

# Every non-mapped source field is declared honest-unmapped. Kept in sync with
# tests/fixtures/session_log/fixture_fields.yaml (the ground truth).
UNMAPPED_FIELDS = ["timestamp", "confidence", "altitude_m"]


def _parse_ts(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt.astimezone(UTC).replace(tzinfo=None)


class GoodFitbitHrParser:
    """Honest reference parser. Maps ``bpm -> heart_rate``; declares the rest."""

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


__all__ = ["GoodFitbitHrParser", "SOURCE_KIND"]
