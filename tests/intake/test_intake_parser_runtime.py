"""Runtime dispatch tests for the parser intake path (WP01 / FR-007).

Stance: black-box. We assert via the parser output, the public dispatch helper
``normalize_parse_output``, and warehouse rows — never by patching
inside-boundary internals. Three parser flavors prove the seam routing:

* an **observation-only** parser (a bare ``IngestBatch``, today's contract) is
  unchanged and lands only in the observation tables;
* an **intake-only** parser (a ``ParseOutput`` carrying an ``IntakeBatch``)
  lands only in the intake tables;
* a **both** parser lands in both, with neither folded into the other.

We also lock the new ``IntakeBatch`` gap surface: an intake parser can declare
an unmapped field, and that gap rides on the batch as review metadata without
ever becoming a loadable row.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from premura.parsers.base import (
    IngestBatch,
    IntakeBatch,
    Measurement,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    ParseOutput,
    SkippedRow,
    SourceDescriptor,
    normalize_parse_output,
)
from premura.store.loader import load
from premura.store.profile_intake import persist_intake_batch

TS = datetime(2026, 1, 1, 8, 0, 0)


# --------------------------------------------------------------------------- #
# Tiny in-test parsers (one per seam). They mirror the real protocol surface.
# --------------------------------------------------------------------------- #
def _observation_batch(source_path: Path) -> IngestBatch:
    batch = IngestBatch(
        source_kind="testsrc",
        declared_metrics=["heart_rate"],
        measurements=[
            Measurement(
                ts_utc=TS,
                metric_id="heart_rate",
                unit="bpm",
                source_id="testsrc_dev",
                source_kind="testsrc",
                value_num=62.0,
                source_uuid="m1",
            )
        ],
        source_descriptors={
            "testsrc_dev": SourceDescriptor(source_id="testsrc_dev", source_kind="testsrc")
        },
    )
    return batch.attach_source_artifact(source_path)


def _intake_batch(*, with_gap: bool = False) -> IntakeBatch:
    batch = IntakeBatch(
        source_descriptors={
            "testsrc_app": SourceDescriptor(source_id="testsrc_app", source_kind="testsrc")
        },
        nutrition_events=[
            NutritionIntakeInput(
                source_id="testsrc_app",
                source_kind="testsrc",
                start_utc=TS,
                dedupe_key="nut-1",
                items=[
                    NutritionItemInput(
                        item_label="oats",
                        quantities=[
                            NutritionQuantityInput(
                                quantity_key="energy", value_num=150.0, unit="kcal"
                            )
                        ],
                    )
                ],
            )
        ],
    )
    if with_gap:
        batch.unmapped_metrics.append("mystery_micronutrient")
        batch.skipped_rows.append(
            SkippedRow(raw_field="garbled_quantity", reason="non-numeric amount")
        )
    return batch


class _ObservationOnlyParser:
    """Returns a bare IngestBatch — the unchanged, historical contract."""

    source_kind = "testsrc"

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:
        return _observation_batch(path)


class _IntakeOnlyParser:
    """Returns a ParseOutput carrying only an IntakeBatch."""

    source_kind = "testsrc"

    def declares_metrics(self) -> list[str]:
        return []

    def parse(self, path: Path) -> ParseOutput:  # noqa: ARG002 - source not read
        return ParseOutput(intake=_intake_batch())


class _BothParser:
    """Returns a ParseOutput carrying observation AND intake from one artifact."""

    source_kind = "testsrc"

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> ParseOutput:
        return ParseOutput(observation=_observation_batch(path), intake=_intake_batch())


# --------------------------------------------------------------------------- #
# normalize_parse_output: the single dispatch helper.
# --------------------------------------------------------------------------- #
def test_bare_ingest_batch_normalizes_to_observation_only(tmp_path: Path) -> None:
    source = tmp_path / "s"
    source.write_text("x")
    observation, intake = normalize_parse_output(_ObservationOnlyParser().parse(source))
    assert isinstance(observation, IngestBatch)
    assert intake is None


def test_parse_output_intake_only_normalizes_to_intake_only(tmp_path: Path) -> None:
    observation, intake = normalize_parse_output(_IntakeOnlyParser().parse(tmp_path / "s"))
    assert observation is None
    assert isinstance(intake, IntakeBatch)


def test_parse_output_both_normalizes_to_both(tmp_path: Path) -> None:
    source = tmp_path / "s"
    source.write_text("x")
    observation, intake = normalize_parse_output(_BothParser().parse(source))
    assert isinstance(observation, IngestBatch)
    assert isinstance(intake, IntakeBatch)


def test_normalize_rejects_unknown_output() -> None:
    with pytest.raises(TypeError):
        normalize_parse_output(object())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# End-to-end seam routing against a real warehouse. We route exactly as the
# runtime call sites do: observation -> loader.load, intake -> persist_intake_batch.
# --------------------------------------------------------------------------- #
def _route(conn, output) -> None:
    observation, intake = normalize_parse_output(output)
    if observation is not None:
        load(conn, observation)
    if intake is not None:
        persist_intake_batch(conn, intake)


def test_observation_parser_lands_only_in_observation_tables(
    empty_warehouse, tmp_path: Path
) -> None:
    source = tmp_path / "s"
    source.write_text("x")
    _route(empty_warehouse, _ObservationOnlyParser().parse(source))

    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 1
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 0
    )


def test_intake_parser_lands_only_in_intake_tables(empty_warehouse, tmp_path: Path) -> None:
    _route(empty_warehouse, _IntakeOnlyParser().parse(tmp_path / "s"))

    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 1
    )
    # Intake never coerced into the observation home (two-seam / one-home rule).
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 0
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_clinical_note").fetchone()[0] == 0


def test_both_parser_lands_in_both_homes(empty_warehouse, tmp_path: Path) -> None:
    source = tmp_path / "s"
    source.write_text("x")
    _route(empty_warehouse, _BothParser().parse(source))

    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 1
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 1
    )


# --------------------------------------------------------------------------- #
# IntakeBatch gap surface: declared, validatable, and never a loadable row.
# --------------------------------------------------------------------------- #
def test_intake_batch_carries_unmapped_and_skipped_gaps() -> None:
    batch = _intake_batch(with_gap=True)
    assert batch.unmapped_metrics == ["mystery_micronutrient"]
    assert batch.skipped_rows[0].raw_field == "garbled_quantity"
    # The gap surface is review metadata, not loadable rows; the batch still
    # validates (gaps are not events).
    batch.validate()


def test_declared_gap_does_not_persist_as_a_row(empty_warehouse) -> None:
    batch = _intake_batch(with_gap=True)
    stats = persist_intake_batch(empty_warehouse, batch)
    # The one real event lands; the declared gaps add no rows.
    assert stats.nutrition_events_inserted == 1
    assert (
        empty_warehouse.execute("SELECT COUNT(*) FROM hp.nutrition_intake_event").fetchone()[0] == 1
    )
