from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _collect_tests(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
        check=True,
    )
    return result.stdout


def test_default_pytest_collection_excludes_real_export_regressions() -> None:
    collected = _collect_tests()

    assert "tests/test_schema_regression.py::" not in collected


def test_regression_marker_explicitly_collects_real_export_regressions() -> None:
    collected = _collect_tests("-m", "regression")

    assert "tests/test_schema_regression.py::test_ingest_smoke_then_idempotent" in collected
