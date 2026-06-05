"""The intake drawer's :class:`DrawerGradingStrategy` + its scenario (FR-003..006).

The intake analogue of :class:`premura.harness.scenario.ObservationStrategy`: it
supplies the three drawer-specific facts the generic
:func:`premura.harness.grader.grade` body calls into, so the *same* grader scores
an intake run with **no per-drawer branch** (NFR-005). Adding the intake source is
registering one :class:`~premura.harness.scenario.Scenario`; the shared grade path
is never edited.

The three responsibilities, intake-shaped:

* ``boundary_truth(conn)`` — loaded row count + present drawer keys recomputed from
  the **intake** warehouse tables only (``hp.nutrition_intake_*`` /
  ``hp.supplement_intake_*``), never from the parser's report (FR-006). A
  nutrition/supplement row that landed in ``hp.fact_*`` is, by construction, absent
  here and so cannot witness a loaded field — that is the failing-case property
  (the proof is WP05).
* ``runtime_check(provenance, conn)`` — delegates to WP02's
  :func:`premura.harness.intake_contract_check.check_intake_runtime_contract` over
  the captured produce/persist evidence; intake has no canonical declared/emitted
  *metric* surface, so the truthful coherence is on the source dimension via
  ``IntakeBatch.validate()`` (re-run by the checker).
* ``gap_set(manifest, provenance, boundary_truth)`` — the manifest-derived silent
  drops: a source column accounted iff it is **loaded** (witnessed by warehouse
  boundary truth) OR **declared** by the parser (``unmapped_metrics`` /
  ``skipped_rows``). A column that is neither is a silent drop and fails
  ``honest_about_gaps`` (FR-005). Declared metadata is evidence to verify, never
  proof.

This module is import-light (no Ollama, no network) so it is safe to import from
the registry and the grader path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from premura.config import REPO_ROOT
from premura.harness.intake_contract_check import check_intake_runtime_contract
from premura.harness.scenario import (
    BoundaryTruth,
    IngestProvenance,
    Scenario,
    _declared_field_names,
)

if TYPE_CHECKING:
    import duckdb

    from premura.parsers.contract_check import ContractCheckResult


# The intake event tables that hold boundary truth for the ``loaded`` rule. Only
# the intake drawer's own homes (migration 004) — a row in ``hp.fact_*`` is
# deliberately NOT counted here, so an intake field "loaded" into the wrong drawer
# cannot witness a loaded column (FR-006 / NFR-006).
_INTAKE_EVENT_TABLES: tuple[str, ...] = (
    "hp.nutrition_intake_event",
    "hp.supplement_intake_event",
)

# Maps a manifest ``canonical_home`` to the SQL that witnesses it in the intake
# warehouse. Each value is a COUNT-returning query whose positive result means the
# home concept actually landed. This is a bounded *rubric* (a home → witness rule),
# not an enumeration of source columns: a new intake home is added by registering a
# witness here, and the manifest reconciliation reads it generically.
_INTAKE_HOME_WITNESS_SQL: dict[str, str] = {
    # Event-level homes are witnessed by ANY persisted intake event.
    "event_timestamp": (
        "SELECT (SELECT COUNT(*) FROM hp.nutrition_intake_event)"
        " + (SELECT COUNT(*) FROM hp.supplement_intake_event)"
    ),
    "event_kind": (
        "SELECT (SELECT COUNT(*) FROM hp.nutrition_intake_event)"
        " + (SELECT COUNT(*) FROM hp.supplement_intake_event)"
    ),
    # An item label is witnessed by a persisted nutrition item or supplement item.
    "item_label": (
        "SELECT (SELECT COUNT(*) FROM hp.nutrition_intake_item)"
        " + (SELECT COUNT(*) FROM hp.supplement_item)"
    ),
    # A quantity value/unit is witnessed by a persisted nutrition quantity or
    # supplement dose row.
    "quantity_value": (
        "SELECT (SELECT COUNT(*) FROM hp.nutrition_quantity)"
        " + (SELECT COUNT(*) FROM hp.supplement_dose)"
    ),
    "quantity_unit": (
        "SELECT (SELECT COUNT(*) FROM hp.nutrition_quantity)"
        " + (SELECT COUNT(*) FROM hp.supplement_dose)"
    ),
}

# Committed synthetic alien source + its grader-only ground-truth manifest (C-005).
_INTAKE_FIXTURE_DIR = Path(REPO_ROOT) / "tests" / "fixtures" / "intake_scenario"
_INTAKE_SOURCE = _INTAKE_FIXTURE_DIR / "alien_intake.csv"
_INTAKE_MANIFEST = _INTAKE_FIXTURE_DIR / "alien_intake_manifest.yaml"
# The layer-1 known-good intake reference parser (import target). The alien source
# is a deliberately unsupported live-trial target, so the reference parser is the
# committed honest fixture, not a shipped parser.
_INTAKE_REFERENCE_PARSER = (
    "tests.fixtures.intake_scenario.reference_intake_parser:AlienIntakeReferenceParser"
)


@dataclass(frozen=True)
class IntakeStrategy:
    """The intake drawer's grading, satisfying the ``DrawerGradingStrategy`` Protocol.

    Wraps intake-table boundary truth (T012), the WP02 intake runtime checker
    (delegated), and the intake manifest honesty reconcile (T013). The shared
    ``grade()`` body names none of these — they are reached only through the
    Protocol seam, which is how the intake scenario flows through the unchanged
    generic grader (NFR-005).
    """

    event_tables: tuple[str, ...] = _INTAKE_EVENT_TABLES

    # --- T012: intake boundary-truth reader ------------------------------- #
    def boundary_truth(self, warehouse_conn: duckdb.DuckDBPyConnection) -> BoundaryTruth:
        """Persisted intake-event row count + present home keys (FR-006).

        ``row_count`` counts persisted intake **events** (the ``loaded`` support,
        consistent with the loader-measured event inserts). ``present_keys`` is the
        set of manifest ``canonical_home`` concepts actually witnessed in the intake
        warehouse — the honesty witness set. Both are recomputed from the warehouse,
        never from the parser's report: an intake row that landed in ``hp.fact_*``
        is absent from every query here.
        """
        total = 0
        for table in self.event_tables:
            count_row = warehouse_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
            total += int(count_row[0]) if count_row else 0

        present: set[str] = set()
        for home, sql in _INTAKE_HOME_WITNESS_SQL.items():
            witness_row = warehouse_conn.execute(sql).fetchone()
            if witness_row and int(witness_row[0]) > 0:
                present.add(home)

        return BoundaryTruth(row_count=total, present_keys=frozenset(present))

    # --- T014 wiring: delegate runtime check to WP02 ---------------------- #
    def runtime_check(
        self,
        provenance: IngestProvenance,
        warehouse_conn: duckdb.DuckDBPyConnection,
    ) -> ContractCheckResult:
        """Delegate to WP02's intake checker over the CAPTURED produce/persist evidence.

        Intake ``runtime_valid`` has no canonical declared/emitted *metric* surface
        (those are observation-only); the truthful coherence is on the source
        dimension, which the checker re-derives by re-running
        ``IntakeBatch.validate()``. The captured produced batch + persist outcome
        ride on the provenance, transported by the harness (never a stored verdict).
        """
        produced = getattr(provenance, "produced", None)
        persisted_ok = bool(getattr(provenance, "ingest_run_ok", False))
        persist_error = getattr(provenance, "error", None)
        return check_intake_runtime_contract(
            produced=produced,
            persisted_ok=persisted_ok,
            persist_error=persist_error,
        )

    # --- T013: intake gap reconciler -------------------------------------- #
    def gap_set(
        self,
        fixture_manifest: dict[str, Any],
        provenance: IngestProvenance,
        boundary_truth: BoundaryTruth,
    ) -> list[str]:
        """Sorted silent-drop columns: manifest vs (loaded ∪ declared).

        Truth is the manifest: for every source column it derives whether the
        column is accounted. A column is accounted iff its ``canonical_home`` is
        **present in the intake warehouse** (boundary truth) OR the column name is
        **declared** by the parser (``unmapped_metrics`` / ``skipped_rows``). A
        column that is neither is a silent drop — present in the returned set, which
        fails ``honest_about_gaps``.

        Declared metadata is evidence on the *declared* side only; it never
        witnesses that a column was actually loaded (FR-005). A column with no
        canonical home (``canonical_home: null``, the intended gap) can only be
        accounted by being declared, so a parser that drops it silently fails here.
        """
        homes_present = boundary_truth.present_keys
        declared_fields = _declared_field_names(provenance)

        silent_drops: list[str] = []
        for column in fixture_manifest["columns"]:
            name = column["source_column"]
            canonical_home = column.get("canonical_home")
            loaded = canonical_home is not None and canonical_home in homes_present
            declared = name in declared_fields
            if not (loaded or declared):
                silent_drops.append(name)

        silent_drops.sort()
        return silent_drops


def intake_scenario() -> Scenario:
    """The intake :class:`Scenario`, wired to the alien source + reference parser.

    The bounded-abstraction surface (FR-003): the alien source artifact, its
    grader-only manifest (C-005), the layer-1 known-good reference parser, and the
    :class:`IntakeStrategy` supplying drawer specifics. The registry composes this
    with the observation scenario so the registry lists ≥ 2 sources (SC-003).
    """
    return Scenario(
        name="intake_alien",
        source_path=_INTAKE_SOURCE,
        manifest_path=_INTAKE_MANIFEST,
        reference_parser=_INTAKE_REFERENCE_PARSER,
        strategy=IntakeStrategy(),
    )


__all__ = ["IntakeStrategy", "intake_scenario"]
