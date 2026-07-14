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

== Named follow-up CLOSED: real-model wiring is available (D4 / R5 / SC-005) ======

The concrete cheap-model :class:`Operator` and :class:`Driver` were a **named
follow-up**, NOT a silent waiver (DIRECTIVE_010). WP04 closes that follow-up
(FR-013): the two explicitly-named factories below —
:func:`real_model_operator` and :func:`real_model_driver` — now DELEGATE to the
WP03 cheap-model operator/driver. The default-constructed operator points at the
committed SYNTHETIC fixture so construction stays network-free and deterministic;
no committed default-suite test invokes a real model, while the gated tests prove
the delegated path works when Ollama is available.

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

import importlib
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from premura.harness import open_sandbox_warehouse_for_grading
from premura.harness.grader import grade
from premura.harness.sandbox import Sandbox, build_sandbox, install_parser
from premura.harness.scenario import Scenario, observation_scenario
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
class TurnLike(Protocol):
    """One conversation turn an operator may expose for capture (m2 FR-2).

    A bounded structural abstraction (guide-don't-enumerate): any object with a
    ``role`` and ``content`` string is a turn, with the per-turn telemetry
    (``tool_name`` / ``model`` / ``token_count``) optional. The harness reads
    these attributes off whatever an operator's ``transcript()`` returns — it
    does not require a specific class, so each tier maps its own message shape to
    this protocol (``ToolLoopOperator``'s chat messages, the one-shot operator's
    prompt/response). ``role`` is validated against the store's ``TURN_ROLES``
    vocabulary at persistence time, not here.
    """

    role: str
    content: str


@runtime_checkable
class HasTranscript(Protocol):
    """The optional transcript-capture capability an operator may expose (m2 FR-2).

    An operator that implements ``transcript()`` after ``operate()`` gets its
    conversation persisted by the harness (the sole log writer). The harness
    detects this STRUCTURALLY (a ``transcript`` attribute / this protocol) — there
    is no registry of tiers and no per-tier capture branch. Operators without it
    behave exactly as before (zero ``log_turn`` rows, unchanged verdict).
    """

    def transcript(self) -> Sequence[TurnLike]:
        """Return the final-state conversation as a sequence of :class:`TurnLike`."""
        ...


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
    """Captured ingest evidence assembled from the runner envelope (transport only).

    Every field is *captured measured evidence* or a *parser claim* the strategy
    reconciles — never a precomputed rule verdict (FR-005). The observation fields
    are unchanged; ``produced`` and ``error`` are the **intake runtime-evidence
    seam** the harness carries so the injected
    :class:`~premura.harness.intake_strategy.IntakeStrategy` reads real captured
    values (not ``getattr`` fallbacks) when an intake scenario is driven:

    * ``error`` — the runner envelope's **stage-tagged** failure detail
      (``parse:`` / ``validate:`` / ``persist:``), surfaced by the WP02 runner
      change; ``None`` on success. The intake checker reads it as the
      ``persisted_without_raising`` violation message.
    * ``produced`` — the produced :class:`~premura.parsers.base.IntakeBatch` when
      the run path holds it in-process; ``None`` across the subprocess boundary and
      for the observation drawer (whose strategy never reads it). Transport only:
      the grader recomputes ``loaded`` from the warehouse and ``honest_about_gaps``
      from the manifest regardless (FR-005).
    """

    declared_metrics: Sequence[str]
    emitted_metric_ids: Sequence[str]
    unmapped_metrics: Sequence[str]
    skipped_rows: Sequence[dict[str, Any]]
    rows_inserted: int
    ingest_run_ok: bool
    error: str | None = None
    produced: Any = None


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
# WIRED (FR-013) — these factories delegate to the WP03 Ollama operator/driver.
# The operator defaults to the committed synthetic fixture so the seam can be
# constructed without bespoke caller plumbing and without reopening stub behavior.
# The import is lazy so this slice-one seam has no import cycle with the WP03 module.
# --------------------------------------------------------------------------- #


