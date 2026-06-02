"""In-sandbox ingest runner: one parser-build ingest → JSON outcome envelope.

Runnable as ``python -m premura.harness.ingest_runner`` **inside a sandbox** (the
parent harness invokes it as a subprocess with ``cwd=sandbox.root`` and the
sandbox's ``src`` on ``PYTHONPATH``). It imports the sandbox copy of ``premura``,
runs ONE named parser over a source artifact through the real ingest/load seam,
and prints a structured JSON envelope on stdout.

Contract: the stdout JSON conforms EXACTLY to
``contracts/ingest-outcome-envelope.schema.json`` (``additionalProperties:false``)
— raw measured evidence, no verdict.

**Single-writer rule (FR-021):** this runner NEVER opens or writes the session
log. It only *returns* its outcome via stdout; the parent harness (WP06/WP07) is
the sole session-log writer. Nothing in this module imports the session-log
store.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

# Top-level keys allowed by ingest-outcome-envelope.schema.json. Kept here so the
# error path (which must not import the heavy seam) can still build a conforming
# envelope.
_EMPTY_ENVELOPE: dict[str, Any] = {
    "status": "error",
    "error": None,
    "parser_kind": "",
    "batch_id": None,
    "load_stats": None,
    "declared_metrics": [],
    "emitted_metric_ids": [],
    "unmapped_metrics": [],
    "skipped_rows": [],
}


def _load_parser(spec: str) -> tuple[str, Any]:
    """Import ``module.path:ClassOrFactory`` and instantiate it.

    Returns ``(parser_kind, parser_instance)`` where ``parser_kind`` is the
    attribute name (the human-facing "which parser ran" label).
    """
    if ":" not in spec:
        raise ValueError(f"--parser must be 'module.path:Attr', got {spec!r}")
    module_path, attr = spec.split(":", 1)
    module = importlib.import_module(module_path)
    target = getattr(module, attr)
    instance = target() if callable(target) else target
    return attr, instance


def _skipped_rows_payload(batch: Any) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for row in getattr(batch, "skipped_rows", []):
        if is_dataclass(row) and not isinstance(row, type):
            payload.append(asdict(row))
        elif isinstance(row, dict):
            payload.append(row)
        else:  # pragma: no cover - defensive
            payload.append({"reason": str(row)})
    return payload


def run(*, source: Path, parser_spec: str, warehouse: Path) -> dict[str, Any]:
    """Run one ingest and return the outcome envelope dict (no log writing)."""
    envelope = dict(_EMPTY_ENVELOPE)

    # Import the seam lazily so an import error surfaces as a structured error
    # envelope rather than a bare traceback.
    from premura.store import duck, loader

    parser_kind = ""
    try:
        parser_kind, parser = _load_parser(parser_spec)
        envelope["parser_kind"] = parser_kind

        batch = parser.parse(source)
        # The runner owns the warehouse provenance fields; attach if the parser
        # has not already done so.
        if getattr(batch, "source_path", None) is None:
            batch.attach_source_artifact(source)

        conn = duck.initialize(warehouse)
        try:
            stats = loader.load(conn, batch)
        finally:
            conn.close()

        envelope.update(
            status="ok",
            error=None,
            batch_id=stats.batch_id,
            load_stats={
                "rows_inserted": stats.rows_inserted,
                "rows_skipped_dup": stats.rows_skipped_dup,
                "rows_skipped_priority": stats.rows_skipped_priority,
            },
            declared_metrics=list(batch.declared_metrics),
            emitted_metric_ids=sorted(batch.emitted_metrics),
            unmapped_metrics=list(batch.unmapped_metrics),
            skipped_rows=_skipped_rows_payload(batch),
        )
        return envelope
    except Exception as exc:  # noqa: BLE001 - the runner's job is to capture any raise
        envelope.update(
            status="error",
            parser_kind=parser_kind,
            error={"kind": type(exc).__name__, "message": str(exc)},
        )
        # required array fields stay present and empty (schema required list)
        envelope["declared_metrics"] = []
        envelope["emitted_metric_ids"] = []
        envelope["unmapped_metrics"] = []
        envelope["skipped_rows"] = []
        envelope["batch_id"] = None
        envelope["load_stats"] = None
        return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="premura.harness.ingest_runner",
        description="Run one parser-build ingest inside a sandbox; emit a JSON envelope.",
    )
    parser.add_argument("--source", required=True, type=Path, help="Source artifact to parse.")
    parser.add_argument(
        "--parser",
        required=True,
        help="Parser import spec, 'module.path:ClassOrFactory'.",
    )
    parser.add_argument(
        "--warehouse",
        required=True,
        type=Path,
        help="Sandbox warehouse DuckDB path (created on use).",
    )
    args = parser.parse_args(argv)

    envelope = run(source=args.source, parser_spec=args.parser, warehouse=args.warehouse)
    # stdout carries ONLY the envelope (the parent parses it).
    sys.stdout.write(json.dumps(envelope))
    sys.stdout.flush()
    return 0 if envelope["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
