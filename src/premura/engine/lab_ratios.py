"""Built-in sparse lab derivations for M3's first Stage 2 slice."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ._registry import signal

if TYPE_CHECKING:
    import duckdb


@signal(
    name="ast_alt_ratio",
    domain=["liver", "blood"],
    inputs=["lab:ast", "lab:alt"],
    output="derived:ast_alt_ratio",
    priority="high",
    auto_safe=True,
    revision="1",
)
def compute_ast_alt_ratio(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _ratio_rows(
        conn,
        numerator_metric="lab:ast",
        denominator_metric="lab:alt",
        output_metric="derived:ast_alt_ratio",
        unit="ratio",
    )


@signal(
    name="ldl_hdl_ratio",
    domain=["cardiometabolic", "blood"],
    inputs=["lab:ldl", "lab:hdl"],
    output="derived:ldl_hdl_ratio",
    priority="high",
    auto_safe=True,
    revision="1",
)
def compute_ldl_hdl_ratio(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _ratio_rows(
        conn,
        numerator_metric="lab:ldl",
        denominator_metric="lab:hdl",
        output_metric="derived:ldl_hdl_ratio",
        unit="ratio",
    )


@signal(
    name="tg_hdl_ratio",
    domain=["cardiometabolic", "blood"],
    inputs=["lab:triglycerides", "lab:hdl"],
    output="derived:tg_hdl_ratio",
    priority="high",
    auto_safe=True,
    revision="1",
)
def compute_tg_hdl_ratio(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return _ratio_rows(
        conn,
        numerator_metric="lab:triglycerides",
        denominator_metric="lab:hdl",
        output_metric="derived:tg_hdl_ratio",
        unit="ratio",
    )


def _ratio_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    numerator_metric: str,
    denominator_metric: str,
    output_metric: str,
    unit: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            numerator.ts_utc,
            numerator.local_tz,
            numerator.source_id,
            numerator.source_uuid AS numerator_source_uuid,
            denominator.source_uuid AS denominator_source_uuid,
            numerator.value_num / denominator.value_num AS ratio_value
        FROM hp.fact_measurement AS numerator
        JOIN hp.fact_measurement AS denominator
            ON numerator.source_id = denominator.source_id
           AND numerator.ts_utc = denominator.ts_utc
        WHERE numerator.metric_id = ?
          AND denominator.metric_id = ?
          AND numerator.value_num IS NOT NULL
          AND denominator.value_num IS NOT NULL
          AND denominator.value_num <> 0
        ORDER BY numerator.ts_utc, numerator.source_id
        """,
        [numerator_metric, denominator_metric],
    ).fetchall()
    return [
        _derived_row(
            output_metric=output_metric,
            ts_utc=row[0],
            local_tz=row[1],
            source_id=row[2],
            numerator_metric=numerator_metric,
            denominator_metric=denominator_metric,
            numerator_source_uuid=row[3],
            denominator_source_uuid=row[4],
            value_num=float(row[5]),
            unit=unit,
        )
        for row in rows
    ]


def _derived_row(
    *,
    output_metric: str,
    ts_utc: datetime,
    local_tz: str | None,
    source_id: str,
    numerator_metric: str,
    denominator_metric: str,
    numerator_source_uuid: str | None,
    denominator_source_uuid: str | None,
    value_num: float,
    unit: str,
) -> dict[str, Any]:
    key = f"{output_metric}:{source_id}:{ts_utc.isoformat(sep=' ')}"
    return {
        "ts_utc": ts_utc,
        "local_tz": local_tz,
        "source_id": source_id,
        "source_uuid": key,
        "dedupe_key": key,
        "value_num": value_num,
        "value_text": None,
        "unit": unit,
        "raw_payload": json.dumps(
            {
                "kind": "derived_ratio",
                "numerator_metric": numerator_metric,
                "denominator_metric": denominator_metric,
                "numerator_source_uuid": numerator_source_uuid,
                "denominator_source_uuid": denominator_source_uuid,
                "revision": "1",
            }
        ),
    }


__all__ = [
    "compute_ast_alt_ratio",
    "compute_ldl_hdl_ratio",
    "compute_tg_hdl_ratio",
]
