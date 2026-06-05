"""Cheap local Ollama operator/driver for the live-trial seam (D4 / R5 / SC-005).

This is the real, *deliberately cheap* cheap-model operator the slice-one
substrate deferred (``live_trial.real_model_operator`` / ``real_model_driver``).
It drives a local Ollama model to author a Premura parser INTO the sandbox tree,
gates each attempt with the WP01 manifest-blind self-reconciliation check (plus
an in-sandbox import/parse/validate smoke), feeds failures back up to a bounded
cap, then runs the FINAL parser through the EXACT same lower machinery as the
repeatable check via :func:`premura.harness.live_trial.run_live_trial_with_log`.

Two verdicts are recorded (FR-014): the **independent slice-one grader** judges
the **un-nagged attempt-1** parser AND the **final** parser. The operator's
self-reconcile gate is SEPARATE from the grader — the model never sees the
grader's answer key (C-005). The honesty gate is manifest-blind: it reads the
source header directly and reconciles it against the parser's own declared gaps
plus the source columns the parser says it mapped.

Boundaries this module honours:

* **NFR-004 / FR-021** — the operator only edits the sandbox *tree*; the harness
  remains the sole session-log writer. This module never opens the session log.
* **C-005** — no prompt path ever includes ``fixture_fields.yaml`` or any
  ground-truth mapping. The model gets the parser contract, a small source
  sample, the goal, and (on retry) its own failure verbatim — nothing else.
* **C-003 / NFR-002 / FR-012** — only the committed SYNTHETIC fixture persists
  (via WP02 :func:`persist_run`, synthetic-guarded). A real-dump source records
  NOTHING; the real-data path stays a manual, local-only exercise. The opt-in
  ``keep_sandboxes`` inspection knob is likewise synthetic-only — a real source
  always tears its sandbox down so no real local data is left on disk.
* **NFR-005** — the matching test is marked ``live_trial`` and the default suite
  excludes it; a missing/failing live trial can never block CI.

Run it directly::

    uv run python -m premura.harness.live_trial_ollama          # synthetic fixture
    OLLAMA_MODEL=qwen2.5-coder:7b uv run python -m premura.harness.live_trial_ollama

It needs a running Ollama (``http://localhost:11434``) with the model pulled.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from premura.harness import live_trial
from premura.harness.live_trial import (
    LiveTrialConfig,
    LiveTrialResult,
    Operator,
)
from premura.harness.sandbox import Sandbox
from premura.harness.scenario import Scenario, observation_scenario
from premura.harness.scoreboard import (
    LiveTrialRunRecord,
    ScoreboardEntry,
    Verdict,
    append_scoreboard,
    persist_run,
)
from premura.harness.self_reconcile import SelfReconciliationResult

# --------------------------------------------------------------------------- #
# Configuration (env-overridable; defaults to a locally available cheap coder).
# --------------------------------------------------------------------------- #

#: Default operator/driver model — a small local coder model (NFR-003 / FR-008).
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

#: Local Ollama generate endpoint (no third-party HTTP client; stdlib only).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

#: Bounded retry cap for the self-reconcile loop (NFR-003).
MAX_TRIES = int(os.environ.get("LIVE_TRIAL_MAX_TRIES", "3"))

# Repo root resolved from this module's location, NOT the process cwd, so the
# harness works from any clone. scoreboard.py shares this convention.
# live_trial_ollama.py -> harness -> premura -> src -> <repo-root>.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The committed synthetic fixture (no PHI). The single source that persists.
_SYNTHETIC_CSV = (
    _REPO_ROOT / "tests" / "fixtures" / "session_log" / "fitbit_heart_rate_synthetic.csv"
)

# Where the operator's parser lands inside the sandbox; mirrors live_trial's
# ``_PARSER_DEST_RELPATH`` / ``_PARSER_MODULE`` so the runner resolves it.
_PARSER_DEST_RELPATH = "src/premura/parsers/_live_trial_parser.py"
_PARSER_MODULE = "premura.parsers._live_trial_parser"
_PARSER_ATTR = "LiveTrialParser"

# The module-level constant the generated parser MUST expose so the gate gets an
# EXPLICIT set of mapped source columns rather than guessing (per WP03 T011 and
# the self-reconciliation contract: ``mapped_columns`` is a caller-supplied set).
_MAPPED_COLUMNS_CONST = "MAPPED_SOURCE_COLUMNS"

# The contract surface a real operator has from CONTRACT.md + base.py. This is
# the contract, NOT the reference parser and NOT the manifest — the model never
# sees the answer key (C-005).
_OBSERVATION_CONTRACT_PROMPT = f"""\
You are writing a Premura parser plugin. Output ONE Python module, nothing else.

Target API (importable in the sandbox):
    from premura.parsers.base import (
        IngestBatch, Measurement, SourceDescriptor, SkippedRow,
    )

