"""Shared fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Disable color at import time — conftest is imported before test modules pull
# in premura.cli, whose module-level ``Console()`` captures FORCE_COLOR at
# construction. Rich treats FORCE_COLOR / CLICOLOR_FORCE as set-by-presence, so
# the vars must be removed, not blanked, for NO_COLOR to win.
for _var in ("FORCE_COLOR", "CLICOLOR_FORCE"):
    os.environ.pop(_var, None)
os.environ["NO_COLOR"] = "1"

from premura.store import duck  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _disable_forced_color():
    """Keep Rich uncolored under pytest regardless of the developer's shell."""
    for var in ("FORCE_COLOR", "CLICOLOR_FORCE"):
        os.environ.pop(var, None)
    os.environ["NO_COLOR"] = "1"
    yield


@pytest.fixture()
def empty_warehouse(tmp_path: Path):
    """Initialized DuckDB warehouse with the seed dim_metric and clean schema."""
    db = tmp_path / "test.duckdb"
    conn = duck.initialize(db)
    yield conn
    conn.close()