def real_model_operator(source: Path | None = None, **kwargs: Any) -> Operator:
    """Resolve the D4/R5 follow-up: delegate to the WP03 cheap-model operator.

    The slice-one substrate shipped this as a ``NotImplementedError`` placeholder;
    that follow-up is now CLOSED (FR-013). This builds and returns the real
    cheap-model :class:`Operator` —
    :class:`premura.harness.live_trial_ollama.OllamaOperator` — forwarding
    ``model`` / ``max_tries`` kwargs. A bare call defaults to the committed
    synthetic fixture, which keeps construction deterministic and removes the last
    placeholder-style stub behavior. The import is LAZY so the slice-one seam has
    no import cycle with the WP03 module (which imports this one).
    """
    from premura.harness.live_trial_ollama import OllamaOperator

    if source is None:
        source = Path(__file__).resolve().parents[3] / _SYNTHETIC_CSV
    return OllamaOperator(source, **kwargs)


def real_model_driver(**kwargs: Any) -> Driver:
    """Resolve the D4/R5 follow-up: delegate to the WP03 cheap-model driver.

    The slice-one substrate shipped this as a ``NotImplementedError`` placeholder;
    that follow-up is now CLOSED (FR-013). It builds and returns the real
    cheap-model :class:`Driver` —
    :class:`premura.harness.live_trial_ollama.OllamaDriver` — forwarding the
    ``model`` kwarg. The import is LAZY to avoid an import cycle.

    Calling it with no kwargs still returns a working driver using the default
    cheap local model; there is no remaining stub behavior.
    """
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
        # The runner crashed before emitting its envelope (e.g. an unimportable
        # parser module the subprocess could not even start, or an interpreter-level
        # abort). The harness MUST still reach a completed, persisted, gradeable
        # FAIL — never raise before a record exists (FR-009; the session-log-substrate
        # RCA). Synthesize a stage-tagged ``parse:`` error envelope so the failure
        # path persists a record exactly like a caught parser raise.
        return _synthetic_error_envelope(parser_spec, proc.stderr)
    try:
        envelope: dict[str, Any] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Garbled stdout is likewise a runner failure, not a reason to abort before
        # a record exists; synthesize the same gradeable FAIL envelope (FR-009).
        return _synthetic_error_envelope(parser_spec, proc.stderr or proc.stdout)
    return envelope


def _synthetic_error_envelope(parser_spec: str, detail: str) -> dict[str, Any]:
    """Build an error envelope for a runner that produced no usable stdout (FR-009).

    Shape-identical to the runner's own error envelope (the same keys the happy
    path emits, all arrays present-and-empty) so the downstream provenance write +
    grading proceed unchanged. The ``error.message`` is stage-tagged ``parse:`` so
    the intake checker witnesses the broken stage; the harness never trusts it as a
    verdict (FR-005). The detail is truncated to stay PHI-safe and bounded.
    """
    parser_kind = parser_spec.split(":", 1)[1] if ":" in parser_spec else parser_spec
    message = (detail or "ingest runner produced no envelope").strip()
    return {
        "status": "error",
        "error": {"kind": "RunnerNoEnvelope", "message": f"parse: {message[:500]}"},
        "parser_kind": parser_kind,
        "batch_id": None,
        "load_stats": None,
        "declared_metrics": [],
        "emitted_metric_ids": [],
        "unmapped_metrics": [],
        "skipped_rows": [],
    }


def _envelope_error_detail(envelope: dict[str, Any]) -> str | None:
    """Extract the runner's stage-tagged error message (transport only).

    The runner's ``error`` is ``None`` on success or an object
    ``{"kind", "message"}`` whose ``message`` carries the stage tag
    (``parse:`` / ``validate:`` / ``persist:``). We carry that message verbatim so
    the intake checker can witness which stage broke; we never re-tag or trust it.
    """
    error = envelope.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        return str(message) if message is not None else None
    if isinstance(error, str):
        return error
    return None


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
        error=_envelope_error_detail(envelope),
        produced=None,
    )


