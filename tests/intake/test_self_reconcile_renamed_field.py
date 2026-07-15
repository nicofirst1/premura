"""WP02 T005 — renamed-field absorption fails the self-reconcile gate (FR-009).

The spec-named edge case (SC-007, acceptance scenario 5): in the 2026-06-04
clean re-test, a local 14B's only near-miss was consuming the ``timestamp``
column into ``ts_utc`` without listing it — the column was *used* but invisible
to the honesty account. FR-009 sharpens the declared-gap rule: a column
consumed under **any** output name is still a consumed column and must be
declared accounted (in ``mapped_columns``) or be an explicit gap. Renaming is
not declaring.

Per research §R-6 the existing gate arithmetic (``unaccounted = source_columns
− (mapped ∪ declared_gaps)``) already fails this case; this test is the
committed deterministic proof that pins the rule against regression. Default
suite: no model, no network, no randomness.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime

from premura.harness.self_reconcile import self_reconcile
from premura.parsers.base import IngestBatch, Measurement, SourceDescriptor
from tests import FIXTURES_DIR

FIXTURE_DIR = FIXTURES_DIR / "session_log"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"

TIMESTAMP_COLUMN = "timestamp"
BPM_COLUMN = "bpm"
_SOURCE_KIND = "fitbit_heart_rate"


def _read_header() -> list[str]:
    """The fixture's real header — the test learns column names from the file."""
    with SYNTHETIC_CSV.open(encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    return [column.strip() for column in header]


def _absorbing_batch() -> IngestBatch:
    """A batch that GENUINELY consumes both ``bpm`` and ``timestamp``.

    Mimics the audit case: every measurement's ``ts_utc`` is parsed from the
    fixture's timestamp column (the renamed output field) and ``value_num``
    from the bpm column — so the timestamp column is consumed, not ignored.
    Whether it is *declared* is the caller's choice via ``mapped_columns``.
    """
    measurements: list[Measurement] = []
    with SYNTHETIC_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ts_utc = (
                datetime.fromisoformat(row[TIMESTAMP_COLUMN].replace("Z", "+00:00"))
                .astimezone(UTC)
                .replace(tzinfo=None)
            )
            measurements.append(
                Measurement(
                    ts_utc=ts_utc,
                    metric_id="heart_rate",
                    unit="bpm",
                    source_id=_SOURCE_KIND,
                    source_kind=_SOURCE_KIND,
                    value_num=float(row[BPM_COLUMN]),
                    source_uuid=f"{_SOURCE_KIND}:{row[TIMESTAMP_COLUMN]}",
                )
            )
    # Every header column EXCEPT bpm (mapped) and timestamp (the absorbed one,
    # whose accounting each test controls) is declared as an explicit gap.
    gaps = [c for c in _read_header() if c not in (BPM_COLUMN, TIMESTAMP_COLUMN)]
    return IngestBatch(
        source_kind=_SOURCE_KIND,
        declared_metrics=["heart_rate"],
        measurements=measurements,
        source_descriptors={
            _SOURCE_KIND: SourceDescriptor(source_id=_SOURCE_KIND, source_kind=_SOURCE_KIND)
        },
        unmapped_metrics=gaps,
    )


def test_fixture_header_carries_the_audit_columns() -> None:
    """The committed fixture really has the columns the audit case names."""
    header = _read_header()
    assert TIMESTAMP_COLUMN in header
    assert BPM_COLUMN in header


def test_renamed_field_absorption_fails_the_gate() -> None:
    """Consumed-into-``ts_utc`` but undeclared timestamp column → FAIL (FR-009)."""
    batch = _absorbing_batch()
    assert batch.measurements, "batch must genuinely consume the fixture rows"

    # The silent absorption: only bpm is declared mapped; the timestamp column
    # fed every ts_utc but is neither mapped nor declared as a gap.
    result = self_reconcile(SYNTHETIC_CSV, batch, mapped_columns={BPM_COLUMN})

    assert result.passed is False
    assert TIMESTAMP_COLUMN in result.unaccounted
    assert result.unaccounted == [TIMESTAMP_COLUMN]


def test_declared_renamed_field_passes_the_gate() -> None:
    """Positive contrast: declaring the consumed column accounted → PASS.

    The timestamp column WAS consumed (into ``ts_utc``); listing it in
    ``mapped_columns`` is the honest statement. With every other header column
    already declared as a gap, the gate passes.
    """
    batch = _absorbing_batch()

    result = self_reconcile(SYNTHETIC_CSV, batch, mapped_columns={BPM_COLUMN, TIMESTAMP_COLUMN})

    assert result.passed is True
    assert result.unaccounted == []
    assert TIMESTAMP_COLUMN in result.accounted
