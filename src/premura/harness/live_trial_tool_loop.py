"""Tool-loop live-trial tier — the multiturn, tool-using capability tier (WP04).

This is the tier ABOVE the constrained one-shot floor probe, never a
replacement for it (the spec's premise): the same live trial, run through a
multiturn agent loop in which the operator reads context, writes its parser,
and verifies it with a real sandbox ingest — all through the WP03 bounded tool
contract — so the maintainer agent can compare, per operator model, "what the
model can do in one constrained shot" against "what the model can do with
tools and turns". Binding behavior: ``contracts/tool-loop-tier.md`` §§3–5.

Boundaries this module honours:

* **Local-only** (NFR-001): all chat goes through the WP03 client, whose URL is
  derived from the same validated localhost-only ``OLLAMA_URL`` guard.
* **Synthetic-only persistence** (NFR-002 / C-001): only a committed synthetic
  scenario source persists a record + scoreboard line; ANY other source records
  nothing and always tears its sandboxes down, ``keep_sandboxes`` included.
* **Never blocks CI** (NFR-003 / C-004): no default-suite test reaches a real
  model — the loop is exercised through the injectable chat seam; the real-model
  test is ``live_trial``-marked and excluded by default.
* **Reuse, not fork** (NFR-004): this module is new orchestration only. Grading
  runs through the unchanged ``live_trial.run_live_trial_with_log``; the gate is
  the one-shot tier's ``_gate_parser``; tools/brief/client come from
  ``tool_loop_contract``; persistence goes through ``scoreboard.persist_run`` /
  ``append_scoreboard`` with the WP01 ``tier`` axis.

Run it directly (quickstart.md)::

    uv run python -m premura.harness.live_trial_tool_loop
    OLLAMA_MODEL=qwen2.5-coder:14b LIVE_TRIAL_MAX_TURNS=10 \\
      uv run python -m premura.harness.live_trial_tool_loop

Exit codes: ``0`` ran, ``2`` model unavailable, ``3`` model lacks tool support.
It needs a running Ollama with a TOOL-CAPABLE model pulled.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from premura.harness import live_trial
from premura.harness.live_trial import LiveTrialResult
from premura.harness.live_trial_ollama import (
    _PARSER_DEST_RELPATH,
    _REPO_ROOT,
    _SYNTHETIC_CSV,
    DEFAULT_MODEL,
    OLLAMA_URL,
    AttemptRecord,
    OllamaDriver,
    OllamaUnavailableError,
    _DrawerProbe,
    _FixedCodeOperator,
    _gate_parser,
    _grade_one,
    _print_verdict,
    _teardown_kept_sandbox,
    is_synthetic_source,
    ollama_available,
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
from premura.harness.tool_loop_contract import (
    ToolCallsUnsupportedError,
    ToolRegistration,
    TrialContext,
    assemble_brief,
    build_trial_context,
    default_tool_registry,
    ollama_chat,
    registry_as_chat_tools,
    resolve_drawer_probe,
    resolve_num_ctx,
)

#: Documented default turn cap (contract §6). This module is the env knob's
#: single home; :func:`resolve_max_turns` reads the override at run time.
LIVE_TRIAL_MAX_TURNS = 8

#: The one tool whose first successful call is snapshotted as the FIRST complete
#: parser (FR-006). This is a snapshot HOOK on the loop, not a dispatch branch:
#: dispatch itself stays pure registry lookup (NFR-005); the WP03 handler stays
#: stateless and the loop owns the first-call capture.
_PARSER_WRITER_TOOL = "write_parser"

#: A chat backend is the operator's OUTSIDE boundary (DIRECTIVE_036): the same
#: call shape as :func:`tool_loop_contract.ollama_chat` —
#: ``(messages, *, model, tools, num_ctx) -> message dict``. The default is the
#: real WP03 client; tests (and WP05's edge fixtures) inject a scripted fake.
ChatBackend = Callable[..., dict]


def resolve_max_turns() -> int:
    """Resolve the turn cap from ``LIVE_TRIAL_MAX_TURNS`` (default 8, contract §6).

    Mirrors ``tool_loop_contract.resolve_num_ctx``: a missing, non-integer, or
    non-positive override falls back to the documented default, so the cap is
    always a positive bound and the loop always terminates (FR-005).
    """
    raw = os.environ.get("LIVE_TRIAL_MAX_TURNS")
    if raw is None:
        return LIVE_TRIAL_MAX_TURNS
    try:
        value = int(raw)
    except ValueError:
        return LIVE_TRIAL_MAX_TURNS
    return value if value > 0 else LIVE_TRIAL_MAX_TURNS


# --------------------------------------------------------------------------- #
# ToolLoopOperator — the multiturn loop (contract §3). [T013]
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _ToolLoopTurn:
    """One captured chat turn — a structural ``live_trial.TurnLike`` (m2 FR-3).

    Maps a single entry of the operator's final ``messages`` history to the
    transcript-seam protocol: ``role`` / ``content`` plus the optional per-turn
    telemetry the harness persists. ``model`` is the operator's model id;
    ``tool_name`` is set on tool-result turns, ``None`` otherwise.
    """

    role: str
    content: str
    tool_name: str | None = None
    model: str | None = None
    token_count: int | None = None


class ToolLoopOperator:
    """Multiturn tool-using operator implementing the ``live_trial.Operator`` protocol.

    The whole chat conversation runs INSIDE :meth:`operate` — the harness calls it
    after the sandbox is built and before the ingest/grade steps, so the loop's
    only write surface is the sandbox tree (through the WP03 bounded tools; C-005
    holds by construction via the registry, FR-004). It never opens the session
    log — the harness remains the sole log writer (FR-021 inheritance); per-turn
    telemetry is collected in ``attempts`` for the harness to append POST-run.

    Loop protocol (contract §3, exact):

    * one assistant response = ONE turn, always — a malformed or unknown tool
      call consumes its turn with a corrective tool message fed back;
    * a response with no tool calls ends the working phase → the manifest-blind
      self-reconcile gate runs on the parser currently on disk; gate fail with
      turns remaining feeds the verbatim feedback back and continues;
    * gate pass or cap exhausted → the trial ends; the parser-on-disk (or none)
      is what gets graded (FR-005 — the cap always terminates into a graded
      record, never an exception).

    What propagates: :class:`OllamaUnavailableError` and
    :class:`ToolCallsUnsupportedError` are NEVER swallowed here — they escape
    ``operate`` so the entry point maps them to explicit outcome states
    (NFR-006) instead of a half-graded trial.

    The loop body contains no per-drawer and no per-tool branches beyond registry
    dispatch (NFR-005): drawer specifics come from the scenario's ``probe`` and
    the tool surface from :func:`default_tool_registry`.
    """

    def __init__(
        self,
        source: Path,
        *,
        model: str = DEFAULT_MODEL,
        max_turns: int | None = None,
        num_ctx: int | None = None,
        probe: _DrawerProbe | None = None,
        chat: ChatBackend | None = None,
    ) -> None:
        self.source = source
        self.model_id = model
        self.max_turns = max_turns if max_turns is not None else resolve_max_turns()
        self.num_ctx = num_ctx if num_ctx is not None else resolve_num_ctx()
        # Scenario-parametric drawer probe (FR-008): default observation, exactly
        # like the one-shot operator — never an ``if drawer`` branch in the loop.
        self.probe = probe if probe is not None else resolve_drawer_probe(observation_scenario())
        self._chat: ChatBackend = chat if chat is not None else ollama_chat
        self.turns_used = 0
        self.first_parser_code = ""
        self.attempts: list[AttemptRecord] = []
        #: The final chat history of the last :meth:`operate` run — the system
        #: brief plus every assistant/tool/user turn, in order. ``transcript()``
        #: maps it 1:1 to :class:`live_trial.TurnLike` items for the harness to
        #: persist post-run (m2 FR-3). Empty until the loop runs.
        self.messages: list[dict] = []
        #: The sandbox the last trial ran in — kept so the entry point can tear it
        #: down when an error propagates out of ``operate`` mid-conversation.
        self.last_sandbox: Sandbox | None = None

    def operate(self, sandbox: Sandbox, goal: str) -> None:
        """Run the multiturn tool loop inside the already-built sandbox (FR-005).

        On every exit (gate pass, cap exhaustion, or a propagating transport
        error) the working-phase warehouse state is cleared: the ``run_ingest``
        verification tool loads the sandbox warehouse during the conversation,
        but the verdict-bearing ingest the harness runs AFTER ``operate()`` must
        measure a fresh load — the same condition the one-shot tier grades under,
        or the tiers' ``loaded`` verdicts stop being comparable (FR-007).
        """
        self.last_sandbox = sandbox
        try:
            self._converse(sandbox, goal)
        finally:
            sandbox.warehouse_path.unlink(missing_ok=True)

    def _converse(self, sandbox: Sandbox, goal: str) -> None:
        """The loop proper (contract §3); see :meth:`operate` for the exit contract."""
        context = build_trial_context(sandbox, source=self.source)
        registry = default_tool_registry()
        chat_tools = registry_as_chat_tools(registry)
        sandbox_src = sandbox.root / "src"
        parser_dest = sandbox.root / _PARSER_DEST_RELPATH

        brief = assemble_brief(self.probe, goal=goal, source=self.source, num_ctx=self.num_ctx)
        messages: list[dict] = [{"role": "system", "content": brief}]
        # Expose the live chat history so transcript() reflects the FINAL state of
        # the conversation regardless of which exit the loop takes (m2 FR-3).
        self.messages = messages

        for turn in range(1, self.max_turns + 1):
            self.turns_used = turn
            reply = self._chat(
                messages, model=self.model_id, tools=chat_tools, num_ctx=self.num_ctx
            )
            tool_calls = list(reply.get("tool_calls") or [])
            assistant: dict = {"role": "assistant", "content": str(reply.get("content") or "")}
            if tool_calls:
                assistant["tool_calls"] = tool_calls
            messages.append(assistant)

            if tool_calls:
                # Execute every call of this ONE turn, in order; malformed or
                # unknown calls yield a corrective tool message (turn consumed).
                for call in tool_calls:
                    messages.append(self._execute_tool_call(call, registry, context))
                continue

            # No tool calls → working phase over for this round: run the
            # manifest-blind self-reconcile gate on the parser currently on disk.
            gate = _gate_parser(sandbox_src, self.source, self.probe)
            code = parser_dest.read_text(encoding="utf-8") if parser_dest.exists() else ""
            self.attempts.append(
                AttemptRecord(
                    index=turn,
                    self_reconciliation=gate.self_reconciliation,
                    parser_error=gate.parser_error,
                    code=code,
                )
            )
            if gate.passed:
                return
            if turn < self.max_turns:
                # Verbatim gate feedback re-enters the conversation (contract §3).
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"The harness gate FAILED your current parser:\n{gate.feedback}\n"
                            "Fix it with your tools, then reply with no tool calls when done."
                        ),
                    }
                )
        # Cap exhausted: the parser on disk (or none) is graded as-is by the
        # entry point — a deterministic FAIL is a legitimate capability-floor
        # finding, never an exception (FR-005 / SC-005).

    def transcript(self) -> list[_ToolLoopTurn]:
        """Map the final chat history 1:1 to :class:`live_trial.TurnLike` items (FR-3).

        Reflects the FINAL state of the conversation — the system brief and every
        assistant / tool / user turn captured during the last :meth:`operate`, in
        order. Roles pass through to the chat-API vocabulary; a tool-result turn
        carries the ``tool_name`` of the call it answered (the ``name`` field the
        loop tagged onto it). The operator never writes the log — the harness reads
        this and persists it post-run (FR-021 inheritance).
        """
        return [
            _ToolLoopTurn(
                role=str(message.get("role") or ""),
                content=str(message.get("content") or ""),
                model=self.model_id,
                tool_name=(str(message["name"]) if message.get("name") else None),
            )
            for message in self.messages
        ]

    def _execute_tool_call(
        self,
        call: dict,
        registry: dict[str, ToolRegistration],
        context: TrialContext,
    ) -> dict:
        """Dispatch one tool call via the registry; corrective message on misuse.

        Pure registry dispatch (NFR-005): unknown names and unparseable argument
        sets return a corrective tool-result STRING (the turn is already
        consumed); they never raise. The single named exception is the FR-006
        snapshot hook: the FIRST successful ``write_parser`` call's ``code``
        argument is captured as the first complete parser.
        """
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict):
            return {
                "role": "tool",
                "content": (
                    "MALFORMED tool call: expected {'function': {'name', 'arguments'}}. "
                    "This turn was consumed; emit valid tool calls."
                ),
            }
        name = str(function.get("name") or "")
        registration = registry.get(name)
        if registration is None:
            known = ", ".join(sorted(registry))
            return {
                "role": "tool",
                "name": name,
                "content": (
                    f"UNKNOWN tool {name!r}. This turn was consumed; "
                    f"the only available tools are: {known}."
                ),
            }
        args = _normalize_tool_args(function.get("arguments"))
        if args is None:
            return {
                "role": "tool",
                "name": name,
                "content": (
                    f"MALFORMED arguments for tool {name!r}: expected a JSON object. "
                    "This turn was consumed; pass arguments matching the tool's schema."
                ),
            }
        result = registration.handler(args, context)
        # FR-006 snapshot hook (see _PARSER_WRITER_TOOL): first successful
        # write_parser call's body becomes the first complete parser.
        if name == _PARSER_WRITER_TOOL and not self.first_parser_code:
            self.first_parser_code = str(args.get("code", ""))
        # The tool name rides on the tool-result message (chat-API ``name`` field)
        # so transcript() can attribute the result turn to its call (m2 FR-3).
        return {"role": "tool", "name": name, "content": result}


def _normalize_tool_args(raw: object) -> dict | None:
    """Normalize tool-call arguments to a dict; ``None`` means malformed.

    Backends differ: Ollama serves a dict, other transports a JSON string. A
    missing argument set means "no arguments" (e.g. ``run_ingest``); anything
    that cannot become a JSON object is a malformed call (turn still consumed).
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