def _captured_intake_batch(
    sandbox: Sandbox,
    *,
    source: Path,
    parser_attr: str,
) -> Any:
    """Re-parse inside the parent to recover the produced intake batch for grading.

    The ingest runner crosses a JSON-only subprocess seam, so an intake-only run's
    produced ``IntakeBatch`` is otherwise lost before the grader sees it. For the
    live-trial path we re-import the operator-authored parser from the sandboxed
    tree after the runner finishes and closed its writer handles, then normalize
    its ``parse()`` output locally. This keeps the frozen ingest envelope untouched
    while restoring the evidence the intake runtime checker needs.
    """
    from premura.parsers.base import normalize_parse_output

    module_path = sandbox.root / _PARSER_DEST_RELPATH
    spec = importlib.util.spec_from_file_location(_PARSER_MODULE, module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        parser = getattr(module, parser_attr)()
        _observation, intake = normalize_parse_output(parser.parse(source))
        return intake
    except Exception:  # noqa: BLE001 - transport-only evidence recovery
        return None


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    import yaml  # type: ignore[import-untyped]

    return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))


@dataclass(slots=True)
class LiveTrialResult:
    """Verdict + session identity + the (kept) sandbox log path, for inspection."""

    verdict: Verdict
    session_id: str
    session_log_path: Path


def _persist_transcript(
    log_conn: duckdb.DuckDBPyConnection,
    *,
    operator: Operator,
    session_id: str,
    step_id: str,
) -> None:
    """Persist a capable operator's conversation as ordered ``log_turn`` rows (FR-5).

    The harness is the SOLE log writer (FR-021 / NFR-1): the operator only
    EXPOSES its turns; this writes them. The capability is detected STRUCTURALLY
    (``hasattr``) — no registry of tiers, no per-tier branch (FR-2). An operator
    without ``transcript()`` is a no-op here.

    Capture must never change an otherwise-successful run's verdict (FR-5): any
    failure assembling or writing turns is swallowed and surfaced as a recorded
    ``error``-status step under the run's root ``agent_turn``, not re-raised. The
    turns link to that root step (FR-1 step_id link) and are written in the order
    the operator returns them (``turn_index`` is the 0-based position).
    """
    if not hasattr(operator, "transcript"):
        return
    try:
        turns = list(operator.transcript())  # type: ignore[attr-defined]
        for index, turn in enumerate(turns):
            store.record_turn(
                log_conn,
                session_id=session_id,
                step_id=step_id,
                turn_index=index,
                role=turn.role,
                content=turn.content,
                tool_name=getattr(turn, "tool_name", None),
                model=getattr(turn, "model", None),
                token_count=getattr(turn, "token_count", None),
            )
    except Exception as exc:  # noqa: BLE001 - capture failure must not flip the verdict
        store.record_step(
            log_conn,
            session_id=session_id,
            parent_step_id=step_id,
            kind="tool_call",
            name="transcript capture failed",
            tool_name="capture_transcript",
            request_summary=None,
            request_hash=None,
            result_status="error",
            result_summary=f"transcript capture failed: {type(exc).__name__}: {exc}"[:500],
            result_hash=None,
        )


