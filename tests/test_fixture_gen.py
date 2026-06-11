"""Tests for the synthetic fixture auto-generator (m5 / FR-1..FR-7).

All offline + deterministic (NFR-5): no model, no network, no clock, no Ollama
marker. Determinism is asserted by generating twice from one seed and comparing
bytes (FR-1). The metric registry the generator draws from is the committed
``src/premura/dim_metric.yaml`` (the repo's real metric registry seed — see the
mission deviation note); never a list hardcoded in ``fixture_gen``.
"""

from __future__ import annotations

import pytest

from premura.harness.fixture_gen import (
    FixtureSpec,
    UnknownDrawerError,
    generate_fixture,
    registry_metric_ids,
)

# A handful of well-known real vendor tokens a synthetic source name must never be.
_REAL_VENDORS = {"fitbit", "garmin", "apple", "oura", "whoop", "withings", "samsung", "polar"}


def test_same_seed_yields_byte_identical_output() -> None:
    """FR-1: same spec -> byte-identical CSV and manifest text (determinism)."""
    spec = FixtureSpec(seed=7)
    a = generate_fixture(spec)
    b = generate_fixture(spec)
    assert a.csv_text == b.csv_text
    assert a.manifest_text == b.manifest_text


def test_different_seeds_yield_different_fixtures() -> None:
    """FR-1: a different seed produces a different fixture (not a constant)."""
    a = generate_fixture(FixtureSpec(seed=1))
    b = generate_fixture(FixtureSpec(seed=2))
    assert (a.csv_text, a.manifest_text) != (b.csv_text, b.manifest_text)


@pytest.mark.parametrize("seed", range(20))
def test_challenge_invariants_present(seed: int) -> None:
    """FR-3: every generated observation fixture is a fair, honest challenge.

    (a) >=1 mappable column whose distinct canonical metric is in the registry,
    (b) >=1 declared-gap column with no canonical home,
    (c) a structural timestamp column in a known encoding,
    (d) distinct canonical metrics (the grader's D6 distinct-metric rule).
    """
    fixture = generate_fixture(FixtureSpec(seed=seed))

    mappable = fixture.mappable_fields
    gaps = fixture.gap_fields
    assert len(mappable) >= 1, "no mappable column"
    assert len(gaps) >= 1, "no declared-gap column"

    # Canonical metrics are drawn from the registry and are distinct (D6).
    metrics = [f.canonical_metric for f in mappable]
    assert all(m in registry_metric_ids() for m in metrics)
    assert len(metrics) == len(set(metrics)), "duplicate canonical metric"

    # A structural timestamp column exists in a known encoding (c).
    assert fixture.timestamp_encoding in {"iso8601", "epoch_seconds", "epoch_micros"}

    # CSV header == manifest field order, and row_count data rows.
    csv_lines = fixture.csv_text.splitlines()
    assert csv_lines[0].split(",") == fixture.csv_columns
    assert len(csv_lines) == 1 + fixture.spec.row_count


@pytest.mark.parametrize("seed", range(20))
def test_source_name_is_not_a_real_vendor(seed: int) -> None:
    """FR-3 / NFR-1: the fabricated source name is never a real vendor brand."""
    fixture = generate_fixture(FixtureSpec(seed=seed))
    lowered = fixture.source_name.lower()
    assert not any(vendor in lowered for vendor in _REAL_VENDORS)


def test_unknown_drawer_fails_loudly() -> None:
    """FR-2: a drawer with no registered strategy raises, never defaults silently."""
    with pytest.raises(UnknownDrawerError):
        generate_fixture(FixtureSpec(seed=1, drawer="intake"))
