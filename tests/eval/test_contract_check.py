"""Tests for the runtime contract checker (WP02, FR-050/FR-061/FR-063).

Black-box: assert only on the returned ``ContractCheckResult``. Each runtime
clause is exercised passing and failing independently (presence-vs-absence per
the fidelity gate). The ``empty_warehouse`` fixture supplies boundary truth for
the ``dim_metric`` existence clause (seed ``dim_metric`` is loaded).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from premura.parsers.contract_check import ContractCheckResult, check_runtime_contract

if TYPE_CHECKING:
    import duckdb


def _seed_metric_ids(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Two metric_ids that are present in the seeded ``hp.dim_metric``."""
    rows = conn.execute("SELECT metric_id FROM hp.dim_metric ORDER BY metric_id LIMIT 2").fetchall()
    ids = [row[0] for row in rows]
    assert len(ids) == 2, "seed dim_metric must provide at least two metrics for fixtures"
    return ids


def test_all_clauses_pass(empty_warehouse: duckdb.DuckDBPyConnection) -> None:
    metrics = _seed_metric_ids(empty_warehouse)
    result = check_runtime_contract(
        declared_metrics=metrics,
        emitted_metric_ids=list(reversed(metrics)),  # same set, different order
        warehouse_conn=empty_warehouse,
        ingest_run_ok=True,
    )
    assert isinstance(result, ContractCheckResult)
    assert result.runtime_valid is True
    assert result.violations == []


def test_derived_emitted_fails(empty_warehouse: duckdb.DuckDBPyConnection) -> None:
    metrics = _seed_metric_ids(empty_warehouse)
    declared = [*metrics, "derived:foo"]
    result = check_runtime_contract(
        declared_metrics=declared,
        emitted_metric_ids=declared,
        warehouse_conn=empty_warehouse,
        ingest_run_ok=True,
    )
    assert result.runtime_valid is False
    assert any(v.startswith("no_derived_emitted:") for v in result.violations)
    assert any("derived:foo" in v for v in result.violations)


def test_declared_not_equal_emitted_fails(
    empty_warehouse: duckdb.DuckDBPyConnection,
) -> None:
    metrics = _seed_metric_ids(empty_warehouse)
    result = check_runtime_contract(
        declared_metrics=metrics,
        emitted_metric_ids=metrics[:1],  # emitted is a strict subset of declared
        warehouse_conn=empty_warehouse,
        ingest_run_ok=True,
    )
    assert result.runtime_valid is False
    assert any(v.startswith("declared_equals_emitted:") for v in result.violations)
    # the missing-from-emitted metric is named in the detail
    assert any(metrics[1] in v for v in result.violations)


def test_declared_missing_from_dim_metric_fails(
    empty_warehouse: duckdb.DuckDBPyConnection,
) -> None:
    metrics = _seed_metric_ids(empty_warehouse)
    absent = "vendor:test:not_in_dim_metric_xyz"
    declared = [*metrics, absent]
    result = check_runtime_contract(
        declared_metrics=declared,
        emitted_metric_ids=declared,
        warehouse_conn=empty_warehouse,
        ingest_run_ok=True,
    )
    assert result.runtime_valid is False
    assert any(v.startswith("declared_exist_in_dim_metric:") for v in result.violations)
    assert any(absent in v for v in result.violations)


def test_ingest_run_not_ok_fails(empty_warehouse: duckdb.DuckDBPyConnection) -> None:
    metrics = _seed_metric_ids(empty_warehouse)
    result = check_runtime_contract(
        declared_metrics=metrics,
        emitted_metric_ids=metrics,
        warehouse_conn=empty_warehouse,
        ingest_run_ok=False,
    )
    assert result.runtime_valid is False
    assert "produced_batch_without_raising: ingest_run failed" in result.violations


def test_violations_sorted(empty_warehouse: duckdb.DuckDBPyConnection) -> None:
    # Trip every clause at once; the violations list must be deterministically
    # sorted regardless of input ordering.
    metrics = _seed_metric_ids(empty_warehouse)
    result = check_runtime_contract(
        declared_metrics=[*metrics, "derived:z", "vendor:test:absent_metric"],
        emitted_metric_ids=["derived:z", *metrics],  # also != declared set
        warehouse_conn=empty_warehouse,
        ingest_run_ok=False,
    )
    assert result.runtime_valid is False
    assert result.violations == sorted(result.violations)
    assert len(result.violations) >= 2
