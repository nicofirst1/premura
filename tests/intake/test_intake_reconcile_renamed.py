"""WP05 T019 — renamed-but-consumed intake column is accounted (two controls).

The spec edge case "renamed-but-consumed field": the reference intake parser
consumes ``logged_at_us`` under a **different internal name** (it decodes the epoch
microseconds into the event timestamp / ``event_timestamp`` home) and records it in
``MAPPED_SOURCE_COLUMNS``. A column the parser maps under another name must still
count as accounted, never a gap.

Two **distinct** controls guard this, asserted **independently** (not blended):

* **Control A — ``self_reconcile`` (manifest-blind, FR-003 / C-005).** It counts a
  column accounted iff it is in the parser's ``MAPPED_SOURCE_COLUMNS`` **or**
  declared as a gap. ``logged_at_us`` is in ``MAPPED_SOURCE_COLUMNS``, so it must be
  in ``accounted`` and **not** in ``unaccounted`` — even though its internal name
  changed.
* **Control B — grader ``honest_about_gaps`` (manifest-derived, FR-005).** A
  different oracle: manifest truth vs (loaded ∪ declared). ``logged_at_us`` maps to
  the ``event_timestamp`` home, which is witnessed in the intake warehouse after a
  real load, so the grader must **not** flag it as a silent drop and the rule passes.

Both controls run end-to-end against the real reference parser + real intake load
(no mocked verdict, D7). Offline / deterministic (NFR-001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from premura.harness.grader import grade
from premura.harness.intake_strategy import intake_scenario
from premura.harness.self_reconcile import self_reconcile
from premura.parsers.base import IntakeBatch, normalize_parse_output
from premura.store.profile_intake import persist_intake_batch
from tests.fixtures.intake_scenario.reference_intake_parser import (
    MAPPED_SOURCE_COLUMNS,
    AlienIntakeReferenceParser,
)

_SCENARIO = intake_scenario()
SOURCE_PATH = _SCENARIO.source_path
MANIFEST_PATH = _SCENARIO.manifest_path
_INTAKE_STRATEGY = _SCENARIO.strategy

# The column the parser consumes under a different internal name (decoded into the
# event timestamp), mapped to the `event_timestamp` home.
RENAMED_COLUMN = "logged_at_us"

_missing = [p.name for p in (SOURCE_PATH, MANIFEST_PATH) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed intake fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


@dataclass(slots=True)
class _IntakeProvenance:
    """Captured intake ingest evidence (satisfies grader.IngestProvenance + the
    intake runtime seam read via ``produced`` / ``error``)."""

    declared_metrics: list[str] = field(default_factory=list)
    emitted_metric_ids: list[str] = field(default_factory=list)
    unmapped_metrics: list[str] = field(default_factory=list)
    skipped_rows: list[dict[str, Any]] = field(default_factory=list)
    rows_inserted: int = 0
    ingest_run_ok: bool = False
    produced: Any = None
    error: str | None = None


def _run_and_capture(conn: Any) -> tuple[IntakeBatch, _IntakeProvenance]:
    """Drive the real reference parser → real intake load → capture provenance."""
    output = AlienIntakeReferenceParser().parse(SOURCE_PATH)
    _, intake_batch = normalize_parse_output(output)
    assert isinstance(intake_batch, IntakeBatch)

    persist_error: str | None = None
    persisted_ok = True
    try:
        stats = persist_intake_batch(conn, intake_batch)
        rows_inserted = stats.nutrition_events_inserted + stats.supplement_events_inserted
    except Exception as exc:  # pragma: no cover - reference parser persists cleanly
        persisted_ok = False
        rows_inserted = 0
        persist_error = f"persist: {exc}"

    provenance = _IntakeProvenance(
        unmapped_metrics=list(intake_batch.unmapped_metrics),
        skipped_rows=[
            {"raw_field": r.raw_field, "reason": r.reason} for r in intake_batch.skipped_rows
        ],
        rows_inserted=rows_inserted,
        ingest_run_ok=persisted_ok,
        produced=intake_batch,
        error=persist_error,
    )
    return intake_batch, provenance


# --------------------------------------------------------------------------- #
# Control A — self_reconcile: the renamed-but-consumed column is accounted
# because it is in MAPPED_SOURCE_COLUMNS, never unaccounted (FR-003 / C-005).
# --------------------------------------------------------------------------- #
def test_renamed_column_accounted_by_self_reconcile(empty_warehouse) -> None:
    """``logged_at_us`` is ``accounted`` and NOT ``unaccounted`` (manifest-blind).

    The manifest-blind control: ``self_reconcile`` reads the source header and the
    parser's ``MAPPED_SOURCE_COLUMNS`` + declared gaps. ``logged_at_us`` is consumed
    under a different internal name but listed in ``MAPPED_SOURCE_COLUMNS``, so it is
    accounted — proving a renamed-but-consumed column is not mistaken for a drop.
    """
    intake_batch, _ = _run_and_capture(empty_warehouse)

    recon = self_reconcile(SOURCE_PATH, intake_batch, MAPPED_SOURCE_COLUMNS)

    assert RENAMED_COLUMN in recon.accounted, recon
    assert RENAMED_COLUMN not in recon.unaccounted, recon
    # The whole source reconciles honestly: every header column is mapped or declared.
    assert recon.passed is True, recon
    assert recon.unaccounted == [], recon


# --------------------------------------------------------------------------- #
# Control B — grader honest_about_gaps: the renamed-but-consumed column is NOT a
# silent drop because its canonical home is witnessed in the warehouse (FR-005).
# --------------------------------------------------------------------------- #
def test_renamed_column_not_silent_drop_in_grader(empty_warehouse) -> None:
    """The grader does NOT flag ``logged_at_us`` as a silent drop; the rule passes.

    A DIFFERENT oracle from control A: the grader reconciles the manifest against
    (loaded ∪ declared). ``logged_at_us`` maps to the ``event_timestamp`` home,
    which the real intake load witnesses in the warehouse, so the manifest-derived
    truth accounts for it as loaded. ``honest_about_gaps`` passes and the column is
    absent from ``silent_drops``.
    """
    _, provenance = _run_and_capture(empty_warehouse)
    manifest = yaml.safe_load(Path(MANIFEST_PATH).read_text(encoding="utf-8"))

    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=manifest,
        strategy=_INTAKE_STRATEGY,
    )

    honest = verdict["rules"]["honest_about_gaps"]
    assert RENAMED_COLUMN not in honest["silent_drops"], honest
    assert honest["passed"] is True, honest
    # And the witness really is the warehouse, not a declaration: logged_at_us is
    # NOT in the declared gaps, so only a loaded witness can account for it.
    assert RENAMED_COLUMN not in provenance.unmapped_metrics


def test_two_controls_are_independent_oracles(empty_warehouse) -> None:
    """Both controls pass for the SAME run, asserted separately (review fix).

    A guard that the two checks are genuinely independent: ``self_reconcile`` is
    manifest-blind (reads ``MAPPED_SOURCE_COLUMNS``), the grader is manifest-derived
    (reads warehouse witness). The renamed-but-consumed column must satisfy each on
    its own terms, not a blended "one of them passed".
    """
    intake_batch, provenance = _run_and_capture(empty_warehouse)
    manifest = yaml.safe_load(Path(MANIFEST_PATH).read_text(encoding="utf-8"))

    recon = self_reconcile(SOURCE_PATH, intake_batch, MAPPED_SOURCE_COLUMNS)
    verdict = grade(
        provenance=provenance,
        warehouse_conn=empty_warehouse,
        fixture_manifest=manifest,
        strategy=_INTAKE_STRATEGY,
    )

    # Control A — manifest-blind mapping witness.
    assert RENAMED_COLUMN in recon.accounted
    # Control B — manifest-derived warehouse witness.
    assert RENAMED_COLUMN not in verdict["rules"]["honest_about_gaps"]["silent_drops"]
    assert verdict["rules"]["honest_about_gaps"]["passed"] is True
