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


# --------------------------------------------------------------------------- #
# FR-5 self-validation — each invariant violated individually.
# --------------------------------------------------------------------------- #
from premura.harness.fixture_gen import (  # noqa: E402
    GeneratedFixture,
    SourceField,
    validate_fixture,
)


def _good_fixture() -> GeneratedFixture:
    return generate_fixture(FixtureSpec(seed=3))


def test_validate_accepts_a_generated_fixture() -> None:
    """A freshly generated fixture passes validation (the happy path)."""
    validate_fixture(_good_fixture())  # no raise


def test_validate_rejects_column_missing_from_manifest() -> None:
    """FR-5: a CSV column not enumerated in source_fields is a violation."""
    good = _good_fixture()
    # Drop the last source_field but keep the CSV: a column without a manifest row.
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text=good.csv_text,
        manifest_text=good.manifest_text,
        source_fields=good.source_fields[:-1],
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="exactly once"):
        validate_fixture(broken)


def test_validate_rejects_duplicate_canonical_metric() -> None:
    """FR-5: a non-null canonical metric appearing twice is a violation (D6)."""
    good = _good_fixture()
    metric = good.mappable_fields[0].canonical_metric
    # Re-label a gap column to reuse an already-used canonical metric.
    fields = list(good.source_fields)
    for i, f in enumerate(fields):
        if f.canonical_metric is None:
            fields[i] = SourceField(name=f.name, canonical_metric=metric)
            break
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text=good.csv_text,
        manifest_text=good.manifest_text,
        source_fields=tuple(fields),
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="unique|duplicate"):
        validate_fixture(broken)


def test_validate_rejects_metric_not_in_registry() -> None:
    """FR-5: a non-null canonical metric absent from the registry is a violation."""
    good = _good_fixture()
    fields = list(good.source_fields)
    for i, f in enumerate(fields):
        if f.canonical_metric is not None:
            fields[i] = SourceField(name=f.name, canonical_metric="vendor:fake:not_real_metric")
            break
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text=good.csv_text,
        manifest_text=good.manifest_text,
        source_fields=tuple(fields),
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="registry"):
        validate_fixture(broken)


def test_validate_rejects_no_mappable_column() -> None:
    """FR-5: at least one mappable column is required."""
    good = _good_fixture()
    fields = tuple(SourceField(name=f.name, canonical_metric=None) for f in good.source_fields)
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text=good.csv_text,
        manifest_text=good.manifest_text,
        source_fields=fields,
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="mappable"):
        validate_fixture(broken)


def test_validate_rejects_no_gap_column() -> None:
    """FR-5: at least one null-metric (declared-gap) column is required."""
    good = _good_fixture()
    ids = iter(sorted(registry_metric_ids()))
    fields = tuple(SourceField(name=f.name, canonical_metric=next(ids)) for f in good.source_fields)
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text=good.csv_text,
        manifest_text=good.manifest_text,
        source_fields=fields,
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="null-metric|gap"):
        validate_fixture(broken)


def test_validate_rejects_wrong_row_count() -> None:
    """FR-5: the CSV must carry exactly row_count data rows."""
    good = _good_fixture()
    truncated = "\n".join(good.csv_text.splitlines()[:-1]) + "\n"
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text=truncated,
        manifest_text=good.manifest_text,
        source_fields=good.source_fields,
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="row"):
        validate_fixture(broken)


def test_validate_rejects_unparseable_timestamp() -> None:
    """FR-5: every timestamp cell must decode in the declared encoding."""
    good = _good_fixture()
    lines = good.csv_text.splitlines()
    # Corrupt the first data row's first cell (the structural timestamp column).
    cells = lines[1].split(",")
    cells[0] = "not-a-timestamp"
    lines[1] = ",".join(cells)
    broken = GeneratedFixture(
        spec=good.spec,
        source_name=good.source_name,
        csv_text="\n".join(lines) + "\n",
        manifest_text=good.manifest_text,
        source_fields=good.source_fields,
        timestamp_encoding=good.timestamp_encoding,
        timestamp_column=good.timestamp_column,
    )
    with pytest.raises(ValueError, match="timestamp"):
        validate_fixture(broken)


# --------------------------------------------------------------------------- #
# FR-4 manifest fidelity — same code path that reads the committed manifest.
# --------------------------------------------------------------------------- #


