"""Always-on deterministic check: the fake-scripted-agent end-to-end loop (FR-004/FR-030).

This module wires the whole session-log substrate into one CI-able check. A
**fake scripted agent** (no model — just this orchestrator scripting fixed
actions) runs the parser-build flow for a committed reference parser, the harness
records the named ``tool_call`` log steps it is the **sole** writer of, the
deterministic grader recomputes a verdict, and a re-run yields a byte-identical
verdict. It is the MVP that proves SC-001..SC-006 and the piece that runs in CI
offline from the committed fixture (NFR-001 / NFR-002).

Design boundaries (data-model.md, ``contracts/session-log-writer.md``, WP01..WP05):

* **The harness is the SOLE log writer (FR-021 / NFR-008).** Only this module
  opens the session-log file (via WP01's :mod:`premura.session_log.store`) and
  writes ``log_session`` / ``log_step`` / ``log_ingest_provenance``. The WP03
  subprocess runner returns its outcome on stdout and never touches the log.
* **Named ``tool_call`` steps (FR-004).** The scripted dev-time actions are
  recorded as NAMED ``tool_call`` steps — ``edit_file`` (install parser),
  ``parser_contract_check`` (informational), and ``ingest_run`` (the
  verdict-bearing step whose detail lands in ``log_ingest_provenance``) — under a
  single ``agent_turn`` parent, by the named-tool convention, never as one
  free-text blob.
* **Grader-only ``contract_pass`` (FR-065).** ``record_ingest_provenance`` is
  given the GRADER's recomputed ``runtime_valid`` as ``contract_pass``; it is
  never a parser/runner self-report.
* **Connection discipline.** The session log lives in its OWN file and the parent
  holds the sole writable handle for it. The sandbox warehouse is opened
  **read-only for grading only after** the runner subprocess has closed its
  writable handle (separate files, so handles never contend).
* **Drive-mode seam (FR-030).** The core flow takes the "agent" as a seam: the
  scripted (repeatable) path here installs a committed reference parser; the live
  trial (WP07) reuses :func:`run_repeatable_check` with an operator-edit agent.
  No model is wired here.

The whole loop tears the sandbox down afterward (NFR-004); the verdict carries no
ids/timestamps, so two runs serialize byte-identically (NFR-001).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

from premura.harness import open_sandbox_warehouse_for_grading
from premura.harness.grader import grade
from premura.harness.sandbox import Sandbox, build_sandbox, install_parser
from premura.session_log import store

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

# Committed slice-one fixture inputs (NFR-002: the check reads ONLY these + the
# repo, never a private dump and never the network).
_FIXTURE_DIR = Path("tests") / "fixtures" / "session_log"
_SYNTHETIC_CSV = _FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
_MANIFEST = _FIXTURE_DIR / "fixture_fields.yaml"

# Where the scripted agent installs the reference parser inside the sandbox tree.
_PARSER_DEST_RELPATH = "src/premura/parsers/_repeatable_check_parser.py"
_PARSER_MODULE = "premura.parsers._repeatable_check_parser"


@dataclass(slots=True)
class _CapturedProvenance:
    """Captured ingest evidence assembled from the runner envelope.

    Satisfies :class:`premura.harness.grader.IngestProvenance` structurally so the
    grader reconciles these CAPTURED sets/claims without trusting a self-report.
    """

    declared_metrics: Sequence[str]
    emitted_metric_ids: Sequence[str]
    unmapped_metrics: Sequence[str]
    skipped_rows: Sequence[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool


@dataclass(slots=True)
class _LoadStats:
    """The three loader-measured ints :func:`store.record_ingest_provenance` reads."""

    rows_inserted: int
    rows_skipped_dup: int
    rows_skipped_priority: int


@dataclass(slots=True)
class RepeatableCheckResult:
    """The outcome of one full repeatable check.

    ``verdict`` is the grader's recomputed verdict (the public artifact, no
    ids/timestamps — byte-identical across runs). ``envelope`` is the raw runner
    outcome (debug only). ``session_log_path`` is the (already torn-down by
    default) sandbox log path; when ``keep_sandbox=True`` is requested for
    inspection, it points at a still-present file.
    """

    verdict: dict[str, Any]
    envelope: dict[str, Any]
    session_id: str
    session_log_path: Path


def _load_manifest(repo_root: Path) -> dict[str, Any]:
    """Parse the committed honesty ground-truth manifest (D6)."""
    return yaml.safe_load((repo_root / _MANIFEST).read_text(encoding="utf-8"))


def _run_ingest_subprocess(
    sandbox: Sandbox,
    *,
    source: Path,
    parser_spec: str,
) -> dict[str, Any]:
    """Invoke the WP03 ingest runner as a subprocess; return its JSON envelope.

    The subprocess is rooted in the sandbox with the sandbox's own ``src`` on
    ``PYTHONPATH`` so it imports the sandbox copy of ``premura`` and the installed
    reference parser, getting its OWN DuckDB handles. It writes the warehouse but
    NEVER the session log (FR-021). The environment is the minimal PATH/HOME — no
    network client is configured or invoked (NFR-002).
    """
    env = {
        "PYTHONPATH": str(sandbox.root / "src"),
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "premura.harness.ingest_runner",
            "--source",
            str(source),
            "--parser",
            parser_spec,
            "--warehouse",
            str(sandbox.warehouse_path),
        ],
        cwd=sandbox.root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if not proc.stdout:
        raise RuntimeError(f"ingest runner produced no envelope; stderr={proc.stderr}")
    envelope: dict[str, Any] = json.loads(proc.stdout)
    return envelope


def _captured_provenance(envelope: dict[str, Any]) -> _CapturedProvenance:
    """Assemble captured provenance from the runner envelope (transport only)."""
    load_stats = envelope.get("load_stats") or {}
    return _CapturedProvenance(
        declared_metrics=list(envelope["declared_metrics"]),
        emitted_metric_ids=list(envelope["emitted_metric_ids"]),
        unmapped_metrics=list(envelope["unmapped_metrics"]),
        skipped_rows=list(envelope["skipped_rows"]),
        rows_inserted=int(load_stats.get("rows_inserted", 0)),
        ingest_run_ok=envelope["status"] == "ok",
    )


def run_repeatable_check(
    repo_root: Path,
    *,
    parser_src: Path,
    parser_attr: str,
    keep_sandbox: bool = False,
) -> RepeatableCheckResult:
    """Run the full fake-scripted-agent loop end-to-end and return the verdict.

    The flow, in order (T022):

    1. :func:`build_sandbox` (WP03); open the sandbox session-log file with WP01's
       :func:`store.connect` + :func:`store.init_schema`. The parent holds the
       **sole** writable log handle.
    2. :func:`store.open_session` with the fake-scripted sentinels and
       ``run_kind="repeatable_check"``.
    3. Record an ``agent_turn`` parent, then under it the named ``tool_call``
       steps (FR-004): ``edit_file`` (install the reference parser),
       ``parser_contract_check`` (informational), and ``ingest_run`` (the runner
       subprocess; its ``result_status`` comes from the envelope).
    4. Persist provenance from the envelope; ``contract_pass`` is filled from the
       GRADER's recomputed ``runtime_valid`` (FR-065), never a self-report.
    5. Grade against the sandbox warehouse (opened read-only AFTER the runner
       closed its writable handle) + the committed manifest (WP05).
    6. :func:`store.finish_session`; tear the sandbox down (unless ``keep_sandbox``
       is requested for log inspection); return the verdict.

    The "agent" is the scripted install of ``parser_src`` — the seam the live
    trial (WP07) reuses with an operator-edit agent over the SAME machinery
    (FR-030). No model is invoked, so the flow is identical every run.

    Args:
        repo_root: the clean clone to sandbox (NFR-002: only the repo + committed
            fixtures are read; no private dump, no network).
        parser_src: a committed reference parser module to install.
        parser_attr: the parser class/factory attribute name in that module.
        keep_sandbox: when True, skip teardown so a test can inspect the recorded
            log; default False (production tears the sandbox down — NFR-004).

    Returns:
        A :class:`RepeatableCheckResult` carrying the grader verdict (no
        ids/timestamps — byte-identical across runs).
    """
    repo_root = repo_root.resolve()
    manifest = _load_manifest(repo_root)
    source = repo_root / _SYNTHETIC_CSV

    sandbox = build_sandbox(repo_root)
    log_conn: duckdb.DuckDBPyConnection | None = None
    try:
        # (1) The parent opens the SOLE writable session-log handle (its own file).
        log_conn = store.connect(sandbox.session_log_path)
        store.init_schema(log_conn)

        # (2) Open the session for the fake scripted agent.
        session_id = store.open_session(
            log_conn,
            operator_model="fake-scripted",
            driver_model="fake-scripted",
            premura_version=sandbox.premura_version,
            isolation_tag=sandbox.isolation_tag,
            run_kind="repeatable_check",
        )

        # (3) One agent_turn parent; the scripted dev-time actions hang under it as
        #     NAMED tool_call steps (FR-004), never a single free-text blob.
        turn_id = store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=None,
            kind="agent_turn",
            name="parser_build",
            tool_name=None,
            request_summary="fake-scripted parser-build turn",
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )

        # tool_call: edit_file — the scripted agent installs the reference parser.
        install_parser(sandbox, parser_src, _PARSER_DEST_RELPATH)
        store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=turn_id,
            kind="tool_call",
            name="install reference parser",
            tool_name="edit_file",
            request_summary=f"install {parser_src.name} -> {_PARSER_DEST_RELPATH}",
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )

        # tool_call: parser_contract_check — informational record. The GRADER is
        # what the verdict trusts (FR-061); this step is only the dev-time note.
        store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=turn_id,
            kind="tool_call",
            name="runtime contract check",
            tool_name="parser_contract_check",
            request_summary="informational; grader recomputes the trusted result",
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )

        # tool_call: ingest_run — the verdict-bearing step. The subprocess runner
        # returns its envelope on stdout; the harness records it (single-writer).
        envelope = _run_ingest_subprocess(
            sandbox,
            source=source,
            parser_spec=f"{_PARSER_MODULE}:{parser_attr}",
        )
        ingest_ok = envelope["status"] == "ok"
        ingest_step_id = store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=turn_id,
            kind="tool_call",
            name="parser-build ingest",
            tool_name="ingest_run",
            request_summary=f"ingest via {parser_attr} over {source.name}",
            request_hash=None,
            result_status="available" if ingest_ok else "error",
            result_summary=None,
            result_hash=None,
        )

        provenance = _captured_provenance(envelope)

        # (5) Grade: open the sandbox WAREHOUSE read-only ONLY NOW — the runner
        #     subprocess has already closed its writable warehouse handle, so the
        #     read never contends (separate file from the log handle anyway). On the
        #     failure path the parser raised before any warehouse file was created;
        #     the helper materializes an EMPTY (0-fact-row) warehouse so grading still
        #     yields a deterministic FAIL instead of crashing the run (FR-080).
        warehouse_conn = open_sandbox_warehouse_for_grading(sandbox.warehouse_path)
        try:
            verdict = grade(
                provenance=provenance,
                warehouse_conn=warehouse_conn,
                fixture_manifest=manifest,
            )
        finally:
            warehouse_conn.close()

        # (4) Persist provenance — contract_pass is the GRADER's recomputed
        #     runtime_valid, the only producer of that value (FR-065).
        store.record_ingest_provenance(
            log_conn,
            step_id=ingest_step_id,
            batch_id=envelope.get("batch_id") or "",
            parser_kind=envelope.get("parser_kind") or parser_attr,
            load_stats=_LoadStats(
                rows_inserted=provenance.rows_inserted,
                rows_skipped_dup=int((envelope.get("load_stats") or {}).get("rows_skipped_dup", 0)),
                rows_skipped_priority=int(
                    (envelope.get("load_stats") or {}).get("rows_skipped_priority", 0)
                ),
            ),
            declared_metrics=provenance.declared_metrics,
            emitted_metric_ids=provenance.emitted_metric_ids,
            unmapped_metrics=provenance.unmapped_metrics,
            skipped_rows=provenance.skipped_rows,
            contract_pass=bool(verdict["rules"]["runtime_valid"]["passed"]),
        )

        # (6) Finish the session.
        store.finish_session(log_conn, session_id=session_id)

        return RepeatableCheckResult(
            verdict=verdict,
            envelope=envelope,
            session_id=session_id,
            session_log_path=sandbox.session_log_path,
        )
    finally:
        if log_conn is not None:
            log_conn.close()
        if not keep_sandbox:
            sandbox.teardown()


# --------------------------------------------------------------------------- #
# Thin good/dishonest entry points (T023): scripted-install both reference
# parsers over the SAME machinery. Sources resolve under the repo's committed
# fixtures, so the check stays offline (NFR-002).
# --------------------------------------------------------------------------- #


def _reference_parser(repo_root: Path, filename: str) -> Path:
    return repo_root / _FIXTURE_DIR / "parsers" / filename


def run_good(repo_root: Path, *, keep_sandbox: bool = False) -> RepeatableCheckResult:
    """Run the repeatable check with the HONEST reference parser (expect PASS)."""
    return run_repeatable_check(
        repo_root,
        parser_src=_reference_parser(repo_root, "good_fitbit_hr.py"),
        parser_attr="GoodFitbitHrParser",
        keep_sandbox=keep_sandbox,
    )


def run_dishonest(repo_root: Path, *, keep_sandbox: bool = False) -> RepeatableCheckResult:
    """Run the repeatable check with the DISHONEST reference parser (expect FAIL)."""
    return run_repeatable_check(
        repo_root,
        parser_src=_reference_parser(repo_root, "dishonest_fitbit_hr.py"),
        parser_attr="DishonestFitbitHrParser",
        keep_sandbox=keep_sandbox,
    )


__all__ = [
    "RepeatableCheckResult",
    "run_dishonest",
    "run_good",
    "run_repeatable_check",
]
