"""Live-trial seam — scaffold; real-model wiring deferred (FR-030 / FR-031).

This module lays the **live-trial seam** so a real, deliberately-cheap operator
model can be wired in later WITHOUT reshaping any of the machinery the repeatable
check already proves. The live trial reuses the EXACT same lower layers as the
repeatable check — the WP03 sandbox + ingest runner, the WP01 session-log store
(the harness is still the sole log writer), and the WP05 grader — and differs in
exactly one place: an :class:`Operator` *edits the already-built sandbox tree* to
make the dropped data ingestable (it writes a parser), instead of a scripted
install of a committed reference parser.

The two roles, per ``contracts/live-trial-seam.md`` + spec.md (Operator AI /
Driver AI):

* :class:`Operator` — in a live trial the *deliberately cheap, low-capability* AI
  that edits the sandbox to build a working parser. ``operate(sandbox, goal)``.
* :class:`Driver` — the AI that plays the human: supplies the goal and answers
  the operator's questions.

Design boundaries (mirrors WP06 :mod:`premura.harness.repeatable_check`):

* **The harness is the SOLE log writer (FR-021 / NFR-008).** Only this module
  opens the sandbox session-log file and writes ``open_session`` / ``record_step``
  / ``record_ingest_provenance``. The :class:`Operator` edits the sandbox *tree*;
  it never touches the log. The WP03 subprocess runner writes the warehouse and
  returns its outcome on stdout, never the log.
* **Grader-only ``contract_pass`` (FR-065).** The persisted ``contract_pass`` is
  the GRADER's recomputed ``runtime_valid``, never an operator/runner self-report.
* **Distinct ``run_kind`` (FR-031/FR-032).** The session records
  ``run_kind="live_trial"`` (distinct from ``"repeatable_check"``) plus
  ``operator_model`` / ``driver_model`` so capability tiers can be compared later.
* **Lower layers, not WP06's orchestrator.** To respect file ownership this module
  calls the sandbox / runner / store / grader layers directly; it does NOT import
  :mod:`premura.harness.repeatable_check`. The seam is the shared lower machinery,
  not a shared orchestrator file.

== Named follow-up: real-model wiring is DEFERRED (D4 / R5 / SC-005) ==============

The concrete cheap-model :class:`Operator` and :class:`Driver` are a **named
follow-up**, NOT a silent waiver (DIRECTIVE_010). This slice ships the seam and
proves it end-to-end with a deterministic FAKE operator
(:class:`ReferenceParserOperator`, an outside-boundary substitute permitted by
DIRECTIVE_036) over the SYNTHETIC fixture. No real model is invoked by this
module's committed default suite. That follow-up was CLOSED in WP04 (FR-013): the
two explicitly-named factories below — :func:`real_model_operator` and
:func:`real_model_driver` — now DELEGATE to the WP03 cheap-model operator/driver
when handed the arguments to build one. A BARE no-argument call still raises a
:class:`NotImplementedError` that points back at this follow-up (there is nothing
to delegate to without a data source). SC-005 is refined accordingly: the seam is
exercised by a fake operator in the default suite; model-driven execution against
the real dump is the local follow-up (recorded in plan.md Risks R5).

== NFR-005: the live trial is wired into NO CI gate and can NEVER block ===========

:func:`run_live_trial` is invoked by NO default-collected test against the real
``source_dir`` and is referenced by NO CI / pytest default marker. The committed
seam test exercises it only against the SYNTHETIC fixture via the fake operator;
any real-dump exercise is the local follow-up and is never part of the default
suite. A failing or absent live trial therefore cannot block a code change.

== C-003 / NFR-004: PHI containment ==============================================

``LiveTrialConfig.source_dir`` (default ``~/Downloads/MyFitbitData``) is a
LOCAL-only, never-committed target. Nothing under it is ever copied into the repo
or a commit. The sandbox is torn down after every run (NFR-004). No committed test
reads the real dump.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from premura.harness import open_sandbox_warehouse_for_grading
from premura.harness.grader import grade
from premura.harness.sandbox import Sandbox, build_sandbox, install_parser
from premura.session_log import store

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

# Same committed slice-one fixture inputs the repeatable check reads (NFR-002): the
# seam test drives the live trial over the SYNTHETIC csv + manifest, never the real
# dump (C-003). These resolve under the sandboxed repo copy at grade time.
_FIXTURE_DIR = Path("tests") / "fixtures" / "session_log"
_SYNTHETIC_CSV = _FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
_MANIFEST = _FIXTURE_DIR / "fixture_fields.yaml"

# Where an operator's parser lands inside the sandbox tree (the import path the
# in-sandbox runner resolves it by).
_PARSER_DEST_RELPATH = "src/premura/parsers/_live_trial_parser.py"
_PARSER_MODULE = "premura.parsers._live_trial_parser"

# A live-trial verdict is the SAME plain-dict grader verdict the repeatable check
# returns (``contracts/grader-verdict.schema.json``): no ids, no timestamps.
Verdict = dict[str, Any]


@runtime_checkable
class Operator(Protocol):
    """The cheap operator AI: edits the sandbox tree to make the data ingestable.

    Mirrors ``contracts/live-trial-seam.md``. ``operate`` is handed the
    ALREADY-BUILT sandbox and the goal; it writes a parser (and, where needed,
    appends ``dim_metric`` rows) INSIDE the sandbox so the subsequent ingest run
    can load the dropped data. It never touches the session log — the harness is
    the sole writer. The deferred real operator drives a cheap model plus the
    parser-generator skill; the committed test uses :class:`ReferenceParserOperator`.
    """

    model_id: str

    def operate(self, sandbox: Sandbox, goal: str) -> None:
        """Edit ``sandbox``'s tree to make the dropped data ingestable."""
        ...