Measurement(dataclass) fields you set:
    ts_utc: datetime (UTC, tz-naive), metric_id: str, unit: str,
    source_id: str, source_kind: str, value_num: float | None = None,
    source_uuid: str | None = None
IngestBatch(dataclass) fields you set:
    source_kind: str, declared_metrics: list[str],
    measurements: list[Measurement], unmapped_metrics: list[str],
    skipped_rows: list[SkippedRow], source_descriptors: dict[str, SourceDescriptor]
    methods: .attach_source_artifact(path) -> self ; .validate() (call before returning)
SourceDescriptor(source_id, source_kind, device_manufacturer=...)
    EVERY source_id you put on a Measurement MUST have a matching entry in
    source_descriptors keyed by that source_id, or validate() raises.
SkippedRow(raw_field: str, reason: str) — use raw_field for a declared-gap COLUMN.

Your class MUST be named exactly:
    class {_PARSER_ATTR}:
        source_kind: str = "<short stable source id>"
        language_hint: str | None = None
        def declares_metrics(self) -> list[str]: ...   # canonical metric_ids you emit
        def parse(self, path: Path) -> IngestBatch: ...

You MUST also expose, at MODULE level, the set of raw source COLUMN NAMES your
parser actually consumed to emit metrics:
    {_MAPPED_COLUMNS_CONST}: list[str] = [...]   # e.g. the bpm column name

RULES (decision tree, in order, per source column):
  1. Map a column to a canonical metric_id ONLY if it is a real physiological
     metric. Heart-rate beats-per-minute -> metric_id "heart_rate", unit "bpm".
     Add every column you map to {_MAPPED_COLUMNS_CONST}.
  2. A column that is structural metadata (a timestamp), a vendor confidence
     flag, or has no canonical metric MUST NOT be invented as a metric. Declare
     its raw COLUMN NAME in unmapped_metrics (or as a SkippedRow.raw_field).
     NEVER silently drop a column: EVERY column in the source header must be
     either in {_MAPPED_COLUMNS_CONST} or declared as a gap.
  3. declares_metrics() MUST equal the set of metric_ids you actually emit.
  4. Never emit a metric_id starting with "derived:".
  5. Call result.validate() before returning the batch.

Emit exactly one heart_rate Measurement per data row that has a bpm value.
Give each Measurement a stable source_uuid like f"{{source_kind}}:{{timestamp}}".
Parse the ISO timestamp to a tz-naive UTC datetime.

Output ONLY the python module source. No markdown, no prose, no code fences.
"""

# The intake-drawer contract surface. Same posture as the observation prompt: it
# is the CONTRACT (IntakeBatch + the intake input dataclasses), NEVER the
# reference parser and NEVER the grader-only manifest (C-005). The model gets the
# loadable-row shape, the gap-declaration rule, and the self-reconcile honesty
# rule — the same three rules grade observation and intake; only the loadable
# shape differs (FR-007 / D9).
_INTAKE_CONTRACT_PROMPT = f"""\
You are writing a Premura intake parser plugin. Output ONE Python module, nothing else.

Target API (importable in the sandbox):
    from premura.parsers.base import (
        IntakeBatch, ParseOutput, SourceDescriptor, SkippedRow,
        NutritionIntakeInput, NutritionItemInput, NutritionQuantityInput,
        SupplementIntakeInput, SupplementItemInput, SupplementDoseInput,
    )

This is the INTAKE seam (meals + supplements), NOT the observation seam: emit an
IntakeBatch (carried inside a ParseOutput), never measurements / heart_rate rows.

IntakeBatch(dataclass) fields you set:
    source_descriptors: dict[str, SourceDescriptor],
    nutrition_events: list[NutritionIntakeInput],
    supplement_events: list[SupplementIntakeInput],
    unmapped_metrics: list[str], skipped_rows: list[SkippedRow]
    method: .validate() (call before returning)
A meal row -> NutritionIntakeInput(source_id, source_kind, start_utc, local_tz,
    dedupe_key, items=[NutritionItemInput(item_label, quantities=[
    NutritionQuantityInput(quantity_key, value_num, unit)])]).
A supplement row -> SupplementIntakeInput(source_id, source_kind, ts_utc, local_tz,
    dedupe_key, items=[SupplementItemInput(product_label, doses=[
    SupplementDoseInput(amount_num, unit)])]).
SourceDescriptor(source_id, source_kind, app_name=...) — EVERY event source_id
    MUST have a matching source_descriptors entry, or validate() raises.
SkippedRow(raw_field: str, reason: str) — use raw_field for a declared-gap COLUMN.

Your class MUST be named exactly:
    class {_PARSER_ATTR}:
        source_kind: str = "<short stable source id>"
        language_hint: str | None = None
        def declares_metrics(self) -> list[str]: ...   # intake has none -> return []
        def parse(self, path: Path) -> ParseOutput: ... # ParseOutput(intake=batch)

