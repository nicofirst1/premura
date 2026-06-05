"""WP05 T017 / T018 — intake drawer-truth + silent-drop edge cases, end-to-end.

Two spec-named intake failure modes, each proven through the **real**
parse → load → grade pipeline (no mocked verdict, D7):

* **T017 — mis-filed intake row (SC-002 / FR-006).** A parser variant writes a
  nutrition row into the **observation** ``hp.fact_*`` tables instead of the intake
  drawer. Graded with the intake strategy, the intake warehouse is empty, so
  boundary truth witnesses no loaded intake row → ``loaded`` is **false** and the
  overall verdict fails. Cross-drawer coercion is never scored as success: a row in
  the wrong home cannot witness an intake field.
* **T018 — unmappable field, declared vs silently dropped (SC-004 / FR-005).**
  Variant A declares the homeless ``note`` column as a gap → ``honest_about_gaps``
  passes (the happy honesty path). Variant B loads the same intake rows but **drops
  ``note`` silently** (never declares it) → the manifest reconcile detects the
  silent drop → ``honest_about_gaps`` is **false**. The contrast is the whole point:
  a declared gap is honest; a silent drop is not.

Stance mirrors ``test_intake_scenario_grading.py`` / the observation golden: real
reference/variant parsers, real loaders, a real warehouse, the GENERIC ``grade()``
with the injected strategy. Offline / deterministic (NFR-001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from premura.harness.grader import grade
from premura.harness.intake_strategy import intake_scenario
from premura.parsers.base import (
    IngestBatch,
    IntakeBatch,
    Measurement,
    SourceDescriptor,
    normalize_parse_output,
)
from premura.store.loader import load
from premura.store.profile_intake import persist_intake_batch

# Reuse the WP03 reference parser surface — variants are authored here, never by
# editing the committed fixtures (WP05 ownership).
from tests.fixtures.intake_scenario.reference_intake_parser import (
    AlienIntakeReferenceParser,
)

_SCENARIO = intake_scenario()
SOURCE_PATH = _SCENARIO.source_path
MANIFEST_PATH = _SCENARIO.manifest_path
_INTAKE_STRATEGY = _SCENARIO.strategy

_missing = [p.name for p in (SOURCE_PATH, MANIFEST_PATH) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed intake fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


@dataclass(slots=True)
class _IntakeProvenance:
    """Captured intake ingest evidence (satisfies grader.IngestProvenance + the
    intake runtime seam the strategy reads via ``produced`` / ``error``)."""

    declared_metrics: list[str] = field(default_factory=list)
    emitted_metric_ids: list[str] = field(default_factory=list)
    unmapped_metrics: list[str] = field(default_factory=list)
    skipped_rows: list[dict[str, Any]] = field(default_factory=list)
    rows_inserted: int = 0
    ingest_run_ok: bool = False
    produced: Any = None
    error: str | None = None


def _load_manifest() -> dict[str, Any]:
    return yaml.safe_load(Path(MANIFEST_PATH).read_text(encoding="utf-8"))


def _capture_intake(batch: IntakeBatch, conn: Any) -> _IntakeProvenance:
    """Persist a produced intake batch into ``conn`` and capture provenance.

    The real intake load seam (no mock) so the warehouse holds genuine intake
    boundary truth before grading.
    """
    persist_error: str | None = None
    persisted_ok = True
    try:
        stats = persist_intake_batch(conn, batch)
        rows_inserted = stats.nutrition_events_inserted + stats.supplement_events_inserted
    except Exception as exc:  # pragma: no cover - variants persist cleanly
        persisted_ok = False
        rows_inserted = 0
        persist_error = f"persist: {exc}"

    return _IntakeProvenance(
        unmapped_metrics=list(batch.unmapped_metrics),
        skipped_rows=[{"raw_field": r.raw_field, "reason": r.reason} for r in batch.skipped_rows],
        rows_inserted=rows_inserted,
        ingest_run_ok=persisted_ok,
        produced=batch,
        error=persist_error,
    )


# --------------------------------------------------------------------------- #
# T017 — mis-filed intake row: a nutrition row written into the OBSERVATION
# drawer cannot witness `loaded` for the intake scenario (SC-002 / FR-006).
# --------------------------------------------------------------------------- #
class MisfiledIntakeAsObservationParser:
    """A broken variant that mis-files an intake row into the OBSERVATION drawer.

    Instead of producing an ``IntakeBatch``, it folds the nutrition occurrence into
    an observation :class:`Measurement` (``hp.fact_measurement``) — the exact
    cross-drawer coercion FR-006 forbids. Graded on the intake scenario, the intake
    warehouse stays empty, so this row can never witness a loaded intake field.
    """

    source_kind = "alien_intake_misfiled"

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:  # noqa: ARG002 - synthesizes one row
        batch = IngestBatch(
            source_kind=self.source_kind,
            declared_metrics=["heart_rate"],
        )
        batch.source_descriptors["misfiled:journal"] = SourceDescriptor(
            source_id="misfiled:journal",
            source_kind=self.source_kind,
            app_name="Misfiled Intake (synthetic)",
        )
        # A nutrition/supplement occurrence forced into an observation measurement
        # row — the wrong-drawer coercion. Uses a seeded metric so it actually
        # lands in hp.fact_measurement.
        batch.measurements.append(
            Measurement(
                ts_utc=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                metric_id="heart_rate",
                unit="bpm",
                source_id="misfiled:journal",
                source_kind=self.source_kind,
                value_num=72.0,
                source_uuid="misfiled-row-1",
            )
        )
        return batch


def test_misfiled_intake_row_fails_loaded(empty_warehouse) -> None:
    """A nutrition row landed in the observation drawer → intake ``loaded`` FAILS (SC-002).

    Real pipeline: the variant emits an observation ``IngestBatch``, the REAL
    observation loader persists it into ``hp.fact_measurement``, then we grade with
    the INTAKE strategy. Intake boundary truth reads only the intake event tables,
    which are empty, so ``loaded`` is false and the verdict fails — cross-drawer
    coercion is never scored as success (FR-006).
    """
    misfiled = MisfiledIntakeAsObservationParser().parse(SOURCE_PATH)
    misfiled.attach_source_artifact(SOURCE_PATH)
    stats = load(empty_warehouse, misfiled)
    assert stats.rows_inserted == 1  # the row really landed — in the WRONG drawer

    # Sanity: it landed in the observation home, not the intake home.
    obs_rows = empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0]
    assert obs_rows == 1
    intake_rows = empty_warehouse.execute(
        "SELECT COUNT(*) FROM hp.nutrition_intake_event"
    ).fetchone()[0]
    assert intake_rows == 0

    provenance = _IntakeProvenance(
        rows_inserted=stats.rows_inserted,  # the loader DID insert a row...
        ingest_run_ok=True,
        produced=IntakeBatch(),  # ...but no intake batch was produced
    )
    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=_load_manifest(),
        strategy=_INTAKE_STRATEGY,
    )

    # Boundary truth (intake warehouse) saw zero rows → loaded is false even though
    # a row WAS inserted somewhere; the grader trusts the drawer's warehouse, not
    # the rows_inserted self-report.
    assert verdict["rules"]["loaded"]["passed"] is False, verdict["rules"]["loaded"]
    assert verdict["rules"]["loaded"]["warehouse_rows"] == 0
    assert verdict["passed"] is False, verdict


# --------------------------------------------------------------------------- #
# T018 — unmappable `note` field: DECLARED (honest) vs SILENTLY DROPPED.
# --------------------------------------------------------------------------- #
class SilentDropNoteIntakeParser(AlienIntakeReferenceParser):
    """A variant that loads the intake rows but SILENTLY DROPS the ``note`` column.

    Identical to the honest reference parser except it never declares ``note`` as a
    gap (``unmapped_metrics`` stays empty). ``note`` has no canonical home, so with
    no declaration the manifest reconcile cannot account for it → it is a silent
    drop and ``honest_about_gaps`` fails (FR-005).
    """

    source_kind = "alien_intake_silentdrop"

    def parse(self, path: Path):  # type: ignore[override]
        output = super().parse(path)
        assert output.intake is not None
        # The single mutation that makes the variant DISHONEST: erase the declared
        # gap so `note` is neither loaded (no canonical home) nor declared.
        output.intake.unmapped_metrics = []
        return output


def test_unmappable_note_declared_is_honest(empty_warehouse) -> None:
    """Variant A — the reference parser DECLARES the ``note`` gap → honest passes (SC-004).

    The honest contrast for T018: ``note`` has no canonical home, but it is surfaced
    via ``unmapped_metrics``, so the manifest reconcile accounts for it (declared)
    and ``honest_about_gaps`` passes through the real grade path.
    """
    output = AlienIntakeReferenceParser().parse(SOURCE_PATH)
    _, intake_batch = normalize_parse_output(output)
    assert intake_batch is not None
    assert "note" in intake_batch.unmapped_metrics  # really declared, not loaded

    provenance = _capture_intake(intake_batch, empty_warehouse)
    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=_load_manifest(),
        strategy=_INTAKE_STRATEGY,
    )
    assert verdict["rules"]["honest_about_gaps"]["passed"] is True, verdict["rules"]
    assert verdict["rules"]["honest_about_gaps"]["silent_drops"] == []


def test_silently_dropped_note_fails_honest(empty_warehouse) -> None:
    """Variant B — the same rows but ``note`` SILENTLY DROPPED → honesty FAILS (SC-004).

    Real pipeline: the variant loads the intake events honestly (so ``loaded`` would
    pass) but never declares ``note``. ``note`` has no canonical home, so it is
    neither witnessed in the warehouse nor declared → the manifest reconcile flags it
    as a silent drop and ``honest_about_gaps`` is false. This is the failure the
    happy-path declared-gap case (variant A) is contrasted against (FR-005).
    """
    output = SilentDropNoteIntakeParser().parse(SOURCE_PATH)
    _, intake_batch = normalize_parse_output(output)
    assert intake_batch is not None
    assert intake_batch.unmapped_metrics == []  # the silent drop: nothing declared

    provenance = _capture_intake(intake_batch, empty_warehouse)
    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=_load_manifest(),
        strategy=_INTAKE_STRATEGY,
    )

    # The rows DID load (so this is not a load failure) — the only failing rule is
    # honesty, proving the silent drop is caught by manifest reconcile, not luck.
    assert verdict["rules"]["loaded"]["passed"] is True, verdict["rules"]["loaded"]
    assert verdict["rules"]["honest_about_gaps"]["passed"] is False, verdict["rules"]
    assert "note" in verdict["rules"]["honest_about_gaps"]["silent_drops"]
    assert verdict["passed"] is False, verdict
