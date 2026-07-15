"""WP05 T020 — intake-only vs both drawer targets flow through grading.

The drawer-target scoping edge case: a scenario's *target set* — which drawers a
run is graded on — must be honored by the grader, and ``normalize_parse_output``'s
``(observation, intake)`` separation must flow correctly into the right strategy.

Two cases, each end-to-end (real parser → real loader(s) → generic ``grade()`` with
the per-target strategy injected, no mocked verdict, D7):

* **Intake-only target.** The reference intake parser returns intake-only
  (``observation is None``). Graded on the **intake** drawer, the empty observation
  home is **not** a failure — observation absence is expected and unscored.
* **Both targets.** A variant returns **both** an observation ``IngestBatch`` and an
  ``IntakeBatch`` from one source. Each target drawer is graded with its OWN strategy
  over the SAME generic ``grade()``; both pass. The harness no longer assumes
  observation — intake is graded on intake truth, observation on observation truth.

``normalize_parse_output`` is exercised directly so the separation it produces is
the thing that flows into grading. Offline / deterministic (NFR-001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from premura.harness.grader import grade
from premura.harness.intake_strategy import intake_scenario
from premura.harness.scenario import observation_scenario
from premura.parsers.base import (
    IngestBatch,
    IntakeBatch,
    Measurement,
    NutritionIntakeInput,
    NutritionItemInput,
    NutritionQuantityInput,
    ParseOutput,
    SourceDescriptor,
    normalize_parse_output,
)
from premura.store.loader import load
from premura.store.profile_intake import persist_intake_batch
from tests.fixtures.intake_scenario.reference_intake_parser import AlienIntakeReferenceParser

_INTAKE_SCENARIO = intake_scenario()
_OBS_SCENARIO = observation_scenario()
SOURCE_PATH = _INTAKE_SCENARIO.source_path
INTAKE_MANIFEST_PATH = _INTAKE_SCENARIO.manifest_path
_INTAKE_STRATEGY = _INTAKE_SCENARIO.strategy
_OBS_STRATEGY = _OBS_SCENARIO.strategy

_missing = [p.name for p in (SOURCE_PATH, INTAKE_MANIFEST_PATH) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed intake fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


@dataclass(slots=True)
class _Provenance:
    """Captured ingest evidence (satisfies grader.IngestProvenance + the intake
    runtime seam read via ``produced`` / ``error``)."""

    declared_metrics: list[str] = field(default_factory=list)
    emitted_metric_ids: list[str] = field(default_factory=list)
    unmapped_metrics: list[str] = field(default_factory=list)
    skipped_rows: list[dict[str, Any]] = field(default_factory=list)
    rows_inserted: int = 0
    ingest_run_ok: bool = False
    produced: Any = None
    error: str | None = None


def _intake_manifest() -> dict[str, Any]:
    return yaml.safe_load(Path(INTAKE_MANIFEST_PATH).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Intake-only target: observation absence is NOT a failure.
# --------------------------------------------------------------------------- #
def test_intake_only_target_observation_absence_not_a_failure(empty_warehouse) -> None:
    """Intake-only parser graded on the intake drawer; empty observation is fine.

    ``normalize_parse_output`` yields ``(None, IntakeBatch)``. Graded on the intake
    target, the empty ``hp.fact_*`` observation home is never consulted, so its
    absence is not a failure — the run passes on the intake drawer alone.
    """
    output = AlienIntakeReferenceParser().parse(SOURCE_PATH)
    observation_batch, intake_batch = normalize_parse_output(output)
    assert observation_batch is None  # intake-only: the separation we rely on
    assert isinstance(intake_batch, IntakeBatch)

    stats = persist_intake_batch(empty_warehouse, intake_batch)
    provenance = _Provenance(
        unmapped_metrics=list(intake_batch.unmapped_metrics),
        rows_inserted=stats.nutrition_events_inserted + stats.supplement_events_inserted,
        ingest_run_ok=True,
        produced=intake_batch,
    )
    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=_intake_manifest(),
        strategy=_INTAKE_STRATEGY,
    )

    # Graded on the intake drawer only: passes despite zero observation rows.
    assert verdict["passed"] is True, verdict
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 0


# --------------------------------------------------------------------------- #
# Both targets: each drawer graded on its own strategy through one grade().
# --------------------------------------------------------------------------- #
class BothDrawersParser:
    """A variant emitting BOTH an observation batch and an intake batch.

    Returns a :class:`ParseOutput` carrying one observation ``IngestBatch`` (a real
    ``heart_rate`` measurement) and one ``IntakeBatch`` (one nutrition event) — so
    ``normalize_parse_output`` yields a non-None pair and each target is graded on
    its own drawer truth.
    """

    source_kind = "alien_both"

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> ParseOutput:  # noqa: ARG002 - synthesizes rows
        observation = IngestBatch(source_kind=self.source_kind, declared_metrics=["heart_rate"])
        observation.source_descriptors["both:obs"] = SourceDescriptor(
            source_id="both:obs", source_kind=self.source_kind, app_name="Both (synthetic)"
        )
        observation.measurements.append(
            Measurement(
                ts_utc=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                metric_id="heart_rate",
                unit="bpm",
                source_id="both:obs",
                source_kind=self.source_kind,
                value_num=66.0,
                source_uuid="both-obs-1",
            )
        )

        intake = IntakeBatch()
        intake.source_descriptors["both:intake"] = SourceDescriptor(
            source_id="both:intake", source_kind=self.source_kind, app_name="Both (synthetic)"
        )
        intake.nutrition_events.append(
            NutritionIntakeInput(
                source_id="both:intake",
                source_kind=self.source_kind,
                start_utc=datetime(2024, 1, 15, 8, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                local_tz="America/New_York",
                dedupe_key="both-intake-1",
                items=[
                    NutritionItemInput(
                        item_label="Zorblax Morning Mash",
                        quantities=[
                            NutritionQuantityInput(
                                quantity_key="energy", value_num=180, unit="kcal"
                            )
                        ],
                    )
                ],
            )
        )
        intake.validate()
        return ParseOutput(observation=observation, intake=intake)


def test_both_targets_each_graded_on_its_own_drawer(empty_warehouse) -> None:
    """A both-drawer run grades each target with its own strategy → both pass.

    ``normalize_parse_output`` yields ``(IngestBatch, IntakeBatch)``. We persist each
    via its real loader, then grade EACH target drawer through the SAME generic
    ``grade()`` with the matching strategy injected. The harness no longer assumes
    observation: intake is graded on intake truth, observation on observation truth,
    and the two verdicts are produced by one shared grade path (proven structurally
    in ``test_scenario_no_fork.py``).
    """
    output = BothDrawersParser().parse(SOURCE_PATH)
    observation_batch, intake_batch = normalize_parse_output(output)
    assert isinstance(observation_batch, IngestBatch)
    assert isinstance(intake_batch, IntakeBatch)

    # Real loads into the SAME warehouse, each in its own home.
    observation_batch.attach_source_artifact(SOURCE_PATH)
    obs_stats = load(empty_warehouse, observation_batch)
    intake_stats = persist_intake_batch(empty_warehouse, intake_batch)

    # --- intake target, intake strategy ---
    intake_prov = _Provenance(
        unmapped_metrics=list(intake_batch.unmapped_metrics),
        rows_inserted=intake_stats.nutrition_events_inserted
        + intake_stats.supplement_events_inserted,
        ingest_run_ok=True,
        produced=intake_batch,
    )
    # An intake manifest scoped to this variant's single loaded home (no homeless
    # column to declare) so honesty is judged on what this run actually carries.
    intake_manifest = {
        "source": "alien_both",
        "columns": [
            {"source_column": "logged_at_us", "canonical_home": "event_timestamp"},
            {"source_column": "item", "canonical_home": "item_label"},
            {"source_column": "qty", "canonical_home": "quantity_value"},
        ],
    }
    intake_verdict = grade(
        provenance=intake_prov,
        warehouse_conn=empty_warehouse,
        fixture_manifest=intake_manifest,
        strategy=_INTAKE_STRATEGY,
    )

    # --- observation target, observation strategy ---
    obs_prov = _Provenance(
        declared_metrics=["heart_rate"],
        emitted_metric_ids=["heart_rate"],
        rows_inserted=obs_stats.rows_inserted,
        ingest_run_ok=True,
    )
    obs_manifest = {
        "source": "alien_both",
        "source_fields": [{"name": "bpm", "canonical_metric": "heart_rate"}],
    }
    obs_verdict = grade(
        provenance=obs_prov,
        warehouse_conn=empty_warehouse,
        fixture_manifest=obs_manifest,
        strategy=_OBS_STRATEGY,
    )

    # Each target graded on its own drawer truth; both pass through one grade().
    assert intake_verdict["passed"] is True, intake_verdict
    assert intake_verdict["rules"]["loaded"]["warehouse_rows"] == 1
    assert obs_verdict["passed"] is True, obs_verdict
    assert obs_verdict["rules"]["loaded"]["warehouse_rows"] == 1


def test_normalize_separation_routes_each_batch_to_its_target() -> None:
    """``normalize_parse_output`` produces the separation that flows into grading.

    The unit witness under the e2e: a both-drawer ``ParseOutput`` separates into a
    non-None observation batch and a non-None intake batch, so the e2e above can
    route each to its own strategy. The intake-only case separates to
    ``(None, IntakeBatch)``. This is the routing fact the drawer-target scoping
    depends on.
    """
    obs, intake = normalize_parse_output(BothDrawersParser().parse(SOURCE_PATH))
    assert isinstance(obs, IngestBatch)
    assert isinstance(intake, IntakeBatch)

    obs2, intake2 = normalize_parse_output(AlienIntakeReferenceParser().parse(SOURCE_PATH))
    assert obs2 is None
    assert isinstance(intake2, IntakeBatch)