# --------------------------------------------------------------------------- #
# ToolLoopOutcome + the tier entry point (contract §§4–5). [T014]
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ToolLoopOutcome:
    """Returnable outcome of a tool-loop trial — exactly one state (NFR-006).

    Every started trial ends as exactly one of {complete graded ``record``,
    ``model_unavailable``, ``tool_calls_unsupported``}; no path raises out of
    the entry point after the trial starts. ``tool_calls_unsupported`` is the
    NEW state beside the one-shot tier's ``model_unavailable``: the endpoint is
    reachable but the loaded model's template cannot accept tools. ``turns`` is
    the per-gate-round telemetry; the kept results survive only for synthetic +
    ``keep_sandboxes`` runs (NFR-002).
    """

    model_unavailable: bool = False
    tool_calls_unsupported: bool = False
    record: LiveTrialRunRecord | None = None
    turns: list[AttemptRecord] = field(default_factory=list)
    final_result: LiveTrialResult | None = None
    first_attempt_result: LiveTrialResult | None = None
    persisted_run_dir: Path | None = None


def _teardown_trial_sandbox(operator: ToolLoopOperator) -> None:
    """Remove the trial sandbox after a mid-conversation failure (NFR-002).

    When the chat backend fails INSIDE ``operate``, the kept-sandbox run path
    never returns a result to tear down — the operator's remembered sandbox is
    the only handle left, so the entry point removes it here.
    """
    if operator.last_sandbox is not None:
        operator.last_sandbox.teardown()