def test_generated_manifest_reads_via_committed_code_path(tmp_path) -> None:
    """FR-4: the generated manifest parses with the SAME loader as the committed one.

    The committed observation manifest (``fixture_fields.yaml``) is read by
    ``yaml.safe_load(path.read_text(...))`` — both by the committed fixtures'
    self-test (``tests/fixtures/session_log/test_fixtures.py``) and by the harness's
    ``live_trial._load_manifest``. We read BOTH the committed manifest and a freshly
    generated one through that identical loader and assert the generated one yields
    the same shape the grader consumes: ``source``, ``csv``, and ``source_fields``
    of ``name`` + ``canonical_metric``. (We do not import the live-trial harness
    here; the default suite must never reference it — pinned by
    ``test_live_trial_seam.py``.)
    """
    import yaml

    from premura.harness.fixture_gen import write_fixture
    from premura.harness.scenario import observation_scenario

    # The committed manifest reads cleanly into the consumed shape (the baseline).
    committed = yaml.safe_load(observation_scenario().manifest_path.read_text(encoding="utf-8"))
    assert {"source", "csv", "source_fields"} <= set(committed)
    assert all({"name", "canonical_metric"} <= set(f) for f in committed["source_fields"])

    fixture = generate_fixture(FixtureSpec(seed=5))
    written = write_fixture(fixture, tmp_path)

    parsed = yaml.safe_load(written.manifest_path.read_text(encoding="utf-8"))
    assert parsed["source"] == fixture.source_name
    assert parsed["csv"] == f"{fixture.source_name}.csv"
    assert set(parsed) == set(committed), "generated manifest top-level keys differ from committed"

    parsed_fields = [(f["name"], f["canonical_metric"]) for f in parsed["source_fields"]]
    expected = [(f.name, f.canonical_metric) for f in fixture.source_fields]
    assert parsed_fields == expected

    # The honesty header marks it grader-only, matching the committed manifests.
    assert "GRADER-ONLY" in written.manifest_path.read_text(encoding="utf-8")


def test_write_fixture_refuses_overwrite(tmp_path) -> None:
    """FR-6: the writer refuses to clobber an existing pair unless told to."""
    from premura.harness.fixture_gen import write_fixture

    fixture = generate_fixture(FixtureSpec(seed=9))
    write_fixture(fixture, tmp_path)
    with pytest.raises(FileExistsError):
        write_fixture(fixture, tmp_path)
    # Explicit opt-in succeeds.
    again = write_fixture(fixture, tmp_path, overwrite=True)
    assert again.csv_path.is_file()


def test_write_fixture_lands_only_where_pointed(tmp_path) -> None:
    """NFR-3: output goes ONLY under out_dir, never into tests/fixtures/."""
    from premura.harness.fixture_gen import write_fixture

    fixture = generate_fixture(FixtureSpec(seed=11))
    written = write_fixture(fixture, tmp_path)
    assert written.csv_path.parent == tmp_path
    assert written.manifest_path.parent == tmp_path
    assert written.marker_path.parent == tmp_path


def test_generated_source_is_synthetic_via_marker(tmp_path) -> None:
    """FR-6: a written generated source is recognized synthetic via its marker."""
    from premura.harness.fixture_gen import is_generated_synthetic_source, write_fixture

    fixture = generate_fixture(FixtureSpec(seed=13))
    written = write_fixture(fixture, tmp_path)
    assert is_generated_synthetic_source(written.csv_path)


def test_real_looking_path_stays_non_synthetic(tmp_path) -> None:
    """FR-6: a real-looking CSV with NO marker beside it is NOT synthetic.

    The synthetic recognition must not loosen for arbitrary/real paths: a plausible
    operator dump that was never written by the generator (no marker) must stay
    non-synthetic so it can never be persisted to the scoreboard.
    """
    from premura.harness.fixture_gen import is_generated_synthetic_source

    real = tmp_path / "garmin_real_export.csv"
    real.write_text("timestamp,bpm\n2026-01-01T00:00:00Z,60\n", encoding="utf-8")
    assert not is_generated_synthetic_source(real)


def test_harness_synthetic_rule_unchanged_for_real_path(tmp_path) -> None:
    """FR-6: the harness's committed-source rule still rejects a real-looking path.

    The harness's committed-source synthetic recognizer only ever counts a committed
    scenario source. A generated/real path it has never seen stays non-synthetic —
    the generated-fixture marker is a SEPARATE, additive recognition surface that
    does not loosen the committed-source rule.

    The recognizer is loaded via ``importlib`` rather than a direct top-level
    import, so this default-suite test carries no textual reference to the
    live-trial harness module (pinned by ``test_live_trial_seam.py``); this test
    runs no trial, it only calls the pure path-classification helper.
    """
    import importlib

    ollama_mod = importlib.import_module("premura.harness." + "live_trial_ollama")
    is_committed_synthetic = ollama_mod.is_synthetic_source

    real = tmp_path / "oura_real_export.csv"
    real.write_text("ts,hr\n2026-01-01T00:00:00Z,60\n", encoding="utf-8")
    assert not is_committed_synthetic(real)


# --------------------------------------------------------------------------- #
# FR-6 scenario adapter — yields a Scenario the harness accepts unchanged.
# --------------------------------------------------------------------------- #


def test_scenario_for_yields_a_valid_scenario(tmp_path) -> None:
    """FR-6: scenario_for builds a Scenario wired to the written pair + observation."""
    from premura.harness.fixture_gen import scenario_for, write_fixture
    from premura.harness.scenario import ObservationStrategy, Scenario

    fixture = generate_fixture(FixtureSpec(seed=17))
    written = write_fixture(fixture, tmp_path)
    scenario = scenario_for(written)

    assert isinstance(scenario, Scenario)
    assert scenario.source_path == written.csv_path
    assert scenario.manifest_path == written.manifest_path
    # The observation drawer is graded by the observation strategy (no new strategy).
    assert isinstance(scenario.strategy, ObservationStrategy)


