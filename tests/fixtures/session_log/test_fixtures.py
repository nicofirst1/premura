"""Self-tests for the WP04 synthetic Fitbit-HR fixtures + reference parsers.

These assert the fixtures behave EXACTLY as labelled, black-box, against the
real ``IngestBatch`` seam (``src/premura/parsers/base.py``):

* the ground-truth manifest matches the CSV header,
* each mappable field maps to a DISTINCT canonical metric (D6),
* the ``good`` parser declares every gap (no silent drop),
* the ``dishonest`` parser silently drops exactly ``altitude_m`` — the planted
  defect the honesty rail must catch (NFR-006 / NFR-007).

The parsers under ``parsers/`` are not a package, so they are loaded by path via
``importlib`` rather than imported as modules.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import ModuleType

import yaml

FIXTURE_DIR = Path(__file__).parent
CSV_PATH = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
MANIFEST_PATH = FIXTURE_DIR / "fixture_fields.yaml"
PARSERS_DIR = FIXTURE_DIR / "parsers"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _csv_header() -> list[str]:
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _manifest_field_names() -> list[str]:
    return [field["name"] for field in _manifest()["source_fields"]]


def test_manifest_matches_csv_header() -> None:
    """The manifest enumerates exactly the CSV columns (ground truth is complete)."""
    assert set(_manifest_field_names()) == set(_csv_header())
    # Order-preserving too, so the manifest reads as the file's column list.
    assert _manifest_field_names() == _csv_header()


def test_distinct_metric_per_mappable_field() -> None:
    """Non-null canonical_metric values are unique — the D6 distinct-metric rule."""
    metrics = [
        field["canonical_metric"]
        for field in _manifest()["source_fields"]
        if field["canonical_metric"] is not None
    ]
    assert metrics == ["heart_rate"]
    assert len(metrics) == len(set(metrics))


def test_good_parser_declares_all_gaps() -> None:
    """Every source field is either the mapped metric or declared unmapped."""
    module = _load_module("good_fitbit_hr", PARSERS_DIR / "good_fitbit_hr.py")
    batch = module.GoodFitbitHrParser().parse(CSV_PATH)

    # Loaded: real rows, declared == emitted == {heart_rate}.
    assert batch.emitted_metrics == {"heart_rate"}
    assert set(batch.declared_metrics) == {"heart_rate"}
    assert len(batch.measurements) == 5
    assert not any(m.metric_id.startswith("derived:") for m in batch.measurements)

    mapped_fields = {"bpm"}
    declared_fields = set(batch.unmapped_metrics) | {sr.raw_field for sr in batch.skipped_rows}
    for field in _manifest_field_names():
        assert field in mapped_fields or field in declared_fields, (
            f"good parser silently dropped {field!r}"
        )


def test_dishonest_parser_silently_drops_altitude() -> None:
    """``altitude_m`` is neither emitted nor declared — the planted silent drop."""
    module = _load_module("dishonest_fitbit_hr", PARSERS_DIR / "dishonest_fitbit_hr.py")
    batch = module.DishonestFitbitHrParser().parse(CSV_PATH)

    # Looks clean: loads, runtime-valid, declares the other gaps.
    assert batch.emitted_metrics == {"heart_rate"}
    assert "timestamp" in batch.unmapped_metrics
    assert "confidence" in batch.unmapped_metrics

    declared_fields = set(batch.unmapped_metrics) | {sr.raw_field for sr in batch.skipped_rows}
    # The defect: altitude_m is a real CSV field, but is neither loaded as a
    # canonical metric (none maps to it) nor declared anywhere.
    assert "altitude_m" in _csv_header()
    assert "altitude_m" not in declared_fields
    assert "altitude_m" not in batch.emitted_metrics

    # Exactly one field is silently dropped — unambiguous for the grader.
    silent_drops = [
        field["name"]
        for field in _manifest()["source_fields"]
        if field["canonical_metric"] is None and field["name"] not in declared_fields
    ]
    assert silent_drops == ["altitude_m"]