def run_live_trial_tool_loop(
    *,
    model: str = DEFAULT_MODEL,
    source: Path | None = None,
    max_turns: int | None = None,
    repo_root: Path = _REPO_ROOT,
    operator: ToolLoopOperator | None = None,
    keep_sandboxes: bool = False,
    scenario: Scenario | None = None,
) -> ToolLoopOutcome:
    """Drive one tool-loop trial end-to-end into a tier-tagged result (SC-001).

    Mirrors ``run_live_trial_ollama`` exactly — same machinery, new orchestration
    (NFR-004). ``scenario`` selects the acceptance drawer (default observation;
    the intake scenario runs through the identical path via its registered probe,
    FR-008); ``source`` defaults to the scenario's committed synthetic source.
    ``operator`` is injectable (DIRECTIVE_036): tests pass one with a scripted
    chat backend so the whole loop runs in the default suite.

    Flow:

    1. Final run via the unchanged ``live_trial.run_live_trial_with_log`` — the
       operator's whole multiturn loop runs inside it; its verdict is the final
       authority.
    2. Post-run, append the loop's per-gate-round telemetry to the kept log
       (harness-written ``record_live_trial_attempt`` rows — same block as the
       one-shot module; the operator never touched the log).
    3. Independently grade the FIRST ``write_parser`` body through the SAME
       machinery via a fixed-code operator (FR-006). No parser ever written →
       the empty body grades as the machinery's deterministic absent-parser
       FAIL (SC-005) — both verdicts always exist.
    4. Assemble the ``tier="tool_loop"`` record; persist + append the scoreboard
       ONLY for a synthetic source (NFR-002) — alongside, never overwriting, the
       one-shot floor rows (FR-007).

    Returns exactly one of the three :class:`ToolLoopOutcome` states (NFR-006):
    an unreachable endpoint → ``model_unavailable``; a tools-incapable model →
    ``tool_calls_unsupported`` (both persist nothing, sandboxes torn down); else
    the complete graded record.

    ``keep_sandboxes`` retains the kept-sandbox trees on the outcome ONLY for a
    synthetic source: a kept sandbox holds the parsed source, so retaining one
    for a non-synthetic source would leave the operator's real local data on
    disk after the run (NFR-002) — a non-synthetic source always tears both
    sandboxes down.
    """
    if scenario is None:
        scenario = observation_scenario()
    probe = resolve_drawer_probe(scenario)
    if source is None:
        source = scenario.source_path

    if operator is None:
        # Availability probe, like the one-shot: unreachable → explicit outcome
        # before any sandbox is built (NFR-006).
        if not ollama_available():
            return ToolLoopOutcome(model_unavailable=True)
        operator = ToolLoopOperator(source, model=model, max_turns=max_turns, probe=probe)

    driver = OllamaDriver(model=model, goal=probe.goal)

    # (1) Final run — the operator's whole loop runs inside the unchanged path.
    try:
        final_result = _grade_one(
            operator, driver=driver, source=source, repo_root=repo_root, scenario=scenario
        )
    except OllamaUnavailableError:
        _teardown_trial_sandbox(operator)
        return ToolLoopOutcome(model_unavailable=True)
    except ToolCallsUnsupportedError:
        _teardown_trial_sandbox(operator)
        return ToolLoopOutcome(tool_calls_unsupported=True)

    # (2) Post-run telemetry: the HARNESS appends the per-turn rows to the kept
    #     log (the operator never opened it — sole-log-writer inheritance).
    log_conn = live_trial.store.connect(final_result.session_log_path)
    try:
        for attempt in operator.attempts:
            live_trial.store.record_live_trial_attempt(
                log_conn,
                session_id=final_result.session_id,
                attempt_index=attempt.index,
                self_reconciliation=attempt.self_reconciliation,
                parser_error=attempt.parser_error,
            )
    finally:
        log_conn.close()

    # (3) Independent first-parser grade through the SAME machinery (FR-006).
    #     An empty body (no write_parser ever) still grades: the machinery's
    #     absent-parser path yields the deterministic FAIL (SC-005).
    first_operator = _FixedCodeOperator(operator.first_parser_code, model=operator.model_id)
    first_result = _grade_one(
        first_operator, driver=driver, source=source, repo_root=repo_root, scenario=scenario
    )

    final_verdict: Verdict = final_result.verdict
    first_verdict: Verdict = first_result.verdict

    record = LiveTrialRunRecord(
        operator_model=operator.model_id,
        driver_model=driver.model_id,
        attempts_used=operator.turns_used,
        first_attempt_verdict=first_verdict,
        final_verdict=final_verdict,
        tier="tool_loop",
    )

    # (4) Persist — synthetic-only (the no-persist decision is made HERE),
    #     tier-tagged alongside the one-shot floor (FR-007 / NFR-002).
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
                tier="tool_loop",
            )
        )

    kept_final_result: LiveTrialResult | None = final_result
    kept_first_result: LiveTrialResult | None = first_result
    # keep_sandboxes is honored ONLY for a synthetic source: a kept sandbox holds
    # the parsed source, so retaining one for a NON-synthetic source would leave
    # the operator's real local data on disk after the run (NFR-002).
    if not (keep_sandboxes and synthetic):
        _teardown_kept_sandbox(final_result)
        _teardown_kept_sandbox(first_result)
        kept_final_result = None
        kept_first_result = None

    return ToolLoopOutcome(
        model_unavailable=False,
        tool_calls_unsupported=False,
        record=record,
        turns=operator.attempts,
        final_result=kept_final_result,
        first_attempt_result=kept_first_result,
        persisted_run_dir=persisted_dir,
    )


