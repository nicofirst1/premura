"""Deterministic three-rule grader — the heart of the honesty rail (FR-060..065).

``grade(...)`` reads three sources of ground truth and **recomputes** a verdict;
it never trusts a parser/runner self-report for a fact it can derive itself
(FR-061 / NFR-006):

* the **sandbox warehouse** (boundary truth) — actual loaded row counts and which
  ``metric_id``s actually landed in ``hp.fact_*``;
* the **committed fixture manifest** (``fixture_fields.yaml``, ground truth, D6) —
  the complete enumeration of source fields and their distinct canonical metric;
* the **captured ingest provenance** (WP01 store / WP03 envelope) — the captured
  ``declared_metrics`` / ``emitted_metric_ids`` sets and the parser's *claims*
  (``unmapped_metrics`` / ``skipped_rows``), plus the loader-measured
  ``rows_inserted`` and the ``ingest_run`` step status.

The three rules:

1. ``loaded`` (FR-062) — recomputed from the WAREHOUSE: a positive warehouse row
   count that is consistent with the logged ``rows_inserted``.
2. ``runtime_valid`` (FR-063) — delegates to WP02's
   :func:`premura.parsers.contract_check.check_runtime_contract` over the CAPTURED
   sets + the sandbox warehouse; never a stored ``contract_pass`` flag.
3. ``honest_about_gaps`` (FR-064 / D6) — reconciles every manifest source field
   against (a) its distinct canonical metric being **present in the warehouse** or
   (b) the field being **declared** in the parser's ``unmapped_metrics`` /
   ``skipped_rows``. A field that is neither is a *silent drop* and fails honesty.

The returned verdict conforms EXACTLY to ``contracts/grader-verdict.schema.json``
(``additionalProperties: false`` everywhere, all arrays sorted, **no ids/
timestamps**), so two runs over the same evidence produce a byte-identical verdict
(D5 / NFR-001). The grader is the **sole** producer of ``contract_pass`` (FR-065):
the caller (WP06/WP07) persists ``verdict["rules"]["runtime_valid"]["passed"]`` via
``record_ingest_provenance(contract_pass=...)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from premura.parsers.contract_check import check_runtime_contract

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb


# Fact tables whose ``metric_id`` rows count as "loaded" boundary truth. Slice-one
# parsers emit measurements; intervals are included so a future interval-emitting
# parser is graded on the same warehouse truth without changing the grader.
_FACT_TABLES: tuple[str, ...] = ("hp.fact_measurement", "hp.fact_interval")


class IngestProvenance(Protocol):
    """The captured evidence the grader reconciles — passed in, never re-read with trust.

    Structural so either a live object or a small test/harness helper assembled
    from the WP03 ingest-outcome envelope satisfies it without this module
    importing the session-log store. Every field here is *captured measured
    evidence* or a *parser claim*; none of it is a precomputed rule verdict.
    """

    declared_metrics: Sequence[str]
    emitted_metric_ids: Sequence[str]
    unmapped_metrics: Sequence[str]
    skipped_rows: Sequence[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool


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


def _warehouse_row_count(warehouse_conn: duckdb.DuckDBPyConnection) -> int:
    """Total rows actually present across the warehouse fact tables (boundary truth)."""
    total = 0
    for table in _FACT_TABLES:
        row = warehouse_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        total += int(row[0]) if row else 0
    return total


def _metrics_present_in_warehouse(warehouse_conn: duckdb.DuckDBPyConnection) -> set[str]:
    """The set of ``metric_id``s that actually landed in the warehouse fact tables.

    Boundary truth: derived from the warehouse itself, NOT from the parser's
    ``emitted_metric_ids`` claim — so a parser lying about emission cannot fake a
    field being honestly loaded (NFR-006).
    """
    present: set[str] = set()
    for table in _FACT_TABLES:
        rows = warehouse_conn.execute(f"SELECT DISTINCT metric_id FROM {table}").fetchall()
        present.update(row[0] for row in rows)
    return present


def _grade_loaded(
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
) -> dict[str, Any]:
    """``loaded`` rule (FR-062), recomputed from the warehouse, not a self-report.

    ``passed`` iff the warehouse holds at least one fact row AND that count is
    consistent with the loader-measured ``rows_inserted``. A parser that raised
    (0 rows) or a tampered ``rows_inserted`` that disagrees with the warehouse both
    fail here.
    """
    warehouse_rows = _warehouse_row_count(warehouse_conn)
    logged_rows_inserted = int(provenance.rows_inserted)
    passed = warehouse_rows > 0 and warehouse_rows == logged_rows_inserted
    return {
        "passed": passed,
        "warehouse_rows": warehouse_rows,
        "logged_rows_inserted": logged_rows_inserted,
    }


def _grade_runtime_valid(
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
) -> dict[str, Any]:
    """``runtime_valid`` rule (FR-063): delegate to WP02 over the CAPTURED sets.

    The dataclass field is ``ContractCheckResult.runtime_valid`` (bool); the
    schema's ``runtime_valid`` block names that boolean ``passed``. Map the
    dataclass ``runtime_valid`` -> schema ``passed`` and carry ``violations``
    through (already sorted by the checker). Inputs are the captured declared/
    emitted sets + the ingest-run status — never a stored ``contract_pass`` flag.
    """
    result = check_runtime_contract(
        declared_metrics=list(provenance.declared_metrics),
        emitted_metric_ids=list(provenance.emitted_metric_ids),
        warehouse_conn=warehouse_conn,
        ingest_run_ok=bool(provenance.ingest_run_ok),
    )
    return {
        "passed": result.runtime_valid,
        "violations": sorted(result.violations),
    }


def _grade_honest_about_gaps(
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
    fixture_manifest: dict[str, Any],
) -> dict[str, Any]:
    """``honest_about_gaps`` rule (FR-064 / D6): reconcile manifest vs ground truth.

    For every source field in the manifest:

    * if it maps to a canonical metric -> handled iff that metric is **present in
      the warehouse** (boundary truth) OR the field is **declared** by the parser;
    * if it has no canonical metric -> handled iff the field is **declared**.

    Any field that is neither loaded nor declared is a *silent drop*. The
    distinct-metric constraint (D6 / R3, enforced by WP04) makes "metric present"
    an unambiguous witness for the one field that maps to it.
    """
    metrics_present = _metrics_present_in_warehouse(warehouse_conn)
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
    return {"passed": not silent_drops, "silent_drops": silent_drops}


def grade(
    *,
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
    fixture_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Recompute the three-rule verdict from ground truth (FR-060..064).

    Args:
        provenance: the CAPTURED ingest evidence (declared/emitted sets, parser
            claims, loader-measured ``rows_inserted``, ``ingest_run`` status). Passed
            in, never re-read with trust; no rule reads a precomputed verdict from it.
        warehouse_conn: the disposable sandbox warehouse — boundary truth for the
            ``loaded`` count, the ``dim_metric`` existence clause, and the
            "metric present" honesty witness. Read-only is sufficient.
        fixture_manifest: the parsed committed manifest (``fixture_fields.yaml``),
            the honesty ground truth (D6).

    Returns:
        A plain dict conforming to ``contracts/grader-verdict.schema.json``:
        ``{"passed": bool, "rules": {"loaded": ..., "runtime_valid": ...,
        "honest_about_gaps": ...}}``. All arrays sorted; **no ids, no timestamps** —
        so two runs over the same evidence serialize byte-identically (D5/NFR-001).
        ``rules.runtime_valid.passed`` is the grader's recomputed runtime-subset
        result that the caller persists as ``contract_pass`` (FR-065); the grader is
        its sole producer.
    """
    loaded = _grade_loaded(provenance, warehouse_conn)
    runtime_valid = _grade_runtime_valid(provenance, warehouse_conn)
    honest_about_gaps = _grade_honest_about_gaps(provenance, warehouse_conn, fixture_manifest)

    passed = bool(loaded["passed"] and runtime_valid["passed"] and honest_about_gaps["passed"])
    return {
        "passed": passed,
        "rules": {
            "loaded": loaded,
            "runtime_valid": runtime_valid,
            "honest_about_gaps": honest_about_gaps,
        },
    }


__all__ = ["IngestProvenance", "grade"]
