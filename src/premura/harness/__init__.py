"""Harness: throwaway sandbox + in-sandbox ingest runner (mission session-log-substrate).

The sandbox (:mod:`premura.harness.sandbox`) is the isolation mechanism that lets
an agent edit parser files and run a real ingest without touching the real repo
or warehouse (FR-020). The ingest runner
(:mod:`premura.harness.ingest_runner`) executes one parser-build ingest as a
subprocess inside a sandbox and emits a JSON outcome envelope on stdout; the
parent harness — never the runner — is the sole session-log writer (FR-021).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from premura.harness.sandbox import (
    EXCLUDED_TOP_LEVEL,
    INSTALL_TIER,
    InstallStep,
    InstallTierResult,
    Sandbox,
    build_sandbox,
    install_parser,
    run_install_tier,
)

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb


def open_sandbox_warehouse_for_grading(warehouse_path: Path) -> duckdb.DuckDBPyConnection:
    """Open the sandbox warehouse read-only for grading, tolerating the failure path.

    On the happy path the in-sandbox ingest runner has already created and
    populated the warehouse file, so this just opens it read-only.

    On the FAILURE path (the parser raised before the runner reached
    :func:`premura.store.duck.initialize`, so NO warehouse file exists), opening a
    missing DuckDB file read-only would itself raise and abort the run BEFORE the
    harness records provenance and finishes the session — violating the spec edge
    case ("parser raises -> graded fail, no partial credit", FR-080). To keep the
    run gradeable and auditable, this helper first materializes an EMPTY warehouse
    (schema seeded, ZERO fact rows) via ``duck.initialize(...).close()`` and then
    opens it read-only. The grader then sees ground truth = 0 rows, so ``loaded``
    fails, ``runtime_valid`` fails (``ingest_run_ok`` is False), and
    ``honest_about_gaps`` fails (nothing loaded, nothing declared) — a deterministic
    ``verdict.passed == False``.

    Either way the returned connection is READ-ONLY; the caller closes it.
    """
    from premura.store import duck

    if not warehouse_path.exists():
        # Materialize the schema with zero fact rows so grading has ground truth.
        duck.initialize(warehouse_path).close()
    return duck.connect(warehouse_path, read_only=True)


__all__ = [
    "EXCLUDED_TOP_LEVEL",
    "INSTALL_TIER",
    "InstallStep",
    "InstallTierResult",
    "Sandbox",
    "build_sandbox",
    "install_parser",
    "open_sandbox_warehouse_for_grading",
    "run_install_tier",
]
