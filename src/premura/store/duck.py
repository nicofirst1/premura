"""DuckDB warehouse connection + migrations + dim_metric seed."""

from __future__ import annotations

import importlib.resources as resources
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable

MIGRATIONS_PACKAGE = "premura.store.migrations"
DIM_METRIC_YAML = "dim_metric.yaml"


def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse. Creates parent dir if missing.

    Caller is responsible for calling run_migrations() once after creation.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def run_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply all bundled migrations in lexical order. Idempotent (CREATE IF NOT EXISTS)."""
    for path in sorted(_migration_paths()):
        sql = path.read_text(encoding="utf-8")
        conn.execute(sql)


def _migration_paths() -> Iterable[Path]:
    pkg = resources.files(MIGRATIONS_PACKAGE)
    for entry in pkg.iterdir():
        if entry.name.endswith(".sql"):
            yield Path(str(entry))


def seed_dim_metric(conn: duckdb.DuckDBPyConnection) -> int:
    """Insert / upsert rows from dim_metric.yaml. Returns row count present after seed."""
    yaml_text = (
        resources.files("premura").joinpath(DIM_METRIC_YAML).read_text(encoding="utf-8")
    )
    data = yaml.safe_load(yaml_text) or []
    for row in data:
        conn.execute(
            """
            INSERT INTO hp.dim_metric (metric_id, display_name, canonical_unit, value_kind, description)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (metric_id) DO UPDATE SET
                display_name   = excluded.display_name,
                canonical_unit = excluded.canonical_unit,
                value_kind     = excluded.value_kind,
                description    = excluded.description
            """,
            [
                row["metric_id"],
                row["display_name"],
                row["canonical_unit"],
                row["value_kind"],
                row.get("description"),
            ],
        )
    return conn.execute("SELECT COUNT(*) FROM hp.dim_metric").fetchone()[0]


def upsert_dim_source(
    conn: duckdb.DuckDBPyConnection,
    *,
    source_id: str,
    source_kind: str,
    app_package: str | None = None,
    app_name: str | None = None,
    device_manufacturer: str | None = None,
    device_model: str | None = None,
) -> None:
    """Ensure a dim_source row exists; bump last_seen on every call."""
    conn.execute(
        """
        INSERT INTO hp.dim_source (
            source_id, source_kind, app_package, app_name,
            device_manufacturer, device_model, first_seen, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, now(), now())
        ON CONFLICT (source_id) DO UPDATE SET
            app_package          = COALESCE(excluded.app_package, hp.dim_source.app_package),
            app_name             = COALESCE(excluded.app_name, hp.dim_source.app_name),
            device_manufacturer  = COALESCE(excluded.device_manufacturer, hp.dim_source.device_manufacturer),
            device_model         = COALESCE(excluded.device_model, hp.dim_source.device_model),
            last_seen            = now()
        """,
        [source_id, source_kind, app_package, app_name, device_manufacturer, device_model],
    )


def initialize(db_path: Path) -> duckdb.DuckDBPyConnection:
    """One-call helper: connect + migrate + seed."""
    conn = connect(db_path)
    run_migrations(conn)
    seed_dim_metric(conn)
    return conn