@runtime_checkable
class Driver(Protocol):
    """The driver AI that plays the human: supplies the goal, answers questions.

    Mirrors ``contracts/live-trial-seam.md``. In the deferred real trial the
    driver wraps a model; the committed seam test uses :class:`ScriptedDriver`.
    """

    model_id: str

    def goal(self) -> str:
        """Return the operator's goal (e.g. 'ingest the heart-rate category')."""
        ...

    def respond(self, question: str) -> str:
        """Answer one operator question during the trial."""
        ...


@dataclass(slots=True)
class LiveTrialConfig:
    """Points the live trial at the LOCAL Fitbit dump (live-trial only, C-003).

    ``source_dir`` defaults to ``~/Downloads/MyFitbitData`` — a local-only,
    never-committed target. ``category`` scopes the trial to one data category
    (slice-one: ``heart_rate``). ``run_kind`` is the distinct ``"live_trial"``
    session kind (FR-031/FR-032). For the committed seam test the source is
    overridden to the synthetic fixture; nothing under the real ``source_dir`` is
    ever read by a committed test.
    """

    source_dir: Path = field(default_factory=lambda: Path.home() / "Downloads" / "MyFitbitData")
    category: str = "heart_rate"
    run_kind: str = "live_trial"


# --------------------------------------------------------------------------- #
# Captured-evidence shims (structural matches for the grader / store; identical
# in shape to WP06's, kept local so this module does not import that orchestrator).
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _CapturedProvenance:
    """Captured ingest evidence assembled from the runner envelope (transport only)."""

    declared_metrics: Sequence[str]
    emitted_metric_ids: Sequence[str]
    unmapped_metrics: Sequence[str]
    skipped_rows: Sequence[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool


@dataclass(slots=True)
class _LoadStats:
    """The three loader-measured ints ``store.record_ingest_provenance`` reads."""

    rows_inserted: int
    rows_skipped_dup: int
    rows_skipped_priority: int


# --------------------------------------------------------------------------- #
# Fake operator / driver test doubles (outside-boundary substitutes, DIRECTIVE_036).
# These prove the seam deterministically; they are NOT the real cheap model.
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ReferenceParserOperator:
    """A FAKE operator that installs a committed reference parser into the sandbox.

    Outside-boundary substitute for the deferred real cheap-model operator: instead
    of driving a model to author a parser, it copies a committed reference parser
    module into the sandbox tree — exactly the edit the real operator would make,
    so the seam is exercised identically. Used only by the committed seam test over
    the synthetic fixture (never the real dump).

    ``model_id`` is a sentinel (e.g. ``"fake-operator:reference-parser"``) recorded
    as the session ``operator_model`` (FR-031).
    """

    parser_src: Path
    model_id: str = "fake-operator:reference-parser"

    def operate(self, sandbox: Sandbox, goal: str) -> None:  # noqa: ARG002 - goal unused by the fake
        """Install the committed reference parser into the sandbox (models the edit)."""
        install_parser(sandbox, self.parser_src, _PARSER_DEST_RELPATH)


@dataclass(slots=True)
class ScriptedDriver:
    """A FAKE driver that returns a fixed goal and canned answers (test double).

    Outside-boundary substitute for the deferred real cheap-model driver; records a
    sentinel ``model_id`` as the session ``driver_model`` (FR-031).
    """

    trial_goal: str = "ingest the heart-rate category from the dropped dump"
    model_id: str = "fake-driver:scripted"

    def goal(self) -> str:
        return self.trial_goal

    def respond(self, question: str) -> str:  # noqa: ARG002 - canned response
        return "proceed"


# --------------------------------------------------------------------------- #
# Closed follow-up (D4 / R5 / SC-005): the REAL cheap-model operator/driver are now
# WIRED (FR-013) — these factories delegate to the WP03 Ollama operator/driver when
# handed the arguments to build one. A BARE no-argument call still raises
# NotImplementedError pointing at the follow-up, since the real operator must be
# handed a data source (there is nothing to delegate to without one). The import is
# lazy so this slice-one seam has no import cycle with the WP03 module.
# --------------------------------------------------------------------------- #

_DEFERRED_MSG = (
    "Real cheap-model live-trial wiring is a NAMED follow-up (D4 / R5 / SC-005), "
    "deferred from the slice-one substrate — NOT a silent waiver. This slice ships "
    "the seam and proves it with a fake operator over the synthetic fixture; the "
    "real {role} (cheap model + parser-generator skill, run locally against "
    "~/Downloads/MyFitbitData) is the follow-up. See contracts/live-trial-seam.md "
    "and plan.md Risks R5."
)


def real_model_operator(source: Path | None = None, **kwargs: Any) -> Operator:
    """Resolve the D4/R5 follow-up: delegate to the WP03 cheap-model operator.

    The slice-one substrate shipped this as a ``NotImplementedError`` placeholder;
    that follow-up is now CLOSED (FR-013). Given a data ``source``, this builds and
    returns the real cheap-model :class:`Operator` —
    :class:`premura.harness.live_trial_ollama.OllamaOperator` — forwarding
    ``model`` / ``max_tries`` kwargs. The import is LAZY so the slice-one seam has
    no import cycle with the WP03 module (which imports this one).

    Calling it with NO ``source`` is the bare named-follow-up probe: there is no
    data to build a parser against, so it still raises a ``NotImplementedError``
    pointing back at the follow-up (the real operator MUST be handed a source).
    """
    if source is None:
        raise NotImplementedError(_DEFERRED_MSG.format(role="Operator"))
    from premura.harness.live_trial_ollama import OllamaOperator

    return OllamaOperator(source, **kwargs)


def real_model_driver(**kwargs: Any) -> Driver:
    """Resolve the D4/R5 follow-up: delegate to the WP03 cheap-model driver.

    The slice-one substrate shipped this as a ``NotImplementedError`` placeholder;
    that follow-up is now CLOSED (FR-013). It builds and returns the real
    cheap-model :class:`Driver` —
    :class:`premura.harness.live_trial_ollama.OllamaDriver` — forwarding the
    ``model`` kwarg. The import is LAZY to avoid an import cycle.

    Calling it with NO model kwargs is the bare named-follow-up probe and still
    raises a ``NotImplementedError`` pointing back at the follow-up.
    """
    if not kwargs:
        raise NotImplementedError(_DEFERRED_MSG.format(role="Driver"))
    from premura.harness.live_trial_ollama import OllamaDriver

    return OllamaDriver(**kwargs)


# --------------------------------------------------------------------------- #
# The seam: run_live_trial — same machinery as the repeatable check, but an
# Operator edits the sandbox instead of a scripted install.
# --------------------------------------------------------------------------- #


def _run_ingest_subprocess(
    sandbox: Sandbox,
    *,
    source: Path,
    parser_spec: str,
) -> dict[str, Any]:
    """Invoke the WP03 ingest runner as a subprocess; return its JSON envelope.

    Identical transport to the repeatable check: the runner is rooted in the
    sandbox with the sandbox ``src`` on ``PYTHONPATH`` so it imports the sandbox
    copy of ``premura`` and the operator's installed parser, gets its OWN DuckDB
    handles, writes the warehouse, and never touches the session log (FR-021). The
    minimal env configures no network client (NFR-002).
    """
    import json
    import os
    import subprocess
    import sys

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


def _load_manifest(repo_root: Path) -> dict[str, Any]:
    import yaml  # type: ignore[import-untyped]

    return yaml.safe_load((repo_root / _MANIFEST).read_text(encoding="utf-8"))


@dataclass(slots=True)
class LiveTrialResult:
    """Verdict + session identity + the (kept) sandbox log path, for inspection."""

    verdict: Verdict
    session_id: str
    session_log_path: Path


def _drive_live_trial(
    config: LiveTrialConfig,
    *,
    driver: Driver,
    operator: Operator,
    repo_root: Path,
    parser_attr: str,
    source: Path | None,
    keep_sandbox: bool,
) -> LiveTrialResult:
    """Core seam flow: same machinery as the repeatable check, operator-edited.

    The flow, in order — the ONLY difference from the repeatable check is the
    :class:`Operator` editing the sandbox in place of a scripted install:

    1. :func:`build_sandbox` (WP03); open the sandbox session-log file (WP01). The
       parent holds the SOLE writable log handle (FR-021).
    2. :func:`store.open_session` with ``operator_model=operator.model_id``,
       ``driver_model=driver.model_id``, and ``run_kind=config.run_kind``
       (``"live_trial"`` — distinct from the repeatable check) so capability tiers
       compare later (FR-031/FR-032).
    3. Record an ``agent_turn`` parent (carrying the driver's goal as a PHI-safe
       summary), then ``operator.operate(sandbox, goal)`` recorded as the
       ``edit_file`` ``tool_call`` step — the operator EDITS the sandbox; the
       harness writes the log.
    4. Run the WP03 subprocess runner over ``source`` (the synthetic fixture for the
       committed seam test; the real dump only in the local follow-up), recorded as
       the verdict-bearing ``ingest_run`` step.
    5. Grade against the sandbox warehouse (opened read-only AFTER the runner closed
       its writable handle) + the committed manifest (WP05). Persist provenance with
       ``contract_pass`` = the GRADER's recomputed ``runtime_valid`` (FR-065).
    6. :func:`store.finish_session`; tear the sandbox down unless ``keep_sandbox``
       (NFR-004); return the result.
    """
    repo_root = repo_root.resolve()
    manifest = _load_manifest(repo_root)
    ingest_source = source if source is not None else (repo_root / _SYNTHETIC_CSV)
    goal = driver.goal()

    sandbox = build_sandbox(repo_root)
    log_conn: duckdb.DuckDBPyConnection | None = None
    try:
        # (1) The parent opens the SOLE writable session-log handle (its own file).
        log_conn = store.connect(sandbox.session_log_path)
        store.init_schema(log_conn)

        # (2) Open the session — distinct run_kind + the two model identities (FR-031).
        session_id = store.open_session(
            log_conn,
            operator_model=operator.model_id,
            driver_model=driver.model_id,
            premura_version=sandbox.premura_version,
            isolation_tag=sandbox.isolation_tag,
            run_kind=config.run_kind,
        )

        # (3) One agent_turn parent carrying the driver's goal; the operator edit
        #     hangs under it as a NAMED edit_file tool_call. The OPERATOR edits the
        #     sandbox tree; the HARNESS writes the log (sole writer).
        turn_id = store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=None,
            kind="agent_turn",
            name="live_trial_turn",
            tool_name=None,
            request_summary=f"live-trial goal: {goal}",
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )

        operator.operate(sandbox, goal)
        store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=turn_id,
            kind="tool_call",
            name="operator edits sandbox",
            tool_name="edit_file",
            request_summary=(
                f"operator {operator.model_id} edits sandbox for category {config.category}"
            ),
            request_hash=None,
            result_status="available",
            result_summary=None,
            result_hash=None,
        )

        # (4) ingest_run — the verdict-bearing step (same runner as the repeatable check).
        envelope = _run_ingest_subprocess(
            sandbox,
            source=ingest_source,
            parser_spec=f"{_PARSER_MODULE}:{parser_attr}",
        )
        ingest_ok = envelope["status"] == "ok"
        ingest_step_id = store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=turn_id,
            kind="tool_call",
            name="live-trial ingest",
            tool_name="ingest_run",
            request_summary=f"ingest via {parser_attr} over {ingest_source.name}",
            request_hash=None,
            result_status="available" if ingest_ok else "error",
            result_summary=None,
            result_hash=None,
        )

        provenance = _captured_provenance(envelope)

        # (5) Grade against the sandbox warehouse (read-only, AFTER the runner closed).
        #     On the failure path the operator's parser raised before any warehouse
        #     file was created; the helper materializes an EMPTY (0-fact-row)
        #     warehouse so grading still yields a deterministic FAIL (FR-080).
        warehouse_conn = open_sandbox_warehouse_for_grading(sandbox.warehouse_path)
        try:
            verdict = grade(
                provenance=provenance,
                warehouse_conn=warehouse_conn,
                fixture_manifest=manifest,
            )
        finally:
            warehouse_conn.close()

        # Persist provenance — contract_pass is the GRADER's runtime_valid (FR-065).
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

        return LiveTrialResult(
            verdict=verdict,
            session_id=session_id,
            session_log_path=sandbox.session_log_path,
        )
    finally:
        if log_conn is not None:
            log_conn.close()
        if not keep_sandbox:
            sandbox.teardown()