You MUST also expose, at MODULE level, the list of raw source COLUMN NAMES your
parser actually consumed to emit intake events:
    {_MAPPED_COLUMNS_CONST}: list[str] = [...]

RULES (decision tree, in order, per source column):
  1. Consume a column to fill an intake event (timestamp, kind, item label,
     quantity value, quantity unit) and add it to {_MAPPED_COLUMNS_CONST}.
  2. A column with no canonical intake home (e.g. free-text commentary) MUST NOT
     be invented. Declare its raw COLUMN NAME in unmapped_metrics (or as a
     SkippedRow.raw_field). NEVER silently drop a column: EVERY column in the
     source header must be either in {_MAPPED_COLUMNS_CONST} or declared as a gap.
  3. Give each event a stable, unique dedupe_key.
  4. Call result.validate() before returning ParseOutput(intake=result).

Output ONLY the python module source. No markdown, no prose, no code fences.
"""


class OllamaUnavailableError(RuntimeError):
    """Raised when the local Ollama endpoint cannot be reached."""


# --------------------------------------------------------------------------- #
# Ollama client (stdlib urllib only — no third-party HTTP client). [T010]
# --------------------------------------------------------------------------- #


def _validated_ollama_url(url: str) -> str:
    """Enforce the slice's local-only model backend boundary (C-003).

    ``OLLAMA_URL`` is env-configurable for localhost variants, but this mission's
    contract is still *local model backend*. Refuse non-local endpoints so prompt
    data and source samples cannot be sent off-machine by configuration drift.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise OllamaUnavailableError(f"Ollama URL must be http(s), got: {url!r}")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise OllamaUnavailableError(
            f"Ollama URL must stay local-only for this slice, got: {url!r}"
        )
    return url


