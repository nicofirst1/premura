from __future__ import annotations

import subprocess
import sys

from tests import REPO_ROOT

ROOT = REPO_ROOT


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

    assert "tests/intake/test_schema_regression.py::" not in collected


def test_regression_marker_explicitly_collects_real_export_regressions() -> None:
    collected = _collect_tests("-m", "regression")

    assert "tests/intake/test_schema_regression.py::test_ingest_smoke_then_idempotent" in collected
