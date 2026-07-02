"""Materialize the local-only Withings fixture zip for manual CLI runs.

Not committed: ``*.zip`` is gitignored repo-wide and
``ops/check_no_tracked_data.sh`` documents that synthetic fixtures stay
text-format (see ``csv_content.py``'s docstring). Run once with
``uv run python tests/fixtures/parsers/withings/build_fixture.py`` to produce
``withings_export_synthetic.zip`` alongside this script, then point the
issue #33 acceptance commands (``hpipe ingest --source withings <path>`` /
``hpipe inspect <path>``) at that output. The parser's own pytest suite never
depends on this file existing -- it builds the same content in ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from csv_content import write_zip

if __name__ == "__main__":
    out = Path(__file__).parent / "withings_export_synthetic.zip"
    write_zip(out)
    print(f"wrote {out}")
