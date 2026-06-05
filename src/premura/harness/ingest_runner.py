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


class _StagedError(Exception):
    """An intake-stage failure tagged with which stage broke.

    The runner *witnesses* the operator's intake batch through three stages —
    ``parse`` / ``validate`` / ``persist`` — so a failure tells the grader which
    stage broke. The tag rides in the existing envelope ``error`` object's
    ``message`` as a ``"<stage>: <detail>"`` string, so the frozen
    ``ingest-outcome-envelope.schema.json`` (``additionalProperties:false``) is
    unchanged — no new top-level key. The intake runtime checker
    (:func:`premura.harness.intake_contract_check.check_intake_runtime_contract`)
    reads ``status`` + this stage tag as its evidence.
    """

    def __init__(self, stage: str, cause: BaseException) -> None:
        self.stage = stage
        self.cause = cause
        super().__init__(f"{stage}: {cause}")


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
    from premura.parsers.base import normalize_parse_output
    from premura.store import duck, loader
    from premura.store.profile_intake import persist_intake_batch

    parser_kind = ""
    try:
        parser_kind, parser = _load_parser(parser_spec)
        envelope["parser_kind"] = parser_kind

        # A parser may return a bare IngestBatch (observation-only, today's
        # parsers) or a ParseOutput carrying observation and/or intake; the
        # single dispatch helper routes each to its seam (FR-007).
        #
        # parse stage — a raise here (parser.parse or normalize dispatch) is the
        # `parse:` intake stage; tag it so the grader knows the shape was wrong.
        try:
            observation, intake = normalize_parse_output(parser.parse(source))
        except Exception as exc:  # noqa: BLE001 - witnessing the parse stage
            raise _StagedError("parse", exc) from exc

        conn = duck.initialize(warehouse)
        try:
            if intake is not None:
                # The runner WITNESSES intake through its own stages so the intake
                # runtime checker has real evidence (it is harness code grading the
                # operator's batch, never a parser self-report). validate() is
                # called explicitly — today the runner persisted without it, so
                # `batch_validates` was unwitnessed.
                try:
                    intake.validate()
                except Exception as exc:  # noqa: BLE001 - witnessing the validate stage
                    raise _StagedError("validate", exc) from exc
                try:
                    # Intake never travels the observation loader; it persists
                    # through its own home, exactly as the CLI/harness do.
                    persist_intake_batch(conn, intake)
                except Exception as exc:  # noqa: BLE001 - witnessing the persist stage
                    raise _StagedError("persist", exc) from exc

            if observation is not None:
                # The runner owns the warehouse provenance fields; attach if the
                # parser has not already done so.
                if observation.source_path is None:
                    observation.attach_source_artifact(source)
                stats = loader.load(conn, observation)
        finally:
            conn.close()

        # The outcome envelope is observation-shaped (its schema is owned by the
        # session-log substrate). An intake-only parser produces no observation
        # rows, so the envelope reports an empty observation outcome while the
        # intake rows still land via persist_intake_batch above.
        if observation is not None:
            envelope.update(
                status="ok",
                error=None,
                batch_id=stats.batch_id,
                load_stats={
                    "rows_inserted": stats.rows_inserted,
                    "rows_skipped_dup": stats.rows_skipped_dup,
                    "rows_skipped_priority": stats.rows_skipped_priority,
                },
                declared_metrics=list(observation.declared_metrics),
                emitted_metric_ids=sorted(observation.emitted_metrics),
                unmapped_metrics=list(observation.unmapped_metrics),
                skipped_rows=_skipped_rows_payload(observation),
            )
        else:
            envelope.update(
                status="ok",
                error=None,
                unmapped_metrics=list(intake.unmapped_metrics) if intake else [],
                skipped_rows=_skipped_rows_payload(intake) if intake else [],
            )
        return envelope
    except _StagedError as exc:
        # A witnessed intake stage failed. The error message carries the stage
        # tag (`parse:`/`validate:`/`persist:`); the checker reads it as evidence.
        # `kind` reports the underlying exception type for human triage.
        envelope.update(
            status="error",
            parser_kind=parser_kind,
            error={"kind": type(exc.cause).__name__, "message": str(exc)},
        )
        envelope["declared_metrics"] = []
        envelope["emitted_metric_ids"] = []
        envelope["unmapped_metrics"] = []
        envelope["skipped_rows"] = []
        envelope["batch_id"] = None
        envelope["load_stats"] = None
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