def run_live_trial(
    config: LiveTrialConfig,
    *,
    driver: Driver,
    operator: Operator,
    repo_root: Path,
    parser_attr: str,
    source: Path | None = None,
) -> Verdict:
    """Drive one live trial end-to-end and return the grader verdict (FR-030/FR-031).

    Reuses the SAME lower machinery as the repeatable check; the ONLY difference is
    the :class:`Operator` editing the sandbox in place of a scripted install (see
    :func:`_drive_live_trial`). The sandbox is torn down afterward (NFR-004).

    NFR-005: this function is wired into NO default CI gate; only the committed seam
    test calls it, and only over the synthetic fixture.

    Args:
        config: the live-trial config (its ``run_kind`` is recorded on the session).
        driver: the driver AI (its ``model_id`` is the session ``driver_model``).
        operator: the operator AI that edits the sandbox (its ``model_id`` is the
            session ``operator_model``); for tests, :class:`ReferenceParserOperator`.
        repo_root: the clean clone to sandbox.
        parser_attr: the parser class/factory attribute the operator's installed
            module exposes (the runner resolves ``<module>:<attr>``).
        source: the dropped data to ingest; defaults to the committed SYNTHETIC
            fixture (never the real dump). The real-dump follow-up passes a path
            under ``config.source_dir`` locally — never in a committed test (C-003).

    Returns:
        The grader :data:`Verdict` (no ids/timestamps).
    """
    return _drive_live_trial(
        config,
        driver=driver,
        operator=operator,
        repo_root=repo_root,
        parser_attr=parser_attr,
        source=source,
        keep_sandbox=False,
    ).verdict


def run_live_trial_with_log(
    config: LiveTrialConfig,
    *,
    driver: Driver,
    operator: Operator,
    repo_root: Path,
    parser_attr: str,
    source: Path | None = None,
) -> LiveTrialResult:
    """Like :func:`run_live_trial` but KEEPS the sandbox and returns its log path.

    Used by the seam test to assert on the harness-written session/provenance rows
    (run_kind, operator_model/driver_model). Production never keeps the sandbox.
    The caller is responsible for tearing the kept sandbox down (NFR-004).
    """
    return _drive_live_trial(
        config,
        driver=driver,
        operator=operator,
        repo_root=repo_root,
        parser_attr=parser_attr,
        source=source,
        keep_sandbox=True,
    )


__all__ = [
    "Driver",
    "LiveTrialConfig",
    "LiveTrialResult",
    "Operator",
    "ReferenceParserOperator",
    "ScriptedDriver",
    "Verdict",
    "real_model_driver",
    "real_model_operator",
    "run_live_trial",
    "run_live_trial_with_log",
]