def _ollama(prompt: str, *, model: str, timeout: int = 300) -> str:
    """Call the local Ollama ``/api/generate`` endpoint (``stream=False``, low temp).

    Returns the model's ``response`` text. Raises :class:`OllamaUnavailableError`
    if the endpoint is unreachable so callers can treat unavailability as a
    returnable outcome rather than a crash.
    """
    url = _validated_ollama_url(OLLAMA_URL)
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed localhost URL
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OllamaUnavailableError(f"Ollama not reachable at {OLLAMA_URL}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        # A reachable-but-garbled local endpoint is still "unavailable" as far as a
        # caller is concerned: surface it as the returnable sentinel, not a crash
        # that escapes the availability probe (NFR-001).
        raise OllamaUnavailableError(
            f"Ollama returned a non-JSON response at {OLLAMA_URL}: {exc}"
        ) from exc
    response = payload.get("response")
    if not isinstance(response, str):
        raise OllamaUnavailableError(f"Ollama returned no 'response' field: {payload!r}")
    return response


def ollama_available() -> bool:
    """True if the local Ollama endpoint answers (used by the gated test to skip)."""
    try:
        _ollama("ping", model=DEFAULT_MODEL, timeout=10)
    except OllamaUnavailableError:
        return False
    return True


# --------------------------------------------------------------------------- #
# Generated-code helpers.
# --------------------------------------------------------------------------- #


def _extract_code(text: str) -> str:
    """Strip optional markdown fences from a model response; return module source."""
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    code = match.group(1) if match else text
    return code.strip() + "\n"


def _normalize_class_name(code: str) -> str:
    """Guarantee the runner-resolved attr exists: alias the parse-class to the attr."""
    if re.search(rf"class\s+{_PARSER_ATTR}\b", code):
        return code
    classes = re.findall(r"^class\s+(\w+)", code, re.MULTILINE)
    if classes:
        target = classes[-1]
        for candidate in classes:
            if re.search(rf"class\s+{candidate}\b.*?def\s+parse\s*\(", code, re.DOTALL):
                target = candidate
                break
        code += f"\n\n{_PARSER_ATTR} = {target}\n"
    return code


@dataclass(frozen=True, slots=True)
class _DrawerProbe:
    """The scenario-derived drawer specifics the in-sandbox probe + operator need.

    This is the bounded *rubric* (guide-don't-enumerate, D9) that generalizes the
    probe off its observation-only gate. Each field is the SAME role for every
    drawer — only the loadable-row shape differs:

    * ``contract_prompt`` — the contract surface the operator authors against
      (observation measurements vs intake events). Never the manifest (C-005).
    * ``batch_selector`` — the expression (over the ``(observation, intake)`` tuple
      from ``normalize_parse_output``) that picks THIS drawer's batch in the probe.
    * ``nonempty_check`` — the drawer's "produced at least one loadable row" check
      (observation: ``batch.measurements``; intake: ``len(batch)``), evaluated in
      the probe over the selected ``batch``.
    * ``missing_msg`` / ``empty_msg`` — the probe's assertion messages.
    * ``goal`` — the driver's PHI-safe goal sentence for this drawer (the human's
      intent the operator authors toward).

    A new drawer is added by registering one of these in ``_DRAWER_PROBES`` keyed
    by its scenario name — appending to a list, never forking the probe body.
    """

    contract_prompt: str
    batch_selector: str
    nonempty_check: str
    missing_msg: str
    empty_msg: str
    goal: str


# The drawer-probe rubric: scenario name -> its :class:`_DrawerProbe`. Adding a
# new acceptance drawer is registering an entry here (the guide-don't-enumerate
# surface), NOT adding an ``if drawer:`` branch to the probe or the operator.
_DRAWER_PROBES: dict[str, _DrawerProbe] = {
    "observation": _DrawerProbe(
        contract_prompt=_OBSERVATION_CONTRACT_PROMPT,
        batch_selector="observation",
        nonempty_check="batch.measurements",
        missing_msg="parser emitted no observation batch",
        empty_msg="parser emitted zero measurements",
        goal="ingest the heart-rate category from the dropped Fitbit CSV",
    ),
    "intake_alien": _DrawerProbe(
        contract_prompt=_INTAKE_CONTRACT_PROMPT,
        batch_selector="intake",
        nonempty_check="len(batch) > 0",
        missing_msg="parser emitted no intake batch",
        empty_msg="parser emitted zero intake events",
        goal="ingest the meals and supplements from the dropped intake journal",
    ),
}


def _resolve_drawer_probe(scenario: Scenario) -> _DrawerProbe:
    """Resolve a scenario to its drawer-probe spec via the rubric (no per-drawer fork).

    The single lookup that makes the operator + probe scenario-parametric: it reads
    the rubric keyed by ``scenario.name``. An unregistered scenario is a missing
    rubric entry (a named, explicit follow-up), never a silent observation default.
    """
    try:
        return _DRAWER_PROBES[scenario.name]
    except KeyError as exc:
        raise KeyError(
            f"no live-trial drawer probe registered for scenario {scenario.name!r}; "
            f"register one in _DRAWER_PROBES (known: {sorted(_DRAWER_PROBES)})"
        ) from exc


@dataclass(slots=True)
class _GateOutcome:
    """Result of gating one generated parser inside the sandbox.

    ``passed`` is the AND of (a) import/parse/validate succeeded and (b) the WP01
    self-reconcile gate passed. ``feedback`` is the verbatim error and/or
    ``unaccounted`` columns fed back to the model on the next retry; it is empty
    on success.
    """

    passed: bool
    feedback: str
    self_reconciliation: SelfReconciliationResult
    parser_error: str | None = None


# The in-sandbox probe: imports the generated parser, parses + validates the
# source, reads the parser's own declared gaps + its MAPPED_SOURCE_COLUMNS, and
# runs the WP01 self_reconcile gate IN the sandbox (so the real, manifest-blind
# WP01 code judges it). It prints a single JSON object on stdout. It never reads
# the fixture manifest (C-005) — only the source artifact + the parser's batch.
#
# The body is DRAWER-DRIVEN, not observation-hardcoded (D9): the two drawer
# specifics — which side of ``normalize_parse_output`` carries the batch and the
# drawer's non-empty check — are filled in from the scenario's :class:`_DrawerProbe`
# rubric (``{batch_selector}`` / ``{nonempty_check}``). The self_reconcile gate is
# drawer-agnostic already (it reads ``unmapped_metrics`` / ``skipped_rows``, both
# present on either batch type), so it is reached identically for every drawer.
_PROBE_TEMPLATE = """\
import json
import sys
from pathlib import Path

result = {{
    "ok": False,
    "parser_error": "",
    "self_reconciliation": {{
        "passed": False,
        "source_columns": [],
        "accounted": [],
        "unaccounted": [],
    }},
}}
try:
    from premura.harness.self_reconcile import _read_source_columns, self_reconcile
    from premura.parsers.base import normalize_parse_output
    from premura.parsers.{module_attr} import {attr} as _Parser
    import premura.parsers.{module_attr} as _mod

    # A parser may return a bare IngestBatch (observation-only) or a ParseOutput
    # carrying observation and/or intake; normalize to the (observation, intake)
    # union, then pick the batch for THIS scenario's target drawer (FR-007 shape).
    observation, intake = normalize_parse_output(_Parser().parse(Path({source!r})))
    batch = {batch_selector}
    if batch is None:
        raise AssertionError({missing_msg!r})
    batch.validate()
    if not ({nonempty_check}):
        raise AssertionError({empty_msg!r})
    mapped = list(getattr(_mod, {mapped_const!r}, []))
    recon = self_reconcile(Path({source!r}), batch, mapped)
    result["ok"] = True
    result["self_reconciliation"] = {{
        "passed": bool(recon.passed),
        "source_columns": list(recon.source_columns),
        "accounted": sorted(recon.accounted),
        "unaccounted": list(recon.unaccounted),
    }}
except Exception as exc:  # noqa: BLE001
    import traceback
    cols = _read_source_columns(Path({source!r}))
    result["parser_error"] = traceback.format_exc()[-1500:]
    result["self_reconciliation"] = {{
        "passed": False,
        "source_columns": list(cols),
        "accounted": [],
        "unaccounted": sorted(cols),
    }}
print(json.dumps(result))
"""


def _gate_parser(sandbox_src: Path, source: Path, probe: _DrawerProbe) -> _GateOutcome:
    """Import/parse/validate the generated parser AND run the WP01 self-reconcile gate.

    Runs in a subprocess rooted at the sandbox ``src`` so it imports the sandbox
    copy of premura and the operator's installed parser. Both checks are
    manifest-blind: only the source artifact + the parser's own batch are read
    (C-005). ``probe`` supplies the scenario's drawer specifics (which batch side
    to gate, the non-empty check) so the SAME gate runs for observation or intake
    with no per-drawer branch (D9). Returns a :class:`_GateOutcome` whose
    ``feedback`` carries the parse error and/or the verbatim ``unaccounted``
    columns for the next retry.
    """
    probe_src = _PROBE_TEMPLATE.format(
        module_attr=_PARSER_MODULE.split(".")[-1],
        attr=_PARSER_ATTR,
        mapped_const=_MAPPED_COLUMNS_CONST,
        source=str(source),
        batch_selector=probe.batch_selector,
        nonempty_check=probe.nonempty_check,
        missing_msg=probe.missing_msg,
        empty_msg=probe.empty_msg,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(probe_src)
        probe_path = handle.name
    env = {
        "PYTHONPATH": str(sandbox_src),
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    try:
        proc = subprocess.run(
            [sys.executable, probe_path],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    finally:
        Path(probe_path).unlink(missing_ok=True)

    try:
        outcome = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (json.JSONDecodeError, IndexError):
        outcome = {}

    recon_payload = outcome.get("self_reconciliation") or {}
    recon = SelfReconciliationResult(
        passed=bool(recon_payload.get("passed")),
        source_columns=list(recon_payload.get("source_columns", [])),
        accounted=frozenset(recon_payload.get("accounted", [])),
        unaccounted=list(recon_payload.get("unaccounted", [])),
    )

    if not outcome.get("ok"):
        error = outcome.get("parser_error") or (proc.stderr or proc.stdout).strip()[-1500:]
        return _GateOutcome(
            passed=False,
            feedback=f"import/parse/validate failed:\n{error}",
            self_reconciliation=recon,
            parser_error=error,
        )

    if recon.passed:
        return _GateOutcome(passed=True, feedback="", self_reconciliation=recon)

    feedback = (
        "self-reconcile FAILED — these source columns were neither mapped nor "
        f"declared as a gap (silent drops): {recon.unaccounted}. "
        "Map each real metric column and add it to "
        f"{_MAPPED_COLUMNS_CONST}; declare every other column in unmapped_metrics."
    )
    return _GateOutcome(passed=False, feedback=feedback, self_reconciliation=recon)


@dataclass(slots=True)
class AttemptRecord:
    """Telemetry for one operator attempt (for grading + inspection, FR-014)."""

    index: int
    self_reconciliation: SelfReconciliationResult
    parser_error: str | None
    code: str


# --------------------------------------------------------------------------- #
# OllamaOperator — the cheap operator with the self-reconcile retry loop. [T011]
# --------------------------------------------------------------------------- #


class OllamaOperator:
    """Cheap-model operator: drives a local model to author a parser into the sandbox.

    Implements the slice-one :class:`~premura.harness.live_trial.Operator`
    protocol. ``operate`` runs the bounded retry loop: prompt -> write parser ->
    gate (import/parse/validate + WP01 self-reconcile) -> on failure feed the
    error and/or ``unaccounted`` columns back verbatim -> retry, up to
    ``max_tries`` (NFR-003). It leaves the FINAL parser at the sandbox dest and
    captures every :class:`AttemptRecord` (notably attempt-1's code) so T013 can
    grade the un-nagged first attempt independently.

    It edits ONLY the sandbox tree and never opens the session log (NFR-004); the
    self-reconcile gate is the operator's own honesty check, SEPARATE from the
    independent grader (the model never sees the answer key, C-005).
    """

    def __init__(
        self,
        source: Path,
        *,
        model: str = DEFAULT_MODEL,
        max_tries: int = MAX_TRIES,
        probe: _DrawerProbe | None = None,
    ) -> None:
        self.source = source
        self.model_id = model
        self.max_tries = max_tries
        self.tries_used = 0
        self.attempts: list[AttemptRecord] = []
        # The scenario's drawer probe drives the contract prompt the operator
        # authors against AND the in-sandbox gate's batch/non-empty check. Default
        # to observation so existing callers/tests are unchanged (C-004); the
        # intake entry passes the intake probe (D9). No per-drawer branch here.
        self.probe = probe if probe is not None else _DRAWER_PROBES["observation"]

    @property
    def first_attempt_code(self) -> str:
        """The parser produced at attempt 1 (un-nagged), for independent grading."""
        return self.attempts[0].code if self.attempts else ""

    @property
    def gate_passed(self) -> bool:
        """Whether the FINAL attempt passed the self-reconcile gate."""
        return bool(self.attempts) and self.attempts[-1].self_reconciliation.passed

    def operate(self, sandbox: Sandbox, goal: str) -> None:
        """Author a parser into the sandbox, gated and retried (NFR-003 / C-005)."""
        sample = "\n".join(self.source.read_text(encoding="utf-8").splitlines()[:8])
        base_prompt = (
            f"{self.probe.contract_prompt}\n\nGOAL: {goal}\n\n"
            f"DATA SAMPLE ({self.source.name}):\n{sample}\n"
        )
        dest = sandbox.root / _PARSER_DEST_RELPATH
        sandbox_src = sandbox.root / "src"

        prompt = base_prompt
        for attempt in range(1, self.max_tries + 1):
            self.tries_used = attempt
            code = _normalize_class_name(_extract_code(_ollama(prompt, model=self.model_id)))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(code, encoding="utf-8")

            outcome = _gate_parser(sandbox_src, self.source, self.probe)
            self.attempts.append(
                AttemptRecord(
                    index=attempt,
                    self_reconciliation=outcome.self_reconciliation,
                    parser_error=outcome.parser_error,
                    code=code,
                )
            )
            if outcome.passed:
                return
            # Feed the failure back verbatim and retry within the cap.
            prompt = (
                f"{base_prompt}\n\nYour previous attempt FAILED:\n"
                f"```\n{outcome.feedback}\n```\n"
                "Fix the parser. Output ONLY the corrected python module, no prose, no fences."
            )
        # Cap exhausted: the final (best-effort) parser is already written; the
        # independent grader judges it as-is — a self-reconcile miss is a
        # legitimate capability-floor finding, never an exception.


class _FixedCodeOperator:
    """Deterministic operator that installs a pre-captured parser, no model call.

    Used to grade attempt 1 (un-nagged) through the SAME machinery as the final
    run, independently of any feedback (FR-014). Edits only the sandbox tree.
    """

    def __init__(self, code: str, *, model: str) -> None:
        self._code = code
        self.model_id = model

    def operate(self, sandbox: Sandbox, goal: str) -> None:  # noqa: ARG002 - goal unused
        dest = sandbox.root / _PARSER_DEST_RELPATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self._code, encoding="utf-8")


# --------------------------------------------------------------------------- #
# OllamaDriver — fixed goal + canned response (no frontier model). [T012]
# --------------------------------------------------------------------------- #


class OllamaDriver:
    """Cheap-model driver: a fixed scenario goal and a canned answer.

    Implements the :class:`~premura.harness.live_trial.Driver` protocol. Records
    a driver ``model_id`` but does NOT call a frontier model (FR-008; the canned
    driver is the DIRECTIVE_036 outside-boundary substitute for #10's frontier
    driver). ``goal`` defaults to the observation heart-rate goal so existing
    callers are unchanged (C-004); the intake entry passes the scenario's intake
    goal so the driver is scenario-derived, not hardcoded to one drawer (FR-007).
    """

    _DEFAULT_GOAL = "ingest the heart-rate category from the dropped Fitbit CSV"

    def __init__(self, *, model: str = DEFAULT_MODEL, goal: str | None = None) -> None:
        self.model_id = f"canned-driver:{model}"
        self._goal = goal if goal is not None else self._DEFAULT_GOAL

    def goal(self) -> str:
        return self._goal

    def respond(self, question: str) -> str:  # noqa: ARG002 - canned for the cheap driver
        return "proceed"


# --------------------------------------------------------------------------- #
# Source classification + run entry point. [T013 / T014]
# --------------------------------------------------------------------------- #


def _committed_synthetic_sources() -> set[Path]:
    """Resolved paths of every registered scenario's committed synthetic source.

    The bounded set of "safe to persist" sources is whatever the scenario registry
    declares (guide-don't-enumerate): a new acceptance source becomes synthetic by
    registering its scenario, not by editing this guard. The observation CSV is
    kept explicitly so the synthetic decision is unchanged even before the registry
    import resolves.
    """
    from premura.harness.scenario_registry import all_scenarios

    sources: set[Path] = set()
    for path in (_SYNTHETIC_CSV, *(s.source_path for s in all_scenarios())):
        try:
            sources.add(path.resolve())
        except OSError:
            continue
    return sources


def is_synthetic_source(source: Path) -> bool:
    """True iff ``source`` is a committed synthetic scenario source (T013/FR-012).

    The single decision point for whether a run persists: only a committed
    synthetic scenario source is synthetic; ANY other source (a real local dump, a
    temp copy at a different path) is treated as real and records nothing. WP05
    exercises this helper directly. Scenario-derived so the intake scenario's
    committed alien CSV persists the same way the observation CSV does, with no
    per-source branch (FR-007).
    """
    try:
        return source.resolve() in _committed_synthetic_sources()
    except OSError:
        return False


@dataclass(slots=True)
class LiveTrialOutcome:
    """Returnable outcome of an Ollama live trial (T014).

    On success, ``record`` / ``attempts`` / ``final_result`` are populated and
    ``model_unavailable`` is False. When the default operator cannot reach the
    model server, ``model_unavailable`` is True and the run records nothing — a
    returnable sentinel, not just a print, so WP05 can assert the unavailable
    edge.
    """

    model_unavailable: bool = False
    record: LiveTrialRunRecord | None = None
    attempts: list[AttemptRecord] = field(default_factory=list)
    final_result: LiveTrialResult | None = None
    first_attempt_result: LiveTrialResult | None = None
    persisted_run_dir: Path | None = None


def _grade_one(
    operator: Operator,
    *,
    driver: OllamaDriver,
    source: Path,
    repo_root: Path,
    scenario: Scenario,
) -> LiveTrialResult:
    """Run one parser through the unchanged slice-one machinery + grader (NFR-006).

    ``scenario`` is threaded into the WP06 scenario-parametric run path so the SAME
    machinery grades the run against the selected acceptance source via the
    scenario's injected strategy — no per-source branch here (NFR-005).
    """
    return live_trial.run_live_trial_with_log(
        LiveTrialConfig(),
        driver=driver,
        operator=operator,
        repo_root=repo_root,
        parser_attr=_PARSER_ATTR,
        source=source,
        scenario=scenario,
    )


def run_live_trial_ollama(
    *,
    model: str = DEFAULT_MODEL,
    source: Path | None = None,
    max_tries: int = MAX_TRIES,
    repo_root: Path = _REPO_ROOT,
    operator: OllamaOperator | None = None,
    keep_sandboxes: bool = False,
    scenario: Scenario | None = None,
) -> LiveTrialOutcome:
    """Drive one Ollama-backed live trial end-to-end (T013/T014; FR-001..014).

    The ``operator`` is INJECTABLE (defaults to constructing an
    :class:`OllamaOperator`): WP05 passes a deterministic fake operator so the
    end-to-end path runs in the default suite without a model server.

    ``scenario`` selects which acceptance source the cheap model authors a parser
    for and is graded against; it defaults to the observation scenario so existing
    callers are unchanged (C-004). Passing the intake scenario makes the SAME path
    run the intake trial — the operator authors an intake parser, the in-sandbox
    probe gates the intake batch, and the WP06 scenario-parametric run path grades
    it via the intake strategy. No per-scenario branch (FR-007 / NFR-005). The
    drawer specifics (contract prompt, probe batch/non-empty check, driver goal)
    all come from the scenario's :class:`_DrawerProbe` rubric entry.

    ``source`` defaults to the scenario's committed synthetic source; callers may
    override it (the local real-dump follow-up passes a non-synthetic path, which
    records nothing).

    Flow:

    1. Run the FINAL parser via :func:`live_trial.run_live_trial_with_log` (reuse,
       don't fork) — its verdict is the authority (FR-004).
    2. Independently grade **attempt 1** (un-nagged) through the same unchanged
       machinery + grader (FR-014).
    3. Assemble a :class:`~premura.harness.scoreboard.LiveTrialRunRecord` recording
       ``run_kind="live_trial"`` + the ``operator_model`` / ``driver_model``
       identities (so tiers compare, FR-007) and, for a SYNTHETIC source only,
       persist it + append the scoreboard (WP02). A real source records nothing —
       the no-persist decision is made here and enforced by WP02's guard
       (FR-012 / C-003 / NFR-002).

    Returns a :class:`LiveTrialOutcome`. If the default operator cannot reach the
    model server, returns ``LiveTrialOutcome(model_unavailable=True)`` (it does
    NOT only print).

    ``keep_sandboxes`` retains the kept-sandbox trees on the returned outcome for
    caller inspection, but ONLY for a SYNTHETIC source. A non-synthetic source
    always tears both sandboxes down regardless of this flag, so no real local
    data is left on disk (FR-004 / NFR-002 / NFR-004).
    """
    if scenario is None:
        scenario = observation_scenario()
    probe = _resolve_drawer_probe(scenario)
    if source is None:
        source = scenario.source_path

    if operator is None:
        if not ollama_available():
            return LiveTrialOutcome(model_unavailable=True)
        operator = OllamaOperator(source, model=model, max_tries=max_tries, probe=probe)

    driver = OllamaDriver(model=model, goal=probe.goal)

    # (1) Final run — the authority verdict (reuses the unchanged machinery).
    try:
        final_result = _grade_one(
            operator, driver=driver, source=source, repo_root=repo_root, scenario=scenario
        )
    except OllamaUnavailableError:
        return LiveTrialOutcome(model_unavailable=True)

    # (2) Independently grade attempt 1 (un-nagged) with the SAME grader.
    first_code = operator.first_attempt_code
    first_operator = _FixedCodeOperator(first_code, model=operator.model_id)
    first_result = _grade_one(
        first_operator, driver=driver, source=source, repo_root=repo_root, scenario=scenario
    )

    final_verdict: Verdict = final_result.verdict
    first_verdict: Verdict = first_result.verdict

    record = LiveTrialRunRecord(
        operator_model=operator.model_id,
        driver_model=driver.model_id,
        attempts_used=operator.tries_used,
        first_attempt_verdict=first_verdict,
        final_verdict=final_verdict,
    )

    # (3) Persist — synthetic-only (the no-persist decision is made HERE).
    synthetic = is_synthetic_source(source)
    persisted_dir = persist_run(
        record,
        kept_session_log=final_result.session_log_path,
        verdict=final_verdict,
        is_synthetic=synthetic,
    )
    if synthetic:
        append_scoreboard(
            ScoreboardEntry(
                ts=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
                operator_model=record.operator_model,
                driver_model=record.driver_model,
                attempts_used=record.attempts_used,
                first_attempt_pass=bool(first_verdict["passed"]),
                final_pass=bool(final_verdict["passed"]),
            )
        )

    kept_final_result: LiveTrialResult | None = final_result
    kept_first_result: LiveTrialResult | None = first_result
    # keep_sandboxes is honored ONLY for the synthetic fixture: a kept sandbox
    # holds the parsed source, so retaining one for a NON-synthetic source would
    # leave the operator's real local data on disk after the run — exactly the
    # no-persist rule enforced above for persistence (FR-012 / C-003 / NFR-002).
    # A non-synthetic source therefore always tears both sandboxes down.
    if not (keep_sandboxes and synthetic):
        _teardown_kept_sandbox(final_result)
        _teardown_kept_sandbox(first_result)
        kept_final_result = None
        kept_first_result = None

    return LiveTrialOutcome(
        model_unavailable=False,
        record=record,
        attempts=operator.attempts,
        final_result=kept_final_result,
        first_attempt_result=kept_first_result,
        persisted_run_dir=persisted_dir,
    )


def _teardown_kept_sandbox(result: LiveTrialResult | None) -> None:
    """Remove a kept-sandbox tree left by ``run_live_trial_with_log`` (NFR-004)."""
    if result is None:
        return
    import shutil

    # session_log_path == <sandbox>/data/session_log.duckdb -> remove <sandbox>.
    shutil.rmtree(result.session_log_path.parent.parent, ignore_errors=True)


def _print_verdict(label: str, verdict: Verdict) -> None:
    """Print one three-rule verdict compactly for the CLI."""
    rules = verdict.get("rules", {})
    flags = " ".join(
        f"{name}={'PASS' if rule.get('passed') else 'FAIL'}" for name, rule in rules.items()
    )
    print(f"  {label}: overall={'PASS' if verdict.get('passed') else 'FAIL'}  {flags}")


def _main() -> int:
    """CLI entry: run over the synthetic fixture; never raises into a test (NFR-001)."""
    print(
        f"Live trial: operator={DEFAULT_MODEL}  source={_SYNTHETIC_CSV.name}  max_tries={MAX_TRIES}"
    )
    outcome = run_live_trial_ollama()
    if outcome.model_unavailable:
        print(f"Ollama not reachable at {OLLAMA_URL}. Start it and pull {DEFAULT_MODEL!r}.")
        return 2

    try:
        assert outcome.record is not None  # noqa: S101 - narrowing for the type checker
        print(f"\nattempts used: {outcome.record.attempts_used}")
        _print_verdict("first-attempt", outcome.record.first_attempt_verdict)
        _print_verdict("final", outcome.record.final_verdict)
        if outcome.persisted_run_dir is not None:
            print(f"\nkept run: {outcome.persisted_run_dir}")
        else:
            print("\nreal-data run: nothing persisted (synthetic-only).")
    finally:
        _teardown_kept_sandbox(outcome.final_result)
        _teardown_kept_sandbox(outcome.first_attempt_result)
    return 0


__all__ = [
    "DEFAULT_MODEL",
    "MAX_TRIES",
    "OLLAMA_URL",
    "AttemptRecord",
    "LiveTrialOutcome",
    "OllamaDriver",
    "OllamaOperator",
    "OllamaUnavailableError",
    "is_synthetic_source",
    "ollama_available",
    "run_live_trial_ollama",
]


if __name__ == "__main__":
    raise SystemExit(_main())
