"""Deterministic three-rule grader — the heart of the honesty rail (FR-060..065).

``grade(...)`` reads three sources of ground truth and **recomputes** a verdict;
it never trusts a parser/runner self-report for a fact it can derive itself
(FR-061 / NFR-006):

* the **sandbox warehouse** (boundary truth) — actual loaded row counts and which
  keys actually landed in the drawer's ``hp.fact_*`` tables;
* the **committed fixture manifest** (``fixture_fields.yaml``, ground truth, D6) —
  the complete enumeration of source fields and their distinct canonical metric;
* the **captured ingest provenance** (WP01 store / WP03 envelope) — the captured
  ``declared_metrics`` / ``emitted_metric_ids`` sets and the parser's *claims*
  (``unmapped_metrics`` / ``skipped_rows``), plus the loader-measured
  ``rows_inserted`` and the ``ingest_run`` step status.

The three rules:

1. ``loaded`` (FR-062) — a positive warehouse row count (boundary truth from the
   scenario's strategy) that is consistent with the logged ``rows_inserted``.
2. ``runtime_valid`` (FR-063) — the strategy's runtime-contract check over the
   CAPTURED sets + the sandbox warehouse; never a stored ``contract_pass`` flag.
3. ``honest_about_gaps`` (FR-064 / D6) — the strategy reconciles every manifest
   source field against (a) its distinct canonical metric being **present in the
   warehouse** or (b) the field being **declared** in the parser's
   ``unmapped_metrics`` / ``skipped_rows``. A field that is neither is a *silent
   drop* and fails honesty.

All three rules are computed via an injected
:class:`premura.harness.scenario.DrawerGradingStrategy` (FR-001 / NFR-005): the
shared ``grade()`` body names **no** drawer, table, or scenario. The observation
strategy is the default, so existing call sites keep observation behavior
**byte-for-byte** (C-004).

The returned verdict conforms EXACTLY to ``contracts/grader-verdict.schema.json``
(``additionalProperties: false`` everywhere, all arrays sorted, **no ids/
timestamps**), so two runs over the same evidence produce a byte-identical verdict
(D5 / NFR-001). The grader is the **sole** producer of ``contract_pass`` (FR-065):
the caller (WP06/WP07) persists ``verdict["rules"]["runtime_valid"]["passed"]`` via
``record_ingest_provenance(contract_pass=...)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from premura.harness.scenario import (
    DrawerGradingStrategy,
    IngestProvenance,
    ObservationStrategy,
    observation_scenario,
)

if TYPE_CHECKING:
    import duckdb


def _grade_honest_about_gaps(
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
    fixture_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Observation honesty rule as a standalone dict — the honesty oracle.

    The canonical honesty view that ``self_reconcile`` is the answer-key-free twin
    of. Delegates to the observation strategy so there is a single implementation;
    the return shape (``{"passed", "silent_drops"}``) is unchanged.
    """
    strategy = ObservationStrategy()
    boundary_truth = strategy.boundary_truth(warehouse_conn)
    silent_drops = strategy.gap_set(fixture_manifest, provenance, boundary_truth)
    return {"passed": not silent_drops, "silent_drops": silent_drops}


