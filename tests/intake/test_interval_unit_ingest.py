"""End-to-end interval-unit population through a real parser (m7 WP3, E3.3).

E3.3 demands the canonical-unit invariant be proven end-to-end through a parser
fixture, not just a unit test on the loader: after a real ingest, every
fact_interval row whose metric exists in dim_metric must carry
unit = canonical_unit, sourced from the registry rather than the parser.

The SAA parser emits a ``sleep_session`` interval from a synthetic CSV (no PHI),
which makes it the cheapest real interval-producing path to drive here.
"""

from __future__ import annotations

from pathlib import Path

from premura.parsers.sleep_as_android import SleepAsAndroidParser
from premura.store import duck
from premura.store.loader import load


def _write_saa_fixture(tmp_path: Path) -> Path:
    csv = (
        "Id,Tz,From,To,Sched,Hours,Rating,Comment,Framerate,Snore,Noise,Cycles,"
        "DeepSleep,LenAdjust,Geo,23:00,23:01\n"
        "1700000000000,Europe/Berlin,21. 03. 2024 23:00,22. 03. 2024 06:00,"
        ",7.0,3.5,sample,60.0,0,0,4,0.42,0,,1.2,0.9\n"
    )
    p = tmp_path / "saa.csv"
    p.write_text(csv, encoding="utf-8")
    return p


def test_ingested_interval_carries_canonical_unit(tmp_path: Path) -> None:
    fixture = _write_saa_fixture(tmp_path)
    db = tmp_path / "wh.duckdb"
    conn = duck.initialize(db)
    try:
        batch = SleepAsAndroidParser().parse(fixture)
        batch.attach_source_artifact(fixture)
        load(conn, batch)

        rows = conn.execute(
            """
            SELECT fi.unit, dm.canonical_unit
            FROM hp.fact_interval fi
            JOIN hp.dim_metric dm ON dm.metric_id = fi.metric_id
            """
        ).fetchall()
        assert rows, "expected at least one ingested interval row"
        # Single source of unit truth: every row's unit equals its metric's
        # canonical_unit, regardless of what the parser carried in memory.
        for got_unit, canonical_unit in rows:
            assert got_unit == canonical_unit

        # And concretely: sleep_session canonical_unit is 'enum'.
        sleep = conn.execute(
            "SELECT unit FROM hp.fact_interval WHERE metric_id = 'sleep_session'"
        ).fetchone()
        assert sleep is not None
        assert sleep[0] == "enum"
    finally:
        conn.close()