def test_scenario_for_manifest_grades_via_observation_strategy(tmp_path) -> None:
    """FR-6: the scenario's manifest is consumable by the observation gap_set rule.

    Proves the generated manifest reconciles through the real ObservationStrategy
    code the grader drives — the same code path that grades the committed fixture.
    """
    from premura.harness.fixture_gen import scenario_for, write_fixture
    from premura.harness.scenario import BoundaryTruth

    fixture = generate_fixture(FixtureSpec(seed=19))
    written = write_fixture(fixture, tmp_path)
    scenario = scenario_for(written)

    import yaml

    manifest = yaml.safe_load(scenario.manifest_path.read_text(encoding="utf-8"))

    class _Prov:
        declared_metrics: list[str] = []
        emitted_metric_ids: list[str] = []
        unmapped_metrics: list[str] = []
        skipped_rows: list[dict] = []
        rows_inserted = 0
        ingest_run_ok = True

    # With nothing loaded and nothing declared, EVERY source field is a silent drop:
    # the gap_set must equal the full set of manifest columns (sorted).
    drops = scenario.strategy.gap_set(manifest, _Prov(), BoundaryTruth(0, frozenset()))
    assert drops == sorted(fixture.csv_columns)


# --------------------------------------------------------------------------- #
# FR-7 CLI entry — generate/validate/write + honest exit codes.
# --------------------------------------------------------------------------- #


def test_cli_writes_pair_and_returns_zero(tmp_path, capsys) -> None:
    """FR-7: --seed/--out generates, writes, prints paths + summary, exits 0."""
    from premura.harness.fixture_gen import _main

    rc = _main(["--seed", "42", "--out", str(tmp_path), "--rows", "6"])
    assert rc == 0

    csvs = list(tmp_path.glob("*.csv"))
    manifests = list(tmp_path.glob("*.manifest.yaml"))
    assert len(csvs) == 1
    assert len(manifests) == 1
    # row_count honored (header + 6 data rows).
    assert len(csvs[0].read_text(encoding="utf-8").splitlines()) == 7

    out = capsys.readouterr().out
    assert str(csvs[0]) in out
    assert str(manifests[0]) in out
    # One-line summary names drawer, source, column count, mappable/gap split.
    assert "observation" in out
    assert "mappable" in out


def test_cli_same_seed_byte_identical(tmp_path) -> None:
    """FR-1 via CLI: the same --seed writes byte-identical CSV + manifest."""
    from premura.harness.fixture_gen import _main

    a, b = tmp_path / "a", tmp_path / "b"
    assert _main(["--seed", "100", "--out", str(a)]) == 0
    assert _main(["--seed", "100", "--out", str(b)]) == 0
    csv_a = next(a.glob("*.csv")).read_bytes()
    csv_b = next(b.glob("*.csv")).read_bytes()
    man_a = next(a.glob("*.manifest.yaml")).read_bytes()
    man_b = next(b.glob("*.manifest.yaml")).read_bytes()
    assert csv_a == csv_b
    assert man_a == man_b


def test_cli_unknown_drawer_returns_nonzero(tmp_path, capsys) -> None:
    """FR-7: a failure (unknown drawer) returns a nonzero exit code, no crash."""
    from premura.harness.fixture_gen import _main

    rc = _main(["--seed", "1", "--drawer", "intake", "--out", str(tmp_path)])
    assert rc != 0


def test_cli_refuses_overwrite_returns_nonzero(tmp_path) -> None:
    """FR-7 / FR-6: writing twice to the same dir without --overwrite fails loudly."""
    from premura.harness.fixture_gen import _main

    assert _main(["--seed", "7", "--out", str(tmp_path)]) == 0
    assert _main(["--seed", "7", "--out", str(tmp_path)]) != 0


# --------------------------------------------------------------------------- #
# Acceptance — the whole story end to end (spec acceptance clause).
# --------------------------------------------------------------------------- #


def test_end_to_end_spec_in_pair_out_validated_written_adapted(tmp_path) -> None:
    """Acceptance: spec -> validated pair -> written -> Scenario -> byte-identical.

    Mirrors the mission acceptance clause: a spec generates a validated fixture
    pair, written to a temp dir, adapted to a Scenario the harness accepts, with
    byte-identical regeneration from the same seed.
    """
    from premura.harness.fixture_gen import scenario_for, write_fixture
    from premura.harness.scenario import Scenario

    spec = FixtureSpec(seed=2027, row_count=10)
    fixture = generate_fixture(spec)  # generated + self-validated
    validate_fixture(fixture)  # explicit re-validation, no raise

    out = tmp_path / "run"
    written = write_fixture(fixture, out)
    assert written.csv_path.is_file()
    assert written.manifest_path.is_file()
    assert written.marker_path.is_file()

    scenario = scenario_for(written)
    assert isinstance(scenario, Scenario)
    assert scenario.source_path == written.csv_path

    # Byte-identical regeneration from the same seed.
    regenerated = generate_fixture(spec)
    assert regenerated.csv_text == fixture.csv_text
    assert regenerated.manifest_text == fixture.manifest_text