def _drive_live_trial(
    config: LiveTrialConfig,
    *,
    driver: Driver,
    operator: Operator,
    repo_root: Path,
    parser_attr: str,
    source: Path | None,
    keep_sandbox: bool,
    scenario: Scenario | None = None,
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
       its writable handle) + the scenario's committed manifest (WP05), driven through
       the GENERIC :func:`grade` with the **scenario's injected strategy** — no
       per-source branch (NFR-005). Persist provenance with ``contract_pass`` = the
       GRADER's recomputed ``runtime_valid`` (FR-065).
    6. :func:`store.finish_session`; tear the sandbox down unless ``keep_sandbox``
       (NFR-004); return the result.

    ``scenario`` selects which acceptance source the run is graded against. It
    defaults to the observation scenario so existing callers/tests are unchanged
    (C-004); passing the intake scenario makes the SAME path grade an intake run via
    the injected :class:`~premura.harness.intake_strategy.IntakeStrategy`.
    """
    repo_root = repo_root.resolve()
    if scenario is None:
        scenario = observation_scenario()
    manifest = _load_manifest(scenario.manifest_path)
    ingest_source = source if source is not None else scenario.source_path
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
        if scenario.name == "intake_alien":
            provenance.produced = _captured_intake_batch(
                sandbox,
                source=ingest_source,
                parser_attr=parser_attr,
            )

        # (5) Grade against the sandbox warehouse (read-only, AFTER the runner closed).
        #     On the failure path the operator's parser raised before any warehouse
        #     file was created; the helper materializes an EMPTY (0-fact-row)
        #     warehouse so grading still yields a deterministic FAIL (FR-080).
        warehouse_conn = open_sandbox_warehouse_for_grading(sandbox.warehouse_path)
        try:
            # Scenario-owned grading dispatch (#68): each scenario declares its own
            # grading entry point via `grade_fn` (None means "use the shared
            # `grade()`"). No name matching on scenario.name here (NFR-005).
            grader_fn = scenario.grade_fn or grade
            verdict = cast(
                "dict[str, Any]",
                grader_fn(
                    provenance=provenance,
                    warehouse_conn=warehouse_conn,
                    fixture_manifest=manifest,
                    strategy=scenario.strategy,
                ),
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

        # (5b) Persist the operator's conversation transcript, if it exposes one
        #      (FR-2/FR-5). Detected structurally; the harness is the sole writer.
        #      Capture failure surfaces as an error-status step, never an exception
        #      that flips the run's verdict.
        _persist_transcript(
            log_conn,
            operator=operator,
            session_id=session_id,
            step_id=turn_id,
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
    scenario: Scenario | None = None,
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
        source: the dropped data to ingest; defaults to the scenario's committed
            SYNTHETIC source (never the real dump). The real-dump follow-up passes a
            path under ``config.source_dir`` locally — never in a committed test
            (C-003).
        scenario: the acceptance :class:`~premura.harness.scenario.Scenario` the run
            is graded against; dispatched via ``scenario.grade_fn or grade`` (no
            per-source branch, NFR-005). Defaults to the observation scenario so
            existing callers are unchanged (C-004).

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
        scenario=scenario,
    ).verdict


def run_live_trial_with_log(
    config: LiveTrialConfig,
    *,
    driver: Driver,
    operator: Operator,
    repo_root: Path,
    parser_attr: str,
    source: Path | None = None,
    scenario: Scenario | None = None,
) -> LiveTrialResult:
    """Like :func:`run_live_trial` but KEEPS the sandbox and returns its log path.

    Used by the seam test to assert on the harness-written session/provenance rows
    (run_kind, operator_model/driver_model). Production never keeps the sandbox.
    The caller is responsible for tearing the kept sandbox down (NFR-004).

    ``scenario`` is threaded through to :func:`_drive_live_trial` so the kept-log
    path can be graded against any registered acceptance source (defaults to
    observation; C-004).
    """
    return _drive_live_trial(
        config,
        driver=driver,
        operator=operator,
        repo_root=repo_root,
        parser_attr=parser_attr,
        source=source,
        keep_sandbox=True,
        scenario=scenario,
    )


__all__ = [
    "Driver",
    "HasTranscript",
    "LiveTrialConfig",
    "LiveTrialResult",
    "Operator",
    "ReferenceParserOperator",
    "ScriptedDriver",
    "TurnLike",
    "Verdict",
    "real_model_driver",
    "real_model_operator",
    "run_live_trial",
    "run_live_trial_with_log",
]
