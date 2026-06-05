"""The ``Scenario`` abstraction + injected ``DrawerGradingStrategy`` (FR-001).

A new acceptance source is added by **registering a scenario**, with **no change
to the shared grading logic** (NFR-005). A :class:`Scenario` is a frozen value
object that names a synthetic source artifact, its grader-only ground-truth
manifest, the known-good reference parser, and the
:class:`DrawerGradingStrategy` that supplies all drawer-specific grading.

The strategy is the seam the generic :func:`premura.harness.grader.grade` body
calls into. It exposes exactly three responsibilities (one per grader rule):

* ``boundary_truth(conn)`` -> :class:`BoundaryTruth` — the loaded row count and
  the set of metric keys that actually landed in the drawer's warehouse tables
  (FR-006). Warehouse-recomputed boundary truth, never the parser's self-report.
* ``runtime_check(provenance, conn)`` -> ``ContractCheckResult`` — the drawer's
  bounded runtime-contract clause set over the captured declared/emitted sets.
* ``gap_set(manifest, provenance, boundary_truth)`` -> ``list[str]`` — the
  silent-drop source fields: manifest fields neither truly loaded (witnessed by
  ``boundary_truth``) nor declared by the parser.

This module is intentionally import-light (no Ollama, no network): it is imported
by the grader. The only scenario registered here is the observation one; the
registry that lists ≥ 2 scenarios is WP04's ``scenario_registry.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from premura.config import REPO_ROOT
from premura.parsers.contract_check import check_runtime_contract

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

    from premura.parsers.contract_check import ContractCheckResult


# Fact tables whose ``metric_id`` rows count as "loaded" boundary truth for the
# observation drawer. Intervals are included so a future interval-emitting
# observation parser is graded on the same warehouse truth without code change.
_OBSERVATION_FACT_TABLES: tuple[str, ...] = ("hp.fact_measurement", "hp.fact_interval")

# Committed synthetic observation fixture + its grader-only ground-truth manifest.
_OBSERVATION_FIXTURE_DIR = Path(REPO_ROOT) / "tests" / "fixtures" / "session_log"
_OBSERVATION_SOURCE = _OBSERVATION_FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
_OBSERVATION_MANIFEST = _OBSERVATION_FIXTURE_DIR / "fixture_fields.yaml"
# The layer-1 known-good observation parser (import target). Fitbit is a
# deliberately unsupported live-trial target, so the reference parser is the
# committed honest fixture installed into the sandbox — not a shipped parser.
_OBSERVATION_REFERENCE_PARSER = (
    "tests.fixtures.session_log.parsers.good_fitbit_hr:GoodFitbitHrParser"
)


class IngestProvenance(Protocol):
    """The captured ingest evidence a strategy reconciles — passed in, never trusted.

    Structural so either a live object or a small test/harness helper assembled
    from the WP03 ingest-outcome envelope satisfies it. Every field is *captured
    measured evidence* or a *parser claim*; none is a precomputed rule verdict.
    """

    declared_metrics: Sequence[str]
    emitted_metric_ids: Sequence[str]
    unmapped_metrics: Sequence[str]
    skipped_rows: Sequence[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool


@dataclass(frozen=True)
class BoundaryTruth:
    """Warehouse-recomputed boundary truth for one graded run (FR-006).

    Recomputed from the drawer's warehouse tables, NOT from the parser's
    ``emitted_metric_ids`` claim — so a parser lying about emission cannot fake a
    field being honestly loaded (NFR-006). A row landing in the *wrong* drawer's
    tables is absent here and so cannot witness a loaded field.

    Attributes:
        row_count: total fact rows present across the drawer's warehouse tables.
        present_keys: the distinct ``metric_id`` (or drawer key) values that
            actually landed — the witness set for the honesty reconciliation.
    """

    row_count: int
    present_keys: frozenset[str]


class DrawerGradingStrategy(Protocol):
    """Drawer-specific grading behind the generic grader (NFR-005).

    The three methods are the only places a drawer's table names / clause set /
    manifest-reconciliation rule appear. The shared :func:`grade` body names none
    of them; it just orchestrates these calls into the unchanged verdict schema.
    """

    def boundary_truth(self, warehouse_conn: duckdb.DuckDBPyConnection) -> BoundaryTruth:
        """Loaded row count + present metric keys from the drawer's warehouse."""
        ...

    def runtime_check(
        self,
        provenance: IngestProvenance,
        warehouse_conn: duckdb.DuckDBPyConnection,
    ) -> ContractCheckResult:
        """Run the drawer's runtime-contract clause set over the captured sets."""
        ...

    def gap_set(
        self,
        fixture_manifest: dict[str, Any],
        provenance: IngestProvenance,
        boundary_truth: BoundaryTruth,
    ) -> list[str]:
        """Sorted silent-drop source fields (neither truly loaded nor declared)."""
        ...


