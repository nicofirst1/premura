"""WP04 — Layer-1 happy-path intake grading e2e (SC-001 / FR-003..006).

Proves the first user-visible intake value: the **reference intake parser** over
the synthetic *alien* source scores a clean three-rule pass when driven through
the **generic** :func:`premura.harness.grader.grade` with the intake
:class:`~premura.harness.intake_strategy.IntakeStrategy` injected — the SAME grader
the observation scenario flows through, with NO intake-specific branch (NFR-005).

Stance (mirrors ``test_observation_scenario_golden.py`` / ``test_grader.py``): no
mocks of the grade path. We run the real reference parser → real
``persist_intake_batch`` into a real warehouse → capture provenance → grade. The
warehouse holds genuine boundary truth; the verdict is recomputed, never trusted.

Offline / deterministic — no network, no model server (NFR-001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from premura.harness.grader import grade
from premura.harness.intake_strategy import intake_scenario
from premura.harness.scenario_registry import all_scenarios
from premura.parsers.base import IntakeBatch, normalize_parse_output
from premura.store.profile_intake import persist_intake_batch

_SCENARIO = intake_scenario()
SOURCE_PATH = _SCENARIO.source_path
MANIFEST_PATH = _SCENARIO.manifest_path

# Committed fixtures ship with the mission; their absence is a HARD failure, never
# a skip (same posture as the observation golden).
_missing = [p.name for p in (SOURCE_PATH, MANIFEST_PATH) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed intake fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )

# Import the reference parser the way the harness installs it (committed fixture).
from tests.fixtures.intake_scenario.reference_intake_parser import (  # noqa: E402
    AlienIntakeReferenceParser,
)


@dataclass(slots=True)
class _IntakeProvenance:
    """Captured intake ingest evidence (satisfies grader.IngestProvenance + the
    intake runtime seam the strategy reads via ``produced`` / ``error``).

    Every field is captured measured evidence or a parser claim — never a
    precomputed rule verdict. ``produced`` carries the parser's batch and ``error``
    the stage-tagged failure detail; both are what WP02's checker re-derives over.
    """

    # IngestProvenance Protocol surface (observation-shaped; intake leaves the
    # metric fields empty since there is no canonical metric surface on intake).
    declared_metrics: list[str] = field(default_factory=list)
    emitted_metric_ids: list[str] = field(default_factory=list)
    unmapped_metrics: list[str] = field(default_factory=list)
    skipped_rows: list[dict[str, Any]] = field(default_factory=list)
    rows_inserted: int = 0
    ingest_run_ok: bool = False
    # Intake runtime-check seam read by IntakeStrategy.runtime_check.
    produced: Any = None
    error: str | None = None


def _run_reference_intake_and_capture(conn: Any) -> _IntakeProvenance:
    """Drive the reference parser → persist into ``conn`` → capture provenance.

    The real parse → normalize → persist seam (no mocks), so the warehouse holds
    genuine intake boundary truth before grading.
    """
    output = AlienIntakeReferenceParser().parse(SOURCE_PATH)
    observation_batch, intake_batch = normalize_parse_output(output)
    assert observation_batch is None, "reference intake parser must be intake-only"
    assert isinstance(intake_batch, IntakeBatch)

    persist_error: str | None = None
    persisted_ok = True
    try:
        stats = persist_intake_batch(conn, intake_batch)
        rows_inserted = stats.nutrition_events_inserted + stats.supplement_events_inserted
    except Exception as exc:  # pragma: no cover - happy path persists cleanly
        persisted_ok = False
        rows_inserted = 0
        persist_error = f"persist: {exc}"

    return _IntakeProvenance(
        unmapped_metrics=list(intake_batch.unmapped_metrics),
        skipped_rows=[
            {"raw_field": r.raw_field, "reason": r.reason} for r in intake_batch.skipped_rows
        ],
        rows_inserted=rows_inserted,
        ingest_run_ok=persisted_ok,
        produced=intake_batch,
        error=persist_error,
    )


def _grade_intake(conn: Any) -> dict[str, Any]:
    provenance = _run_reference_intake_and_capture(conn)
    manifest = yaml.safe_load(Path(MANIFEST_PATH).read_text(encoding="utf-8"))
    return grade(
        provenance=provenance,
        warehouse_conn=conn,
        fixture_manifest=manifest,
        strategy=_SCENARIO.strategy,
    )


# --------------------------------------------------------------------------- #
# T016 — the layer-1 happy-path full three-rule pass (SC-001).
# --------------------------------------------------------------------------- #
def test_intake_reference_parser_full_three_rule_pass(empty_warehouse) -> None:
    """Reference intake parser over the alien source → clean three-rule PASS (SC-001).

    All three rules green, driven through the GENERIC grade() with the intake
    strategy injected: loaded (intake rows present + consistent with the loader
    count), runtime_valid (intake clauses), honest_about_gaps (the `note` gap is
    DECLARED, not a silent drop).
    """
    verdict = _grade_intake(empty_warehouse)

    assert verdict["passed"] is True, verdict
    rules = verdict["rules"]
    assert rules["loaded"]["passed"] is True, rules["loaded"]
    assert rules["runtime_valid"]["passed"] is True, rules["runtime_valid"]
    assert rules["runtime_valid"]["violations"] == []
    assert rules["honest_about_gaps"]["passed"] is True, rules["honest_about_gaps"]


def test_loaded_reads_intake_warehouse_not_fact_tables(empty_warehouse) -> None:
    """`loaded` counts intake-event rows; nothing landed in the observation home."""
    verdict = _grade_intake(empty_warehouse)
    # 4 meals + 2 supplements in the alien source = 6 intake events.
    assert verdict["rules"]["loaded"]["warehouse_rows"] == 6
    assert verdict["rules"]["loaded"]["logged_rows_inserted"] == 6
    # Intake never coerced into the observation drawer (two-seam / one-home rule).
    assert empty_warehouse.execute("SELECT COUNT(*) FROM hp.fact_measurement").fetchone()[0] == 0


def test_note_column_accounted_as_declared_gap_not_silent_drop(empty_warehouse) -> None:
    """The `note` column (canonical_home: null) is DECLARED → not a silent drop (SC-004).

    The happy-path honesty proof: the one column with no canonical home is honestly
    surfaced via `unmapped_metrics`, so it is accounted (declared) and the gap set
    is empty.
    """
    verdict = _grade_intake(empty_warehouse)
    assert verdict["rules"]["honest_about_gaps"]["silent_drops"] == []
    # And it really is the declared route, not a hidden warehouse witness: `note`
    # has no canonical home, so only a declaration can account for it.
    provenance = _run_reference_intake_and_capture(empty_warehouse)  # idempotent re-run
    assert "note" in provenance.unmapped_metrics


# --------------------------------------------------------------------------- #
# Registry surface — both scenarios reachable (SC-003).
# --------------------------------------------------------------------------- #
def test_registry_lists_both_scenarios() -> None:
    """`all_scenarios()` returns ≥ 2 scenarios including observation + intake."""
    scenarios = all_scenarios()
    names = {s.name for s in scenarios}
    assert len(scenarios) >= 2
    assert {"observation", "intake_alien"} <= names


def test_intake_scenario_flows_through_generic_grade_via_registry(empty_warehouse) -> None:
    """The intake scenario picked FROM the registry grades to a full pass.

    Proves the live-harness path (iterate scenarios → grade each with its injected
    strategy) reaches the intake scenario with no per-source branch: we select it
    from `all_scenarios()` by name and drive the same generic grade().
    """
    intake = next(s for s in all_scenarios() if s.name == "intake_alien")
    provenance = _run_reference_intake_and_capture(empty_warehouse)
    manifest = yaml.safe_load(Path(intake.manifest_path).read_text(encoding="utf-8"))
    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=manifest,
        strategy=intake.strategy,
    )
    assert verdict["passed"] is True, verdict
