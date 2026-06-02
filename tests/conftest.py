"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from premura.store import duck


@pytest.fixture()
def empty_warehouse(tmp_path: Path):
    """Initialized DuckDB warehouse with the seed dim_metric and clean schema."""
    db = tmp_path / "test.duckdb"
    conn = duck.initialize(db)
    yield conn
    conn.close()