# --------------------------------------------------------------------------- #
# CLI (quickstart.md). [T015]
# --------------------------------------------------------------------------- #


def _main() -> int:
    """CLI entry: run over the synthetic fixture; exit 0 ran / 2 unreachable / 3 no tools."""
    max_turns = resolve_max_turns()
    print(
        f"Tool-loop live trial: operator={DEFAULT_MODEL}  "
        f"source={_SYNTHETIC_CSV.name}  max_turns={max_turns}"
    )
    outcome = run_live_trial_tool_loop()
    if outcome.model_unavailable:
        print(f"Ollama not reachable at {OLLAMA_URL}. Start it and pull {DEFAULT_MODEL!r}.")
        return 2
    if outcome.tool_calls_unsupported:
        print(
            f"Model {DEFAULT_MODEL!r} does not support tool calls. "
            "Pull a tool-capable model (set OLLAMA_MODEL)."
        )
        return 3

    try:
        assert outcome.record is not None  # noqa: S101 - narrowing for the type checker
        print(f"\nturns used: {outcome.record.attempts_used}")
        _print_verdict("first-parser", outcome.record.first_attempt_verdict)
        _print_verdict("final", outcome.record.final_verdict)
        if outcome.persisted_run_dir is not None:
            print(f"\nkept run (tier=tool_loop): {outcome.persisted_run_dir}")
        else:
            print("\nreal-data run: nothing persisted (synthetic-only).")
    finally:
        _teardown_kept_sandbox(outcome.final_result)
        _teardown_kept_sandbox(outcome.first_attempt_result)
    return 0


__all__ = [
    "LIVE_TRIAL_MAX_TURNS",
    "ChatBackend",
    "ToolCallsUnsupportedError",
    "ToolLoopOperator",
    "ToolLoopOutcome",
    "resolve_max_turns",
    "run_live_trial_tool_loop",
]


if __name__ == "__main__":
    raise SystemExit(_main())