@dataclass(frozen=True)
class Scenario:
    """A registered acceptance source — the bounded abstraction (FR-001).

    Adding a source is registering one of these; the shared grade path is never
    edited (see ``contracts/scenario-contract.md``). ``manifest_path`` is
    grader-only ground truth and MUST NOT appear on any operator-visible path
    (C-005).

    Attributes:
        name: unique within the registry.
        source_path: a synthetic, obviously-fake source artifact (no PHI, NFR-004).
        manifest_path: grader-only ground-truth field manifest (C-005).
        reference_parser: the layer-1 known-good parser import target.
        strategy: the :class:`DrawerGradingStrategy` supplying drawer specifics.
    """

    name: str
    source_path: Path
    manifest_path: Path
    reference_parser: str
    strategy: DrawerGradingStrategy


# --------------------------------------------------------------------------- #
# Observation strategy — today's grader logic, moved verbatim (C-004).
# --------------------------------------------------------------------------- #


def _declared_field_names(provenance: IngestProvenance) -> set[str]:
    """Source-field names the parser *declared* as gaps (unmapped or skipped).

    These are the parser's own claims — used only on the declared side of the
    honesty reconciliation, never to witness that a field was actually loaded.
    """
    declared: set[str] = set(provenance.unmapped_metrics)
    for row in provenance.skipped_rows:
        raw_field = row.get("raw_field")
        if isinstance(raw_field, str):
            declared.add(raw_field)
    return declared


@dataclass(frozen=True)
class ObservationStrategy:
    """The observation drawer's grading — today's ``grader`` logic, unchanged (C-004).

    Wraps the verbatim ``_grade_loaded`` fact-table count, the
    ``check_runtime_contract`` delegation, and the manifest honesty reconcile so
    the observation verdict reproduces byte-for-byte after the grader refactor.
    """

    fact_tables: tuple[str, ...] = _OBSERVATION_FACT_TABLES

    def boundary_truth(self, warehouse_conn: duckdb.DuckDBPyConnection) -> BoundaryTruth:
        """Total fact rows + distinct ``metric_id``s present in the warehouse.

        Boundary truth derived from the warehouse itself, NOT from the parser's
        ``emitted_metric_ids`` claim (NFR-006).
        """
        total = 0
        present: set[str] = set()
        for table in self.fact_tables:
            count_row = warehouse_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            total += int(count_row[0]) if count_row else 0
            metric_rows = warehouse_conn.execute(
                f"SELECT DISTINCT metric_id FROM {table}"
            ).fetchall()
            present.update(row[0] for row in metric_rows)
        return BoundaryTruth(row_count=total, present_keys=frozenset(present))

    def runtime_check(
        self,
        provenance: IngestProvenance,
        warehouse_conn: duckdb.DuckDBPyConnection,
    ) -> ContractCheckResult:
        """Delegate to WP02's checker over the CAPTURED sets (never a stored flag)."""
        return check_runtime_contract(
            declared_metrics=list(provenance.declared_metrics),
            emitted_metric_ids=list(provenance.emitted_metric_ids),
            warehouse_conn=warehouse_conn,
            ingest_run_ok=bool(provenance.ingest_run_ok),
        )

    def gap_set(
        self,
        fixture_manifest: dict[str, Any],
        provenance: IngestProvenance,
        boundary_truth: BoundaryTruth,
    ) -> list[str]:
        """Sorted silent-drop fields: manifest vs (present-in-warehouse ∪ declared).

        For every source field in the manifest: it is *handled* iff its canonical
        metric is present in the warehouse (boundary truth) OR the field is
        declared by the parser. Any field that is neither is a silent drop. The
        distinct-metric constraint (D6 / R3) makes "metric present" an
        unambiguous witness for the one field that maps to it.
        """
        metrics_present = boundary_truth.present_keys
        declared_fields = _declared_field_names(provenance)

        silent_drops: list[str] = []
        for source_field in fixture_manifest["source_fields"]:
            name = source_field["name"]
            canonical_metric = source_field.get("canonical_metric")
            loaded = canonical_metric is not None and canonical_metric in metrics_present
            declared = name in declared_fields
            if not (loaded or declared):
                silent_drops.append(name)

        silent_drops.sort()
        return silent_drops


def observation_scenario() -> Scenario:
    """The observation :class:`Scenario`, wired to today's grading + committed fixture.

    The only scenario this module registers. WP04's registry composes this with
    the new intake scenario so the registry lists ≥ 2 sources (SC-003).
    """
    return Scenario(
        name="observation",
        source_path=_OBSERVATION_SOURCE,
        manifest_path=_OBSERVATION_MANIFEST,
        reference_parser=_OBSERVATION_REFERENCE_PARSER,
        strategy=ObservationStrategy(),
    )


__all__ = [
    "BoundaryTruth",
    "DrawerGradingStrategy",
    "IngestProvenance",
    "ObservationStrategy",
    "Scenario",
    "observation_scenario",
]
