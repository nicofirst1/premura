"""Runtime contract checker (FR-050 / FR-061 / FR-063).

The minimal runtime-valid checker that does not exist elsewhere: a **pure
function over captured evidence** so the grader (WP05) can *recompute* the
runtime-valid subset of ``parsers/CONTRACT.md`` and never *trust* a precomputed
flag.

It computes only the **runtime tier** of the contract. The reviewer-checklist
tier (decision-tree order, fixtures, PR notes, ontology diff, clinically-standard
aliases) is explicitly out of scope — it needs a per-field resolution map that
slice one does not capture.

The four runtime-valid clauses are recomputed from captured evidence; the checker
does **not** rely on the parser (``base.py`` ``derived:`` raise) or loader
(``loader.validate_batch_against_warehouse`` ``dim_metric`` raise) having raised.
It derives each fact itself so the grader's verdict never rests on trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


@dataclass(slots=True)
class ContractCheckResult:
    """Recomputed runtime-valid verdict over captured evidence.

    ``violations`` are ``"<clause>: <detail>"`` strings, sorted for determinism.
    This feeds ``grader-verdict.schema.json``'s ``runtime_valid.violations``.
    """

    runtime_valid: bool
    violations: list[str] = field(default_factory=list)


def check_runtime_contract(
    *,
    declared_metrics: list[str],
    emitted_metric_ids: list[str],
    warehouse_conn: duckdb.DuckDBPyConnection,
    ingest_run_ok: bool,
) -> ContractCheckResult:
    """Recompute the runtime-valid subset of ``parsers/CONTRACT.md`` from evidence.

    Args:
        declared_metrics: the metrics the batch declared (captured set).
        emitted_metric_ids: the metric_ids actually emitted on rows (captured set).
        warehouse_conn: the sandbox warehouse — boundary truth for the
            ``dim_metric`` existence clause. Queried, never trusted to a
            hardcoded list (altitude: check, don't enumerate).
        ingest_run_ok: the ingest_run step status (did it produce a batch without
            raising).

    Returns:
        A ``ContractCheckResult`` with ``runtime_valid`` and a sorted
        ``violations`` list. Pure: no I/O beyond the read-only ``dim_metric``
        query, no file writes, no global state, no ids/timestamps in the output.
    """
    violations: list[str] = []

    # Clause 1 — no_derived_emitted: the derived: namespace is reserved for the
    # Stage 2 engine; parsers must not emit it (mirrors base.py's raise).
    derived = sorted(m for m in emitted_metric_ids if m.startswith("derived:"))
    if derived:
        violations.append(f"no_derived_emitted: {derived}")

    # Clause 2 — declared_equals_emitted: the declared set must exactly match the
    # emitted set (symmetric difference names both directions of drift).
    declared_set = set(declared_metrics)
    emitted_set = set(emitted_metric_ids)
    if declared_set != emitted_set:
        diff = sorted(declared_set ^ emitted_set)
        violations.append(f"declared_equals_emitted: {diff}")

    # Clause 3 — declared_exist_in_dim_metric: every declared metric must exist in
    # hp.dim_metric (mirrors loader.validate_batch_against_warehouse). Recomputed
    # against the passed sandbox warehouse, not a module-level constant.
    if declared_metrics:
        placeholders = ", ".join(["?"] * len(declared_metrics))
        rows = warehouse_conn.execute(
            f"SELECT metric_id FROM hp.dim_metric WHERE metric_id IN ({placeholders})",
            declared_metrics,
        ).fetchall()
        present = {row[0] for row in rows}
        missing = sorted(set(declared_metrics) - present)
        if missing:
            violations.append(f"declared_exist_in_dim_metric: {missing}")

    # Clause 4 — produced_batch_without_raising: the ingest run must have produced
    # a batch without raising.
    if not ingest_run_ok:
        violations.append("produced_batch_without_raising: ingest_run failed")

    violations.sort()
    return ContractCheckResult(runtime_valid=not violations, violations=violations)