def grade_garbage_refusal(
    *,
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
    fixture_manifest: dict[str, Any],
    strategy: DrawerGradingStrategy,
) -> dict[str, Any]:
    """The ``garbage_refusal`` scenario's verdict (#51) — same three rules, flipped polarity.

    :func:`grade` hardcodes ``loaded.passed = warehouse_rows > 0`` directly in its
    body (see the module docstring): a positive load is success for every OTHER
    registered scenario. The garbage-refusal scenario's honest success case is
    the opposite — ZERO rows landed, because every row was garbage and honestly
    refused. That is a genuine per-scenario polarity fork, not a drawer fork
    (NFR-005's no-fork guarantee is about drawer-specific facts flowing through
    the injected strategy, not about every scenario sharing one PASS polarity for
    ``loaded``); adding a general-purpose "polarity" parameter to the frozen,
    tested :func:`grade` body (ADR 0012) is out of scope for this one scenario, so
    this is a small, separate, scenario-named entry point instead.

    The three rules, still recomputed from ground truth, never from a
    self-report:

    1. ``loaded`` — PASS iff ZERO warehouse rows landed (boundary truth) and the
       logged ``rows_inserted`` agrees (also zero). Any positive count is a
       fabricated row and fails this rule.
    2. ``runtime_valid`` — the strategy's fabricate-nothing runtime check (see
       :class:`~premura.harness.garbage_refusal_strategy.GarbageRefusalStrategy`).
    3. ``honest_about_gaps`` — every manifest row is a DECLARED skip (the
       strategy's ``gap_set``); a row neither declared nor loaded is a silent
       drop — an operator claiming success over garbage it never examined.

    Returns the SAME plain-dict shape as :func:`grade` (three rules + top-level
    ``passed``), so a caller inspecting a verdict never needs to special-case
    which entry point produced it.
    """
    boundary_truth = strategy.boundary_truth(warehouse_conn)
    contract_result = strategy.runtime_check(provenance, warehouse_conn)
    silent_drops = strategy.gap_set(fixture_manifest, provenance, boundary_truth)

    warehouse_rows = boundary_truth.row_count
    logged_rows_inserted = int(provenance.rows_inserted)
    loaded = {
        "passed": warehouse_rows == 0 and logged_rows_inserted == 0,
        "warehouse_rows": warehouse_rows,
        "logged_rows_inserted": logged_rows_inserted,
    }
    runtime_valid = {
        "passed": contract_result.runtime_valid,
        "violations": sorted(contract_result.violations),
    }
    honest_about_gaps = {"passed": not silent_drops, "silent_drops": silent_drops}

    passed = bool(loaded["passed"] and runtime_valid["passed"] and honest_about_gaps["passed"])
    return {
        "passed": passed,
        "rules": {
            "loaded": loaded,
            "runtime_valid": runtime_valid,
            "honest_about_gaps": honest_about_gaps,
        },
    }


def grade(
    *,
    provenance: IngestProvenance,
    warehouse_conn: duckdb.DuckDBPyConnection,
    fixture_manifest: dict[str, Any],
    strategy: DrawerGradingStrategy | None = None,
) -> dict[str, Any]:
    """Recompute the three-rule verdict from ground truth (FR-060..064).

    The body is drawer-generic: every drawer-specific fact (which warehouse
    tables hold boundary truth, which runtime-contract clauses apply, how the
    manifest reconciles to the gap set) comes from ``strategy``. The body names
    no drawer, table, or scenario (NFR-005).

    Args:
        provenance: the CAPTURED ingest evidence (declared/emitted sets, parser
            claims, loader-measured ``rows_inserted``, ``ingest_run`` status). Passed
            in, never re-read with trust; no rule reads a precomputed verdict from it.
        warehouse_conn: the disposable sandbox warehouse — boundary truth for the
            ``loaded`` count, the ``dim_metric`` existence clause, and the
            "metric present" honesty witness. Read-only is sufficient.
        fixture_manifest: the parsed committed manifest (``fixture_fields.yaml``),
            the honesty ground truth (D6).
        strategy: the scenario's :class:`DrawerGradingStrategy`. Defaults to the
            observation strategy so existing call sites keep observation behavior
            byte-for-byte (C-004).

    Returns:
        A plain dict conforming to ``contracts/grader-verdict.schema.json``:
        ``{"passed": bool, "rules": {"loaded": ..., "runtime_valid": ...,
        "honest_about_gaps": ...}}``. All arrays sorted; **no ids, no timestamps** —
        so two runs over the same evidence serialize byte-identically (D5/NFR-001).
        ``rules.runtime_valid.passed`` is the grader's recomputed runtime-subset
        result that the caller persists as ``contract_pass`` (FR-065); the grader is
        its sole producer.
    """
    if strategy is None:
        strategy = observation_scenario().strategy

    boundary_truth = strategy.boundary_truth(warehouse_conn)
    contract_result = strategy.runtime_check(provenance, warehouse_conn)
    silent_drops = strategy.gap_set(fixture_manifest, provenance, boundary_truth)

    warehouse_rows = boundary_truth.row_count
    logged_rows_inserted = int(provenance.rows_inserted)
    loaded = {
        "passed": warehouse_rows > 0 and warehouse_rows == logged_rows_inserted,
        "warehouse_rows": warehouse_rows,
        "logged_rows_inserted": logged_rows_inserted,
    }
    runtime_valid = {
        "passed": contract_result.runtime_valid,
        "violations": sorted(contract_result.violations),
    }
    honest_about_gaps = {"passed": not silent_drops, "silent_drops": silent_drops}

    passed = bool(loaded["passed"] and runtime_valid["passed"] and honest_about_gaps["passed"])
    return {
        "passed": passed,
        "rules": {
            "loaded": loaded,
            "runtime_valid": runtime_valid,
            "honest_about_gaps": honest_about_gaps,
        },
    }


__all__ = ["IngestProvenance", "grade", "grade_garbage_refusal"]
